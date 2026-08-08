# Work graphs, authority, and peer collaboration

A Todo is not an ordinary checklist item. Together with Gates, dependencies, claims, capabilities,
workspaces, and evidence, it forms a computable work graph. This chapter explains how a Goal produces the
current frontier and how equal peers collaborate without turning one Agent, Host, or conversation into a
hidden leader.

## What you should learn

After this chapter, you should be able to:

- distinguish Goal, Acceptance, and per-Agent Vision;
- distinguish an Agent Todo, User Gate, User Action, Monitor, and Blocker;
- explain the different jobs of claims, leases, lifecycle authority, capability Gates, and workspace
  guards;
- use dependency, resume, successor, supersede, continuation, and no-follow-up to close work;
- decide whether a Gate actually covers an action rather than freezing the Goal at any “waiting for user”
  message;
- explain why handoff transfers bounded state references instead of a complete transcript.

## Goal, Acceptance, and per-Agent Vision

These objects operate at different levels:

| Object | Scope | Question it answers |
| --- | --- | --- |
| Goal | Project | What outcome must the project achieve? |
| Acceptance | Goal or explicit delivery stage | Which observable evidence is sufficient for completion? |
| Agent Vision | `agent_id` | What direction, role scope, acceptance summary, and replan trigger does this peer currently own? |

Vision is not a global product vision or free-form scratchpad.
[`goal_vision_replan_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/goal-vision-replan-contract-v0.md)
defines it as bounded per-Agent execution-routing state. It can include:

- `role_scope`;
- `vision_summary`;
- `acceptance_summary`;
- `advancement_policy`;
- `replan_trigger_summary`;
- the latest bounded patch.

After material progress, a peer records whether Vision was patched, preserved with a reason, retired, or
superseded. Without that checkpoint, quota may report `vision_checkpoint_missing` and require replan
evidence before ordinary delivery.

This protects against two kinds of drift:

1. a busy Todo queue that no longer advances Goal acceptance;
2. several peers working on the same Goal while each keeps an invisible private account of the next step.

## A Todo is the smallest executable or waiting unit

A Todo can carry:

- role and priority;
- `task_class` and `action_kind`;
- dependency and resume condition;
- required capability and write scope;
- claim, lease, and continuation policy;
- Gate, evidence, successor, and supersession references.

It is not a complete project plan or a reminder that exists only in a prompt.

### Five common work classes

| Class | Owner | Typical meaning |
| --- | --- | --- |
| `advancement_task` | Agent | Current implementation, documentation, analysis, or repair work |
| `user_gate` | User/controller | A related action cannot legally continue without a decision |
| `user_action` | User/controller | A person should act, but independent Agent work need not stop |
| `continuous_monitor` | Agent/Host | Observe an external condition on a cadence and advance only on material change |
| `blocker` | Agent/controller | An executable condition is missing and needs a concrete recovery path |

Human-readable Todo text is useful. Machine routing must not infer the work class from prose alone.

## The frontier is not the list of open Todos

The **frontier** is the set that survives every current guard:

```text
open todos
  -> dependency and resume
  -> decision scope and authority
  -> agent claim and lifecycle authority
  -> host capability
  -> workspace and write scope
  -> freshness and evidence
  -> current frontier
```

Therefore:

- open does not mean runnable;
- priority does not bypass a Gate;
- claimed does not prove the work is still executable;
- capability does not grant authority;
- Todo completion does not prove Goal completion.

[`task_graph_projection_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/task-graph-projection-v0.md)
can render those relations. The graph remains a read-only projection; lifecycle changes still pass through
Todo, Gate, refresh, and event protocols.

## Claim, lease, and lifecycle authority

These three concepts are often collapsed incorrectly.

### Claim: soft work ownership

A claim says “this peer currently owns the work.” It helps quota and other Agents avoid duplicate
selection. It is not a lock, and it does not prove that the Agent is alive or in the correct worktree.

### Lease: optional concurrent occupancy

A lease is useful when an operation needs TTL, renewal, transfer, version/CAS, or an idempotent occupancy
identity. It may protect an expensive or effectful execution, but it does not replace the Todo lifecycle.

A system may have:

- a claim without a lease;
- a valid lease while a Gate still blocks execution;
- reassignment after lease expiry;
- a handoff that deliberately does not transfer the old lease.

### Lifecycle authority: who may change state

A claim answers who plans to execute. Lifecycle authority answers who may complete, supersede, reassign,
or perform a special override. Delegating one lifecycle mutation to a peer does not turn that peer into a
global leader.

LoopX live multi-agent work uses an **equal peer** model. An Agent id is a work identity, not proof of a
Host surface or organizational hierarchy. A `codex-*` name alone cannot prove Codex App or Codex CLI is
currently running the work.

## A Gate is scoped authority

[`decision_scope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/decision-scope-v0.md)
requires a user or controller decision to identify:

- `kind`, such as `private_read`, `write_scope`, `resource`, `production`, `public_claim`, or `direction`;
- `granularity`, such as action, lane, goal, project, or global;
- `scope_key`, a public-safe identity for the blocked operation;
- optional expiry, decision id, and reason.

An Agent Todo can declare `required_decision_scopes`. An unresolved Gate blocks the Todo only when its
scope covers the selected action.

```text
Gate G1
  decision_scope = public_claim:action:bilingual_homepage

Todo A
  required_decision_scopes = public_claim:action:bilingual_homepage

Todo B
  repair internal link checker
  required_decision_scopes = none
```

G1 blocks A, not B. If a projection only says “waiting for user approval” and has no scope relation, repair
the projection or ask the concrete question. Do not invent authority, and do not assume a global freeze.

A `user_action` is not authority either. Seeing a reminder does not approve production, publication, or
private reads.

## Capability Gate and workspace guard

Decision scope, capability, and workspace are independent axes:

| Boundary | Primary question | It does not prove |
| --- | --- | --- |
| Decision scope | Has the required user/controller decision been granted? | Whether this Host can execute |
| Capability Gate | Does the Host/runtime provide the required ability? | Whether the action is authorized |
| Workspace guard | Is the Agent in the correct repository, worktree, and write scope? | Whether the result is correct |

An Agent may have publication approval while its Host lacks network capability. A Host may have shell and
network access while running in the wrong worktree. Neither case is safe to execute.

Combine these boundaries in the current decision. Do not copy a project-specific `if` chain into an
automation prompt.

## Dependency, resume, and successor

A work graph must explain not only “A before B,” but also how work resumes after waiting.

### Dependency

Names durable facts or Todos that the current item requires.

### Resume condition

Names a machine-readable condition that lets blocked or deferred work re-enter replanning, such as:

```text
todo_done:<todo-id>
pr_merged:<pr-id>
capacity_available:<capability>
```

A satisfied condition does not always make the old Todo runnable. The task may be stale and require a
successor replan.

### Successor

Creates the next identified unit of work after completion. A successor moves “what happens next” into the
durable graph rather than leaving it in the completed Agent's chat.

### Supersede

Replaces obsolete work with a new Todo while preserving lineage. Do not mark invalidated work as done.

### No-follow-up

When no successor is necessary, record why acceptance is closed or why later work is outside the Goal.
Structured no-follow-up is more auditable than “looks finished.”

## Continuation and handoff

After a Todo completes, two common continuation policies are:

- `same_agent_non_delivery`: the same peer performs a bounded follow-up that is not an independent
  delivery;
- `independent_handoff`: the successor remains unclaimed so any qualified peer may take it unless an
  explicit assignment says otherwise.

Completing one item does not give an Agent ownership of the whole Goal.

A handoff also does not copy the transcript. A bounded handoff should let the receiver reconstruct:

- Goal, Todo, and stop condition;
- current revision and workspace;
- Gate, capability, and authority boundary;
- evidence and material references with freshness;
- next action and validation;
- omitted or private material that must be reacquired through a legal route.

The receiver reruns current guards. The prior Agent's receipt does not grant source permission to the new
Agent, and an old workspace observation does not prove the environment stayed unchanged.

## Multi-repository and parallel work

One business outcome may span several Git repositories. That does not require several unrelated Goals when
acceptance and decision authority belong to one result. Keep one Goal and give every Agent Todo explicit
repository scope:

```text
todo_id
task_repository = git:github.com/owner/repo
required_write_scopes = src/**, tests/**
claimed_by = <registered-peer>
continuation_policy = independent_handoff | same_agent_non_delivery
```

`task_repository` is a credential-free repository identity. It selects the repository for workspace
isolation and **does not grant write authority**. Claims, leases, Goal boundaries, and repository
maintainer policy still apply.

The current
[`peer_agent_runtime_v1`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/peer-agent-runtime-v1.md)
and `workspace_guard` require a repository-writing selected Todo to run from a linked independent worktree
whose origin matches `task_repository`. A matching repository is necessary but not sufficient: the
canonical checkout may still be rejected.

### Work that can run in parallel

| Work type | Parallel policy |
| --- | --- |
| Research, source location, triage, read-only review | Fan out, then collect bounded evidence |
| Implementation in different repositories | Bind each Todo to its own `task_repository` and worktree |
| One repository with disjoint write scopes | Parallelize only when scopes are proven disjoint and validation is independent |
| One file or shared schema/state machine | Default to serial work or split an owner/seam first |
| External effects, merge, or publish | Keep scoped Gates and repository policy authoritative |

A claim is a soft owner, not a lock. Only Hosts with a demonstrated concurrent-write problem need the
optional `task_lease_v0`. Current quota does not automatically consume a hard lease, so documentation must
not imply that a server already arbitrates every concurrent write.

### Multi-repository example

Suppose one release changes four repositories:

```text
Goal: ship-cross-repo-release
├── Todo A -> repo-a -> agent-a -> worktree-a
├── Todo B -> repo-b -> agent-b -> worktree-b
├── Todo C -> repo-c -> agent-c -> worktree-c
└── Todo D -> integration verification -> waits for A/B/C evidence
```

A, B, and C may run in parallel. D cannot infer readiness from prose. Each implementation Todo writes back
an exact revision, validation, and completion evidence; D enters the frontier only after dependencies and
fresh readback agree.

Cross-repository PR conditions also need repository identity. `resume_when=pr_merged:#123` is satisfied
only when the Todo's GitHub `task_repository` matches the merge-event repository. Use
`pr_merged:owner/repo#123` across repositories. Missing repository identity fails closed instead of
guessing from the PR number.

### Automation that is not currently shipped

The product does not promise “point LoopX at a root folder and it automatically runs four Goals in
parallel,” nor a cloud coordinator that chooses devices and claims work. Bounded multi-agent orchestration
can enable child-agent planning, while peer identity, claim, workspace guard, Gate, and writeback remain
per-Todo contracts. Cross-device online authority remains a Draft design boundary.

## Three ways a work item leaves the active frontier

A Todo should leave the active frontier through one of these outcomes:

1. **Completed with evidence**: delivery and validation both hold.
2. **Superseded with lineage**: direction changed and a replacement Todo takes over.
3. **Blocked or deferred with a resume contract**: a concrete condition is missing and recovery remains
   durable.

Deleting an item from a list is not a lifecycle transition.

Goal terminal closure needs additional checks:

- acceptance is satisfied;
- no unresolved Gate remains;
- no due monitor, pending external effect, or stale readback remains;
- no successor, replan obligation, or acceptance gap remains;
- no retryable postcondition remains;
- no-follow-up is explicit where required.

## Protocol reading routes

For work-graph or authority changes, start with:

- [`task_graph_projection_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/task-graph-projection-v0.md)
  for read-only dependency, Gate, validation, repair, and handoff relations;
- [`decision_scope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/decision-scope-v0.md)
  for coverage and fail-closed authority;
- [`goal_vision_replan_contract_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/goal-vision-replan-contract-v0.md)
  for per-Agent Vision and replan checkpoints;
- [Peer Agent Runtime v1](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/peer-agent-runtime-v1.md)
  for equal peer identity and continuation;
- [Host Integration Surface](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/host-integration-surface-v0.md)
  for claims, optional leases, capability, and Host boundaries.

For changes involving equal peers, lifecycle authority, handoff, dependencies, or successors, continue to
[Control-Plane Course Lesson 3](/loopx/docs/development/control-plane-course/03-work-graph-and-peers/).
The course provides combined cases and source walkthroughs; this chapter preserves the work-graph and
authority model needed by external contributors.

The next chapter compiles these facts and authorities into one governed Turn: who acts, who waits, which
channel informs the user, and when writeback and spend are legal.
