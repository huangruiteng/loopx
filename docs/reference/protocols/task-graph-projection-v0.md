# task_graph_projection_v0

`task_graph_projection_v0` is an optional read-only graph view over existing
LoopX state. It helps agents and operators see dependency, gate,
validation, repair, and handoff relationships without creating a second task
store.

The source of truth remains:

- the append-only event ledger and compact run indexes;
- the active goal state and its todos;
- operator gates and user todos;
- leases or todo claims;
- quota and status projections;
- run-history evidence and blocker writebacks.

The projection may appear under `attention_queue.items[].task_graph_projection`
in `loopx --format json status`. Full
`loopx --format json review-packet --goal-id <goal-id>` output may
include the same object for operator review. The handoff-only review-packet
surface should stay compact and omit the graph unless a future interface budget
explicitly allows it.

## Shape

```json
{
  "schema_version": "task_graph_projection_v0",
  "mode": "read_only",
  "goal_id": "loopx-meta",
  "generated_at": "2026-06-21T12:00:00Z",
  "derived_from": {
    "source_of_truth": [
      "event_ledger",
      "active_goal_state",
      "todos",
      "gates",
      "leases",
      "run_history"
    ],
    "status_item_goal_id": "loopx-meta",
    "active_state_updated_at": "2026-06-21T11:55:00Z",
    "run_history_window": "compact_latest_runs"
  },
  "truth_contract": {
    "event_ledger_is_source_of_truth": true,
    "projection_is_writable": false,
    "write_api": false,
    "recompute_rule": "Recompute from status, active state, gates, leases, and run history after each lifecycle event."
  },
  "nodes": [],
  "edges": []
}
```

## Nodes

Each node must be compact and must point back to durable LoopX ids.
Allowed `kind` values are:

- `deliverable`: a todo-backed artifact or implementation step;
- `gate`: a user, owner, or operator decision point;
- `lease`: an active claim or worker ownership signal;
- `validation`: a smoke, check, CI result, or review proof;
- `repair`: a self-repair or blocker-recovery step;
- `handoff`: a transition from one agent or surface to another;
- `evidence`: a compact run-history evidence item.

Required node fields:

- `node_id`: stable inside this projection;
- `kind`;
- `title`;
- `state`: one of `open`, `ready`, `blocked`, `done`, `waiting`, or `unknown`;
- `refs`: compact references such as `todo_ids`, `gate_ids`, `lease_ids`,
  `run_ids`, or `review_packet_ids`.

Nodes must not copy raw task text, transcripts, logs, credentials, private file
paths, or large run artifacts. They should summarize only the relationship
needed for dispatch or review.

## Edges

Edges describe why one node affects another. Allowed `relation` values are:

- `depends_on`;
- `blocks`;
- `validates`;
- `repairs`;
- `hands_off_to`;
- `supersedes`.

Each edge must name `from_node_id`, `to_node_id`, `relation`, and a compact
public-safe `reason`. Edges may carry the same compact `refs` object as nodes.
An edge does not grant permission to run a command or mutate state.

## Write Boundary

`task_graph_projection_v0` has no write authority. It must never expose a graph
write command, browser write affordance, hidden scheduler, or alternate lease
store. State changes continue through existing LoopX lifecycle commands:

- `loopx todo ...`;
- `loopx operator-gate ...`;
- `loopx reward ...`;
- `loopx refresh-state ...`;
- `loopx quota spend-slot ...`;
- future server/MCP write APIs that preserve the same event-ledger semantics.

Consumers should treat the graph as stale after any lifecycle event until it is
recomputed from the current status and run-history window.

## Acceptance Checks

A valid public fixture or implementation must prove:

- `schema_version` is exactly `task_graph_projection_v0`;
- `mode` is `read_only`;
- `truth_contract.projection_is_writable=false`;
- `truth_contract.write_api=false`;
- every node id is unique;
- every edge endpoint references an existing node;
- every node and edge references existing LoopX ids rather than raw
  private material;
- no local absolute paths, credentials, raw transcripts, or raw logs are
  projected;
- status/review-packet consumers can safely ignore the field when absent.
