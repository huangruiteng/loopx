# Provider-neutral periodic report v0

## Product activation

An explicit request in an active project session, such as "generate this
week's project report", is sufficient authority for one provider-free local
generation. LoopX resolves the built-in `weekly-progress` profile (aliases
`weekly` and `weekly-report`), whose normalized `periodic_report_profile_v0`
sets `enabled: true`, binds `project_progress_v0`, Markdown, and HTML, and
declares neither a schedule nor a sink. The profile can be inspected without
effects:

```bash
loopx periodic-report inspect-profile --preset weekly --format json
```

This does not persist project activation, create a scheduler, or grant an
external write. The current session owns the requested calendar window. When
the built-in preset is selected, the activation packet includes an
`interaction_contract` that makes those session-generation defaults explicit;
the generic heartbeat prompt does not need a report-specific expansion.

A project-owned `periodic_report_profile_v0` is the advanced opt-in contract
for custom or unattended operation. Enabled custom profiles declare:

- provider-neutral trigger policy and an optional host-owned RRULE/timezone;
- one or more domain source adapter bindings;
- one or more renderer bindings;
- zero or more required, optional, or disabled extension sink bindings.

Use a host Automation only when the report must run unattended on an RRULE.
The Automation schedule and project profile must agree; ordinary in-session
generation does not need an Automation. External delivery still requires an
explicit sink binding and its independent runtime authority/readback checks.

`periodic_report_activation_v0` is the effect-free inspection receipt. It
records whether generation is allowed, the normalized profile digest, and the
portable/enhanced/durable extension mode. It performs no source read, schedule
mutation, provider lookup, rendering, archive write, or message delivery.

`periodic_report_project_progress_projection_v0` is the built-in,
domain-neutral source input. It groups typed project facts into progress,
capability evolution, risks, next actions, and supporting evidence, with no
more than eight primary audience items. Issue Fix has no special standing in
either schema. It may register a peer source adapter under the same contract as
release, research, operations, or another domain. OpenViking is likewise an
optional archive/query provider behind a sink extension; it does not own
trigger, selection, rendering, or delivery.

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

## Split phase contract

`periodic_report_v0` also exposes a split contract for profiles that must keep
local report generation independent from provider availability:

- `periodic_report_generation_bundle_v0` contains the normalized document,
  one to eight artifacts, and a deterministic
  `periodic_report_generation_receipt_v0`. The receipt declares that no
  provider or external write was required.
- `periodic_report_sink_binding_v0` pins a sink id, role, dependency policy,
  capability id/version, extension id/version, and provider-neutral
  `periodic_report_sink_v0` protocol.
- `periodic_report_extension_readiness_v0` verifies those bindings against
  observed provider receipts. It reports `portable`, `enhanced`, or `durable`
  delivery mode and never performs a provider call.
- `periodic_report_delivery_receipt_v0` binds provider sink results back to the
  generation and readiness receipts. A sent sink is accepted only with an
  idempotency key, compact receipt reference, and verified exact readback.

The dependency policy is `required`, `optional`, or `disabled`. Required sinks
block formal delivery when unavailable. Optional sinks degrade without
invalidating the generation receipt. Disabled sinks are skipped. Provider
versions, protocols, or capabilities that do not match the profile binding are
`incompatible`; providers without verified readiness are `unverified`.

The bundled `openviking-periodic-report` LoopX extension is one concrete
implementation of this port. Its runtime protocol is
`periodic_report_sink_v0`, its manifest permission and observed runtime
capability are both `openviking_context_write`, and its sink capability is
`report.archive.write/v0`. Runtime activation recomputes the normalized
`periodic_report_activation_v0`; a disabled or altered receipt, a missing or
disabled sink binding, a stale extension doctor proof, or a missing observed
runtime capability rejects the invocation before any provider write.

`openviking_periodic_report_archive_request_v0` carries the activation receipt,
normalized document, Markdown artifact, archive context, and an execution bit.
The provider writes two OpenViking Resources in commit order: `report.md`, then
`manifest.json`. The latter records
`openviking_periodic_report_archive_commit_v0`, the bundle digest, stable
result id, and `manifest_written_last=true`. A `sent` sink result requires an
exact content-digest readback of both URIs. HTML hosting, historical queries,
and memory distillation are separate consumers of the committed Resource and
are not part of this provider protocol.

The older run request below remains a compatibility full-delivery envelope. It
still requires archive and delivery receipts, while the split contract makes
the provider-free generation truth available before those receipts exist.

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
single-file projection with optional local interaction. Its default
`editorial_dense_v2` presentation keeps normalized primary item facts visible,
accepts profile-owned language and at most four first-screen highlights,
compiles its audience summary from typed primary items, and moves supporting
items, profile identity, source health,
generation metadata, and digests into a collapsed appendix. Items may declare
`visibility=primary|supporting`; `runtime` and `delivery_receipt` content kinds
must be supporting. The linear Markdown artifact preserves those items in a
labeled appendix so copy/export remains complete without interrupting the main
narrative. HTML embeds that Markdown rendering and records its companion
artifact digest. Audience items may also carry up to four ordered `details`
rows for readable fact grouping and optional `tag_labels` for localized display;
the canonical token tags remain unchanged.
Hosting or generating a shareable URL remains a separate sink action with its
own idempotency and readback receipt; it is not renderer authority.
The bundled Lark extension includes an opt-in `miaoda_html` delivery sink for
`html_artifact_v0`. It validates the single HTML, compressed archive, and
uncompressed payload limits before any external effect. A successful receipt
requires exact readback of the profile-owned app id, published URL, and
published state, and also records the observed access scope and login
requirement. The project or host still owns app selection, authentication,
audience policy, and the execute decision.

The normalized document's optional `editorial` input is split by ownership.
The project profile owns bounded `kicker`, `period_label`, `language`, and zero
to four ordered public-safe highlights. The document builder owns `summary` and
its `periodic_report_editorial_orchestration_v0` receipt. It deterministically
selects typed primary `outcome`/`decision`, `risk`, and `next_action` titles,
falls back to an item's typed `next_action` field when needed, records exact
item lineage, and rejects an authored summary. Both built-in
renderers recompute the value before rendering, so changing the summary without
changing its source facts fails closed. Primary summaries are limited to 360
characters, and primary `capability_change` items require at least two named
details.

This orchestration is structural, not semantic guessing. Source adapters own
`content_kind`; the compiler never promotes `runtime` or `delivery_receipt`
items, and untyped/progress/capability-change facts remain in the body without
being pulled into the hero. This object is for audience conclusions, not
artifact construction or sink status.
Delivery parity, archive-provider validation, digests, canaries, renderer
lineage, and exact readback remain supporting items or sink receipts.

The core rejects raw content, messages, logs, transcripts, credentials, secret
fields, and private paths. Public packets retain only compact references and
digests.
