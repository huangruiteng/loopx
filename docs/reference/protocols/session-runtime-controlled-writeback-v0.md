# Session Runtime Controlled Writeback v0

Status: public-safe protocol draft for external agent runtime metadata writes.

This contract defines the first writeback boundary after
`session_runtime_loopx_projection_v0` has proven read-only value. The goal is
not to make LoopX drive the runtime directly. The goal is to let an external
runtime carry compact LoopX decisions as metadata or event pointers, so a
visible session can recover, hand off, and explain why it is allowed to
continue.

## Entry Criteria

Controlled writeback is available only when all of these are true:

1. A read-only projection already exists and identifies `goal_id`, `agent_id`,
   `runtime_id`, `session_id`, and at least one LoopX `run_id` or `todo_id`.
2. The LoopX source event is already recorded through the CLI or a
   CLI-equivalent adapter.
3. The runtime target supports a dry-run or preview path.
4. The payload is compact metadata, not raw transcript, raw tool output, local
   path, credential, or private document body.
5. The adapter can report an applied, skipped, rejected, or failed result back
   to LoopX without guessing.

If any entry criterion is missing, the adapter must stay in read-only mode and
write a blocker or user todo through LoopX instead of attempting a host write.

## Write Classes

| LoopX Source | Runtime Target | Allowed Payload | Must Not Mean |
| --- | --- | --- | --- |
| `operator_gate` decision | approval-like runtime event or metadata | decision id, decision label, actor class, reason summary, source run id | Runtime permission override, hidden approval, production authorization |
| `human_reward` overlay | run-bound judgment metadata | reward id, judged run id, decision label, public-safe reason | Model score, benchmark score, or task pass/fail impersonation |
| `quota_decision` | scheduler hint metadata | eligible/throttled/monitor hint, window id, reason code | Billing decision, launch authority, or hidden session start |
| `handoff_packet` | session metadata pointer or message draft | handoff id, next action, stop condition, evidence pointers | Raw transcript copy, unbounded prompt injection, or forced same-session control |
| compact artifact/run pointer | runtime artifact annotation | artifact id, validation label, outcome class | Raw evidence upload, local path exposure, or private log mirror |

Writeback is deliberately narrower than the host integration surface. Todo
creation, gate recording, reward recording, refresh-state, and quota spend
still originate in LoopX. The runtime receives a compact reflection after
LoopX has recorded the authoritative event.

## Minimal Shape

```json
{
  "schema_version": "session_runtime_controlled_writeback_v0",
  "goal_id": "loopx-meta",
  "agent_id": "codex-side-bypass",
  "runtime": {
    "runtime_id": "codex_cli_tui",
    "session_id": "public-safe-session-handle"
  },
  "loopx_source": {
    "source_run_id": "run_123",
    "source_todo_id": "todo_123",
    "source_event_class": "handoff_packet"
  },
  "writeback": {
    "write_class": "handoff_packet_pointer",
    "mode": "dry_run",
    "idempotency_key": "loopx-meta:run_123:handoff_packet_pointer",
    "payload": {
      "decision_label": "approved_next_action",
      "summary": "continue the validated next action until the stop condition fires",
      "evidence_pointer_count": 2
    }
  },
  "boundary": {
    "raw_transcripts_copied": false,
    "raw_tool_outputs_copied": false,
    "credentials_copied": false,
    "private_paths_copied": false,
    "launch_authority_granted": false
  },
  "result": {
    "status": "previewed",
    "runtime_event_id": "evt_123",
    "loopx_writeback_run_id": null
  }
}
```

The dry-run result may be shown in a local control-plane UI. It is not a
runtime command to continue. A real apply must still be tied to the recorded
LoopX event and must report a compact result.

## Flow

1. Read the current LoopX projection and host session facts.
2. Verify the entry criteria and public/private boundary.
3. Build a dry-run payload with an `idempotency_key`.
4. Show or record the dry-run preview.
5. Apply only when the relevant LoopX event already exists and the runtime
   adapter exposes the matching write class.
6. Append a compact LoopX result run with `status=applied`, `skipped`,
   `rejected`, or `failed`.

An adapter may skip apply when the runtime already has the same
`idempotency_key`. It must still report the skip as a compact result so LoopX
can tell the difference between "already reflected" and "never attempted."

## Failure Semantics

Controlled writeback fails closed:

- Missing read-only projection: stay read-only and request projection first.
- Missing LoopX source event: record the LoopX event first.
- Missing runtime dry-run support: block writeback and keep CLI as source of
  truth.
- Runtime target unavailable: record `failed` or `skipped`, not a user approval.
- Unsafe payload: reject the payload and create a public-safe blocker.

Runtime writeback failure does not invalidate the LoopX decision. It only means
the host did not receive the compact reflection yet.

## Acceptance Checks

A controlled writeback adapter is acceptable when:

1. every supported write class has a CLI-equivalent LoopX source event;
2. dry-run works before apply;
3. `idempotency_key` prevents duplicate runtime metadata;
4. the payload excludes raw transcripts, raw tool outputs, credentials, local
   paths, private document bodies, and production logs;
5. quota writeback is treated as a scheduler hint, never launch or billing
   authority;
6. human reward writeback is clearly distinct from benchmark/task scoring; and
7. failure returns a compact blocker or result event instead of guessing around
   gates.
