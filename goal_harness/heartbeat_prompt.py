from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_prompt import render_cli_preflight, render_quota_guard_command, render_quota_spend_command


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."


def build_heartbeat_prompt(
    *,
    goal_id: str,
    active_state: Path | None = None,
    active_state_source: str = "explicit",
    resolved_active_state: Path | None = None,
    material_queue_rule: str | None = None,
    permission_rule: str | None = None,
    compact: bool = False,
    brief: bool = False,
    cli_bin: str = "goal-harness",
) -> dict[str, Any]:
    effective_resolved_active_state = resolved_active_state or active_state
    active_state_text = str(active_state.expanduser()) if active_state else "the registry-declared active state"
    if active_state:
        resolved_active_state_source = active_state_source
    else:
        resolved_active_state_source = "registry" if active_state_source == "explicit" else active_state_source
    active_state_arg = f" --active-state {active_state_text}" if active_state else ""
    resolved_material_rule = material_queue_rule or DEFAULT_MATERIAL_QUEUE_RULE
    resolved_permission_rule = permission_rule or DEFAULT_PERMISSION_RULE
    quota_guard_command = render_quota_guard_command(goal_id, cli_bin=cli_bin)
    quota_spend_command = render_quota_spend_command(goal_id, source="heartbeat", cli_bin=cli_bin)
    cli_preflight = render_cli_preflight(cli_bin=cli_bin)
    expanded_prompt_command = f"{cli_bin} heartbeat-prompt --goal-id {goal_id}{active_state_arg}"
    compact_prompt_command = f"{cli_bin} heartbeat-prompt --compact --goal-id {goal_id}{active_state_arg}"
    if brief:
        task_body_renderer = render_brief_heartbeat_task_body
    elif compact:
        task_body_renderer = render_compact_heartbeat_task_body
    else:
        task_body_renderer = render_heartbeat_task_body
    task_body = task_body_renderer(
        goal_id=goal_id,
        active_state=active_state_text,
        cli_preflight=cli_preflight,
        quota_guard_command=quota_guard_command,
        quota_spend_command=quota_spend_command,
        material_queue_rule=resolved_material_rule,
        permission_rule=resolved_permission_rule,
        cli_bin=cli_bin,
        expanded_prompt_command=expanded_prompt_command,
        compact_prompt_command=compact_prompt_command,
    )
    return {
        "ok": True,
        "goal_id": goal_id,
        "active_state": active_state_text,
        "active_state_source": resolved_active_state_source,
        "resolved_active_state": str(effective_resolved_active_state.expanduser())
        if effective_resolved_active_state
        else None,
        "compact": compact,
        "brief": brief,
        "cli_bin": cli_bin,
        "expanded_prompt_command": expanded_prompt_command,
        "compact_prompt_command": compact_prompt_command,
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
    cli_bin: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

This heartbeat body is the generic Goal Harness lifecycle. Do not add
project-specific branching to the automation prompt. Put project-specific
policy in the Goal Harness registry, active-state sections, adapter output,
`quota should-run.goal_boundary`, or boundary rules; if a new lifecycle rule is
needed, update `goal-harness heartbeat-prompt` so all projects inherit it.

Before spending delivery compute, first make the Goal Harness CLI reachable and
run the quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If that preflight still fails, do no implementation, adapter, file edit,
research, exploration, or spend; return quiet `DONT_NOTIFY` with exact failure.

If the result says `should_run=false`:

- If `state=operator_gate`, treat it as a user/controller interaction. Read
  `gate_prompt`, `operator_question`, `recommended_action`,
  `next_handoff_condition`, `missing_gates`, `user_todo_summary`, and
  `agent_todo_summary`. If not surfaced recently, return heartbeat `NOTIFY`
  with one concise Chinese question listing the gate and expected reply format.
  If `user_todo_summary.open_count > 0`, list existing open user todos even
  when no new user actions were discovered; never summarize this case as "no
  new user action". Do not execute `agent_command`, adapter work,
  write-control, production actions, or the gated path while asking.
- If `notify_user_on_open_todo=true`, treat existing open `user_todo_summary`
  as a blocker-push opportunity, not a silent skip. For `state=focus_wait`,
  `state=waiting`, and `waiting_on=external_evidence`, a short user/owner
  answer can unlock the project. If not surfaced recently, return heartbeat
  `NOTIFY` with one concise Chinese ask listing at most three
  `first_open_items`, `open_todo_notify_reason`, and expected reply format:
  `done`, `defer/not now`, or a new evidence link/date/conclusion. No
  implementation, adapter work, edits, research, exploration, or spend for
  that blocker-push turn. If already surfaced recently, return quiet
  `DONT_NOTIFY` and do not append quota spend.
- If the payload also says `safe_bypass_allowed=true` and the same gate has
  already been surfaced, the gate blocks only the gated delivery path. You may
  do exactly one bounded safe-bypass step from the Priority Stack that does not
  depend on that gate; validate, write back, optionally refresh, spend once, and
  report compactly. If `user_todo_summary.open_count > 0`, that report must
  include the existing open user todos and must not say there is "no new user
  action". If no useful safe-bypass step exists, report the pending gate.
- If `waiting_on=external_evidence` or `state=waiting`, and this automation is
  explicitly a monitor, run at most one bounded read-only observation poll using
  project-approved status/log/metric/marker surfaces named in active state,
  `recommended_action`, or `goal_boundary.next_probe`. Unchanged evidence:
  quiet `DONT_NOTIFY`, no edits, no spend. New eval/fail/complete/blocker/
  approval/CI/deploy/data evidence: report, write back only allowed canonical
  state/board/ledger, add todos if needed, then spend once after validation.
  Still do not launch/stop/restart/sync/design code or mutate production unless
  `should_run=true` or the user explicitly authorizes it.
- Otherwise, do not do implementation work, adapter work, file edits, research,
  or project exploration in this turn. Return a quiet heartbeat `DONT_NOTIFY`
  response with the skip reason.

If the result says `should_run=true`:

1. Read the active state, Priority Stack, recent progress, and critic.
   When you inspect current Goal Harness routing, use the current status queue:
   `attention_queue.items` and each item's `project_asset` are authoritative
   for owner, gate, waiting party, and next action. If `project_asset` is absent
   or legacy/raw fallback, raw queue fields are not owner/gate/stop authority. Treat
   `run_history.latest_runs` as evidence and drill-down only; it may be limited
   by status command limits or filters, so do not decide whether a gate is
   pending or approved from latest runs alone. Also inspect `goal_boundary` and
   guard `user_todo_summary`. Stop for an open user/owner todo only when it
   belongs to this goal's guard payload or current project asset and blocks the
   selected path; then use the blocker-push pattern above. Dependency or
   sibling-goal todos found in `attention_queue.items` should be recorded as
   dependency blockers; they must not consume the whole eligible turn. Choose a
   gate-independent P0/P1/P2 candidate for this goal when one exists.
   If `effective_action=outcome_floor_recovery` or
   `recovery_delivery_allowed=true` or
   `safe_bypass_kind=outcome_floor_recovery`, produce the required
   ranker/cross-domain evidence artifact named by `must_advance`, or write back
   the concrete blocker. Do not fall through to ordinary delivery,
   surface propagation, or synthetic-only chains.
   Also read `heartbeat_recommendation` from the quota payload before inventing
   local automation behavior. If it says `recommended_mode=run_first_read_only_map`,
   run exactly its `command` as a real read-only map, not another dry-run, then
   validate/save the `read_only_project_map` result, append exactly one
   heartbeat spend, sync or refresh state if needed, and `NOTIFY`. If it says
   `recommended_mode=mapped_noop_if_unchanged` with `stop_if_unchanged=true`,
   and you find no new user instruction, owner evidence, agent todo, stale
   source, or safe handoff, return quiet `DONT_NOTIFY`: do not run, edit, or
   spend.
   Check `delivery_batch_scale`, `delivery_outcome`,
   `post_handoff_outcome_gap_streak`, and `handoff_delivery_contract`; for
   repeated-small or surface-only loops, obey the contract.
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
4. Choose one bounded, verifiable progress segment from that audit. It may be a
   coherent batch across related implementation, test, doc, and state-writeback
   files when the write scope is clear and validation is explicit; it should not
   be forced into a tiny single-file step.
5. Do that segment only. Stay inside `goal_boundary` when present and keep
   public/private boundaries intact. Public-safe repo publication is not an
   operator gate by itself: for routine public project work, commit, push, and
   PR creation may proceed autonomously after validation and a clean
   public/private boundary scan. Stop and surface a user/controller gate only
   for private or company-internal material, credentials, destructive git
   operations, production actions, or repository rules that explicitly require
   review.
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
8. After validation and writeback complete, append exactly one spend event
   before any state-only refresh that might close the active delivery lane:

   ```bash
   {quota_spend_command}
   ```

   Do not append spend for quiet `should_run=false` skips, preflight failures,
   pure dry-run previews, or duplicate accounting attempts. If
   `should_run=false` but `safe_bypass_allowed=true` and you actually completed
   a bounded safe-bypass step, append this same spend event once after
   validation/writeback.

9. If the dashboard or controller needs state after spend, refresh:

   ```bash
   {cli_bin} refresh-state --goal-id {goal_id}
   ```

   For a validated progress artifact, add a public-safe classification and
   explicit delivery hints so readiness does not infer from classification
   names:

   ```bash
   {cli_bin} refresh-state --goal-id {goal_id} --classification <PUBLIC_SAFE_PROGRESS_CLASSIFICATION> --delivery-batch-scale multi_surface --delivery-outcome outcome_progress
   ```

10. Return a compact final report. Use heartbeat `NOTIFY` only for meaningful
    user visibility, such as a committed artifact, a user gate, a real blocker,
    or the automation self-stop. Otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_brief_heartbeat_task_body(
    *,
    goal_id: str,
    active_state: str,
    cli_preflight: str,
    quota_guard_command: str,
    quota_spend_command: str,
    material_queue_rule: str,
    permission_rule: str,
    cli_bin: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

Brief installed Goal Harness heartbeat. Thin dispatcher: keep context small;
pull details on demand: `{compact_prompt_command}`.

Preflight and quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

Preflight fail: quiet `DONT_NOTIFY`, no work

If `should_run=false`: no work/spend except explicit
`safe_bypass_allowed=true` branches. Gate/open todo -> Chinese `NOTIFY`.
external/wait monitor -> one read-only
status/log/metric/marker poll; new evidence -> allowed writeback/spend once.
Else quiet `DONT_NOTIFY`.

If `should_run=true`: fetch compact; read needed state
priority slice + guard payload. Use `status --limit 3` for cross-goal
ambiguity; `review-packet --handoff-only` for scale/readiness. Blocker-push first; obey
`effective_action`, `recovery_delivery_allowed`, `heartbeat_recommendation`,
`safe_bypass_kind=outcome_floor_recovery`, `goal_boundary`, `delivery_batch_scale`,
`delivery_outcome`, outcome streaks, `handoff_delivery_contract`; do 1
bounded segment/batch;
if recovery, run ranker/cross-domain evidence recovery or blocker writeback;
validate/writeback/todos; spend once; refresh with explicit delivery
scale/outcome for progress artifacts. Stop on private, credentials,
destructive git, prod, or review rules.

Spend exactly once only after completed delivery or safe-bypass work:
`{quota_spend_command}`

No spend for quiet skips, preflight failures, blocker-push asks, dry-runs,
self-cancel, or duplicate accounting. Return compactly; `NOTIFY` only for a
committed artifact, user gate, real blocker, or self-stop.

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
    cli_bin: str,
    expanded_prompt_command: str,
    compact_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

This compact Goal Harness heartbeat body keeps project-specific branches out of
the automation prompt. Put local policy in registry, active state, adapter, or
`goal_boundary`. Expanded lifecycle contract:
`{expanded_prompt_command}`; inspect it for ambiguous edge branches.

Before delivery, make CLI reachable; run quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If preflight fails: quiet `DONT_NOTIFY`; no work/spend.

If `should_run=false`:
- `state=operator_gate` or `notify_user_on_open_todo=true`: blocker-push. If
  not surfaced recently, concise Chinese `NOTIFY` with gate or up to three
  user todos/first_open_items, reason, and reply format (`done`,
  `defer/not now`, or evidence link/date/conclusion). No delivery/spend.
- `safe_bypass_allowed=true`: do one gate-independent safe-bypass step.
  Validate/writeback/spend once; refresh if needed.
- `waiting_on=external_evidence` or `state=waiting` with explicit monitor
  purpose: one read-only status/log/metric/marker poll. Unchanged: quiet
  `DONT_NOTIFY`, no edits/spend. New evidence: report, allowed
  state/board/ledger writeback, todos, spend once. No prod mutation without
  authorization.
- Otherwise quiet `DONT_NOTIFY` with the skip reason; no work or spend.

If `should_run=true`:
1. Read active state, Priority Stack, progress/critic, `goal_boundary`,
   `attention_queue.items` / `project_asset`, and guard `user_todo_summary`.
   Legacy/raw fallback is not owner/gate/stop authority. Treat
   `run_history.latest_runs` as drill-down only.
2. Stop only for this goal's own blocker todo: Chinese `NOTIFY`, no work/spend.
   Dependency/sibling todos: record/surface, do not skip; continue P0/P1/P2 audit.
3. If `effective_action=outcome_floor_recovery` or
   `recovery_delivery_allowed=true` or
   `safe_bypass_kind=outcome_floor_recovery`, run only ranker/cross-domain
   evidence artifact or blocker recovery; no ordinary delivery or
   surface/synthetic-only work.
4. Follow `heartbeat_recommendation` before inventing behavior:
   `run_first_read_only_map` means run exact real-map command, then
   validate/save/spend/refresh/`NOTIFY`; `mapped_noop_if_unchanged` plus
   `stop_if_unchanged=true` means quiet no-op if no new instruction/evidence/
   todo/stale source/safe handoff.
   Check `delivery_batch_scale`, `delivery_outcome`,
   `post_handoff_outcome_gap_streak`, `handoff_delivery_contract`; obey
   repeated-small/surface-loop contracts.
5. Run steering audit: compare P0/P1/P2, continuation checks,
   compute/focus quota, bottleneck lens.
6. Run the no-progress self-stop check: if 5 eligible heartbeats only repeat
   status/brief checks with no artifact, implementation/adapter progress,
   gate/user decision, or validation signal, pause/delete automation, `NOTIFY`,
   no spend.
7. Choose one bounded, verifiable segment. Coherent batch is OK when
   scope/validation are clear. Public-safe commit/push/PR may proceed
   after validation and clean scan. Stop for private/company material,
   credentials, destructive git, production, or explicit review rules.
8. Validate; write files/validation/critic/next action to active state;
   use `goal-harness todo add --goal-id {goal_id} --role user|agent` for
   blockers/follow-ups, not prose.
9. After completed delivery or safe-bypass work, spend once before state
   refresh:

```bash
{quota_spend_command}
```

10. Refresh after spend if needed; validated progress artifacts pass explicit
   `--delivery-batch-scale` and `--delivery-outcome`.

Do not append spend for quiet skips, preflight failures, blocker-push asks,
pure dry-runs, self-cancel turns, or duplicate accounting attempts.

Return compactly. Use heartbeat `NOTIFY` only for committed artifact, user gate,
real blocker, or self-stop; otherwise use `DONT_NOTIFY`.

{material_queue_rule}
{permission_rule}"""


def render_heartbeat_prompt_markdown(payload: dict[str, Any]) -> str:
    if payload.get("brief"):
        style = "brief "
    elif payload.get("compact"):
        style = "compact "
    else:
        style = ""
    return f"""# Heartbeat Automation Prompt

Copy this {style}task body into a Codex App heartbeat automation.

````text
{payload.get("task_body", "")}
````

## Generator Inputs

- goal_id: `{payload.get("goal_id")}`
- active_state: `{payload.get("active_state")}`
- active_state_source: `{payload.get("active_state_source")}`
- resolved_active_state: `{payload.get("resolved_active_state")}`
- compact: `{payload.get("compact")}`
- brief: `{payload.get("brief")}`
- cli_bin: `{payload.get("cli_bin")}`
- expanded_prompt_command: `{payload.get("expanded_prompt_command")}`
- compact_prompt_command: `{payload.get("compact_prompt_command")}`
- quota_guard_command: `{payload.get("quota_guard_command")}`
- quota_spend_command: `{payload.get("quota_spend_command")}`
- cli_preflight: `{payload.get("cli_preflight")}`
"""
