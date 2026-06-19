# Marketing Copy Bank

This is a public-safe source bank for Goal Harness outreach copy. It turns
first-contact confusion, launch-note drafts, and maintainer advertising
patterns into reusable language without publishing private screenshots, raw
benchmark traces, internal links, local paths, credentials, or unverified
performance claims.

Use this file as source material for README copy, social posts, GitHub issue
descriptions, Lark/Notion intros, demo narration, and future website cards.
It is not a product contract; stable behavior belongs in the CLI/docs and
showcase catalog.

## Core Positioning

**Gate-aware human-in-the-loop control plane**

**让人的判断成为控制面，而不是让 agent 在等待里空转。**

Goal Harness keeps user decisions, agent todos, safe fallback, run history,
quota, and public/private boundaries in one shared state layer. The gated
route waits clearly; independent safe side work can continue with evidence.

Short form:

> Long-running agent work, without losing the plot.

Plain Chinese form:

> Goal Harness 不是新的 agent runtime。它是给 Codex、Claude Code、Cursor 这类
> agent loop 加的一层长程控制面：目标、用户决策、agent todo、fallback、证据和
> quota 不再散落在聊天里。

## What To Say First

When someone asks whether Goal Harness replaces Codex goal mode:

> No. Codex goal, automation, CLI loops, Claude Code, Cursor, and benchmark
> runners execute bounded work. Goal Harness keeps the lifetime-goal control
> plane visible across those loops.

When someone asks why this matters:

> Long-running agent projects usually do not fail only because the next model
> call was wrong. They fail because state drifts: gates become vague, fallback
> work stops being labeled as fallback, evidence gets separated from the turn,
> and the next agent has to reconstruct user intent from chat memory.

When someone asks what the product does:

> It makes the current goal, user gates, agent todos, ownership, quota spend,
> run history, validation evidence, and public/private boundary explicit enough
> that a human or another agent can safely continue the work.

## Audience Angles

### Heavy AI Coding Users

Use when talking to developers already using Codex, Claude Code, Cursor, or
similar agents for real project work.

Good copy:

- "If your agent can work for hours, it also needs a control plane for what it
  is allowed to do next."
- "Goal Harness lets the agent keep the long-running goal stable while the
  executor loop changes from Codex to automation to another terminal agent."
- "It helps distinguish 'blocked by a user decision' from 'safe to continue
  another lane'."

Avoid:

- claiming Goal Harness makes the model smarter;
- implying it replaces the coding agent;
- promising unattended production control.

### Long Research Tasks

Use for benchmark exploration, technical research, multi-day investigation,
or any task where progress is partly asynchronous.

Good copy:

- "Research tasks do not only need more context; they need durable routing
  state."
- "When one branch is gated, Goal Harness keeps the gate visible and lets safe
  evidence-gathering continue elsewhere."
- "The next run inherits the latest goal, todo ownership, gate, blocker, and
  validation boundary instead of starting from a half-remembered chat."

Avoid:

- publishing raw benchmark tasks, trajectories, verifier output, logs, or task
  ids;
- making benchmark-wide uplift claims from one case;
- using private resource names or cloud-host details as proof.

### Off-Hours Agent Progress

Use when explaining why scheduled turns or nighttime automation can be useful
without turning into uncontrolled autonomy.

Good copy:

- "Off-hours progress is valuable only when the agent knows what counts as a
  safe side path."
- "Quota spend should follow validated writeback, not a vague feeling that the
  agent did something."
- "Goal Harness makes overnight progress reviewable: what happened, why it was
  allowed, what evidence was written, and what still needs a human."

Avoid:

- framing the product as 'run agents forever';
- promising that every blocked task can be bypassed;
- hiding user gates behind generic status words.

### High-Touch Human-Agent Workflows

Use for product, creator-ops, research ops, design exploration, or workflows
where the user gives frequent steering feedback.

Good copy:

- "Human-in-the-loop should not mean making the user become a scheduler."
- "User feedback becomes a visible control-plane signal: gate, preference,
  correction, reward, todo update, or product-improvement note."
- "The agent can explain what it did, what it is doing now, where it is stuck,
  and what future slice should change because of the user's feedback."

Avoid:

- treating inferred preferences as hard rules;
- storing raw private chats or creative material as public examples;
- auto-publishing or acting on behalf of non-technical users without a gate.

### Showcase And Case Accumulation

Use when asking contributors or maintainers to add public cases.

Good copy:

- "A good case shows a reusable control-plane behavior, not just that an agent
  did work."
- "Each case should name the trigger, visible state, agent move, human role,
  evidence, and redaction boundary."
- "The public showcase catalog is the renderable source of truth; narrative
  pages add context."

Avoid:

- copying internal screenshots into public docs;
- using private names, teams, projects, local paths, or raw run artifacts;
- filling redacted gaps with speculation.

## Pattern Phrases

Use these as modular building blocks.

### One-Liners

- "A local control plane for long-running agent goals."
- "Keep goals, gates, todos, quota, and evidence visible across agent turns."
- "Let gated work wait clearly while safe side work continues with evidence."
- "Not an agent runtime; the control plane around the runtime."
- "For teams that already trust agents to work, but still need the work to stay
  governable."

### Chinese One-Liners

- "给长程 agent 工作一层本地控制面。"
- "不绕过人的判断，也不让 agent 在等待里空转。"
- "让目标、gate、todo、证据和 quota 不再散落在聊天里。"
- "不是替代 Codex / Claude Code / Cursor，而是让这些 executor loop 有长期状态。"
- "该停的地方明确停；该继续的安全侧路继续走。"

### Problem Statements

- "The agent is capable, but the project state is not durable enough."
- "A single user gate can freeze the whole loop even when safe work remains."
- "The next agent turn often has to infer which decisions were real, stale, or
  merely suggested."
- "Benchmark and research evidence gets hard to trust when route, quota,
  boundary, and validation are not tied to the turn."

### Value Statements

- "Goal Harness reduces state drift, not by hiding decisions, but by making
  them first-class objects."
- "It turns long-running agent work into a reviewable sequence of bounded
  decisions, actions, validations, and handoffs."
- "It gives side agents a way to contribute without colliding with the primary
  lane."
- "It helps maintainers turn good cases into reproducible demos, docs, and
  product improvements."

## Claim Boundaries

Safe claims:

- Goal Harness is a local control plane for long-running agent goals.
- It can make user gates, agent todos, claims, quota, run history, and evidence
  visible across turns.
- It supports public-safe showcases and synthetic demos.
- It can help side agents work in scoped lanes while a primary agent continues
  high-risk or benchmark work.

Claims that need evidence:

- benchmark uplift;
- time or cost reduction;
- reliability improvements over a baseline;
- "works for all long-horizon tasks";
- production readiness.

Avoid entirely unless a maintainer explicitly approves a public artifact:

- raw private screenshots;
- internal document links;
- local absolute paths;
- benchmark task text, trajectories, logs, verifier tails, or task ids;
- credentials, auth material, cloud host details, or unpublished metrics;
- personal claims about a non-public user or team.

## Copy Patterns By Surface

### GitHub README

Keep the first screen direct:

```text
# Goal Harness

Gate-aware human-in-the-loop control plane.

Long-running agent work, without losing the plot.
```

Then explain the relationship:

```text
Codex, Claude Code, Cursor, and scheduled terminal agents execute work.
Goal Harness keeps the lifetime-goal control plane visible across those loops:
goals, gates, todos, ownership, run history, quota, and evidence.
```

### Lark / Internal Intro

Lead with the bilingual punchline, then use Chinese for the explanation:

```text
Gate-aware human-in-the-loop control plane
让人的判断成为控制面，而不是让 agent 在等待里空转。

Goal Harness 不是替代 Codex goal/automation，而是给这些 agent loop
提供长期控制面：用户决策、agent todo、safe fallback、run history 和 quota
能在同一层状态里被看见、继承、验证。
```

### Social Post

Use a concrete pain point:

```text
The hard part of long-running agent work is not only whether the agent can do
the next step. It is whether the project still knows what the next step means:
what is gated, what is safe fallback, what was validated, and what should be
handed to the next turn.
```

### Showcase Card

Use a case-shaped sentence:

```text
When a P0 lane needed owner judgment, Goal Harness kept that gate visible while
the agent continued a safe P1/P2 side path, wrote evidence, and preserved the
handoff boundary.
```

## Reusable Calls To Action

- "Try the synthetic showcase demo first."
- "Add one public-safe case before adding a new claim."
- "Open a contributor task if you have a control-plane pattern to reproduce."
- "Use Goal Harness when your agent project spans many turns, tools, decisions,
  or handoffs."
- "If your agent keeps working while you sleep, make the gates and evidence
  visible before you trust the result."

## Maintenance Notes

- Prefer concrete cases over abstract hype.
- Prefer "control plane around agent loops" over "agent teammate" framing.
- Keep "lifetime-goal" as category/tagline language unless a rename decision
  packet changes the public brand.
- If a phrase becomes a stable product promise, move it into README/docs and
  add appropriate validation. Do not enforce temporary marketing wording with
  brittle text-only smokes.
