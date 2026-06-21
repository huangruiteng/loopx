# PerfBench Alternate Source Selection V0

Date: 2026-06-12

## Scope

This packet records a no-run PerfBench alternate-source selection attempt after
the owner delegated small public-source decisions to Codex. It checks whether
the previously blocked advertised source has become transport-accessible, and
whether a credible alternate public source can be selected without reading task
rows or running the benchmark.

This packet does not clone PerfBench, read `examples.jsonl`, read benchmark
task rows, read solution/gold/test material, build Docker images, start
containers, run .NET or BenchmarkDotNet, invoke Codex CLI, call model APIs,
generate patches, evaluate patches, upload, submit, touch public ranking
paths, read credentials, inspect raw trajectories, or open screenshots.

## Probe Result

The advertised GitHub repository remains split-brain:

- browser/search metadata can render `https://github.com/glGarg/PerfBench`;
- browser/search metadata reports a repository page, 3 commits, `README.md`,
  `examples.jsonl`, and a README heading for "PerfBench: Performance Issue
  Benchmark for Software Engineering Agents";
- the compact browser metadata summary hash recorded for this packet is
  `658416db34c02ff9012911fe6d4b0039d3660c56eaa0a7fb3662e359564dbb9c`;
- the same source remains unavailable through reproducible transport surfaces.

Transport probes:

| Probe | Target | Result |
| --- | --- | --- |
| git HEAD | `https://github.com/glGarg/PerfBench.git` | repository not found |
| GitHub repository API | `https://api.github.com/repos/glGarg/PerfBench` | HTTP 404 |
| GitHub contents API | `https://api.github.com/repos/glGarg/PerfBench/contents/` | HTTP 404 |
| Raw README | `https://raw.githubusercontent.com/glGarg/PerfBench/main/README.md` | HTTP 404 |
| Raw examples HEAD | `https://raw.githubusercontent.com/glGarg/PerfBench/main/examples.jsonl` | HTTP 404 |

Repository-search probes through the public GitHub API returned zero
repository matches for:

- `PerfBench performance bug benchmark`;
- `glGarg PerfBench`;
- `PerfBench Performance Issue Benchmark Software Engineering Agents`.

Unauthenticated GitHub code search is not usable as a source authority here
because it requires authentication and would still be insufficient without a
transport-accessible repository.

## Selection Decision

No alternate public source is selected.

Reason: no transport-reachable official or equivalent public source was found.
The browser-rendered repository metadata is useful evidence that the benchmark
surface exists, but it is not sufficient for a reproducible runner/source
preflight because it cannot provide a pin, file inventory through API/git, raw
README, task-row metadata, or runner scripts through normal transport.

PerfBench remains a high-value benchmark candidate because of its low reported
success rates and performance-validation focus, but it is not runner-source
ready from this machine.

## Executable Fixture

The executable fixture is:

```bash
python3 examples/perfbench-alternate-source-selection-smoke.py
```

It emits:

- `perfbench_alternate_source_selection_v0`;
- a no-run `benchmark_run_v0` projection with
  `mode=alternate_source_selection_no_run`.

The `benchmark_run_v0` projection records:

- advertised browser metadata visible;
- git/API/raw transports unavailable;
- no alternate official repository found;
- no alternate source selected;
- runner source not ready;
- no task rows read;
- no Docker, Codex/model, upload, submit, or public ranking path.

## Validation

Targeted validation:

```bash
python3 examples/perfbench-alternate-source-selection-smoke.py
python3 -m py_compile examples/perfbench-alternate-source-selection-smoke.py
loopx check \
  --scan-path examples/perfbench-alternate-source-selection-smoke.py \
  --scan-path docs/research/long-horizon-agent-benchmarks/perfbench-alternate-source-selection-v0.md \
  --scan-path docs/research/long-horizon-agent-benchmarks/README.md
```

The fixture asserts that public outputs do not contain local paths,
credentials, raw task rows, raw benchmark artifacts, solution material, test
bodies, Docker output, Codex auth material, sessions, raw trajectories,
screenshots, command argv, or environment dumps.

## Next Safe Step

Do not spend more automatic turns on PerfBench unless one of these changes:

1. the official repository becomes reachable through git/API/raw transport;
2. the authors publish a canonical alternate source;
3. the owner provides a public mirror and explicitly accepts it as an
   equivalent non-official source.

Until then, the benchmark-readiness lane should either request a separate
execution-scope decision for the already prepared SWE-Bench Pro one-instance
pilot, or move to another low-success long-horizon benchmark with a reachable
public runner.
