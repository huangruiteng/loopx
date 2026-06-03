from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_prompt import render_cli_preflight, render_quota_guard_command, render_quota_spend_command


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."


def build_heartbeat_prompt(
    *,
    goal_id: str,
    active_state: Path,
    material_queue_rule: str | None = None,
    permission_rule: str | None = None,
    compact: bool = False,
) -> dict[str, Any]:
    active_state_text = str(active_state.expanduser())
    resolved_material_rule = material_queue_rule or DEFAULT_MATERIAL_QUEUE_RULE
    resolved_permission_rule = permission_rule or DEFAULT_PERMISSION_RULE
    quota_guard_command = render_quota_guard_command(goal_id)
    quota_spend_command = render_quota_spend_command(goal_id, source="heartbeat")
    cli_preflight = render_cli_preflight()
    task_body_renderer = render_compact_heartbeat_task_body if compact else render_heartbeat_task_body
    task_body = task_body_renderer(
        goal_id=goal_id,
        active_state=active_state_text,
        cli_preflight=cli_preflight,
        quota_guard_command=quota_guard_command,
        quota_spend_command=quota_spend_command,
        material_queue_rule=resolved_material_rule,
        permission_rule=resolved_permission_rule,
    )
    expanded_prompt_command = f"goal-harness heartbeat-prompt --goal-id {goal_id} --active-state {active_state_text}"
    return {
        "ok": True,
        "goal_id": goal_id,
        "active_state": active_state_text,
        "compact": compact,
        "expanded_prompt_command": expanded_prompt_command,
        "quota_guard_command": quota_guard_command,
        "quota_spend_command": quota_spend_command,
        "cli_preflight": cli_preflight,
        "material_queue_rule": resolved_material_rule,
        "permission_rule": resolved_permission_rule,
        "task_body": task_body,
    }


def render_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    material_queue_rule: str,
    permission_rule: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

This heartbeat body is the generic Goal Harness lifecycle. Do not add
project-specific branching to the automation prompt. Put project-specific
policy in the Goal Harness registry, active-state sections, adapter output, or
narrow public/private boundary rules; if a new lifecycle rule is needed, update
`goal-harness heartbeat-prompt` so all projects inherit it.

Before spending delivery compute, first make the Goal Harness CLI reachable in
this automation shell, then run the quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If that preflight still fails, do not do implementation work, adapter work,
file edits, research, project exploration, or quota spend in this turn. Return
a quiet heartbeat `DONT_NOTIFY` response with the exact preflight failure
reason.

If the result says `should_run=false`:

- If the payload says `state=operator_gate`, treat the gate as a user/controller
  interaction, not as a silent skip. Read `gate_prompt`, `operator_question`,
  `recommended_action`, `next_handoff_condition`, `missing_gates`,
  `user_todo_summary`, and `agent_todo_summary` from the payload. If the same
  unresolved gate has not already been asked in the recent visible thread,
  return heartbeat `NOTIFY`
  with one concise Chinese question that lists the gate and the expected reply
  format. If `user_todo_summary.open_count > 0`, the notification must list the
  existing open user todos even when there are no newly discovered user actions;
  never summarize this case as "no new user action". Do not execute
  `agent_command`, adapter work, write-control, production actions, or the
  gated path while asking.
- If the payload says `notify_user_on_open_todo=true`, treat the existing open
  `user_todo_summary` as a blocker-push opportunity, not as a silent skip. This
  is especially important for `state=focus_wait`, `state=waiting`, and
  `waiting_on=external_evidence`, where a short user/owner answer can unlock a
  quiet project. If the same blocker ask has not already been surfaced in the
  recent visible thread, return heartbeat `NOTIFY` with one concise Chinese ask
  listing at most three `first_open_items`, the `open_todo_notify_reason`, and
  the expected reply format: `done`, `defer/not now`, or a new evidence
  link/date/conclusion. Do not do implementation work, adapter work, file
  edits, research, project exploration, or quota spend for that blocker-push
  turn. If the same blocker was already surfaced recently, return a quiet
  `DONT_NOTIFY` skip reason and do not append quota spend.
- If the payload also says `safe_bypass_allowed=true` and the same gate has
  already been surfaced, the gate blocks only the gated delivery path. You may
  read the active state and do exactly one bounded safe-bypass step from the
  Priority Stack, such as read-only steering analysis, documentation, or another
  P0/P1 item that does not depend on that gate. If you do a safe-bypass step,
  validate it, write back progress/critic/next action, optionally refresh state,
  append exactly one spend event, and report compactly. If
  `user_todo_summary.open_count > 0`, that report must include the existing
  open user todos and must not say there is "no new user action". If
  `agent_todo_summary.open_count > 0`, the report should also name the first
  safe agent todo it can execute next. If no useful safe-bypass step exists,
  report the pending gate compactly instead of doing work.
- Otherwise, do not do implementation work, adapter work, file edits, research,
  or project exploration in this turn. Return a quiet heartbeat `DONT_NOTIFY`
  response with the skip reason.

If the result says `should_run=true`:

1. Read the active state, Priority Stack, recent progress, and critic.
   When you inspect current Goal Harness routing, use the current status queue:
   `attention_queue.items` and each item's `project_asset` are authoritative
   for owner, gate, waiting party, and next action. Treat
   `run_history.latest_runs` as evidence and drill-down only; it may be limited
   by status command limits or filters, so do not decide whether a gate is
   pending or approved from latest runs alone. Also inspect any
   `user_todo_summary` from the guard/status payload. If an open user/owner
   todo is the current blocker that can unlock a gate, `focus_wait`, or
   external-evidence wait, handle it before delivery as the same blocker-push
   opportunity: short `NOTIFY`, at most three items, no implementation work,
   and no quota spend for that blocker-push turn.
   Also read `heartbeat_recommendation` from the quota payload before inventing
   local automation behavior. If it says `recommended_mode=run_first_read_only_map`,
   run exactly its `command` as a real read-only map, not another dry-run, then
   validate/save the `read_only_project_map` result, sync or refresh state if
   needed, append exactly one heartbeat spend, and `NOTIFY`. If it says
   `recommended_mode=mapped_noop_if_unchanged` with `stop_if_unchanged=true`,
   and you find no new user instruction, owner evidence, agent todo, stale
   source, or safe handoff, return a quiet `DONT_NOTIFY` no-op: do not run
   another dry-run, do not edit files, and do not append quota spend.
2. Run a short steering audit before choosing work: list at least three
   plausible next-action candidates across different P0/P1/P2 lanes when
   useful; if the same topic has consumed several recent delivery slices, apply
   a continuation check and state why continuing still wins; keep compute quota
   separate from focus quota; record any losing high-value candidate that should
   not be forgotten. Include a product bottleneck lens: ask whether the core
   goal is currently bottlenecked by user experience, agent capability,
   evidence quality, adapter readiness, or priority-rule gaps, and promote one
   concrete bottleneck candidate when it should outrank the nearest local TODO.
3. Run the no-progress self-stop check before choosing delivery work. Inspect
   recent active-state progress and run history for consecutive eligible
   heartbeat turns. Count a turn as no-progress only when it produced no
   substantive artifact, no adapter or implementation progress, no new gate or
   user decision, no new validation signal, and only repeated
   status/brief-check/compact-checkpoint state edits. If 5 consecutive eligible
   heartbeats are no-progress loops, delete or pause this heartbeat automation
   through the Codex App automation management path, do not append a quota spend
   for that self-cancel turn, and return `NOTIFY` explaining that the automation
   was cancelled because it was spinning without progress.
4. Choose exactly one bounded, verifiable step from that audit.
5. Do that step only. Keep public/private boundaries intact. Public-safe repo
   publication is not an operator gate by itself: for routine public project
   work, commit, push, and PR creation may proceed autonomously after validation
   and a clean public/private boundary scan. Stop and surface a user/controller
   gate only for private or company-internal material, credentials, destructive
   git operations, production actions, or repository rules that explicitly
   require review.
6. Run the smallest useful validation.
7. Write back changed files, validation, critic, and next action to the active
   state. If the step discovers a concrete user/owner action, do not hide it in
   `Next Action`, a review doc, or chat. Add it to the active-state user todo
   queue with:

   ```bash
   goal-harness todo add --goal-id {goal_id} --role user --text "<public-safe user/owner action>"
   ```

   Use `--role agent` for project-agent follow-up work.
   For the full field contract, see `docs/project-agent-todo-contract.md` in
   the Goal Harness checkout.
8. If the dashboard or controller needs to see a state-only update, run:

   ```bash
   goal-harness refresh-state --goal-id {goal_id}
   ```

9. After validation and required state refresh are complete, append exactly one
   spend event:

   ```bash
   {quota_spend_command}
   ```

   Do not append spend for quiet `should_run=false` skips, preflight failures,
   pure dry-run previews, or duplicate accounting attempts. If
   `should_run=false` but `safe_bypass_allowed=true` and you actually completed
   a bounded safe-bypass step, append this same spend event once after
   validation/writeback.

10. Return a compact final report. Use heartbeat `NOTIFY` only for meaningful
    user visibility, such as a committed artifact, a user gate, a real blocker,
    or the automation self-stop. Otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_compact_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    material_queue_rule: str,
    permission_rule: str,
) -> str:
    expanded_prompt_command = f"goal-harness heartbeat-prompt --goal-id {goal_id} --active-state {active_state}"
    return f"""Advance `{goal_id}` using `{active_state}`.

This compact Goal Harness heartbeat body keeps project-specific branches out of
the automation prompt. Put local policy in registry, active state, adapter, or
boundary rules. Expanded lifecycle contract:
`{expanded_prompt_command}`; inspect it for ambiguous edge branches.

Before delivery, make CLI reachable; run quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If preflight fails: quiet `DONT_NOTIFY` exact failure; no implementation,
adapter work, file edits, research, exploration, or spend.

If `should_run=false`:
- `state=operator_gate` or `notify_user_on_open_todo=true`: blocker-push. If
  not surfaced recently, return one concise Chinese `NOTIFY` with the gate or
  up to three open user todos/first_open_items, reason, and expected reply
  format (`done`, `defer/not now`, or evidence link/date/conclusion). No
  delivery or spend.
- `safe_bypass_allowed=true` after the same gate was already surfaced: do at
  most one bounded gate-independent safe-bypass step; validate, write back,
  refresh if needed, and spend once only if real work completed.
- Otherwise quiet `DONT_NOTIFY` with the skip reason; no work or spend.

If `should_run=true`:
1. Read active state, Priority Stack, progress, critic,
   `attention_queue.items` / `project_asset`, and guard `user_todo_summary`.
   Treat `run_history.latest_runs` as drill-down only.
2. Before delivery, surface open user/owner todo that can unlock a gate,
   `focus_wait`, or external-evidence wait: short Chinese `NOTIFY`, no work or
   spend.
3. Follow `heartbeat_recommendation` before inventing behavior:
   `run_first_read_only_map` means run exact real-map command, then
   validate/save/refresh/spend/`NOTIFY`; `mapped_noop_if_unchanged` plus
   `stop_if_unchanged=true` means quiet no-op if there is no new instruction,
   owner evidence, agent todo, stale source, or safe handoff.
4. Run a steering audit before choosing work: compare at least three P0/P1/P2
   candidates when useful, apply continuation checks, keep compute quota
   separate from focus quota, include product-bottleneck lens, record any
   losing high-value candidate.
5. Run the no-progress self-stop check: if 5 consecutive eligible heartbeats
   only repeat status/brief checks with no artifact, implementation/adapter
   progress, gate/user decision, or validation signal, pause/delete automation,
   `NOTIFY`, no spend.
6. Choose one bounded, verifiable step. Public-safe commit, push, and
   PR creation may proceed after validation and clean scan. Stop for
   private/company-internal material, credentials, destructive git, production
   actions, or explicit repo review rules.
7. Validate; write files/validation/critic/next action to active state;
   use `goal-harness todo add --goal-id {goal_id} --role user|agent` for
   blockers/follow-ups, not prose.
8. Refresh state if dashboard/controller needs it.
9. After completed delivery or safe-bypass work, append exactly one spend event:

```bash
{quota_spend_command}
```

Do not append spend for quiet skips, preflight failures, blocker-push asks,
pure dry-runs, self-cancel turns, or duplicate accounting attempts.

Return compactly. Use heartbeat `NOTIFY` only for committed artifact, user gate,
real blocker, or self-stop; otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_heartbeat_prompt_markdown(payload: dict[str, Any]) -> str:
    style = "compact " if payload.get("compact") else ""
    return f"""# Heartbeat Automation Prompt

Copy this {style}task body into a Codex App heartbeat automation.

````text
{payload.get("task_body", "")}
````

## Generator Inputs

- goal_id: `{payload.get("goal_id")}`
- active_state: `{payload.get("active_state")}`
- compact: `{payload.get("compact")}`
- expanded_prompt_command: `{payload.get("expanded_prompt_command")}`
- quota_guard_command: `{payload.get("quota_guard_command")}`
- quota_spend_command: `{payload.get("quota_spend_command")}`
- cli_preflight: `{payload.get("cli_preflight")}`
"""
