# Codex Sub-Agent Orchestration

LoopX should support Codex-style work where one main controller starts
multiple sub-agents. This is useful for large repos, multi-surface validation,
and parallel exploration, but it needs a stronger contract than a single-agent
goal tick.

## Role Split

The main controller owns the goal:

- reads the active goal state,
- chooses the bounded progress segment,
- checks the goal's current compute quota before spawning or continuing child
  work,
- decides which sub-agents are worth starting,
- assigns disjoint scopes,
- integrates or rejects their results,
- writes the final run record and next action.

Sub-agents own scoped work:

- one repo question,
- one implementation slice,
- one validation surface,
- one docs or benchmark audit,
- one independent risk check.

Sub-agents should not independently redefine the goal, widen scope, force-push,
publish private state, or launch production actions.

## Dreaming / Exploration Lane

Some Codex work should not run inside the project agent that is actively
shipping changes. Broad exploration, slow memory consolidation, refactor
warnings, and cross-project pattern mining are useful, but they create scope
pressure when mixed into the delivery lane.

LoopX should model this as a separate dreaming / exploration lane:

- it reads run history and project state over a wider time window;
- it has its own compute quota so background exploration cannot starve delivery
  work;
- it proposes options, warnings, and memory-consolidation patches;
- it does not mutate project truth or imply user approval;
- its outputs enter the operator gate for review before becoming project work.

See [dreaming-exploration-lane.md](dreaming-exploration-lane.md) for priority,
permissions, and proposed run shape.

## When To Spawn

Spawn sub-agents when parallelism reduces uncertainty or latency:

- large repo map: split docs, code, tests, and runtime evidence;
- implementation batch: split disjoint file ownership;
- verification: run an independent check while the main controller continues;
- high-complexity adapter: let separate agents inspect TODO, docs, eval, and
  public/private boundary.

Do not spawn sub-agents for work that is tightly coupled to the next immediate
decision. If the main controller is blocked on the answer, it should usually do
that part itself.

## Context Policy: Fresh, Fork, Resume

The current task coordinator should choose the child context shape from the work type. LoopX
can record the decision and provide hints, but the active agent loop still owns
whether to launch a child, continue itself, or wait.

| Work type | Preferred context | Why | Required parent brief |
| --- | --- | --- | --- |
| Exploration, broad mapping, prior-art scan, risk discovery | Fresh child | Clean context reduces inherited assumptions and is cheaper than copying a long parent thread. | Objective, authority artifact, allowed sources, public/private boundary, expected output, and non-goals. |
| Independent review, adversarial check, public/private scan, validation map | Fresh child | The child should not inherit the parent's conclusion or local tunnel vision. | Candidate claim to review, exact evidence to inspect, validation command or acceptance rule, and merge rule. |
| Same-branch bug follow-up, failed smoke repair, review-comment fix | Resume or fork child | The child needs recent debugging context, branch state, and failed-command history. | Branch/worktree, failing evidence, latest patch summary, and the next bounded fix target. |
| Disjoint implementation slice after controller planning | Fresh child with a narrow handoff | The implementation should start from the shared control plane, not from the controller's whole chat history. | Claimed todo, allowed paths, write scope, validation, and parent review requirement. |
| Long-running owned peer lane | Resume the existing peer task | Stable ownership is more valuable than a new agent for each tick. | Agent id, lane scope, due monitor or todo, and latest accepted evidence. |
| Emergency rollback or production action | No automatic child by default | Boundary risk is high and usually needs explicit operator control. | Operator approval, stop condition, and reversible command plan. |

This policy is deliberately asymmetric: exploration and review default to fresh
children, while continuous repair and same-branch follow-up default to resume or
fork. Fresh children are useful only when the parent can write a complete brief.
If the parent cannot state the authority, boundary, expected output, and merge
rule, spawning a fresh child only hides ambiguity.

The control plane should eventually expose a compact advisory hint rather than
a hard scheduler decision:

```json
{
  "subagent_context_hint": {
    "recommended_context": "fresh",
    "reason": "independent_review",
    "parent_brief_required": true,
    "may_spawn_idle_agent": true,
    "writeback_owner": "parent"
  }
}
```

`recommended_context` can be `fresh`, `resume`, `fork`, or
`do_not_spawn`. The hint should be derived from todo class, claim state,
evidence freshness, validation needs, and risk boundary. It must not override
quota, user gates, parent approval, write-scope checks, or the controller's
local judgment.

## Handoff Contract

Every sub-agent brief should start from the shared control plane before it
describes the task. A child worker should never infer current authority from a
chat thread, an old packet, or another child's summary.

The shared control-plane handoff is `subagent_control_plane_handoff_v0`:

- `parent_goal_id` and optional `parent_run_id`,
- `authority_artifact`: the source doc, registry entry, or review packet the
  child must treat as current authority,
- `latest_state_ref`: the active-state hash, run id, or generated-at timestamp
  the child must read before work,
- `quota_gate_snapshot`: whether the parent goal is eligible, gated, waiting,
  or in focus wait,
- `evidence_boundary`: public/private boundary, allowed files, and whether the
  child may write or must stay read-only,
- `writeback_spend_contract`: who may write the final run record and spend
  quota,
- `child_decision`: one of `continue`, `wait`, or `reuse_existing_evidence`.

Only after that shared-control-plane prefix should the task brief include:

- `goal_id`,
- role: `explorer`, `worker`, or `validator`,
- scope and explicit non-goals,
- allowed files or read-only boundary,
- expected output,
- validation command if applicable,
- merge rule: what the main controller may accept, ignore, or retry.

For the lightweight shared-control-plane model, the brief or automation prompt
is also where agent scope lives. Do not stamp a scope field onto every todo.
Instead, register the agent id, give the child that `agent_id` and scope, then
have it claim only matching open todos:

```bash
loopx configure-goal \
  --goal-id <goal-id> \
  --registered-agent codex-main-control \
  --registered-agent codex-side-bypass \
  --execute

loopx todo claim \
  --goal-id <goal-id> \
  --todo-id <todo_id> \
  --claimed-by codex-side-bypass
```

The claim is soft ownership for visibility and conflict avoidance. It does not
replace disjoint write scopes, task-coordinator approval, quota, or user gates.
The CLI rejects unregistered claim ids. If the first executable todo is already
claimed by another peer or is outside the current task scope, the peer should
pick another eligible unclaimed todo or project `reassignment_required`.
Repository-writing peers and child runs use independent worktrees when the
selected task or repository policy requires them. They may self-merge small
AGENTS-eligible validated changes with explicit LoopX evidence; otherwise they
use an explicit `review_handoff` to a different registered peer.
When this becomes a server-backed pending/lease path, the contention unit should
stay per todo: one pending lease for `(goal_id, todo_id)`, not a broad lock on
the whole goal. In this context, `goal_id` is the shared control-plane lane and
`todo_id` is the work item being claimed.

The temporary task coordinator may aggregate child evidence, validation, or
blockers for the current bundle. It does not own durable goal authority; normal
quota, task, and repository policy determine acceptance and writeback.

Example:

```text
subagent_control_plane_handoff_v0:
  parent_goal_id: agent-harness-main-control
  authority_artifact: review-packet generated_at=2026-01-01T00:00:00+00:00
  latest_state_ref: active_state_sha256_16=0123456789abcdef
  quota_gate_snapshot: operator_gate
  evidence_boundary: read-only docs/TODO.md and docs/meta/DOC_REGISTRY.yaml
  writeback_spend_contract: child reports evidence only; parent writes and spends
  child_decision: continue

goal_id: agent-harness-main-control
role: explorer
scope: inspect docs/TODO.md and doc registry only
non_goals: do not edit files; do not inspect private prod logs
expected_output: current task clusters, likely blockers, validation surfaces
merge_rule: main controller turns this into a read-only map, not direct actions
```

## Registry Contract

Task-coordinator and child-run fields should stay minimal:

```json
{
  "parent_goal_id": null,
  "spawn_policy": {
    "mode": "multi_subagent",
    "allowed": true,
    "max_children": 3,
    "allowed_domains": ["docs-map", "validation-map", "implementation-slice"],
    "max_child_agent_turns_per_window": 3
  },
  "quota": {
    "compute": 0.5,
    "window_hours": 24,
    "max_agent_turns": 12
  },
  "coordination": {
    "agent_model": "peer_v1",
    "registered_agents": ["codex-main-control", "codex-docs-map", "codex-validation-map", "codex-implementation-slice"],
    "write_scope": ["docs/**", "examples/**"],
    "claim_ttl_minutes": 30,
    "requires_parent_approval": ["write", "publish", "production-action"]
  }
}
```

`spawn_policy.mode` is the control-plane execution mode. `default` means one
peer advances the selected task. `multi_subagent` means LoopX may select a
temporary task coordinator that launches child workers within `max_children`,
`allowed_domains`, and the coordination/write-scope rules. Status and quota derive the same
compact `orchestration` projection from this policy so agents do not need to
infer sub-agent permissions from chat history.

The user-facing switch is intentionally default-off. Prefer configuring it with
the feature wrapper:

```bash
loopx configure-goal \
  --goal-id your-project-goal \
  --multi-subagent-feature enabled \
  --max-children 2 \
  --allowed-domain docs \
  --allowed-domain validation
```

Use `--multi-subagent-feature off` to return the goal to single-agent mode.
The older `--orchestration-mode` and `--spawn-allowed` flags remain as low-level
compatibility knobs, but product surfaces should expose the feature wrapper.

The registered agents remain peers. A deterministic coordinator is selected for
one task bundle only; it may activate child runs and aggregate accepted bundle
evidence, but gains no durable review, merge, publication, or reassignment
authority. Repository-writing peers and child runs follow task/repository
workspace policy, and blocking review uses an explicit `review_handoff` to a
different registered peer.

For a child goal:

```json
{
  "parent_goal_id": "agent-harness-main-control",
  "coordination": {
    "agent_model": "peer_v1",
    "registered_agents": ["codex-docs-map"],
    "write_scope": [],
    "requires_parent_approval": ["write"]
  }
}
```

`parent_goal_id` describes a task-run relationship, not identity rank. These
fields do not turn LoopX into a lock service. They make compute quota explicit
so peers and automations do not encode priority only through timer cadence.

## Run Record Shape

LoopX run history should eventually record sub-agent activity as first
class evidence:

```json
{
  "goal_id": "agent-harness-main-control",
  "run_id": "2026-06-01T02-00-00+08-00",
  "controller": "codex-goal",
  "classification": "ready_for_parallel_probe",
  "recommended_action": "spawn docs-map and validation-map explorers",
  "subagents": [
    {
      "id": "subagent-docs-map",
      "control_plane_handoff_version": "subagent_control_plane_handoff_v0",
      "child_decision": "continue",
      "role": "explorer",
      "scope": "docs/TODO.md + doc registry",
      "status": "completed",
      "changed_files": [],
      "summary": "Found 4 task clusters and 3 validation surfaces."
    }
  ],
  "merge_decision": "accepted docs-map as evidence; no file edits",
  "next_action": "ask main controller to connect read-only adapter"
}
```

The exact schema can stay loose in v0.1, but the contract should remain stable:
the controller records who did what, why it was safe, what changed, what was
validated, and what was deliberately ignored.

Useful child-run fields:

- `run_id`,
- `parent_run_id`,
- `spawned_by_goal_id`,
- `agent_role`,
- `claim_id`,
- `work_scope`,
- `touched_paths`,
- `handoff_summary`,
- `approval_state`,
- `result_status`.

Concurrent child runs should use stable `run_id` values so history readers do
not confuse overlapping work with duplicate index records.

## Long-Term Implementation Plan

LoopX should grow this policy as a set of small control-plane surfaces, not as a
large automatic orchestrator.

1. **Documented advisory contract.** Keep the decision matrix above as the
   public contract. Teach agent skills and runtime prompts to prefer fresh
   children for exploration and review, and resume or fork for same-branch
   follow-up.
2. **Todo and status hints.** Add optional projected fields such as
   `subagent_context_hint`, `spawn_reason`, `recommended_child_role`, and
   `parent_brief_missing_fields` to status/review packets. These fields help the
   agent loop decide; they do not launch work by themselves.
3. **Brief completeness check.** Provide a lightweight checker that tells the
   parent whether a fresh-child brief contains objective, authority, scope,
   boundary, expected output, validation, and merge rule. Missing fields should
   block fresh-child launch and ask the parent to refine the brief.
4. **Idle-child handoff path.** When a suitable idle agent exists, let the
   controller emit a `subagent_control_plane_handoff_v0` packet with
   `recommended_context=fresh`. The child starts from that packet and the shared
   control plane, not from an inherited hidden chat.
5. **Resume/fork evidence path.** For same-branch repairs, attach the failed
   command, branch/worktree, touched paths, and latest accepted patch summary to
   the handoff so a resumed or forked child can continue without re-mining the
   whole parent thread.
6. **Run-history attribution.** Record whether each child used fresh, fork, or
   resume context; why that was chosen; what evidence it produced; and whether
   the parent accepted, retried, or ignored it.
7. **Outcome review.** Compare fresh-review children against forked/resumed
   follow-up children on token cost, latency, false assumptions, duplicated
   work, and parent integration quality before making stronger defaults.

The first useful product behavior is not automatic spawning. It is helping the
parent agent notice that a task is an exploration or review task and can be
delegated to an idle fresh child with a complete, auditable brief.

## Safety Rules

- Prefer read-only explorers before worker sub-agents in complex repos.
- Prefer fresh children for exploration and review; prefer resume or fork for
  same-branch repair and continuous side lanes.
- Do not launch a fresh child without a complete parent brief.
- Give workers disjoint write sets.
- Tell every worker that other agents may be editing nearby files and that it
  must not revert unrelated changes.
- Keep production, credentials, private docs, and user-specific state outside
  public run records.
- The main controller, not sub-agents, performs the final public/private scan.
- The main controller decides the final response and state writeback.

## UI Implication

A future multi-project UI should not show only one status per goal. It should
show the controller run, child sub-agent runs, and compute quota state:

```text
goal
  quota: eligible, compute=0.5, 240/720 minute-slots spent today
  controller run
    subagent: docs-map       completed
    subagent: validation-map completed
    subagent: implementation running
  merge decision
  next action
```

This keeps Codex parallelism inspectable instead of turning it into invisible
background work.
