# Terminal-Bench Official Pilot Readiness V0

Checked at: 2026-06-07T20:23:00+08:00.

This note turns `terminal_bench_official_pilot_decision_packet_v0` into a
local-only readiness fixture. It is not a Terminal-Bench run, not a Harbor run,
not a Codex invocation, and not leaderboard evidence.

## Purpose

The readiness fixture proves LoopX can prepare the evidence shape for a
future Terminal-Bench official pilot without crossing the benchmark boundary.
It should emit a compact `benchmark_result_v0` comparison shell and a
control-plane evidence checklist for two scenarios:

- `bare_codex_cli_readiness`
- `passive_loopx_wrapper_readiness`

Both scenarios must keep `official_task_score.kind = not_run`. The fixture may
show which fields would be collected, but it must not claim task success,
accuracy, reward, or leaderboard uplift.

## Readiness Fields

Every readiness shell should preserve:

| Field | Rule |
| --- | --- |
| `schema_version` | `benchmark_result_v0`. |
| `decision_id` | `terminal_bench_official_pilot_decision_packet_v0`. |
| `benchmark_id` | `terminal-bench@2.0`. |
| `scenario_id` | `bare_codex_cli_readiness` or `passive_loopx_wrapper_readiness`. |
| `harness_identity` | `none` or `loopx_passive_wrapper`. |
| `worker_surface` | Codex CLI official/custom-agent boundary under review. |
| `terminal_state` | `readiness_only`. |
| `official_task_score` | `not_run`; no score value. |
| `control_plane_score` | `readiness_checklist_v0`; checklist only, no measured uplift. |
| `benchmark_run_pairing_rule` | Future official task results must pair one compact `benchmark_run_v0` row per mode. |
| `trace_publicness` | `public_readiness_only`. |
| `stop_conditions` | Include no real benchmark, no Docker, no model API, no cloud sandbox, no paid compute, no leaderboard upload, and no private trace. |

## Control-Plane Checklist

The fixture passes only when it proves the following fields are represented:

- runner source and version or commit placeholder;
- task id or split placeholder;
- agent command boundary;
- official score fields;
- LoopX control-plane score fields;
- pairing rule for `benchmark_run_v0`;
- public artifact manifest;
- side-effect and forbidden-surface audit;
- stop conditions before real execution.

## Stop Conditions

Stop before:

- running Terminal-Bench or Harbor;
- starting Docker or a cloud sandbox;
- invoking Codex, model APIs, paid compute, or any external evaluator;
- uploading leaderboard traces or creating a submission;
- copying raw runner logs, private traces, credentials, local user paths, or
  raw session history into public artifacts;
- claiming official benchmark or leaderboard improvement.

## Current Smoke

The readiness fixture smoke is:

```bash
python3 examples/terminal-bench-official-pilot-readiness-smoke.py
```

It constructs deterministic public-safe `benchmark_result_v0` shells and a
`benchmark_comparison_v0` readiness summary. It does not append runtime history,
does not run a benchmark, and does not contact any external service.
