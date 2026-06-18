# Architecture

Goal Harness has seven layers.

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
goal-harness history/check
        |
        v
goal-harness status
        |
        v
quota-aware agent tick / heartbeat / future UI
```

The core repository intentionally avoids domain logic. A data experiment goal,
a note-maintenance goal, and a harness self-improvement goal should share the
same runtime and contract, but use different adapters.

Goal Harness should still absorb field-tested project-control mechanisms such
as authority registries, current-belief TODOs, managed external-source
manifests, experiment boards, validation surface maps, and gated handoff
packets. See [field-derived-patterns.md](field-derived-patterns.md).

Goal Harness should also expose a human-friendly frontstage without moving the
source of truth into chat. A goal can project as a channel, agents can project
as workspace members, and task ownership can project as explicit leases; the
registry, active state, run history, quota, gates, and lease events remain the
backstage ledger. See
[frontstage-channel-lease-roadmap.md](frontstage-channel-lease-roadmap.md).

Goal Harness should also grow a narrow host-integration surface. CLI commands
remain the compatibility baseline, but long-running agent hosts benefit when
the same state is available through hook/MCP/server adapters:

- hook activation should only route the host toward the current Goal Harness
  contract; it must not embed a second scheduler or stale project policy;
- MCP/server tools should expose lifecycle reads, todo/gate/lease writes, and
  compact status projections without requiring the host to parse Markdown;
- host adapters should isolate platform details while preserving the same
  registry, event-ledger, quota, public/private boundary, and lease semantics;
- task graphs should be optional projections over Goal Harness state, not a
  replacement for the event ledger or active goal truth.

This keeps Goal Harness portable across Codex, local CLI loops, dashboards, and
future agent hosts while avoiding a forked control plane per host.

## Local Server / Daemon Roadmap

The CLI remains the compatibility baseline. A future local server should be an
optional control-plane coordinator over the same registry, active state, run
history, quota, todo, and boundary contracts, not a replacement state machine.

The server path should land in layers:

1. **Writer correctness before a server**: make existing CLI writers safe under
   concurrency with per-goal locks, idempotency keys, and optimistic revision
   checks. `todo`, `refresh-state`, reward writeback, quota spend, and history
   append paths should fail closed on stale revision or overlapping write scope.
2. **Lease projection**: add `task_lease_v0` records for claimed todos,
   including owner, TTL, write scope, idempotency key, and conflict policy.
   Status and quota should expose active leases so Codex/App/CLI loops can
   avoid duplicate work without reading chat history.
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

## State Interaction Model

Goal Harness has four product actors:

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

## Controller / Sub-Agent Model

For Codex-style parallel work, Goal Harness treats the main goal run as a
controller run. The controller owns:

- the objective and active goal state,
- the decision to spawn sub-agents,
- write-scope assignment,
- merge or rejection of child results,
- final validation, public/private scan, and state writeback.

Sub-agents own bounded child work:

- read-only repo exploration,
- one implementation slice with a disjoint write scope,
- one validation or benchmark surface,
- one risk or boundary check.

Goal Harness does not replace the operating-system scheduler or Codex App
executor. It should, however, own the simple compute quota that those executors
read before running more work. Timer cadence is an execution mechanism, not the
product source of truth for project priority.

See [quota-allocation.md](quota-allocation.md).

See [codex-subagent-orchestration.md](codex-subagent-orchestration.md).

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
