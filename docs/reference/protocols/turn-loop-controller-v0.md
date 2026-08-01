# loop_turn_loop_disposition_v0

`loop_turn_loop_disposition_v0` is the pure Turn Loop Controller transition
contract. It decides what a governed loop does next from one validated Turn
receipt plus a fresh quota/scheduler decision, and nothing else.

`loopx turn run-once` remains the atomic governed executor: decide, execute one
bounded host segment, validate independently, write back, spend once. The
controller does not replace it, schedule processes, call host wake APIs, invoke
a model, sleep, write state, or spend quota. Scheduler process management,
host-specific wake adapters, and operator presentation are later slices in the
Turn Loop Controller plan.

## Inputs

| Input | Shape | Notes |
| --- | --- | --- |
| `turn_receipt` | one `ValidatedTurnReceipt` (proven by `validate_loopx_turn_receipt`) | may be absent when no Turn has run yet |
| `quota_decision` | fresh `loopx_turn_envelope_v0` | must satisfy the shared typed envelope contract |
| `bounded_turn_budget` | one `BoundedTurnBudget` | required when the receipt is `validated_progress` |

Inputs are typed and validated at the boundary. The controller does not accept
caller-authored `result_kind + lineage` mappings: a receipt must be a
`loopx_turn_receipt_validation_v0` result with `ok=true`, a supported result
kind, and full `(goal_id, agent_id, todo_id)` lineage. A budget must carry
strict integer domains (`type(...) is int`, `max_turns > 0`,
`0 <= completed_turns <= max_turns`) and the same lineage as the fresh
decision. Invalid or stale input raises `ValueError`; it is never encoded as a
disposition.

## Output

Exactly one typed disposition:

| disposition | meaning | quota |
| --- | --- | --- |
| `run_now` | fresh decision allows the next delivery Turn | no spend by the controller |
| `wait` | quiet cadence or blocked delivery | no spend |
| `user_action_required` | a concrete user action is projected by receipt or decision | no spend |
| `repair` | repair-class recovery is required before any successor Turn | no spend |
| `replan` | replan-class recovery; see continuation boundary below | no spend |
| `terminal` | terminal postcondition met or bounded budget exhausted | no spend |

The output space is exactly these six dispositions. There is no
`contract_error` disposition: contract failures are rejected at the typed-input
boundary. Every payload carries `spends_quota=false`, `launches_host=false`,
and `writes_state=false`.

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
| `validated_completion` + decision user action | — | `terminal` (completion wins) |
| `wait` | any | `wait` |
| `host_failure` / `validation_failed` / `writeback_failed` / `quota_spend_failed` | any | `repair` (route before any successor Turn) |
| replan-class decision action (`autonomous_replan*`) | — | `replan` |
| repair-class decision action (`*_repair*`) | — | `repair` |
| user action projected by decision | — | `user_action_required` |

## Precedence And Fail-Closed Rules

- A `validated_completion` receipt wins over a decision-only user action, but
  only after the receipt is proven valid and fresh. Material receipts must
  carry full `(goal_id, agent_id, todo_id)` lineage, and any mismatch with the
  fresh decision (including `todo_id`) raises `ValueError` (`stale_receipt`),
  never `terminal`.
- Every other user-action signal (from receipt or decision) routes to
  `user_action_required` before delivery dispositions.
- The fresh decision must satisfy the shared Turn envelope contract
  (`loopx_turn_envelope_v0` schema, non-empty equal signature hashes, and an
  in-budget compaction) via the same typed route the Turn plan driver uses;
  forged or truncated envelopes raise `ValueError`, never `run_now`.
- `validated_progress` may continue only with a proven `BoundedTurnBudget`
  whose lineage matches the fresh decision; without it the controller raises
  `ValueError` instead of guessing an unbounded continuation.
- Input validity is enforced at the typed-input boundary, not encoded as a
  seventh disposition. The transition output space is always one of the six
  dispositions above.

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
host scheduler, write state, or spend quota. Invalid or stale input is rejected
at the typed-input boundary with a `ValueError`; it never guesses a recovery
or fabricates a host, gate, or user action.
