# active_state_structured_projection_v0

`active_state_structured_projection_v0` is a read model for
`ACTIVE_GOAL_STATE.md`. It keeps Markdown as the human/agent workbench while
exposing typed todo, gate, next-action, and migration diagnostics for status,
quota, review packets, dashboards, and future event-store migration.

This is not a new canonical store. The projection is recomputable from the
current active-state Markdown and does not grant write permission.

The machine-owned Todo read subset is versioned separately in
`coordination_state_contract_v0.json`. That provider-neutral contract is shared
by Python and TypeScript. It declares the legacy consumer record and a separate
native domain record for file, NoKV, or PostgreSQL authority heads.
`archive_state` is durable task state: archival changes handoff and succession
eligibility independently of completion. `source_section` and optional `index`
belong to the Markdown compatibility projection, not native creation inputs.
Legacy v0 records retain those fields; importing them into the domain version
requires explicit qualification, including preservation of priority tie ordering
currently influenced by `index`. There is no automatic stored-head migration.
Provider-bound projection rejects an unknown
field instead of silently dropping it. Removing a declared field requires a
reviewed compatibility decision and maintainer approval, including for fields
that are persisted but not yet used by a decision path.

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
- `priority`, `title`, `task_class`, `action_kind`, `continuation_policy`;
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

## Markdown Ownership Boundary

Markdown is not one undifferentiated database row. Agents generate and maintain
both its structured sections and narrative through LoopX. The distinction is
canonical ownership, not human versus Agent authorship: after promotion,
sections covered by the versioned coordination contract are regenerated from
that authority. Content outside that contract must remain intact until its own
canonical source can reconstruct it.

The cutover is deliberately section-sized, not document-sized:

- before promotion, Markdown remains the authority and existing writers are
  unchanged;
- after promotion, the versioned Todo records live in the canonical provider
  head and Markdown's Todo section is a compatibility/workbench projection;
- other generated sections remain in Markdown until their canonical ownership
  migrates; Todo promotion does not silently discard or reinterpret them;
- a provider outage after promotion fails closed and never makes stale
  Markdown authoritative again.

The first write using this boundary is Todo claim. It exercises a complete
provider-neutral TypeScript transaction while leaving the default local path
unchanged. On promoted `hard_lease` authority, the same claim command may
supply a task-lease idempotency key and optional expected version so the claim,
canonical lease, and durable receipt commit in one provider transaction; the
write scopes come from the canonical Todo rather than caller input. After
promotion, `loopx todo project-markdown` can explicitly
regenerate active and archived Todo sections from the exact provider revision. It
never runs before promotion and never turns Markdown back into authority.

The projection command has four safety properties:

- it replaces only the machine-owned active user, agent and archived Todo regions;
- it preserves every segment outside those spans byte-for-byte;
- it fails closed when a canonical field cannot be represented by the current
  Markdown metadata grammar, rather than dropping that field;
- it parses the rendered sections back and requires deterministic parity and
  idempotent second rendering before an `--execute` write.

The writer imports the legacy LoopX-generated H2/list/metadata layout. It stops
at the first non-generated line, rather than extending replacement to the next
H2 or EOF; following H1, Setext, indented headings and ordinary narrative remain
outside its ownership. Code fences and multiline comments are not Todo headers.
The projection then emits paired `loopx:todo-region-v0` begin/end markers under
each Todo heading. The renderer, active Todo reader and section editor share
that boundary contract. Future projections use those explicit bounds; orphan,
nested, mismatched or missing markers, and non-generated content inside a marked
region, fail closed. No ordinary Goal is rewritten or opted in by installation.
Legacy unmarked readers and bootstrap output remain unchanged.

Non-Todo byte preservation and canonical Todo parse/render parity are separate
checks: the former compares untouched source slices, while the latter reads only
the generated regions. Neither marker is provider authority or a current-head
freshness guarantee.

Each section includes a compact `loopx:todo-section-projection-v0` marker with
the canonical provider revision and a SHA-256 digest of the complete canonical
records for that role. The marker is lineage evidence, not a write API.
The command proves that the rendered records came from the exact provider head
observed at read time. It does not claim that the revision remains the current
head after that read; a later canonical mutation makes the Markdown projection
stale until the journal-backed delivery replays. Consumers must always read the
provider, never the Markdown marker, when they need current authority state.

Rollback is intentionally asymmetric. Before promotion, the existing shadow
rollback quarantines the candidate provider lineage and Markdown remains
canonical. After promotion, a provider outage or revision mismatch fails
closed; operators may restore a reviewed provider snapshot and regenerate the
Todo sections, but must not promote stale Markdown back to canonical truth.

## Migration Path

The projector accepts complete legacy records and native `TodoDomainRecord`
manifests. Native records receive display-only section/index provenance; that
provenance never enters the canonical record. Archived records render in a
machine-owned `Completed Work Archive` region (created when needed) and retain
their original `role`. Unknown canonical fields and unsafe region ownership
continue to fail closed.

For promoted provider-first Todo create, claim, and narrow text/note update,
the committed authority journal is the transaction-bound projection outbox:
the canonical mutation, complete head, cursor, revision, and receipt land in
one provider transaction. After that commit, the Python compatibility adapter
renders the latest head under the Markdown lock and durably reads it back. A
renderer/write failure leaves typed `pending` delivery
evidence without reversing or hiding the canonical commit. A later successful
mutation or `todo project-markdown --execute` replays the current head
idempotently. This is projection recovery, not a second authority path.

### Generated display recovery / 生成式展示恢复

LoopX state documents are generated and maintained by Agents through LoopX.
There is no separate hand-written-document workflow or recovery approval gate.
After promotion, a missing Markdown target is automatically regenerated during
normal projection delivery. The existing command is also sufficient:

```bash
loopx --format json todo list --goal-id <goal-id>
# Use provider_revision from that read; omitting --execute previews only.
loopx todo project-markdown --goal-id <goal-id> --provider-revision <revision>
loopx todo project-markdown --goal-id <goal-id> --provider-revision <revision> --execute
```

The generated document states its recovery scope. The current coordination
provider contains Todo and lease state, not every Objective, operating contract,
vision, Next Action or progress-ledger section. A missing-file rebuild therefore
reports `recovery_scope=todo_sections_only` and `narrative_preserved=false`;
it is not a complete Goal-state restore. Existing non-Todo content is preserved
regardless of who generated it. Those remaining state families must converge
on their own canonical sources before whole-document reconstruction can be
claimed; do not introduce a second Markdown authority or fill gaps from prose.

Publication uses the existing source lock and source-ownership checks. New files
are private (`0600` on POSIX) and published atomically without replacing a file
concurrently restored by another writer. Existing malformed or non-UTF-8 files
remain untouched and delivery stays pending. A stale requested revision or
unavailable canonical provider cannot rebuild the target. Normal reads never
write it. Recovery does not rerun the business transaction or validation command;
private validation declarations must still match the canonical digest.

缺失的展示文件由投影交付自动重建，不增加手写文档假设、人工确认或额外开关；原有
`project-markdown` 仍默认预览。当前只恢复 canonical Todo 的活动与归档区域，并明确
报告 `todo_sections_only`，不冒充完整 Goal 状态恢复。已有的非 Todo 内容无论由谁生成
都保持原样；其权威源归一化是后续状态迁移，不是人工补文档流程。损坏文件不静默覆盖，
revision 不匹配或 provider 不可用时不重建；交付失败只重试投影，不重复业务事务。

1. Emit this projection from active-state Markdown.
2. Add parity smokes comparing it with existing status todo summaries.
3. Move Markdown parsing into a dedicated active-state read-model module behind
   the same projection fields.
4. Promote one complete provider-backed mutation at a time behind the durable
   writer fence; keep the default Markdown mode unchanged.
5. Regenerate only machine-owned active/archive sections from one exact
   canonical provider revision, preserving human narrative and validating
   parse/render parity.
6. Extend the same journal-backed delivery contract to each remaining native
   Todo mutation before claiming full promotion coverage.
7. Promote a provider projection only after rollback and idempotency checks are
   in place.
