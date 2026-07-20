# Periodic report

`periodic-report` is LoopX's reusable reporting capability. It gives any
project a stable report-run envelope while leaving source semantics, cadence,
presentation, and destinations to profiles and adapters.

| Surface | Value |
| --- | --- |
| CLI | `loopx periodic-report inspect-profile --profile-json <path>`, `evaluate-trigger`, and `compose-run` |
| Protocol | [`periodic_report_v0`](../../reference/protocols/periodic-report-v0.md) |
| Smokes | `python3 examples/periodic-report-smoke.py`, `periodic-report-profile-smoke.py`, `periodic-report-html-smoke.py`, and `periodic-report-bindings-smoke.py` |

The capability ships with LoopX but is **disabled by default for every
project**. A project opts in with `periodic_report_profile_v0` and
`enabled: true`; the profile then names generic trigger policy, source adapter
bindings, renderer bindings, and required/optional/disabled sink bindings.
There is no issue-fix-specific report capability: issue-fix, release notes,
research, operations, and other domains are peers that supply source adapters.

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

Project-specific weekly reports should be layered as profiles and adapters.
For example, a maintenance profile may choose a local timezone and weekly
cadence, collect repository and discussion signals, render a team card, archive
the artifact, and deliver it to a configured channel. None of those choices
becomes an invariant of the shared core.

This is a built-in capability, not an extension: callers need the trigger,
idempotency, retry, and receipt contract even when no provider is installed.
Optional or independently versioned collectors, renderers, archive stores, and
message transports remain extension providers (or built-in adapters) that
implement the capability's ports without owning its lifecycle.

Use `inspect-profile` before scheduling a run. It returns a deterministic
`periodic_report_activation_v0` receipt and never starts a scheduler or invokes
a provider. An omitted `enabled` field is treated as `false`. When enabled, at
least one source and one renderer binding are required. An optional archive
extension can therefore add durable history without making report generation
or another configured delivery sink depend on that provider.

The public profiles fixture covers a default-disabled project, a cadence-based
release report with an optional archive extension, and a milestone-only
research report with an extension-provided source. These are peer product uses;
none changes the capability identity or core schema.

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

## Built-in renderers

- `markdown_v0` produces a compact linear artifact for documents and message
  adapters.
- `html_artifact_v0` produces a self-contained, zero-build editorial report
  with dense outcome rows, responsive section navigation, text search,
  Markdown copy, and print/PDF controls. Its default `editorial_dense_v1`
  profile keeps the report body focused on title, status, tags, summary,
  next action, and evidence. Generation metadata, source status, and digests
  live in a collapsed supporting appendix instead of interrupting the report.
  The renderer has no external runtime dependency and escapes all source
  content before rendering.

Both built-in renderers consume the exact same normalized document. The HTML
artifact records the companion Markdown digest, so a caller can prove that the
shareable page and linear message/document version carry the same primary
content. The public fixture at
`examples/fixtures/periodic-report-editorial-dense.public.json` demonstrates a
reusable, project-neutral report.

## Default editorial contract

The reusable renderer deliberately separates audience content from operational
receipts:

- visible body: outcomes, evidence, impact or risk expressed in the summary,
  status, and a concrete next action when one exists;
- collapsed supporting context: profile identity, generation time, source
  health, snapshot digests, and renderer lineage;
- omitted by default: narration about how the report was generated, tool-use
  commentary, local paths, raw logs, or policy explanations that do not change
  an audience decision.

Source adapters and profiles still decide what is material. The renderer does
not guess business semantics or silently rewrite a weak report; it gives all
projects one readable default once their facts have been normalized.

HTML generation is separate from publication. A static-site, Lark HTML, or
other hosting adapter may publish the artifact and return an exact readback
receipt, but the renderer neither chooses a destination nor performs a write.
Project profiles still own language, layout policy, audience, cadence, and
selection rules.
