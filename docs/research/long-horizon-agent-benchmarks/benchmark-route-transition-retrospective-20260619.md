# Benchmark Route Transition Retrospective 2026-06-19

Status: route-transition retrospective; no benchmark score evidence.

## Summary

Goal Harness moved the near-term benchmark program from local-Codex /
remote-executor split-control to a dedicated cloud-host Codex route.

The new default is simple:

1. Codex CLI runs on the dedicated benchmark host.
2. Benchmark runners, Docker-compatible runtime, task data, raw artifacts, and
   compact reducers stay on that host.
3. Goal Harness records only control-plane truth: todos, gates, quota, compact
   evidence handles, ledger updates, docs, and public/private boundaries.

The old split-control path remains useful as a research asset for
credential-constrained or shared-host settings, but it should no longer absorb
mainline benchmark attention while a dedicated host can answer the execution
question directly.

## Why Split-Control Was Hard

Split-control solved a real safety problem: keep Codex auth, model invocation,
and Goal Harness state local while a remote machine provides Docker, runner
dependencies, task-data staging, bounded execution, and compact result
reduction.

That safety boundary created several useful contracts, but it also multiplied
the surfaces that could fail before a real benchmark run:

- the local driver had to materialize safe requests;
- the remote side had to expose command/file execution without becoming an
  agent-auth environment;
- launch handles had to prove runner acceptance without leaking raw task text,
  logs, trajectories, verifier tails, credentials, or private paths;
- readiness checks could prove bridge transport while still not proving a
  real benchmark task was runnable;
- missing remote Codex/Codex-ACP could be misclassified as a blocker even
  though, in split-control, remote Codex was intentionally absent.

With a dedicated host, these are no longer the default bottlenecks. The
benchmark question should move back to source freshness, runner setup,
container/runtime compatibility, task-data gates, no-upload execution, compact
result reduction, and attribution.

## Reusable Assets To Keep

Keep split-control pieces only when they protect a durable public contract:

- source and task-data boundary language;
- compact launch/result handle shapes;
- result reducer and ledger schemas;
- route labels such as `cloud_codex_default`, `split_control_fallback`, and
  `upstream_adapter_branch`;
- smokes that prove a public/private boundary or a reusable route contract;
- posthoc parity ideas for checking what a benchmark run actually saw.

These assets can still help cloud-host runs because compact reducers, ledger
schemas, and no-upload boundaries are independent of where Codex runs.

## Mainline Exit Criteria

Do not add more split-control bridge layers on the main benchmark path unless
the cloud-host route is blocked by a concrete auth, policy, or host gate.

After at least one cloud-host smoke or mini-pair produces compact evidence, run
a split-control inventory:

| Asset class | Default action |
| --- | --- |
| Durable reducer/schema/boundary smoke | Retain in mainline. |
| Historical route note or blocker packet | Keep in research docs if indexed. |
| Bridge probe that only proves transport | Move to an experimental branch or delete. |
| Benchmark-fork patch not needed by upstream-close cloud runs | Move to adapter branch or delete. |
| Raw/private evidence, logs, trajectories, host details | Keep out of public repo. |

## Branch Hygiene Runbook

For external benchmark repositories:

- track upstream `main` or a pinned upstream commit;
- keep a clean local branch that can be reset/rebased from upstream;
- keep internal adapter changes on a tiny, named adapter branch;
- prefer wrapper scripts, sidecars, runbooks, and reducers outside the upstream
  source tree;
- do not patch scorer logic, task definitions, prompts, or official runner
  behavior unless the patch is upstreamable and separately reviewed;
- do not mix Goal Harness bridge probes, raw logs, credentials, local paths,
  or private host details into benchmark forks.

For internal benchmark workspaces:

- keep private raw artifacts on the benchmark host;
- write compact public-safe handles back to Goal Harness;
- label runs by route, for example `cloud_codex_default` or
  `split_control_fallback`;
- keep upload, leaderboard, and public-claim decisions as explicit gates.

## Next Todo Mapping

- P0: run the first cloud-host benchmark smoke batch after remote Codex auth is
  complete.
- P0: keep ALE task-data access and disk budget as an explicit user gate before
  formal ALE execution.
- P1: use this retrospective as the runbook for branch hygiene and route
  transition.
- P2: after cloud-host smoke evidence exists, retire or move split-control
  bridge code that no longer supports the default route.

## Claim Boundary

This retrospective may claim only that the benchmark execution route changed
and that split-control is now fallback/research. It must not claim benchmark
uplift, official task success, or Goal Harness effectiveness until compact
benchmark evidence exists.
