# Long-Task Cadence Policy

LoopX should preserve the native long-horizon strength of an agent loop.
Heartbeat automation is useful because it keeps goals alive, but it can also
train the controller into tiny status-only turns if every wakeup is treated as a
small independent task. The cadence policy describes how product surfaces and
future server runners should choose the size of an agent work segment.

## Problem

A recurring heartbeat can fragment work in two bad ways:

- the agent spends most turns restating status or editing state without a
  validated artifact;
- a blocked high-priority item causes the controller to drift into unrelated
  low-value work without telling the operator what remains blocked.

The right behavior is not simply "run longer." The control plane should widen a
turn only when the selected work is safe, in scope, and likely to produce a
coherent artifact. User gates, credentials, private material, destructive git,
production actions, paid resource boundaries, and public benchmark submissions
still stop or ask.

## Product Presets

LoopX should expose a small preset set instead of making users tune many
heuristics directly:

| Preset | Intended Use | Minimum Segment |
| --- | --- | --- |
| `ultra-long` | unattended research, benchmark sweeps, migration campaigns | finish a coherent milestone or write a hard blocker |
| `long` | default for trusted heartbeat goals and product-mode benchmark work | implementation plus focused validation plus state writeback |
| `medium` | active collaboration where the user expects visible progress often | one reviewable artifact or one repaired control-plane contract |
| `short` | diagnosis, review, or gate-heavy work | one narrow inspection, repair, or explicit question |

The default for connected autonomous goals should be `long`: a single wakeup
should usually deliver code/docs plus validation/writeback, not a small status
mutation. Interactive UI sessions can present `medium` as a friendlier default
while still letting advanced users opt into `long` or `ultra-long`.

Preset selection should be explicit in product surfaces:

- connected autonomous goals default to `long`;
- visible TUI sessions default to `medium` unless the user installs a recurring
  goal loop;
- diagnosis, PR review, and gate-heavy work should use `short`;
- `ultra-long` requires an explicit user/controller opt-in and a current
  boundary contract that allows the larger segment.

## Signals

The policy should be based on public-safe control-plane signals, not raw
conversation transcripts or raw local logs:

- `delivery_batch_scale`: whether recent turns were `single_surface`,
  `multi_surface`, or `implementation`;
- `delivery_outcome`: whether recent turns produced `primary_goal_outcome`,
  `outcome_progress`, a blocker, or monitor-only status;
- small-step streak: consecutive eligible turns that did not produce an
  implementation, durable design, validated evidence, or blocker;
- compact turn duration: scheduler-visible elapsed minutes for a completed
  turn, rounded or bucketed so it does not expose transcripts or local logs;
- progress granularity: a compact enum such as `status_only`,
  `single_surface`, `multi_surface`, `implementation_plus_validation`, or
  `milestone`;
- validation/writeback ratio: whether artifacts are routinely validated and
  reflected into active state/history;
- user-gate projection: whether a higher-priority blocked item is surfaced
  while lower-priority safe work continues;
- interface-budget cadence: whether status surfaces remain fresh without
  turning freshness checks into the main work.

## Too-Small Batch Detection

Each completed eligible heartbeat can contribute one compact sample:

```json
{
  "turn_duration_minutes": 11,
  "progress_granularity": "single_surface",
  "delivery_batch_scale": "single_surface",
  "delivery_outcome": "surface_only",
  "validated_artifact": false,
  "state_writeback": true
}
```

The controller should mark `too_small_heartbeat_batch=true` only when all of
these are true:

- the goal was eligible and no user/controller gate blocked the selected path;
- the same preset and boundary contract still apply;
- the recent streak is below the preset's minimum segment;
- the turn did not write a hard blocker explaining why widening was unsafe.

For the default `long` preset, the minimum useful batch is
`implementation_plus_validation_writeback`: one coherent artifact, targeted
validation, and LoopX writeback. A docs-only batch can still satisfy
`long` when the selected todo is a durable design contract and the matching
smoke or public boundary check passes. Status-only refreshes, repeated brief
checks, and unvalidated single-surface edits should increment the too-small
streak.

## Controller Behavior

When a goal is eligible and safe, the controller should run a steering audit
before delivery, then choose one bounded segment at the preset's scale.

If the small-step streak crosses the profile threshold, the next eligible turn
should widen the minimum segment. For `long`, that means one coherent artifact
plus targeted validation and state writeback. For `ultra-long`, it can mean a
larger milestone, but only while the same boundary contract remains valid.

If a high-priority task is blocked and a lower-priority fallback is safe, the
controller may continue the fallback, but the blocked priority must remain
visible in quota/status/heartbeat output. The fallback is not allowed to become
the main story silently.

If the selected action requires a write scope that is missing from
`goal_boundary.write_scope`, the next action should become boundary projection
repair or a concrete user/controller gate. Cadence widening must not paper over
a stale checkpointed decision.

When `too_small_heartbeat_batch=true`, the next eligible turn should widen or
write a blocker. It should not spend another quota slot on a pure status
mutation unless the quota guard says monitor-only quiet skip or a user gate is
the actual state.

## Public Fields

A future status/quota projection can carry these compact fields:

```json
{
  "long_task_cadence": {
    "schema_version": "long_task_cadence_policy_v0",
    "cadence_preset": "long",
    "preset_source": "connected_autonomous_default",
    "turn_duration_minutes": 11,
    "progress_granularity": "single_surface",
    "small_step_streak": 2,
    "too_small_heartbeat_batch": true,
    "recommended_batch_granularity": "implementation_plus_validation_writeback",
    "widen_next_turn": true,
    "blocked_priority_fallback_visible": true
  }
}
```

These fields are policy hints. They do not grant permissions and do not replace
the existing quota, interaction contract, goal boundary, or public/private scan.

## Rollout

1. Keep the current `execution_profile` fields as the compatibility layer.
2. Add preset-derived projections to status/quota after the benchmark adapters
   stop carrying benchmark-specific state shapes.
3. Teach heartbeat prompts to say when a turn is being widened because recent
   work was too small.
4. Move rolling metrics into the future server runner so the product can offer
   stable "ultra-long / long / medium / short" controls without each agent
   inventing its own heuristic.

The current smoke for this design is
`python3 examples/long-task-cadence-policy-smoke.py`.
