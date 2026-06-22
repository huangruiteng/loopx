# Project-Level Reward Model

LoopX should not explain long-running agent value only with a single benchmark
score. Benchmarks are useful for narrow task capability, but a Loop Agent works
inside a project over time: it absorbs signals, completes work, asks for human
judgment, spends tokens, and leaves evidence for the next turn.

This note defines a conservative product model for comparing that project-level
value without claiming universal benchmark uplift.

## Core Formula

For complex project work, LoopX should treat agent value as:

```text
project_reward = f(quantity, quality, token_cost, user_attention_cost)
```

The formula is intentionally product-facing. It is not a model-training reward
function, and it is not a replacement for task benchmark metrics. Its job is to
make a Loop Agent reviewable by a human operator.

## Dimensions

### Quantity

What the agent produced.

Observable inputs:

- completed todos;
- merged PRs or accepted patches;
- validated docs, fixtures, or demos;
- resolved gates or blockers;
- evidence packets written back to run history.

Quantity should count bounded deliverables, not chat volume. A summary-only turn
does not count as outcome progress unless the summary itself is the requested
artifact.

### Quality

Whether the output was useful and trustworthy.

Observable or reviewable inputs:

- human review feed: useful, not useful, needs evidence, off-scope, too
  expensive, private/unsafe;
- validation strength: smoke passed, proof artifact present, reviewer accepted,
  or blocker precisely recorded;
- rework rate: whether the user had to correct the same failure pattern again;
- boundary quality: whether the work avoided private material, raw logs,
  credentials, and over-claims.

Quality is the dimension the intelligent management surface must help capture.
Before enough review data exists, use coarse labels such as `high`, `medium`,
`low`, or `blocked` rather than pretending precision.

### Token Cost

How much model or executor budget the agent consumed.

Observable inputs:

- model token counters when the host exposes them;
- LoopX quota slots or runtime minutes as a fallback;
- number of executor turns needed to reach a validated artifact.

Token cost should be comparable within one project or host integration before
being compared across different runtimes.

### User Attention Cost

How much human steering the agent consumed.

Observable inputs:

- number of user gates opened;
- number of repeated or unclear questions;
- time spent waiting on user decisions;
- frequency of avoidable status-only updates;
- number of corrections needed before the agent followed the intended route.

Low attention cost does not mean "never ask the user." Good Loop Agents ask
when judgment is needed and avoid asking the user to be the scheduler.

## Performance Review Shape

A project-level review should summarize a lane or Loop Agent over a time window:

```json
{
  "schema_version": "project_reward_review_v0",
  "goal_id": "loopx-meta",
  "agent_id": "codex-side-bypass",
  "window": "2026-06-22",
  "quantity": {
    "completed_todos": 3,
    "validated_artifacts": 2
  },
  "quality": {
    "label": "medium",
    "evidence": ["smoke_passed", "human_useful"],
    "risk": ["needs_more_user_feedback"]
  },
  "token_cost": {
    "label": "normal",
    "source": "quota_slots"
  },
  "user_attention_cost": {
    "label": "low",
    "asks": 1,
    "avoidable_reasks": 0
  },
  "review_summary": "Useful docs and dashboard progress; needs more outcome evidence before benchmark-level claims."
}
```

The schema should stay compact and inspectable. It should reference source
runs, todos, review events, and validation artifacts instead of copying raw
transcripts or private evidence.

## Relationship To Benchmarks

Benchmark results remain useful, especially for single-task capability and
controlled comparisons. They should be displayed as one evidence source inside
the broader review, not as the whole story.

LoopX should avoid these over-claims:

- "project_reward improved, so the model is generally better";
- "one successful case proves benchmark uplift";
- "low token cost is good even when quality is low";
- "low user attention is good when the agent silently crossed a boundary";
- "many completed todos mean high value without human review or evidence."

Instead, the product claim should be narrower:

```text
LoopX makes long-running agent work reviewable by quantity, quality, cost, and
human attention, so operators can decide which Loop Agents deserve more trust.
```

## Product Surface

The intelligent management surface should expose this model in three levels:

1. **Review feed**: card-level feedback such as useful, not useful, needs
   evidence, too expensive, off-scope, or private/unsafe.
2. **Lane snapshot**: current quantity, quality label, cost label, attention
   label, blocker, and next expectation for one agent lane.
3. **Performance review**: periodic rollup that compares selected lanes or
   anchors over a bounded window.

The first implementation can be read-only. Scoring and control writes should
remain separate: a review can recommend a todo, gate, or replan, but actual
mutation still goes through LoopX authority, quota, and boundary checks.

## Acceptance Criteria

This model is ready for implementation when:

- status or dashboard can show quantity, quality, token cost, and attention
  cost as separate fields;
- quality can be driven by explicit review events or validation evidence, not
  hidden inference from chat;
- benchmark scores can be attached as evidence without becoming the only value
  metric;
- user attention cost can distinguish good human gates from avoidable repeated
  steering;
- public docs and showcases avoid claiming general benchmark uplift from this
  project-level review model.
