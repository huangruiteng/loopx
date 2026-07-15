# Model Behavior Qualification v0

`model_behavior_qualification_v0` is a low-frequency validation contract for
agent-facing control-plane packet changes. It complements deterministic smokes;
it does not replace them and does not change the default `quota should-run`
view.

The core is provider-neutral. It defines the actor request, no-write sandbox,
strict model decision, compact receipt, and paired comparison. The optional
direct Ark adapter supports low-frequency Doubao 2.1 shadow runs without
changing the default quota path.

## Pair Contract

One qualification case runs the same actor against two public-safe inputs:

1. `full_packet`: the current full `quota should-run` decision;
2. `candidate_packet`: the candidate `loopx_turn_envelope_v0` projection.

Both arms share `qualification_id` and `actor_ref`. Before either actor call,
the pair runner verifies that the candidate's action signature matches and its
`source_decision_hash` identifies the paired full packet. This prevents an
unrelated candidate from producing a false equivalence result. The runner also
recomputes both semantic signature documents instead of trusting the
candidate's stored `matches` flag; a field ablation therefore fails before any
provider call. The comparator then checks these hard behavior dimensions:

- decision: execute, wait, ask the user, or stop;
- selected todo;
- user action required;
- must attempt work;
- delivery allowed;
- quiet no-op allowed;
- external write requested.

Any drift in those dimensions fails the pair. An external-write request or a
quiet-noop/must-attempt contradiction also fails even when both arms agree.
The receipt separately records an ordered, allowlisted
`intended_action_kinds` sequence such as inspect, edit, test, writeback, and
spend. A sequence difference is behavior drift even when the high-level
decision is unchanged. Reason codes remain diagnostic and do not make a safety
drift pass.

Each arm also has an explicit terminal boundary. A successful arm emits the
compact decision receipt above. If provider transport or actor-result
validation fails, the pair raises a `model_behavior_arm_terminal_receipt_v0`
error containing only the failed arm, a bounded error code, and digests for any
arm that already completed. It never retains exception detail, packets,
prompts, or provider responses. Corpus mode records that failure as
`actor_failed` instead of losing which arm stopped the pair.

## Corpus And Grader

`model_behavior_corpus_v0` is an in-memory qualification input assembled from
the deterministic TurnEnvelope state matrix, retained public-safe decisions,
counterfactual patches, and candidate field ablations. Paired arms run in a
seeded randomized order and repeat at least twice so ordering and stochastic
drift are visible. First-action and trajectory-action divergence are reported
separately from hard-invariant drift.

The durable corpus result contains case ids, source kinds, compact drift field
names, safety codes, and receipt digests. It excludes packets, prompts, raw
responses, and conversations. Candidate ablations are expected to fail closed;
ordinary cases must remain equivalent on every repeat.

Coverage is explicit. Corpus mode requires a bounded `semantic_contract` for
the concrete user question, required reads, gate/stop state, write scope, spend
rule, scheduler action, vision continuation, and actionable warnings. The core
derives the expected contract independently from each arm's packet and compares
the model result with that source before comparing arms. Two arms that repeat
the same wrong or incomplete interpretation therefore fail source alignment.

Receipts retain only per-dimension digests, completeness, and mismatch field
names; they do not retain semantic-contract values. Complete aligned coverage
can pass the corpus gate, but the overall promotion decision remains false
until repeated live-model evidence and explicit owner review are present.

### Retained Public-Safe Decisions

Real shadow decisions may be retained only through the explicit local-runtime
`model_behavior_retained_case_v0` store. Each full packet must pass the same
public-safety and schema validation as an actor request, remain below the case
size limit, and carry a stable id and digest. Writes are atomic, mode `0600`,
bounded to 24 cases, and rejected when the requested runtime root is inside a
git worktree. Existing ids are idempotent only when their complete content
matches.

The store is never populated automatically. It contains no model response,
conversation, credential metadata, or candidate packet; a current candidate is
rebuilt in memory when the case is loaded into a corpus. Store receipts expose
only case id, digest, created/idempotent status, and count, never the packet or
local path.

## No-Write Boundary

The actor request always declares:

- tools disabled;
- filesystem writes disabled;
- external writes disabled;
- network limited to the model provider transport.

The adapter must return parsed JSON and an empty `tool_calls` list. The core
rejects non-empty tool calls, unknown schemas, unknown response fields,
credential-shaped fields, credential-like values, and local absolute paths.
There is no fallback to an unrecognized packet or model response.

The sandbox is a qualification boundary, not an authority grant. It never
authorizes repository writes, public comments, publishing, production actions,
or quota writeback.

## Persistence Boundary

The durable output is `model_behavior_decision_receipt_v0`. It contains compact
decision dimensions, reason codes, safety violations, and SHA-256 digests. It
does not contain:

- the source packet;
- prompts or model reasoning;
- raw model responses;
- tool payloads;
- credentials or provider authentication metadata.

`model_behavior_pair_result_v0` retains only the drift map, safety violations,
and receipt digests. Raw model conversations belong in ignored local runtime
state and are never a public repository artifact.

## Direct Doubao Shadow Actor

`DoubaoModelBehaviorActor` calls only the canonical Ark Chat Completions
endpoint and allowlists the versioned Doubao 2.1 Pro and Turbo model ids. It
does not accept an arbitrary base URL, does not follow redirects, does not send
tool definitions, and converts transport failures into bounded errors without
provider response bodies.

The provider-visible user input contains only the arm, a locally derived
`canonical_selected_todo_id`, the `semantic_contract_required` flag, and that
arm's packet. Qualification ids, sandbox declarations, actor instructions, and
response-contract metadata are validated locally but are not repeated in the
model prompt. The actor disables provider deep thinking for this deterministic
extraction task and reserves 4096 output tokens so the bounded semantic
contract is not constrained by the former 1200-token response budget.

The actor derives `canonical_selected_todo_id` independently for each arm from
the canonical selected-todo field: top-level `selected_todo.todo_id` in a full
packet or `action.selected_todo.todo_id` in a TurnEnvelope. The model must copy
that value into `selected_todo_id`, including `null`; todo ids found only in
summaries, diagnostics, handoffs, history, or other cold-path references are
not selected work. The pair's pre-provider action-signature check still fails
closed when the candidate actually omits or changes selected work.

Live use requires `ARK_API_KEY` to be injected into the process environment.
The key is held only by the in-memory adapter and is never placed in a LoopX
packet, receipt, error, command argument, fixture, or repository file. The
optional `LOOPX_MODEL_BEHAVIOR_MODEL` selector can choose one of the two
allowlisted Doubao 2.1 model ids. Missing credentials, unsupported models,
malformed provider JSON, or non-conforming decisions fail closed. LoopX does
not search credential stores and does not route these calls through a memory
system or another agent service.

The live actor is deliberately absent from PR smoke and normal CI. It belongs
in manually triggered or low-frequency shadow qualification where cost,
repetition, corpus selection, and promotion policy are explicit. Only compact
decision receipts and paired drift results may become durable evidence.

## New-User Onboarding Closed Loop

`onboarding_actual_behavior_qualification_v0` extends the same low-frequency
boundary to the first new-user transaction. Its durable contract has one arm:
the currently shipped default `start-goal --guided` packet. The qualification
does not retain a retired full-detail implementation as a second product
contract.

The closed loop checks three decisions:

1. the entry turn must select `connect_if_needed` from the actual default
   packet;
2. an allowlisted local transition runner performs the canonical connection in
   an isolated fixture, after which the model must select
   `continue_validation` for the healthy executable todo;
3. a known-bad `state_projection_gap` observation calibrates the model's
   `repair_projection` decision against the regression class tracked by issue
   #2134: a visible onboarding Next Action without an executable structured
   todo.

Two checks are deliberately independent. Before any provider call, a stable
behavior oracle requires the canonical connect, refresh, host-activation, and
quota commands; goal and agent identity; no write or quota spend during the
preview; and host-loop activation only after todo writeback. The model then
has to reproduce the semantic contract derived from the actual packet. This
separation prevents an implementation and its source-alignment expectation
from deleting the same behavior and still passing.

The model never supplies a shell command to the transition runner. The runner
is a caller-owned allowlist and returns only the compact
`onboarding_postcondition_observation_v0` shape. A missing command or host-loop
contract fails before model invocation; a damaged actual postcondition fails
the qualification even when the model correctly recognizes the damage.

The result retains only source-alignment flags, route names, safety codes, and
receipt digests. Packets, observations, model responses, local paths, and
credentials are not retained. It always sets
`automatic_release_promotion_allowed=false`.

For a sensitive behavior-changing pull request, maintainers may additionally
run a temporary base/candidate differential evaluation. That comparison is PR
evidence, not a merged API, fixture, or permanent test arm. Once the candidate
becomes the default, the one-arm qualification follows the new actual packet;
changing the independent behavior invariants remains an explicit reviewable
contract change.

This profile is a local/manual gate for sensitive agent-facing changes and
release qualification. Deterministic onboarding fixtures and catalog canaries
remain the normal CI gate. A future trusted scheduled job may invoke the live
profile with injected credentials and explicit cost limits, but ordinary pull
requests must not depend on provider availability, latency, rate limits, or
stochastic output.

## Promotion Boundary

This contract is one gate in a larger promotion process. Turning a candidate
packet into the default requires deterministic state-matrix parity, a complete
field-classification ledger, repeated paired model runs over representative and
counterfactual states, zero safety drift, bounded behavioral drift, and explicit
owner review. Missing provider access, an unknown schema, or incomplete
evidence keeps the full packet as the default.
