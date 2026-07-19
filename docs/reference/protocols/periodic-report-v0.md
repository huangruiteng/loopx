# Provider-neutral periodic report v0

`periodic_report_v0` is the LoopX control contract for one bounded report run.
It binds a period window and a profile to typed source snapshots, one rendered
artifact receipt, archive and delivery receipts, deterministic idempotency,
explicit partial/unknown states, and a bounded retry projection.

The capability also defines `periodic_report_trigger_decision_v0`. A caller
evaluates compact LoopX or provider facts before collecting or delivering a
report:

```bash
loopx periodic-report evaluate-trigger \
  --request-json periodic-report-trigger-request.json \
  --format json
```

```bash
loopx periodic-report compose-run \
  --request-json periodic-report-request.json \
  --format json
```

The command is local and effect-free. Source collection, rendering, archive
writes, message delivery, and receipt readback all execute in adapters or
connectors outside this core.

## Trigger decision

A `periodic_report_trigger_request_v0` binds a profile and trigger policy to an
evaluation timestamp, optional last-report receipt, and up to 64 compact
candidate facts. The built-in kinds are:

- `cadence_due`: a profile-owned schedule says a report window is due;
- `vision_closed`: the vision transition is closed, acceptance is validated,
  and a successor is established or the goal is terminal;
- `primary_goal_outcome`: the primary delivery outcome is validated and has a
  durable writeback;
- `material_decision`: an approved, rejected, or cancelled decision changed
  the execution route and was durably recorded;
- `material_blocker`: a new or escalated P0 blocker stops the primary path;
- `material_recovery`: a validated resolution reopens the primary path;
- `manual`: an explicitly authorized run.

`surface_only`, `state_refreshed`, `todo_completed`, `monitor_unchanged`, and
`vision_checkpoint` are accepted only so the decision receipt can explain why
they were suppressed. They never trigger a report by themselves.

The decision sorts material candidates by urgency, coalesces concurrent facts,
and derives a stable `report_key`. Trigger identity is derived from kind,
source reference, and evidence digest; a last-report receipt suppresses ids it
already covered. A profile-owned minimum interval suppresses non-urgent
updates, while authorized manual runs, validated primary outcomes, validated
vision closures, and primary-path blockers may bypass it. The output records
the selected and coalesced ids, every suppression reason, cooldown state, and
the report kind (`cadence_digest`, `milestone_update`, `exception_update`, or
`manual_update`).

An eligible decision may be embedded as `trigger_receipt` in a
`periodic_report_run_request_v0`. Its `report_key` and `report_kind` then
participate in run identity, so a milestone update and a scheduled digest over
the same evidence window cannot collide.

## Request and identity

A `periodic_report_run_request_v0` contains:

- `generated_at` and an offset-aware `period_window.start_at` / `end_at`;
- a stable `profile_id`, `profile_version`, and optional opaque `profile_ref`;
- one or more `source_snapshots[]` with source identity, typed status, compact
  digest/reference/count evidence, and retryability;
- one `artifact_receipt` naming a renderer and artifact state;
- at least one `archive` and one `delivery` receipt;
- `retry_policy.attempt` and `max_attempts`.

It may also contain an eligible `periodic_report_trigger_decision_v0` receipt.

LoopX derives `run_id` and the run-level `idempotency_key` from the normalized
window, profile, source identities, renderer identity, and sink identities.
Snapshot contents and attempt number do not change that identity, so a retry
cannot create a second logical report. Callers may repeat the derived values;
stale or mismatched values fail closed.

Every sink receives a deterministic sink-specific idempotency key derived from
the run, sink role, and sink id. A `sent` receipt is valid only with an exact
key, a compact receipt reference, and verified readback.

## State and retry semantics

Source statuses are `complete`, `partial`, `failed`, or `unknown`. Artifact
statuses are `pending`, `rendered`, `failed`, or `unknown`. Sink statuses are
`pending`, `sent`, `failed`, `skipped`, or `unknown`.

The derived run state is one of:

- `pending`: rendering or a sink has not settled;
- `succeeded`: all sources are complete, the artifact is rendered, and every
  archive/delivery sink is sent with verified readback;
- `partial`: usable output exists but a source is partial, a sink was skipped,
  or at least one sink succeeded while another failed;
- `failed`: collection/rendering failed, or every required sink failed;
- `unknown`: a source, artifact, or sink postcondition cannot be determined.

Retry is allowed only for terminal non-success states, before `max_attempts`,
and only when at least one unsettled component explicitly declares itself
retryable. The output names those components and the exact next attempt.

## Ownership boundary

The core deliberately contains no project, pull request, issue, weekday,
timezone, chat, document, or provider policy. Those belong to reusable
adapters and project profiles:

- a project profile owns cadence, timezone, report sections, audience, and
  selection policy;
- source adapters collect and normalize domain evidence;
- renderers turn normalized evidence into artifacts;
- archive and delivery sinks perform gated writes and verify readback;
- project products may index historical artifacts without changing run
  identity or delivery truth.

The built-in presentation adapters include linear Markdown and a
self-contained `html_artifact_v0` renderer. The HTML renderer is a zero-build,
single-file projection with optional local interaction. Hosting or generating
a shareable URL remains a separate sink action with its own idempotency and
readback receipt; it is not renderer authority.

The core rejects raw content, messages, logs, transcripts, credentials, secret
fields, and private paths. Public packets retain only compact references and
digests.
