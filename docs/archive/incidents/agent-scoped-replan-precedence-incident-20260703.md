# Agent-Scoped Replan Precedence Incident

Date: 2026-07-03

Audience: LoopX quota/status owners, goal-routing maintainers, dreaming /
replan owners, heartbeat prompt maintainers, and multi-agent controller
authors.

## Summary

A registered side agent reached a stopped-turn state where it had no current
or unclaimed advancement todo, while the broader goal still had visible work
and periodic planning pressure. The intended behavior was not ordinary
delivery: the agent should not steal another agent's claimed task. The intended
behavior also was not an indefinite quiet monitor: when the goal needs a
control-plane replan, the selected agent must receive a bounded replan action
that can change the todo graph, route, or blocker state.

The bad case is that LoopX could project planning pressure and scoped no-work
signals in the same packet family without a single authoritative interaction
mode. Depending on the surface, the agent saw either a quiet monitor / scoped
wait, or a replan obligation as advisory context. In both shapes, the agent
could truthfully stay quiet while the goal still needed a routing repair.

## Public-Safe Shape

The case is recorded without raw active-state bodies, private paths, benchmark
logs, trajectories, credentials, or local runtime artifacts. The reusable
shape is:

```text
quota call = quota should-run --goal-id <goal-id> --agent-id <side-agent>
current-agent advancement candidates = 0
unclaimed advancement candidates = 0
other-agent advancement candidates > 0
user_todo_summary.open_count = 0
ordinary delivery should not run = true
replan pressure exists = periodic review / stale route / goal acceptance gap
bad interaction = quiet no-op or agent-scope wait wins over bounded replan
expected interaction = autonomous_replan_required wins, but only for
  control-plane replan/todo writeback, not ordinary delivery
```

This is adjacent to the earlier monitor-only replan stall, but narrower. The
older incident said that a replan must change the frontier. This incident says
that when replan is required, the quota payload must make replan the selected
frontier before another quiet wait.

## What Went Wrong

1. **Replan was visible but not selected.** Replan pressure could appear as
   advisory payload beside `must_attempt=false`, `delivery_allowed=false`, or a
   quiet monitor recommendation. That creates a self-contradictory executor
   experience: the agent can see that planning work is due but is also told not
   to attempt work.

2. **Agent-scope wait was too final.** `agent_scope_wait` is correct when the
   current agent has no in-scope delivery candidate. It is not sufficient when
   the reason no candidate exists is itself the thing a control-plane replan
   should repair.

3. **Monitor todos had no promotion path through replan.** A monitor lane
   should stay quiet while it is intentionally watching. Once the goal needs a
   route repair, the transition should be: monitor evidence -> replan required
   -> todo split/add/retire/blocker. It should not stay monitor-only merely
   because the current agent has no advancement todo.

4. **Goal completion was not first-class routing input.** Goal-level
   acceptance criteria, when present only as prose or product intuition, cannot
   reliably trigger a replan. The route layer needs a compact per-goal contract
   that says what "done enough" means for the current stage and how stale,
   incomplete, or contradictory routes should be repaired.

5. **Dreaming and replan boundaries were close but not connected enough.**
   Dreaming is advisory; autonomous replan is an executable control-plane
   obligation. A goal-level routing contract should let dreaming propose
   better acceptance criteria or routes, but only autonomous replan should
   override quiet monitor / no-candidate states without an operator promotion.

## Desired Semantics

The small rule is:

> If `autonomous_replan_obligation.required=true`, the selected interaction
> mode must be `autonomous_replan_required` unless a harder gate blocks it.

Harder gates include user decisions, private material, credentials,
destructive git, production actions, missing repository boundary, or broken
control-plane health. Ordinary monitor quiet, agent-scope wait, and empty
current-agent delivery frontier are not harder gates.

The payload should stay explicit rather than omit fields. The issue is not
that `must_attempt` or delivery fields exist; the issue is that they are scoped
too coarsely. A clean contract would say:

```text
interaction_contract.mode = autonomous_replan_required
agent_channel.must_attempt = true
agent_channel.delivery_allowed = true
agent_channel.allowed_action_scope = control_plane_replan
normal_delivery_allowed = false
cli_channel.spend_after_validation = true
primary_action = split/add/retire todos, write blocker, or record watch expiry
```

That preserves the safety boundary: the agent may repair routing state, but it
may not perform the ordinary task owned by another lane.

## Per-Goal Routing Contract

The durable repair should be a small per-goal routing contract, not an
auto-research-specific completion system. The contract should live with the
goal state / registry projection and feed quota, status, replan, and dreaming.

Minimum useful fields:

```json
{
  "schema_version": "goal_routing_contract_v0",
  "stage": "current public-safe stage name",
  "acceptance": [
    {
      "id": "short stable id",
      "description": "public-safe done condition",
      "required": true,
      "evidence_kind": "todo|run_history|smoke|artifact|operator_decision"
    }
  ],
  "replan_triggers": [
    "acceptance_gap",
    "stale_route",
    "no_current_agent_candidate"
  ],
  "dreaming_policy": {
    "advisory_only": true,
    "may_propose_acceptance_updates": true,
    "promotion_requires": "operator_or_controller_decision"
  }
}
```

This keeps the mechanism small. The goal contract defines the current route
and acceptance gap; autonomous replan repairs the executable frontier; dreaming
can suggest changes but cannot silently execute them.

## Follow-Up Work

### P0: Replan Precedence In Quota

When status or run history projects `autonomous_replan_obligation.required`,
quota should select `autonomous_replan_required` before
`monitor_quiet_skip`, `agent_scope_wait`, or generic no-candidate waits. The
payload must expose an allowed control-plane replan action and a validation /
writeback command. Ordinary delivery can remain blocked.

### P1: Minimal Goal Routing Contract

Add a compact `goal_routing_contract_v0` projection with acceptance checks and
replan triggers. Keep it per goal and generic. It should not know about any
particular product preset; auto-research can later use it as one example.

### P1: Planning-Lane Regression

Add a focused quota/status regression where a side agent has no advancement
candidate, another agent owns the delivery work, and a goal-level autonomous
replan is required. Expected result: the side agent receives
`autonomous_replan_required` with `allowed_action_scope=control_plane_replan`,
not a quiet no-op.

## Related Patterns

- `IP-013 Autonomous Replan Vs Advisory Dreaming`
- `IP-024 Repair Delta Contract`
- `IP-026 Agent-Scoped No-Candidate Gap`
- `IP-008 Monitor Quiet Skip`
- `monitor_replan_noop_loop`
- `agent_scoped_no_candidate_gap`
