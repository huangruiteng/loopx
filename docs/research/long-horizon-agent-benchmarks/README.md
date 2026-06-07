# Long-Horizon Agent Benchmark Research

This topic folder owns Goal Harness research on public long-horizon agent
benchmarks, external leaderboard strategy, operator-simulator study design, and
paper-oriented experiment planning.

Keep this folder focused on research artifacts:

- benchmark and paper dossiers;
- runner setup notes and legality/protocol reviews;
- official leaderboard versus passive-control-plane versus assisted-simulator
  experiment plans;
- result summaries, failure taxonomies, and publication-readiness notes.

Do not implement Goal Harness product capability here. Foundational capability
work still belongs in the existing code, examples, and contract documents:

- CLI, quota, status, history, registry, and dashboard behavior belongs under
  `goal_harness/`, `scripts/`, and the existing contract docs.
- Deterministic smoke or regression coverage belongs under `examples/`.
- General Goal Harness control-plane specs belong under top-level `docs/`.
- This folder may link to those artifacts, but should not become a parallel
  implementation or a second product-spec tree.

## Current Artifacts

- `roadmap.md`: benchmark selection, passive baseline, operator-simulator, and
  publication-readiness roadmap.
- `paper-runner-dossier.md`: first evidence-backed ranking of benchmark papers,
  runner surfaces, Codex compatibility signals, and the next Terminal-Bench
  probe slice.
- `terminal-bench-probe-v0.md`: first public-safe runner-boundary probe for
  Terminal-Bench and Harbor, including Codex CLI integration surfaces, output
  files for passive Goal Harness ingestion, and the stop condition before paid
  or leaderboard execution.
- `benchmark-run-v0-ingest.md`: first passive `benchmark_run_v0` ingestion
  contract for Harbor job outputs, with deterministic fixture coverage and no
  default Docker, model, cloud, or leaderboard execution.
- `passive-baseline-protocol-v0.md`: paired bare Codex CLI versus passive Goal
  Harness wrapper protocol, connecting local `benchmark_result_v0` comparison
  evidence to compact `benchmark_run_v0` history rows without operator
  simulation.
- `terminal-bench-official-pilot-readiness-v0.md`: local-only readiness
  fixture for `terminal_bench_official_pilot_decision_packet_v0`, proving the
  `benchmark_result_v0` comparison shell and control-plane checklist before any
  real Terminal-Bench, Docker, Codex/model API, cloud, paid compute, or
  leaderboard path.

## Relationship To Goal Harness Work

The research track should discover what to measure and which public benchmark
protocols are credible. Once the work requires a Goal Harness feature, that
feature should be split into a normal product todo and implemented in the
existing public capability surface, with this folder retaining only the research
motivation, protocol, and result evidence.
