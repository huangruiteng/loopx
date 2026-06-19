from __future__ import annotations

from pathlib import Path
from typing import Any

from .project_prompt import render_cli_preflight, render_quota_guard_command, render_quota_spend_command


DEFAULT_MATERIAL_QUEUE_RULE = "Do not consume the learning material queue unless the user explicitly asks."
DEFAULT_PERMISSION_RULE = "Do not ask for permissions when the current Codex session is already trusted."
USER_TODO_FINAL_MESSAGE_RULE = (
    "Only if action_required=true/open_count>0: name concrete payload todo(s)/questions, "
    'never only "owner gate"; missing -> '
    '"具体 user todo 未投影，需修复 Goal Harness 状态投影". '
    "If false/0, allow quiet/no-user-todo."
)
INTERFACE_BUDGET_CHARS = {
    "full": 11_200,
    "compact": 5_000,
    "brief": 2_700,
    "thin": 1_000,
}


def heartbeat_prompt_mode(*, compact: bool = False, brief: bool = False, thin: bool = False) -> str:
    if thin:
        return "thin"
    if brief:
        return "brief"
    if compact:
        return "compact"
    return "full"


def prompt_budget_text(text: str, *, goal_id: str, active_state: str) -> str:
    return text.replace(goal_id, "<GOAL_ID>").replace(active_state, "<ACTIVE_STATE>")


def build_interface_budget(
    *,
    task_body: str,
    goal_id: str,
    active_state: str,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
) -> dict[str, Any]:
    mode = heartbeat_prompt_mode(compact=compact, brief=brief, thin=thin)
    budget_text = prompt_budget_text(task_body, goal_id=goal_id, active_state=active_state)
    budget_chars = len(budget_text)
    max_chars = INTERFACE_BUDGET_CHARS[mode]
    return {
        "mode": mode,
        "char_count": len(task_body),
        "line_count": len(task_body.splitlines()),
        "budget_char_count": budget_chars,
        "max_chars": max_chars,
        "within_budget": budget_chars <= max_chars,
    }


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
    thin: bool = False,
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
    brief_prompt_command = f"{cli_bin} heartbeat-prompt --brief --goal-id {goal_id}{active_state_arg}"
    thin_prompt_command = f"{cli_bin} heartbeat-prompt --thin --goal-id {goal_id}{active_state_arg}"
    if thin:
        task_body_renderer = render_thin_heartbeat_task_body
    elif brief:
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
        brief_prompt_command=brief_prompt_command,
        thin_prompt_command=thin_prompt_command,
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
        "thin": thin,
        "cli_bin": cli_bin,
        "expanded_prompt_command": expanded_prompt_command,
        "compact_prompt_command": compact_prompt_command,
        "brief_prompt_command": brief_prompt_command,
        "thin_prompt_command": thin_prompt_command,
        "quota_guard_command": quota_guard_command,
        "quota_spend_command": quota_spend_command,
        "cli_preflight": cli_preflight,
        "material_queue_rule": resolved_material_rule,
        "permission_rule": resolved_permission_rule,
        "interface_budget": build_interface_budget(
            task_body=task_body,
            goal_id=goal_id,
            active_state=active_state_text,
            compact=compact,
            brief=brief,
            thin=thin,
        ),
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
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

Generic Goal Harness lifecycle. Keep project-specific branching out of the
automation prompt. Put local policy in registry, active-state sections, adapter
output, `quota should-run.goal_boundary`, or boundary rules; if a lifecycle
rule is needed, update `goal-harness heartbeat-prompt` so all projects inherit it.

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
  when nothing new was found; never say "no new user action".
  {USER_TODO_FINAL_MESSAGE_RULE} Do not execute `agent_command`, adapter work,
  write-control, production actions, or the gated path while asking.
- If `notify_user_on_open_todo=true`, existing open `user_todo_summary` is a
  blocker-push opportunity, not a silent skip. For focus/wait/evidence lanes,
  a user/owner answer can unlock progress. If the payload explicitly includes
  `open_todo_notification_policy=repeat_until_resolved`, `NOTIFY` every poll
  until done/deferred/replaced. Other blockers may de-dupe if surfaced
  recently; otherwise `NOTIFY` in Chinese with up to three
  `first_open_items`, `open_todo_notify_reason`, and reply format: `done`,
  `defer/not now`, or evidence link/date/conclusion. No delivery/spend.
- If the payload also says `safe_bypass_allowed=true` and the same gate has
  already been surfaced, the gate blocks only the gated delivery path. You may
  do exactly one bounded safe-bypass step from the Priority Stack that does not
  depend on that gate; validate, write back, optionally refresh, spend once, and
  report compactly. If `user_todo_summary.open_count > 0`, include those todos
  and do not say "no new user action". If none exists, report the gate.
- If `effective_action=monitor_quiet_skip`, run one no-spend
  `quota monitor-poll --goal-id {goal_id} --source heartbeat --execute`, rerun
  guard; quiet unless autonomous replan. No delivery edits/spend; unchanged
  monitor-only polls are not self-stop signals.
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
   Read `execution_obligation`: `notify` is not an execution gate;
   `must_attempt_work=true` means one bounded segment even with
   `notify=DONT_NOTIFY`; quiet no-op needs `must_attempt_work=false` and no
   `notify_user_on_open_todo=true` blocker-push notification. Then use
   `heartbeat_recommendation`: `recommended_mode=run_first_read_only_map` means
   run its `command` as a real read-only map, then
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
   Plan/top todo/route changes need todo/Next Action writeback or no-writeback rationale.
3. Run the no-progress self-repair check before choosing delivery work. Obey
   any machine-readable `autonomous_replan_obligation` or
   `execution_obligation.must_attempt_work=true` from `quota should-run`; that
   hard contract overrides a quiet no-op. Count a turn as no-progress only when
   it produced no substantive artifact, adapter/implementation progress,
   gate/user decision, or validation signal. If 2 consecutive eligible
   heartbeats are no-progress loops, run one bounded self-repair/replan segment
   before another quiet no-op. Delete/pause only when that repair path is stuck
   for 2 more eligible turns; no spend for the self-cancel turn.
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
   For non-trivial feature slices, complete the current todo only after adding
   a successor todo, or include a compact no-follow-up rationale.
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
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

Brief installed Goal Harness heartbeat. Thin dispatcher: keep context small;
pull details on demand: `{compact_prompt_command}`.

Preflight and quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

Preflight fail: quiet.

If `should_run=false`: no work/spend except explicit
`safe_bypass_allowed=true` branches. Gate/open todo -> Chinese `NOTIFY`.
external/wait monitor -> one read-only status/log/metric/marker poll; new
evidence -> writeback/spend once.
Else quiet.
Action/open todo: list todos/questions; never only "owner gate";
missing -> "具体 user todo 未投影，需修复 Goal Harness 状态投影"; false/0: 无用户待办/无需通知 or quiet.

If `should_run=true`: fetch compact; read needed state priority slice + guard
payload. Use `status --limit 3`; `review-packet --handoff-only`.
Blocker-push first; obey
`execution_obligation`, `effective_action`, `recovery_delivery_allowed`,
`heartbeat_recommendation`, `safe_bypass_kind=outcome_floor_recovery`,
`goal_boundary`, `delivery_batch_scale`, `delivery_outcome`, outcome streaks,
`handoff_delivery_contract`; do 1 bounded segment/batch when
`execution_obligation.must_attempt_work=true`; if recovery, run
ranker/cross-domain evidence recovery or blocker writeback;
validate/writeback/todos; successor todo or no-follow-up rationale for
non-trivial feature slices; spend once; refresh with explicit delivery
scale/outcome for progress artifacts. Stop on private, credentials, destructive
git, prod, or review rules.

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
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    return f"""Advance `{goal_id}` using `{active_state}`.

This compact Goal Harness heartbeat body keeps project-specific branches out.
Put local policy in registry/state/adapter/`goal_boundary`.
Expanded lifecycle contract: `{expanded_prompt_command}`.

Before delivery, make CLI reachable; run quota guard:

```bash
{cli_preflight}
{quota_guard_command}
```

If preflight fails: quiet `DONT_NOTIFY`; no work/spend.

If `should_run=false`: `monitor_quiet_skip` appends at most one no-spend
`quota monitor-poll --execute` event, reruns the guard, then stays quiet unless
the next guard exposes `autonomous_replan_required` / `must_attempt_work=true`;
no delivery edits/spend; unchanged monitor-only polls are not self-stop
signals.
`state=operator_gate` or `notify_user_on_open_todo=true`: blocker-push;
`open_todo_notification_policy=repeat_until_resolved`: repeat `NOTIFY`;
if action/open todo exists, list payload todo(s)/questions, never only
"owner gate"; no delivery/spend. `safe_bypass_allowed=true`: one
gate-independent safe-bypass, validate/writeback/spend. External/wait monitor:
one read-only status/log/metric/marker poll; unchanged quiet, new evidence
writeback/spend. Otherwise quiet `DONT_NOTIFY`.

If `should_run=true`:
1. Read active state, Priority Stack, progress/critic, `goal_boundary`,
   `attention_queue.items` / `project_asset`, and guard `user_todo_summary`.
   Legacy/raw fallback is not owner/gate/stop authority. Treat
   `run_history.latest_runs` as drill-down only.
2. Stop only for this goal's own blocker todo: Chinese `NOTIFY`, no work/spend.
   Dependency/sibling todos: record/surface; continue audit.
3. If `effective_action=outcome_floor_recovery` or
   `recovery_delivery_allowed=true` or
   `safe_bypass_kind=outcome_floor_recovery`, run only ranker/cross-domain
   evidence artifact or blocker recovery; no ordinary delivery or
   surface/synthetic-only work.
4. Follow `execution_obligation`: `notify` is not an execution gate.
   `must_attempt_work=true` means one bounded segment even with
   `notify=DONT_NOTIFY`; quiet no-op needs `must_attempt_work=false` and no
   `notify_user_on_open_todo=true` blocker-push notification.
   Then follow `heartbeat_recommendation`:
   `run_first_read_only_map` means run exact real-map command, then
   validate/save/spend/refresh/`NOTIFY`; `mapped_noop_if_unchanged` plus
   `stop_if_unchanged=true` means quiet no-op if no new instruction/evidence/
   todo/stale source/safe handoff.
   Check `delivery_batch_scale`, `delivery_outcome`,
   `post_handoff_outcome_gap_streak`, `handoff_delivery_contract`; obey
   repeated-small/surface-loop contracts.
5. Run steering audit: compare P0/P1/P2, continuation checks,
   compute/focus quota, bottleneck lens.
6. Run no-progress self-repair: obey `autonomous_replan_obligation` or
   `execution_obligation.must_attempt_work=true`; monitor poll events are
   no-spend stall evidence, so if 2 eligible heartbeats only repeat status/brief
   checks with no artifact/progress/gate/validation, replan before quiet no-op.
   Pause/delete only if repair is stuck for 2 more turns.
7. Choose one bounded segment. Coherent batch is OK with clear validation.
   Public-safe commit/push/PR may proceed after validation/clean scan. Stop
   for private/company material, credentials, destructive git, production, or
   explicit review rules.
8. Validate; write files/validation/critic/next action to active state;
   use `goal-harness todo add --goal-id {goal_id} --role user|agent` for
   blockers/plans, not prose. Nontrivial done ->
   successor todo or no-follow-up rationale.
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


def render_thin_heartbeat_task_body(
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
    brief_prompt_command: str,
    thin_prompt_command: str,
) -> str:
    permission_tail = "" if permission_rule == DEFAULT_PERMISSION_RULE else f" {permission_rule}"
    material_sentence = (
        "Do not consume the learning material queue unless explicitly asked."
        if material_queue_rule == DEFAULT_MATERIAL_QUEUE_RULE
        else material_queue_rule
    )
    return f"""Advance `{goal_id}` from {active_state}.

Use skills: `goal-harness-project`; if surprising/tiny/contradictory,
`goal-harness-self-repair`. Goal Harness CLI is source of truth.

Inspect registry/global quota truth, active state, status/run history, repo
state. Run `quota should-run`; follow `interaction_contract`. If
action_required=true/open_count>0, list concrete payload todo(s)/questions;
never only "owner gate"; missing -> "具体 user todo 未投影，需修复 Goal Harness 状态投影".
If false/0: 无用户待办/无需通知 or quiet.
Do bounded validated batch or quiet no-op; spend after writeback.
Plans/done -> GH todo or rationale.
After 2 no-progress, self-repair.

If P0 is blocked but CLI contract permits safe work, continue verifiable
P1/P2; monitor-only quiet skips stay active/no-spend.

No project-specific branches here. {material_sentence} Stop for private material,
credentials, destructive git, or unauthorized production actions{permission_tail}"""


def render_heartbeat_prompt_markdown(payload: dict[str, Any]) -> str:
    if payload.get("thin"):
        style = "thin "
    elif payload.get("brief"):
        style = "brief "
    elif payload.get("compact"):
        style = "compact "
    else:
        style = ""
    interface_budget = payload.get("interface_budget") if isinstance(payload.get("interface_budget"), dict) else {}
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
- thin: `{payload.get("thin")}`
- cli_bin: `{payload.get("cli_bin")}`
- expanded_prompt_command: `{payload.get("expanded_prompt_command")}`
- compact_prompt_command: `{payload.get("compact_prompt_command")}`
- brief_prompt_command: `{payload.get("brief_prompt_command")}`
- thin_prompt_command: `{payload.get("thin_prompt_command")}`
- quota_guard_command: `{payload.get("quota_guard_command")}`
- quota_spend_command: `{payload.get("quota_spend_command")}`
- cli_preflight: `{payload.get("cli_preflight")}`
- interface_budget: mode=`{interface_budget.get("mode")}` budget_chars=`{interface_budget.get("budget_char_count")}` max_chars=`{interface_budget.get("max_chars")}` within_budget=`{interface_budget.get("within_budget")}`
"""
