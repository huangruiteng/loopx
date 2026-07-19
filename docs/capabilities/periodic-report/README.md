# Periodic report

`periodic-report` is LoopX's reusable reporting capability. It gives any
project a stable report-run envelope while leaving source semantics, cadence,
presentation, and destinations to profiles and adapters.

| Surface | Value |
| --- | --- |
| CLI | `loopx periodic-report evaluate-trigger --request-json <path>` and `compose-run` |
| Protocol | [`periodic_report_v0`](../../reference/protocols/periodic-report-v0.md) |
| Smokes | `python3 examples/periodic-report-smoke.py` and `python3 examples/periodic-report-html-smoke.py` |

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
