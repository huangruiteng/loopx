# todo_detail_cold_path_v0

`todo_detail_cold_path_v0` is the cold-path detail contract for LoopX todos.
It lets dashboards, review tools, and agents inspect a complete todo without
expanding `status`, `quota should-run`, heartbeat prompts, or handoff packets
past their hot-path budgets.

The hot path remains `todo_summary_v0` plus bounded lanes such as
`first_open_items`, `executable_backlog_items`, and claim-aware lanes. Those
lanes answer the dispatch question: "which todo should the current actor look
at now?" They are not an archival todo store.

## Hot-Path Reference

Hot-path producers may attach only a compact reference when a consumer needs a
drill-down target:

```json
{
  "schema_version": "todo_detail_ref_v0",
  "goal_id": "loopx-meta",
  "role": "agent",
  "todo_id": "todo_1234abcd",
  "projection": "todo_detail_cold_path_v0",
  "page_size_hint": 20
}
```

The reference is optional. It must not copy notes, evidence bodies, raw logs,
private paths, verifier output, or full sibling todo lists. A missing reference
means the consumer can still route from the compact summary.

## Cold-Path Shape

A paged detail response should use this shape:

```json
{
  "schema_version": "todo_detail_cold_path_v0",
  "goal_id": "loopx-meta",
  "role": "agent",
  "todo_id": "todo_1234abcd",
  "generated_at": "2026-06-27T00:00:00Z",
  "source": {
    "kind": "active_state_todo",
    "state_updated_at": "2026-06-27T00:00:00Z"
  },
  "todo": {
    "schema_version": "todo_item_v0",
    "todo_id": "todo_1234abcd",
    "role": "agent",
    "status": "open",
    "priority": "P1",
    "title": "Design cold-path todo detail.",
    "task_class": "advancement_task",
    "action_kind": "todo_projection_pagination",
    "claimed_by": "codex-main-control"
  },
  "pages": {
    "current": {
      "kind": "todo_detail",
      "items": []
    },
    "next_page_token": null
  },
  "related": {
    "sibling_open_count": 12,
    "blocked_by_user_todo_ids": [],
    "unblocks_todo_ids": [],
    "successor_todo_ids": []
  },
  "truth_contract": {
    "source_of_truth": "active_goal_state_and_event_ledger",
    "projection_is_writable": false,
    "write_api": false,
    "refresh_rule": "Requery after any todo, gate, reward, refresh-state, or quota lifecycle event."
  }
}
```

## Paging Rules

- `todo` carries the canonical parsed todo item, not a markdown excerpt.
- `pages.current.items` may include compact public-safe detail records such as
  notes, evidence summaries, closeout summaries, and related lifecycle event
  references.
- Large note/evidence bodies must be summarized. Raw task text, transcripts,
  local file paths, credentials, private links, raw verifier output, and raw
  benchmark trajectories are not valid page items.
- `next_page_token` is opaque. Consumers must not parse it or infer ordering
  from it.
- Producers should make the first page sufficient for human inspection of one
  todo. Cross-todo list browsing belongs in filtered list endpoints or a
  dashboard view, not in one todo detail response.

## Ordering And Freshness

The detail response is a projection. It should preserve the active-state todo
ordering metadata (`index`, `source_section`, `priority`, and `role`) when
known, but it must not become a second writable ordering store. Consumers must
treat the detail as stale after any lifecycle event and requery before making a
new dispatch or merge decision.

## Acceptance Checks

A valid public fixture or implementation must prove:

- `schema_version` is exactly `todo_detail_cold_path_v0`;
- hot-path surfaces include at most `todo_detail_ref_v0`, never the full
  detail response;
- `truth_contract.projection_is_writable=false`;
- `truth_contract.write_api=false`;
- the response references exactly one `goal_id`, `role`, and `todo_id`;
- page tokens are opaque and optional;
- no local absolute paths, credentials, raw logs, raw transcripts, raw
  benchmark trajectories, or raw verifier output are projected;
- consumers can safely ignore both `todo_detail_ref_v0` and
  `todo_detail_cold_path_v0` when absent.
