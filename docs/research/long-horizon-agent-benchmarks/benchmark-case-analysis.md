# Benchmark Case Analysis

This file is the human view of `benchmark_case_analysis_v0`. It records durable
case lessons that should guide benchmark routing, treatment design, and claims.

It is intentionally separate from `benchmark-run-ledger.md`. The run ledger
records compact attempts and scores; this file records why a result matters.

- schema_version: `benchmark_case_analysis_v0`
- updated_at: `2026-06-24T12:31:00Z`
- machine_source: `benchmark-case-analysis.json`
- ledger-only migration audit:
  `benchmark-case-analysis-ledger-only-migration-audit-20260618.md`

## Summary

The table below is generated from compact public case-analysis JSON. It uses
`n/a` when the compact record does not establish a comparable paired arm,
and it preserves detailed hand-authored case notes below the generated
summary sections.

- case_count: `34`
- generated_compact_record_count: `8`

| Benchmark | Case | Class | Baseline | Treatment | Delta | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `terminal-bench@2.0` | `multi-source-data-merger` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `terminal-bench@2.0` | `nginx-request-logging` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `terminal-bench@2.0` | `make-doom-for-mips` | timeout attribution asset | `` | `` | `` | `paired_result_requires_attribution` |
| `terminal-bench@2.0` | `mteb-retrieve` | setup probe asset | `` | `` | `` | `environment_setup_probe_materialized_with_exception_repeat_blocked` |
| `terminal-bench@2.0` | `pytorch-model-recovery` | exception attribution asset | `` | `` | `` | `paired_no_score_uplift_exception_research_required` |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | reward feedback positive blind loop neutral asset | `` | `` | `` | `reward_feedback_positive_primary_blind_loop_no_uplift` |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | native goal connected no trace runner error asset | `` | n/a | n/a | `baseline_runner_or_setup_repair_required` |
| `skillsbench@1.1` | `dapt-intrusion-detection` | reward feedback positive blind loop neutral asset | `` | `` | `` | `reward_feedback_positive_primary_blind_loop_no_uplift` |
| `skillsbench@1.1` | `debug-trl-grpo` | regression asset | `0.25` | `` | `-0.25` | `paired_treatment_regressed` |
| `skillsbench@1.1` | `civ6-adjacency-optimizer` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `skillsbench@1.1` | `manufacturing-codebook-normalization` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `skillsbench@1.1` | `software-dependency-audit` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `skillsbench@1.1` | `react-performance-debugging` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `skillsbench@1.1` | `pddl-airport-planning` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `skillsbench@1.1` | `ada-bathroom-plan-repair` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `skillsbench@1.1` | `organize-messy-files` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `skillsbench@1.1` | `citation-check` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `skillsbench@1.1` | `3d-scan-calc` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `skillsbench@1.1` | `bike-rebalance` | current-protocol baseline-solved / non-regression asset | `1` | `1` | `` | `paired_baseline_solved_treatment_preserved` |
| `skillsbench@1.1` | `azure-bgp-oscillation-route-leak` | no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `terminal-bench@2.0` | `train-fasttext` | single arm failure asset | n/a | `` | n/a | `single_arm_recorded` |
| `skillsbench@1.1` | `setup-fuzzing-py` | setup blocker asset | `missing` | n/a | n/a | `baseline_runner_or_setup_repair_required` |
| `skillsbench@1.1` | `adaptive-cruise-control` | setup blocker asset | `missing` | n/a | n/a | `baseline_runner_or_setup_repair_required` |
| `skillsbench@1.1` | `travel-planning` | baseline solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `skillsbench@1.1` | `paratransit-routing` | product mode invalid shallow loopx asset | `` | `` | `` | `product_mode_treatment_invalid_shallow_loopx_lifecycle` |
| `swe-marathon` | `zstd-decoder` | extended round product path negative asset | `1.0` | `` | `-1.0` | `paired_treatment_regressed` |
| `terminal-bench@2.0` | `headless-terminal` | generated no-uplift asset | `` | `` | `` | `paired_no_score_uplift` |
| `terminal-bench@2.0` | `build-cython-ext` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `compile-compcert` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `financial-document-processor` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `fix-code-vulnerability` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `merge-diff-arc-agi-task` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `path-tracing` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |
| `terminal-bench@2.0` | `sqlite-db-truncate` | generated baseline-solved control asset | `1.0` | n/a | n/a | `baseline_passed_not_current_treatment_priority` |

## Public Trajectory Summary Coverage

These rows are generated from `trajectory_public_summary` blocks already
backfilled into `benchmark-case-analysis.json`. They expose only compact
public counters; absence from this table means the durable case record does
not yet contain a public trajectory summary.

- schema_version: `trajectory_public_summary_coverage_v0`
- summary_count: `5`
- attribution_conclusion_count: `5`

| Benchmark | Case | Summary | Rounds | Tools | LoopX CLI | Protected Edits | Attribution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `skillsbench@1.1` | `3d-scan-calc` | `historical_final_only_lifecycle_trajectory_summaries.baseline.trajectory_public_summary` (public-safe) | `1` | `7` | `0` | `0` | `yes` |
| `skillsbench@1.1` | `3d-scan-calc` | `historical_final_only_lifecycle_trajectory_summaries.treatment.trajectory_public_summary` (public-safe) | `8` | `138` | `73` | `0` | `yes` |
| `skillsbench@1.1` | `citation-check` | `post_stop_policy_raw_rerun.trajectory_public_summary` (public-safe) | `1` | `26` | `0` | `0` | `yes` |
| `skillsbench@1.1` | `debug-trl-grpo` | `trajectory_public_summary` (public-safe) | `5` | `112` | `0` | `2` | `yes` |
| `skillsbench@1.1` | `paratransit-routing` | `legacy_blind_loop_positive_result.trajectory_public_summary` (public-safe) | `1` | `16` | `0` | `0` | `yes` |

## Public Harness Interaction Coverage

These rows are generated from compact case-analysis counters across
benchmarks. They combine SkillsBench trajectory summaries, Terminal-Bench
worker/LoopX counters, SWE-Marathon product-path counters, and any future
benchmark case records that expose the same public fields. They do not read
or copy raw trajectories, task text, verifier output, logs, or local paths.

- schema_version: `harness_interaction_public_summary_coverage_v0`
- summary_count: `14`
- benchmark_ids: `skillsbench@1.1, swe-marathon, terminal-bench@2.0`

| Benchmark | Case | Source | Kind | LoopX CLI | Rounds | Tools | Events | Controller Trace | Lifecycle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `skillsbench@1.1` | `3d-scan-calc` | `historical_final_only_lifecycle_trajectory_summaries.baseline.trajectory_public_summary` (public-safe) | `trajectory_public_summary` | `0` | `1` | `7` | `7` | `no` | `no` |
| `skillsbench@1.1` | `3d-scan-calc` | `historical_final_only_lifecycle_trajectory_summaries.treatment.trajectory_public_summary` (public-safe) | `trajectory_public_summary` | `73` | `8` | `138` | `211` | `no` | `no` |
| `skillsbench@1.1` | `citation-check` | `post_stop_policy_raw_rerun.trajectory_public_summary` (public-safe) | `trajectory_public_summary` | `0` | `1` | `26` | `0` | `no` | `no` |
| `skillsbench@1.1` | `debug-trl-grpo` | `trajectory_public_summary` (public-safe) | `trajectory_public_summary` | `0` | `5` | `112` | `0` | `no` | `no` |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | `native_goal_route_observations` (public-safe) | `native_goal_route_observation` | `0` | `0` | `0` | `0` | `yes` | `no` |
| `skillsbench@1.1` | `paratransit-routing` | `arms.treatment` (public-safe) | `case_arm` | `1` | `0` | `0` | `0` | `no` | `no` |
| `skillsbench@1.1` | `paratransit-routing` | `legacy_blind_loop_positive_result.trajectory_public_summary` (public-safe) | `trajectory_public_summary` | `0` | `1` | `16` | `0` | `no` | `no` |
| `skillsbench@1.1` | `paratransit-routing` | `product_mode_attribution.blind_loop_positive_treatment` (public-safe) | `product_mode_attribution` | `0` | `0` | `16` | `0` | `no` | `no` |
| `skillsbench@1.1` | `paratransit-routing` | `product_mode_attribution.product_mode_neutral_treatment` (public-safe) | `product_mode_attribution` | `1` | `0` | `13` | `0` | `no` | `no` |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | `native_goal_route_observations` (public-safe) | `native_goal_route_observation` | `0` | `0` | `0` | `0` | `yes` | `no` |
| `swe-marathon` | `zstd-decoder` | `arms.baseline` (public-safe) | `case_arm` | `0` | `0` | `0` | `0` | `no` | `no` |
| `swe-marathon` | `zstd-decoder` | `arms.treatment` (public-safe) | `case_arm` | `31` | `0` | `0` | `0` | `no` | `yes` |
| `terminal-bench@2.0` | `nginx-request-logging` | `arms.treatment` (public-safe) | `case_arm` | `0` | `0` | `0` | `0` | `no` | `no` |
| `terminal-bench@2.0` | `nginx-request-logging` | `legacy_runner_materialization_asset.arms.treatment` (public-safe) | `case_arm` | `0` | `0` | `0` | `0` | `no` | `no` |

## Terminal-Bench Current-Protocol Coverage

These rows are generated from the latest compact ledger decisions. They are
current-protocol success-preservation guards: both baseline and treatment
score `1.0`, so none of them should be counted as current uplift.

| Case | Baseline | Treatment | Delta | Role | Case Analysis Status |
| --- | --- | --- | --- | --- | --- |
| `cobol-modernization` | `1` (`5d2bb1d5974a`) | `1` (`a14ad9487f8a`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `coverage_row_only_no_deep_case_note_yet` |
| `git-multibranch` | `1` (`af14bc3210c8`) | `1` (`daf4b67ab222`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `coverage_row_only_no_deep_case_note_yet` |
| `large-scale-text-editing` | `1` (`52105cdfe282`) | `1` (`01cd5e4bf562`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `coverage_row_only_no_deep_case_note_yet` |
| `multi-source-data-merger` | `1` (`37d3587daf12`) | `1` (`76cbfb57f1ea`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `case_record_has_legacy_positive_plus_current_protocol_recheck` |
| `nginx-request-logging` | `1` (`c9e583310242`) | `1` (`2a6a46cfb953`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `case_record_current_protocol_baseline_solved_with_legacy_runner_asset` |
| `regex-log` | `1` (`a9503b70072d`) | `1` (`5926107e45f4`) | `0.0` | `current_protocol_baseline_solved_non_regression_guard` | `coverage_row_only_no_deep_case_note_yet` |

## Treatment Policy Control Set

Current active control set:
`skillsbench_automation_loop_policy_controls_20260615`.

## Case: Terminal-Bench train-fasttext

This is a single-arm monitor closeout asset, not uplift evidence.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- treatment arm: `codex_loopx_treatment`
- treatment run id: `5a8f56f61908`
- treatment score: `0.0`
- failure: `official_verifier_solution_failure`
- run group: `terminal-bench-train-fasttext-managed-20260618T035534CST`

Interpretation:

The run completed one no-upload trial and reached verifier scoring, but official
reward stayed `0.0`. There is no comparable baseline or paired treatment arm
for this case yet, so it must not be counted as uplift or no-uplift evidence.

The important process lesson is monitor closeout: the active todo still reported
the detached process as running after compact result artifacts already existed.
Future Terminal-Bench monitors should promptly ingest completed `result.json`
and update the ledger/case-analysis instead of leaving stale running state.

Follow-up guidance:

- Do not repeat immediately unless a paired baseline/treatment protocol selects
  `train-fasttext`.
- Keep it out of main paired tables until a comparable counterpart exists.
- Continue ALE/Terminal/Skills rotation, but track remaining ledger-only cases
  as a migration gap instead of claiming the case table is complete.

Good-case conclusion:

- `llm-prefix-cache-replay` and `dapt-intrusion-detection` are now a two-case
  positive-control pair. In both cases the baseline reached official scoring
  and received `0.0`; the automation-loop treatment observed failed reward,
  sent one follow-up, and reached official `1.0`.
- The help signal is therefore not "LoopX is globally better". The
  durable signal is narrower and more useful: a compact outer loop with one
  reward-aware follow-up can recover some clean, solver-scoped SkillsBench
  baseline failures. This is now classified as a reward-feedback ablation, not
  as primary no-reward-leakage uplift evidence.

Interaction-count assessment:

- The current SkillsBench baseline records use the legacy arm name
  `codex_goal_mode_baseline`, but the audited runs do not prove native Codex
  `/goal` invocation. Their compact/config evidence shows official BenchFlow
  `codex-acp` execution with no LoopX controller user, no `user_rounds`
  file, and no true slash-goal prompt candidate. Treat the current uplift
  evidence as `codex-acp` baseline versus outer reward-feedback loop, not as a
  confirmed native `/goal` baseline.
- The runner contract now separates request from confirmation:
  `native_goal_mode_requested` may be true for an ACP prompt that starts with
  `/goal`, but `native_goal_mode_invoked` must stay false unless the run has
  interactive Codex CLI slash-command or goal-state evidence. ACP prompt text
  alone is not sufficient confirmation.
- The post-PR-353 native app-server Goal canary pair now confirms a narrower
  route fact: `native_goal_mode_invoked=true`, a host app-server worker
  connection, and a public-safe controller trace can be observed through compact
  counters. Both observed cases still classify as `skillsbench_runner_error`
  with no public worker trace directory, so they are runner/observation repair
  assets rather than model-quality or uplift evidence.
- The treatment route is `loopx_automation_loop_treatment`, still with
  `loopx_inside_case=false`; LoopX is the outer automation loop,
  not an in-case solver skill. Current positive, neutral, and regression
  treatment runs all use the same shape: two controller decisions, meaning an
  initial prompt plus one follow-up after failed reward.
- The follow-up payload after failed reward should be treated as reward
  feedback. It forwards `previous_reward`, `previous_verifier_error`, and
  `previous_tool_calls`; private verifier output tail can leak verifier/reward
  diagnostics into the treatment and should stay disabled by default.
- Blind-loop max5 remains the fair prompt/continuation guard: compare
  `codex-acp-blind-loop-baseline` against
  `loopx-blind-loop-treatment`, with ordinary Codex ACP/CLI inside both
  arms, no `/goal` mode, identical `max_rounds`/timeout budgets, and no
  official reward, pass/fail status, verifier error, verifier output, or
  verifier tail returned to the agent during the loop. Scheduled continuations
  must explicitly say they are pre-set, do not imply verifier success/failure,
  and re-project durable round-1 controller constraints and protected paths.
- Main-table comparison should collapse to one base+test pair: base is raw
  Codex autonomous max5, test is LoopX product-mode with state,
  todos, replanning, and LoopX CLI. Both arms receive no official verifier
  feedback during execution and stop on reward `1.0` or agent-declared done/no
  remaining goals; all other prompt/loop variants are ablations or guards.
- The controller still records scalar official reward after each completed agent
  round for offline analysis. The ledger must preserve `round_rewards` and the
  first `agent_round` that reaches the official pass threshold; these metrics are
  never forwarded to the agent in blind-loop execution.
- Product-mode setup check: no-apt task selection is not sufficient by itself,
  but the host Docker readiness blocker is now repaired for
  `paratransit-routing`. Earlier raw-Codex-autonomous-max5 reruns compact-closed
  before agent rounds as `skillsbench_docker_compose_setup_failure` and then
  `skillsbench_docker_daemon_unavailable`; correct Colima/Lima daemon cleanup
  and restart brought `loopx-bench` back to a healthy Docker context.
  The docker-ready rerun
  `skillsbench-product-mode-paratransit-routing-main-dockerready-20260616T2156CST`
  reached Codex ACP, agent round 1, verifier, and official result, with raw
  Codex autonomous max5 scoring `0.0` and declaring done in round 1. The
  matching `loopx-product-mode` treatment also reached agent round 1,
  verifier, and official result, but scored `0.0` and declared done in round 1.
  Compact counters show that treatment only ran `loopx which goal`, with no
  state read/write/replan lifecycle, so this is not a valid main-table
  product-mode no-uplift result. Keep the older blind-loop `0.0 -> 1.0`
  positive asset separate from this shallow product-mode recheck.
  The public-safe attribution is now stable at the mechanism level: the
  blind-loop positive treatment succeeded in round 1 with zero LoopX CLI
  calls and stopped only after offline official success; the product-mode
  treatment failed in round 1, made only one non-substantive LoopX CLI
  call (`loopx which goal`), performed no state reads/writes, and stopped
  on `agent_declared_done` at score `0.0`. The product-mode miss is therefore
  a stop/goal-state semantics failure. The later depth-gate product-mode rerun
  `skillsbench-product-mode-paratransit-depth-gate-20260617T1229CST`
  continued through five rounds and reached official score `1.0`, so future
  product-mode claims must require stateful LoopX lifecycle before accepting
  declared done at `0.0`. It is not explained by extra interactions, reward
  leakage, protected-path edits, or
  Docker readiness. It is currently best attributed to the changed product-mode
  prompt/stop contract failing to preserve the blind-loop treatment's successful
  first-round behavior; content-level root cause still requires a stronger
  redacted trajectory summarizer or explicit raw-trace owner gate.
- Blind-loop recheck result: `llm-prefix-cache-replay` protocol v10 and
  `dapt-intrusion-detection` protocol v0 both completed under the primary
  no-reward protocol. Each produced baseline `0.0`, treatment `0.0`,
  `paired_no_score_uplift`. This preserves the old `1.0` results as
  reward-feedback ablation wins, but removes both cases from the evidence pool
  for blind no-reward uplift.
- Max-5 blind-loop recheck result: `llm-prefix-cache-replay` completed the
  stricter default `max_rounds=5` protocol after the old reward-feedback uplift
  was questioned. Baseline exhausted five blinded rounds at `0.0`
  (`1:0,2:0,3:0,4:0,5:0`); treatment also exhausted five blinded rounds at
  `0.0` (`1:0,2:0,3:0,4:0,5:0`). No reward/pass/fail/verifier feedback was
  returned to either agent. This makes the old uplift reward-feedback-specific
  and rules out "more blind interactions alone" as the explanation.
- Blind-loop regression result: `debug-trl-grpo` protocol v0 completed under
  the same primary no-reward protocol. Baseline held `0.25` across rounds
  `1:0.25,2:0.25`; treatment reached `0.25` after round 1 but dropped to final
  `0.0` after the scheduled continuation. This makes the regression a
  continuation/scope-stability problem, not a reward-feedback leakage artifact.
- Max-5 blind-loop stability result: `debug-trl-grpo` now has a stricter
  max-rounds-5 rerun under the same no-reward protocol. Baseline held `0.25`
  across all five rounds (`1:0.25,2:0.25,3:0.25,4:0.25,5:0.25`); treatment held
  `0.25` for rounds 1-2 but dropped to `0.0` for rounds 3-5
  (`1:0.25,2:0.25,3:0,4:0,5:0`). Under max-score loop analysis both arms reach
  `0.25`, so this is not a best-score capability regression; it is a
  final-workspace stability/regression signal.
- Prompt ablation result: `debug-trl-grpo` baseline-safe treatment prompt v0
  kept the same two-round blind budget and treatment route, but replaced the
  structured treatment framing with baseline-compatible ordinary Codex framing.
  It preserved official `0.25` across rounds `1:0.25,2:0.25`, recovering the
  structured-treatment regression to baseline partial credit.
- Max-5 neutral guard result: `azure-bgp-oscillation-route-leak` completed a
  fresh max-rounds-5 blind-loop pair under the same no-reward protocol.
  Baseline exhausted five rounds at `0.0` (`1:missing,2:0,3:0,4:0,5:0`);
  treatment also exhausted five rounds at `0.0`
  (`1:missing,2:0,3:0,4:0,5:0`). This upgrades the earlier two-round neutral
  pair into a stricter no-uplift guard: extra blinded interactions alone did
  not move either arm, while both arms reached real solver/verifier execution.
- Blind-loop neutral result: `manufacturing-codebook-normalization` protocol v0
  completed under the same primary no-reward protocol. Both arms scored `0.0`
  with round rewards `1:0,2:0`, so it is now a clean neutral guard for prompt,
  continuation, and task-family policy changes.
- Blind-loop neutral result: `civ6-adjacency-optimizer` protocol v0 also
  completed under the primary no-reward protocol. Both arms scored `0.0` with
  round rewards `1:0,2:0`; this upgrades the old legacy neutral case into a
  clean blind-loop neutral guard.
- Blind-loop neutral result: `software-dependency-audit` protocol v0 also
  completed under the primary no-reward protocol. Both arms scored `0.0` with
  round rewards `1:0,2:0`; this broadens the neutral guard set to a dependency
  audit task family.
- Blind-loop neutral result: `react-performance-debugging` protocol v0 also
  completed under the primary no-reward protocol. Both arms scored `0.0` with
  round rewards `1:0,2:0`; this adds a frontend/performance-debugging task
  family to the neutral guard set.
- Blind-loop neutral result: `pddl-airport-planning` protocol v0 also
  completed under the primary no-reward protocol. Both arms scored `0.0` with
  round rewards `1:0,2:0`; this adds a PDDL/planning task family to the neutral
  guard set.
- Blind-loop success/non-regression result: `ada-bathroom-plan-repair` protocol
  v0 now completes under the same primary no-reward protocol. Both arms scored
  `1.0` in round 1 with feedback blinded, so the old setup blocker is resolved
  for this route and the case becomes a guard that treatment does not damage
  already-solvable baseline tasks.
- Blind-loop success/non-regression result: `organize-messy-files` protocol v0
  now also completes under the primary no-reward protocol. Both arms scored
  `1.0` in round 1 with feedback blinded; the treatment arm used the
  baseline-safe prompt framing. The old Docker compose setup blocker is now
  historical runner-readiness evidence rather than the current case state.
- Blind-loop success/non-regression result: `citation-check` protocol v0 now
  also completes under the primary no-reward protocol. Both arms scored `1.0`
  in round 1 with feedback blinded; the treatment arm used the baseline-safe
  prompt framing. The old `/app` mount setup blocker is now historical
  runner-readiness evidence rather than the current case state.
- Blind-loop success/non-regression result: `3d-scan-calc` protocol v0 now
  also completes under the primary no-reward protocol. Both arms scored `1.0`
  in round 1 with feedback blinded; the treatment arm used the baseline-safe
  prompt framing. This converts an old baseline-pass-only record into a
  comparable treatment non-regression guard.
- Blind-loop success/non-regression result: `bike-rebalance` now also completes
  under the primary no-reward protocol after a baseline-only runner repair
  rerun. The initial comparable baseline attempt ended as
  `skillsbench_runner_error`, but the repaired baseline and the baseline-safe
  treatment both scored `1.0` in round 1. This is a runner-readiness lesson and
  success guard, not a positive uplift claim.
- Blind-loop baseline-solved control: `travel-planning` baseline scored `1.0`
  in round 1 with official feedback blinded and reward feedback not forwarded.
  This historical run used `max_rounds=2`, but it proves the success early-stop
  rule: the controller stopped after the first official success. Future runs use
  the updated default `max_rounds=5` and retain the same stop-at-1 rule.
- Blind-loop positive result: `paratransit-routing` completed under the updated
  primary no-reward protocol with `max_rounds=5` and stop-at-1. Baseline
  exhausted five rounds at `0.0` (`1:0,2:0,3:0,4:0,5:0`); treatment reached
  official `1.0` in round 1 (`1:1`) and stopped without forwarding official
  reward/pass/fail/verifier feedback. This is the first clean primary
  blind-loop positive control, not a reward-feedback ablation win.
- Trace-backed positive attribution: the treatment's public-safe ACP trajectory
  summary records 1 round, 16 tool calls, `loopx_cli_call_count=0`, and
  no protected-path edit signals. This makes the current explanation narrower:
  the uplift is not from in-case GH CLI interaction or extra rounds, but from
  first-round treatment framing plus stop-at-1 discipline.
- SkillsBench uplift is therefore not explained by interaction count alone.
  The reward-feedback positives are best explained by explicit failed-reward
  follow-up on solver-addressable first failures, while the `paratransit-routing`
  blind positive is best explained by first-round treatment framing plus
  validation discipline. The old two-round samples without returning
  reward/pass/fail/verifier information did not improve either reward-feedback
  positive-control case; generic two-decision treatment also produced
  blind-loop no-uplift on `civ6-adjacency-optimizer` and
  `manufacturing-codebook-normalization`, produced no-uplift on
  `software-dependency-audit`, `react-performance-debugging`, and
  `pddl-airport-planning`, produced a blind-loop regression on
  `debug-trl-grpo` under both two-round and max-5 checks, and preserved an
  already-solved `1.0` baseline on
  `ada-bathroom-plan-repair`, `organize-messy-files`, `citation-check`,
  `3d-scan-calc`, and `bike-rebalance`.

| group | case | baseline official | treatment official | treatment controller decisions | follow-ups | result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| reward-feedback positive; blind-loop neutral | `llm-prefix-cache-replay` | 0.0 | 1.0 | 2 | 1 | uplift under reward-feedback; blind-loop v10 and max-5 both 0.0 -> 0.0 |
| reward-feedback positive; blind-loop neutral | `dapt-intrusion-detection` | 0.0 | 1.0 | 2 | 1 | uplift under reward-feedback; blind-loop v0 0.0 -> 0.0 |
| blind-loop stability regression | `debug-trl-grpo` | 0.25 | 0.0 final / 0.25 best | 5 | 4 | max-score ties baseline at 0.25, but final workspace regresses to 0.0 after protected-path edits in rounds 3-4 |
| prompt ablation | `debug-trl-grpo` | 0.25 | 0.25 | 2 | 1 | baseline-safe treatment prompt v0 recovered to baseline partial credit; rounds 1:0.25,2:0.25 |
| blind-loop neutral | `civ6-adjacency-optimizer` | 0.0 | 0.0 | 2 | 1 | blind-loop v0 0.0 -> 0.0; rounds 1:0,2:0 in both arms |
| blind-loop neutral | `manufacturing-codebook-normalization` | 0.0 | 0.0 | 2 | 1 | blind-loop v0 0.0 -> 0.0; rounds 1:0,2:0 in both arms |
| blind-loop neutral | `software-dependency-audit` | 0.0 | 0.0 | 2 | 1 | blind-loop v0 0.0 -> 0.0; rounds 1:0,2:0 in both arms |
| blind-loop neutral | `react-performance-debugging` | 0.0 | 0.0 | 2 | 1 | blind-loop v0 0.0 -> 0.0; rounds 1:0,2:0 in both arms |
| blind-loop neutral | `pddl-airport-planning` | 0.0 | 0.0 | 2 | 1 | blind-loop v0 0.0 -> 0.0; rounds 1:0,2:0 in both arms |
| blind-loop success/non-regression | `ada-bathroom-plan-repair` | 1.0 | 1.0 | 2 | 0 | blind-loop v0 1.0 -> 1.0; first_success_round=1 in both arms |
| blind-loop success/non-regression | `organize-messy-files` | 1.0 | 1.0 | 2 | 0 | blind-loop v0 baseline-safe treatment 1.0 -> 1.0; first_success_round=1 in both arms |
| blind-loop success/non-regression | `citation-check` | 1.0 | 1.0 | 2 | 0 | blind-loop v0 baseline-safe treatment 1.0 -> 1.0; first_success_round=1 in both arms |
| blind-loop success/non-regression | `3d-scan-calc` | 1.0 | 1.0 | 2 | 0 | blind-loop v0 baseline-safe treatment 1.0 -> 1.0; first_success_round=1 in both arms |
| blind-loop success/non-regression | `bike-rebalance` | 1.0 | 1.0 | 1 | 0 | repaired baseline rerun and baseline-safe treatment both reached first_success_round=1; no uplift claim |
| baseline-solved control | `travel-planning` | 1.0 | n/a | n/a | 0 | baseline-only blind-loop run reached first_success_round=1 and stopped; future default max_rounds=5, stop-at-1 |
| blind-loop positive | `paratransit-routing` | 0.0 | 1.0 | 2 | 0 | primary blind-loop max_rounds=5: baseline rounds 1:0,2:0,3:0,4:0,5:0; treatment first_success_round=1 and stopped |

Bad-case conclusion:

- `debug-trl-grpo` is the stability regression guard. Baseline kept scope
  narrow and preserved partial credit, scoring `0.25`; structured treatment can
  also reach `0.25`, but later blind continuations damage the final workspace to
  `0.0`.
- The max-5 blind-loop pair is especially diagnostic: baseline stayed at
  `0.25` for all five blinded rounds, while treatment stayed at `0.25` for two
  rounds and then dropped to final `0.0`. Under the controller's best-round
  metric, treatment ties baseline; under final-workspace scoring, treatment
  regresses. The problem is not connectivity, setup, reward leakage, or simply
  too few interactions. It is treatment policy: prompt shape, scope preservation,
  round budget, and stop/stabilize conditions.
- The baseline-safe prompt ablation is the first repair signal: with the same
  two-round blind budget and treatment route, replacing the structured treatment
  framing with baseline-compatible ordinary Codex framing kept final score at
  `0.25`. So the current leading suspect is structured prompt/scope framing
  rather than interaction count alone.

Neutral-control conclusion:

- `civ6-adjacency-optimizer` proves the automation loop can run under the
  primary blind-loop protocol and still fail to improve. Generic two-round
  scheduled continuation is not enough for every task family.
- `manufacturing-codebook-normalization` now gives the same neutral signal under
  the primary blind-loop protocol: both baseline and treatment scored `0.0`,
  both recorded `1:0,2:0`, and the treatment surface ran without receiving
  official reward/pass/fail/verifier feedback.
- `software-dependency-audit` adds the same neutral signal in a dependency-audit
  task family, again with both arms at `0.0` and round rewards `1:0,2:0`.
- `react-performance-debugging` adds the same neutral signal in a
  frontend/performance-debugging task family, again with both arms at `0.0` and
  round rewards `1:0,2:0`.
- `pddl-airport-planning` adds the same neutral signal in a PDDL/planning task
  family, again with both arms at `0.0` and round rewards `1:0,2:0`.

Success/non-regression conclusion:

- `ada-bathroom-plan-repair` is no longer a current setup blocker under the
  primary blind-loop route. It is also not uplift evidence: baseline already
  passed at `1.0` in round 1. Its durable value is as a success guard showing
  the treatment wrapper can preserve a baseline-solved case without reward or
  verifier feedback leakage.
- `organize-messy-files` similarly moved from setup-blocker history to a
  baseline-solved non-regression guard. The old Docker compose setup failure is
  useful runner-readiness evidence, but the current blind-loop pair scored
  `1.0`/`1.0` in round 1, including the baseline-safe treatment prompt.
- `citation-check` also moved from setup-blocker history to a baseline-solved
  non-regression guard. The old `/app` mount setup failure is useful
  runner-readiness evidence, but the current blind-loop pair scored
  `1.0`/`1.0` in round 1, including the baseline-safe treatment prompt.
- `3d-scan-calc` moved from a legacy baseline-pass-only record to a
  baseline-solved non-regression guard. The current blind-loop pair scored
  `1.0`/`1.0` in round 1, including the baseline-safe treatment prompt, so it
  checks that treatment does not damage an already-solvable 3D calculation task.
- `bike-rebalance` also moved from route-canary history to a baseline-solved
  non-regression guard. The first comparable baseline attempt failed before
  rounds with `skillsbench_runner_error`, but the repaired baseline-only rerun
  reached official `1.0` in round 1. The previously recorded baseline-safe
  treatment also scored `1.0` in round 1, so this case is useful as a success
  guard and runner-readiness lesson, not as uplift evidence.
- `travel-planning` is a baseline-solved control rather than a paired
  non-regression guard. The ordinary Codex ACP blind-loop baseline reached
  official `1.0` in round 1 with feedback blinded, so treatment was not launched
  for uplift mining. Its durable value is route selection: when baseline already
  passes, skip treatment unless explicitly checking non-regression.

Policy gate:

- Do not claim route-wide improvement from positive cases alone.
- Do not claim uplift from treatment passes when the paired baseline is a
  runner/setup failure; repair or rerun baseline first.
- Any prompt or round-policy change should preserve the `debug-trl-grpo`
  regression guard, avoid regressing the `civ6-adjacency-optimizer` and
  `manufacturing-codebook-normalization`, `software-dependency-audit`, and
  `react-performance-debugging` and `pddl-airport-planning` blind neutral
  guards, keep the `ada-bathroom-plan-repair` baseline-solved success guard
  plus the `organize-messy-files`, `citation-check`, `3d-scan-calc`, and
  `bike-rebalance`
  baseline-solved success guards passing, keep at least one positive-control
  case passing, and avoid counting setup/materialization blockers as case
  outcomes.
- Primary SkillsBench main-table claims should use the single product-mode
  base+test pair: raw Codex autonomous max5 versus LoopX
  state/todo/replan/CLI product-mode. Blind-loop pairs with
  `reward_feedback_forwarded=false` and `official_feedback_blinded=true` remain
  prompt/continuation guards, and reward-aware routes remain ablations.
- New blind-loop guard runs should use the shared default `max_rounds=5` for
  both arms and stop an arm as soon as official reward reaches `1.0`; always
  record `first_success_round` and per-round scalar reward offline.
- Main-table runs should report only `best_score`, `final_score`,
  `first_success_round`, and `declared_done_score` as the shared headline
  metrics; keep extra prompt/round variants out of the main comparison table.
- Future blind-loop treatment prompts should start from baseline-safe
  scope-preserving framing. Scheduled continuations must explicitly preserve
  protected files, no-GH-CLI/no-upload/no-human-query controls, and narrow task
  scope unless compact verifier-facing evidence requires broader edits.

## Case: Terminal-Bench multi-source-data-merger

This is a legacy end-to-end positive-control case that became a
current-protocol baseline-solved/non-regression control. The old evidence is
strong that the historical treatment route could pass a real case, but it is
weaker evidence that the treatment solver is intrinsically better than baseline
on this task. Under the current Terminal-Bench protocol, both the hardened Codex
baseline and LoopX managed treatment scored `1.0`.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `232721f7caf1`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `codex_loopx_treatment`
- treatment run id: `2986c373a314`
- treatment score: `1.0`
- treatment failure: `none`

Current protocol rerun:

- route pair: Terminal-Bench `hardened-codex` baseline vs.
  `loopx-managed-codex` treatment
- run group: `terminal-bench-multi-source-data-merger-current-protocol-20260617T201625CST`
- baseline job:
  `terminal_bench_multi_source_data_merger_hardened_codex_current_protocol_20260617T202500CST`
- baseline run id: `37d3587daf12`
- baseline score: `1.0`
- treatment job:
  `terminal_bench_multi_source_data_merger_loopx_managed_codex_current_protocol_20260617T201625CST`
- treatment run id: `76cbfb57f1ea`
- treatment score: `1.0`
- official score delta: `0.0`
- decision: `paired_baseline_solved_treatment_preserved`
- boundary: no upload, no leaderboard submit, no raw task/log/trajectory read

Interpretation:

LoopX treatment produced correct artifacts that the official verifier
scored `1.0`. The trajectory shows a useful harness pattern: bridge preflight,
schema inspection, reproducible script generation, and local validation before
final closeout.

The caveat is that the baseline trajectory also inspected schemas, wrote a
merge script, regenerated outputs, and self-validated row counts, types, dates,
priority selection, and conflict count. Its official `0.0` came from a
verifier/runtime crash before task tests completed, not from a clean hidden-test
failure. Treatment also hit a bridge status hang after output validation, but
the artifacts were already written and verifier-facing output passed.

Why it matters:

- It proves the treatment route can reach official `1.0` on a real
  Terminal-Bench case.
- It anchors the migration from historical `codex_loopx` evidence to the
  newer LoopX managed route: the current route preserves success, but
  the comparable baseline now also passes.
- It proves the distinction between runner readiness, self-validation, and
  verifier success matters; baseline self-validation and official score
  diverged.
- It is a good non-regression/control case for end-to-end harness behavior, but
  not current-protocol uplift evidence.

Follow-up guidance:

- Do not use the old `0.0 -> 1.0` result as current main-table uplift evidence;
  the new comparable pair is `1.0 -> 1.0`.
- Keep this case as a current-protocol success-preservation guard when changing
  Terminal-Bench managed routing, lifecycle trace, or worker setup policy.
- Preserve the materialization and compact closeout path that made the case
  interpretable.
- Fix or time-bound the worker bridge status call; it should not hang after
  successful artifact validation.

## Case: Terminal-Bench nginx-request-logging

This is now a current-protocol baseline-solved non-regression guard. The older
`0.0 -> 1.0` row remains useful as a runner-materialization lesson, not as a
main-table uplift claim.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- baseline arm: `hardened_codex_baseline`
- baseline run id: `c9e583310242`
- baseline score: `1.0`
- baseline failure: `none`
- treatment arm: `codex_loopx_treatment`
- treatment run id: `2a6a46cfb953`
- treatment score: `1.0`
- treatment failure: `none`
- treatment worker CLI calls observed: `0`
- legacy blocked baseline run id: `890f0a8487e4`
- legacy blocked baseline score: `0.0`
- legacy blocked baseline failure:
  `worker_install_failed_agent_codex_install_nvm_node`
- follow-up worker materialization probe run id: `51fa05316d18`
- follow-up worker materialization probe failure: `codex_cli_not_on_path`

Interpretation:

The LoopX treatment arm reached official verifier pass, and after the
worker materialization route was repaired the hardened Codex baseline also
reached official verifier pass. The current comparable conclusion is therefore
`1.0 -> 1.0`: treatment preserved success, but there is no current-protocol
uplift.

A follow-up fail-fast worker materialization probe used the `require_existing_codex`
repair profile and ended before solver execution with compact
`codex_cli_not_on_path`. This proves the current hardened baseline worker path
does not contain a usable Codex CLI; same-config baseline reruns would mostly
remeasure runner setup rather than case solving.

This distinction matters because earlier `nginx-request-logging` evidence had
unstable runner/setup shape: at one point treatment was setup-blocked; later a
hardened baseline was setup-blocked while treatment passed. The useful durable
signal is therefore not "LoopX always helps this case"; it is that
runner/materialization state must be fixed before the case can be used for a
fair treatment comparison.

Why it matters:

- It preserves the treatment pass as a useful end-to-end route-canary.
- It converts nginx into a current-protocol success-preservation guard.
- It prevents a false uplift claim from a baseline worker/setup blocker.
- It records that access-packet presence is not the same as observed
  worker-side LoopX CLI use.
- It turns the baseline blocker into a concrete repair target: materialize
  `codex` on worker `PATH` before solver start.

Follow-up guidance:

- Keep this case out of pure solver-uplift counts because the repaired baseline
  reaches worker materialization and official `1.0`.
- Use the legacy blocked baseline as a regression guard for worker setup and
  false-claim prevention, not as the active score comparison.
- Continue alternating to fresh baseline-failing cases if the next goal is
  evidence breadth rather than this specific materialization repair.

## Case: Terminal-Bench make-doom-for-mips

This is a timeout and attribution asset, not a treatment-uplift case.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `1e0e7327d18a`
- baseline score: `0.0`
- baseline failure: `agent_timeout_before_solution_completion`
- treatment arm: `codex_loopx_treatment`
- treatment run id: `1caa8b39f0a4`
- treatment score: `0.0`
- treatment failure: `score_failure_unattributed`

Interpretation:

This case answers one of the timeout questions: simply raising the case budget
is not enough by itself. The first default-timeout pair failed before solution
completion. A private 2h relaunch then exposed worker setup timeout, which is a
different phase and should not be counted as solver failure. After applying the
setup8+2h route, the baseline still ended in timeout context and the treatment
still produced official `0.0`, but the treatment closeout did not include
enough compact verifier-facing attribution to say whether the bottleneck was
solver output, verifier behavior, or result finalization.

Why it matters:

- It prevents `make-doom-for-mips` from being mislabeled as clean no-uplift.
- It shows that Terminal-Bench long cases need explicit lifecycle phase
  evidence: setup readiness, worker start, solver completion, result write,
  and verifier score.
- It gives us a concrete guardrail for timeout-tier policy: increase timeout
  only with materialization and attribution evidence, not as a blind retry.

Follow-up guidance:

- Do not repeat immediately.
- First collect compact phase/verifier attribution for the setup8+2h pair.
- Only rerun after the launcher can prove worker materialization and record the
  chosen timeout tier in the compact closeout.

Latest case-first managed run, 2026-06-17:

- run group: `terminal-bench-make-doom-managed-20260617T193035CST`
- arm: `loopx-managed-codex`
- compact result: completed, official score `0.0`
- compact attribution: `official_verifier_solution_failure`
- control-plane signal: the launcher and post-launch closeout are now usable;
  job root materialized, the trial completed, and compact ingestion reached a
  verifier-facing official score without reading raw task text, logs, or
  trajectories.
- product-mode gap: this run is not a clean treatment claim. The compact
  counters show `worker_loopx_cli_call_total=0` and no worker bridge
  trace, so it proves the managed Terminal-Bench route can run and close out,
  not that the in-case LoopX product experience improved the task.

Updated guidance:

- Use this as a completed Terminal-Bench lifecycle/attribution data point.
- Do not claim uplift or regression from it.
- Before another `make-doom-for-mips` repeat, either add Terminal-Bench
  product-mode parity/trace evidence comparable to the SkillsBench route, or
  choose a different material-ready case where the current product-mode route
  can expose real state/todo/replan behavior.

## Case: Terminal-Bench mteb-retrieve

This is a setup-probe asset, not a solver comparison.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `f51ed0bc44ef`
- baseline compact failure: `environment_setup_failed_before_worker`
- treatment arm: `codex_loopx_treatment`
- treatment run id: `4dca7e651fac`
- treatment compact failure: `environment_setup_failed_before_worker`
- setup probe arm: `harbor_observed`
- setup probe run id: `b1c43dfaaa19`
- setup probe run group: `terminal-bench-mteb-retrieve-env-probe-20260616T0800CST`
- setup probe worker mode: `nop`
- setup probe worker start status: `environment_setup_probe_materialized`
- setup probe trial result count: `1`
- setup probe artifact manifest count: `1`
- setup probe exception type: `RuntimeError`
- setup probe outcome: `materialized_with_exception`
- setup probe repeat blocker: `environment_setup_probe_exception_requires_interpretation`

Interpretation:

The previous paired baseline and treatment both failed before worker start in
environment setup. This turn launched a no-upload, NOP-agent,
verification-disabled environment setup probe for the same task. The probe
materialized a Harbor job root, produced a trial result, and exposed an
artifact manifest through compact ingest.

That is progress on the runner/setup layer, but it is not a case success and
not a treatment comparison. The compact lifecycle reducer now reports
`environment_setup_probe_completed` instead of misrouting the single-arm probe
to `paired_comparison_missing`. It also keeps `case_attempt_countable=false`,
`benchmark_budget_countable=false`, and `repeat_allowed=false`.
The probe is now further classified as `materialized_with_exception`, so the
same-task full repeat remains blocked until the compact `RuntimeError` is
classified.

Why it matters:

- It gives `mteb-retrieve` a real setup/materialization signal instead of only
  old pre-worker setup failures.
- It proves the no-upload setup-probe path can move past launcher/job-root
  materialization for this case.
- It prevents a setup probe from being counted as a benchmark case attempt or
  hidden-test no-uplift.

Follow-up guidance:

- Do not launch a full same-task repeat yet.
- First classify whether the compact `RuntimeError` is expected from the
  NOP/disable-verification route or indicates persistent task environment
  failure.
- Keep setup-probe lifecycle accounting separate from case-attempt and
  benchmark-budget accounting.

## Case: Terminal-Bench pytorch-model-recovery

This is an exception-attribution asset, not a clean no-uplift case.

Compact evidence:

- benchmark: `terminal-bench@2.0`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `2db3f1047704`
- baseline compact failure: `agent_exception_before_solution_completion`
- baseline exception type: `RuntimeError`
- baseline verifier reward: absent
- treatment arm: `codex_loopx_treatment`
- treatment run id: `9ba1b6872167`
- treatment compact failure: `agent_exception_before_solution_completion`
- treatment exception type: `RuntimeError`
- treatment verifier reward: absent
- treatment worker bridge: `not_materialized`

Interpretation:

The stable conclusion is not "baseline and treatment both failed hidden tests."
The compact artifacts show both arms ended before verifier reward with
`RuntimeError`. The treatment side has an additional bridge-readiness caveat:
the bridge-materialization compact marker reports `worker_bridge_materialization_status=not_materialized`.

The verifier-attribution review now classifies this pattern as
`agent_exception_score_failure` instead of generic
`unattributed_score_failure`. That matters because the next action is no longer
"collect arbitrary finer verifier attribution"; it is narrower: inspect compact
agent-exception context or form a case-level exception hypothesis before any
same-task repeat.

Why it matters:

- It prevents this case from being mislabeled as clean no-uplift.
- It separates agent/runtime exception before verifier reward from official
  verifier solution failure.
- It keeps treatment-readiness evidence separate from solver quality: treatment
  cannot be judged until bridge materialization is proven.
- It gives Terminal-Bench a durable exception-attribution guard alongside the
  timeout guard from `make-doom-for-mips`.

Follow-up guidance:

- Do not use this case for uplift, regression, or clean no-uplift claims.
- Do not repeat the same task until compact exception context or a case-level
  intervention hypothesis exists.
- If compact exception context cannot be improved without raw logs or
  trajectory, select a new material-ready Terminal-Bench case instead.
- Preserve the public-safe boundary: no raw logs, task text, verifier output,
  or trajectories are needed for this classification.

## Case: SkillsBench llm-prefix-cache-replay

This is the first clean SkillsBench reward-feedback positive-control case, but
it is now a blind-loop neutral guard under the primary no-reward protocol.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `7eb47e9e7f35`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `cf8da5bd77a2`
- treatment score: `1.0`
- treatment failure: `none`
- max-5 blind-loop run group:
  `skillsbench-llm-prefix-cache-replay-blind-loop-max5-20260616T1531CST`
- max-5 blind-loop baseline: `codex-acp-blind-loop-baseline`, score `0.0`,
  rounds `1:0,2:0,3:0,4:0,5:0`, `first_success_round=null`
- max-5 blind-loop treatment: `loopx-blind-loop-treatment`, score `0.0`,
  rounds `1:0,2:0,3:0,4:0,5:0`, `first_success_round=null`
- native app-server Goal canary run group:
  `skillsbench-native-goal-post353-20260620T220003Z`
- native Goal baseline run id: `b7fdd71e481b`
- native Goal baseline score: `0.0`
- native Goal baseline failure: `skillsbench_runner_error`
- native Goal route counters: `native_goal_mode_invoked=true`,
  worker connected, public worker trace count `0`

Interpretation:

The baseline reached official SkillsBench verifier scoring and failed with
reward `0.0`, so this is a solver/case-scoped baseline failure rather than a
setup or materialization artifact. The treatment ran the outer automation loop:
compact controller counters record two heartbeat/controller decisions, one
initial controller prompt, one failed-reward observation, and one follow-up.
After that follow-up, the official verifier scored the case `1.0`.
The same case does not improve when reward/pass/fail/verifier feedback is
blinded: both the two-round blind recheck and the stricter max-5 rerun finished
at `0.0` for both arms.

The post-PR-353 native app-server Goal canary is a separate route observation:
it confirms native Goal invocation, host-worker connection, and public-safe
controller trace, but it still fails as `skillsbench_runner_error` and exposes
no public worker trace directory. It should not be folded into the reward
feedback or blind-loop claim table until worker trace collection or runner
attribution is repaired.

Why it matters:

- It proves the reward-feedback automation-loop route can convert a clean
  baseline `0.0` into an official `1.0` without relying on setup repair as the
  outcome.
- It does not prove blind no-reward LoopX uplift: under protocol v10 and
  the max-5 rerun, the same case completed both blind-loop arms and stayed at
  `0.0`.
- It gives a positive control to pair with `debug-trl-grpo` regression and
  `civ6-adjacency-optimizer` no-uplift controls.
- It shows that compact controller counters are enough to confirm the treatment
  surface actually ran, even without copying raw task text, logs, or
  trajectory.
- It also gives the native Goal route a concrete repair target: public worker
  trace collection must materialize before this route can support model-quality
  comparisons.

Follow-up guidance:

- Do not repeat this case immediately unless testing a stability or
  treatment-policy hypothesis.
- Keep this as the SkillsBench positive-control asset for automation-loop
  reward-feedback-ablation prompt, round, and termination-policy changes.
- Do not use it as a positive-control asset for the primary blind-loop protocol;
  protocol v10 and the max-5 rerun are no-uplift guards.
- Do not generalize from one uplift case; compare future changes against the
  regression and no-uplift assets before making route-wide claims.
- For native app-server Goal, repair or explain the missing public worker trace
  directory before using the route as the default SkillsBench quality baseline.

## Case: SkillsBench tictoc-unnecessary-abort-detection

This is a native app-server Goal route/runner observation, not a model-quality
case result yet.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `skillsbench_codex_app_server_goal_baseline`
- run group: `skillsbench-native-goal-post353-20260620T220003Z`
- baseline run id: `a054a9322569`
- baseline score: `0.0`
- baseline failure: `skillsbench_runner_error`
- native Goal route counters: `native_goal_mode_invoked=true`,
  worker connected, public-safe controller trace present, public worker trace
  count `0`

Interpretation:

The compact result proves the host app-server Goal route can connect to the
worker and record public-safe controller evidence without reading raw task text,
raw logs, verifier output, or trajectory. The useful finding is still negative:
the public worker trace directory was not observed, so the failure remains
`runner_or_setup` and cannot be used to judge whether the agent solved the task.

Why it matters:

- It gives the native Goal SkillsBench route a second concrete canary beyond
  `llm-prefix-cache-replay`.
- It confirms route connection and controller trace observability, while
  keeping the public/private boundary compact-only.
- It blocks quality comparison until the missing worker trace or runner error is
  repaired.

Follow-up guidance:

- Do not launch treatment or claim uplift/no-uplift from this row.
- Repair public worker trace collection, or record a compact explanation for
  why no worker trace is expected, then rerun a selected SkillsBench case.
- Keep this as a runner/observation repair asset in the rotation ledger.

## Case: SkillsBench dapt-intrusion-detection

This is the second clean SkillsBench positive-control case for the
automation-loop treatment route.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `da0d9b235bee`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `8f4799261e11`
- treatment score: `1.0`
- treatment failure: `none`

Interpretation:

The baseline reached official SkillsBench verifier scoring and failed with
reward `0.0`, so this is a solver/case-scoped baseline failure rather than a
setup or materialization artifact. The matching treatment ran the outer
automation loop. Compact controller counters record two heartbeat/controller
decisions, one initial controller prompt, one failed-reward observation, and
one follow-up. After that follow-up, the official verifier scored the case
`1.0`.

Why it matters:

- It gives a second SkillsBench positive-control case, reducing the chance that
  `llm-prefix-cache-replay` is a one-off reward-feedback treatment win.
- It strengthens the evidence that one explicit follow-up after failed reward
  can recover some clean SkillsBench baseline failures.
- It does not support blind-loop uplift: protocol v0 completed the primary
  no-reward comparison with baseline `0.0`, treatment `0.0`, round rewards
  `1:0,2:0` in both arms, and `first_success_round=null`.
- The useful difference is not interaction count alone. The reward-feedback
  route passed after receiving failed-reward semantics; the blind-loop route had
  the same two-round budget without reward/pass/fail/verifier feedback and did
  not improve.
- It still does not justify a broad route-wide superiority claim, because
  `debug-trl-grpo` remains a regression asset and several cases remain neutral
  or setup-blocked.

Follow-up guidance:

- Keep this paired with `llm-prefix-cache-replay` as the SkillsBench
  reward-feedback-ablation positive control set for automation-loop policy
  changes.
- Do not use it as a positive-control asset for the primary blind-loop protocol;
  protocol v0 is a no-uplift guard.
- Repeat only after a concrete prompt, round-policy, or stability hypothesis.
- Compare every new treatment-policy change against positive, regression, and
  no-uplift controls before widening claims.

## Case: SkillsBench debug-trl-grpo

This is the current negative-control case.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `9db0404df80b`
- baseline score: `0.25`
- baseline failure: `none`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `ef452ac2450b`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group: `skillsbench-debug-trl-grpo-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, score `0.25`, rounds
  `1:0.25,2:0.25`
- blind-loop treatment: `loopx-blind-loop-treatment`, score `0.0`,
  rounds `1:0.25,2:0`, `first_success_round=null`
- max-5 blind-loop run group:
  `skillsbench-debug-trl-grpo-blind-loop-max5-20260616T144124CST`
- max-5 blind-loop baseline: `codex-acp-blind-loop-baseline`, score `0.25`,
  rounds `1:0.25,2:0.25,3:0.25,4:0.25,5:0.25`
- max-5 blind-loop treatment: `loopx-blind-loop-treatment`, score
  `0.0`, rounds `1:0.25,2:0.25,3:0,4:0,5:0`,
  `first_success_round=null`
- max-5 scoring view: baseline best `0.25`, treatment best `0.25`,
  `best_round_score_delta=0.0`; baseline final `0.25`, treatment final `0.0`,
  `final_round_score_delta=-0.25`
- prompt ablation: `loopx-blind-loop-treatment` with
  `treatment_prompt_style=baseline-safe`, run `f37b0a3e9654`, score `0.25`,
  rounds `1:0.25,2:0.25`
- max-5 treatment public trajectory summary: 5 rounds, 112 tool calls,
  `loopx_cli_call_count=0`, protected edit signals on
  `/app/train_grpo.py` in rounds 3 and 4

Interpretation:

After the local Docker CPU setup blocker was repaired, the treatment route
still regressed relative to baseline. The primary blind-loop repeat reproduced
the regression without returning reward, pass/fail, verifier errors, or verifier
output to the agent. That makes this a treatment-design signal, not a
runner-readiness issue or reward-feedback leakage artifact.

The max-5 rerun strengthens but also narrows the conclusion. Baseline held its
`0.25` partial-credit plateau across five blinded rounds, while structured
treatment also reached `0.25` for two rounds and then fell to `0.0` for the
remaining rounds. If the controller is evaluated by best round, treatment ties
baseline on this case; if evaluated by final workspace, treatment regresses.
More blind interaction did not improve best score; it revealed that scheduled
continuation needs a partial-credit stabilization rule.

Trace-backed attribution:

- The max-5 treatment's public-safe ACP trajectory summary records zero in-case
  LoopX CLI calls. The regression is therefore not explained by
  treatment talking to the LoopX CLI more often than baseline.
- The same summary records protected-path edit signals in rounds 3 and 4, both
  on `/app/train_grpo.py`. This strengthens the scope-drift diagnosis: the
  harmful factor is scheduled continuation plus structured treatment framing
  crossing protected task boundaries after already reaching baseline-level
  partial credit.
- A direct comparison of baseline, structured treatment, and baseline-safe
  ACP user messages showed the same continuation gap: round 1 contained the
  protected paths and no-`/goal`/no-GH-CLI controls, while later scheduled
  continuations preserved only generic narrow-scope language. The controller
  now re-projects those durable round-1 constraints on every blind-loop
  continuation.
- Raw ACP trajectory, task text, verifier output, and local artifact paths stay
  out of this analysis record; only compact counters and protected edit-round
  facts are durable here.

Trajectory comparison:

- Baseline stayed narrow: it focused on the TRL trainer, fixed the advantage
  epsilon bug, added a constructor compatibility alias, and left protected
  files alone.
- Baseline verifier result was partial credit: it passed source presence,
  protected training script, protected reward function, advantage epsilon, and
  non-vanishing advantage checks; it still failed selective log-softmax
  correctness and decode preservation.
- Treatment used more rounds and more tool calls, fixed the same epsilon bug,
  then expanded into rewriting `reward_fn.py`.
- The treatment still failed selective log-softmax and decode preservation, and
  additionally failed the protected reward-function check. That extra scope
  expansion is the concrete regression.
- In the blind-loop repeat, the first treatment round reached the same `0.25`
  partial-credit score as baseline, but the scheduled continuation destabilized
  the final result to `0.0`. This points at continuation policy and
  scope-stability guards, not simply at interaction count.
- In the max-5 repeat, baseline remained stable at `0.25` for rounds 1-5, while
  treatment remained at `0.25` for rounds 1-2 and then degraded to `0.0` for
  rounds 3-5. That makes the continuation-risk diagnosis more stable than the
  old two-round sample alone.
- In the baseline-safe prompt ablation, the treatment route kept the same
  two-round blind-loop budget but used ordinary baseline-compatible framing for
  the first prompt. It preserved `0.25` across both rounds, so the regression is
  more likely caused by structured treatment framing and scope expansion than by
  the mere presence of a second interaction.

Why it matters:

- It prevents us from making a broad "LoopX treatment is better" claim
  based only on the Terminal-Bench uplift case.
- It points specifically at automation-loop behavior: prompt shape, polling
  cadence, round budget, termination policy, and scope-preservation rules.
- It gives us a negative-control case for prompt/round-policy ablations.
- It gives us a repair candidate: baseline-safe treatment framing should be
  tested against positive, neutral, and success/non-regression guards before any
  default policy change.

Follow-up guidance:

- Treat baseline-safe framing as the current prompt-policy candidate, but do not
  promote it until it preserves at least one positive-control, one neutral
  control, and the `ada-bathroom-plan-repair` success guard.
- Compare fixed polling, model-decided termination, and hybrid termination on
  compact evidence rather than chat memory.
- Use this case as a regression guard when changing the automation-loop route or
  blind-loop scheduled-continuation policy.
- Test a stop/stabilize rule that preserves nonzero partial-credit states unless
  local evidence clearly justifies further risky edits.
- Add a hard guard or strong prompt rule against editing protected files unless
  verifier-facing evidence explicitly requires it.

## Case: SkillsBench civ6-adjacency-optimizer

This is a clean no-uplift case from the repaired SkillsBench staging path, now
rechecked under the primary blind-loop treatment route.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `8eccae2d04d6`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `978868092e84`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group:
  `skillsbench-civ6-adjacency-optimizer-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, run id
  `973d9618d7f6`, score `0.0`, rounds `1:0,2:0`
- blind-loop treatment: `loopx-blind-loop-treatment`, run id
  `8d21a5cc42f2`, score `0.0`, rounds `1:0,2:0`,
  `first_success_round=null`

Interpretation:

The baseline failure is useful because it reached official verifier scoring
after staging repair; it is a case/solution failure, not a setup or
materialization artifact. The treatment exercised the automation-loop surface:
compact controller trace was present, two heartbeat/action decisions were
recorded, and the second round followed failed reward/verifier feedback.

The treatment still scored `0.0`. The stable conclusion is therefore not
"LoopX regressed", but "generic two-round feedback did not help this
task family."

The blind-loop repeat preserves that conclusion without returning official
reward, pass/fail status, verifier errors, verifier output, or private verifier
tail to the agent. Both arms completed official scoring at `0.0` and recorded
`1:0,2:0`, so this case is a clean neutral guard for no-reward comparison
claims.

Why it matters:

- It adds a baseline-failing SkillsBench case without setup confound.
- It shows that the automation-loop machinery ran, observed feedback, and
  still did not improve official score.
- It is a good control for tuning verifier-feedback summaries and treatment
  specificity.
- It now also guards blind-loop prompt, continuation, and termination changes
  alongside `manufacturing-codebook-normalization`.

Follow-up guidance:

- Do not count this as uplift evidence.
- Repeat only after a targeted blind-loop prompt, termination, or task-family
  hypothesis.
- Mine more baseline-failing SkillsBench cases before overfitting to this one.

## Case: SkillsBench manufacturing-codebook-normalization

This is the first clean no-uplift neutral guard that has been rechecked under
the primary blind-loop treatment route.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `c76c8bed6a8a`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `e85065a9c230`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group:
  `skillsbench-manufacturing-codebook-normalization-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, score `0.0`, rounds
  `1:0,2:0`
- blind-loop treatment: `loopx-blind-loop-treatment`, score `0.0`,
  rounds `1:0,2:0`, `first_success_round=null`

Interpretation:

The baseline reached official SkillsBench verifier scoring and failed with
reward `0.0`, so it is a valid baseline-failing candidate rather than a setup
or materialization blocker. The treatment also reached official scoring and
exercised the automation-loop surface: compact counters record two
heartbeat/controller decisions, one initial prompt, one failed-reward
observation, and one follow-up after failed reward.

The treatment still scored `0.0`. This strengthens the neutral-control set:
the outer loop can run correctly and still fail to improve a clean
solver-scoped baseline failure.

The primary blind-loop repeat preserves that conclusion without returning
official reward, pass/fail, verifier errors, or verifier output to the agent.
Both blind-loop arms completed official scoring at `0.0` and recorded
`1:0,2:0`, so this case is a neutral guard for the no-reward comparison route.

Why it matters:

- It adds a second no-uplift SkillsBench control after
  `civ6-adjacency-optimizer`.
- It prevents overfitting prompt/round policy to the two positive-control
  cases.
- It shows that "one follow-up after failed reward" is a useful mechanism on
  some cases, but not a sufficient policy for all task families.
- It also shows that the current blind-loop framing alone is not sufficient for
  this task family.

Follow-up guidance:

- Do not count this as uplift evidence.
- Repeat only after a targeted blind-loop prompt, continuation, or task-family
  hypothesis.
- Use it as a neutral guard alongside the `debug-trl-grpo` regression guard and
  the reward-feedback-only positive controls.

## Case: SkillsBench software-dependency-audit

This is a clean no-uplift case from the repaired SkillsBench staging path, now
rechecked under the primary blind-loop treatment route.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline run id: `885b7647488b`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment run id: `6cf96cd0b19a`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group:
  `skillsbench-software-dependency-audit-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, run id
  `42be7dc4459e`, score `0.0`, rounds `1:0,2:0`
- blind-loop treatment: `loopx-blind-loop-treatment`, run id
  `173a02eb893d`, score `0.0`, rounds `1:0,2:0`,
  `first_success_round=null`

Interpretation:

The legacy pair already showed no score uplift after the SkillsBench staging
repair: both arms reached official scoring and stayed at `0.0`. The primary
blind-loop repeat preserves that conclusion under the stricter no-reward
protocol. It returned no official reward, pass/fail status, verifier errors,
verifier output, or private verifier tail to the agent during the loop.

Both blind-loop arms completed official scoring at `0.0` and recorded
`1:0,2:0`. This makes the case another neutral guard for no-reward comparison
claims, especially for dependency-audit-style task families.

Why it matters:

- It broadens the neutral-control set beyond `civ6-adjacency-optimizer` and
  `manufacturing-codebook-normalization`.
- It shows that a dependency-audit task can remain flat even when the outer
  loop runs correctly.
- It helps prevent overfitting prompt/round policy to the two old
  reward-feedback positive controls.

Follow-up guidance:

- Do not count this as uplift evidence.
- Repeat only after a targeted blind-loop prompt, termination, or task-family
  hypothesis.
- Keep it in the neutral guard set when changing scheduled continuation policy.

## Case: SkillsBench react-performance-debugging

This is a clean no-uplift case from the repaired SkillsBench staging path, now
rechecked under the primary blind-loop treatment route.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group:
  `skillsbench-react-performance-debugging-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, run id
  `851ca794f780`, score `0.0`, rounds `1:0,2:0`
- blind-loop treatment: `loopx-blind-loop-treatment`, run id
  `8efed51d81e5`, score `0.0`, rounds `1:0,2:0`,
  `first_success_round=null`

Interpretation:

The blind-loop pair completed both arms under the stricter no-reward protocol:
no official reward, pass/fail status, verifier errors, verifier output, or
private verifier tail was returned to the agent during the loop. Both arms
still reached official scoring at `0.0` and recorded `1:0,2:0`.

This makes the case another neutral guard rather than uplift evidence. It is
especially useful because it covers a frontend/performance-debugging task
family instead of another data normalization or dependency-audit task.

Why it matters:

- It broadens the neutral-control set to a new SkillsBench task family.
- It shows that the two-round blind-loop treatment can execute cleanly and
  still fail to improve official score.
- It helps prevent overfitting future prompt/round-policy changes to the two
  old reward-feedback positive controls.

Follow-up guidance:

- Do not count this as uplift evidence.
- Repeat only after a targeted blind-loop prompt, termination, or task-family
  hypothesis.
- Keep it in the neutral guard set when changing scheduled continuation policy.

## Case: SkillsBench pddl-airport-planning

This is a clean no-uplift blind-loop pair for a PDDL/planning task family.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex_goal_mode_baseline`
- baseline score: `0.0`
- baseline failure: `official_verifier_solution_failure`
- treatment arm: `loopx_automation_loop_treatment`
- treatment score: `0.0`
- treatment failure: `official_verifier_solution_failure`
- blind-loop run group:
  `skillsbench-pddl-airport-planning-blind-loop-v0`
- blind-loop baseline: `codex-acp-blind-loop-baseline`, run id
  `adf46f67374c`, score `0.0`, rounds `1:0,2:0`
- blind-loop treatment: `loopx-blind-loop-treatment`, run id
  `1564d6cfc2fb`, score `0.0`, rounds `1:0,2:0`,
  `first_success_round=null`

Interpretation:

The blind-loop pair completed both arms under the stricter no-reward protocol:
no official reward, pass/fail status, verifier errors, verifier output, or
private verifier tail was returned to the agent during the loop. Both arms
reached official scoring at `0.0` and recorded `1:0,2:0`.

Historical pddl-airport-planning attempts were noisy, including runner/result
variability, so this record should be scoped to the new primary blind-loop
pair. The value is not uplift evidence; it is another neutral guard, now for
planning-style tasks.

Why it matters:

- It broadens the neutral-control set to a PDDL/planning task family.
- It shows that the current two-round blind-loop treatment can execute cleanly
  and still fail to improve official score.
- It helps prevent overfitting future prompt/round-policy changes to data,
  frontend, or dependency-audit task families only.

Follow-up guidance:

- Do not count this as uplift evidence.
- Repeat only after a targeted blind-loop prompt, termination, or task-family
  hypothesis.
- Keep it in the neutral guard set when changing scheduled continuation policy.

## Case: SkillsBench ada-bathroom-plan-repair

This was a runner/setup blocker asset, but the primary blind-loop rerun now
turns it into a baseline-solved treatment non-regression guard.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `7d919631a765`
- baseline score: `1.0`
- baseline first success round: `1`
- treatment arm: `loopx-blind-loop-treatment`
- treatment run id: `52a934d39c59`
- treatment score: `1.0`
- treatment first success round: `1`
- historical setup blocker run ids: `2eba92c0552d`, `87abf4d54cb6`
- historical blocker classes: `skillsbench_codex_acp_launch_failed`,
  `skillsbench_codex_acp_binary_missing`

Interpretation:

The old setup blocker remains useful historical runner-readiness evidence, but
it no longer describes the current primary route. The new blind-loop baseline
and treatment both reached official verifier pass at `1.0` in the first
completed agent round. Official feedback stayed blinded, reward feedback was
not forwarded, and no raw task text, raw logs, verifier output, or trajectory
were copied into this analysis.

Why it matters:

- It repairs the previous classification: this case should no longer be counted
  as a current setup blocker for the primary blind-loop route.
- It is not uplift evidence, because baseline already solved the task.
- It is a non-regression guard: treatment must continue to preserve easy
  baseline successes while we tune prompt, continuation, and stop policies.
- It keeps the historical setup failures available as compact runner-readiness
  evidence without letting them override the newer comparable pair.

Follow-up guidance:

- Do not use this case for uplift claims.
- Rerun it only after a treatment prompt, round, or stop-policy change.
- Prefer baseline-failing cases for the next uplift-mining run, while preserving
  this case as a success/non-regression guard.

## Case: SkillsBench organize-messy-files

This was a Docker compose setup blocker asset, but the primary blind-loop rerun
now turns it into another baseline-solved treatment non-regression guard.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `f25208ace86a`
- baseline score: `1.0`
- baseline first success round: `1`
- treatment arm: `loopx-blind-loop-treatment`
- treatment prompt style: `baseline-safe`
- treatment run id: `60878623ceca`
- treatment score: `1.0`
- treatment first success round: `1`
- historical setup blocker run id: `a1c722810880`
- historical blocker class: `skillsbench_docker_compose_setup_failure`

Interpretation:

The old Docker compose setup blocker remains useful historical
runner-readiness evidence, but it no longer describes the current primary
route. The new blind-loop baseline and baseline-safe treatment both reached
official verifier pass at `1.0` in the first completed agent round. Official
feedback stayed blinded, reward feedback was not forwarded, and no raw task
text, raw logs, verifier output, or trajectory were copied into this analysis.

Why it matters:

- It repairs the previous classification: this case should no longer be counted
  as a current setup blocker for the primary blind-loop route.
- It is not uplift evidence, because baseline already solved the task.
- It is a non-regression guard for baseline-safe treatment prompt framing.
- It shows the local Docker capacity/resource staging repair is sufficient for
  this case family under the current runner path.

Follow-up guidance:

- Do not use this case for uplift claims.
- Rerun it only after a treatment prompt, round, stop-policy, or Docker staging
  change.
- Prefer baseline-failing cases for the next uplift-mining run, while preserving
  this case as a success/non-regression guard.

## Case: SkillsBench citation-check

This was an `/app` mount setup blocker asset, but the primary blind-loop rerun
now turns it into another baseline-solved treatment non-regression guard.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `9b4df14b3ed8`
- baseline score: `1.0`
- baseline first success round: `1`
- treatment arm: `loopx-blind-loop-treatment`
- treatment prompt style: `baseline-safe`
- treatment run id: `d553e635f00c`
- treatment score: `1.0`
- treatment first success round: `1`
- historical setup blocker run id: `cec197c1424a`
- historical blocker class: `skillsbench_environment_app_mount_missing`

Interpretation:

The old `/app` mount setup blocker remains useful historical runner-readiness
evidence, but it no longer describes the current staged primary route. The new
blind-loop baseline and baseline-safe treatment both reached official verifier
pass at `1.0` in the first completed agent round. Official feedback stayed
blinded, reward feedback was not forwarded, and no raw task text, raw logs,
verifier output, or trajectory were copied into this analysis.

Why it matters:

- It repairs the previous classification: this case should no longer be counted
  as a current setup blocker for the primary blind-loop route.
- It is not uplift evidence, because baseline already solved the task.
- It is a non-regression guard for baseline-safe treatment prompt framing.
- It gives a second setup-history-to-success-guard example after
  `organize-messy-files`, which helps keep stale setup blockers out of case
  outcome statistics.

Follow-up guidance:

- Do not use this case for uplift claims.
- Rerun it only after a treatment prompt, round, stop-policy, or task-staging
  change.
- Prefer baseline-failing cases for the next uplift-mining run, while preserving
  this case as a success/non-regression guard.

Canonical product-mode rerun note:

- run group: `skillsbench-citation-check-c9facd4-canonicalbridge-20260624T1815Z`
- route: `loopx-product-mode`
- official score: `0.0`
- failure attribution: `official_verifier_solution_failure`
- lifecycle counters: 8 driver lifecycle checkpoints, 32 successful driver
  lifecycle calls, 0 driver lifecycle failures, 10 agent LoopX CLI calls,
  1 agent state read, and 8 agent state writes.
- verifier policy: `final-only`; intermediate soft verify call count `0`,
  skipped count `8`; official feedback and reward/pass/fail signals were not
  forwarded to the agent.

This rerun does not overturn the older blind-loop non-regression result. It
answers a different product-mode question: the canonical bridge can exercise
LoopX lifecycle, but `final-only` gives the controller no private per-round
reward signal. Therefore the runner continues through the scheduled prompt
budget even when another run history says this case can be solved. In the
historical product-mode `1.0` row, the `1.0` was only observed at the final
official scoring point, so earlier rounds could not have stopped on it.

Every-round product-mode rerun note:

- run group: `skillsbench-citation-check-ef3006e-everyround-cleanup-20260624T2022Z`
- run id: `ac6716eb1ae2`
- route: `loopx-product-mode`
- official score: `0.0`
- failure attribution: `official_verifier_solution_failure`
- lifecycle counters: 1 driver lifecycle checkpoint, 4 driver lifecycle CLI
  calls, 18 agent LoopX CLI calls, 2 agent state reads, 16 agent state writes,
  and 8 task-facing bridge operations.
- verifier policy: `every-round`; intermediate soft verify call count `1`,
  skipped count `0`; soft verifier timeout was enabled at 180 seconds but did
  not trigger in this completed run.

This rerun proves the canonical product-mode driver can produce public-safe
every-round verifier counters and full LoopX lifecycle counters. It stopped
after round 1 because the agent declared done and final official scoring
returned `0.0`. The attribution is therefore solution/case scoped, not
transport, lifecycle, or reward-sampling scoped. The separate soft-timeout
cleanup path is covered by runner smoke and remains a guard for cases whose
intermediate verifier process tree does hang.

Policy outcome:

- Product-mode should default to every-round private soft verification.
- The controller may stop as soon as reward reaches `1.0`.
- Reward, pass/fail, verifier output, and task-private material must remain
  blinded from the agent unless an experiment explicitly studies feedback.
- `final-only` remains useful only as an explicit ablation for measuring the
  cost of withholding all intermediate verifier observations.

## Case: SkillsBench 3d-scan-calc

This was a legacy baseline-pass-only record, but the primary blind-loop rerun
now turns it into another baseline-solved treatment non-regression guard.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `9b1d8be29eb4`
- baseline score: `1.0`
- baseline first success round: `1`
- treatment arm: `loopx-blind-loop-treatment`
- treatment prompt style: `baseline-safe`
- treatment run id: `306537fca3ac`
- treatment score: `1.0`
- treatment first success round: `1`
- historical context: older baseline run `9e5ca7417555` also passed, but was
  not a current primary blind-loop treatment pair.

Canonical product-mode every-round recheck:

- baseline run group:
  `skillsbench-3d-scan-calc-d666545-everyround-baseline-20260624T2047Z`
- baseline run id: `fac3a39fdd9a`
- treatment run group:
  `skillsbench-3d-scan-calc-d666545-everyround-treatment-20260624T2053Z`
- treatment run id: `10d4a914cccc`
- route pair: `raw-codex-autonomous-max5` -> `loopx-product-mode`
- max-rounds budget: `8`
- baseline score / first success round / final round: `1.0` / `1` / `1`
- treatment score / first success round / final round: `1.0` / `1` / `1`
- every-round private soft verifier calls: baseline `1`, treatment `1`
- product-mode pair review: `main_table_ready`; `claim_blocker=none`
- treatment lifecycle counters: checkpoint count `1`, checkpoint round `1`,
  state reads `2`, state writes `16`, refresh-state calls `2`, quota spend-slot
  calls `2`, todo closeout calls `6`
- host-local ACP Codex exec preflight: `passed`

Historical final-only lifecycle trajectory summary:

- baseline summary: `1` round, `7` tool calls, `0` LoopX CLI calls
- treatment summary: `8` rounds, `138` tool calls, `73` LoopX CLI calls
- treatment LoopX CLI state usage: `28` reads, `43` writes, `2` other
- case-local state access in that historical public trace: `0` reads, `0`
  writes

Interpretation:

The old record said the case was solvable by baseline, but it did not answer
whether the current LoopX treatment wrapper preserves that success under
the no-reward primary protocol. The new blind-loop baseline and baseline-safe
treatment both reached official verifier pass at `1.0` in the first completed
agent round. Official feedback stayed blinded, reward feedback was not
forwarded, and no raw task text, raw logs, verifier output, or trajectory were
copied into this analysis.

The canonical product-mode recheck answers a different question: can the
current product-mode lifecycle driver run a real SkillsBench case, sample the
private verifier every round, stop early when reward reaches `1.0`, and still
leave public-safe LoopX lifecycle counters? For this case, yes. Both arms had
an 8-round budget but stopped after round 1 because the private verifier
observed reward `1.0`; the reward/pass/fail/verifier output was not forwarded
to the agent. In treatment, the full case-local lifecycle was visible through
state read/write, refresh, spend, and todo-closeout counters.

The historical final-only lifecycle trace is kept only as overhead and
lifecycle-depth-gap evidence. It predates the every-round recheck, and it shows
that the older product-mode treatment preserved final official success but
needed all `8` rounds and substantial LoopX CLI activity. It should not be used
as the current stop-policy proof.

Why it matters:

- It is not uplift evidence, because baseline already solved the task.
- It expands the baseline-solved non-regression set to a 3D calculation task
  family.
- It checks that baseline-safe treatment prompt framing does not harm a case
  where ordinary Codex ACP can solve the task in the first round.
- It is a good-case proof for the canonical product-mode every-round driver:
  the driver stopped on private reward `1.0` and produced complete lifecycle
  counters.
- It keeps the current policy evidence aligned with the primary blind-loop
  protocol instead of relying on a legacy baseline-only pass.

Follow-up guidance:

- Do not use this case for uplift claims.
- Rerun it only after a treatment prompt, round, stop-policy, or task-staging
  change.
- Prefer baseline-failing cases for the next uplift-mining run, while preserving
  this case as a success/non-regression guard.

## Case: SkillsBench bike-rebalance

This is a baseline-solved non-regression asset and runner-readiness lesson, not
uplift evidence.

Compact evidence:

- benchmark: `skillsbench@1.1`
- original pair run group: `skillsbench-bike-rebalance-blind-loop-20260616T082339CST-popen`
- repaired baseline rerun group: `skillsbench-bike-rebalance-baseline-rerun-20260616T0852CST`
- baseline arm: `codex-acp-blind-loop-baseline`
- original baseline run id: `a22a96cea1fe`
- original baseline failure: `skillsbench_runner_error`
- repaired baseline run id: `7ab4d4e3f194`
- repaired baseline score: `1.0`
- repaired baseline rounds: `1:1`
- repaired baseline first success round: `1`
- treatment arm: `loopx-blind-loop-treatment`
- treatment prompt style: `baseline-safe`
- treatment run id: `239aecc4f3a3`
- treatment score: `1.0`
- treatment rounds: `1:1`
- treatment first success round: `1`

Interpretation:

The first baseline attempt was invalid for score comparison because it ended as
`skillsbench_runner_error` before any recorded round rewards. After the generic
baseline closeout/preflight-state repair, the baseline-only rerun reached
official verifier pass in the first completed round.

The treatment route also reached official verifier pass in the first completed
round, with official feedback blinded and reward feedback not forwarded to the
agent. The score delta is therefore `0.0`: both arms solved the case at `1.0`
in round 1.

Why it matters:

- It prevents a false uplift claim: the treatment pass looked interesting only
  while the baseline runner was broken.
- It proves the repaired baseline route can materialize, solve, and record
  `first_success_round=1` under the no-reward blind protocol.
- It adds a success/non-regression guard: future prompt, continuation, or stop
  policy changes should keep this baseline-solved case at `1.0`.

Follow-up guidance:

- Treat this as a baseline-solved non-regression guard, not a treatment-search
  target.
- Keep the initial `skillsbench_runner_error` as runner-readiness evidence, but
  keep it separate from case-score comparisons.
- Repeat only after a concrete prompt or round-policy change.

## Case: SkillsBench azure-bgp-oscillation-route-leak

This is a clean no-uplift control, setup-repair proof, and product-mode depth
check, not treatment uplift evidence.

Compact evidence:

- benchmark: `skillsbench@1.1`
- run group: `skillsbench-azure-bgp-route-leak-blind-loop-20260616T103700CST`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `ed2c390f39b9`
- baseline score: `0.0`
- baseline rounds: `1:0,2:0`
- treatment arm: `loopx-blind-loop-treatment`
- treatment run id: `8d9511cee40f`
- treatment score: `0.0`
- treatment rounds: `1:0,2:0`
- max5 run group:
  `skillsbench-azure-bgp-oscillation-route-leak-blind-loop-max5-20260616T1649CST`
- max5 baseline run id: `d08c5bf09769`
- max5 baseline score: `0.0`
- max5 baseline rounds: `1:missing,2:0,3:0,4:0,5:0`
- max5 treatment run id: `c50ebc418b8e`
- max5 treatment score: `0.0`
- max5 treatment rounds: `1:missing,2:0,3:0,4:0,5:0`
- product-mode run group:
  `skillsbench-azure-bgp-product-mode-20260617T195844CST`
- product-mode baseline route: `raw-codex-autonomous-max5`
- product-mode baseline run id: `788c64ee1ddd`
- product-mode baseline score: `0.0`
- product-mode baseline rounds: `1:0`
- product-mode baseline stop: agent declared done in round 1 with no remaining
  goals
- product-mode treatment route: `loopx-product-mode`
- product-mode treatment run id: `4002396acce9`
- product-mode treatment score: `0.0`
- product-mode treatment rounds: `1:0,2:0,3:0,4:0,5:0`
- product-mode treatment depth: 5 controller decisions, 5 heartbeat turns, 5
  case-state reads, and 5 case-state writes
- product-mode protected-path edit signals: `0`
- setup patch: staged Codex ACP runtime tools
  (`codex_acp_runtime_tools_patch_applied=true`)

Interpretation:

Earlier attempts on this case failed before solver execution: first in Codex ACP
runtime bootstrap, then in Docker build/container capacity. After adding the
staged runtime-tools patch and clearing only stopped containers plus dangling
image layers, both arms reached two completed blind-loop rounds and official
SkillsBench scoring.

Both the two-round pair and the later max-5 pair scored `0.0`, with official
reward/pass/fail/verifier feedback blinded during the agent loop and rewards
recorded only after each completed round. The subsequent product-mode pair also
stayed `0.0 -> 0.0`: the raw Codex autonomous baseline stopped after round 1
when the agent declared done, while the LoopX product-mode treatment kept
the case alive for all 5 rounds through case-local active-state reads/writes.
The result is therefore a real neutral pair and a depth-control proof: useful
for runner readiness, product-mode parity, and stop-policy analysis, not for
uplift claims. The first round's scalar reward is missing in both earlier max-5
blind-loop arms because only later round and final compact records exposed
scalar reward; this does not change the final-score or best-score conclusion.

Why it matters:

- It proves the SkillsBench runner can now move a fresh Docker case past setup
  into real Codex ACP rounds and official verifier scoring.
- It preserves a no-uplift guard for BGP/network-analysis style tasks.
- It demonstrates that local Docker capacity can masquerade as runner or apt
  setup failure unless recorded separately from case outcome.
- It shows a real product-mode difference: LoopX prevented premature
  "done" collapse and drove five compact-safe rounds, but that extra depth did
  not solve this case.

Follow-up guidance:

- Do not repeat this case until a prompt, stop-policy, or compact-safe semantic
  failure hypothesis changes.
- Keep it in the no-uplift guard set when evaluating future blind-loop policy
  changes.
- Use it as a product-mode depth regression guard: future changes should retain
  case-state init/read/write counters and avoid reward leakage, but should not
  claim uplift unless score improves.
- Do not inspect raw trajectory, logs, or task text unless explicitly authorized;
  use compact summaries first.

## Case: SkillsBench setup-fuzzing-py

This is a runner/setup blocker asset, not a solver-quality signal.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `92aaefc0c077`
- baseline score: missing
- baseline failure: `skillsbench_docker_compose_apt_repository_failure`
- latest setup intervention: staged Dockerfile apt retry/no-cache patch applied
  (`apt_retry_patch_applied=true`, `staged=true`, `task_skills_removed=true`)
- treatment arm: not launched
- treatment run id: n/a
- treatment score: n/a
- treatment failure: n/a

Interpretation:

The case still has not reached solver execution. Compact evidence shows zero
completed agent rounds and no official score. The earlier repaired baseline
uncovered a `codex-acp` startup failure for missing `libssl.so.3`; the current
primary blind-loop baseline has moved past that class and now fails during
Docker compose setup with a compact `apt` repository/GPG/hash-fetch
attribution in the Focal/Oss-Fuzz environment.

The latest aptrepair rerun proves the staged setup patch was not merely missed:
the compact artifact and ledger record `apt_retry_patch_applied=true`, but the
run still completed zero agent rounds and produced no official score. The
remaining blocker is deeper than the current retry/no-cache staging layer.

Why it matters:

- It prevents an environment/runner ABI failure from being counted as a
  benchmark case failure.
- It gives SkillsBench routing a concrete compatibility constraint: Focal-based
  Oss-Fuzz tasks need both agent-runtime compatibility and robust package
  repository setup before they are valid baseline/treatment comparisons.
- It validates the preflight direction: classify startup/setup failures before
  spending treatment budget.
- It makes same-config repeats low value: repeating this case with the current
  apt retry/no-cache patch would mostly re-measure the same setup blocker.

Follow-up guidance:

- Do not launch treatment for this case until the Docker compose apt setup
  failure is repaired or bypassed by a materially different runner route.
- Prefer a non-Focal or already-compatible SkillsBench case for the next
  baseline/treatment pair if immediate paired evidence is needed.
- Keep this case as a setup preflight regression test when changing SkillsBench
  runner bootstrap and Docker setup logic.

## Case: SkillsBench adaptive-cruise-control

This is a second compact setup blocker asset for the SkillsBench Docker apt
route, not a solver-quality signal.

Compact evidence:

- benchmark: `skillsbench@1.1`
- baseline arm: `codex-acp-blind-loop-baseline`
- baseline run id: `235f52dc6a5b`
- baseline score: missing
- baseline failure: `skillsbench_docker_compose_apt_repository_failure`
- setup intervention: staged Dockerfile apt retry/no-cache patch applied
  (`apt_retry_patch_applied=true`, `staged=true`, `task_skills_removed=true`)
- treatment arm: not launched
- treatment score: n/a

Interpretation:

The fresh no-upload baseline probe produced compact result and controller-trace
artifacts quickly, but no initial prompt or follow-up was sent because setup
failed before controller/agent interaction. The same public staging metadata
as the `setup-fuzzing-py` aptrepair run shows that the retry/no-cache patch
entered the staged task. The remaining failure is therefore a broader
SkillsBench Docker apt setup route risk, not a missed patch or task-solving
behavior.

Follow-up guidance:

- Do not launch treatment for this case until baseline reaches agent rounds or
  official scoring.
- Avoid blind random sampling of additional apt-based Docker tasks until either
  a compact task-selection filter excludes likely apt setup blockers or the
  Docker apt setup route changes materially.
- Current runner support: `skillsbench_task_setup_preflight` now reports
  public-safe apt setup risk, and `--fail-fast-on-apt-risk` can close out the
  case as a setup-selection blocker before a full baseline/treatment attempt.
- Keep `adaptive-cruise-control` plus `setup-fuzzing-py` as a two-case setup
  guard when changing SkillsBench runner bootstrap, staging, or Docker setup.

## Case: SWE-Marathon zstd-decoder

This is the first SWE-Marathon product-path verified negative asset with an
extended prompt-polling rerun. It is not an uplift row, not a LoopX connectivity
blocker, and not yet a content-level root-cause claim.

Compact evidence:

- benchmark: `swe-marathon`
- baseline arm: `swe_marathon_host_codex_app_server_goal_baseline`
- baseline run id: `9ae95dbf5ab4`
- baseline score: `1.0`
- baseline wall limit: `3600s`
- baseline actual wall time: `1071.022472s`
- baseline official-timeout comparable: `false`
- treatment arm: `swe_marathon_loopx_prompt_polling_treatment_10800_pr467`
- treatment run id: `1e3c8703e24b`
- treatment score: `0.0`
- treatment wall limit: `900s`
- treatment actual wall time: `3265.878558s`
- treatment official-timeout comparable: `false`
- treatment polling rounds observed: `5` of budget `5`
- treatment follow-up prompts observed: `4`
- treatment failure: `official_verifier_solution_failure`
- first blocker: `none`
- product path: `loopx_inside_case=true`, worker bridge `verified`,
  public LoopX lifecycle/trace observed, and 31 LoopX CLI calls

Interpretation:

The native app-server Goal baseline can solve this CPU/no-CUA SWE-Marathon case
under the current runner. After PR #467, the prompt-driven LoopX treatment also
exercised the intended case-local LoopX lifecycle and reached official scoring
after five controller rounds and four follow-up prompts, but still scored
`0.0`. The old one-round timeout and pre-bridge runtime blockers are therefore
superseded for product-path validation. The remaining issue is solution-phase
quality, prompt/stop policy, or benchmark semantics; public compact evidence
does not expose the exact code-level mistake.

Follow-up guidance:

- Do not claim treatment value from this pair.
- Do not claim a stable LoopX-caused regression from this pair without
  additional phase attribution or a redacted trajectory summary.
- Do not repeat the same case just to prove LoopX connectivity; that part is
  already verified.
- Before a same-case repeat, add compact edit/build/test/verify phase counters
  that distinguish incomplete continuation from wrong solution edits or
  verifier-facing behavior.
- Use this as an extended-round negative guard when changing SWE-Marathon
  prompt-driven polling, case-local LoopX state, or stop policy.

## Cross-Case Lessons

| Lesson | Evidence | Implication |
| --- | --- | --- |
| Connectivity is not case success. | Terminal-Bench needed materialization and closeout repair before scores were meaningful. | Keep lifecycle stages separate: launch, materialization, trial, solver, result, verifier. |
| Historical treatment route can help, but current-protocol claims need reruns. | `multi-source-data-merger` improved from `0.0` to `1.0` under the legacy Terminal-Bench route; under the current protocol, baseline and treatment both scored `1.0`. | Keep the treatment lane alive, but make the main table prefer current product-mode evidence over legacy uplift rows. |
| Score delta is not automatically claimable uplift. | `nginx-request-logging` once showed treatment `1.0` while the hardened baseline `0.0` came from worker Codex materialization failure; after repair, the current comparison is `1.0 -> 1.0`. | Preserve legacy blocked rows as runner lessons, but make the main table prefer repaired comparable evidence. |
| Treatment can preserve baseline success. | `ada-bathroom-plan-repair`, `organize-messy-files`, `citation-check`, `3d-scan-calc`, and `bike-rebalance` scored `1.0` in both blind-loop arms with first_success_round=1. | Keep baseline-solved non-regression guards so treatment prompts do not damage easy wins. |
| Baseline comparability must be repaired before uplift claims. | `bike-rebalance` first looked like a treatment-only pass because the baseline ended with `skillsbench_runner_error`; after baseline repair, the rerun also passed at `1.0`. | Treat initial runner errors as readiness evidence, not case-score deltas. |
| Timeout policy needs phase attribution. | `make-doom-for-mips` default attempts timed out, a 2h relaunch exposed setup timeout, and setup8+2h still needed verifier attribution. | Do not treat a longer timeout as a case result unless setup, worker, solver, result, and verifier phases are compactly separated. |
| Agent exceptions before verifier reward are not clean no-uplift. | `pytorch-model-recovery` has compact `RuntimeError` in both arms with verifier reward absent, and treatment bridge materialization was not proven. | Route these cases to compact exception-hypothesis work before same-task repeat or treatment claims. |
| Treatment can help on SkillsBench too. | `llm-prefix-cache-replay` and `dapt-intrusion-detection` both improved from `0.0` to `1.0` after one reward-feedback automation-loop follow-up. | Keep multiple SkillsBench positive-control cases in the reward-feedback ablation test set. |
| Blind-loop claims need fresh evidence. | `llm-prefix-cache-replay` protocol v10 completed baseline `0.0` and treatment `0.0` with no reward feedback forwarded. | Do not recycle reward-feedback wins as blind-control-plane uplift claims; use blind-loop pairs and `first_success_round` instead. |
| Treatment can regress. | `debug-trl-grpo` dropped from `0.25` to `0.0` under both reward-feedback and blind-loop treatment; in the max-5 blind-loop rerun, baseline held `0.25` for five rounds while treatment fell from early `0.25` partial credit to `0.0` after round 2. | Add negative controls and optimize stop/stabilize policy before scaling treatment claims. |
| Treatment can be neutral. | `civ6-adjacency-optimizer`, `manufacturing-codebook-normalization`, `software-dependency-audit`, `react-performance-debugging`, and `pddl-airport-planning` all stayed `0.0` after blind-loop two-round treatment, while `azure-bgp-oscillation-route-leak` stayed `0.0/0.0` after both a two-round pair and a max-5 pair. | Track no-uplift controls separately from regressions and positive cases, and keep neutral guards in prompt/round-policy validation. |
| Setup repair is necessary but not sufficient. | SkillsBench setup was repaired, then a behavior regression remained. | Separate infra blockers from solver-quality blockers in the ledger and analysis. |
| Baseline launch must reach solver/verifier before treatment. | `ada-bathroom-plan-repair` first produced generic `skillsbench_codex_acp_launch_failed`; after the preflight repair, rerun evidence narrowed it to `skillsbench_codex_acp_binary_missing`. | Block treatment and materialize Codex ACP inside the SkillsBench sandbox before repeating or treating the case. |
| Runner ABI can block before solver execution. | `setup-fuzzing-py` ended with missing `libssl.so.3`/Focal ABI incompatibility and `n_tool_calls=0`. | Preflight task image versus agent binary compatibility; exclude startup blockers from case score statistics. |
| Docker capacity can masquerade as apt/signature failure. | `organize-messy-files` first hit `skillsbench_docker_compose_setup_failure`; after runner staging/resource repair, the primary blind-loop baseline and treatment both scored `1.0`. | Track Docker free space as runner readiness, and update setup-blocked cases after a clean rerun instead of leaving stale blocker classifications. |
| Task staging can repair app-mount setup failures. | `citation-check` first hit `skillsbench_environment_app_mount_missing`; after staged task preparation, the primary blind-loop baseline and treatment both scored `1.0`. | Treat staging/setup blockers as infra facts until a clean comparable pair supersedes them. |
| Apt retry/no-cache staging is not enough for every Docker apt setup. | `setup-fuzzing-py`, `adaptive-cruise-control`, and the product-mode `debug-trl-grpo` raw baseline rerun all recorded apt hardening metadata but still ended before agent rounds with `skillsbench_docker_compose_apt_repository_failure`. A setup-shape scan found only 8 of 87 local SkillsBench tasks are no-apt Docker candidates. | Add a task-selection filter for apt-risk Docker tasks or materially change the apt setup route before spending more full SkillsBench probes on the same blocker. |
| Shallow product-mode lifecycle is not a valid no-uplift claim. | After Docker readiness repair, `paratransit-routing` raw-Codex-autonomous-max5 baseline and the old `loopx-product-mode` treatment both reached agent round 1 and official result at `0.0`, but treatment only recorded `loopx which goal`, with `loopx_state_reads=0` and `loopx_state_writes=0`. | Treat host readiness as repaired but mark this product-mode treatment invalid: goal discovery is not stateful LoopX use. Require state read/write/replan lifecycle before a product-mode pair can enter the main table as no-uplift. |
| Depth-gate stop semantics can recover the paratransit positive behavior. | `paratransit-routing` blind-loop treatment passed in round 1; the old product-mode treatment stopped on `agent_declared_done` at `0.0`; the later depth-gate product-mode rerun continued to round 5 and reached official score `1.0`. | Preserve the depth gate: do not accept declared done at `0.0` unless the case state has no active todo/goal and compact counters show substantive LoopX lifecycle. For content-level root cause, add a stronger public-safe trajectory summarizer or request an explicit raw-trace gate. |
| Apt-risk preflight should happen before full case execution. | A plan-only probe for `setup-fuzzing-py` now emits `skillsbench_task_setup_preflight` with `apt_setup_risk_detected=true` and no raw task text, raw logs, or raw trajectory reads. | Use `--fail-fast-on-apt-risk` or select a non-apt-risk task before launching blind-loop baseline/treatment pairs. |
| Docker capacity and runtime-tools setup are runner readiness, not case quality. | `azure-bgp-oscillation-route-leak` moved from runtime apt/cache and Docker capacity failures to a complete baseline/treatment pair only after staged Codex ACP runtime-tools setup plus bounded dangling-layer cleanup. | Record setup/capacity repairs separately and do not count pre-materialization failures as case attempts. |
| Product-path verification does not prove causal regression. | `zstd-decoder` baseline passed at `1.0`; after PR #467 the LoopX prompt-driven treatment reached official scoring with verified case-local lifecycle, five controller rounds, four follow-ups, and 31 CLI calls, but still scored `0.0`. | Separate "LoopX path exercised" from "treatment improved outcome" and "LoopX caused regression"; add solution-phase counters or a redacted trajectory summarizer before repeating or claiming root cause. |

## Boundary

This file records only compact public-safe evidence. It does not copy raw logs,
task prompts, trajectories, credentials, hidden tests, uploads, or absolute
local paths.
