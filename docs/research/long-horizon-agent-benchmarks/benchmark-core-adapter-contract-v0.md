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

## First Extraction Slice

The first refactor should keep runtime behavior stable:

1. Add the shared `benchmark_core` package.
2. Project existing lifecycle state into canonical lifecycle fields.
3. Add a focused smoke that proves `process_started` is not case entry.
4. Move one mature adapter slice next, starting with SkillsBench reducer/route
   contracts before adding more benchmark features.
