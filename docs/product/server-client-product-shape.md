# Server-Client Product Shape

This note describes a medium-term product shape for LoopX. It is not an
implementation spec for a network service. The purpose is to name the product
roles clearly enough that future CLI, dashboard, Lark, MCP, and server work can
share one mental model.

LoopX is the control plane around agent loops:

- the server owns durable goal state, event history, and governed planning
  lanes;
- the client acts as the user's intent proxy;
- executor loops do bounded work and write back evidence.

## Product Roles

### Server

The LoopX server is the durable control-plane owner. It should be
thought of first as a database-backed state system, not as the place where
agent intelligence lives. In local-first mode, this may still be implemented
by files plus CLI commands. In the product shape, however, the server is where
long-running facts become coherent:

- stable goal identity, current belief, todo state, gate state, and run
  history;
- registered agent identity, role, scope, worktree policy, and review handoff
  defaults;
- maintainer-facing signal inbox, selected anchors, and performance-review
  summaries;
- per-todo claim and future lease state;
- quota, spend, idempotency, and concurrency policy;
- compact public/private boundary summaries;
- compact mental-model and management projections for clients;
- scheduled planning, dreaming, and replanning queues;
- review and feedback rollups for maintainer-facing performance review;
- proposal promotion from advisory lanes into normal user or agent todos.

The backend layer around that store should be thin but strict: typed reads,
idempotent writes, conflict checks, compact projections, scheduler decisions,
and public/private boundary enforcement. It is closer to a control-plane
database plus projection API than to a traditional application server that
owns domain behavior.

The server should stay conservative. Planning lanes may rank candidate todos,
surface refactor warnings, or propose evidence probes, but they do not execute
protected work, read private material, or spend delivery quota until promoted
through the normal gate, quota, and boundary path.

For the maintainer-first product surface, the server should treat external
signals as candidates before they become work. A GitHub issue, pull request,
failing check, Lark feedback, or document change can enter the signal inbox;
only selected high-value anchors become todos, owner-routing requests, or
showcase candidates. This keeps "always running" from turning into "always
busy."

### Delivery And Planning Queues

The server roadmap should separate two queue families while keeping them in the
same durable state system:

- **Delivery queue**: promoted user or agent todos that an executor may work on
  after `quota should-run`, claim or lease checks, workspace policy, capability
  checks, and goal-boundary checks.
- **Planning queue**: dreaming, periodic replan, memory consolidation, and
  refactor-warning proposals that may inspect compact run history and rank
  candidate work, but remain advisory until promoted.

Both queues should share the boring control-plane substrate: per-goal locks,
per-todo or per-proposal identity, idempotency keys, append-only events,
public/private boundary summaries, and compact status projections. They should
not share delivery permission. A planning proposal can say "this todo should
move up", "this stale lane needs a split", or "this blocker should be asked";
it cannot silently mutate active truth, claim delivery work, read gated
material, or spend delivery quota.

Promotion is the critical transition:

```text
planning proposal
  -> operator/controller decision or policy-approved controller action
  -> normal user/agent todo or gate
  -> quota / lease / boundary checked delivery turn
```

This keeps server-side dreaming and periodic replanning useful without turning
the server into a hidden autonomous agent. The server owns durable scheduling
facts and proposal records; the client and executor still perform the visible
human-in-the-loop transition and bounded delivery work.

### Management Projections And Summaries

Loop Agent management adds a second projection need on top of ordinary status.
The server should keep kernel state explicit, but expose compressed read models
for clients:

- **mental-model projection**: maps goal state, gates, todos, claims, scope,
  evidence, run history, quota, and handoff into the five user concepts:
  Goal, Next step, Needs your judgment, Evidence, and Can continue.
- **performance-review projection**: rolls a lane or anchor into quantity,
  quality, token cost, user-attention cost, latest evidence, and next
  expectation.
- **review-feed projection**: turns recent outputs, gates, blockers, and
  signals into cards that the user can mark useful, not useful, needs evidence,
  off-scope, or too expensive.

These projections should be deterministic from recorded state first. A
model-backed summarizer can help produce friendlier wording, cluster duplicate
signals, or draft a review summary, but it must be default-off for control
purposes. Its output is advisory until promoted through a typed review,
feedback, todo, or gate transition. It cannot approve gates, mutate active
truth, hide missing evidence, or spend quota.

## Multica Reference Point

Multica is a useful reference implementation for this product split, but Goal
Harness should borrow the shape rather than the full product category.

Public Multica docs describe a stack with a Next.js frontend, a Go backend
using Chi / sqlc / WebSocket, PostgreSQL 17 with pgvector, and a local agent
daemon that runs coding CLIs. Its CLI/daemon guide makes the daemon the local
runtime: it detects installed agent CLIs, registers runtimes with the server,
polls for claimed tasks, creates isolated workspaces, starts the agent CLI,
streams results back, and sends heartbeats.

The LoopX takeaway:

- **Database first**: durable coordination facts should live in a real state
  store or a file-backed equivalent before they are projected into UI, prompts,
  or handoff packets.
- **Backend as control API**: server code should enforce schemas,
  idempotency, leases, boundaries, quota, and projection contracts.
- **Daemon / executor outside the state store**: agent execution belongs in a
  local daemon, Codex/App loop, terminal agent, or benchmark runner. The server
  schedules and observes; it does not become the model runtime.
- **Event stream plus projections**: issue/task status, comments, blockers,
  heartbeats, claims, and results should be appendable facts that can produce
  first-screen cards, review packets, and automation prompts.
- **Vector memory is optional**: pgvector is useful when a product wants skill
  or memory retrieval. LoopX should not require vector storage for v0
  control-plane correctness; relational/event facts come first.

So "server" in LoopX should usually mean:

```text
durable state store
  + event ledger
  + typed write API
  + projection API
  + scheduler / quota decisions
```

not:

```text
agent runtime
  + hidden planner
  + autonomous executor
```

### Client

The client is the maintainer's agent-facing proxy. It turns human intent into
governed control-plane transitions and turns raw agent activity back into an
operator-readable surface.

The client can be a CLI, dashboard, Lark document workflow, browser UI, or host
adapter. The important product responsibility is the same:

- explain what the goal is trying to accomplish now;
- show the signal inbox and selected high-value anchors;
- show what happened, what is blocked, and what will happen next;
- show whether a Loop Agent is earning value, respecting control, and staying
  cost-aware;
- collect user judgment, taste, approval, rejection, deferral, or reward;
- translate that input into gates, preferences, todo changes, or handoffs;
- route executor loops toward the current state without embedding stale policy;
- make side-agent ownership and review expectations visible.

This is why the client is more than intent classification. It is a product
surface for long-running work: it carries context, permission, feedback,
visibility, and trust.

Issue / PR solver pilots should therefore appear first as anchor-management
flows, not as a separate issue-fix product. The client can show: why this issue
or PR is worth acting on, who owns implementation, what action is allowed, what
evidence will be accepted, and whether the outcome can graduate into public
showcase material.

### Executor Loop

The executor loop is Codex, Claude Code, Cursor, a terminal agent, a benchmark
runner, or another bounded worker. It does the work, but it should not be the
long-term source of truth.

An executor loop should:

- read the current goal state and quota decision before work;
- respect user gates, public/private boundaries, and claimed todo ownership;
- keep one turn bounded to the selected todo or safe side path;
- write back evidence, validation, blockers, and next-step proposals;
- stop before sensitive material, destructive git, private material, production
  actions, or unapproved publication boundaries.

The executor can be powerful without being the product authority. LoopX
keeps the authority in the shared state that the user, primary agent, and side
agents can all inspect.

## Interaction Loop

The product loop is:

```text
user
  -> client
  -> LoopX server/state
  -> executor loop
  -> LoopX server/state
  -> client
  -> user
```

The client should not bypass the server by turning every user sentence directly
into an agent instruction. The executor should not bypass the client by hiding
important decisions in chat or local memory. LoopX exists so user
judgment, agent work, evidence, and future planning remain visible in the same
control plane.

## Decoupled Display And Control

The intelligent display surface can be adopted before the full LoopX control
loop. This separation matters for early users and partner teams.

In **display-only mode**, the server or local state store can ingest agent work
products and review signals without owning the executor's next action:

```text
external agent artifacts
  -> signal / evidence ingestion
  -> review_event_v0
  -> performance_review_v0
  -> maintainer dashboard
```

This mode quantifies value but does not steer execution. It is appropriate for
existing Codex, Claude Code, OpenViking-style solver, office-operations, or
internal agent workflows where the user first wants to inspect and score work.

In **LoopX control mode**, accepted review output becomes governed state:

```text
performance_review_v0
  -> gate / todo / anchor / reward / preference writeback
  -> quota and boundary checked LoopX work
  -> new evidence
  -> next review event
```

Both modes should live in one product system and preferably one repository for
now. The code boundary should still be explicit: the display app may run
read-only, while writeback paths must call LoopX schemas, gates, quota, and
boundary checks. This lets frontend collaborators build a polished surface
without accidentally creating a second source of truth.

## Capability Boundaries

LoopX should not become:

- an agent runtime that owns model execution, tools, billing, or permissions;
- a generic workflow engine where every step is a hidden automation edge;
- a raw transcript store for private chat, logs, benchmark traces, or local
  evidence;
- a crawler, publisher, or production-action authority;
- a replacement for project-specific adapters, evaluators, or domain tools.

It should provide the governed projection around those systems: goal state,
gates, todos, claims or leases, quota, evidence summaries, run history,
feedback, planning proposals, and handoff packets.

## First Contract Slices

The first product slices should remain small and compatible with CLI-only mode.

1. **`goal_channel_projection_v0`**: a read-only first-screen projection for
   goal, gate, todos, current blocker, latest evidence, quota, and next action.
2. **`mental_model_projection_v0`**: a user-facing compression layer that maps
   kernel state into Goal, Next step, Needs your judgment, Evidence, and Can
   continue. Clients should render this before exposing raw claim, scope,
   quota, run-history, or handoff details.
3. **`agent_profile_v0`**: registered agent identity with role, primary/side
   relationship, default scope, worktree policy, and review handoff policy.
4. **`task_lease_v0`**: per-`(goal_id, todo_id)` ownership with TTL,
   idempotency key, write scope, renewal, transfer, and conflict behavior.
5. **`planning_queue_v0`**: advisory planning, dreaming, and replanning
   proposals that remain non-executable until promoted by controller or user
   decision plus normal quota and boundary checks. The minimal record should
   include proposal id, source run window, due/retry policy, candidate todo
   refs, confidence, promotion target, and idempotency key.
6. **`feedback_signal_v0`**: user feedback captured as one of four control
   effects: gate decision, preference hint, todo mutation, or product
   improvement note. Raw private chat should not become public evidence.
7. **`performance_review_projection_v0`**: lane or anchor rollup over a bounded
   window with output quantity, quality label, token or quota cost, user
   attention cost, evidence references, and next expectation. It should cite
   source events instead of copying raw work context.
8. **`review_feed_card_v0`**: card-level projection for outputs, blockers,
   signals, or proposed todos that can receive user feedback and later produce
   `feedback_signal_v0`, `todo_update`, `anchor_update`, or
   `performance_review_note`.
9. **`anchor_candidate_v0`**: selected external signals that may become work.
   The minimal record should include source kind, public/private boundary,
   reason to care, allowed action, owner split, stop condition, expected
   evidence, and showcase-consent status.
10. **`project_level_reward_v0`**: aggregate value estimate for long-running
   agent work across a project. It combines quantity, human-scored quality,
   token spend, and user-attention spend so benchmark evidence can be compared
   with maintainer value without reducing everything to a single task score.
11. **`advisory_summary_v0`**: optional model-backed summary of recent state,
   used only for wording or clustering. It is default-off for control and cannot
   mutate state unless converted into a typed object above.
12. **`handoff_packet_v0`**: compact executor input that carries the selected
   todo, stop condition, validation expectation, boundary notes, and writeback
   target without copying the whole project history.

Each slice should have a CLI fallback, a compact status projection, and one
public/private boundary check before it becomes part of a richer UI.

## Roadmap Implication

This product shape changes the center of gravity from "a CLI around a Markdown
goal file" to "a dynamic goal control plane with CLI as the first client."

That does not make the CLI obsolete. The CLI is the compatibility baseline and
the safety fallback. It also keeps contracts honest: if a future server or
dashboard cannot fall back to equivalent CLI reads and writes, it is probably
creating a second source of truth.

The near-term roadmap should therefore prefer:

- contract-first status and write APIs over UI-only state;
- mental-model projections before frontend-only remapping;
- local concurrency correctness before broad server scheduling;
- side-agent scope and worktree policy before autonomous multi-agent merging;
- planning proposals before background execution;
- user feedback and performance-review modeling before personalization claims;
- anchor selection before domain-specific solver UIs.

The product promise stays the same across these layers: make the human decision
explicit, keep safe side work moving when it is independent, and make every
agent loop leave enough evidence for the next loop to recover the plot.

## References

- Multica README architecture section:
  <https://github.com/multica-ai/multica#architecture>
- Multica CLI and Agent Daemon Guide:
  <https://github.com/multica-ai/multica/blob/main/CLI_AND_DAEMON.md>
