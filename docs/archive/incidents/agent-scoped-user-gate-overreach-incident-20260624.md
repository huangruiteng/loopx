# Agent-Scoped User Gate Overreach Incident

Date: 2026-06-24

Audience: LoopX status/quota owners, project-agent controller authors,
self-repair maintainers, and benchmark/product-lane operators.

## Summary

A user-gate todo was correctly scoped to one registered agent with
`blocks_agent=<target-agent>`, but `quota should-run --agent-id
<other-agent>` still treated that todo as a current-agent owner gate. The
non-target agent had runnable work, but its interaction contract became
`user_gate` and `delivery_allowed=false`.

The operational consequence was subtle but serious: one agent's legitimate
user decision stalled an unrelated agent lane. In the observed shape, a
product-capability gate for a Lark Kanban target could block a main-control /
benchmark lane even though the benchmark lane had its own claimed executable
todo.

## Public-Safe Shape

This incident is recorded without raw active-state payloads, private logs,
trajectories, local paths, verifier output, or internal links. The reusable
shape is:

```text
quota call = quota should-run --agent-id <agent-a>
raw quota state = operator_gate
open user todo = task_class=user_gate, blocks_agent=<agent-b>
agent A todo = claimed executable advancement todo
bad interaction = user_channel.action_required=true for agent A
bad agent channel = delivery_allowed=false for agent A
expected target-agent behavior = agent B remains blocked on the user gate
expected non-target behavior = agent A can continue bounded delivery
```

## What Went Wrong

1. **`blocks_agent` was visible but not authoritative.** The user-todo summary
   exposed `blocks_agent`, but the blocking summary counted every open user
   gate for every agent identity.

2. **Goal-level `operator_gate` leaked into agent-scoped quota.** The goal was
   legitimately waiting on a user decision for one lane. The current-agent
   quota view failed to ask whether that gate applied to the current agent
   before setting `requires_user_action=true`.

3. **The failure looked like an owner gate, not a projection bug.** Because
   the payload had a concrete user todo, the agent could keep reporting the
   gate instead of noticing that it belonged to another agent.

4. **The nearby no-candidate pattern was not the right repair.** The current
   agent was not out of work. It had a runnable todo. The bug was that another
   agent's gate overrode the runnable lane.

## Desired Semantics

`blocks_agent` on a user todo is a hard scope boundary:

| View | User Channel | Agent Channel |
| --- | --- | --- |
| target agent | notify concrete user gate | stop gated delivery |
| non-target agent with runnable work | no user action required | continue bounded delivery |
| non-target agent with no runnable work | no user action required | classify empty frontier via agent-scoped routing |
| unscoped user gate | notify concrete user gate | stop ordinary delivery |

The non-target agent may still see the other-agent gate as diagnostic context,
but it must not count that todo in its own blocking `open_count`,
`gate_open_items`, or `interaction_contract.user_channel.action_required`.

## Repair

The durable repair landed in PR #629:

- filter `user_todos` with `blocks_agent` set to another registered agent out
  of the current agent's blocking quota summary;
- preserve those todos as diagnostic `other_agent_scoped_items`;
- when the raw state is `operator_gate` only because of the other-agent gate
  and the current agent has executable work, project an eligible current-agent
  lane;
- keep the target agent blocked on the same concrete user todo.

## Validation

- `examples/control_plane/quota-agent-scoped-user-gate-smoke.py` covers:
  - non-target agent can run;
  - target agent remains user-gated;
  - unscoped user gates remain global gates.
- `examples/control_plane/work-lane-contract-smoke.py`
- `examples/control_plane/quota-action-scope-guard-smoke.py`
- `examples/protocol-action-packet-smoke.py`
- `examples/control_plane/quota-plan-smoke.py`
- a real active-state quota check confirmed the non-target agent returned
  `decision=run`, `requires_user_action=false`, and `delivery_allowed=true`
  while the target agent remained `user_gate`.

## Related Patterns

- `IP-003 Scoped Gate With Safe Fallback`: owns the `blocks_agent` scope rule.
- `IP-022 Claimed Todo Visibility And Agent-Lane Next Action`: keeps the
  current agent's claimed work visible so a scoped gate does not hide it.
- `IP-026 Agent-Scoped No-Candidate Gap`: applies only after other-agent
  gates are filtered and no current-agent runnable frontier remains.
- `agent_scoped_user_gate_overreach`: self-repair pattern for this failure
  mode.
