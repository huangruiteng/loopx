# Codex Peer Task Orchestration

LoopX supports two different concepts that must not be conflated:

- durable registered agents are equal peers;
- a host runtime may launch an ephemeral child worker for one bounded task.

No registered identity owns the goal. Claims, leases, task boundaries,
capabilities, and continuation policy decide who acts. When parallel work is
useful, LoopX may choose one temporary task coordinator from the participating
peers. That responsibility ends with the task bundle.

## Peer Runtime Contract

A registered identity uses `agent_model=peer_v1`. It has no rank-bearing role,
implicit review authority, or permanent writeback ownership. A task coordinator
may:

- activate or resume eligible peer lanes;
- issue complete briefs to ephemeral child workers;
- aggregate returned evidence;
- write accepted task-bundle state and account for the completed turn.

It does not own durable goal authority. Repository policy, explicit decision
scopes, and todo continuation still govern review, merge, publication, and
production actions.

## When To Parallelize

Parallelize when it reduces uncertainty or latency:

- map disjoint code, docs, test, or runtime surfaces;
- implement isolated slices in independent worktrees;
- run an independent review or validation pass;
- inspect separate adapter, evidence, or boundary questions.

Keep tightly coupled decisions in one peer lane. Do not launch workers merely
to make the activity graph look busy, and never let worker count override
quota, user gates, write scope, or repository policy.

## Fresh, Fork, Or Resume

The temporary task coordinator chooses a worker context from the work shape:

| Work type | Context | Required task brief |
| --- | --- | --- |
| Broad mapping, prior-art search, risk discovery | Fresh worker | Objective, authority source, allowed sources, boundary, expected output, non-goals |
| Independent review or adversarial validation | Fresh worker | Claim under review, exact evidence, validation command, acceptance and merge rules |
| Failed-smoke repair or review-comment follow-up | Resume or fork | Worktree, failing evidence, latest patch, next bounded repair |
| Disjoint implementation | Fresh worker in an independent worktree | Claimed todo, allowed paths, write scope, validation, continuation policy |
| Long-running claimed lane | Resume the registered peer task | Agent id, todo or lease, latest accepted evidence |
| Production action or emergency rollback | No automatic worker | Operator approval, stop condition, reversible command plan |

Fresh workers are useful only when the task coordinator can provide a complete
brief. Missing authority, scope, expected output, or validation is a planning
gap, not a reason to launch an under-specified worker.

## Shared Control Plane Handoff

Every child-worker brief starts from the shared control plane. A worker must not
infer current authority from chat history, an old packet, or another worker's
summary.

The existing host-child packet name remains
`subagent_control_plane_handoff_v0` for compatibility. Its lineage fields do
not create durable rank:

- `parent_goal_id`: shared goal lineage, not an owner identity;
- `authority_artifact`: current goal, policy, or review authority;
- `latest_state_ref`: state hash, run id, or generated-at value to read first;
- `quota_gate_snapshot`: current eligibility, wait, or gate state;
- `evidence_boundary`: allowed sources, paths, and public/private rule;
- `writeback_spend_contract`: who may accept evidence and account for the turn;
- `child_decision`: `continue`, `wait`, or `reuse_existing_evidence`.

Only then should the brief include todo id, work scope, expected artifact,
validation, and continuation policy. The compact rule is: child worker reports
evidence only; the temporary task coordinator writes accepted state and spends.

```yaml
subagent_control_plane_handoff_v0:
  parent_goal_id: example-peer-task-goal
  authority_artifact: .codex/goals/example-peer-task-goal/ACTIVE_GOAL_STATE.md
  latest_state_ref: state_hash_or_run_id
  quota_gate_snapshot: eligible
  evidence_boundary: public-safe read-only repository map
  writeback_spend_contract: child worker reports evidence only; task coordinator writes accepted state and spends
  child_decision: continue
goal_id: example-peer-task-goal
todo_id: todo_docs_map
work_scope: inspect docs and return evidence paths
validation: cite files and residual risk; do not edit
continuation_policy: independent_handoff
```

The host may still expose a `subagent_context_hint` with `fresh`, `resume`,
`fork`, or `do_not_spawn`. It is advisory and cannot widen authority.

## Claims, Leases, And Worktrees

Registered peers claim work through LoopX todos and leases. The control plane
allows one pending lease for `(goal_id, todo_id)`. `goal_id` is the shared
control-plane lane; `todo_id` is the work item being claimed. A host child may
carry the claim context in its brief, but it does not become a ranked agent.

Repository-writing peers and child workers use independent worktrees. Overlap
is resolved through task boundaries and repository policy, not through a
permanent controller. Completion uses typed continuation:

- `independent_handoff`: leave the successor available to peers;
- `same_agent_non_delivery`: keep a non-delivery follow-up with the same peer;
- explicit `review_handoff`: route review to a different peer or leave it
  unclaimed; self-review is invalid.

## Enabling Bounded Orchestration

The feature remains opt-in:

```bash
loopx configure-goal \
  --goal-id example-peer-task-goal \
  --multi-subagent-feature enabled \
  --max-children 2 \
  --allowed-domain docs \
  --allowed-domain validation \
  --execute
```

`multi_subagent` is the compatibility name for host child-worker capacity. It
does not select an agent hierarchy. `quota should-run` hashes the current open
participant lanes, selects one task-scoped coordinator, and projects a
`task_orchestration_contract_v1`. Dormant registered agents and closed,
blocked, or deferred todos are not coordinator candidates.

Use `--multi-subagent-feature off` to disable worker spawning. The low-level
`--orchestration-mode` and `--spawn-allowed` flags remain available for host
integrations.

## Run History And Observation

Run history should attribute task coordination without persisting rank:

```json
{
  "agent_model": "peer_v1",
  "task_coordinator": "codex-alpha",
  "control_plane_handoff_version": "subagent_control_plane_handoff_v0",
  "peer_lanes": [
    {"agent_id": "codex-beta", "todo_id": "todo_docs_map", "state": "completed"},
    {"agent_id": "codex-gamma", "todo_id": "todo_validation", "state": "running"}
  ],
  "accepted_evidence_count": 1,
  "next_action": "review the remaining validation evidence"
}
```

Useful observation surfaces include task bundle, participant peers, worker
context (`fresh`, `fork`, or `resume`), accepted or rejected evidence, leases,
worktrees, quota state, and typed continuation. They must not reconstruct a
durable leader from a temporary coordination event.

## Safety Rules

- Do not spawn when quota or the selected user gate blocks the task.
- Do not infer permissions from an agent name, profile label, or old prompt.
- Do not launch a fresh worker without a complete task brief.
- Do not put credentials, private links, raw logs, or production material in a
  public handoff packet.
- Keep implementation scopes disjoint and use independent worktrees.
- Let repository policy decide review and merge; peer identity grants neither.
- Let one temporary coordinator accept bundle evidence and write one spend
  event after validated progress.

The result is parallel execution without a permanent leader: durable agents
remain peers, while task coordination and host-child relationships stay bounded
to the work that requires them.
