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

`protocol_action_packet` remains in the full ledger/cold path. Because its
reconstructability is not yet proven, the capsule conservatively keeps its
current compact summary plus schema and summary hash with
`derivation_status=unproven_retain_summary`. LoopX may remove that repeated
summary from the hot path only after proving that the envelope preserves every
action-bearing residue; it must not stop persisting the source packet as part
of this projection change.

Large todo summaries, frontier diagnostics, readiness history, compatibility
fields, and warning collections stay on the referenced full-decision/status
cold paths. The envelope has an 8 KiB JSON budget and reports its measured
source/envelope byte counts.

This contract is a projection only. It does not change quota selection, todo
routing, scheduler state, history writes, or state transitions. Promoting it to
the default agent view requires separate parity evidence across delivery,
monitor, user-gate, capability-gate, workspace-guard, and blocked states.
