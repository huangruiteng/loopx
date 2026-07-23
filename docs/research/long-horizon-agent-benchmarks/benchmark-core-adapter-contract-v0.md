# Benchmark Core Adapter Contract v0

LoopX benchmark code should use a small shared core plus
benchmark-specific adapters, following the pattern used by Inspect AI, Inspect
Evals, BrowserGym, and AgentLab.

## Shared Core

The control plane should only depend on these adapter-neutral concepts:

- `BenchmarkAdapter`: `preflight -> launch -> observe -> ingest -> classify -> ledger`.
- Canonical lifecycle:
  `process_started -> runner_accepted_args -> job_root_materialized -> trial_started -> worker_started -> result_written -> verifier_scored`.
- Round rewards: per-round official scalar stored offline, with
  `first_success_round`, `best_reward_round`, and final-round fields.
- Attempt accounting: `benchmark_attempt_accounting_v0` records launcher,
  case, solver, verifier, and official-score attempts separately. Generic
  failure classes are `runner_startup_failed`, `job_materialization_failed`,
  `solver_failed`, `verifier_failed`, and `official_score_failed`.
  Launcher/materialization failures must not count as case attempts.
- Run permission policy: `run_permission_policy_v0` is the machine-readable
  benchmark execution boundary for allowed local no-upload model/Docker/Harbor
  actions, forbidden upload/leaderboard/public-claim/production-cloud actions,
  timeout budget, and compact-only observation. Quota/status code should consume
  this policy projection instead of inferring permission from narrative text.

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

Keep `loopx/benchmark.py` as a legacy public facade while moving durable
surfaces into smaller modules:

| Module | Owns | Must Not Own |
| --- | --- | --- |
| `loopx.benchmark_core` | adapter-neutral lifecycle, round summaries, artifact/source boundary policy, JSON/number IO reducers | benchmark-specific launchers or scoring quirks |
| `loopx.benchmarks.read_models` | public-safe benchmark result, comparison, ledger, lifecycle, and diagnostic projections | generic control-plane runtime rules or benchmark-family launch behavior |
| `loopx.benchmark_adapters.skillsbench` | SkillsBench routes, arm semantics, job names, public-safe setup failure attribution | Terminal-Bench/ALE/AgentIssue behavior |
| `loopx.benchmark_adapters.terminal_bench` | Terminal-Bench public constants, runner modes, CLI-bridge/access-packet labels, private-runner launch/materialization/readiness helpers, Harbor result reducers, timeout and compact validation policy constants | ALE/SkillsBench/AgentIssue behavior |
| `loopx.benchmark_adapters.agents_last_exam` | ALE public constants, case-state path, local runner/source readiness, launch-packet, validation-gate, CUA/Codex-route, task-material and result-report helpers | Terminal-Bench/SkillsBench/AgentIssue behavior or raw ALE task material |
| `loopx.benchmark_adapters.agentissue` | AgentIssue-Bench runner packets, synthetic staging, execution gates, compact result reducer | shared artifact boundary or unrelated benchmark policy |
| `loopx.benchmark` | backward-compatible public imports plus legacy functions not yet extracted | new benchmark-specific code when a narrower adapter module exists |

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
7. `benchmark_core.io` for shared JSON/number reducers and
   `benchmark_adapters.agents_last_exam` for ALE helper surfaces formerly kept
   in the legacy facade.
8. `benchmark_adapters.terminal_bench` for Terminal-Bench helper surfaces
   formerly kept in the legacy facade, including runner launch/materialization,
   access-packet, bridge-trace, and Harbor compact result reducers.
9. `benchmark_core.run_permissions` for `run_permission_policy_v0` and the
   compact quota projection used by `goal_boundary.run_permission_policy`.
10. `benchmark_core.attempts` for `benchmark_attempt_accounting_v0` and the
    shared failure taxonomy that keeps runner startup/materialization blockers
    out of case-attempt accounting.
11. `benchmark_core.remote_closeout` for compact/public-only remote artifact
    sync and local ledger/aggregate ownership. Remote benchmark runners produce
    compacts; they do not also maintain a second ledger.

## Adapter Rollout Matrix

This table is the public-safe rollout ledger for the shared adapter contract.
It records which benchmark family owns the generic lifecycle stages through an
adapter, and which stage should be migrated next. Benchmark-specific runner
details must stay in the adapter column, not in `benchmark_core`.

| Benchmark family | Adapter module | Current generic lifecycle coverage | Next migration slice |
| --- | --- | --- | --- |
| Terminal-Bench | `loopx.benchmark_adapters.terminal_bench` | First migration target. Public configuration, private-runner launch/materialization helpers, access packets, bridge traces, Harbor reducers, timeout policy, compact validation policy, `run_permission_policy_v0`, and `benchmark_attempt_accounting_v0` adoption are adapter-owned. | Adopt the same permission-policy and attempt-accounting fields in any new public launch/result packets before adding new Terminal-Bench runner behavior. |
| SkillsBench | `loopx.benchmark_adapters.skillsbench` plus ACP relay helpers | Route contracts, arm semantics, job names, public-safe setup failure attribution, case-local product lifecycle, compact reducer surfaces, no-upload permission policy, and split attempt-accounting surfaces are adapter-owned. | Goal-start `/loopx` raw/new mapping remains blocked on transport monitor `todo_45357c108d81`: the latest compact monitor saw no solver output and no new-arm compact artifact, so it must not be promoted into launch/observe/ingest/classify/ledger fields yet. |
| ALE | `loopx.benchmark_adapters.agents_last_exam` | Public configuration, local runner/source readiness, launch packets, validation gates, CUA/Codex-route helpers, and task-material/result-report helpers are adapter-owned. | Add attempt accounting and permission-policy fields to local launch/readiness packets before any new ALE run path is promoted. |
| SWE-Marathon | no dedicated adapter yet | Current evidence remains in public-safe research packets and run ledger rows, not in a reusable adapter module. | Deferred: create the adapter only after a second SWE-Marathon route needs shared launch/observe/ingest behavior; until then, do not add SWE-specific conventions to `benchmark_core`. |

Next slices:

1. Keep `benchmark.py` as the compatibility facade until callers are migrated
   to adapter imports.
2. Split shared compact/result helper functions that are still only imported
   through the Terminal-Bench adapter into narrower `benchmark_core` modules
   when a second benchmark needs them.
3. Adopt `run_permission_policy_v0` in any remaining benchmark adapter public
   launch packet before relying on adapter-specific prose for authorization.
4. Adopt `benchmark_attempt_accounting_v0` in remaining adapter reducers so
   compact ledgers can compare startup, solver, verifier, and official-score
   failures without benchmark-specific label drift.
5. Keep SkillsBench goal-start matrix rows blocked until compact transport
   monitor evidence includes solver output and a new-arm compact artifact.
