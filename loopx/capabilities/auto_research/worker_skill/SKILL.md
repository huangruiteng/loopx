---
name: loopx-auto-research
description: Use when a LoopX worker is operating an auto-research lane, demo pane, frontier item, evidence packet, promotion/retirement decision, or visible tmux/Codex auto-research rehearsal. Identity must come from the LoopX role profile and quota/frontier packet; this skill only provides role-specific execution checklists, artifact contracts, and stop conditions.
---

# LoopX Auto Research

This is a worker-local role playbook for auto-research panes. It is packaged
with the auto-research capability and should be injected or referenced by the
worker launcher; it is not a global LoopX skill for ordinary project agents.

## Routing Boundary

Use this skill after a LoopX auto-research worker has a role profile,
frontier item, launcher packet, or user-visible demo pane. The skill is the
role playbook. It is not the source of truth for identity, authority, current
frontier, or merge/publication permission.

Identity comes from LoopX control-plane metadata:

- `auto_research_role_profile_v0` in the launcher/frontier/bootstrap packet;
- `quota should-run --goal-id ... --agent-id ...`;
- todo claim, capability token, write scope, and protected scope;
- repository or workspace `AGENTS.md` rules, which can only make the boundary
  stricter.

No role owns the full graph. Do not infer role from pane title, branch name,
tmux window name, or the section of this skill that happens to be visible.

## Pane Tick Contract

The generic multi-agent kernel prompt already points panes at `$loopx-project`
and `$loopx-doc-registry`. This skill should stay role-specific: use it after
the pane-local tick has resolved identity, quota, and frontier from LoopX.

Compact frontier command: `loopx --format json auto-research frontier --goal-id "$LOOPX_GOAL_ID" --agent-id "$LOOPX_AGENT_ID"`. Also honor `quota should-run`.

If the launcher exported `LOOPX_ROLE_ID`, `LOOPX_ROLE_PROFILE_REF`, or a profile
JSON path, compare those values with the quota and frontier packets. Stop when
they disagree. Do not guess the intended role.

If the role profile includes `successor_todos`, treat those declarations as the
only role-local way to create the next agent todo. A successor declaration must
name the target agent and include a `todo_command_template` such as
`loopx todo add ... --claimed-by {target_agent_id_shell}`. The worker-turn/tick
may render and run that declared command after a successful action and generic
condition check. Do not invent an extra continuation plan in prose, and do not
ask a leader pane to pick the next role.

For a visible demo rehearsal, `auto-research demo-supervisor` is read-only by
default; use `--execute` only when the user opted into starting visible local
panes. The default rehearsal must not start Codex, write LoopX state, or spend
quota by itself.

## Role Resolution

Map the role profile to one of these sections:

| Role id or lane | Skill section | Authority source |
| --- | --- | --- |
| `research_curator` | Research curator | role profile, quota packet, contract todo |
| `hypothesis_mapper`, `hypothesis-runner` when proposing | Hypothesis mapper | role profile, frontier packet, hypothesis todo |
| `evidence_runner`, `hypothesis-runner` when executing | Evidence runner | role profile, selected frontier item, write scope |
| `evidence_verifier`, `evidence-promoter` | Evidence verifier | role profile, evidence packet, promotion policy |
| `research-narrator`, `product_narrator` | Projection narrator | read-only projection packet and first-screen gate |
| `control-plane-guard` | Control-plane guard | quota/status/check packet and repository rules |

The current demo may render fewer or differently named panes than the four
logical research roles. That is only a host layout choice. Every durable
record should still name the logical role or transition duty that produced it.

## Shared Stop Conditions

Stop and report the exact blocker when any of these are true:

- quota says `should_run=false`, `delivery_allowed=false`, or a user/operator
  gate is open;
- the selected todo is missing, claimed by another agent, or not compatible
  with the profile's `capability_token`;
- the next edit touches `protected_scope`, credentials, private material, raw
  logs, raw evaluator data, or unapproved publication surfaces;
- the profile, frontier, `AGENTS.md`, and this skill disagree;
- the work would require a leader/coordinator agent to select, promote, or
  rewrite the whole graph.

## Research Curator

Use when the role owns objective, metric, editable scope, protected scope,
budget, and gates.

Allowed actions:

- create or refresh `research_contract_v0`;
- make protected boundaries explicit;
- write user/operator gate todos when promotion or publication needs judgment;
- request read-only projections from existing evidence.

Useful command:

```bash
loopx --format json auto-research worker-turn \
  --goal-id "$LOOPX_GOAL_ID" \
  --agent-id "$LOOPX_AGENT_ID" \
  --execute
```

Artifact contract:

- objective is public-safe and bounded;
- metric direction and protected evaluator are explicit;
- write scope and protected scope are named;
- promotion policy says what evidence is sufficient.

Must not:

- pick winners;
- run experiments;
- present unsupported metrics as product value.

## Hypothesis Mapper

Use when the role turns ideas into todo-backed hypotheses, refinements,
successors, or retirements.

Allowed actions:

- create `research_hypothesis_v0` records with `todo_id`, `claimed_by`,
  mechanism family, parent link, and grounding refs or no-grounding rationale;
- retire duplicates, exhausted retries, or contradicted directions while
  keeping negative evidence visible;
- add the next bounded agent todo.

Before writing:

- confirm the idea is not claiming novelty from the same source used to ideate;
- confirm the hypothesis can be attempted inside allowed write scope;
- keep todo order and rationale in LoopX state, not only in chat.

Must not:

- delete failures;
- select a winner;
- hide contradictory evidence by replacing a hypothesis with a cleaner story.

## Evidence Runner

Use when the role runs exactly one selected hypothesis in an isolated
workspace/worktree and records attempt evidence.

Allowed actions:

- claim the current frontier item selected for this agent;
- edit only allowed solution or experiment scope;
- run dev or holdout evaluation only when the contract permits it;
- build an `auto_research_evidence_packet_v0` or equivalent public-safe event;
- create only the role-declared successor todo, such as a holdout validation
  todo, when the profile's `successor_todos.condition` is satisfied.

Successor routing belongs here, not in a central projector: the role profile
must name the target agent and provide the `todo_command_template`, typically a
normal `loopx todo add ... --claimed-by {target_agent_id_shell}` command. The
kernel only validates the target agent and executes the normal LoopX todo
writer.

Evidence writeback should use the auto-research worker-turn/evidence commands
exposed by the current LoopX state. Append only after reviewing packet boundary,
then capture compact live evidence from the lane-authored packet when visible
lanes are accepted.

Must not:

- edit protected evaluator/data scope;
- promote results;
- omit failed, inconclusive, or guardrail-failed attempts.

## Evidence Verifier

Use when the role reads evidence and classifies it as supported,
contradicted, retry-needed, promotion-ready, or retirement-ready.

Allowed actions:

- run held-out validation only when the selected frontier action is
  `run_holdout_eval` and the contract permits that split;
- apply the contract's metric and promotion policy to scored or unscored
  evidence;
- request retry with a bounded reason and resumable ref;
- create promotion, retirement, or gate candidates;
- write compact validation notes for the next worker;
- add only the role-declared successor todo when evidence needs another bounded
  split, using the profile's `todo_command_template`.

Verification checklist:

- split label and metric direction are explicit;
- dev evidence is not represented as held-out proof;
- boundary says protected scope stayed clean;
- negative evidence remains queryable.

Must not:

- bypass an owner/operator gate;
- certify a showcase claim;
- rewrite the hypothesis graph to make the result look cleaner.

## Projection Narrator

Use when the role is read-only product narration over accepted projections. This
is a transition duty in v0 and may become a separate role later.

Allowed actions:

- render `research_evidence_graph_v0` from promoted, retired, and retry
  evidence;
- update public-safe docs or Frontstage surfaces only from projection refs;
- preserve failed and retired directions as useful learning.

Useful command:

```bash
loopx --format json auto-research frontier \
  --goal-id "$LOOPX_GOAL_ID" \
  --agent-id "$LOOPX_AGENT_ID"
```

Must stop before:

- inventing metrics;
- reading private source bodies;
- changing first viewport, hero, primary CTA, or opening nav without the
  first-screen review gate.

## Control-Plane Guard

Use when the role checks whether a visible demo, frontier, evidence append,
merge, or publication action is safe and interruptible.

Allowed actions:

- run quota/status/check packets;
- validate public/private boundary;
- confirm attach/stop/takeover controls are visible;
- write blockers or repair todos when projection is contradictory.

Useful command:

```bash
loopx --format json auto-research demo-supervisor \
  --goal-id "$LOOPX_GOAL_ID" \
  --workspace "$LOOPX_PROJECT"
```

Must not:

- act as a leader agent;
- select experiments for other roles;
- approve its own gate.

## Writeback

After a validated step, write back only the smallest durable artifact allowed
by the role:

- `research_contract_v0`;
- `research_hypothesis_v0`;
- `auto_research_evidence_packet_v0`;
- promotion/retirement/gate candidate;
- `research_evidence_graph_v0`;
- LoopX todo completion plus next todo/rationale;
- `loopx refresh-state` and one quota spend only after validation when the
  quota contract permits it.

If the step is blocked, write the blocker as a todo/rationale and do not spend
quota merely for discovering an unchanged gate.
