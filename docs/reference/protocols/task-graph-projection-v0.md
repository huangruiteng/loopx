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
in `loopx --format json status --include-task-graph`. Default status output
keeps this object on the cold path so the dashboard hot path remains within its
interface budget. Full
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
  "limits": {
    "user_gate_node_limit": 2,
    "user_gate_open_count": 5,
    "user_gate_truncated_count": 3
  },
  "nodes": [],
  "edges": []
}
```

`limits` explains hot-path truncation. The task graph may expand only the first
`user_gate_node_limit` open user gate nodes. When more user gates are open,
`user_gate_open_count` and `user_gate_truncated_count` must say so. Consumers
that need the complete gate list should use the user todo detail path or full
review packet fields instead of treating the graph as an exhaustive store.

## Nodes

Each node must be compact and must point back to durable LoopX ids.
Allowed `kind` values are:

- `deliverable`: a todo-backed artifact or implementation step;
- `gate`: a user, owner, or operator decision point;
- `gate_summary`: a compact "more gates exist" node used when user gates are
  truncated from the graph hot path;
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
  `goal_ids`, `run_ids`, or `review_packet_ids`.

Nodes must not copy raw task text, transcripts, logs, credentials, private file
paths, or large run artifacts. They should summarize only the relationship
needed for dispatch or review.

## Edges

Edges describe why one node affects another. Allowed `relation` values are:

- `depends_on`;
- `blocks`;
- `validates`;
- `repairs`;
- `audits`;
- `continues`;
- `hands_off_to`;
- `supersedes`.

Each edge must name `from_node_id`, `to_node_id`, `relation`, and a compact
public-safe `reason`. Edges may carry the same compact `refs` object as nodes.
An edge does not grant permission to run a command or mutate state.

`repairs`, `audits`, and `continues` are lineage relations, not lifecycle
commands. They are derived from existing run history, todo/gate metadata, and
compact blocker or validation writebacks:

- `repairs` says a repair or replan node is intended to recover a selected
  work lane.
- `audits` says compact run-history evidence reviews, checks, or bounds a
  selected work lane.
- `continues` says compact run-history evidence is a continuation of a selected
  work lane.

These relations may help a dashboard or reviewer explain why a work item is
still active, stale, repaired, or safe to hand off. They must not create a graph
resume command, mutate todo status, or replace freshness checks against current
quota, gates, claims, and run history.

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
- `limits.user_gate_node_limit` is present;
- `limits.user_gate_open_count` is present;
- `limits.user_gate_truncated_count` is present;
- every node id is unique;
- every edge endpoint references an existing node;
- every node and edge references existing LoopX ids rather than raw
  private material;
- repair, audit, and continuation relations are rendered only as derived
  read-only lineage over existing todos, gates, leases, and compact run ids;
- no local absolute paths, credentials, raw transcripts, or raw logs are
  projected;
- status/review-packet consumers can safely ignore the field when absent.
