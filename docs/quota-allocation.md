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
  eligible on every healthy check.
- `0.5`: half duty cycle, roughly 12 hours per day or half of scheduling slots.
- `0.3`: 30% duty cycle, roughly 7.2 hours per day or 30% of scheduling slots.
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
    "allowed_slots": 12,
    "spent_slots": 4,
    "state": "eligible",
    "next_eligible_at": "2026-06-02T12:00:00+08:00",
    "reason": "0.5 compute quota, 4/12 slots spent in the current window"
  }
}
```

Registry entries may declare the same policy directly:

```json
{
  "quota": {
    "compute": 0.5,
    "window_hours": 24
  }
}
```

If `quota.compute` is missing, status treats the goal as `1.0` by default so a
newly connected project remains eligible unless a harder gate blocks it.

For the first implementation, `spent_slots` can count automatic Goal Harness
ticks, adapter runs, heartbeat continuations, or controller-selected Codex
turns. It does not need to count exact tokens or wall-clock seconds yet.

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
4. Compute quota: among goals that are otherwise eligible, quota decides
   whether this one should receive the next automatic turn.

This keeps the model small. Quota does not become a second permission system.

## Allocation Contract

`quota plan` reports an advisory next automatic turn. It does not grant
permission, clear an operator gate, record human reward, or authorize a project
agent to run work that would otherwise be blocked.

The allocation rule is intentionally small:

1. derive quota groups from the same status payload used by `goal-harness
   status`;
2. keep `blocked_health`, `operator_gate`, `waiting`, `throttled`, and `paused`
   goals in their own lanes, even when they have a high `quota.compute`;
3. only goals with `state=eligible` enter the eligible lane;
4. sort eligible goals by effective `quota.compute`, highest first;
5. set `summary.next_automatic_turn` to the first eligible goal, or `none` when
   the eligible lane is empty.

Automations and controllers should treat `next_automatic_turn` as a scheduling
hint, then ask `quota should-run --goal-id <goal-id>` immediately before
spending compute. If the guard returns `should_run=false`, the executor should
skip delivery work and follow the reported health, operator, evidence, pause, or
throttle reason.

## Compute States

Recommended compact states:

- `eligible`: the goal can consume the next automatic agent turn.
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
- spent/allowed slots for the current window;
- next eligible time when throttled;
- simple operator actions: set quota, pause, resume, or grant a temporary
  burst;
- next-turn view sorted by "should receive the next automatic turn."

The first screen should make it obvious why a project is quiet:

- it is waiting on evidence;
- it is gated by the operator;
- it is throttled by compute quota;
- it is paused;
- or it is eligible and should run next.

## CLI Surface

The first read-only or preview commands are:

```bash
goal-harness quota status
goal-harness quota plan
goal-harness quota should-run --goal-id <goal-id>
goal-harness quota spend-slot --goal-id <goal-id> --slots 1
goal-harness quota spend-slot --goal-id <goal-id> --slots 1 --execute
```

These commands reuse the status contract, including contract health, global
registry health, attention queue, run history, and derived quota state. They do
not mutate registry, runtime history, reward overlays, or operator gates.

`quota status` is the broad inventory for agents: it shows every registered
goal under `blocked_health`, `operator_gate`, `eligible`, `waiting`,
`throttled`, or `paused`.

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
  "reason": "human or target-controller gate must clear before spending compute"
}
```

Only `state=eligible` returns `should_run=true`. Known goals that are gated,
waiting, throttled, paused, or health-blocked return `ok=true` only when the
status export itself is healthy, but still return `should_run=false`. Unknown
goals or status collection failures return non-zero so automations fail closed.

`quota spend-slot` is an accounting helper. By default it is dry-run only: it
shows the before and after `should-run` decision for consuming slots and writes
nothing. With `--execute`, it appends one compact `quota_slot_spent` runtime
event. It never mutates registry, reward overlays, operator gates, write
control, private evidence, or production state.

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
      "spent_slots": 11,
      "allowed_slots": 12
    },
    "after": {
      "should_run": false,
      "state": "throttled",
      "compute": 0.5,
      "window_hours": 24,
      "spent_slots": 12,
      "allowed_slots": 12
    }
  }
}
```

The public fixture is
[`examples/quota-slot-spend-event.example.json`](../examples/quota-slot-spend-event.example.json).

Validation rule:

- write only after a fresh `quota should-run` returned `should_run=true`;
- `slots` must be positive, and `after.spent_slots` must equal
  `before.spent_slots + slots`;
- if `after.spent_slots >= after.allowed_slots`, `after.state` should be
  `throttled` and `after.should_run` should be `false`;
- do not include human reward, operator-gate approval, write-control, private
  evidence, internal links, raw logs, or production identifiers in the quota
  event.

This event is accounting, not permission. It records that compute was spent
after the normal health, operator, evidence, and quota gates had already
allowed the turn.

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
