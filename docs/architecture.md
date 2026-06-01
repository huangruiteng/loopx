# Architecture

Goal Harness has six layers.

1. **Registry**: lists known goals, their repos, adapters, status, and guards.
2. **Goal state**: the active state file for one goal.
3. **Adapter pre-tick**: a read-only project-specific probe.
4. **Run log**: JSON and Markdown reports saved per goal.
5. **Run history**: compact indexes consumed by agents, heartbeats, and UI.
6. **Status / attention queue**: first-screen summary of who needs to act next.

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
agent tick / heartbeat / future UI
```

The core repository intentionally avoids domain logic. A data experiment goal,
a note-maintenance goal, and a harness self-improvement goal should share the
same runtime and contract, but use different adapters.

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

Goal Harness does not execute a scheduler by itself. It records contracts,
claims, run history, and boundary checks so controller/sub-agent work remains
inspectable instead of becoming hidden background activity.

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
