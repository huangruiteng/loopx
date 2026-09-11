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

The controller is an exported transition API, not a loop implicitly started by
`loopx turn run-once`. The CLI does not currently call `decide_loop_disposition`
or persist a `BoundedTurnBudget`. Both `max_turns` and `completed_turns` must be
supplied by an integrating caller; there is no CLI or product default of three
Turns. The budget applies to continued `validated_progress` on the same Todo,
not a chain of completed Todos and not fine-grained planning mode.

## Inputs

| Input | Shape | Notes |
| --- | --- | --- |
| `turn_receipt` | one `ValidatedTurnReceipt` qualified from `loopx_turn_execution_v0` | may be absent when no Turn has run yet; material results require the complete M7 settlement evidence described below |
| `quota_decision` | fresh `loopx_turn_envelope_v0` | must satisfy the shared typed envelope contract |
| `predecessor_turn_key` | causal binding supplied by the outer continuation adapter | required with a receipt and must equal its `turn_key`; it is deliberately not an unsigned field inside the quota envelope |
| `bounded_turn_budget` | one `BoundedTurnBudget` | required when the receipt is `validated_progress` |

Inputs are typed and validated at the boundary. The controller does not accept
caller-authored `result_kind + lineage` or phase-only mappings. A receipt is
qualified from one public `loopx_turn_execution_v0` whose transaction receipt
has `ok=true`, a supported result kind, full `(goal_id, agent_id, todo_id)`
lineage, and a `turn_key`. Material results (`validated_completion` /
`validated_progress`) additionally require all of these facts:

- execution and transaction receipt are both `committed`;
- the core M7 settlement succeeded and emitted exactly the ordered
  `validation -> durable_writeback -> quota_spend` receipt chain;
- every settlement receipt is committed under the same `effect_id`, and that
  id matches the transaction's typed settlement identity;
- public execution effects prove durable state write and one quota spend;
- the scheduler handoff completed;
- `validated_completion` carries the durable Todo lifecycle outcome
  (`successor`, `active_goal`, or `no_followup`) from the required explicit
  `completion_continuation` field. Missing or contradictory completed state is
  rejected rather than inferred.

This keeps settlement truth in the core Effect Program rather than duplicating
it as Turn-controller phase logic. A budget must carry strict integer domains (`type(...) is int`,
`max_turns > 0`, `0 <= completed_turns <= max_turns`) and the same lineage as
the fresh decision. When a receipt is supplied, the outer adapter must bind the
fresh decision with a separate `predecessor_turn_key` equal to the receipt's
`turn_key`; an old receipt cannot be replayed against a later envelope. Invalid
or stale input raises `ValueError`; it is never encoded as a disposition.

## Output

Exactly one typed disposition:

| disposition | meaning | quota |
| --- | --- | --- |
| `run_now` | fresh decision allows the next delivery Turn | no spend by the controller |
| `wait` | quiet cadence or blocked delivery | no spend |
| `stop` | the current iteration ended without authorizing a retry or successor | no spend |
| `user_action_required` | a concrete user action is projected by receipt or decision | no spend |
| `repair` | repair-class recovery is required before any successor Turn | no spend |
| `replan` | replan-class recovery; see continuation boundary below | no spend |
| `terminal` | fresh Goal frontier plus durable no-follow-up prove Goal closure | no spend |

The output space is exactly these seven dispositions. There is no
`contract_error` disposition: contract failures are rejected at the typed-input
boundary. Every payload carries `spends_quota=false`, `launches_host=false`,
and `writes_state=false`.

## Decision Table

| receipt | fresh decision | disposition |
| --- | --- | --- |
| none | delivery allowed | `run_now` |
| none | quiet / cadence-only | `wait` |
| none | fresh `terminal_no_followup` Goal frontier | `terminal` |
| `validated_completion` + durable `successor` | selected Todo is a declared successor | route the fresh decision (`run_now`, `wait`, `repair`, `replan`, or user action) |
| `validated_completion` + durable `active_goal` | fresh Goal frontier selects a different Todo | route the fresh decision |
| `validated_completion` + durable `no_followup` | fresh Goal frontier is also terminal no-follow-up | `terminal` |
| `validated_completion` | stale, missing, or undeclared continuation | `ValueError` |
| `validated_progress`, budget remaining | delivery allowed | `run_now` |
| `validated_progress`, budget exhausted | any | `replan` with bounded-delta requirement |
| `validated_progress` | no delivery | `wait` |
| `repair_required` | any | `repair` |
| `replan_required` | any | `replan` |
| `user_action_required` | any | `user_action_required` |
| durable `no_followup` + fresh terminal frontier + decision user action | — | `terminal` (proven Goal closure wins) |
| continuing completion + decision user action | — | `user_action_required` |
| `wait` | any | `wait` |
| `iteration_failed` | no decision user action | `stop` (iteration-scoped, not Goal terminal) |
| `iteration_failed` | decision user action | `user_action_required` (fresh decision precedence) |
| retryable `host_failure`, attempt budget remains | delivery or wait | `wait` with a same-Turn bounded-backoff continuation |
| retryable `host_failure`, attempt budget exhausted | any | `repair` |
| non-retryable or legacy `host_failure` / `validation_failed` / `writeback_failed` / `quota_spend_failed` | any | `repair` (route before any successor Turn) |
| replan-class decision action (`autonomous_replan*`) | — | `replan` |
| repair-class decision action (`*_repair*`) | — | `repair` |
| user action projected by decision | — | `user_action_required` |

## Precedence And Fail-Closed Rules

- `validated_completion` proves a Todo transition, not Goal closure. A
  declared successor or active Goal frontier continues through the fresh
  decision. Only durable `no_followup` plus a fresh terminal Goal frontier may
  produce `terminal`. An undeclared successor, reselected completed Todo, or
  missing lifecycle outcome raises `ValueError`.
- The lifecycle may recover only an explicit `active_goal` completion to
  `no_followup` within the same `completion_turn_key`. That audited recovery is
  not a fourth continuation and never weakens the controller's fresh-frontier
  requirement.
- A validation-only intermediate, phase-only committed mapping, incomplete
  settlement receipt chain, mismatched effect identity, missing durable
  effects, or incomplete scheduler handoff cannot drive `terminal`, `run_now`,
  or any other material continuation.
- When a receipt is supplied, the outer adapter must supply a separate
  `predecessor_turn_key` equal to the receipt's `turn_key`. A missing or
  mismatched key raises `ValueError` (`stale_receipt`); this closes the stale
  replay gap without adding an unsigned field to `loopx_turn_envelope_v0`.
- Every other user-action signal (from receipt or decision) routes to
  `user_action_required` before delivery dispositions.
- A typed retryable Host failure never authorizes a different model or a new
  Todo. The controller returns `wait` with the exact attempt, maximum attempts,
  retry delay, `same_turn=true`, and `model_fallback_allowed=false`. The outer
  scheduler may wake that same failed Turn with explicit retry authority after
  the delay. Once the attempt budget is exhausted, the controller returns
  `repair`; legacy or malformed failure metadata cannot opt into retry.
- `iteration_failed` is an ordinary bounded-loop outcome, not an infrastructure
  failure. It stops only the current iteration, sets neither retry nor replan
  continuation, creates no successor, and does not claim Goal terminal closure.
  A later iteration starts only through a new explicit controller decision.
- The fresh decision must satisfy the shared Turn envelope contract
  (`loopx_turn_envelope_v0` schema, non-empty equal signature hashes, and an
  in-budget compaction) via the same typed route the Turn plan driver uses;
  forged or truncated envelopes raise `ValueError`, never `run_now`.
- `validated_progress` may continue only with a proven `BoundedTurnBudget`
  whose lineage matches the fresh decision; without it the controller raises
  `ValueError` instead of guessing an unbounded continuation. Budget
  exhaustion routes to `replan`, not `terminal`, because a bounded Turn chain
  ending is not evidence that the Goal ended.
- Input validity is enforced at the typed-input boundary, not encoded as an
  eighth disposition. The transition output space is always one of the seven
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
