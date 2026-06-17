# Benchmark Core Adapter Contract v0

Goal Harness benchmark code should use a small shared core plus
benchmark-specific adapters, following the pattern used by Inspect AI, Inspect
Evals, BrowserGym, and AgentLab.

## Shared Core

The control plane should only depend on these adapter-neutral concepts:

- `BenchmarkAdapter`: `preflight -> launch -> observe -> ingest -> classify -> ledger`.
- Canonical lifecycle:
  `process_started -> runner_accepted_args -> job_root_materialized -> trial_started -> worker_started -> result_written -> verifier_scored`.
- Round rewards: per-round official scalar stored offline, with
  `first_success_round`, `best_reward_round`, and final-round fields.

`process_started` alone must not count as entering a benchmark case. Case entry
starts at `job_root_materialized` or later.

## Adapter Boundary

Benchmark-specific code belongs behind adapters:

- Terminal-Bench: Harbor launch/materialization, Docker/job-root observation,
  verifier closeout, no-upload gates.
- SkillsBench: ACP/BaseUser runner, product-mode case state, round reward
  reduction, setup blocker attribution.
- ALE: local Docker/source readiness, large-image gate, launch packet.

The shared ledger should consume only adapter-neutral lifecycle, score, route,
failure, and trace summaries. Raw task text, trajectories, verifier output,
private paths, credentials, and benchmark logs remain outside public artifacts.

## Module Layout

Keep `goal_harness/benchmark.py` as a legacy public facade while moving durable
surfaces into smaller modules:

| Module | Owns | Must Not Own |
| --- | --- | --- |
| `goal_harness.benchmark_core` | adapter-neutral lifecycle, round summaries, artifact/source boundary policy | benchmark-specific launchers or scoring quirks |
| `goal_harness.benchmark_adapters.skillsbench` | SkillsBench routes, arm semantics, job names, public-safe setup failure attribution | Terminal-Bench/ALE/AgentIssue behavior |
| `goal_harness.benchmark_adapters.terminal_bench` | Terminal-Bench public constants, runner modes, CLI-bridge/access-packet labels, timeout and compact validation policy constants | ALE/SkillsBench/AgentIssue behavior or live Harbor execution |
| `goal_harness.benchmark_adapters.agents_last_exam` | ALE public constants, case-state path, local runner/source readiness schema labels, task-data scan regex | Terminal-Bench/SkillsBench/AgentIssue behavior or raw ALE task material |
| `goal_harness.benchmark_adapters.agentissue` | AgentIssue-Bench runner packets, synthetic staging, execution gates, compact result reducer | shared artifact boundary or unrelated benchmark policy |
| `goal_harness.benchmark` | backward-compatible public imports plus legacy functions not yet extracted | new benchmark-specific code when a narrower adapter module exists |

New benchmark code should choose one of these homes before adding functions. If
a helper is useful across benchmarks, put it in `benchmark_core`. If it names a
benchmark, route, Docker image, task family, or verifier convention, put it in a
benchmark adapter.

## Extraction Progress

Completed slices:

1. Shared `benchmark_core` package and canonical lifecycle projection.
2. Focused smoke proving `process_started` is not case entry.
3. `benchmark_core.artifacts` for compact/public artifact and candidate-source
   boundaries.
4. `benchmark_adapters.skillsbench` for SkillsBench route contracts, job names,
   and public-safe runner error attribution.
5. `benchmark_adapters.agentissue` for AgentIssue-Bench runner flow, gates, and
   compact result reducers.
6. `benchmark_adapters.terminal_bench` and
   `benchmark_adapters.agents_last_exam` for benchmark-specific public
   configuration, plus removal of the shadowed duplicate ALE helper block from
   `benchmark.py`.

Next slices:

1. Move Terminal-Bench private-runner launch/materialization helper functions behind the
   `benchmark_adapters.terminal_bench` module.
2. Move ALE readiness/launch packet helper functions behind the
   `benchmark_adapters.agents_last_exam` module.
3. Keep `benchmark.py` as the compatibility facade until callers are migrated
   to adapter imports.
