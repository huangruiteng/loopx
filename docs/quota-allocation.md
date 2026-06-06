# Compute Quota

Goal Harness should own compute allocation across projects. The first version
should stay deliberately simple: each goal gets one compute quota number, and
automations or controller ticks use that number to decide how often the goal may
consume agent time.

This replaces the current ad hoc pattern where priority is encoded only by
changing automation periods. A timer can wake the executor, but the product
policy should live in Goal Harness.

## Product Scope

In v0.1, quota means **compute quota only**.

It does not decide human reward, write approval, production permission, or
operator gate outcomes. Those remain separate Goal Harness states.

Compute quota answers one question:

> Out of the available automatic agent time, how much should this goal be
> allowed to consume?

Examples:

- `1.0`: full duty cycle. If the controller checks hourly, this goal is
  eligible on every healthy check for the full 24-hour window. With the default
  minute-granularity accounting, `1.0` means `24 * 60 = 1440` automatic compute
  minute-slots.
- `0.5`: half duty cycle, roughly 12 hours per day or half of scheduling
  minute-slots.
- `0.3`: 30% duty cycle, roughly 7.2 hours per day or 30% of scheduling
  minute-slots.
- `0`: compute-paused. The goal remains visible but should not receive
  automatic Codex turns.

The number can be interpreted as either a duty cycle or a relative weight,
depending on the executor:

- per-goal automations can turn `0.5` into "run on about half the ticks";
- a shared controller loop can use the same number as a weighted selection
  ratio between eligible goals.

## Minimal Contract

The compact status shape can start with a small object:

```json
{
  "quota": {
    "compute": 0.5,
    "window_hours": 24,
    "slot_minutes": 1,
    "allowed_slots": 720,
    "spent_slots": 240,
    "state": "eligible",
    "next_eligible_at": "2026-06-02T12:00:00+08:00",
    "reason": "0.5 compute quota, 240/720 minute-slots spent in the current window"
  }
}
```

Registry entries may declare the same policy directly:

```json
{
  "quota": {
    "compute": 0.5,
    "window_hours": 24
  },
  "control_plane": {
    "self_repair": {
      "enabled": false,
      "allow_health_blocker_repair": false,
      "allow_waiting_projection_repair": false
    }
  }
}
```

If `quota.compute` is missing, status treats the goal as `1.0` by default so a
newly connected project remains eligible unless a harder gate blocks it.

`slot_minutes` is optional and defaults to `1`. The default `allowed_slots` is
computed as `window_hours * 60 / slot_minutes * compute`, so `compute=1.0` is
already the full available 24-hour duty cycle. Operators should only set
`allowed_slots` explicitly for exceptional overrides such as a temporary burst,
a deliberately stricter experimental cap, or a non-minute scheduler. It should
not be required to express normal full quota.

For the first implementation, `spent_slots` counts compact automatic compute
budget units. Under the default minute granularity, one slot means one minute of
automatic compute budget. Minute-based heartbeat continuations can spend
`--slots 1`; coarser controllers should spend the number of scheduler minutes
they actually reserve. It does not need to count exact tokens yet.

Status derives the current `spent_slots` from compact `quota_slot_spent`
runtime events in the current `window_hours` window. The registry remains the
policy source for `compute`, `window_hours`, and optional `allowed_slots`; it is
not the spend ledger.

Later versions can replace slots with real runtime, token spend, or cost, but
the operator-facing model should remain the same: a project has a simple
compute share.

## State Order

Quota is applied after hard gates:

1. Health and safety gates: broken registry, contract failures, or unsafe
   boundary issues block the goal.
2. Operator gates: read-only opt-in, write-control, reward judgment, and
   production actions still require explicit human decisions.
3. Evidence waits: a goal waiting on external metrics or target-controller
   response should not consume delivery compute just because quota remains.
4. Focus waits: a goal can still be Codex-owned while the current delivery lane
   is saturated or waiting for novelty, owner evidence, external eval, or a
   clean baseline. It should stay visible but should not spend delivery compute
   only because compute quota remains.
5. Compute quota: among goals that are otherwise eligible, quota decides
   whether this one should receive the next automatic turn.

This keeps the model small. Quota does not become a second permission system.

## Control Plane Settings

Registry entries can carry per-goal `control_plane` policy alongside quota.
These settings are the control surface for behavior that would otherwise be
tempting to encode in a heartbeat prompt.

Current self-repair settings:

- `control_plane.self_repair.enabled`: default `false`.
- `control_plane.self_repair.allow_health_blocker_repair`: when enabled, a goal
  may spend one bounded turn repairing Goal Harness health or contract blockers
  that prevent normal delivery.
- `control_plane.self_repair.allow_waiting_projection_repair`: when enabled, a
  goal in `state=waiting` with no concrete waiting owner but with a current
  action or agent backlog may spend one bounded turn repairing the projection or
  writing back the concrete blocker.

Self-repair is deliberately opt-in per goal. A short heartbeat can read the
machine contract from `quota should-run`, but ordinary goals without this
registry policy stay in their existing skip, waiting, or health-blocked lanes.

## Allocation Contract

`quota plan` reports an advisory next automatic turn. It does not grant
permission, clear an operator gate, record human reward, or authorize a project
agent to run work that would otherwise be blocked.

The allocation rule is intentionally small:

1. derive quota groups from the same status payload used by `goal-harness
   status`;
2. keep `blocked_health`, `operator_gate`, `focus_wait`, `waiting`,
   `throttled`, and `paused` goals in their own lanes, even when they have a
   high `quota.compute`;
3. only goals with `state=eligible` enter the eligible lane;
4. sort eligible goals by effective `quota.compute`, highest first;
5. set `summary.next_automatic_turn` to the first eligible goal, or `none` when
   the eligible lane is empty.

Automations and controllers should treat `next_automatic_turn` as a scheduling
hint, then ask `quota should-run --goal-id <goal-id>` immediately before
spending compute. If the guard returns `should_run=false`, the executor should
skip the blocked delivery work and follow the reported health, operator,
evidence, focus-wait, pause, or throttle reason. When `state=operator_gate` also
returns `safe_bypass_allowed=true`, the target heartbeat may do one bounded
read-only steering or analysis step that does not depend on that gate, but it
must not execute `agent_command`, adapter work, write-control, production
actions, or the gated path.
When `state=focus_wait` is caused by a connected-delivery outcome floor and the
payload returns `safe_bypass_kind=outcome_floor_recovery`, the goal is not free
to resume ordinary delivery. It may spend one bounded recovery turn only to
produce the required ranker/cross-domain evidence artifact named by
`quota.must_advance`, or to write back the concrete blocker that prevents that
artifact. Surface-only summary/queue/contract propagation and synthetic-only
test chains remain blocked.
When `control_plane.self_repair.enabled=true` and the selected goal is stalled
by a repairable control-plane condition, `quota should-run` may instead return
`decision=self_repair`, `self_repair_allowed=true`, `stall_self_repair`, and an
`effective_action` such as `control_plane_health_repair` or
`control_plane_projection_repair`. This makes "repair the control plane" a
machine-readable bounded action for the selected goal, not a prompt-specific
branch. Spend is allowed only after validation and durable writeback.

## Compute States

Recommended compact states:

- `eligible`: the goal can consume the next automatic agent turn.
- `focus_wait`: the goal is Codex-addressable in principle, but the current
  delivery focus is intentionally paused by a continuation boundary or missing
  novelty, owner evidence, external eval, or clean baseline.
- `throttled`: the goal is healthy but has spent its current compute quota.
- `waiting`: the goal is waiting on external evidence or a target controller,
  so compute should not be spent yet.
- `operator_gate`: the goal needs a human decision before more compute is
  useful.
- `paused`: compute quota is `0` or the operator paused the goal.
- `blocked_health`: the goal must fix registry, contract, or boundary issues
  before more work runs.

These are product states for the dashboard. Adapter classifications remain
drill-down details.

## Dashboard Implication

The dashboard should show compute quota as a compact control surface:

- quota chips: `1.0`, `0.5`, `0.3`, `0`;
- spent/allowed minute-slots for the current window;
- a visible explicit-override marker only when `allowed_slots` is manually set
  away from the window-derived default;
- next eligible time when throttled;
- simple operator actions: set quota, pause, resume, or grant a temporary
  burst;
- next-turn view sorted by "should receive the next automatic turn."

The first screen should make it obvious why a project is quiet:

- it is waiting on evidence;
- it is gated by the operator;
- it is in focus wait because the current lane needs novelty, evidence, or a
  clean baseline before another delivery turn;
- it is throttled by compute quota;
- it is paused;
- or it is eligible and should run next.

## CLI Surface

The first read-only or preview commands are:

```bash
goal-harness quota status
goal-harness quota plan
goal-harness --format json --registry "$HOME/.codex/goal-harness/registry.global.json" quota should-run --goal-id <goal-id>
goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <goal-id> --slots 1
goal-harness --registry "$HOME/.codex/goal-harness/registry.global.json" quota spend-slot --goal-id <goal-id> --slots 1 --execute
```

These commands reuse the status contract, including contract health, global
registry health, attention queue, run history, and derived quota state. They do
not mutate registry, runtime history, reward overlays, or operator gates.
Project heartbeat prompts should use the shared global registry for
`should-run` and `spend-slot` so they see the same operator gates, user todos,
and quota state as the dashboard. Project-local state writes such as
`refresh-state` and `todo add` still happen in the source project and sync their
public-safe projection back to the global registry.

`quota status` is the broad inventory for agents: it shows every registered
goal under `blocked_health`, `operator_gate`, `focus_wait`, `eligible`,
`waiting`, `throttled`, or `paused`.

`quota plan` is the next-turn view for automations: it hides empty groups in
markdown output and highlights `next_automatic_turn` when a goal is eligible.
If that value is `none`, the automation should skip delivery compute and follow
the displayed gate, evidence, or health reason.

`quota should-run` is the per-goal guard for heartbeat jobs. It returns a small
JSON or Markdown decision:

```json
{
  "goal_id": "project-main-control",
  "decision": "skip",
  "should_run": false,
  "state": "operator_gate",
  "reason": "operator gate blocks gated delivery; safe non-gated steering may continue",
  "blocked_action_scope": "gated_delivery",
  "safe_bypass_allowed": true,
  "heartbeat_recommendation": {
    "source": "quota.should-run",
    "recommended_mode": "ask_operator_gate",
    "notify": "NOTIFY",
    "spend_policy": "do not append quota spend while asking the operator gate"
  },
  "operator_question": "是否同意 project-main-control 先做 read-only map dry-run？",
  "gate_prompt": "请用户/控制器确认当前 gate：..."
}
```

Only `state=eligible`, outcome-floor recovery safe-bypass, or registry-enabled
control-plane self-repair returns `should_run=true`. Known goals that are
gated, in focus wait, waiting, throttled, paused, or health-blocked return
`ok=true` only when the status export itself is healthy, but otherwise return
`should_run=false`.
`safe_bypass_allowed=true` is not permission to clear the gate; it only says the
agent can spend a bounded turn on independent read-only steering/analysis.
For `state=operator_gate`, `quota should-run` should also surface
`gate_prompt`, `operator_question`, `next_handoff_condition`, `missing_gates`,
`user_todo_summary`, or `agent_todo_summary` when those fields are available.
A heartbeat should use that prompt to ask the user or target controller the
concrete gate question instead of silently skipping, unless the same unresolved
gate was already asked in the recent visible thread. If
`user_todo_summary.open_count > 0`, existing open user todos are themselves
user-visible action; do not report "no new user action" while those todos
remain open. This also applies after a bounded safe-bypass step: the compact
report must still list the existing open user todos instead of saying that
there is no user action. If `agent_todo_summary.open_count > 0`, the agent
should use that summary as its next safe follow-up checklist instead of mining
chat history or an overlong `Next Action`.
For `state=focus_wait`, `state=waiting`, or
`waiting_on=external_evidence`, an open user todo can be the smallest unlock
for a quiet project. In that case, `quota should-run` should set
`notify_user_on_open_todo=true` and include `open_todo_notify_reason`. The
target heartbeat should return a compact `NOTIFY` listing at most three open
user todos and the expected reply (`done`, `defer/not now`, or new evidence
link/date/conclusion), while skipping delivery work and quota spend for that
blocker-push turn unless the same blocker was already surfaced recently.
For every registered goal, `quota should-run` also includes a `todo_write_hint`
so agent executors know to write newly discovered user/owner work with
`goal-harness todo add --role user` instead of hiding it in `Next Action`,
review docs, or chat.
When the status payload has same-goal checkpointed decisions that are stale or
have newer sampled events, `quota should-run` includes
`decision_freshness_warning`. This warning does not make an eligible goal skip;
it prevents a worker from treating an old reward, steering note, or operator
gate as current authority. Before reusing that decision, the worker must rebase
the decision point against the latest registry, ACTIVE_GOAL_STATE, quota,
policy, and run status. This is not a repo rollback and does not carry the whole
old chat state forward.
When the status payload has missing, stale, or unknown canary promotion
readiness evidence, `quota should-run` also includes
`promotion_readiness_warning`. This warning is additive: it does not change
`should_run`, but it lets heartbeat workers and dashboards report release
readiness blockers from the shared run-history projection without parsing
`doctor`, dashboard copy, or chat reports. Before promoting the local release
snapshot, run the canary promotion-readiness smoke and confirm fresh evidence in
status or doctor output.
Connected delivery goals also include `goal_boundary` when the registry has
boundary data. That field carries the adapter status, allowed write scope,
parent-approval scopes, registry guards, next probe, and stop condition. It is
the preferred place for project-specific delivery boundaries; automation
prompts should say to obey `goal_boundary` instead of repeating long protected
file or action lists.
It also includes `heartbeat_recommendation`, which keeps generic heartbeat
lifecycle decisions in Goal Harness instead of one-off automation prompts. The
common modes are:

- `run_first_read_only_map`: a connected read-only goal has no saved compact run
  yet; run one real `goal-harness read-only-map --goal-id <goal-id>`, validate
  and save the `read_only_project_map`, then append exactly one heartbeat spend.
- `mapped_noop_if_unchanged`: the latest compact read-only map already exists;
  if there is no new user instruction, owner evidence, agent todo, stale source,
  or safe handoff, return a quiet no-op without another dry-run or quota spend.
- `steering_audit_then_one_step`: the goal is eligible but needs the normal
  steering audit before selecting one bounded progress segment. A coherent
  implementation/test/state batch is valid when scope and validation are clear;
  the contract is bounded, not tiny.

Unknown goals or status collection failures return non-zero so automations fail
closed.

`quota spend-slot` is an accounting helper. By default it is dry-run only: it
shows the before and after `should-run` decision for consuming slots and writes
nothing. With `--execute`, it appends one compact `quota_slot_spent` runtime
event. It never mutates registry, reward overlays, operator gates, write
control, private evidence, or production state. The event is status-neutral:
it remains in run history for audit and quota counting, but it should not
become the current work classification in status, quota `should-run`, or the
dashboard attention queue.

The displayed before -> after transition is a same-status-payload projection
for the slot being written. Later `quota status` and `quota should-run`
commands recompute `spent_slots` from `quota_slot_spent` events still inside
the rolling `window_hours`; if an older spend expires between the preview and
the next check, the visible total can stay flat or drop even though the new
event was appended. Treat the appended event path as the write receipt, and
treat `spent_slots` as the current rolling-window total rather than a monotonic
counter.

Post-turn accounting protocol:

- call `quota should-run` before spending delivery compute;
- do the bounded automatic turn, validation, and state writeback;
- append exactly one `quota spend-slot --execute` event for that completed
  turn before any state-only refresh that might close the active delivery lane;
- refresh state after spend when the dashboard or controller needs the updated
  state projection;
- do not append spend for quiet `should_run=false` skips, preflight failures,
  pure dry-run previews, or duplicate accounting attempts;
- if `should_run=false` but `safe_bypass_allowed=true` and the agent actually
  completes bounded safe-bypass work, append one spend event for that work. For
  `safe_bypass_kind=outcome_floor_recovery`, spend only after validated
  ranker/cross-domain evidence or concrete blocker writeback, not for another
  surface-only report.
- if `should_run=true` with `effective_action=control_plane_health_repair` or
  `control_plane_projection_repair`, append one spend event only after the
  control-plane projection or blocker writeback is validated.

## Slot Spend Event Contract

A real spend write path appends one compact runtime event after an automatic
Codex turn actually consumes quota. The smallest public-safe event is
`classification=quota_slot_spent` with a nested `quota_event` object:

```json
{
  "goal_id": "project-main-control",
  "classification": "quota_slot_spent",
  "quota_event": {
    "event_type": "quota_slot_spent",
    "source": "heartbeat",
    "slots": 1,
    "reason_summary": "one automatic Codex turn completed under an eligible quota guard",
    "before": {
      "should_run": true,
      "state": "eligible",
      "compute": 0.5,
      "window_hours": 24,
      "slot_minutes": 1,
      "spent_slots": 719,
      "allowed_slots": 720
    },
    "after": {
      "should_run": false,
      "state": "throttled",
      "compute": 0.5,
      "window_hours": 24,
      "slot_minutes": 1,
      "spent_slots": 720,
      "allowed_slots": 720
    }
  }
}
```

The public fixture is
[`examples/quota-slot-spend-event.example.json`](../examples/quota-slot-spend-event.example.json).

Validation rule:

- write only after a fresh `quota should-run` returned `should_run=true`, or
  after it returned `safe_bypass_allowed=true` and the agent completed one
  bounded safe-bypass step;
- for `effective_action=control_plane_health_repair` or
  `control_plane_projection_repair`, treat the spend as control-plane
  self-repair accounting, not ordinary delivery;
- `slots` must be positive, and `after.spent_slots` must equal
  `before.spent_slots + slots`;
- if `after.spent_slots >= after.allowed_slots`, `after.state` should be
  `throttled` and `after.should_run` should be `false`;
- do not include human reward, operator-gate approval, write-control, private
  evidence, internal links, raw logs, or production identifiers in the quota
  event.

This event is accounting, not permission. It records that compute was spent
after the normal health/evidence/quota checks allowed the turn, or after an
operator gate explicitly scoped its block to the gated delivery path and allowed
one independent safe-bypass step.

Other write commands can stay behind explicit operator approval:

```bash
goal-harness quota set --goal-id <goal-id> --compute 0.5
goal-harness quota pause --goal-id <goal-id>
goal-harness quota burst --goal-id <goal-id> --slots 2 --dry-run
```

The important behavior is that automations ask Goal Harness whether a goal is
eligible before spending compute. They should not rely only on their own cron
period as the priority model.

## Acceptance Criteria

- Each active goal can expose a compute quota such as `1.0`, `0.5`, `0.3`, or
  `0`.
- `goal-harness status` can explain whether the goal is eligible, throttled,
  waiting, paused, or blocked before an automation spends another turn.
- A shared controller can rank eligible goals by compute quota without opening
  every project-agent thread.
- Per-goal automations can use the same quota to skip some ticks with a compact
  reason.
- Changing automation cadence is no longer the primary way to express project
  priority.
