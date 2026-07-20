# Periodic report

`periodic-report` is LoopX's reusable reporting capability. It gives any
project a stable report-run envelope while leaving source semantics, cadence,
presentation, and destinations to profiles and adapters.

| Surface | Value |
| --- | --- |
| CLI | `loopx periodic-report inspect-profile --preset weekly`, custom `--profile-json <path>`, `evaluate-trigger`, `compose-run`, and optional `archive-openviking` |
| Protocol | [`periodic_report_v0`](../../reference/protocols/periodic-report-v0.md) |
| Smokes | `python3 examples/periodic-report-smoke.py`, `periodic-report-profile-smoke.py`, `periodic-report-html-smoke.py`, `periodic-report-bindings-smoke.py`, and `openviking-periodic-report-extension-smoke.py` |

## Generate this week's report

In an active LoopX or Codex project session, ask the agent to **generate this
week's project report**. That explicit request opts the current session into
one provider-free generation. The agent resolves the built-in
`weekly-progress` profile (short aliases: `weekly` and `weekly-report`),
collects the current project's public-safe LoopX progress, and renders matching
Markdown and self-contained HTML artifacts. No project profile file,
Automation, provider, or external sink is required.

The agent can inspect the exact built-in profile with the effect-free command:

```bash
loopx periodic-report inspect-profile --preset weekly --format json
```

The receipt must report both `active: true` and `generation_allowed: true`.
Its `interaction_contract` also says that the explicit user request is
sufficient, no project profile file or Automation is required, and external
writes are not allowed for this mode. Agents should follow that packet instead
of expanding a generic heartbeat prompt.
The preset binds the built-in `project_progress_v0` source plus `markdown_v0`
and `html_artifact_v0`, declares no schedule, and contains no sink bindings.
The explicit request owns the report window using the active session's local
calendar context; it does not create a recurring job.

`project_progress_v0` organizes typed facts into a reusable hierarchy:
progress and outcomes, capability evolution, risks and blockers, next actions,
and collapsed supporting evidence. It permits at most eight primary items, so
delivery receipts and runtime validation stay supporting instead of crowding
the audience narrative. This hierarchy is inspired by the validated project
weekly-report presentation, but it contains no issue, pull-request, or
Issue Fix policy.

There is no issue-fix-specific report capability. Issue Fix, release notes,
research, operations, and other domains may supply peer source adapters when
their richer semantics are useful; none is required by the built-in weekly
profile.

## Customize or schedule

The capability remains **inactive for background work and external writes by
default**. Create a project-owned `periodic_report_profile_v0` only when the
project needs custom sources, renderers, audience policy, timezone/RRULE, or
explicit sink bindings. Use Codex App Automation only for an unattended
recurring report: the host schedule should match that custom profile's RRULE.
Pausing the Automation or setting the profile to `enabled: false` stops that
scheduled path.

External delivery and archival are separate opt-ins. Adding a sink binding
does not grant authority by itself; the selected extension, runtime capability,
execution decision, and exact readback must still pass their own gates. A
normal in-session weekly report has no sink and performs no external write.

The capability is intentionally effect-free. It first evaluates scheduled or
material progress facts into a deterministic trigger receipt, then composes a
run with stable run and sink idempotency, typed source snapshots, artifact and
sink receipts, explicit partial/unknown outcomes, and bounded retry guidance.
It performs no provider read or write.

Reportable transitions include a due cadence, a validated primary outcome, a
validated vision closure with either a successor or terminal goal, material
route decisions, primary-path blockers and recoveries, and authorized manual
runs. Ordinary todo completion, unchanged monitors, state refreshes,
surface-only events, and intermediate vision checkpoints are suppressed.
Profiles can enable trigger kinds and set a minimum interval; urgent outcome,
closure, blocker, and manual triggers may bypass that interval. Concurrent
material facts are coalesced into one report and previously covered trigger
ids are deduplicated.

Project-specific scheduled reports should be layered as profiles and adapters.
For example, a maintenance profile may choose a local timezone and weekly
cadence, collect repository and discussion signals, render a team card, archive
the artifact, and deliver it to a configured channel. None of those choices
becomes an invariant of the shared core or the in-session preset.

This is a built-in capability, not an extension: callers need the trigger,
idempotency, retry, and receipt contract even when no provider is installed.
Optional or independently versioned collectors, renderers, archive stores, and
message transports remain extension providers (or built-in adapters) that
implement the capability's ports without owning its lifecycle.

`inspect-profile` returns a deterministic `periodic_report_activation_v0`
receipt and never starts a scheduler or invokes a provider. `--preset weekly`
resolves the built-in session profile; `--profile-json` validates a custom
project profile. In a custom profile, an omitted `enabled` field is treated as
`false`, and enabled profiles require at least one source and one renderer.
An optional archive extension can therefore add durable history without making
local report generation or another configured delivery sink depend on it.

The public profiles fixture covers the built-in portable weekly profile, a
default-disabled project, a cadence-based release report with an optional
archive extension, and a milestone-only research report with an
extension-provided source. These are peer product uses; none changes the
capability identity or core schema.

## Generation and formal delivery

The reusable lifecycle has two independently truthful phases:

1. `build_periodic_report_generation_bundle` freezes one normalized document,
   one or more rendered artifacts, and a provider-free generation receipt. A
   missing chat or archive provider cannot invalidate these local artifacts.
2. A project profile declares sink bindings. LoopX checks the pinned extension
   version, protocol, capability version, and provider readback before a caller
   attempts formal delivery. Provider results are then normalized into one
   delivery receipt with retryable sink ids and exact-readback evidence.

Each sink dependency is profile-owned and explicit:

- `required` fails closed when its provider is missing, incompatible, or not
  verified;
- `optional` preserves the generated report and records a degraded or partial
  formal-delivery outcome;
- `disabled` performs no provider lookup or write.

This yields three portable operating modes. `portable` generates artifacts
without providers, `enhanced` adds optional sinks, and `durable` requires one
or more formal delivery or archive sinks. The public fixture at
`examples/fixtures/periodic-report-extension-modes.public.json` exercises all
three without naming a project or relying on a live provider.

`compose-run` remains the compatibility envelope for callers that already have
both archive and delivery receipts. New profile integrations can use the split
generation/readiness/delivery receipts so provider-specific policy does not
leak into the capability core.

## Optional OpenViking archive extension

`openviking-periodic-report` is a bundled **LoopX extension** that implements
the capability's `periodic_report_sink_v0` archive port. It is not an
OpenViking extension and it adds no OpenViking runtime ABI. The dependency
direction is:

```text
periodic-report capability
  -> openviking-periodic-report LoopX extension
     -> OpenViking public SDK read/write
```

Install it through the normal LoopX lifecycle:

```bash
loopx extension install --bundled openviking-periodic-report --execute --format json
```

Activation fails closed unless all three facts hold:

1. a normalized `periodic_report_activation_v0` says the project profile is
   enabled;
2. that profile binds `report.archive.write/v0` to
   `openviking-periodic-report@1.0.0` with `periodic_report_sink_v0` and a
   non-disabled dependency policy;
3. the current run has observed and declared
   `--available-capability openviking_context_write`.

The extension manifest permission does not grant write authority. It only
lets the runtime prove that the selected, enabled, doctor-verified revision is
compatible with authority already observed by the caller. A profile may keep
the sink `optional` for an enhanced experience or mark it `required` for a
durable report contract.

The v0 provider accepts only the Markdown artifact. It writes `report.md`
first and `manifest.json` last; the exact-read-back manifest is the commit
marker and contains the stable bundle digest and result id. A byte-identical
retry performs no write. A stable URI containing different bytes fails closed.
It does not archive HTML, copy the full report into Agent Memory, scan report
history, or implement `/reports`.

```bash
loopx periodic-report archive-openviking \
  --request-json periodic-report-openviking-request.json \
  --available-capability openviking_context_write \
  --openviking-url http://localhost:1933 \
  --execute \
  --format json
```

Use `--openviking-api-key-env` to name an environment variable; never put a
credential in the report profile or request. Without `--openviking-url`, the
provider uses the public embedded `OpenViking` client and optional
`--openviking-path`; `--openviking-config` selects its `ov.conf` explicitly so
an isolated run need not inherit the user's default configuration. The
OpenViking SDK is an optional environment dependency and the extension doctor
stays unavailable until it can import that public client surface. Project
profiles own whether the archive is enabled and
the Resource root/tags supplied in the request context. The generic capability
continues to own trigger, generation, delivery truth, and retry semantics.

## Built-in renderers

- `markdown_v0` produces a compact linear artifact for documents and message
  adapters.
- `html_artifact_v0` produces a self-contained, zero-build editorial report
  with dense outcome rows, responsive deep-linked section navigation, text
  search, Markdown copy, and print/PDF controls. Its default
  `editorial_dense_v2` profile accepts profile-owned language, period labels,
  and at most four first-screen highlights. The document builder compiles the
  hero summary from typed primary outcomes, risks, and next actions; authored
  summaries are rejected so process narration cannot bypass the content
  hierarchy. Normalized items may declare
  `visibility=primary|supporting` and a `content_kind`; `runtime` and
  `delivery_receipt` items are rejected unless they are supporting context.
  Generation metadata, source status, digests, and supporting items live in a
  collapsed appendix instead of interrupting the report. The Markdown renderer
  retains supporting items in a labeled appendix so copied and delivered text
  remains complete.
  The renderer has no external runtime dependency and escapes all source
  content before rendering.

Both built-in renderers consume the exact same normalized document. The HTML
artifact records the companion Markdown digest, so a caller can prove that the
shareable page and linear message/document version carry the same primary
content. The public fixture at
`examples/fixtures/periodic-report-editorial-dense.public.json` demonstrates a
reusable, project-neutral report.

## Bundled Miaoda HTML delivery

The bundled `loopx-lark` extension provides an opt-in `miaoda_html` delivery
sink for the self-contained `html_artifact_v0` output. The sink publishes the
already-rendered artifact to a profile-owned Miaoda HTML app; it does not
rebuild the document or choose an audience. Before any external effect it
checks the single HTML, compressed archive, and uncompressed payload limits.
After publication it requires exact readback of the same app id, published
URL, and published state, and records the observed access scope and login
requirement in the sink receipt.

Projects bind the sink explicitly so report generation remains portable and
external writes remain disabled by default:

```json
{
  "sink_id": "miaoda_html_delivery",
  "sink_kind": "miaoda_html",
  "sink_role": "delivery",
  "dependency_policy": "optional",
  "capability": {
    "capability_id": "report.miaoda_html.publish",
    "capability_version": "v0"
  },
  "extension": {
    "extension_id": "loopx-lark",
    "extension_version": "1.4.0",
    "protocol": "periodic_report_sink_v0"
  }
}
```

The project or host still owns the app id, authentication, execution decision,
and access policy. A preview delivery performs validation only and never calls
the injected publish or readback effects. Repeated publication should reuse the
same app id and delivery idempotency key instead of creating a new app for each
report.

## Default editorial contract

The reusable renderer deliberately separates audience content from operational
receipts:

- visible body: outcomes, evidence, impact or risk expressed in the summary,
  status, and a concrete next action when one exists;
- collapsed supporting context: profile identity, generation time, source
  health, snapshot digests, renderer lineage, runtime notes, and delivery
  receipts;
- omitted by default: narration about how the report was generated, tool-use
  commentary, local paths, raw logs, or policy explanations that do not change
  an audience decision.

Profiles may provide `editorial.kicker`, `period_label`, `language`, and up to
four highlights. They do not author `editorial.summary`. The builder selects
the highest-ranked typed `outcome` or `decision`, `risk`, and `next_action`
titles, falling back to a typed item's `next_action` field when no dedicated
next-action item exists. It records exact item/field lineage in
`periodic_report_editorial_orchestration_v0`. Both renderers recompute that
summary and reject a stale or hand-edited value. A localized profile language
also selects the built-in report controls, compiler labels, and appendix
labels. Items may use up to four ordered `details` rows to split dense evidence
into named facts, plus `tag_labels` to display localized labels without
changing canonical tags. Primary summaries are limited to 360 characters;
primary `capability_change` items require at least two named details so a long
mechanism narrative cannot return as one wall of text. Artifact parity,
archive-provider canaries,
idempotency, digests, renderer versions, and delivery readback belong in
supporting items or sink receipts. A `source_ref` is only a navigation source;
frozen claims should be backed by the source snapshot digest/ref rather than an
open-ended live query.

Source adapters still decide what each fact means by assigning its
`content_kind` and `value_rank`; profiles decide the report sections and
audience. The orchestration layer composes only those typed facts and never promotes `runtime` or
`delivery_receipt` items. The renderer does not guess business semantics,
delete supporting facts, or silently rewrite a weak report; it verifies the
compiled contract and gives all projects one readable default once their facts
have been normalized.

HTML generation is separate from publication. A static-site, Lark HTML, or
other hosting adapter may publish the artifact and return an exact readback
receipt, but the renderer neither chooses a destination nor performs a write.
An HTML host should publish the generated artifact without re-rendering its
normalized document. A host that applies another presentation must preserve the
artifact's primary/supporting visibility policy and validate direct section
hashes after dynamic content is mounted.
Project profiles still own language, layout policy, audience, cadence, and
selection rules.
