# Terminal-Bench CLI Dry-Run Fake Worker V0

Checked at: 2026-06-08T19:21:00+08:00.

This note documents the first public LoopX CLI skeleton for the
Terminal-Bench lane:

```bash
loopx benchmark run terminal-bench \
  --goal-id <goal-id> \
  --mode hardened-codex|codex-loopx|loopx-managed-codex \
  --fake-worker
```

The command is fixture-only. By default it is a dry-run; with `--execute` it
appends a compact `benchmark_run_v0` row to the selected LoopX runtime.
It still does not run Harbor, Terminal-Bench, Docker, real Codex CLI, model
APIs, direct LLM APIs, cloud sandboxes, paid compute, uploads, shares, or
leaderboard paths.

## Public CLI Contract

The CLI exposes the current runner-mode contract lanes:

| Mode | Event mode | Current execution |
| --- | --- | --- |
| `hardened-codex` | `hardened_codex_baseline_cli_dry_run` | Fixture event only. |
| `codex-goal-mode` | `codex_goal_mode_baseline_cli_dry_run` | Fixture event only; primary baseline envelope. |
| `codex-loopx` | `codex_loopx_cli_dry_run` | Fixture event only. |
| `passive-observed-codex` | `passive_observed_codex_cli_dry_run` | Fixture event only. |
| `loopx-managed-codex --fake-worker` | `loopx_managed_codex_fake_worker_wrapper` | Deterministic fake-worker event only. |

`--fake-worker` is currently allowed only for
`loopx-managed-codex` and `codex-loopx`. That keeps the hardened
baseline as a no-worker control and makes LoopX modes the only
fake-worker treatments.

## Event Boundary

The CLI-generated event keeps:

| Field | Value |
| --- | --- |
| `schema_version` | `benchmark_run_v0` |
| `source_runner` | `loopx_terminal_bench_cli_skeleton` |
| `benchmark_id` | default `terminal-bench@2.0` |
| `task_id` | default `build-cython-ext` |
| `real_run` | `false` |
| `submit_eligible` | `false` |
| `official_task_score.kind` | `not_run` |
| `progress.n_total_trials` | `0` |
| `metrics.cost_usd` | `0` |
| `leaderboard_evidence` | `false` |

For managed fake-worker mode it also keeps:

- `worker_mode=loopx_managed_codex_cli`;
- `case_semantics_changed_by_harness=true`;
- `loopx_inside_case=true`;
- `official_score_comparable_to_native_codex=false`;
- `model_plus_harness_pair=true`;
- `first_blocker=fake_managed_worker_only_no_real_case`.

## Claim Boundary

This CLI slice may claim:

- the public command surface exists;
- the command can dry-run and append compact fixture-only `benchmark_run_v0`
  rows;
- managed mode is preserved as a `model + harness` pair;
- real execution and public claims remain gated.

It must not claim:

- official Terminal-Bench task success;
- official reward;
- token or cost reduction;
- native Codex baseline comparability for managed mode;
- leaderboard readiness;
- benchmark uplift;
- paper-ready evidence.

## Stop Conditions

Stop before:

- adding real Harbor, Terminal-Bench, Docker, Codex, model API, cloud, paid
  compute, upload, share, or leaderboard execution to this public command;
- recording raw benchmark prompts, raw logs, raw Codex sessions, Docker logs,
  auth files, local paths, or task artifacts in public artifacts;
- claiming official score, pass/fail improvement, token/cost reduction,
  benchmark uplift, leaderboard signal, or paper-ready evidence.

## Smoke

```bash
python3 examples/terminal-bench-cli-dry-run-fake-worker-smoke.py
```

The smoke validates this document, calls the CLI in dry-run and execute mode
against a temporary registry/runtime, checks that the execute path appends a
compact `benchmark_run_v0`, verifies status reconstruction, and confirms that
`--fake-worker` is rejected outside managed mode.
