# Benchmark Run V0 Ingestion Contract

Checked at: 2026-06-07T18:30:00+08:00

## Purpose

`benchmark_run_v0` is the first LoopX event shape for public benchmark
runs. It is intentionally passive: it reads official runner outputs and turns
them into a compact, restartable control-plane event without changing benchmark
prompts, task files, timeout settings, resources, scoring, or upload behavior.

This contract starts with Harbor because Harbor is the official Terminal-Bench
2.0 runner path and already writes structured job, trial, reward, and trajectory
artifacts. The same event shape should later support the legacy `tb` runner and
other long-horizon suites.

## Input Surface

For a Harbor job directory, read only these public-safe files:

- job `lock.json`;
- job `result.json`;
- per-trial `config.json`;
- per-trial `result.json`;
- per-trial `agent/trajectory.json` when present;
- per-trial `verifier/reward.json` or `verifier/reward.txt`;
- per-trial `verifier/test-stdout.txt` and `verifier/test-stderr.txt` only as
  existence evidence unless a later public-boundary pass allows excerpts;
- per-trial `artifacts/manifest.json` as a list of collected artifact names.

Do not read Codex raw session files, private runner logs, credentials, host
absolute paths, cloud account metadata, or internal project material by default.

## Event Shape

Every ingested run should emit one `benchmark_run_v0` object:

| Field | Meaning |
| --- | --- |
| `schema_version` | Must equal `benchmark_run_v0`. |
| `source_runner` | `harbor` for this first contract. |
| `benchmark_id` | Dataset or benchmark id, such as `terminal-bench@2.0`. |
| `job_name` | Redacted job name, not an absolute path. |
| `mode` | `passive_observer` until a custom LoopX agent wrapper is approved. |
| `agent` | Agent name, import path when used, model, and public-safe kwargs summary. |
| `progress` | Total, completed, errored, running, pending, cancelled, and retry counts. |
| `metrics` | Aggregate input/cache/output tokens and cost when official output supplies them. |
| `trials` | Compact per-trial task id, trial name, reward map, exception type, timing, token/cost metrics, and evidence booleans. |
| `validation` | Parser-side checks that official outputs are present and internally consistent. |
| `evidence_files` | Relative evidence file categories, never host absolute paths. |
| `resume_or_inspect_commands` | Public-safe command templates, such as `harbor job resume --job-path <job-dir>` and `harbor view <jobs-dir>`. |
| `stop_conditions` | Conditions that block automatic execution or public claims. |

## Validation Rules

A default ingestion smoke should pass only when:

- job `lock.json` and job `result.json` exist;
- every completed trial has a trial `result.json`;
- each parsed trial has verifier reward evidence or an explicit exception;
- Codex/agent trajectory presence is recorded as a boolean, not assumed;
- retry and progress counts are internally consistent;
- invocation does not request `--upload`;
- output paths are redacted before entering `benchmark_run_v0`;
- no private document URL, credential-like value, local user path, internal task
  id, or raw Codex session content is copied into the event.

## Default Smoke

The deterministic smoke is:

```bash
python3 examples/benchmark-run-v0-harbor-ingest-smoke.py
python3 examples/benchmark-run-v0-append-cli-smoke.py
```

It creates a synthetic Harbor-style job directory with one completed
Terminal-Bench trial, then parses it into `benchmark_run_v0`. The fixture writes
only public-safe fake data and does not import Harbor, invoke Docker, call Codex,
use model APIs, use cloud sandboxes, or upload leaderboard results.

## CLI Append

After a runner or parser has produced a `benchmark_run_v0` JSON object, append it
to the normal LoopX run history with:

```bash
loopx history append-benchmark-run \
  --goal-id <goal-id> \
  --benchmark-run-json <benchmark-run-v0.json> \
  --delivery-batch-scale implementation \
  --delivery-outcome primary_goal_outcome \
  --execute
```

Without `--execute`, the command is a dry-run preview. The command compacts the
input before writing so status and review-packet surfaces receive a
public-safe summary rather than raw runner logs or host paths.

## Baseline-Failure Gate

Treatment runs should be selected from an explicit compact baseline-failure
gate, not from benchmark-specific prompt wording or regexes. A baseline runner
or supervising agent may attach a public-safe `baseline_failure_gate` object to
a `benchmark_comparison_v0` row before any LoopX treatment attempt:

| Field | Meaning |
| --- | --- |
| `schema_version` | `benchmark_baseline_failure_gate_v0`. |
| `baseline_mode` | The baseline surface, for example `codex_cli_goal_mode`. |
| `baseline_scenario_id` | Public scenario id for the failed baseline arm. |
| `baseline_terminal_state` | Compact terminal state such as `failed` or `blocked`. |
| `baseline_failed` | Whether the baseline actually failed or blocked. |
| `failure_phase` / `failure_class` | Public-safe failure attribution. |
| `control_plane_addressable` | Whether the failure plausibly concerns coordination, writeback, restartability, stale state, boundary, evidence, or similar control-plane behavior. |
| `treatment_eligible` | Whether a LoopX treatment run is allowed for this baseline failure. |
| `minimum_next_evidence` | The next public-safe evidence required before broader claims. |
| `negative_selection_reason` | Required when the candidate is not treatment-eligible. |

When a comparison row has no paired-result deltas yet, the compact
`benchmark_comparison_decision_note_v0` uses this gate to route either to a
treatment attempt (`baseline_failure_gate`) or to negative selection
(`baseline_failure_gate_negative_selection`). Once paired result deltas exist,
the gate remains claim-boundary evidence and does not override the result
interpretation.

The structured reducer is:

```bash
loopx benchmark baseline-failure-gate \
  --benchmark-id terminal-bench@2.0 \
  --baseline-result-json <benchmark-result-v0.json> \
  --baseline-mode codex_cli_goal_mode \
  --failure-phase <public-phase> \
  --failure-class <public-class>
```

By default this is a negative-selection dry run. A treatment route is emitted
only when the caller explicitly supplies `--control-plane-addressable`,
`--same-task-semantics`, `--same-runner-protocol`, and
`--trace-publicness-verified`. With `--execute --goal-id <goal-id>`, the CLI
appends the compact `benchmark_comparison_v0` row through the normal history
writer.

## Stop Conditions

Stop before:

- executing `harbor run`, `tb run`, Codex, Docker, cloud sandboxes, or model
  APIs automatically from a heartbeat;
- using `--upload`, `harbor upload`, or official leaderboard submission;
- modifying benchmark task prompts, tests, resources, timeouts, scoring, or
  official runner code;
- claiming LoopX improves benchmark score without paired bare Codex and
  passive LoopX runs;
- copying private source material, credentials, host paths, or raw Codex session
  content into public artifacts.

## Next Slice

After the append CLI exists, the next bounded product step is a passive baseline
protocol: define a tiny paired-run fixture for bare Codex CLI versus passive
LoopX wrapping, then have the runner write one `benchmark_run_v0` event
through this command. Keep the fixture local and deterministic before invoking
real Terminal-Bench, Docker, Codex, model APIs, or leaderboard upload paths,
and keep doing this without adding benchmark-specific heartbeat prompt branches.
