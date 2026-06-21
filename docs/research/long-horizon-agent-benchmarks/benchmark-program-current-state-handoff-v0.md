# Benchmark Program Current-State Handoff V0

Checked at: 2026-06-08T03:34:00+08:00.

This handoff is the compact current-state runbook for the LoopX
long-horizon benchmark research program. It tells a fresh worker what the
current evidence means, which artifacts own the details, and which transitions
are allowed next.

It is not a benchmark result, runner setup instruction, approval, new status
projection, review-packet field, project-asset field, or leaderboard path. It
does not read raw logs, private traces, local artifact paths, chat history,
worker session history, Terminal-Bench, Harbor, Docker, Codex/model APIs, cloud
sandboxes, paid compute, external evaluators, or leaderboard upload paths.

## Current State

The program is still in public-safe fixture and readiness evidence:

| Layer | Current state | Owner artifact |
| --- | --- | --- |
| Benchmark choice | Terminal-Bench 2.0 / Harbor remains the first official-runner probe candidate. | `paper-runner-dossier.md`, `terminal-bench-probe-v0.md` |
| Official task score | No official run has been executed or claimed. | `terminal-bench-official-pilot-readiness-v0.md` |
| Passive result shell | `benchmark_run_v0` / `benchmark_result_v0` fixtures define the future compact ingest shape. | `benchmark-run-v0-ingest.md`, `passive-baseline-protocol-v0.md` |
| Control-plane score | `control_plane_score_core_v0` is fixture-backed and separated from official score. | `benchmark-result-control-plane-score-v0.md` |
| Report chain | The current fixture chain is reconstructable through replay decision and restart actionability. | `benchmark-report-chain-map-v0.md`, `benchmark-history-reconstructability-v0.md`, `benchmark-restart-actionability-v0.md` |
| Projection policy | Interrupt summary, no-submit approval packet, and restart actionability remain research/docs-only. | `mini-control-plane-interrupt-projection-decision-v0.md`, `terminal-bench-no-submit-approval-packet-projection-decision-v0.md`, `benchmark-restart-actionability-projection-decision-v0.md` |

## Fresh Worker Read Order

Read only these files before choosing the next benchmark action:

1. `benchmark-program-current-state-handoff-v0.md` for current state and
   allowed transitions.
2. `benchmark-report-chain-map-v0.md` for the fixture/reporting chain.
3. `terminal-bench-no-submit-approval-packet-v0.md` only if preparing an
   operator question for a future no-submit setup check.
4. `benchmark-run-v0-ingest.md` only if already-produced public official-runner
   output exists and needs passive compact ingestion.

Do not scan every research note unless one of those files points to a missing
contract or a smoke fails.

## Allowed Next Transitions

Choose at most one transition:

- `ask_no_submit_setup_approval`: ask the operator to approve a no-submit
  Terminal-Bench/Harbor setup check. This is a user gate, not autonomous
  execution.
- `passively_ingest_existing_official_output`: if public official-runner output
  already exists, ingest only the compact public-safe fields into
  `benchmark_run_v0` / `benchmark_result_v0`.
- `quiet_stop`: if neither approval nor existing official output exists, stop
  without spending another benchmark delivery slice on re-deriving the same
  fixture chain.

Local fixture smokes may be run only to validate edits to the public research
artifacts. They are not benchmark execution evidence.

## Stop Conditions

No Terminal-Bench or Harbor runner execution is authorized by this handoff.

Stop before:

- real Terminal-Bench or Harbor runner execution;
- Docker, Codex/model API, cloud sandbox, paid compute, or external evaluator;
- private traces, raw runner logs, hidden tests, task outputs, local artifact
  paths, chat history, or worker session history;
- operator-approval claims, setup execution, official score claims, submission,
  upload, or leaderboard language;
- status, review-packet, project-asset, or handoff hot-path projection changes
  unless a projection gate from an existing decision document opens.

## Projection Policy

This handoff remains research/docs-only. It should not create a new status,
review-packet, project-asset, or hot-path interface-budget key.

Promote a compact projection only if a fresh worker repeatedly fails to find
the current benchmark state through this handoff, or if passive official output
creates a real consumer for a smaller machine-readable summary.

## Smoke

```bash
python3 examples/benchmark-program-current-state-handoff-smoke.py
```
