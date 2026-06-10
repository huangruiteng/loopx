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

- `benchmark-program-current-state-handoff-v0.md`: compact current-state
  runbook for fresh workers, summarizing the active benchmark evidence layer,
  docs-only projection decisions, allowed next transitions, and stop
  conditions without adding hot-path projection keys.
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
  protocol after the passive baseline, including active user injection,
  comparison modes, simulator matrix, visibility limits, intervention budget,
  failure taxonomy, and the `operator_simulator_run_v0` row shape.
- `active-user-assisted-pilot-v0.md`: deterministic active-user assisted pilot
  shape for a previously failed compact Terminal-Bench case, keeping proactive
  user interventions, no-oracle audits, frequency budgets, and official score
  separation in one public-safe fixture. The Terminal-Bench wrapper now also
  has a deterministic active-user observation fixture that proves a worker can
  observe one post-start simulator intervention without running the real
  benchmark or claiming an official score.
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
- `terminal-bench-treatment-arm-taxonomy-v0.md`: no-run taxonomy correction
  separating `hardened_codex_baseline`, Codex runtime `codex_goal_mode`,
  true `codex_goal_harness`, and `passive_goal_harness_observer`. It records
  that `create_goal` / `update_goal` are Codex runtime goal-tool calls, not
  Goal Harness CLI calls, and requires future results to count
  `codex_runtime_goal_tool_calls`, `goal_harness_cli_calls`,
  `goal_harness_state_reads`, and `goal_harness_state_writes` separately.
- `terminal-bench-goal-harness-access-packet-v0.md`: no-run access-packet and
  interaction-counter fixture for the true `codex_goal_harness` arm. It defines
  the public worker packet, keeps Codex runtime goal tools separate from Goal
  Harness CLI/state calls, and adds compact `benchmark_run_v0` counter
  projection before any fake-worker or real benchmark repeat.
- `terminal-bench-goal-harness-cli-bridge-contract-v0.md`: host-agent bridge
  contract for the future true `codex_goal_harness` arm. It maps
  `status`, `quota_should_run`, `todo_list`, `history`, `check`, and
  `append_benchmark_run` to executable Goal Harness CLI templates, with a smoke
  that runs those templates against a temporary registry. The same contract is
  now wired into `goal-harness benchmark run terminal-bench --mode
  codex-goal-harness --cli-bridge-contract`, producing compact runner-side
  bridge availability and `goal_harness_cli_calls.total=6` counters while
  keeping Terminal-Bench/Codex/model execution disabled.
- `terminal-bench-codex-goal-harness-active-cli-bridge-v0.md`: core
  `codex_goal_harness` treatment surface. It adds
  `goal_harness_cli_bridge_enabled=true` to `GoalHarnessManagedCodex`, injects
  worker-side `goal-harness ... status/quota/todo/history/check/append` command
  templates into the Codex instruction, and keeps worker in-case
  `goal_harness_cli_calls.total=6` separate from runner-side bridge probes. It
  also exposes the no-run `--preflight-guard --active-cli-bridge` route for the
  next private repeat and records a claim gate requiring nonzero worker-side
  Goal Harness CLI calls before any in-case use claim.
- `terminal-bench-codex-goal-harness-fake-worker-v0.md`: first executable
  fixture mode for the true `codex_goal_harness` arm:
  `goal-harness benchmark run terminal-bench --mode codex-goal-harness
  --fake-worker`. It appends a no-run/no-submit `benchmark_run_v0` event with
  nonzero Goal Harness CLI/state interaction counters, while keeping Codex
  runtime goal-tool calls separate and preserving no-uplift/no-leaderboard
  boundaries.
- `terminal-bench-codex-goal-harness-custom-agent-v0.md`: custom-agent prompt
  surface for the true `codex_goal_harness` arm. It wires the Goal Harness
  access packet into `GoalHarnessManagedCodex` through
  `goal_harness_mode=codex_goal_harness`, adds compact trace-audited counter
  extraction, and verifies the Harbor command preview before any real repeat.
- `terminal-bench-codex-goal-harness-preflight-guard-v0.md`: no-upload
  preflight guard for `goal-harness benchmark run terminal-bench --mode
  codex-goal-harness --preflight-guard`. It checks runner/Codex/local execution
  surfaces, access-packet prompt injection, trace-counter contract availability,
  and compact preflight/status projection without running Harbor tasks, Codex
  workers, model APIs, uploads, or leaderboard paths.
- `terminal-bench-runner-mode-contract-v0.md`: no-run mode contract for the
  future `goal-harness benchmark run terminal-bench ...` wrapper, separating
  parent runner control-plane behavior from per-case worker modes
  `hardened-codex` and `codex-goal-harness`. The contract treats hardened
  Codex as the true paired baseline for this experiment and
  `codex-goal-harness` as the core `model + harness` pair.
- `terminal-bench-official-hard-case-selection-v0.md`: no-run selection
  contract that moves the next evidence target from `terminal-bench-sample@2.0`
  to official `terminal-bench@2.0`, selects a three-case hard/long-horizon
  primary batch (`fix-code-vulnerability`, `modernize-scientific-stack`, and
  `llm-inference-batching-scheduler`), defines a backup queue, and preserves
  paired-run invariants for `hardened-codex` versus `codex-goal-harness`,
  claim boundaries, metrics, and stop conditions before any full 89-task run or
  leaderboard path.
- `agents-last-exam-triage-v0.md`: source-backed triage note adding Agents'
  Last Exam to the benchmark backlog. It records the Xiaohongshu discovery
  signal, verifies the arXiv and public GitHub surfaces, and keeps ALE behind
  the current Terminal-Bench paired pilot until an adapter dossier exists.
- `terminal-bench-cli-dry-run-fake-worker-v0.md`: public CLI skeleton for
  `goal-harness benchmark run terminal-bench`. The command defaults to dry-run,
  exposes `hardened-codex`, `codex-goal-harness`, passive observation, and
  `goal-harness-managed-codex`, and can append only compact fixture
  `benchmark_run_v0` rows when `--execute` is passed. The current fake-worker
  path is allowed only for managed mode and records
  `goal_harness_managed_codex_fake_worker_wrapper` without invoking real
  Harbor, Terminal-Bench, Docker, Codex, model APIs, uploads, or leaderboard
  paths.
- `terminal-bench-managed-real-run-preflight-guard-v0.md`: no-run guard packet
  for the first managed Goal Harness Terminal-Bench case. It rechecks runner,
  local Docker/Colima, Codex CLI, auth-surface-name, no-upload, and artifact
  redaction boundaries, appends only a compact readiness `benchmark_run_v0`
  when executed, and stops before Harbor, Terminal-Bench, Codex worker,
  benchmark task container, model API, uploads, or leaderboard paths.
- `terminal-bench-managed-codex-custom-agent-v0.md`: first concrete Harbor
  custom-agent bridge for the core managed treatment, using
  `--agent-import-path goal_harness.terminal_bench_agent:GoalHarnessManagedCodex`
  to subclass Harbor's built-in Codex adapter, inject a minimal Goal Harness
  policy envelope, defer public-safe managed metadata until Codex post-run
  session ingestion, and preserve no-upload/private pilot boundaries while
  stopping before leaderboard, uplift, or paper-ready claims.
- `benchmark-history-reconstructability-v0.md`: restartability fixture proving
  compact benchmark run history can reconstruct official-score,
  control-plane-score, claim-boundary, readiness, authorization,
  replay-decision, next-run-mode, and stop-condition state without raw logs,
  private traces, local artifact paths, chat history, or extra hot-path keys.
- `benchmark-restart-actionability-v0.md`: restarted-worker actionability
  fixture proving a compact reconstructed decision can produce exactly one
  bounded local fixture command or a public-safe blocker while preserving
  fixture-only authorization, no-leaderboard claims, and real-run stop
  conditions.
- `benchmark-restart-actionability-projection-decision-v0.md`: fixture-only
  decision to keep `benchmark_restart_actionability_v0` research/docs-only
  until a real restarted-worker consumer, approved no-submit setup evidence, or
  repeated re-derivation justifies a compact hot-path projection.

## Relationship To Goal Harness Work

The research track should discover what to measure and which public benchmark
protocols are credible. Once the work requires a Goal Harness feature, that
feature should be split into a normal product todo and implemented in the
existing public capability surface, with this folder retaining only the research
motivation, protocol, and result evidence.
