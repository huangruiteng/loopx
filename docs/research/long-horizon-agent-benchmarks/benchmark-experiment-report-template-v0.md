# Benchmark Experiment Report Template V0

Checked at: 2026-06-07T23:55:00+08:00.

This template is the paper-ready reporting surface for Goal Harness
long-horizon benchmark work. It separates official benchmark evidence from
Goal Harness control-plane evidence and assisted operator-simulator evidence so
future reports do not overclaim leaderboard uplift from local or assisted
fixtures.

## Purpose

The report should answer three questions without mixing evidence layers:

1. What did the benchmark's native scoring say?
2. What did Goal Harness add as a control plane around the same worker/task?
3. What changed only when an assisted operator-simulator overlay was allowed?

The local report schema is `benchmark_experiment_report_v0`. It can summarize
`benchmark_run_v0`, `benchmark_result_v0`, and `operator_simulator_run_v0`
rows, but it must not replace those source events.

## Required Sections

Every report should include these sections in this order:

| Section | Required Content |
| --- | --- |
| `experiment_identity` | Report id, benchmark id, task slice, worker surface, harness identity, policy version, and trace publicness. |
| `official_score` | Benchmark-native pass/fail, reward, accuracy, task id/split, repetitions, runner source, submit eligibility, and whether it is leaderboard evidence. |
| `passive_control_plane_score` | Restartability, stale-state avoidance, evidence discipline, writeback quality, failure attribution, overhead, and any regression avoidance. |
| `operator_simulator_ablation` | Assisted mode setting, visibility policy, intervention budget, intervention counts, simulator-induced failure labels, and explicit non-leaderboard status. |
| `cost_latency_overhead` | Wall time, worker steps, simulator turns, token/cost estimates, writeback count, and validation count. |
| `failure_taxonomy` | Worker failures, harness failures, simulator failures, benchmark-boundary failures, and unknowns. |
| `reproducibility_artifacts` | Public-safe source events, runner versions, task identifiers, validation commands, smoke commands, and artifact manifests. |
| `claim_boundary` | What may be claimed, what must not be claimed, and which evidence layer supports each claim. |
| `negative_results` | Failures, null results, overhead regressions, and why they matter. |
| `next_decision` | Continue, repeat, broaden, defer, or stop, plus the minimum next evidence. |

## Claim Boundary

The report may claim official benchmark improvement only when official
benchmark rows exist for the compared modes, the benchmark protocol allows the
wrapper, task/scoring are unchanged, and submit eligibility is true.

The report may claim control-plane improvement from local or passive evidence
only for coordination dimensions such as restartability, stale-state avoidance,
writeback quality, evidence discipline, failure attribution, and overhead.

The report may claim assisted-collaboration improvement only for
operator-simulator studies. Assisted results must remain separate from official
leaderboard results.

## Source Event Links

Prefer compact public-safe references:

- `benchmark_run_v0:<mode>:<public-id>`;
- `benchmark_result_v0:<comparison-id>`;
- `operator_simulator_run_v0:<setting>:<public-id>`;
- smoke command names;
- public artifact names.

Do not include credentials, private project material, raw transcript material,
raw runner logs, local host paths, hidden tests, expected solutions, benchmark
answer keys, or raw session records.

## Default Smoke

The deterministic smoke is:

```bash
python3 examples/benchmark-experiment-report-template-smoke.py
```

It constructs one public-safe `benchmark_experiment_report_v0` object with
official, passive-control-plane, assisted-simulator, overhead, failure,
reproducibility, claim-boundary, negative-result, and next-decision sections.
It does not run a benchmark, simulator, model API, Docker, cloud sandbox, paid
compute, or leaderboard upload.
