# Benchmark Restart Actionability V0

Checked at: 2026-06-08T03:25:00+08:00.

This fixture consumes `benchmark_history_reconstructability_v0` and proves that
a freshly restarted worker can turn the reconstructed public-safe benchmark
state into exactly one bounded next command or a blocker.

It is not a new status projection, review-packet field, runner setup step,
benchmark execution, approval path, or leaderboard path. It does not read raw
logs, private traces, local artifact paths, chat history, worker session
history, Terminal-Bench, Harbor, Docker, Codex/model APIs, cloud sandboxes,
paid compute, external evaluators, or leaderboard upload paths.

## Purpose

The useful actionability question is:

Can a fresh worker resume from compact reconstructed history and select the next
safe fixture action without re-reading stale chat context, raw benchmark logs,
private traces, or local artifact paths?

The expected fixture schema is `benchmark_restart_actionability_v0`.

## Required Input

The fixture accepts one reconstructed decision with schema
`benchmark_history_reconstructability_v0`.

The minimum usable input is:

| Field | Required value |
| --- | --- |
| `readiness` | `negative_or_control_plane_only` |
| `authorization` | `fixture_only` |
| `replay_decision` | `continue_fixture_replay` |
| `next_run_mode` | `fixture_replay` |
| `raw_inputs_required` | `false` |
| `official_score.leaderboard_evidence` | `false` |
| `must_not_claim` | includes `official leaderboard uplift` and `real benchmark pass/fail` |
| `stop_condition` | stops before real benchmark execution or leaderboard claims |

Any stronger or less explicit condition must produce a blocker instead of a
command.

## Selected Action

When the reconstructed decision preserves `fixture_only` authorization and
`continue_fixture_replay`, the restarted-worker plan may contain exactly one
local fixture command:

```bash
python3 examples/benchmark-history-reconstructability-smoke.py
```

The action is allowed only as `run_local_fixture_replay_smoke`. It validates the
compact history reconstruction path, not a real benchmark, runner setup, model
call, simulator run, official score, or leaderboard result.

The plan must also carry the blocked external action list:

- `terminal_bench_runner`
- `harbor_runner`
- `docker`
- `codex_model_api`
- `cloud_paid_compute`
- `external_evaluator`
- `leaderboard_upload`

## Blocker Path

If authorization is not `fixture_only`, replay decision is not
`continue_fixture_replay`, raw inputs are required, leaderboard evidence is
present, or the stop condition is missing, the restarted worker must emit a
public-safe blocker.

The blocker should name the failed fixture gate and preserve the same
`must_not_claim` boundary. It must not invent an operator approval, run a setup
probe, read private evidence, or escalate to a benchmark runner.

## Failure Rules

The fixture fails if:

- the selected plan has more than one command;
- the selected command is anything other than the local reconstructability
  smoke;
- the command appears when authorization or replay state is not fixture-only;
- blocked external actions are omitted;
- official score, control-plane score, claim boundary, stop condition, or
  forbidden claims are lost;
- the plan adds a status, dashboard, review-packet, or hot-path projection key;
- raw logs, private traces, local artifact paths, credentials, chat history,
  worker session history, task outputs, official leaderboard claims, or upload
  paths appear in the plan.

## Boundary

No real Terminal-Bench or Harbor runner execution, Docker, Codex/model API,
cloud sandbox, paid compute, external evaluator, private trace, raw runner log,
local artifact path, approval claim, setup execution, or leaderboard path is
involved.

## Smoke

```bash
python3 examples/benchmark-restart-actionability-smoke.py
```
