# Compute Quota

LoopX should own compute allocation across projects. The first version
should stay deliberately simple: each goal gets one compute quota number, and
automations or controller ticks use that number to decide how often the goal may
consume agent time.

This replaces the current ad hoc pattern where priority is encoded only by
changing automation periods. A timer can wake the executor, but the product
policy should live in LoopX.

## Product Scope

In v0.1, quota means **compute quota only**.

It does not decide human reward, write approval, production permission, or
operator gate outcomes. Those remain separate LoopX states.

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
  may spend one bounded turn repairing LoopX health or contract blockers
  that prevent normal delivery.
- `control_plane.self_repair.allow_waiting_projection_repair`: when enabled, a
  goal in `state=waiting` with no concrete waiting owner but with a current
  action or agent backlog may spend one bounded turn repairing the projection or
  writing back the concrete blocker.

Self-repair is deliberately opt-in per goal. A short heartbeat can read the
machine contract from `quota should-run`, but ordinary goals without this
registry policy stay in their existing skip, waiting, or health-blocked lanes.
Independent of opt-in health/projection repair, status may project an
`autonomous_replan_obligation` when active state or public run history shows 2
consecutive stalled monitor/no-progress turns. In that case
`execution_obligation.kind=autonomous_replan_required` and
`must_attempt_work=true`; launchers should run a bounded replan slice before
another quiet no-op, then spend only after validated writeback.

## Allocation Contract

`quota plan` reports an advisory next automatic turn. It does not grant
permission, clear an operator gate, record human reward, or authorize a project
agent to run work that would otherwise be blocked.

The allocation rule is intentionally small:

1. derive quota groups from the same status payload used by `loopx
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

Delivery outcome is a structured enum consumed by quota, not a suffix inferred
from `classification`. New writes should use one of:

| Value | Quota meaning |
| --- | --- |
| `surface_only` | Useful surface work, but not primary result evidence; may trigger follow-through when an advancement todo remains. |
| `outcome_gap` | The run exposed a concrete blocker or missing outcome; follow-up should advance the result or write a precise blocker. |
| `outcome_progress` | Accountable delivery progress that may be eligible for spend after validation/writeback. |
| `primary_goal_outcome` | The selected stage's primary outcome is complete; it satisfies outcome-floor recovery. |

`classification` remains a human/history label. Quota may use old
execution-profile hints only as a compatibility fallback for historical runs;
new control-plane decisions should be driven by the enum above.

`quota should-run` also separates long-running observation from work that should
advance the selected goal. When the selected goal's current projection is a
dependency-only observation, the payload includes `work_lane_contract` with
`lane=continuous_monitor`. If open agent todos remain, schema
`work_lane_contract_v1` now classifies todo items as
`task_class=advancement_task` or `task_class=continuous_monitor`. Agents should
register executable work with `loopx todo add --task-class
advancement_task --action-kind <token>` instead of depending on project-specific
phrases in the automation prompt. The guard treats explicit `task_class` as
authoritative, uses recognized generic `action_kind` tokens as the next best
signal, and falls back to conservative text classification only for older
checkboxes. It sets
`next_lane=advancement_task`,
`obligation=advance_unless_material_monitor_transition`,
`must_attempt_work=true`, and reason codes such as `dependency_observation` and
`open_agent_todo` only when at least one open todo is advancement-class work.
If all visible open todos are monitor-class and no open todo is hidden, the
same contract uses `obligation=quiet_until_material_monitor_transition` and
`must_attempt_work=false`. Hidden open todos are treated as advancement work to
avoid false quiet no-ops from a truncated top-N todo projection.
Open agent todos that explicitly say not to run/launch until owner evidence,
credentials, substrate proof, or another prerequisite is present are
monitor-class blockers rather than executable advancement work; with an open
user todo they should keep that todo visible in `user_todo_summary` without
turning an unchanged eligible monitor poll into a blocker-push notification.
If the selected goal's `next_action`/`recommended_action` explicitly points to
an executable chain, such as collecting or aggregating repeats and then
rebuilding labels, rerunning a scorer, or validating an eval gate,
monitor-only todos are not allowed to make the goal quiet. The contract instead uses
`obligation=materialize_advancement_todo_or_blocker` and
`must_attempt_work=true`, so the worker must either materialize the concrete
advancement todo or write the blocker that prevents it.
`heartbeat_recommendation` should then say `follow_work_lane_contract` or
`monitor_quiet_until_material_transition` instead of encoding another
project-specific branch. An executor may still record one material
dependency-state transition when it changes the selected goal decision, but
unchanged monitor polls are quiet no-spend checks with `should_run=false` and
`effective_action=monitor_quiet_skip`. This keeps monitoring useful without
letting it consume every eligible turn, and it keeps the hard routing rule in
one small machine contract.

Executable todos can also declare explicit write-scope requirements through
todo metadata, for example `required_write_scopes=runner%2F%2A%2A` or the CLI
flag `loopx todo add --required-write-scope runner/**`. Before normal
delivery, `quota should-run` compares the first executable advancement todo's
`required_write_scopes` with `goal_boundary.write_scope`. If the current
boundary does not cover the selected scope, the guard keeps `should_run=true`
for a bounded repair turn but sets `normal_delivery_allowed=false`,
`effective_action=boundary_projection_repair`, and
`blocked_action_scope=boundary_projection`. The worker must repair the
checkpointed boundary projection, rewrite the todo inside the current boundary,
or write a concrete user/controller gate before attempting the write.

Executable todos can also declare environment capability requirements through
todo metadata, for example `required_capabilities=shell%2Cbenchmark_runner` or
the CLI flag `loopx todo add --required-capability benchmark_runner`.
This is not a global agent profile and not a permission system. It is a
per-todo execution preflight so the guard can distinguish "quota is available"
from "this step can actually run in the current environment."
Use `required_capabilities` for prerequisites, not for the capability the todo
is intended to create. A todo that repairs, develops, materializes, or
parity-checks a bridge capability should declare that output side with
`target_capabilities`. Target capabilities are projected for visibility and
repair-mode routing, but they are not hard execution gates.

`quota should-run` compares the visible executable advancement queue with the
current launcher capabilities. Basic local capabilities such as `shell`,
`filesystem_read`, and `filesystem_write` are assumed by default; launchers can
add temporary capabilities with `--available-capability`, for example:

```bash
loopx --format json quota should-run \
  --goal-id <goal-id> \
  --available-capability benchmark_runner
```

Use the same `--available-capability` flags for `quota spend-slot` after a
validated turn, because spend preview recomputes the same should-run guard
before writing quota accounting.

The resulting `capability_gate` is a read-only projection:

```json
{
  "schema_version": "capability_gate_v0",
  "action": "run",
  "required": ["shell", "filesystem_write"],
  "missing": [],
  "decision_owner": "agent",
  "selection_policy": "agent_steering_audit_over_runnable_candidates",
  "runnable_candidates": [
    {"todo_id": "todo_docs"}
  ],
  "blocked_candidates": [
    {
      "todo_id": "todo_eval",
      "required_capabilities": ["shell", "benchmark_runner"],
      "missing_capabilities": ["benchmark_runner"]
    }
  ]
}
```

Multiple P0/P1 items are handled as an ordered queue, not as a single selected
todo. The guard scans visible executable candidates in projection order and
projects which candidates are actually runnable in `runnable_candidates`; the
agent then chooses which runnable item to advance during its steering audit. A
runnable P0 remains visible before any P1 fallback, but LoopX does not
turn that ordering into an automatic final choice. Blocked higher-priority
candidates stay visible in `blocked_candidates`. If every visible executable
candidate is missing a capability, the gate returns
`action=repair_bridge` for repairable local bridges such as
`benchmark_runner`/`external_evidence_poll`, `action=ask_owner` for owner-held
capabilities such as `network`/`credentials`/`production_access`, or
`action=skip` for unsupported capability classes.

When a missing repairable bridge is itself the target of the todo, for example
`required_capabilities=shell` plus `target_capabilities=benchmark_runner`, the
candidate remains in `runnable_candidates` with `capability_repair_mode=true`,
`capability_action=repair_bridge`, and candidate-local
`missing_target_capabilities`. This avoids a circular gate where a todo cannot
develop `benchmark_runner` because it does not already have `benchmark_runner`.

External-evidence waits have an additional CLI-level observation contract. When
the selected goal is `state=waiting`, `waiting_on=external_evidence`, and its
current lane is a continuous monitor, or when the active state says a
long-running external worker was launched and the current action is to poll a
compact result/marker, `quota should-run` returns
`external_evidence_observation.schema_version =
external_evidence_observation_obligation_v0`. The guard keeps
`should_run=false` so ordinary delivery remains blocked, but sets
`effective_action=external_evidence_observe` and
`execution_obligation.kind=external_evidence_observation_required` with
`must_attempt_work=true`. The executor must verify a read-only observable
handle such as a thread id, automation id, job id, lock/result marker, or
compact writeback path before treating the poll as unchanged evidence. If that
handle is missing, stale, or never launched, write back a compact blocker or
launch-readiness fault instead of returning a quiet no-op.

For autonomous heartbeats, unchanged monitor polls can be recorded as
no-spend stall evidence with:

```bash
loopx --registry "$HOME/.codex/loopx/registry.global.json" quota monitor-poll --goal-id <GOAL_ID> --source heartbeat --execute
```

`quota monitor-poll` is valid only when the current guard is
`effective_action=monitor_quiet_skip` and
`recommended_mode=monitor_quiet_until_material_transition`. It appends a
`quota_monitor_poll` run record, does not mutate the registry, and does not
append `quota_slot_spent`. Two consecutive public stalled monitor records can
feed `autonomous_replan_obligation`, so the next independent `quota should-run`
may flip to `autonomous_replan_required` /
`execution_obligation.must_attempt_work=true`; the executor should then perform
one bounded replan slice instead of another quiet skip.

After that bounded replan or accounting slice is acknowledged by a compact
state run such as `monitor_poll_autonomous_replan_recorded_v0` or
`delivery_completion_spend_accounted_v0`, later empty monitor polls for the
same acknowledged wait do not repeatedly retrigger replan. They remain
no-spend liveness checks until a material monitor transition, regression, or
concrete blocker appears.

The same guard exposes `automation_liveness`. For
`monitor_quiet_skip`, it must say `automation_action=keep_active_quiet`,
`keep_active=true`, and `pause_allowed=false`: unchanged monitor-only polls are
not a reason to cancel recurring automation. Pausing/deleting is reserved for a
bounded self-repair or replan path that is itself stuck for two more eligible
turns. This keeps recurring controllers alive while still preventing quota
spend on empty monitor checks.

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
loopx quota status
loopx quota plan
loopx --format json --registry "$HOME/.codex/loopx/registry.global.json" quota should-run --goal-id <goal-id>
loopx --registry "$HOME/.codex/loopx/registry.global.json" quota spend-slot --goal-id <goal-id> --slots 1
loopx --registry "$HOME/.codex/loopx/registry.global.json" quota spend-slot --goal-id <goal-id> --slots 1 --execute
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
blocker-push turn. If quota also sets
`open_todo_notification_policy=repeat_until_resolved`, repeat
that notification until the todo is done, deferred, or replaced. Otherwise,
blocker-push cases may still be de-duplicated when the same blocker was already
surfaced recently. Eligible monitor-only polls with no material transition keep
the open user todo visible in `user_todo_summary`, but do not force a repeated
notification, make the turn a user-action gate, or leave the top-level
`should_run` set for an otherwise quiet no-op.
For every registered goal, `quota should-run` also includes a `todo_write_hint`
so agent executors know to write newly discovered user/owner work with
`loopx todo add --role user` instead of hiding it in `Next Action`,
review docs, or chat.
For goals with `coordination.registered_agents`, `quota should-run` accepts an
optional `--agent-id <registered-agent>`. Identity-aware heartbeat prompts pass
that flag through their quota guard. If a registered goal is checked without an
agent id, the payload includes `automation_prompt_upgrade.required=true` and a
recommended `heartbeat-prompt --agent-id ... --agent-scope ...` command. This
does not flip `should_run`; it is a lightweight migration signal for stale
installed automations.
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
lifecycle decisions in LoopX instead of one-off automation prompts. The
common modes are:

- `run_first_read_only_map`: a connected read-only goal has no saved compact run
  yet; run one real `loopx read-only-map --goal-id <goal-id>`, validate
  and save the `read_only_project_map`, then append exactly one heartbeat spend.
- `mapped_noop_if_unchanged`: the latest compact read-only map already exists;
  if there is no new user instruction, owner evidence, agent todo, stale source,
  or safe handoff, return a quiet no-op without another dry-run or quota spend.
- `steering_audit_then_one_step`: the goal is eligible but needs the normal
  steering audit before selecting one bounded progress segment. A coherent
  implementation/test/state batch is valid when scope and validation are clear;
  the contract is bounded, not tiny.

The same response includes `interaction_contract.schema_version =
loopx_interaction_contract_v0`, the top-level user/agent/CLI protocol
for the selected turn. It tells a worker whether this is a user gate, blocker
push, bounded delivery, external-evidence observation, monitor quiet skip,
autonomous replan, outcome-floor recovery, mapped no-op, or quota throttle. It
also names whether the user must be interrupted, whether Codex must attempt
work, whether delivery is allowed, whether quiet no-op is allowed, and whether
quota spend is allowed only after validation. Executors should read this object
first.
The response also includes `execution_obligation`, which is the compatibility
field that separates worker execution from user-facing notification.
`heartbeat_recommendation.notify` answers "should this heartbeat interrupt the
user?", not "may the worker skip work?" When
`execution_obligation.kind=work_lane_contract`, the hard routing rule is
`work_lane_contract.obligation`; `execution_obligation` should merely point the
worker to that object. When
`execution_obligation.kind=external_evidence_observation_required`, delivery is
still blocked but a read-only observation or compact blocker writeback is
mandatory before quiet no-op. When
`execution_obligation.must_attempt_work=true`, a short heartbeat must attempt
one bounded segment, validate it, write durable state/events, and spend once
after successful delivery. A quiet no-op is only allowed when the machine
contract explicitly says `must_attempt_work=false` and no blocker-push
notification is required. If `notify_user_on_open_todo=true`, the turn should
notify the user and skip spend instead of disappearing silently; verified
`mapped_noop_if_unchanged` after confirming the mapped source is unchanged
remains a quiet no-op case.

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
  turn after validated writeback. When the writeback is a state refresh that
  moves the guard from eligible/replan to waiting, `spend-slot` may still
  account the latest unspent `outcome_progress` delivery run once; a later
  duplicate spend is rejected because the latest run is then the spend event,
  not the delivery run.
- for unchanged `monitor_quiet_skip` heartbeat polls, append at most one
  no-spend `quota monitor-poll --execute` event and rerun `quota should-run`
  before choosing quiet no-op versus autonomous replan;
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
    "delivery_run_generated_at": null,
    "delivery_run_classification": null,
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
loopx quota set --goal-id <goal-id> --compute 0.5
loopx quota pause --goal-id <goal-id>
loopx quota burst --goal-id <goal-id> --slots 2 --dry-run
```

The important behavior is that automations ask LoopX whether a goal is
eligible before spending compute. They should not rely only on their own cron
period as the priority model.

## Acceptance Criteria

- Each active goal can expose a compute quota such as `1.0`, `0.5`, `0.3`, or
  `0`.
- `loopx status` can explain whether the goal is eligible, throttled,
  waiting, paused, or blocked before an automation spends another turn.
- A shared controller can rank eligible goals by compute quota without opening
  every project-agent thread.
- Per-goal automations can use the same quota to skip some ticks with a compact
  reason.
- Changing automation cadence is no longer the primary way to express project
  priority.
