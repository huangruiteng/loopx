# Benchmark Architecture

Benchmark support ships as part of LoopX, but it is not part of the generic
control-plane kernel. The package boundary follows ownership:

```text
loopx/
  control_plane/          generic goal, todo, quota, scheduler, and turn rules
  benchmarks/             benchmark-owned projections and qualification logic
    read_models/          public-safe result, comparison, and debug projections
    qualification/        benchmark-specific release qualification
  benchmark_core/         shared harness contracts (stable legacy import path)
  benchmark_adapters/     benchmark-family providers (stable legacy import path)
  benchmark.py            compatibility facade and unextracted legacy behavior
```

## Why Not A Repository-Root `benchmark/` Package?

LoopX publishes only `loopx*` from `pyproject.toml`. A sibling Python package
would therefore be omitted from the distribution unless packaging and release
ownership were split. It would also create a second product namespace for code
whose CLI, state, history, and version lifecycle are still owned by LoopX.

The useful separation is one level lower: `loopx.benchmarks` is a sibling of
`loopx.control_plane`. This keeps one installable product while preventing the
generic control plane from becoming the home for benchmark-specific reducers,
comparison policy, and suite diagnostics.

## Placement Rule

| Code owns | Place it in |
| --- | --- |
| Goal, todo, quota, scheduler, transaction, or public-safety rules used without benchmarks | `loopx/control_plane/` |
| Adapter-neutral benchmark lifecycle, launch, observation, or artifact contracts | `loopx/benchmark_core/` |
| Public-safe benchmark result, comparison, ledger, or diagnostic projections | `loopx/benchmarks/read_models/` |
| Benchmark-specific release qualification from compact outcomes | `loopx/benchmarks/qualification/` |
| A named benchmark family's runner, verifier, image, route, or task convention | `loopx/benchmark_adapters/` |
| CLI parsing and rendering for `loopx benchmark ...` | `loopx/cli_commands/benchmark_*.py` |
| Optional runner distributed on its own lifecycle | a co-located `extensions/<extension-id>/` package or a separate repository |

`loopx.benchmark_core` and `loopx.benchmark_adapters` are established import
surfaces. Renaming them is a compatibility migration, not a directory cleanup;
do it only with explicit aliases, deprecation coverage, and a release window.
New benchmark-owned read models use `loopx.benchmarks` now, and no new
benchmark-specific module should be added under `loopx.control_plane.runtime`.

## Dependency Direction

The control plane defines generic execution and safety contracts. Benchmark
code may consume those contracts. Status, history, and CLI composition may
consume both domains. A benchmark adapter must not redefine quota, todo,
scheduler, or transaction truth, and the control-plane runtime must not import
benchmark-specific read models.

This is a product boundary, not an isolation claim: benchmark execution still
uses LoopX state and receipts, and it remains covered by the same release and
public-evidence policies.

## EdgeBench Provider Boundary

EdgeBench uses the same ownership rule. The built-in
`loopx.benchmark_adapters.edgebench` module owns only LoopX-facing readiness,
single-task planning, and compact result normalization. The upstream SForge
harness remains the runner provider and owns task acquisition, work/judge
container isolation, iterative submissions, hidden evaluation, Docker or
Kubernetes execution, and agent/model launch.

The first integration slice deliberately does not wrap `sforge fetch-tasks`,
`sforge pull`, `sforge serve`, or `sforge run`. Those commands can download
large task assets, pull images, start containers, invoke paid model APIs, and
run for up to 12 hours. LoopX instead exposes fail-closed commands that make the
boundary reviewable before any of those effects:

```bash
loopx benchmark edgebench-preflight --task-id <public-task-id>
loopx benchmark edgebench-run-plan --preflight-json <compact-preflight.json> \
  --agent <agent> --model <model> --run-id <public-run-id>
loopx benchmark edgebench-result-reduce --result-json <final-result.json> \
  --task-id <public-task-id> --run-id <public-run-id>
```

The result reducer accepts only SForge's compact final result shape and keeps
best score, pass rate, best round, submission counts, runtime, timeout, and
resume count. It does not preserve raw agent output, archives, task bodies,
hidden tests, logs, trajectories, credentials, paths, uploads, or leaderboard
claims.
