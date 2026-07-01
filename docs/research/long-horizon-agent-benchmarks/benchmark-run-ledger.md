# Benchmark Run Ledger

This file is generated from `benchmark_run_ledger_v0`. It records compact
benchmark case outcomes and artifact references; it must not contain raw
logs, task prompts, trajectories, credentials, uploads, or absolute paths.
Archived runs remain in JSON for traceability but are excluded from the
default case decisions, repair backlog, and active runs table.

- schema_version: `benchmark_run_ledger_v0`
- updated_at: `2026-06-30T21:15:57+08:00`
- active_case_count: `28`
- active_run_count: `101`
- archived_run_count: `193`

## Case Decisions

| Benchmark | Case | Decision | Product Pair | Case Routing | Runs |
| --- | --- | --- | --- | --- | --- |
| `skillsbench-cloud-oracle-sanity@v0` | `hello-world` | `single_arm_recorded` | - | - | `1` |
| `skillsbench@1.1` | `3d-scan-calc` | `baseline_passed_not_current_treatment_priority` | - | - | `1 active / 12 archived` |
| `skillsbench@1.1` | `ada-bathroom-plan-repair` | `baseline_failed_treatment_candidate` | - | - | `1 active / 5 archived` |
| `skillsbench@1.1` | `adaptive-cruise-control` | `baseline_runner_or_setup_repair_required` | - | - | `1 active / 2 archived` |
| `skillsbench@1.1` | `citation-check` | `baseline_passed_not_current_treatment_priority` | - | - | `1 active / 15 archived` |
| `swe-marathon` | `find-network-alignments` | `baseline_failed_treatment_candidate` | - | - | `1` |
| `swe-marathon` | `rust-c-compiler` | `single_arm_recorded` | - | - | `2` |
| `swe-marathon` | `zstd-decoder` | `paired_treatment_regressed` | - | `case_exception_research` | `4` |
| `terminal-bench-worker-materialization@v0` | `nginx-request-logging` | `single_arm_recorded` | - | - | `2` |
| `terminal-bench@2.0` | `build-cython-ext` | `baseline_passed_not_current_treatment_priority` | - | - | `11` |
| `terminal-bench@2.0` | `cobol-modernization` | `paired_baseline_solved_treatment_preserved` | - | - | `2` |
| `terminal-bench@2.0` | `compile-compcert` | `baseline_passed_not_current_treatment_priority` | - | - | `1` |
| `terminal-bench@2.0` | `financial-document-processor` | `baseline_passed_not_current_treatment_priority` | - | - | `2` |
| `terminal-bench@2.0` | `fix-code-vulnerability` | `baseline_passed_not_current_treatment_priority` | - | - | `1` |
| `terminal-bench@2.0` | `git-multibranch` | `paired_baseline_solved_treatment_preserved` | - | - | `5` |
| `terminal-bench@2.0` | `headless-terminal` | `paired_no_score_uplift` | - | `bridge_connected_no_uplift` | `5` |
| `terminal-bench@2.0` | `install-windows-3.11` | `paired_treatment_worker_verifier_alignment_required` | - | - | `4` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `paired_baseline_solved_treatment_preserved` | - | - | `5` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `paired_result_requires_attribution` | - | `timeout_tier_policy_candidate` | `9` |
| `terminal-bench@2.0` | `merge-diff-arc-agi-task` | `baseline_passed_not_current_treatment_priority` | - | - | `1` |
| `terminal-bench@2.0` | `mteb-retrieve` | `paired_baseline_environment_setup_repair_required` | - | - | `4` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `paired_baseline_solved_treatment_preserved` | - | - | `19` |
| `terminal-bench@2.0` | `nginx-request-logging` | `paired_baseline_solved_treatment_preserved` | - | - | `8` |
| `terminal-bench@2.0` | `path-tracing` | `baseline_passed_not_current_treatment_priority` | - | - | `2` |
| `terminal-bench@2.0` | `pytorch-model-recovery` | `paired_no_score_uplift_exception_research_required` | - | `case_exception_research` | `3` |
| `terminal-bench@2.0` | `regex-log` | `paired_baseline_solved_treatment_preserved` | - | - | `2` |
| `terminal-bench@2.0` | `sqlite-db-truncate` | `baseline_passed_not_current_treatment_priority` | - | - | `1` |
| `terminal-bench@2.0` | `train-fasttext` | `single_arm_recorded` | - | - | `2` |

## Repair Backlog

| Priority | Benchmark | Case | Arm | Repair Class | Failure | Repair Profile | Next Action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `P0` | `terminal-bench@2.0` | `mteb-retrieve` | `codex_goal_mode_baseline` | `benchmark_environment_setup_contract` | `environment_setup_failed_before_worker` | benchmark_environment_setup_contract | repair or preflight the benchmark environment setup layer before rerunning this case; the failure occurred before Codex/worker startup, so require compact environment setup read... |
| `P0` | `terminal-bench@2.0` | `mteb-retrieve` | `codex_loopx_treatment` | `benchmark_environment_setup_contract` | `environment_setup_failed_before_worker` | benchmark_environment_setup_contract | repair or preflight the benchmark environment setup layer before rerunning this case; the failure occurred before Codex/worker startup, so require compact environment setup read... |
| `P0` | `terminal-bench@2.0` | `nginx-request-logging` | `hardened_codex_worker_materialization_probe` | `runner_codex_cli_materialization` | `codex_cli_not_on_path` | runner_codex_cli_materialization | materialize an existing Codex CLI on the worker PATH or provide an equivalent launcher before rerunning; require a compact setup diagnostic that proves the Codex preflight reach... |
| `P0` | `terminal-bench@2.0` | `make-doom-for-mips` | `codex_loopx_treatment` | `verifier_attribution_required` | `score_failure_unattributed` |  | collect finer compact failure attribution before launching treatment |
| `P0` | `terminal-bench@2.0` | `install-windows-3.11` | `codex_loopx_treatment` | `worker_verifier_alignment` | `worker_validation_scope_ambiguous_official_score_failure` |  | align worker self-validation with verifier-facing compact evidence before repeating |
| `P1` | `swe-marathon` | `zstd-decoder` | `swe_marathon_loopx_prompt_polling_treatment_10800` | `case_exception_research` | `agent_exception_before_solution_completion` |  | inspect compact exception attribution and form a case-level intervention hypothesis |
| `P1` | `terminal-bench@2.0` | `pytorch-model-recovery` | `codex_goal_mode_baseline` | `case_exception_research` | `agent_exception_before_solution_completion` |  | inspect compact exception attribution and form a case-level intervention hypothesis |
| `P1` | `terminal-bench@2.0` | `pytorch-model-recovery` | `codex_loopx_treatment` | `case_exception_research` | `agent_exception_before_solution_completion` |  | inspect compact exception attribution and form a case-level intervention hypothesis |
| `P1` | `terminal-bench@2.0` | `make-doom-for-mips` | `codex_goal_mode_baseline` | `case_timeout_research` | `agent_timeout_before_solution_completion` |  | inspect compact timeout context and decide whether the run needs a private long-horizon timeout tier |

## Archived Run Summary

| Benchmark | Archived Cases | Archived Runs |
| --- | --- | --- |
| `skillsbench@1.1` | `43` | `193` |

## Runs

| Benchmark | Case | Arm | Attempt | Score | First Success Round | Round Rewards | Failure | Artifact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `skillsbench-cloud-oracle-sanity@v0` | `hello-world` | `oracle_uv_prewarm_no_upload_sanity` | `oracle_sanity_attempt` | `1.0` | `1` | `1:1*` | `none` | `` |
| `skillsbench@1.1` | `3d-scan-calc` | `codex-app-server-goal-baseline` | `case_attempt` | `1.0` | `` | `` | `none` | `runs/skillsbench-3d-scan-calc-native-goal-revtunnel-pr941-real-20260630T093746Z/benchmark_run.compact.json` |
| `skillsbench@1.1` | `ada-bathroom-plan-repair` | `codex_app_server_goal_baseline` | `case_attempt` | `0.0` | `` | `` | `official_verifier_solution_failure` | `skillsbench-revtunnel-appgoal-batch3-20260630T1005Z/ada-bathroom-plan-repair/benchmark_run.compact.json` |
| `skillsbench@1.1` | `adaptive-cruise-control` | `codex_app_server_goal_baseline` | `` | `missing` | `` | `` | `skillsbench_native_goal_worker_failed_codex_app_server_turn_timeout` | `skillsbench-revtunnel-appgoal-batch3-20260630T1005Z/adaptive-cruise-control/benchmark_run.compact.json` |
| `skillsbench@1.1` | `citation-check` | `codex_app_server_goal_baseline` | `case_attempt` | `1.0` | `` | `` | `none` | `skillsbench-revtunnel-appgoal-batch3-20260630T1005Z/citation-check/benchmark_run.compact.json` |
| `swe-marathon` | `find-network-alignments` | `swe_marathon_host_codex_app_server_goal_baseline` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/parallel-benchmark-20260620T131254Z/swe-marathon-find-network-alignments-host-app-server-goal-r6/harbor_job_result.compact.json` |
| `swe-marathon` | `rust-c-compiler` | `swe_marathon_host_codex_app_server_goal_prewarmed_rerun` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/parallel-benchmark-20260620T235333Z/swe-marathon-rust-c-compiler-app-server-r2/harbor_job_result.compact.json` |
| `swe-marathon` | `rust-c-compiler` | `swe_marathon_host_codex_loopx_packet_only_observation` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/swe-marathon-rust-c-compiler-treatment-20260621T060729Z/jobs/swe-marathon-rust-c-compiler-gh-treatment-r1/harbor_job_result.compact.json` |
| `swe-marathon` | `zstd-decoder` | `swe_marathon_host_codex_app_server_goal_baseline` | `` | `1.0` | `` | `` | `none` | `cloud-ecs/swe-marathon-zstd-decoder-baseline-r2-20260621T062826Z/jobs/swe-marathon-zstd-decoder-app-server-baseline-r2/harbor_job_result.compact.json` |
| `swe-marathon` | `zstd-decoder` | `swe_marathon_loopx_prompt_polling_treatment` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/swe-marathon-zstd-decoder-gh-prompt-polling-pr433-20260621T110515Z/harbor_job_result.pr438.compact.json` |
| `swe-marathon` | `zstd-decoder` | `swe_marathon_loopx_prompt_polling_treatment_10800` | `` | `0.0` | `` | `` | `agent_exception_before_solution_completion` | `cloud-ecs/swe-marathon-zstd-decoder-gh-prompt-polling-10800-20260621T204620/harbor_job_result.compact.json` |
| `swe-marathon` | `zstd-decoder` | `swe_marathon_loopx_prompt_polling_treatment_10800_pr467` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench-worker-materialization@v0` | `nginx-request-logging` | `hardened_codex_worker_materialization_runtime_probe` | `` | `missing` | `` | `` | `not_applicable_worker_materialization_probe` | `` |
| `terminal-bench-worker-materialization@v0` | `nginx-request-logging` | `hardened_codex_worker_materialization_runtime_probe` | `` | `missing` | `` | `` | `not_applicable_worker_materialization_probe` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `codex_model_access_unsupported_for_account` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_failed_before_worker_start` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `codex_cli_not_on_path` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `build-cython-ext` | `terminal_bench_host_codex_app_server_goal_baseline` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/parallel-benchmark-20260620T131254Z/terminal-bench-build-cython-ext-host-app-server-goal-r9/terminal_official_metadata.compact.json` |
| `terminal-bench@2.0` | `build-cython-ext` | `terminal_bench_host_codex_app_server_goal_baseline` | `` | `1.0` | `` | `` | `none` | `cloud-ecs/parallel-benchmark-20260621T020900Z/terminal-bench-build-cython-ext-app-server-pr335-r1/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `build-cython-ext` | `terminal_bench_host_codex_app_server_goal_completion_aware` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/parallel-benchmark-20260621T022100Z/terminal-bench-build-cython-ext-app-server-pr336-r2/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex-native-goal` | `` | `1.0` | `` | `` | `none` | `terminal-bench/build-cython-ext/pr335-r1/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `build-cython-ext` | `codex-native-goal-completion-aware` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `terminal-bench/build-cython-ext/pr336-r2/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `build-cython-ext` | `terminal_bench_host_codex_app_server_goal_observe_only` | `` | `1.0` | `` | `` | `none` | `cloud-ecs/parallel-benchmark-20260621T203200Z/terminal-bench-build-cython-ext-app-server-observe-pr346-r1/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `cobol-modernization` | `hardened_codex_baseline` | `` | `1.0` | `` | `` | `none` | `baseline.compact.json` |
| `terminal-bench@2.0` | `cobol-modernization` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `treatment.compact.json` |
| `terminal-bench@2.0` | `compile-compcert` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `financial-document-processor` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `codex_model_access_unsupported_for_account` | `` |
| `terminal-bench@2.0` | `financial-document-processor` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `fix-code-vulnerability` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `git-multibranch` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `treatment_benchmark_run.compact.json` |
| `terminal-bench@2.0` | `git-multibranch` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_failed_before_worker_start` | `` |
| `terminal-bench@2.0` | `git-multibranch` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `codex_cli_missing_setup_preflight` | `` |
| `terminal-bench@2.0` | `git-multibranch` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `git-multibranch` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `headless-terminal` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `score_failure_unattributed` | `` |
| `terminal-bench@2.0` | `headless-terminal` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `headless-terminal` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `worker_bridge_connected_official_score_failure` | `` |
| `terminal-bench@2.0` | `headless-terminal` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `headless-terminal` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `install-windows-3.11` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `none` | `treatment_benchmark_run_v0.public.json` |
| `terminal-bench@2.0` | `install-windows-3.11` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `none` | `baseline_benchmark_run_v0.public.json` |
| `terminal-bench@2.0` | `install-windows-3.11` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `worker_self_validation_official_score_mismatch` | `treatment_benchmark_run_v0.after-mismatch-attribution.public.json` |
| `terminal-bench@2.0` | `install-windows-3.11` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `worker_validation_scope_ambiguous_official_score_failure` | `treatment_benchmark_run_v0.after-validation-scope.public.json` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `large-scale-text-editing` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_timeout_before_solution_completion` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_timeout_before_solution_completion` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_timeout_before_solution_completion` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_timeout_before_solution_completion` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `score_failure_unattributed` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_timeout_before_solution_completion` | `` |
| `terminal-bench@2.0` | `make-doom-for-mips` | `loopx-managed-codex` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `merge-diff-arc-agi-task` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `mteb-retrieve` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `environment_setup_failed_before_worker` | `` |
| `terminal-bench@2.0` | `mteb-retrieve` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `environment_setup_failed_before_worker` | `` |
| `terminal-bench@2.0` | `mteb-retrieve` | `harbor_observed` | `` | `0.0` | `` | `` | `not_applicable_environment_setup_probe` | `` |
| `terminal-bench@2.0` | `mteb-retrieve` | `harbor_observed` | `` | `0.0` | `` | `` | `not_applicable_environment_setup_probe` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `codex_model_access_unsupported_for_account` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `missing` | `` | `` | `stale_active_job_without_trial_result` | `post-launch-reconcile.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `missing` | `` | `` | `stale_active_job_without_trial_result` | `post-launch-reconcile.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `runner_closeout_attempt` | `missing` | `` | `` | `stale_active_job_without_trial_result` | `post-launch-reconcile.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `runner_closeout_attempt` | `missing` | `` | `` | `stale_active_job_without_trial_result` | `post-launch-reconcile-stale.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `runner_closeout_attempt` | `missing` | `` | `` | `detached_worker_ended_active_without_trial_result` | `post-launch-reconcile.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `runner_closeout_attempt` | `missing` | `` | `` | `detached_worker_ended_active_without_trial_result` | `compact:terminal-bench-multi-source-data-merger-baseline-prelaunch-guard-20260615T160807CST/post_launch_summary.public.json` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `codex_cli_not_on_path` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed_agent_codex_install` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed_agent_codex_install` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `worker_install_failed_agent_codex_install` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `hardened_codex_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `multi-source-data-merger` | `codex_app_server_goal_observation` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `cloud-ecs/parallel-benchmark-20260620T235333Z/terminal-bench-multi-source-data-merger-app-server-r1/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `nginx-request-logging` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_setup_timeout_before_worker_start` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `hardened_codex_baseline` | `` | `0.0` | `` | `` | `worker_install_failed_agent_codex_install_nvm_node` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `hardened_codex_worker_materialization_probe` | `` | `0.0` | `` | `` | `codex_cli_not_on_path` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `hardened_codex_worker_materialization_runtime_probe` | `` | `0.0` | `` | `` | `pre_worker_startup_blocker_recorded` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `hardened_codex_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `nginx-request-logging` | `codex_app_server_goal_observation` | `` | `1.0` | `` | `` | `none` | `cloud-ecs/parallel-benchmark-20260620T235333Z/terminal-bench-nginx-request-logging-app-server-r1/terminal_bench_official_result.compact.json` |
| `terminal-bench@2.0` | `path-tracing` | `codex_goal_mode_baseline` | `` | `missing` | `` | `` | `score_missing` | `` |
| `terminal-bench@2.0` | `path-tracing` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `pytorch-model-recovery` | `codex_goal_mode_baseline` | `` | `0.0` | `` | `` | `agent_exception_before_solution_completion` | `baseline.benchmark-run.public.json` |
| `terminal-bench@2.0` | `pytorch-model-recovery` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_exception_before_solution_completion` | `treatment.benchmark-run.public.json` |
| `terminal-bench@2.0` | `pytorch-model-recovery` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `agent_exception_before_solution_completion` | `treatment.bridge-materialization-blocker.public.json` |
| `terminal-bench@2.0` | `regex-log` | `codex_loopx_treatment` | `` | `1.0` | `` | `` | `none` | `treatment_benchmark_run.compact.json` |
| `terminal-bench@2.0` | `regex-log` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `baseline_benchmark_run.compact.json` |
| `terminal-bench@2.0` | `sqlite-db-truncate` | `codex_goal_mode_baseline` | `` | `1.0` | `` | `` | `none` | `` |
| `terminal-bench@2.0` | `train-fasttext` | `codex_loopx_treatment` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
| `terminal-bench@2.0` | `train-fasttext` | `loopx_managed_codex` | `` | `0.0` | `` | `` | `official_verifier_solution_failure` | `` |
