# active_state_structured_projection_v0

`active_state_structured_projection_v0` is a read model for
`ACTIVE_GOAL_STATE.md`. It keeps Markdown as the human/agent workbench while
exposing typed todo, gate, next-action, and migration diagnostics for status,
quota, review packets, dashboards, and future event-store migration.

This is not a new canonical store. The projection is recomputable from the
current active-state Markdown and does not grant write permission.

## Shape

```json
{
  "schema_version": "active_state_structured_projection_v0",
  "source": "markdown_active_state",
  "source_ref": "ACTIVE_GOAL_STATE.md",
  "goal_id": "optional-goal-id",
  "frontmatter": {
    "status": "active",
    "updated_at": "2026-06-28T00:00:00+08:00"
  },
  "next_action": {
    "count": 1,
    "first": "Run the next bounded validation slice.",
    "entries": ["Run the next bounded validation slice."]
  },
  "todos": {
    "user": {
      "total_count": 1,
      "open_count": 1,
      "done_count": 0,
      "implicit_todo_id_count": 0,
      "items": []
    },
    "agent": {
      "total_count": 1,
      "open_count": 1,
      "done_count": 0,
      "implicit_todo_id_count": 0,
      "items": []
    }
  },
  "diagnostics": {
    "schema_version": "active_state_projection_diagnostics_v0",
    "parseable": true,
    "migration_ready": true,
    "warning_count": 0,
    "error_count": 0,
    "warnings": [],
    "errors": []
  }
}
```

## Todo Items

Todo items use the existing `todo_item_v0` fields where possible:

- `todo_id`, `todo_id_source`, `role`, `status`, `done`;
- `priority`, `title`, `task_class`, `action_kind`;
- `claimed_by`, `blocks_agent`, `global_gate`, `unblocks_todo_id`;
- `resume_when`, `no_followup`;
- monitor metadata such as `target_key`, `cadence`, `next_due_at`, and
  `consecutive_no_change`;
- compact evidence fields such as `note`, `evidence`, `reason`,
  `completed_at`, and `updated_at`.

`todo_id_source=metadata` means the item carried explicit LoopX metadata.
`todo_id_source=generated` means the projection generated a stable compatibility
id from role, source section, index, and text. Generated ids are useful for
read compatibility but are not migration-ready.

## Diagnostics

Diagnostics are intentionally small and machine-readable:

| Diagnostic | Severity | Meaning |
| --- | --- | --- |
| `missing_frontmatter` | warning | Markdown lacks frontmatter such as status or updated time. |
| `missing_next_action` | warning | No `## Next Action` entries were projected. |
| `missing_todo_sections` | warning | No user or agent todo items were projected. |
| `implicit_todo_ids` | warning | Some todo ids were generated instead of explicit metadata ids. |
| `duplicate_todo_ids` | error | Multiple items use the same explicit or generated todo id. |

`migration_ready=true` requires at least one todo item, no errors, and no
implicit todo ids. A non-ready projection can still be useful for status and
operator displays; it should not be promoted as canonical event-store input.

## Reader Contract

Readers should treat this projection as:

- read-only;
- public-safe only after normal `loopx check` / boundary scanning;
- a compatibility layer over Markdown, not a replacement for todo/event write
  APIs;
- a bridge for parity tests before moving active-state parsing out of
  `status.py`.

Writers must continue to use LoopX commands such as `loopx todo`,
`loopx refresh-state`, `loopx operator-gate`, and future event append APIs.
Directly editing a projection is not a state transition.

## Migration Path

1. Emit this projection from active-state Markdown.
2. Add parity smokes comparing it with existing status todo summaries.
3. Move Markdown parsing into a dedicated active-state read-model module behind
   the same projection fields.
4. Add event-store dual-read parity.
5. Promote event projection only after rollback and idempotency checks are in
   place.
