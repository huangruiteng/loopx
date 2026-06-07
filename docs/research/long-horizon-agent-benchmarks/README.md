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
- `operator-simulator-overlay-v0.md`: assisted operator-simulator overlay
  protocol after the passive baseline, including comparison modes, simulator
  matrix, visibility limits, intervention budget, failure taxonomy, and the
  `operator_simulator_run_v0` row shape.
- `benchmark-experiment-report-template-v0.md`: paper-ready
  `benchmark_experiment_report_v0` template that keeps official scores,
  passive control-plane metrics, assisted operator-simulator ablations,
  overhead, failure taxonomy, reproducibility artifacts, claim boundaries, and
  negative results in separate report sections.
- `terminal-bench-official-pilot-readiness-v0.md`: local-only readiness
  fixture for `terminal_bench_official_pilot_decision_packet_v0`, proving the
  `benchmark_result_v0` comparison shell and control-plane checklist before any
  real Terminal-Bench, Docker, Codex/model API, cloud, paid compute, or
  leaderboard path.
- `terminal-bench-no-submit-boundary-probe-v0.md`: local-only
  `runner_boundary_probe_v0` contract that records runner identity, planned
  command boundaries, submit eligibility, future event shape, and hard stop
  conditions without running Terminal-Bench, Harbor, Docker, Codex/model APIs,
  cloud sandboxes, paid compute, or leaderboard upload paths.

## Relationship To Goal Harness Work

The research track should discover what to measure and which public benchmark
protocols are credible. Once the work requires a Goal Harness feature, that
feature should be split into a normal product todo and implemented in the
existing public capability surface, with this folder retaining only the research
motivation, protocol, and result evidence.
