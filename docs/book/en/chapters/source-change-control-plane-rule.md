# Change one control-plane rule

A control-plane change rarely affects only one return value. A small condition can change which Todo an
Agent selects, whether the user is interrupted, whether the Host wakes again, and whether the turn is
eligible for spend.

The safe sequence is not “find the `if` and change it.” It is:

```text
problem
  -> invariant
  -> source facts
  -> ordered decision
  -> protocol delta
  -> implementation owner
  -> independent oracle
  -> rollout and recovery
```

This chapter repairs one existing contract:

> When an open Gate lacks a valid scope relation, LoopX selects typed repair. It must not guess global
> blocking or guess that authority was granted.

This restores an existing authority invariant. It does not introduce a new product capability.

## What you should learn

After this chapter, you should be able to:

- rewrite a bug report as source facts, an invariant, and forbidden outcomes;
- distinguish an implementation repair, protocol clarification, additive change, and breaking migration;
- express precedence as ordered rules, including negative rules that suppress an action;
- choose the owning bounded context and smallest complete change surface;
- derive contract, smoke, replay, and canary evidence from an independent semantic oracle;
- recognize when a public-contract change needs design or owner review before implementation.

## Classify the change before editing

“Change a rule” can mean four different jobs:

| Type | Meaning | Default response |
| --- | --- | --- |
| Implementation repair | Code violates an existing protocol | Repair conformance and add regression evidence |
| Protocol clarification | Several interpretations exist and the contract is incomplete | Agree on semantics, then update contract and implementation together |
| Additive protocol change | A new legal state, field, or transition is needed | Define compatibility, default, writers, and readers |
| Breaking migration | Old input or output is no longer legal | Use explicit versioning, migration readers, release gates, and stop conditions |

This chapter's case is an implementation repair. Existing
[`decision_scope_v0`](https://github.com/huangruiteng/loopx/blob/main/docs/reference/protocols/decision-scope-v0.md)
already makes Gates scoped authority. The public
[State Machines](https://github.com/huangruiteng/loopx/blob/main/docs/product/core-control-plane/state-machine.md)
already route ambiguous scope toward repair.

If implementation turns ambiguity into global wait, repair implementation. Do not add a compatibility flag
that legitimizes global guessing.

## Step 1: Freeze the semantics

Write source facts before observing current product output:

```text
F1: an Agent Todo requires decision scope S1
F2: an open User Gate exists
F3: the Gate has no valid scope relation
F4: no explicit global authority exists
```

Invariant:

```text
authority cannot be inferred from prose or missing data
```

Allowed outcomes:

```text
the protected action does not run
the ambiguity becomes typed repair or a concrete decision question
independent work may continue only when safety remains provable
```

Forbidden outcomes:

```text
missing scope grants S1
missing scope becomes an implicit global gate
the Gate disappears from the user channel
the Host reconstructs authority from display text
```

This becomes the independent oracle for tests. Do not run current code first and copy its JSON into the
expected result.

## Step 2: Draw the protocol chain and owners

The repair crosses:

```text
Gate/Todo source
  -> scope projection
  -> coverage decision
  -> Goal and Agent frontier
  -> interaction contract
  -> scheduler hint
  -> repair writeback
```

Assign ownership:

| Boundary | Contract responsibility | Should this case change it? |
| --- | --- | --- |
| Gate/Todo source | Store typed scope and lifecycle | No; the current fields are sufficient |
| Scope projection | Preserve missing or invalid diagnostics | Maybe, if this layer drops them |
| Coverage decision | Distinguish matching, unrelated, ambiguous, and global | Yes, if policy guesses |
| Frontier | Exclude unauthorized work and preserve provably independent work | Only if selection is wrong |
| Interaction contract | Preserve user, Agent, and CLI channels | Maybe, if typed repair is hidden |
| Scheduler hint | Consume the final decision | It must not invent another rule |
| Writeback | Record repair, decision, or blocker | Reuse the existing lifecycle path |

This prevents two failures:

- changing only policy while projection continues to erase the diagnostic;
- refactoring status, quota, and scheduler just because the chain crosses them.

Change the first broken boundary and every necessary consumer—not unrelated structure.

## Step 3: Write the decision table

Express mutually exclusive outcomes:

| Gate facts | Todo requirement | Expected mode | Forbidden mode |
| --- | --- | --- | --- |
| Valid matching scope | Requires the same scope | `operator_gate` | Normal protected delivery |
| Valid unrelated scope | Requires another scope | Independent frontier | Global wait |
| Nonblocking `user_action` | Requires protected scope | Scope remains unmet | Authorized delivery |
| Missing or invalid scope | Requires protected scope | Typed repair | Approval or implicit global Gate |
| Explicit global Gate | Any covered action | Global operator Gate | Covered independent delivery |
| Other-Agent scoped Gate | Current Agent unrelated | Current safe frontier | Cross-Agent freeze |

The table includes:

1. **positive cases** proving a matching Gate blocks;
2. **negative cases** proving an unrelated Gate does not block;
3. **illegal states** proving ambiguity cannot receive an arbitrary interpretation.

A single happy path misses the most dangerous control-plane bugs: individually plausible booleans that
combine into authority leakage.

## Step 4: Make precedence explicit

The same quota decision can also observe:

- registry or projection health failure;
- autonomous replan;
- handoff ownership;
- capability and workspace guards;
- a due monitor;
- throttle or pause.

Place the rule in an explicit order:

```text
1. invalid source or projection relation -> repair owns the transition
2. valid matching authority Gate -> ask or wait for that scoped decision
3. valid independent frontier -> bounded delivery may continue
4. no runnable work -> wait, replan, or terminal under existing contracts
```

Rule 1 must precede ordinary Gate wait. Otherwise “cannot determine scope” is projected as “correctly
determined to block,” and the gap is never repaired.

Rule 3 is a negative rule. It proves that a lower-level `open_gate_count` cannot preempt a candidate that is
independent of the Gate. Negative rules need names, reasons, and tests just like positive repair rules.

### Review a first-match policy

For each row, ask:

- Which facts must be true?
- Which higher-priority rule can intercept it?
- Does it derive an obligation or explicitly suppress one?
- Can the reason code explain the match?
- Does adding an unrelated Gate, Todo, or Agent preserve the result?

The final question naturally creates metamorphic tests instead of full-payload snapshots.

## Step 5: Decide whether the protocol changes

The current protocols already express:

- a valid scoped Gate;
- an explicit global Gate;
- required decision scope;
- missing or ambiguous relation;
- repair and separate interaction channels.

The right conclusion is:

```text
protocol semantics: unchanged
implementation conformance: repaired
new public field: none, unless typed repair is not representable
migration: none
```

If a new public field is unavoidable, answer:

1. Is it canonical source or a derived diagnostic?
2. Who writes it and who reads it?
3. What does absence mean?
4. Do old readers ignore, degrade, or reject it?
5. When can it be removed?
6. Does it affect output budgets, dashboards, Hosts, or release compatibility?

Do not add a field to the default hot path merely because it is convenient for debugging.

## Step 6: Choose implementation ownership

Assign code by change reason:

- scope schema and lifecycle belong to the Todo/Gate owner;
- Agent-scoped selection belongs to Agent/Todo read models;
- precedence and interaction mode belong to quota policy;
- cadence belongs to the scheduler;
- Markdown and JSON presentation belong to renderers;
- controlled repair writeback reuses the original lifecycle writer.

Do not create a generic `gate_utils.py` for every module that reads a Gate. Shared authority knowledge is a
contract; similar string handling is not necessarily a bounded context.

### When a new module is justified

Consider one only when:

- a cohesive rule family can be named;
- a real caller exists;
- input and output form a stable contract;
- the existing owner is wrong for the change reason;
- characterization or parity protects the move;
- stale internal entrypoints can be deleted, or a real external compatibility window exists.

A large file is a signal to inspect ownership. It is not automatic permission to extract helpers.

## Step 7: Design the smallest complete validation

Expand validation outward from semantic risk.

### 1. Contract or decision-table test

Cover:

- matching;
- unrelated;
- nonblocking notice;
- ambiguity;
- explicit global authority;
- cross-Agent isolation.

Expected outcomes come from the reviewed table, not a product builder.

### 2. Negative and metamorphic coverage

Examples:

- increase unrelated Gates from one to eight; the decision stays unchanged;
- change renderer wording; authority stays unchanged;
- change `user_action` prose to “approved”; it still grants no scope;
- add other-Agent backlog; current-Agent repair stays unchanged;
- add a valid scope relation; repair resolves into the correct Gate or independent frontier.

These tests protect “irrelevant changes do not change authority.”

### 3. Focused integration

Run the real source-to-quota path and prove:

- projection diagnostics survive;
- final `interaction_contract` selects repair;
- scheduler consumes the final result;
- the protected action never enters TurnEnvelope;
- no validation or writeback means no spend.

### 4. Public-safe replay

A replay fixture contains only minimal source facts, an independent invariant, and expected outcome. It
must not contain:

- raw active state;
- transcripts or complete prompts;
- private Issue or PR links;
- machine registry paths;
- stdout or stderr tails.

Replay executes the real decision path. It is more than a fixture-shape test.

### 5. Risk-based canary

For quota, scheduler, Todo/Gate, or Agent-facing output changes, let the canary planner select affected
surfaces from the Git diff. Canary adds cross-boundary confidence. It does not replace the named focused
regression.

## Step 8: Define failure and recovery

A rule is incomplete when failures have no legal next transition:

| Failure | State | Next step |
| --- | --- | --- |
| Source lacks scope | Typed source/projection repair | Supply valid scope or explicit global authority |
| Parser drops scope | Projection gap | Repair the read model and recompute |
| Duplicate conflicting Gates | Repair with diagnostics | Lifecycle owner supersedes or deduplicates |
| User cannot decide now | Deferred Gate | Write a supported `resume_when` |
| Repair write conflicts | Revision conflict | Fresh read and retry without overwriting another writer |
| Host lacks repair capability | Capability blocker | Preserve a concrete owner action |

“Keep waiting” is not a universal fallback. Waiting needs a target, resume condition, and freshness policy.

## Step 9: Handle compatibility and migration

If a repair makes previously accepted input invalid, decide whether that input is:

- a real public contract;
- local runtime state only;
- an older canonical event;
- an accidental test-fixture shape;
- an already-invalid state tolerated by implementation.

Only real compatibility promises justify a long-lived reader. A migration typically follows:

```text
legacy input
  -> explicit migration reader
  -> exactly-once normalized event
  -> canonical output contains only the new shape
```

Do not let legacy fields remain in new writers. Do not preserve incorrect ownership behind a permanent
wrapper. An implementation repair protects legal behavior, not an authority leak.

## Step 10: Update the authoritative documents

Different artifacts own different claims:

| Artifact | What it should own |
| --- | --- |
| Protocol | Source, state, invariant, transition, and failure semantics |
| State machine or seam map | Precedence, ownership, and composition |
| Contributor guide | Development, validation, and submission workflow |
| User guide | Observable user behavior and recovery |
| Changelog or release note | Compatibility, defaults, and migration impact |

Do not append every explanation to one course lesson, and do not turn this book into a shadow protocol
source. The book teaches the method; official contracts own current fields and status.

## A complete pre-implementation statement

```text
Problem:
  Ambiguous Gate scope is currently projected as a global wait.

Invariant:
  Missing authority data grants nothing and cannot imply global scope.

Protocol status:
  Existing decision_scope_v0 behavior; implementation repair only.

Rule delta:
  Ambiguous relation selects typed repair before ordinary operator-Gate wait.

Unaffected:
  Valid matching scopes, explicit global Gates, independent safe work,
  Host capability declarations, and lifecycle storage.

Evidence:
  Decision table, metamorphic cases, source-to-quota integration,
  public-safe replay, and diff-selected canary.

Recovery:
  Repair writes through the existing lifecycle path with revision checks.
```

A reviewer can judge completeness and scope before learning every implementation detail.

## Common failure modes

### Testing only the new positive result

Without suppression cases, the change can alter precedence for other Agents, monitors, or Gates.

### Adding one boolean per branch

Booleans quickly create illegal combinations. Prefer closed states, typed reasons, and ordered transitions.

### Repairing policy in a renderer

Copy cannot repair source or authority. Policy must not depend on Markdown text either.

### Adding an empty adapter for a future Host

An adapter without a caller, capability, and receipt only increases maintenance surface.

### Treating characterization as correctness

Characterization proves what the system did, not what it should do. Repair contradictions and add negative
coverage instead of refreshing a golden file.

### Refactoring every adjacent module

A cross-module protocol chain does not require every possible cleanup in one PR. Change only the complete
chain required by this invariant.

## Checklist

Before changing a rule, confirm:

- [ ] The work is classified as repair, clarification, additive change, or migration.
- [ ] Source facts, invariant, allowed outcomes, and forbidden outcomes are independent of implementation.
- [ ] The protocol chain and every owner are explicit.
- [ ] The decision table covers positive, negative, and illegal states.
- [ ] Precedence and suppression rules are reviewable.
- [ ] Every new field, module, CLI option, or adapter has a real caller and lifecycle.
- [ ] The oracle does not come from current implementation output.
- [ ] Failure, retry, idempotency, and recovery are defined.
- [ ] Compatibility protects real contracts rather than incorrect behavior.
- [ ] Documentation changes return to their authoritative homes.

To map this method onto real Kernel bounded contexts, ordered rules, schemas, projections, and smoke
paths, continue to
[Control-Plane Course Lesson 7](/loopx/docs/development/control-plane-course/07-engineering-a-control-plane-rule/).
This chapter owns the external contribution method; the course owns the deeper implementation derivation
and review exercises.

The next chapter takes the repair from local evidence to a public PR: quality layers, commits, boundary
scans, and a protocol-level review packet.
