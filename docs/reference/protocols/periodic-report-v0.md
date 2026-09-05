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

### Audience policy and announcement plan

A custom profile may include `periodic_report_audience_policy_v0`. The policy
contains symbolic recipients, an eligible visibility set (primary by default),
and no provider identity. Each recipient must own one or more normalized domain
tokens or declare one or more `periodic_report_audience_routing_rule_v0`
objects. A rule may select `source_ids`, `section_ids`, `content_kinds`,
`tags_any`, or `domains_any`; every selector declared by that rule must match
one normalized item. An item may carry `domains` in addition to its existing
tags and content kind.

`periodic_report_announcement_plan_v0` is a deterministic, provider-neutral
projection over the exact normalized document and audience policy. It records
the selected symbolic recipient ids, matching item references, typed match
reasons, and policy/document digests. An owned-domain intersection or explicit
routing-rule match is required. Supporting items are ignored unless the policy
explicitly makes that visibility eligible. An unrelated recipient is omitted,
and title or summary text never infers relevance.

The Lark delivery adapter accepts the document and policy together. Preview
returns the plan with no identity resolution or external effect. Execute asks
an injected Lark identity adapter to render only the selected symbolic ids,
prepends those `<at>` elements, then uses the existing send and exact-readback
contract. A selected recipient without an identity renderer, a mismatched
artifact/document digest, or mention markup authored into report content,
title, or footer fails closed before send. This keeps relevance in the core
contract and provider identity on the extension side.

The shipped execution path is `loopx periodic-report deliver-goal-channel`.
Its delivery intent must contain exactly two ordered HTTPS announcements: the
hosted report entry, then the Lark document entry. They are sent as two
independently idempotent messages and each one must pass exact readback. Before
each write, the provider scans the complete Goal Channel history from the frozen
generation time and reuses an exact card, chat, and Bot-sender match. An incomplete
history read fails closed; the provider's stable one-hour idempotency key covers
the remaining concurrent-send race. The command does not accept a chat, profile,
App identity, or sender override. Instead,
the Lark extension resolves the current Goal's local-private Goal Channel
binding and requires `mode=project_bot`, Bot sender identity, a non-default
profile, exact Bot App id and display name, and an enabled Lark channel.
Before sending, it live-verifies that the bound profile authenticates as the
same Bot App and can reach the same chat. After sending, it reads back the
exact interactive card from that chat and requires the provider-native message
sender to be an `app` whose id equals the bound Bot App id. Revalidating the
profile alone is not sender proof.
Missing bindings, local-user mode, identity drift, or incomplete readback fail
closed; no environment-default or user-identity fallback exists.

The governed pending-intent consumer persists the normalized generation bundle
and writes one runnable, agent-owned delivery successor. The current effective
`periodic_report` subscription is re-read before consumption; `enabled: true`
with an explicit `route_ref` is the standing authority for this automatic
stage-boundary delivery. Its Goal, source, effective revision, and route are
frozen into `periodic_report_delivery_authority_v0` and must still match before
each external message write. Disabling the subscription or changing its effective
revision/route suppresses the queued action even when a separate explicit Goal
Channel binding still exists.
The successor remains bound to the frozen generation digest, current Goal,
required provider capabilities, configured Goal Channel, project Bot identity,
and exact readback. This makes the external action visible to quota without a
second per-report approval while still failing closed on route or identity
drift.

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

## Personal Workspace publication projection

`periodic_report_workspace_projection_v0` is the built-in, read-only
`milestone_report` view model for the Personal Workspace. It is frozen from the
same typed document and progress facts as the generated report; the browser
does not parse rendered Markdown or infer titles from fingerprints. Its
interaction semantics are `attention_kind=progress`, `interaction=inform`,
`delivery=surface`, and `writable=false`. Compact counts distinguish facts
added since the preceding verified publication from facts whose semantic
fingerprint changed.

Generation alone does not expose this projection. The publication candidate
binds its exact SHA-256, and the Goal Channel sink may advance that binding into the
publication cursor only after delivery readback succeeds. The compact
`periodic_report_workspace_index_v0` hot path contains identity, delivery time,
predecessor lineage, and an exact content-addressed detail reference, but no
report prose. It returns the newest 100 items by default, accepts a bounded
`limit` (0..200) and non-negative `offset`, and reports `total_count` and
`truncated` so callers can page without receiving an unbounded response. The
full projection is a loopback-only cold read and must match
the current publication cursor. Approval-pending, generation-only, stale, or
digest-mismatched projections therefore fail closed instead of appearing as
published.

The Personal Workspace projection does not generate, approve, publish, acknowledge, or
edit a report. The periodic-report capability remains the only owner of report
trigger, document, delivery, and publication-cursor state. This is a bounded
implementation of the intelligent presentation RFC for milestone reports, not
the generic cross-capability compiler described by that RFC.

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
- `bounded_segment_milestone`: an evidence-linked material checkpoint closed
  the current vision and the resulting successor frontier or terminal Goal was
  durably settled, even when unrelated Todos remain open;
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

`bounded_segment_milestone` is derived from the same goal-vision and frontier
facts that drive autonomous replan, but it is a stricter success-path result.
It requires a satisfied evidence-linked material outcome checkpoint, a closed
current vision, durable writeback, and one of these continuation settlements:

- the Goal is terminal; or
- an active Goal emitted the existing `vision_successor_required` transition,
  the matching replan semantic delta was accepted, and the successor vision
  plus its owned frontier were durably established.

The producer deduplicates by the closed-vision revision and frontier identity.
Ordinary Todo completion, Todo-count thresholds, elapsed time, setup work, and
generic replan causes such as blockers, succession gaps, long Todo chains, or
monitor exhaustion are evidence or control-plane context only; they never
prove stage completion. No Todo declaration or second Stage lifecycle is
introduced. Remaining unrelated Todos do not suppress an otherwise valid
closed-vision milestone. The trigger has priority 40, maps to
`milestone_update`, and obeys the normal profile cooldown.

An eligible decision may be embedded as `trigger_receipt` in a
`periodic_report_run_request_v0`. Its `report_key` and `report_kind` then
participate in run identity, so a milestone update and a scheduled digest over
the same evidence window cannot collide.

### Post-writeback hook boundary

The optional automatic path uses the provider-neutral TypeScript
`post_writeback` capability-hook contract. The CLI composition root registers
`periodic_report.runtime_trigger` only when the Goal's local control-plane
configuration explicitly enables a periodic-report profile. Core dispatches
only after the primary `refresh-state` durable writeback and exact settlement
readback have succeeded with complete Goal, Agent, Todo, Turn, and effect
identity. The best-effort rollout-event log is not dispatch authority.

The hook input contains only the committed receipt identity, stable state
revision, and derived `periodic_report_stage_completion_receipt_v0`. Its result
is an idempotent `periodic_report.trigger_evaluation` intent with an empty write
scope. Core validates registration, input, result, and the sidecar receipt in
TypeScript, then stores the bounded receipt separately from the primary
transaction. Terminal replay skips provider invocation. A transient provider
or result-contract failure persists a `retryable_failure` receipt with a stable
dispatch reference and monotonic attempt count; exact replay may atomically
advance that receipt to `intent_recorded` or `not_applicable`. Conflicts and
optional hook failures remain isolated and cannot roll back the primary
writeback or alter quota-spend eligibility.

Recorded trigger intent means neither report generation nor publication. A
later governed executor must evaluate the intent. Composition, rendering, and
content checks remain separate from external delivery; an enabled effective
subscription supplies standing delivery authority, while the extension and
exact sink readback retain effect authority.

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
requires exact readback of the request-selected app id and published URL plus
the exact publication release in `finished` state. The receipt separates
`release_readback`, `access_scope_readback`, and `content_readback`: access
scope may be a typed `unsupported_by_app_type` result for creative HTML apps,
while other query failures remain retryable `unavailable` evidence; the
bundled provider marks remote content-digest verification as
`unavailable` because the provider API does not expose published bytes or a
digest. App existence, URL equality, and release completion must not be
promoted to byte-for-byte content proof. Receipt normalization recomputes exact
release verification from the requested release id and provider status rather
than trusting a provider boolean. The project or host still owns app
selection, authentication, audience policy, and the execute decision.

`loopx periodic-report publish-miaoda` is the concrete CLI for that sink. Its
`periodic_report_miaoda_delivery_request_v0` must carry a complete normalized
profile, the exact `periodic_report_generation_bundle_v0`, and a
`periodic_report_delivery_intent_v0` with `kind=hosted`,
`sink_kind=miaoda_html`, a profile-bound sink id, an operator-selected existing
app id, and a stable idempotency key. The selected profile binding must use
`report.miaoda_html.publish@v0`, `loopx-lark`, and
`periodic_report_sink_v0`; an omitted, disabled, or differently typed sink is
rejected before provider execution.

Without `--execute`, the command performs no provider call and returns
`periodic_report_miaoda_delivery_result_v0` with
`status=pending_execution`, `intent_satisfied=false`, and a pending delivery
receipt. With `--execute`, it uses authenticated `lark-cli` publication and
requires exact readback of the same app id, online URL, and publication release
in `finished` state. Only that verified lifecycle result sets
`intent_satisfied=true`; access-scope and content-proof limitations remain
explicit evidence in both the sink result and normalized delivery receipt. The
generation bundle remains usable in either case, but local HTML never satisfies
the hosted delivery intent. The command does not accept credentials, create
apps, select an audience, mutate access scope, send chat notifications, or
apply schedule policy.

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
