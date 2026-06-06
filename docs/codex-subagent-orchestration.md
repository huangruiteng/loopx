# Codex Sub-Agent Orchestration

Goal Harness should support Codex-style work where one main controller starts
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

Goal Harness should model this as a separate dreaming / exploration lane:

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

## Handoff Contract

Every sub-agent brief should include:

- `goal_id`,
- role: `explorer`, `worker`, or `validator`,
- scope and explicit non-goals,
- allowed files or read-only boundary,
- expected output,
- validation command if applicable,
- merge rule: what the main controller may accept, ignore, or retry.

Example:

```text
goal_id: agent-harness-main-control
role: explorer
scope: inspect docs/TODO.md and doc registry only
non_goals: do not edit files; do not inspect private prod logs
expected_output: current task clusters, likely blockers, validation surfaces
merge_rule: main controller turns this into a read-only map, not direct actions
```

## Registry Contract

Controller/sub-agent fields should stay minimal in v0.1:

```json
{
  "role": "controller",
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
    "write_scope": ["docs/**", "examples/**"],
    "claim_ttl_minutes": 30,
    "requires_parent_approval": ["write", "publish", "production-action"]
  }
}
```

`spawn_policy.mode` is the control-plane execution mode. `default` means the
goal should run as a single ordinary Codex worker. `multi_subagent` means the
controller may launch child workers within `max_children`, `allowed_domains`,
and the coordination/write-scope rules. Status and quota derive the same
compact `orchestration` projection from this policy so agents do not need to
infer sub-agent permissions from chat history.

For a child goal:

```json
{
  "role": "subagent",
  "parent_goal_id": "agent-harness-main-control",
  "coordination": {
    "write_scope": [],
    "requires_parent_approval": ["write"]
  }
}
```

These fields describe permission and coordination expectations. They do not
turn Goal Harness into a lock service. They do make compute quota explicit so
the main controller and automations do not encode priority only through timer
cadence.

## Run Record Shape

Goal Harness run history should eventually record sub-agent activity as first
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

## Safety Rules

- Prefer read-only explorers before worker sub-agents in complex repos.
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
