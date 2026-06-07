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
- `benchmark-report-chain-map-v0.md`: compact reviewer-facing chain map that
  ties `benchmark_run_v0`, `benchmark_result_v0`, `benchmark_comparison_v0`,
  `benchmark_comparison_decision_note_v0`,
  `benchmark_experiment_report_v0`,
  `benchmark_experiment_report_readiness_note_v0`, and
  `benchmark_experiment_report_replay_decision_v0` into one fixture/status
  handoff boundary.
- `benchmark-result-control-plane-score-v0.md`: minimal
  `control_plane_score_core_v0` schema for `benchmark_result_v0`, separating
  official task score from restartability, stale-state avoidance, evidence
  discipline, boundary safety, writeback quality, gate compliance, failure
  attribution, and overhead.
- `mini-control-plane-repair-with-interrupt-v0.md`: deterministic recovery
  fixture slice for `mini_control_plane_repair_with_interrupt_v0`, proving
  worker interruption, stale latest-run avoidance, validation failure capture,
  human-gate resume recheck, and side-effect audit before any real benchmark
  runner path.
- `mini-control-plane-interrupt-comparison-summary-v0.md`: compact fixture-only
  comparison between the non-interrupt and interrupt mini control-plane repair
  modes, preserving official-score versus control-plane-score separation and
  claim boundaries before any status/review-packet projection.
- `mini-control-plane-interrupt-projection-decision-v0.md`: fixture-only
  decision to keep `benchmark_interrupt_comparison_summary_v0` research-only
  until a real consumer or passive benchmark run justifies status/review-packet
  projection.
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
- `terminal-bench-no-submit-approval-packet-v0.md`: smallest
  `terminal_bench_no_submit_approval_packet_v0` operator packet for a future
  no-submit setup check, listing exact candidate commands, forbidden surfaces,
  public artifact shapes, side-effect budgets, stop conditions, and compact
  `benchmark_run_v0` / `benchmark_result_v0` ingestion rules without executing
  the runner path.
- `terminal-bench-no-submit-approval-packet-projection-decision-v0.md`:
  fixture-only decision to keep the no-submit approval packet research/docs-only
  until an agent consumer, approved no-submit setup check, passive wrapper, or
  repeated re-derivation justifies a compact hot-path projection.
- `benchmark-history-reconstructability-v0.md`: restartability fixture proving
  compact benchmark run history can reconstruct official-score,
  control-plane-score, claim-boundary, readiness, authorization,
  replay-decision, next-run-mode, and stop-condition state without raw logs,
  private traces, local artifact paths, chat history, or extra hot-path keys.

## Relationship To Goal Harness Work

The research track should discover what to measure and which public benchmark
protocols are credible. Once the work requires a Goal Harness feature, that
feature should be split into a normal product todo and implemented in the
existing public capability surface, with this folder retaining only the research
motivation, protocol, and result evidence.
