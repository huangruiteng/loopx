# Monitor-Only Replan Stall Incident

Date: 2026-06-21

Audience: LoopX maintainers, heartbeat prompt generator owners,
status/quota owners, self-repair skill owners, and side-agent controller
authors.

## Summary

A side-agent delivery goal entered a stall where the control plane repeatedly
recorded monitor-only or replan/self-repair style runs, but the work frontier
did not actually change. The user channel was not blocked: there was no open
user todo and no user question. The intended state was either:

- stay quiet because the goal was only watching for a material external signal;
  or
- promote a concrete runnable agent todo, blocker, successor, or superseding
  route when the monitor could no longer advance the goal.

Instead, the system hovered between quiet monitor status and autonomous replan
language. This was not primarily a missing user answer. It was a control-plane
quality problem: the agent saw enough action-like language to keep trying, but
not enough machine-verifiable state change to escape the loop.

## Public-Safe Shape

The case is intentionally recorded without raw project paths, private task
names, internal document links, benchmark traces, or local active-state
payloads. The reusable shape is:

```text
quota.effective_action = monitor_quiet_skip
interaction_contract.user_channel.action_required = false
user_todo_summary.open_count = 0
agent_todo_summary.open_count = 1 monitor-style item
recent_history = repeated quota_monitor_poll / replan / repair-adjacent runs
observable problem = no new runnable todo, blocker, successor, or supersede
```

Later runs eventually moved the goal back into an executable `normal_run`
shape, but the incident matters because several turns were spent before the
control plane made the real next step obvious.

## What Went Wrong

1. **Monitor-only status was too easy to read as action.** A monitor quiet skip
   is a watch lane, not a delivery lane. If status or diagnose presents it as
   `waiting_on=codex` with action severity, a well-meaning agent can keep
   attempting work that should have remained quiet or been converted into a
   concrete blocker.

2. **Self-repair lacked a delta contract.** The repair loop could write a
   fresh run record, refresh prose, or acknowledge a replan, but the acceptance
   test did not require a machine-visible frontier change such as a new
   runnable todo, a changed `effective_action`, a user gate, a blocker, a
   superseded todo, or an explicit watch-lane closeout.

3. **Replan was too close to prose.** A replan should repair the todo graph:
   split work, retire stale monitor-only work, create a successor, or record a
   blocker. Merely saying that a replan happened is not enough to unblock
   future executors.

4. **Continuous monitor items had no stale threshold.** Repeated monitor polls
   with the same recommendation are useful for liveness, but after a threshold
   they should become evidence for one of three outcomes: keep watching
   silently, write a concrete blocker, or supersede the monitor with a runnable
   route.

5. **Agent behavior was the near cause, but LoopX carried the product
   responsibility.** A stronger agent could have stopped earlier or written a
   blocker. A stronger control plane should make the correct behavior easier
   than the wrong one.

## Why Self-Repair And Replan Did Not Fully Help

Self-repair and replan are only useful if they change the next control-plane
decision. In this incident, they could diagnose or restate the situation but
did not always prove that the next tick would route differently. A successful
repair should pass a small invariant:

```text
after repair/replan, at least one must change:
- quota.effective_action
- interaction_contract.agent_channel / user_channel
- runnable agent todo set
- open user todo / user question
- blocker state
- superseded todo / successor todo
- monitor target, expiry, or watch-lane rationale
```

If none of these changes, the repair should be classified as a no-op and the
next turn should not spend another delivery slot on the same loop.

## Desired Semantics

LoopX should separate three states that look similar in prose but have
different execution meaning:

| State | User Channel | Agent Channel | Expected Writeback |
| --- | --- | --- | --- |
| Quiet monitor | no notification | optional no-spend poll, then quiet | monitor-poll only |
| Dead monitor | no immediate user ask unless owner input is needed | blocker, supersede, or successor required | concrete transition |
| Replan obligation | no interruption unless promoted to a user decision | update todo graph, then ACK | structured replan ACK plus changed frontier |

The key product rule is simple: **a repair or replan is complete only when the
next agent can see a different, actionable control-plane state.**

## Follow-Up Work

### P1: Self-Repair Delta Contract

Add a machine-visible repair acceptance rule. A self-repair or autonomous
replan run should be considered successful only if it changes the selected
work frontier, user gate, blocker state, runnable todo set, capability gate,
or monitor target. Otherwise mark it as `repair_noop` / `replan_noop` and keep
the stale condition visible.

### P1: Dead Monitor Detector

Detect repeated monitor-only polls with the same monitor target and no material
transition. After a threshold, require one of: explicit watch-lane continuation
with expiry, concrete blocker, `todo supersede`, or a successor runnable todo.

### P1: Replan-To-Todo Contract

Strengthen autonomous replan so it must land in todo lifecycle operations:
split/add/update, `todo supersede`, `todo complete --next-agent-todo`, or a
structured blocker. A replan ACK without a changed frontier should not close
the obligation.

### P2: Bad-Case Catalog And Dashboard Copy

Use this incident as a public-safe bad case for the interaction catalog and
dashboard copy. Monitor-only lanes should render as watch state, not as
immediate Codex work or user/controller gates.

## Related Patterns

- `IP-008 Monitor Quiet Skip`: quiet monitor work is a watch lane, not a
  delivery lane.
- `IP-013 Autonomous Replan Vs Advisory Dreaming`: replan closeout must be
  explicit and structured.
- `IP-020 Todo Claim / Supersede / Successor Lifecycle`: stale work should be
  superseded or completed with a successor instead of edited away in prose.
- `monitor_replan_noop_loop`: self-repair pattern for monitor/replan loops
  that do not change the machine-visible work frontier.
