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
- validation/writeback and quota-spend policy;
- the current scheduler action and cadence acknowledgement command.

Large todo summaries, frontier diagnostics, readiness history, compatibility
fields, and warning collections stay on the referenced full-decision/status
cold paths. The envelope has an 8 KiB JSON budget and reports its measured
source/envelope byte counts.

This contract is a projection only. It does not change quota selection, todo
routing, scheduler state, history writes, or state transitions. Promoting it to
the default agent view requires separate parity evidence across delivery,
monitor, user-gate, capability-gate, workspace-guard, and blocked states.
