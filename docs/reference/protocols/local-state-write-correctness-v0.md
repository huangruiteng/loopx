# Local State Write Correctness v0

Status: public-safe protocol draft for LoopX local state writes.

LoopX still keeps Markdown active state as the human and agent work surface.
This contract defines the correctness envelope for any write that changes that
local state or a derived local control-plane artifact. It is not a new storage
backend. It is the common packet shape that lets future implementations add
stronger locks, idempotent retries, optimistic revision checks, and lease
projection without changing each writer independently.

## Scope

This protocol applies to local LoopX writes such as:

- active-state todo add, update, complete, supersede, and archive operations;
- `refresh-state` writes that update route, progress, or next action;
- event-store append operations that later project into active state;
- review packet or dashboard writeback that records compact local evidence.

It does not grant permission to read private material, publish externally, run
production actions, bypass human gates, or mutate a remote service. Those remain
separate boundary decisions.

## Correctness Model

Every local write should be describable as one `write_intent`:

| Field | Meaning |
| --- | --- |
| `write_id` | Stable id for this requested logical write. |
| `goal_id` | The goal boundary. A writer must not lock or revise unrelated goals. |
| `writer_id` | Registered agent, CLI command, or adapter issuing the write. |
| `write_class` | Compact operation family such as `todo_update`, `refresh_state`, or `event_append`. |
| `target_refs` | Goal-local refs such as `todo_id`, `run_id`, or `state_file`. |
| `idempotency_key` | Deterministic retry key. Replaying the same key must not duplicate the logical effect. |
| `expected_revision` | Optional optimistic revision/CAS token read before the write. |
| `lease_ref` | Optional per-todo or per-goal lease that explains why the writer may proceed. |

The lock boundary is per goal by default. A narrower per-todo lock is allowed
when the write touches only one todo and the writer can prove that no section
ordering, archive compaction, or shared summary update is affected.

## Required Phases

1. `prepare`: resolve `goal_id`, target refs, current revision, and boundary
   policy. No write happens here.
2. `preview`: produce a compact patch summary and safety result.
3. `apply`: acquire the lock, re-read the revision, reject or merge on mismatch,
   then write atomically.
4. `record`: emit compact evidence with applied/skipped/rejected/failed status.
5. `project`: expose the latest revision, lock boundary, and relevant lease
   state in status/review packets without copying raw private state.

## Conflict Semantics

- Same `idempotency_key` and same intended effect: return `skipped_duplicate`
  or `already_applied`.
- Same target but different idempotency key while lock is held: wait or return
  `lock_busy`.
- `expected_revision` mismatch: fail closed with `revision_conflict`, unless
  the writer can recompute a non-overlapping patch from the fresh revision.
- Lease expired or held by a different writer: fail closed with
  `lease_conflict`; do not silently clear another agent's claim.
- Unsafe payload: reject with `boundary_rejected` and write no local state.
- Dry-run preview without mutation: return `preview_only` and include the same
  write intent, lock boundary, revision, and expected write scopes that a real
  apply would need.

## Example Packet

```json
{
  "schema_version": "local_state_write_correctness_v0",
  "write_intent": {
    "write_id": "write_todo_123_complete_001",
    "goal_id": "loopx-meta",
    "writer_id": "codex-product-capability",
    "write_class": "todo_update",
    "target_refs": {
      "todo_id": "todo_123",
      "state_file_ref": "registry.goal.state_file"
    },
    "idempotency_key": "loopx-meta:todo_123:complete:write_todo_123_complete_001",
    "expected_revision": {
      "kind": "active_state_revision",
      "value": "sha256:before-write"
    },
    "lease_ref": {
      "kind": "todo_claim",
      "goal_id": "loopx-meta",
      "todo_id": "todo_123",
      "claimed_by": "codex-product-capability",
      "lease_id": "lease_todo_123_codex_product_capability"
    }
  },
  "lock_boundary": {
    "kind": "per_goal",
    "lock_key": "goal:loopx-meta",
    "narrower_lock_allowed": "per_todo_when_patch_is_single_todo_and_order_independent"
  },
  "preview": {
    "mode": "dry_run",
    "patch_summary": "mark todo_123 done and attach compact evidence",
    "non_destructive": true,
    "expected_write_scopes": [
      "active_state"
    ]
  },
  "apply_result": {
    "status": "applied",
    "applied_revision": {
      "kind": "active_state_revision",
      "value": "sha256:after-write"
    },
    "duplicate_of": null,
    "conflict": null
  },
  "projection": {
    "status_surface": "todo_123 done",
    "lease_projection": {
      "todo_id": "todo_123",
      "claimed_by": "codex-product-capability",
      "lease_state": "released_after_done"
    },
    "public_boundary": {
      "raw_logs_copied": false,
      "private_paths_copied": false,
      "credentials_copied": false,
      "production_action_authorized": false
    }
  }
}
```

## Acceptance Checks

A local-state writer is compatible with this protocol when:

1. it can produce or internally derive a `write_intent` before mutation;
2. retries with the same `idempotency_key` cannot duplicate todos, evidence, or
   events;
3. lock scope is at most per goal unless the operation is proven single-todo and
   order-independent;
4. optimistic revision mismatch fails closed or recomputes from the fresh state;
5. lease projection never lets one agent silently steal another agent's claim;
6. public status/review packets expose compact revision and lease state without
   raw local files, private paths, credentials, raw logs, or raw transcripts;
7. every destructive or external effect remains behind a separate explicit gate.

## Runtime Promotion Gate

The current implementation target is preview-first. A follow-up patch that
changes real write behavior must carry a small promotion gate before it enforces
hard idempotency, revision checks, or lease conflicts on the canonical write
path. The gate is a public-safe fixture contract, not a permission grant.

```json
{
  "schema_version": "local_state_write_correctness_rollout_gate_v0",
  "writer_id": "loopx.todo",
  "write_class": "todo_update",
  "current_mode": "dry_run_preview",
  "promotion_target": "shadow_validate",
  "allowed_to_change_write_behavior": false,
  "required_evidence": {
    "dry_run_packet_smoke": "examples/control_plane/todo-write-correctness-smoke.py",
    "idempotency_key_stability": "same logical input produces the same idempotency_key",
    "expected_revision_fixture": "expected_revision is computed from the active state before mutation",
    "revision_conflict_fixture": "stale expected_revision returns revision_conflict before mutation",
    "lease_projection_fixture": "foreign or expired lease returns lease_conflict before mutation",
    "public_boundary_scan": "loopx check --scan-path <changed-public-paths>"
  },
  "exit_criteria": [
    "dry-run JSON and markdown projections stay stable",
    "duplicate retries cannot duplicate todos, evidence, events, or refresh runs",
    "revision and lease conflicts are observable without copying raw state",
    "status and review packets expose only compact public-safe write refs"
  ]
}
```

`allowed_to_change_write_behavior=false` means the patch may add fixtures,
projection, or shadow-validation scaffolding, but must not reject or rewrite a
previously accepted real write. A later enforcement patch may flip that field
only when the corresponding writer has the required conflict fixtures and its
rollback behavior is documented. This keeps the rollout small: first prove the
contract on one writer, then tighten behavior in a separate validated step.

## Rollout Notes

The first implementation step should be non-destructive: add protocol docs and
fixture smokes, then adapt one existing writer to emit or validate the compact
shape in dry-run. Only after parity is proven should LoopX tighten the runtime
write path with hard idempotency keys, optimistic revision/CAS, or per-goal
lock metadata.
