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
unrelated candidate from producing a false equivalence result. The comparator
then checks these hard behavior dimensions:

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

## Promotion Boundary

This contract is one gate in a larger promotion process. Turning a candidate
packet into the default requires deterministic state-matrix parity, a complete
field-classification ledger, repeated paired model runs over representative and
counterfactual states, zero safety drift, bounded behavioral drift, and explicit
owner review. Missing provider access, an unknown schema, or incomplete
evidence keeps the full packet as the default.
