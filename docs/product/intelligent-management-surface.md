# Intelligent Management Surface

This note defines the maintainer-first management surface for LoopX. It is the
product bridge between a local control plane and the larger "Loop Agent" vision:
agents that keep a stable job, absorb external signals, produce reviewable work,
and improve delivery through long-term human feedback.

The surface should first serve the maintainer operating LoopX itself. If it
cannot help a maintainer understand multiple LoopX agents, user gates, evidence,
quality, cost, and follow-up choices, it is too early to sell as a general
operator dashboard. After that works, the same surface can support issue-fix
loops, open-source PR-led growth, office operations, and domain packs.

## Product Thesis

Loop Engineering is not only about keeping an agent process running. The hard
part is making long-running work manageable:

- goals stay stable enough to recover;
- agents can receive fragmented human and external signals;
- work output is visible, scored, and comparable;
- human attention is spent on judgment, not on scheduling;
- evidence and boundaries survive handoff across agent loops.

LoopX should therefore expose a management surface, not just a status page. The
surface answers: "Which Loop Agent is worth trusting with more work, which lane
needs human judgment, and what value was produced for the cost?"

## Loop Agent Definition

A Loop Agent is a long-running worker with:

- a relatively stable job responsibility;
- a relatively consistent goal or success model;
- the ability to ingest external signals over time;
- output that matches its responsibility;
- a habit of organizing its own work evidence;
- periodic performance review under human guidance;
- a constraint to improve delivery while staying focused and low-cost.

This definition deliberately separates the agent from any one executor. Codex,
Claude Code, browser automation, an issue solver, or a project adapter can be
an executor loop. LoopX owns the control state around that loop: goal, gate,
todo, evidence, feedback, quota, and handoff.

## First User: Maintainer

The first real user is the maintainer managing LoopX work. This matters because
the maintainer has the hardest version of the problem:

- many active project lanes;
- primary and side agents with different scopes;
- public docs, benchmark work, frontend work, and partner exploration moving in
  parallel;
- frequent user feedback that is useful but fragmentary;
- a need to choose a few high-value anchors rather than chase every possible
  issue, case, or integration.

For open-source PR-led growth, LoopX does not need to be the issue solver. A
partner or host product may run the solver. LoopX should help the maintainer
select high-value anchor repositories, track whether solver work creates
credible evidence, and convert useful outcomes into showcase, onboarding, or
product feedback.

## Core Surface

The maintainer surface should start as a read-first console with five stable
regions.

### 1. Signal Inbox

The inbox collects external and human signals without pretending they are all
tasks:

- user feedback and questions;
- issue or PR opportunities;
- partner/project updates;
- benchmark or validation events;
- content or outreach opportunities;
- product friction seen in onboarding.

Each signal should carry source, freshness, privacy boundary, and a suggested
control effect: ignore, ask user, create todo, update evidence, create anchor,
or schedule review.

### 2. Anchor Board

The anchor board is the antidote to doing every plausible thing. It names the
small set of high-value proof paths that currently matter.

Examples:

- LoopX self-management as the dogfood anchor;
- hosted frontstage and quickstart as onboarding anchors;
- one public issue/PR loop as an open-source growth anchor;
- one benchmark/evidence lane as a value-proof anchor.

Anchors should be few, explicit, and reviewable. A signal or todo can be useful
without becoming an anchor.

### 3. Agent Lane Board

The lane board shows the current Loop Agents and their responsibilities:

- primary agent;
- side agents;
- product or capability agents;
- domain-pack agents;
- external partner workers when they are only evidence producers.

For each lane, show current todo, claim, scope, workspace policy, latest
evidence, blocker, and next stop condition. Side agents should be visible as
scoped contributors, not as hidden background work.

### 4. Review Feed

The review feed is the attention-efficient surface. It can feel like a
lightweight recommendation feed, but the semantics are work review, not
entertainment.

Each card should be dismissible or scoreable:

- useful / not useful;
- promote to anchor;
- ask for evidence;
- needs user decision;
- too expensive;
- off-scope;
- private or unsafe;
- split into todo;
- archive.

This lets the maintainer "brush through" agent output quickly while still
creating structured feedback. The card outcome should map to a typed LoopX
event such as `review_event`, `feedback_signal`, `todo_update`,
`anchor_update`, or `performance_review_note`.

### 5. Performance Review

Performance review turns fragmented work into a value story. It should not be a
single benchmark score. For long-running project work, value is closer to:

```text
reward = f(quantity, quality, token_cost, user_attention_cost)
```

Where:

- quantity is task/output count and delivery throughput;
- quality comes from review feed scores, evidence strength, and human feedback;
- token cost is model or execution cost when observable;
- user attention cost is asks, interruptions, unclear summaries, and repeated
  steering burden.

The first implementation can use rough labels before numeric precision:
high/medium/low quality, cheap/normal/expensive cost, low/medium/high attention
cost. The important product move is to make "agent value" reviewable at the
project level, not only at single-task benchmark level.

The narrower reward model lives in
[Project-level reward model](project-level-reward-model.md). That note keeps
the formula, review schema, benchmark boundary, and acceptance criteria in one
place so the management surface can stay focused on user interaction.

## Data Contracts

The surface should grow from explicit contracts rather than UI-only state.

| Contract | Purpose |
| --- | --- |
| `signal_v0` | External or human input with source, boundary, freshness, and suggested effect. |
| `anchor_v0` | A selected proof path that the maintainer wants to evaluate. |
| `review_event_v0` | A user's card-level decision or score on an output, todo, or signal. |
| `feedback_signal_v0` | A normalized effect: gate decision, preference hint, todo mutation, reward, or product note. |
| `performance_review_v0` | Periodic lane-level review of output, quality, cost, attention, and next expectation. |
| `management_projection_v0` | Read model joining goals, lanes, anchors, gates, todos, evidence, and review feed. |

The existing LoopX objects remain the source of truth for control: goal,
gate, todo, quota, evidence, run history, handoff, and boundary. The management
surface adds review and value semantics around them.

## Observe/Review/Score Versus Control

The management surface should be useful before it is allowed to control work.
This keeps adoption low-risk and gives users a way to judge existing agents
before trusting LoopX with writeback.

| Layer | Allowed behavior | Write boundary |
| --- | --- | --- |
| Observe | read goals, todos, claims, gates, evidence, run history, and compact costs | no LoopX state mutation |
| Review | let the user inspect cards, mark useful/not useful, ask for evidence, or flag boundary concerns | local or draft `review_event_v0` only |
| Score | aggregate quality, cost, attention, and output labels for a lane or anchor | append review summary only after explicit user save |
| Control | turn feedback into todo changes, gate decisions, anchor promotion, or replanning | normal LoopX CLI/API write path, quota, boundary, and authority checks |

The UI should not blur these layers. A user can browse and score a feed without
granting control. A score can recommend a control transition, but the transition
must still pass through the same LoopX state, authority, and boundary contracts
as CLI-driven work.

## Adoption Path

The management surface and the control loop can be adopted in stages.

1. **Observe and review**: connect a project, show todos/evidence/lanes, and let
   the user score outputs. No control writes are required.
2. **Structure feedback**: map review choices into `feedback_signal_v0`,
   product notes, and suggested todos.
3. **LoopX control**: promote selected feedback into gates, todo mutations,
   priority changes, or planned agent turns.
4. **Performance review**: summarize each Loop Agent's output quality, cost,
   attention cost, and next responsibility.

This makes the intelligent display surface valuable before full automation is
trusted. It also gives LoopX a path to grow with host products: a host can keep
its executor or issue solver, while LoopX supplies the reviewable control and
management layer.

## Repository And App Boundary

The first implementation can live in the same repository as the existing
dashboard because it depends on the same public control-plane contracts. Keeping
it together avoids a second source of truth while the projection model is still
moving.

The boundary should be explicit:

- `loopx/` owns schemas, CLI writes, status projection, quota, gates, and
  public/private checks;
- `apps/dashboard/` owns read-first operator UI, review-feed mock actions, and
  URL-backed filters;
- `docs/product/` owns product contracts and acceptance criteria;
- public showcase routes explain the idea, while ops routes manage real local
  state;
- any browser write path must call a typed LoopX command or local API and stay
  behind a separate capability gate.

This means the management surface is part of LoopX, but not all future host
products need to live in this repository. A partner issue solver, office-ops
connector, or content agent can remain outside the repo and expose compact
signals, evidence, and review cards to LoopX.

## Frontend Collaboration Model

Frontend collaboration should focus on making the management surface feel like
a real work product, not on moving control authority into the browser.

Useful collaboration areas:

- information architecture for project selector, lanes, anchors, review feed,
  and performance review;
- dense operator interaction patterns for filtering, searching, scoring, and
  quick dismissal;
- accessibility and responsive behavior for repeated review sessions;
- visual hierarchy that distinguishes user gates, soft preferences, and
  boundary risks;
- local-only mock actions for review cards before write APIs are enabled.

Non-goals for frontend collaboration:

- direct mutation of `.loopx`, `.local`, or runtime history from arbitrary UI
  state;
- hidden recommendation ranking that cannot be explained as a LoopX projection;
- autopublish or production actions;
- importing private chats, raw traces, or private documents into public
  fixtures.

## Near-Term PoC

The first PoC should be narrow:

- project selector: all projects or one project;
- todo search by id/text/claim/status;
- lane summary for primary and side agents;
- user-gate panel with concrete questions;
- evidence/review feed with useful/not-useful actions mocked or local-only;
- one performance review panel showing output count, quality label, token cost
  when available, and user-attention cost proxy.

The first accepted use case is maintainer self-management: finding a todo,
understanding why it is selected, reviewing recent outputs, and deciding what
should become an anchor. Issue-fix and office-operation cases can reuse the
same surface after the maintainer flow is credible.

### PoC Acceptance Plan

The PoC is accepted when a maintainer can complete this loop on local data:

1. Select all projects or one project.
2. Search for a todo by id or text and see its goal, status, claim, lane, and
   evidence pointer.
3. Inspect the current user gate and confirm whether action is required.
4. Review at least three work cards and mark them useful, not useful, needs
   evidence, or off-scope in a local/draft layer.
5. See a lane-level review summary with output count, quality label, token cost
   when available, and user-attention cost proxy.
6. Promote exactly one reviewed item into a proposed todo or anchor, without
   mutating LoopX control state until the explicit write path is enabled.

This acceptance path deliberately serves maintainer management before broader
issue-solver or office-ops showcases. Once it works for LoopX itself, the same
projection can ingest partner issue-fix results or office-operation signals as
external evidence instead of treating them as first-class control authorities.

## Non-Goals

- Do not turn the UI into an autonomous hidden planner.
- Do not treat soft preference feedback as safety or permission policy.
- Do not ingest private chats, traces, or internal documents into public
  evidence.
- Do not optimize for content volume alone; output count without quality and
  attention cost is a shallow metric.
- Do not make every issue or signal a task. The maintainer chooses anchors.

## Acceptance Criteria

This design is ready to move from document to implementation when:

- it can explain the current LoopX maintainer workflow without private context;
- it maps every user interaction to a typed event or no-op;
- it keeps observe/review separate from control/writeback;
- it can compare at least two agent lanes by output, quality, cost, and
  attention cost;
- it gives the maintainer a fast way to find a todo, review its evidence, and
  decide whether it belongs to a high-value anchor.
