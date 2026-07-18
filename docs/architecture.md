# Architecture

LoopX has seven layers.

1. **Registry**: lists known goals, their repos, adapters, authority sources,
   status, and guards.
2. **Goal state**: the active state file for one goal.
3. **Adapter pre-tick**: a read-only project-specific probe.
4. **Run log**: JSON and Markdown reports saved per goal.
5. **Run history**: compact indexes consumed by agents, heartbeats, and UI.
6. **Status / attention queue**: first-screen summary of who needs to act next.
7. **Compute quota**: local policy for how much automatic agent compute each
   goal may consume.

```text
project goal state
  + private registry
  + project adapter
        |
        v
shared runtime root
        |
        v
loopx history/check
        |
        v
loopx status
        |
        v
quota-aware agent tick / heartbeat / future UI
```

The core repository intentionally avoids domain logic. A data experiment goal,
a note-maintenance goal, and a harness self-improvement goal should share the
same runtime and contract, but use different adapters.

## Current Dependency Budget

Dependency direction is enforced incrementally while large compatibility
facades are split. `loopx.control_plane` may not gain dependencies on
presentation, CLI, capability, or benchmark-adapter layers; the architecture
test keeps one explicit quota-Markdown migration edge as debt.

The legacy `loopx.status` facade currently has one additional outward edge, the
SkillsBench verifier-bootstrap attribution helper. This is migration debt, not
an extension point. The architecture test records its exact module target so a
new outward edge fails, and removing the edge requires deleting its stale
allowlist entry in the same change.

Each edge should move only after characterization parity exists. Adapter-specific
enrichment belongs behind application/plugin composition rather than in the
status core. Status Markdown callers now use the presentation renderer directly;
the former `loopx.status.render_status_markdown` wrapper was retired after parity
fixtures and repository callers migrated. The formerly SkillsBench-named solution
quality helper moved inward after characterization showed that it projects only
generic compact benchmark fields; its shipped schema remains compatible. Hiding
an adapter dependency inside a function or dynamic import does not count as
architectural separation.

Capabilities and extensions are also orthogonal: a capability is a product
contract, while an extension is an independently managed provider that may
offer one or more capabilities. The provider-aware registration and manifest
boundary is documented in [extensions.md](reference/extensions.md).

LoopX should still absorb field-tested project-control mechanisms such
as authority registries, current-belief TODOs, managed external-source
manifests, experiment boards, validation surface maps, and gated handoff
packets. See [field-derived-patterns.md](field-derived-patterns.md).

LoopX should also expose a human-friendly frontstage without moving the
source of truth into chat. A goal can project as a channel, agents can project
as workspace members, and task ownership can project as explicit leases; the
registry, active state, run history, quota, gates, and lease events remain the
backstage ledger. See
[frontstage-channel-lease-roadmap.md](frontstage-channel-lease-roadmap.md).

LoopX should also grow a narrow host-integration surface. CLI commands
remain the compatibility baseline, but long-running agent hosts benefit when
the same state is available through hook/MCP/server adapters:

- hook activation should only route the host toward the current LoopX
  contract; it must not embed a second scheduler or stale project policy;
- MCP/server tools should expose lifecycle reads, todo/gate/lease writes, and
  compact status projections without requiring the host to parse Markdown;
- host adapters should isolate platform details while preserving the same
  registry, event-ledger, quota, public/private boundary, and lease semantics;
- task graphs should be optional projections over LoopX state, not a
  replacement for the event ledger or active goal truth.

This keeps LoopX portable across Codex, local CLI loops, dashboards, and
future agent hosts while avoiding a forked control plane per host.
The v0 protocol contract is
[`host-integration-surface-v0`](reference/protocols/host-integration-surface-v0.md):
hook activation stays thin, lifecycle reads and todo/gate/lease writes map to
CLI-equivalent operations, compact status projections exclude raw/private
material, optional derived projections remain read-only, and CLI fallback
remains available when an adapter is absent.

## Lifetime Goal Invariant

LoopX should optimize for **lifetime goals**: durable intentions that
may outlive a single thread, executor, project phase, or plan. This is a
product invariant, not an eighth storage layer.

A lifetime goal must be stable enough that a future human or agent can recover
what the goal is, what currently defines it, who may change it, and what the
next safe transition is. It must also stay narrow enough that automation can
make one bounded, verifiable move instead of claiming open-ended authority.

The architecture maps that invariant onto the existing layers:

- the registry gives the lifetime goal a stable identity, repo boundary,
  adapter status, guards, and authority-source list;
- active goal state records the current belief, priority stack, non-goals, and
  next action without becoming a complete diary;
- authority sources replace implicit model memory with reviewable context and
  conflict rules;
- run history preserves the compact evidence trail across sessions and agents;
- todos turn the lifetime goal into bounded user and agent obligations;
- gates, reward, and quota keep human judgment, course correction, and compute
  spend attached to concrete transitions.

The result should preserve continuity without claiming open-ended autonomy: a
goal can live for years, but every agent turn still has to pass through current
authority, boundary, quota, validation, and writeback before it can count as
progress.

For session-runtime platforms that already own agent definitions, session
events, tool execution, permissions, billing, and product frontstage, Goal
Harness should integrate as the goal-level control projection rather than as a
second runtime. The read-only adapter path is: ingest compact session, event,
approval, outcome, and artifact summaries; produce `goal_state`,
`run_projection`, `operator_gate`, `human_reward`, `work_lane_contract`,
`quota_decision`, `handoff_packet`, and `dreaming_proposal` projections; then
let the product surface display those projections. See
[session-runtime-control-plane-adapter.md](session-runtime-control-plane-adapter.md).

## Local Server / Daemon Roadmap

The CLI remains the compatibility baseline. A future local server should be an
optional control-plane coordinator over the same registry, active state, run
history, quota, todo, and boundary contracts, not a replacement state machine.

In the current control plane, a **goal** is the stable `goal_id` boundary: one
registry entry, active-state file, quota lane, run-history stream, and status
projection. A **todo** is a structured active-state checkbox inside that goal,
addressed by `todo_id` and projected as an agent or user work item. There is no
separate issue object in the LoopX runtime model.

The server path should land in layers:

1. **Writer correctness before a server**: make existing CLI writers safe under
   concurrency with per-goal locks, idempotency keys, and optimistic revision
   checks. `todo`, `refresh-state`, reward writeback, quota spend, and history
   append paths should fail closed on stale revision or overlapping write scope.
2. **Lease adoption**: the optional local `task_lease_v0` CLI already provides
   owner, TTL, write scope, idempotency, conflict, transfer, and release
   semantics. Keep `claimed_by` as the default soft route and adopt hard leases
   only for hosts with a demonstrated concurrent-write problem.
   The pending/lease key should be per todo: `(goal_id, todo_id)` is the
   contention unit, not the whole goal or project. Different todos under the
   same goal may proceed in parallel when their write scopes and gates allow
   it; competing claims on the same todo fail closed or renew.
   Status currently exposes capability availability; quota does not enforce or
   consume hard leases. A later host integration may project active lease rows
   after its adoption contract and fallback behavior are validated.
3. **Loopback coordinator**: extend the existing local status server into a
   loopback-only coordinator that can centralize per-goal locks, leases, quota
   decisions, compact status projection, and heartbeat scheduling. It must bind
   locally, keep raw/private evidence out of compact responses, and preserve
   CLI fallbacks for every write.
4. **Heartbeat scheduler**: move recurring heartbeat bookkeeping behind the
   coordinator only after quota/spend idempotency is proven. Scheduler output
   should be the same `quota should-run` / `interaction_contract` /
   `protocol_action_packet` shape that current automation prompts already use.
5. **Planning and dreaming queues**: let background planning produce ranked
   todo proposals, evidence probes, and refactor warnings as advisory records.
   These queues must not execute protected work, read private material, or
   spend delivery quota without a later normal `quota should-run` decision and
   goal-boundary approval. The compact contract is
   `server_managed_planning_contract_v0`; see
   [dreaming-exploration-lane.md](dreaming-exploration-lane.md).
6. **Host adapters**: expose the same contracts through MCP, hooks, or a small
   local HTTP API for Codex-like hosts. Host adapters should route agents to
   current state and valid writes; they should not embed stale project policy or
   create a second scheduler.

Acceptance criteria for the first server-backed milestone:

- the same action can be completed through CLI-only mode after the daemon is
  stopped;
- a duplicate heartbeat, duplicate quota spend, or stale todo update becomes an
  explicit no-op or conflict, not a second delivery event;
- status shows the active lease and current owner without making the lease the
  source of project truth;
- all compact server responses pass the public/private boundary scan;
- tests cover one concurrent writer conflict and one daemon-down fallback.

Before the server-backed lease exists, LoopX keeps a lighter shared-control-plane
contract: todo metadata may include `claimed_by`, written by the todo CLI under
the active-state file lock. That field is a soft owner for visibility only, and
the CLI accepts it only when the id is registered in
`coordination.registered_agents`. Registered identities are peers. Work authority
comes from explicit claims, task leases, goal/write boundaries, and typed
continuation policy rather than a durable leader role. Any peer doing repository
work follows the same workspace-isolation rule when the selected task writes;
repository maintainer policy determines whether it may self-merge. A future
server lease should stay per todo and add TTL, idempotency keys, stale-claim
detection, overlap warnings, and compare-and-swap conflict responses.

## State Interaction Model

LoopX has four product actors:

- the **goal**, which owns durable objective, state, guards, run history, and
  reward overlays;
- the **Codex App executor**, which performs bounded transitions but should not
  be the long-term source of truth;
- the **user**, who supplies operator intent, approval, and high-quality reward
  signals;
- the **dashboard**, which visualizes derived status and should remain
  read-mostly unless an explicit local write boundary is enabled.

This actor model is the design gate for future commands and dashboard work. A
new capability should name the state it reads, the state it writes, the owner
of that write, and how the dashboard proves the transition happened.

See [state-interaction-model.md](state-interaction-model.md).

## Peer Task Coordination

For parallel work, every registered LoopX agent has equal identity authority.
Each peer owns only the work it has claimed or leased, within the current goal
boundary. A peer may:

- inspect or claim an eligible todo;
- advance one bounded implementation, validation, monitor, or repair slice;
- create an ordinary independent successor, optionally with executor exclusions;
- write back evidence for its own accepted task outcome.

When bounded orchestration is enabled, LoopX deterministically selects a
temporary coordinator for one task bundle. That coordinator may activate or
resume eligible peer lanes and aggregate accepted bundle evidence. It does not
become a durable leader and gains no implicit review, merge, publication, or
replan authority over other identities.

LoopX does not replace the operating-system scheduler or Codex App
executor. It should, however, own the simple compute quota that those executors
read before running more work. Timer cadence is an execution mechanism, not the
product source of truth for project priority.

See [quota-allocation.md](quota-allocation.md).

See [peer-agent-runtime-v1.md](reference/protocols/peer-agent-runtime-v1.md).

## Status / Attention Queue

The status layer derives a compact queue from registry, run history, and
contract health. It should be the first thing a controller or future UI reads:

- contract failures block adapter work,
- goals waiting on user/controller opt-in are surfaced explicitly,
- goals ready for Codex work are separated from external evidence watches,
- already-connected read-only goals with valid runs do not keep demanding
  redundant review.

See [attention-queue.md](attention-queue.md).

The JSON export is the boundary for dashboards, heartbeat summaries, and future
UI work. See [status-data-contract.md](status-data-contract.md). The product
dashboard frontend should follow
[dashboard-frontend-selection.md](dashboard-frontend-selection.md); the
single-file HTML renderer remains a fallback for smoke tests and offline
inspection.
