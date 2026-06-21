# Terminal-Bench Managed Real-Run Preflight Guard V0

Checked at: 2026-06-08T19:38:00+08:00.

This note defines the no-run preflight guard before the first real
`loopx-managed-codex` Terminal-Bench case:

```bash
loopx benchmark run terminal-bench \
  --goal-id <goal-id> \
  --mode loopx-managed-codex \
  --preflight-guard
```

By default the command is a dry-run. With `--execute`, it appends only a compact
`benchmark_run_v0` readiness row. It may run local CLI presence/version probes
such as `uvx --version`, `docker --version`, `docker version`, `colima status`,
and `codex --version`; it must not run Harbor, Terminal-Bench, a Codex worker,
a benchmark task container, model APIs, cloud sandboxes, paid compute, uploads,
shares, or leaderboard paths.

## Guard Contract

The preflight guard checks only public-safe readiness signals:

| Surface | Allowed signal |
| --- | --- |
| Runner | `uvx` command presence/version probe; Harbor/Terminal-Bench command execution remains off. |
| Local execution | Docker/Colima CLI/server readiness booleans; no benchmark task container is started. |
| Codex CLI | command presence/version probe; no `codex exec` worker is invoked. |
| Auth | fixed auth-surface variable names are checked, but credential values are never read or stored. |
| Boundary | no-upload, no-submit, artifact-redaction, and no-leaderboard flags stay explicit. |

The probe includes the current shell path plus standard user-local/Homebrew
install locations when checking command presence, but it records only booleans
and fixed surface names, never local directories.

The compact event uses:

| Field | Value |
| --- | --- |
| `schema_version` | `benchmark_run_v0` |
| `source_runner` | `loopx_terminal_bench_managed_real_run_preflight_guard` |
| `mode` | `loopx_managed_codex_real_run_preflight_guard` |
| `worker_mode` | `loopx_managed_codex_cli` |
| `real_run` | `false` |
| `submit_eligible` | `false` |
| `official_task_score.kind` | `not_run` |
| `loopx_inside_case` | `true` |
| `official_score_comparable_to_native_codex` | `false` |
| `model_plus_harness_pair` | `true` |
| `leaderboard_evidence` | `false` |

If all no-run preflight surfaces are ready, the first blocker becomes
`ready_for_private_managed_no_upload_pilot_review`. Otherwise it names the
missing surface, such as `missing_docker_server_surface` or
`missing_codex_cli_surface`.

## Claim Boundary

This guard may claim:

- the managed mode has a preflight command path;
- runner, local execution, Codex CLI, auth-name, no-upload, and redaction
  boundaries were checked at the surface level;
- any readiness blocker is compactly represented before real execution;
- no official task result or leaderboard evidence was produced.

It must not claim:

- official Terminal-Bench task success;
- managed LoopX uplift;
- native Codex baseline comparability for the managed case;
- token/cost reduction;
- benchmark leaderboard readiness;
- paper-ready evidence.

## Stop Conditions

Stop before:

- executing Harbor or Terminal-Bench;
- invoking `codex exec` as a benchmark worker;
- starting a benchmark task container;
- reading credential values, auth files, raw Codex sessions, raw benchmark logs,
  Docker logs, host paths, prompts, or task artifacts into public artifacts;
- uploading, sharing, submitting, or claiming leaderboard/paper evidence.

## Smoke

```bash
python3 examples/terminal-bench-managed-real-run-preflight-guard-smoke.py
```

The smoke validates this document, runs the CLI in dry-run and execute mode
against a temporary registry/runtime with fake surface commands, verifies the
compact `benchmark_run_v0` append/status projection, and confirms the guard is
rejected for non-managed and fake-worker modes.
