# event_sourced_state_contract_v0

`event_sourced_state_contract_v0` defines how LoopX can keep
`ACTIVE_GOAL_STATE.md` as the human/agent workbench while moving canonical
todo and history truth to an append-only event stream.

This is a product/control-plane contract, not an implementation mandate for a
specific database. Implementations may store the stream as JSONL, SQLite rows,
or another local-first append-only format as long as replay, ordering,
privacy, and idempotency behave the same way.

## Role Split

`ACTIVE_GOAL_STATE.md` remains the human/agent workbench. It is the readable
surface where agents and users can inspect current goals, progress, todos,
gates, validation surfaces, and next action. It may keep private or
project-local context when the project has explicitly ignored local state.

Canonical todo/history truth belongs to the event stream:

- Markdown edits are not canonical state changes unless they are converted into
  events by a LoopX command or a migration/backfill tool.
- Markdown renderers are projections. They may be regenerated from events and
  may compact old detail for prompt and review budgets.
- During migration, the Markdown parser may remain a compatibility fallback,
  but the event projection should become the preferred source for status,
  quota, review packets, todo CLI reads, and dashboard exports.

## Canonical Event Stream

Each goal has an ordered event stream. Every event must include:

- `schema_version`: event schema version, starting with
  `loopx_state_event_v0`;
- `event_id`: stable unique id for idempotent append and audit;
- `goal_id`: owning goal id;
- `event_type`: one of the allowed lifecycle event types;
- `recorded_at`: producer timestamp in UTC or offset-aware ISO-8601;
- `append_sequence`: monotonic sequence assigned by the local event store;
- `producer`: compact source such as `loopx.todo`, `loopx.refresh_state`, or
  `agent.codex-product-capability`;
- `privacy`: `public_safe`, `local_private`, or `private_pointer`;
- `projection_version`: projection contract version expected by the writer;
- `refs`: compact ids for todo, gate, run, quota, PR, evidence, or parent
  events;
- `payload`: event-specific compact data.

`append_sequence` is the final same-priority tie-breaker. If a planner creates
multiple P0 todos, the planner emits `planner_order`, and the store preserves
that order through append sequence. UI and prompt projections sort by priority
first, then `planner_order` when present, then `append_sequence`.

## Event Types

First supported todo/history event types:

| Event type | Purpose |
| --- | --- |
| `todo_added` | Add a new todo with role, priority, title, metadata, and planner order. |
| `todo_claimed` | Record or renew ownership, lease, or `claimed_by`. |
| `todo_updated` | Update compact metadata that does not rewrite event history. |
| `todo_blocked` | Mark a todo blocked with a public-safe blocker reason and optional gate refs. |
| `todo_deferred` | Mark a todo deferred with resume conditions. |
| `todo_completed` | Close a todo with validation/evidence refs and completion rationale. |
| `gate_added` | Add a user, owner, operator, or controller gate. |
| `gate_resolved` | Record approve, reject, or defer for a specific gate. |
| `run_recorded` | Attach compact run-history status, classification, and delivery outcome. |
| `refresh_recorded` | Record a state-only or progress refresh summary. |
| `quota_spent` | Record accounting for automatic compute spend. |
| `evidence_attached` | Attach compact public-safe evidence refs to a todo, gate, or run. |
| `projection_rendered` | Record a generated Markdown/status/dashboard projection checksum. |
| `snapshot_compacted` | Declare a derived snapshot checkpoint without replacing the underlying event lineage. |

Forbidden event styles:

- no event may mutate or delete a prior event;
- no event may embed raw chat transcripts, raw logs, credentials, or private
  source bodies in a public-safe stream;
- no projection may become a write API by accepting state that lacks a matching
  canonical event.

## Ordering And Idempotency

Replay order is:

1. `append_sequence`;
2. `recorded_at`;
3. `event_id` as a deterministic final tie-breaker.

Append is idempotent on `event_id`: re-appending the same event id with the
same normalized body is a no-op; re-appending it with a different body is a
conflict. Consumers should ignore duplicate identical events and fail closed on
conflicting duplicates.

Todo ids, gate ids, and evidence ids are stable references. Events may point to
parent events through `refs.parent_event_id`, but a child event must not rewrite
parent payload.

## Projection Rules

The event projection renders:

- current active todos grouped by role and priority;
- completed todo summaries and archive candidates;
- user and controller gate inboxes;
- run-history and refresh timeline summaries;
- quota spend summaries;
- review-packet evidence refs;
- Markdown-compatible `ACTIVE_GOAL_STATE.md` sections.

Projection outputs must carry:

- `schema_version`;
- `goal_id`;
- `generated_at`;
- `source_event_count`;
- `last_event_id`;
- `last_append_sequence`;
- `projection_version`;
- `source_checksum` or equivalent integrity marker.

A projection may be stale after any lifecycle event. Writers should append the
event first, then render projection output. Readers should prefer the latest
projection only when its `last_append_sequence` matches the event store head.

## Privacy Boundary

LoopX should support separate streams or partitioned records:

- `public_safe`: compact state that can be committed or shown in public docs;
- `local_private`: local state such as project-private active Markdown,
  private todo details, or local-only evidence notes;
- `private_pointer`: a compact pointer to private material without copying the
  material into public state.

`ACTIVE_GOAL_STATE.md` can carry private details when the project keeps it out
of git. Public docs, fixtures, dashboards, and PR packets must not copy those
details. Public projections should include only compact labels, ids, redacted
summaries, omission notes, and validation refs.

Tracked outputs require explicit redaction or compact pointers before
projecting information from private streams. A project-level LoopX config may
set defaults such as:

```json
{
  "state_privacy": {
    "active_state": "local_private",
    "public_projection": "public_safe",
    "allow_private_links_in_ignored_state": true,
    "require_redaction_for_tracked_outputs": true
  }
}
```

## Migration And Compatibility

The migration should be staged:

1. Define this contract and smoke-test replay/privacy invariants.
2. Add a minimal event store and projection API for todo/history events.
3. Dual-write `loopx todo`, `refresh-state`, quota spend, and gate commands.
4. Compare event projection against current Markdown parsing.
5. Prefer event projection for status, quota, review packets, dashboard, and
   slash-command help.
6. Keep Markdown rendering as the workbench and compatibility export.
7. Retire Markdown-as-canonical only after replay and idempotency checks are
   clean on real local goals.

Migration tools may backfill events from existing Markdown, but each backfilled
event should mark `producer=loopx.backfill` and include enough source refs to
explain provenance without copying private raw material into public streams.

## Acceptance Checks

A valid implementation or fixture must prove:

- Markdown remains a workbench/projection, not canonical todo/history truth;
- `todo_added`, `todo_claimed`, `todo_updated`, `todo_blocked`,
  `todo_deferred`, and `todo_completed` replay into a deterministic todo
  projection;
- same-priority todos preserve planner order and append order;
- duplicate identical `event_id` append is idempotent;
- duplicate conflicting `event_id` append fails closed;
- prior events are never mutated or deleted;
- projections expose `last_event_id`, `last_append_sequence`, and
  `projection_version`;
- public projections do not include local absolute paths, credentials, raw
  transcripts, raw logs, or private source bodies;
- ignored/private active state may reference private links, while tracked
  outputs require explicit redaction or compact pointers.
