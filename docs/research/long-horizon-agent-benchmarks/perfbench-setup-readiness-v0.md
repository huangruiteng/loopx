# PerfBench Setup Readiness

Date: 2026-06-12

Scope: public-safe setup-readiness scan for PerfBench. This scan used the
paper, Microsoft Research publication page, GitHub web metadata exposed in
search/browser rendering, and no-run source transport probes.

It did not clone benchmark task data, run Docker, run .NET builds or
benchmarks, invoke Codex or model APIs, generate or evaluate patches, read
task body material, read solution/test content, inspect raw trajectories, open
screenshots, upload, submit, or touch credentials.

## Public Sources

- Paper HTML: https://arxiv.org/html/2509.24091v1
- Paper abstract: https://arxiv.org/abs/2509.24091
- Microsoft Research page:
  https://www.microsoft.com/en-us/research/publication/perfbench-can-agents-resolve-real-world-performance-bugs/
- Advertised benchmark repository:
  https://github.com/glGarg/PerfBench

## Difficulty And Fit

PerfBench is a strong LoopX-style benchmark if the runner source becomes
available. The paper defines 81 real-world .NET performance bug-fixing tasks
from popular GitHub repositories. Tasks require agents to reason about
non-functional performance problems, generate BenchmarkDotNet benchmarks, and
validate improvements by comparing execution metrics for the developer fix and
the agent fix.

This is a good match for LoopX because the benchmark stresses:

- long multi-step diagnosis rather than one-shot functional patching;
- measurable validation, regression avoidance, and claim discipline;
- verbose benchmark output summarization;
- cost/token/step tracking;
- failure attribution when performance improves locally but does not satisfy
  the benchmark success definition.

Public difficulty is high enough to be useful. The paper reports baseline
OpenHands at `1.2%` success with GPT-4.1 and `3.7%` with Claude Sonnet 4, while
OpenHands-Perf-Agent reaches `14.8%` with GPT-4.1 and `19.7%` with Claude
Sonnet 4. No direct Codex CLI score was found in this scan.

## Setup Findings

The benchmark is not currently local-runner-ready from this machine because the
advertised source repository is not transport-accessible, even though browser
metadata/search rendering exposes a repository page and file names.

Observed source access probes:

- `git clone --depth 1 https://github.com/glGarg/PerfBench.git`: repository not
  found;
- `git ls-remote https://github.com/glGarg/PerfBench.git HEAD`: repository not
  found;
- `https://raw.githubusercontent.com/glGarg/PerfBench/main/README.md`: HTTP
  404;
- `https://raw.githubusercontent.com/glGarg/PerfBench/main/examples.jsonl`:
  HTTP 404;
- `https://api.github.com/repos/glGarg/PerfBench`: HTTP 404;
- `https://api.github.com/repos/glGarg/PerfBench/contents/`: HTTP 404.

The browser-rendered GitHub page/search metadata showed a minimal repository
surface with `README.md` and `examples.jsonl`, and the README text states that
PerfBench contains 82 extracted issues while the paper and README dataset
overview say the benchmark consists of 81 instances. This count mismatch is
not blocker by itself, but it reinforces that the executable source should be
pinned before any run claims.

## Execution Boundary

Do not attempt a PerfBench run until source transport is available and pinned.
Specifically, stop before:

- cloning or consuming task rows from non-official mirrors;
- reading `examples.jsonl` task body/problem statement rows;
- Docker image build/start;
- .NET build/test/BenchmarkDotNet execution;
- OpenHands/Codex/model invocation;
- generated benchmark or patch evaluation;
- upload, leaderboard, submit, raw trajectories, screenshots, credentials, or
  hidden references.

## Decision

PerfBench stays on the benchmark shortlist as a high-value performance
validation lane, but it is blocked for local/Docker setup-readiness today
because the advertised repository cannot be fetched through git/raw/API. The
next autonomous benchmark-readiness scan should move to SWE-Bench Pro public
unless the owner provides a reachable official PerfBench source route or
explicitly approves a different public source.
