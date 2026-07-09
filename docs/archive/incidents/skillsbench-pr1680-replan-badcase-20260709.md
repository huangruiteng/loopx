# SkillsBench PR #1680 Replan Bad Case

Date: 2026-07-09

Audience: LoopX maintainers, quota/status owners, todo projection owners,
benchmark runner owners, and heartbeat automation owners.

## Summary

SkillsBench Goal xhigh work stopped after the benchmark egress proxy fix was
merged. The benchmark runner was not the immediate blocker. The control plane
continued to expose a quiet monitor lane whose durable next action still said
to keep PR #1680 in review-required state and rerun verifier/bootstrap-failure
cases only after review/merge.

That external condition was already satisfied. GitHub reported PR #1680 as
merged at `2026-07-08T18:14:59Z` (`2026-07-09T02:14:59+08:00`). Later LoopX
quota/status reads still selected:

```text
quota.should_run = false
quota.effective_action = monitor_quiet_skip
goal_frontier_projection.replan_required = false
agent_monitor_due_count = 0
active_state_next_action = keep PR #1680 in review-required state; after
  maintainer review/merge, rerun verifier/bootstrap-failure SkillsBench cases
```

The result was a live but idle automation: the heartbeat stayed active and
quiet, but no runnable SkillsBench rerun todo was projected.

## Public-Safe Shape

This record intentionally excludes raw SkillsBench task text, raw trajectory,
verifier output, private launch material, credentials, and local artifact
paths. The reusable shape is:

```text
external_evidence.state = merged
durable_next_action = wait for that same external merge/review condition
quota.effective_action = monitor_quiet_skip
interaction_contract.agent_channel.must_attempt = false
goal_frontier_projection.replan_required = false
ready_successor_count = 0
observable problem = no runnable rerun todo after the unblock signal landed
```

The public evidence is enough to reproduce the control-plane contradiction:

```bash
gh pr view 1680 --repo huangruiteng/loopx \
  --json state,mergedAt,reviewDecision,headRefName,mergeCommit

loopx --format json quota should-run \
  --goal-id loopx-meta \
  --agent-id codex-main-control
```

## What Went Wrong

1. **External merge evidence did not become a material transition.** PR #1680
   moving to `state=MERGED` should have closed the wait condition and exposed
   a runnable rerun frontier or a concrete blocker.

2. **The durable Next Action stayed stale.** After the merge, the active state
   still instructed agents to keep the PR in review-required state. That made
   the goal look intentionally waiting even though its named unblock condition
   had landed.

3. **Quiet monitor semantics masked the stale condition.** `monitor_quiet_skip`
   was correct only if nothing material had changed. In this case, a public
   external dependency had changed, but the monitor lane reported no due
   monitor and no replan requirement.

4. **No successor rerun todo was projected.** The broader SkillsBench work
   should have resumed as an advancement todo for verifier/bootstrap reruns
   under the required benchmark egress proxy and benchmark_core compact ledger
   standard. Instead, the visible runnable frontier fell back to unrelated or
   capability-missing work.

5. **Agent behavior contributed to the stall.** The agent followed the CLI
   source of truth and remained quiet, but it should have treated the mismatch
   between "wait for PR #1680 merge" and "PR #1680 is merged" as a self-repair
   trigger rather than waiting for the user to point it out.

## Why Replan Did Not Recover

Replan did not fire because the state projection said there was no autonomous
replan obligation:

```text
goal_frontier_projection.replan_required = false
monitor_only_lanes.quiet_until_material_transition = true
deferred_successors.ready_count = 0
acceptance_gaps = []
```

This is the core product gap. A quiet monitor lane needs a way to re-check the
external fact it is waiting on. If that fact is already true, the lane must not
continue as unchanged monitor-only state.

The case is especially subtle because GitHub can still report
`reviewDecision=REVIEW_REQUIRED` on a merged PR. LoopX must use the terminal PR
state as the stronger signal: `state=MERGED` satisfies a merge wait, regardless
of stale review-decision metadata.

## Expected Semantics

When a durable next action or todo resume condition names an external public
dependency, LoopX should treat a terminal dependency transition as a material
frontier change.

| Condition | Expected LoopX Behavior |
| --- | --- |
| PR wait target is open | quiet monitor may continue until due or expiry |
| PR wait target is merged | close or supersede the monitor, then project the successor action |
| PR state contradicts review metadata | prefer terminal `state=MERGED` for merge waits |
| successor cannot run | record a concrete blocker with missing capability or missing material |
| no successor exists | emit `autonomous_replan_required` instead of monitor quiet skip |

## Follow-Up Contracts

### P0: External Dependency Resume Projection

Add a public-safe projection rule for durable next actions and todo
`resume_when` conditions that reference public PR dependencies. When the PR is
merged, the blocked or deferred work should become ready, be superseded with a
fresh successor, or produce a concrete blocker.

### P0: Monitor Quiet Contradiction Guard

`monitor_quiet_skip` should be illegal when the durable next action says to
wait for an external condition and a cheap public read proves the condition is
already satisfied. In that case, quota/status should expose
`autonomous_replan_required` or a runnable successor.

### P1: Terminal PR State Precedence

For PR merge waits, terminal PR state must outrank review metadata. A merged PR
whose `reviewDecision` still says `REVIEW_REQUIRED` is merged for workflow
purposes.

### P1: Bad-Case Regression Smoke

Add a focused fixture where:

```text
active_state_next_action references "after PR #1680 review/merge"
public_pr_state.state = MERGED
public_pr_state.reviewDecision = REVIEW_REQUIRED
monitor_due_count = 0
```

The expected quota/status outcome is not `monitor_quiet_skip`; it should be a
runnable successor, concrete blocker, or autonomous replan obligation.

## Ownership

Primary product ownership is LoopX control-plane projection: the state model
failed to translate a public external unblock event into a new runnable
frontier. The agent also has a process responsibility: when the CLI says quiet
but public evidence contradicts the durable next action, the agent should
invoke self-repair and write a bad-case record instead of waiting.
