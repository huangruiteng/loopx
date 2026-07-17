# TurnEnvelope v0

`loopx_turn_envelope_v0` is an additive, bounded read model over an already
computed `quota should-run` decision. It gives an agent the next action and its
safety contract without replaying every diagnostic lane in the full quota
payload.

Preview it explicitly:

```bash
loopx quota should-run --goal-id <goal-id> --agent-id <agent-id> --turn-envelope
```

The default `quota should-run` output remains unchanged. The v0 envelope keeps:

- the selected todo, claim, and effective action;
- concrete user actions and gate reasons;
- required reads;
- write scope, approvals, guards, workspace/capability gates, and stop rule;
- delivery, repair, safe-bypass, and blocked-action policy;
- validation/writeback and quota-spend policy;
- the current scheduler action and cadence acknowledgement command.

The envelope also carries a bounded `contract_capsule` for interaction mode,
work-lane and execution obligations, successor/replan duties, automation
liveness, vision/handoff state, and actionable warning references. A canonical
`action_signature` is independently built from the full decision and from the
envelope; matching hashes prove the covered action dimensions agree for that
projection. They do not prove that every possible quota state has test
coverage.

Action-signature coverage is versioned independently from the envelope schema.
`turn_envelope_action_dimensions_v0` covers the original action projection;
`turn_envelope_action_dimensions_v1` additionally covers a blocking user
gate's `response_plan`. Base/head qualification accepts that declared v0-to-v1
migration as a review signal, while a digest change without a supported
coverage migration still fails closed.

`protocol_action_packet` remains in the full decision/cold path. The envelope
reconstructs its ordered semantic fields from `action`, `user`, work-lane,
automation, and scheduler contracts, while carrying the explicit
`llm_policy=no_api` invariant. When the reconstruction matches exactly, the
capsule keeps only the source summary hash and derivation status. If a compact
action differs, it keeps only that field-level `residue`; if an older or opaque
packet cannot be reconstructed, it retains the original summary. This removes
repetition only after parity and does not change source packet persistence or
the default quota output.

Large todo summaries, frontier diagnostics, readiness history, compatibility
fields, and warning collections stay on the referenced full-decision/status
cold paths. The envelope has an 8 KiB JSON budget and reports its measured
source/envelope byte counts.

Hot-path fields may use explicit references when the inline value would only
repeat another authoritative field. In particular,
`action.selected_todo.text_ref = action.recommended_action` means the selected
todo text is already present as the recommended action. Scheduler reset plans
keep the exact acknowledgement argv inline when it satisfies the executable
argv limits; the failure argv stays behind `failure_cli_args_detail_ref` until
the host update actually fails. Consumers must follow these references instead
of treating the omitted duplicate as missing state.

This contract is a projection only. It does not change quota selection, todo
routing, scheduler state, history writes, or state transitions. Promoting it to
the default agent view requires separate parity evidence across delivery,
monitor, user-gate, capability-gate, workspace-guard, and blocked states.

## Multi-State Parity Evidence

`tests/fixtures/turn_envelope_state_matrix.json` is the durable synthetic
promotion fixture. It covers delivery, monitor quiet-skip, user gate,
capability gate, workspace guard, autonomous replan, successor replan,
blocked, and throttled decisions. Every case must preserve the canonical action
signature, reconstruct `protocol_action_packet`, and remain within the 8 KiB
budget.

The current matrix produces envelopes from 4,866 to 5,602 bytes, with 66.44% to
69.36% reduction from the full synthetic decision. This is sufficient to keep
the projection available as an opt-in host view. It is not sufficient to change
the default CLI response: default promotion still requires shadow parity from a
real host integration, no consumer regression with the full decision available
as a cold path, and explicit compatibility acceptance for the default-view
change.
