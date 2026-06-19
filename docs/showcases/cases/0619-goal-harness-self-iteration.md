# 0619: Goal Harness Self-Iteration Loop

## Summary

Goal Harness was used to improve Goal Harness itself. A side agent worked on a
productization and coordination lane while the primary control agent stayed
focused on benchmark readiness. The shared control plane kept the work visible:
identity, todo claims, scope, validation, self-merge policy, and successor work
all stayed in structured state instead of private chat memory.

This case is useful because it is public and commit-backed. The same repo that
contains the feature also contains the evidence of how the agent loop changed.

## Public Workload Signal

The public self-iteration slice from `32b466d^..9acdaa2` contains:

| Signal | Value |
| --- | --- |
| Commits | 11 |
| Files touched | 44 |
| Insertions / deletions | 2777 / 92 |
| Main surfaces | CLI, todo metadata, quota/status/review projection, heartbeat prompt, docs, smokes |
| Release outcome | Installed local release `20260619T152248Z` with the new side-agent self-merge flag available |

This is not a raw transcript metric. It is a public Git range that a reader can
inspect locally with:

```bash
git log --reverse --oneline 32b466d^..9acdaa2
git diff --shortstat 32b466d^..9acdaa2
```

## Feature Chain

The self-iteration produced four connected product changes:

1. **Registered todo ownership**: todos can carry `claimed_by`, and the CLI only
   accepts registered public-safe agent ids.
2. **Identity-aware automation prompts**: scoped goals fail closed until the
   agent prompt names an `agent_id` and natural-language scope.
3. **Side-agent worktree policy**: side agents are instructed to work in an
   independent branch/worktree and avoid out-of-scope benchmark execution.
4. **Small self-merge path**: side agents can self-merge small validated changes
   with `--side-agent-self-merged --evidence`, while broad or high-risk work
   still creates a primary-agent review todo.

That chain matters because it converts a fuzzy collaboration question into
product behavior:

- Who owns this todo?
- Is this agent allowed to take it?
- Where should it edit?
- Does this work need primary review, or can it self-merge?
- What evidence proves the work finished?

## Goal Harness Behavior

Goal Harness made the loop durable in three places:

- the registry named `codex-main-control` as the primary agent and
  `codex-side-bypass` as a registered side agent;
- active todos separated primary benchmark work from the side productization
  lane;
- completion evidence recorded the side-agent self-merge instead of leaving the
  decision only in chat. This evidence writeback is the control-plane record
  that lets a later agent understand why the side lane is complete.

The product value is not that an agent wrote code. The value is that a
multi-agent self-improvement loop stayed reviewable: a future agent can see the
claim, the scope, the validation, and the remaining follow-up work.

## User-Facing Value

For an operator, this case shows how Goal Harness reduces coordination load:

- the primary agent can keep focus on a high-priority lane;
- a side agent can improve product surfaces without silently racing the primary;
- small validated side changes do not become primary-agent queue pressure;
- larger or riskier side work still flows through primary review.

For a potential user, this is the reusable pattern: Goal Harness lets a project
delegate bounded improvement lanes to agents without losing ownership, evidence,
or merge discipline.

## Evidence Boundary

This case intentionally uses only public repository evidence: commit ids, file
counts, public docs, public CLI behavior, and smoke names. It excludes private
thread text, local active-state bodies, internal document links, screenshots,
raw benchmark material, credentials, and machine-specific paths.

## Website Story Beats

1. User feedback identifies a coordination problem: side-agent work should not
   always become primary-agent queue pressure.
2. Goal Harness records identity and scope so the side agent can take a bounded
   productization lane.
3. The side agent ships claim, prompt, showcase, and self-merge policy changes
   with focused validation.
4. Completion evidence writes the decision back to the control plane, leaving
   the next frontend/showcase lane visible for future work.
