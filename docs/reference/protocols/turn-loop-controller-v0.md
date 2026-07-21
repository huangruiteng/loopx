# loop_turn_loop_disposition_v0

`loop_turn_loop_disposition_v0` is the pure Turn Loop Controller transition
contract. It decides what a governed loop does next from one Turn receipt plus
a fresh quota/scheduler decision, and nothing else.

`loopx turn run-once` remains the atomic governed executor: decide, execute one
bounded host segment, validate independently, write back, spend once. The
controller does not replace it, schedule processes, call host wake APIs, invoke
a model, sleep, write state, or spend quota. Scheduler process management,
host-specific wake adapters, and operator presentation are later slices in the
Turn Loop Controller plan.

## Inputs

| Input | Shape | Notes |
| --- | --- | --- |
| `turn_receipt` | one Turn receipt mapping (`result_kind`, optional `lineage`) | may be absent when no Turn has run yet |
| `quota_decision` | fresh `loopx_turn_envelope_v0` | must carry a matching action signature |
| `bounded_turn_budget` | optional `max_turns` + `completed_turns` | bounds validated-progress sequences |

## Output

Exactly one typed disposition:

| disposition | meaning | quota |
| --- | --- | --- |
| `run_now` | fresh decision allows the next delivery Turn | no spend by the controller |
| `wait` | quiet cadence, blocked delivery, or fail-closed hold | no spend |
| `user_action_required` | a concrete user action is projected by receipt or decision | no spend |
| `repair` | repair-class recovery is required before any successor Turn | no spend |
| `replan` | replan-class recovery; see continuation boundary below | no spend |
| `terminal` | terminal postcondition met or bounded budget exhausted | no spend |

Every payload carries `spends_quota=false`, `launches_host=false`, and
`writes_state=false`.

## Decision Table

| receipt | fresh decision | disposition |
| --- | --- | --- |
| none | delivery allowed | `run_now` |
| none | quiet / cadence-only | `wait` |
| `validated_completion` | any | `terminal` |
| `validated_progress`, budget remaining | delivery allowed | `run_now` |
| `validated_progress`, budget exhausted | any | `terminal` |
| `validated_progress` | no delivery | `wait` |
| `repair_required` | any | `repair` |
| `replan_required` | any | `replan` |
| `user_action_required` | any | `user_action_required` |
| `wait` | any | `wait` |
| `host_failure` / `validation_failed` / `writeback_failed` / `quota_spend_failed` | any | `repair` (route before any successor Turn) |
| replan-class decision action (`autonomous_replan*`) | — | `replan` |
| repair-class decision action (`*_repair*`) | — | `repair` |
| user action projected by decision | — | `user_action_required` |
| receipt lineage mismatches decision `(goal_id, agent_id)` | — | `wait` with `stale_receipt` reason |
| malformed decision, broken signature, or unknown receipt kind | — | `wait` with `contract_error` reason |

## Replan Continuation Boundary

`replan` never permits rerunning the same stale todo merely because a host
session is resumable. The disposition payload carries
`replan_continuation`:

- `requires_bounded_delta=true`: a bounded `todo_delta` or `vision_delta` must
  be written before any successor Turn;
- `fresh_envelope_required=true`: the next Turn must come from a fresh
  TurnEnvelope, not a replayed one;
- `stale_todo_rerun_allowed=false`.

This mirrors the autonomous-replan and two-stall contracts: no runnable todo
with an open acceptance gap, a terminal/obsolete/incompatible selected todo,
validated negative evidence, or two eligible turns without material progress
all require replan rather than another delivery attempt.

## Boundary

The controller is a pure function. It must not invoke a model, sleep, mutate a
host scheduler, write state, or spend quota. Unknown or contradictory input
fails closed to `wait` with an explicit reason; it never guesses a recovery or
fabricates a host, gate, or user action.
