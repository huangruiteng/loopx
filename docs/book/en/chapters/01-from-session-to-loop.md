# From one session to long-running work

An agent that can edit code, run tests, and explain a result in the current session does not automatically
own work that lasts for days. The first distinction is between session context and project memory.

## What you should learn

After this chapter, you should be able to:

- identify state that must not exist only in a transcript;
- distinguish the execution plane from the control plane;
- list the minimum durable state for work that crosses sessions;
- separate durable project facts from environment facts that require fresh inspection;
- recognize when a normal agent session is still enough.

## The scenario used throughout the book

Assume that you need to add `--format json` to an existing CLI:

1. change the output layer;
2. preserve the default text output;
3. add tests;
4. wait for CI;
5. ask a maintainer to confirm the JSON contract;
6. revise the change and release it.

If all six steps fit into one uninterrupted session, the transcript, Git diff, and test result may be
enough. In real work, the interruption often arrives after step three: context is compacted, CI is still
running, a maintainer replies tomorrow, another agent takes over, or an external dependency changes.
What the model remembers and what the project currently knows then become different things.

## Context is working memory, not a ledger

Model context is useful for:

- local reasoning about the current problem;
- code that was just inspected;
- tool results from this turn;
- the short plan about to be executed.

It is a weak sole owner for:

- the goal and acceptance criteria;
- completed work and its validation;
- a decision that is waiting on a specific authority;
- ownership of the current work item;
- whether an external write actually happened;
- when to retry, wait, or stop.

The problem is not only token capacity. Different events invalidate different assumptions:

| Event | Assumption that no longer holds |
| --- | --- |
| Session ends | The next turn can read the full context |
| Context compaction | Every original detail retains the same strength |
| Agent or model changes | The new executor shares the implicit plan |
| A human decision arrives | The old plan is still authorized |
| CI, an Issue, or a service changes | The last observation is still current |
| A tool times out | Starting an action proves that it completed |

Long-running work externalizes the minimum facts needed to derive the next action. It does not preserve
every thought. Recovery also has to re-inspect the checkout, Host capabilities, and external systems:

```text
next decision =
  replay(durable project facts)
  + inspect(fresh environment)
```

LoopX canonical state owns lifecycle facts. Git commits, CI checks, and external resources remain owned by
their respective systems; LoopX stores bounded readbacks, revisions, and evidence pointers.

## Execution plane and control plane

The **execution plane** performs one bounded action:

- an agent edits code;
- a shell runs tests;
- a provider calls GitHub;
- a Host starts another model turn.

The **control plane** decides which action is legal now, why work should continue, when it should wait, and
how a result becomes durable:

- Is the goal and its acceptance still valid?
- Which Todo is on the current frontier?
- Does a user Gate block this action?
- Can the evidence support the proposed transition?
- Does quota allow another turn?
- Where should work resume after interruption?

```text
Control plane: select and constrain the next action
       |
       v
Execution plane: perform one bounded action
       |
       v
Observation or receipt: return a verifiable result
       |
       v
Control plane: accept, reject, or replan
```

LoopX does not replace the execution plane. It does not write the code, host Git, or run CI. It lets a
workflow consume verifiable results from those systems across turns.

## Why three kinds of long-running work share one control plane

LoopX control contracts are not tied to one domain workflow. The Control-Plane Course uses three
Showcases to demonstrate that domain facts and acceptance can differ completely while Goal, Todo, Gate,
quota, evidence, and recovery remain reusable.

| Showcase | Domain facts and judgment | Reused control plane |
| --- | --- | --- |
| PR Issue Fix | Issue feasibility, exact-head checks, review, and merge state | Todo, claim, workspace guard, monitor, successor, and terminal closeout |
| Single-Agent Auto ML | Metric contract, matched baseline, experiment revision, external task, and guardrail | Quota, Provider receipt, monitor, defer/resume, and promotion Gate |
| Multi-Agent Auto Research | Hypothesis, dev/holdout evidence, and support/refutation relationships | Per-Agent frontier, handoff, evidence lineage, and promotion/retirement |

All three product paths reduce to the same long-running loop:

```text
external fact
  -> Provider observation
  -> Capability domain judgment and transition proposal
  -> Kernel checks authority, frontier, quota, and workspace
  -> Agent / Host executes one bounded Turn
  -> independent validation, evidence, and receipt writeback
  -> recompute continue | wait | ask | replan | repair | terminal
```

The reusable unit is a lifecycle invariant, not a generic prompt. Issue-Fix may interpret
`CHANGES_REQUESTED`, Auto ML may interpret a matched baseline, and Auto Research may interpret holdout
evidence. Those meanings belong to a Capability and Domain State. The common Kernel still decides who can
claim, whether execution is legal, when to wake again, which evidence permits writeback, and whether the
Goal is terminal.

This boundary also explains why a new domain capability should not copy its own runner, queue, retry, and
completion state machine. The domain layer supplies decidable facts and proposals, a Provider performs
external calls, and the Kernel owns cross-domain lifecycle.

For the complete Showcase derivation, architecture, and source entrypoints, continue to
[Control-Plane Course Lesson 0](/loopx/docs/development/control-plane-course/00-goal-control-plane-architecture/).
Use the [concept primer](/loopx/docs/development/control-plane-course/00-concept-primer/) first when the
vocabulary is new.

## The minimum state to externalize

For the running scenario, the minimum useful state is not the full transcript. It is enough state to answer
recovery questions:

```yaml
# Simplified for explanation; this is not a LoopX file format.
goal: Add compatible JSON output to the CLI
acceptance:
  - Default text output is unchanged
  - JSON schema is tested
frontier:
  - todo: Wait for the maintainer to approve field naming
    state: blocked
gate:
  question: Is error_code accepted as a stable field?
evidence:
  - Unit tests passed at commit abc123
next_wake:
  when: Maintainer decision arrives
```

The next executor can reason from the goal, work queue, Gate, evidence, and fresh environment instead of
trusting a previous agent's narrative. The example is a teaching model, not a LoopX storage format. Part I
next separates these facts across the state and projection protocols.

## When a normal session is enough

Do not upgrade every task into a long-running control plane. A normal session is a good fit when the work:

- has closed scope;
- can finish in the current context;
- waits on no external event;
- needs no agent handoff;
- is cheap to redo after failure;
- can be recovered from the Git diff and tests.

Explaining a function, fixing a typo, or testing a pure function rarely needs a project-level Goal and Todo.

Consider a persistent Goal or LoopX when any of these are present:

- multiple turns or sessions;
- dependencies, parallel lanes, or handoffs;
- authority boundaries or human Gates;
- external effects that require readback and receipts;
- scheduled monitoring or backoff;
- recovery from another Host or agent.

The next chapter compares a normal session, Codex Goal, and LoopX by the state each moves out of the prompt.
