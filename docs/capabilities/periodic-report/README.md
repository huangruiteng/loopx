# Periodic report

`periodic-report` is LoopX's reusable reporting capability. It gives any
project a stable report-run envelope while leaving source semantics, cadence,
presentation, and destinations to profiles and adapters.

| Surface | Value |
| --- | --- |
| CLI | `loopx periodic-report compose-run --request-json <path>` |
| Protocol | [`periodic_report_v0`](../../reference/protocols/periodic-report-v0.md) |
| Smoke | `python3 examples/periodic-report-smoke.py` |

The first slice is intentionally a pure contract. It provides deterministic
run and sink idempotency, typed source snapshots, artifact and sink receipts,
explicit partial/unknown outcomes, and bounded retry guidance. It performs no
provider read or write.

Project-specific weekly reports should be layered as profiles and adapters.
For example, a maintenance profile may choose a local timezone and weekly
cadence, collect repository and discussion signals, render a team card, archive
the artifact, and deliver it to a configured channel. None of those choices
becomes an invariant of the shared core.
