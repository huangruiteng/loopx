# Peer Supervisor v0

## Status

Experimental and default-off. This protocol adds an observation and proposal
layer over registered `peer_v1` agents. It does not add a new scheduler, create
agent sessions, or grant one identity durable authority over another.

The design is informed by Shepherd's runtime-supervisor experiments, where a
stronger observer can compare concurrent effect streams and choose to inject,
handoff, or discard a branch. LoopX keeps those actions as typed proposals until
a host runtime exposes the required execution capabilities and returns evidence.

## Why A Supervisor

Several equal peers are useful for independent progress, but they give the user
multiple places to inspect. An optional supervisor provides one synthesis
channel that can compare:

- goal status and user gates;
- each peer's quota and interaction contract;
- todo claims, leases, and continuation state;
- recent agent-scoped evidence;
- compact runtime effect or state references.

The user can use the supervisor task as the preferred control-room conversation
while several peers run. The user may still talk directly to any peer. Decisions
that change goal authority remain LoopX user todos or gates, so they do not live
only in a supervisor transcript.

## Configuration

The supervisor must already be a registered peer. Enabling it is explicit:

```bash
loopx configure-goal \
  --goal-id <goal-id> \
  --supervisor-agent <registered-agent-id> \
  --supervised-agent <peer-a> \
  --supervised-agent <peer-b> \
  --execute
```

Omit `--supervised-agent` to observe every registered peer except the supervisor.
Disable the feature with:

```bash
loopx configure-goal --goal-id <goal-id> --clear-supervisor --execute
```

Configuration is stored as `coordination.supervisor` with schema
`peer_supervisor_v0`. Absence means disabled. The canonical configuration has
`execution_mode=proposal_only`.

Generate the dedicated task body after configuration:

```bash
loopx supervisor-prompt \
  --goal-id <goal-id> \
  --agent-id <supervisor-agent-id>
```

## Decision Contract

`supervisor_decision_v0` uses an enum-like closed set:

| Kind | Meaning | Required host capability |
| --- | --- | --- |
| `observe` | Keep watching; no intervention is justified. | none |
| `inject` | Propose a bounded message to an existing session. | `session_message_injection` |
| `handoff` | Propose continuing a target from a named source state. | `session_state_fork`, `workspace_state_transfer` |
| `discard` | Propose terminating a failed branch while retaining compact evidence. | `session_termination` |

Every proposal names reason codes and compact evidence references. `inject`
names a target and message. `handoff` names source, target, and state reference.
`discard` names target and state reference.

The v0 CLI does not execute these actions. Missing host capabilities leave the
proposal unexecuted; a model response is never accepted as proof that a session
was injected, forked, or terminated. Destructive actions require explicit host
authority even after an executor exists.

## Authority Boundaries

- The supervisor is an equal peer with an extra observation responsibility.
- It cannot claim another peer's todo, spend another peer's quota, or rewrite a
  user gate merely to resolve a proposal.
- Review and handoff remain ordinary task policies; the supervisor does not
  become a hidden review owner.
- Legacy `primary_agent` fields remain confined to the existing exactly-once
  migration reader. They are not a live configuration model and are not used by
  this protocol.

This separation lets LoopX test whether richer synthesis improves delivery
without coupling the State Kernel to a particular session runtime or bringing
durable hierarchy back into `peer_v1`.

## References

- [Shepherd: A Meta-Agent for Versioned Execution](https://arxiv.org/abs/2605.10913)
- [CooperBench](https://arxiv.org/abs/2601.13295)
- [Shepherd repository](https://github.com/shepherd-agents/shepherd)
