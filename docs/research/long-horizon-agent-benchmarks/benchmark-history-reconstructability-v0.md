# Benchmark History Reconstructability V0

Checked at: 2026-06-08T03:05:00+08:00.

This fixture proves a worker can reconstruct the current benchmark
next-decision chain from compact public-safe run history after a restart.

It is not a new status projection, runner setup step, benchmark execution, or
approval path. It does not read raw logs, private traces, local artifact paths,
chat history, worker session history, Terminal-Bench, Harbor, Docker,
Codex/model APIs, cloud sandboxes, paid compute, external evaluators, or
leaderboard paths.

## Purpose

The useful restart question is:

Can a fresh worker recover the benchmark next action from compact history rows
alone, without re-reading stale chat context or re-deriving the whole research
chain?

The expected fixture schema is `benchmark_history_reconstructability_v0`.

## Chain Inputs

The fixture uses the existing benchmark reporting order:

1. `benchmark_run_v0`
2. `benchmark_result_v0`
3. `benchmark_comparison_v0`
4. `benchmark_comparison_decision_note_v0`
5. `benchmark_experiment_report_v0`
6. `benchmark_experiment_report_readiness_note_v0`
7. `benchmark_experiment_report_replay_decision_v0`

Rows may arrive out of order. Reconstruction must sort by explicit sequence
metadata, validate that every required schema appears exactly once for the
decision chain, and ignore any stale row with an older sequence for the same
schema.

## Reconstructed Decision

The reconstructed public-safe handoff should preserve:

| Field | Required value |
| --- | --- |
| `official_score.kind` | `not_run` or otherwise non-leaderboard evidence for the fixture. |
| `official_score.delta` | The compact official-score delta, if available. |
| `control_plane_score.kind` | The compact control-plane score schema. |
| `control_plane_score.delta` | The compact control-plane delta, if available. |
| `claim_boundary.must_not_claim` | Claims blocked by the evidence layer. |
| `readiness` | Report readiness such as `negative_or_control_plane_only`. |
| `authorization` | Next-run authorization such as `fixture_only`. |
| `replay_decision` | Replay action such as `continue_fixture_replay`. |
| `next_run_mode` | Next run mode such as `fixture_replay`. |
| `stop_condition` | The boundary that prevents benchmark escalation. |

The reconstructed handoff must remain compact enough for a worker to continue
without adding a new hot-path top-level projection key.

## Failure Rules

The fixture fails if:

- any required chain schema is missing;
- a stale row wins over a newer row for the same schema;
- official score and control-plane score are merged into one undifferentiated
  result;
- readiness, authorization, replay decision, next-run mode, claim boundary, or
  stop condition is lost;
- private traces, raw logs, local artifact paths, credentials, chat history,
  worker session history, task outputs, official leaderboard claims, or upload
  paths appear in the reconstructed handoff.

## Boundary

No real Terminal-Bench or Harbor runner execution, Docker, Codex/model API,
cloud sandbox, paid compute, external evaluator, private trace, raw runner log,
local artifact path, approval claim, setup execution, or leaderboard path is
involved.

## Smoke

```bash
python3 examples/benchmark-history-reconstructability-smoke.py
```
