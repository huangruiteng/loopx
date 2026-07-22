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
