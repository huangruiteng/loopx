# Benchmark Closeout Failure Attribution 2026-06-20

This note turns the latest compact benchmark closeouts into public-safe failure
attribution. The goal is to stop treating a final `0.0` score as the end of
debugging. A compact closeout answers "what did the verifier record"; this
layer answers "what should the next engineering move be."

Public boundary:

- no raw task text, raw trajectories, verifier output, raw logs, credentials,
  uploads, leaderboard submissions, or remote absolute paths are copied here;
- compact refs, run ids, case ids, route names, and public-safe phase labels
  are allowed;
- raw trajectories and verifier tails remain private runtime evidence.

Machine-readable companion:
`benchmark-closeout-failure-attribution-20260620.json`.

## Policy

Every benchmark case closeout should get failure attribution before the next
rotation. The minimum row is:

- compact run id and route;
- whether this is native Codex app-server Goal evidence;
- official score/pass/failure class;
- what has been ruled out;
- what remains unknown;
- the next reducer, runner, or worker obligation.

`official_verifier_solution_failure` means the runner reached the official
verifier and the verifier returned a failing score. It is not precise enough to
choose the next action by itself: it can hide timeout, incomplete edits, wrong
solution, a weak worker policy, or a bad canary.

## Case Attribution

| Benchmark | Case | Route | Compact Result | Refined Attribution | Next Obligation |
| --- | --- | --- | --- | --- | --- |
| `terminal-bench@2.0` | `build-cython-ext` | host Codex app-server Goal | `0.0`, `official_verifier_solution_failure`; historical compact control `53729101fea3` scored `1.0` | `official_zero_native_goal_regression_needs_phase_attribution` | Add public-safe Terminal-Bench phase counters and compare against the historical passing control before launching more treatment on this case. |
| `terminal-bench@2.0` | `multi-source-data-merger` | host Codex app-server Goal observation | `0.0`, `official_verifier_solution_failure`; current route reached official scoring and wrote compact result | `official_zero_current_app_server_goal_baseline_needs_phase_or_treatment_comparison` | Do not treat this as a setup blocker. Compare against current-protocol passing rows and launch either a treatment arm or an alternate pass/control case before making route-quality claims. |
| `terminal-bench@2.0` | `nginx-request-logging` | host Codex app-server Goal observation | `1.0`, official pass; raw transcript not recorded | `native_goal_route_sanity_pass_current_protocol_control` | Use as route sanity evidence that app-server Goal can complete a Terminal-Bench pass/control case; do not spend another primary slot rerunning the same observation unless it is needed as a regression guard. |
| `swe-marathon` | `find-network-alignments` | Harbor host Codex app-server Goal | `0.0`, `official_verifier_solution_failure` | `official_zero_native_goal_first_closeout_needs_solution_phase_counters` | Teach the Harbor/SWE-Marathon reducer to preserve public-safe edit/test/verify phase counters before treating this as model-capability evidence. |
| `swe-marathon` | `rust-c-compiler` | Harbor host Codex app-server Goal, prewarmed/larger-budget r2 | `0.0`, `official_verifier_solution_failure`; setup, agent execution, official verifier, and job closeout completed | `official_zero_native_goal_second_closeout_setup_cleared_needs_solution_phase_counters` | Stop treating this case as an environment blocker; add public-safe edit/test/verify counters or run a matched treatment/alternate small SWE case before making model-quality claims. |
| `skillsbench@1.1` | `react-performance-debugging` | native app-server Goal baseline, high reasoning | `0.0`, `skillsbench_runner_error`; public compact shows worker connection but no worker trace directory or turn-start evidence | `native_goal_worker_connected_trace_dir_missing_not_solver_quality_evidence` | Repair the native worker public trace materialization path before using this or any new SkillsBench native Goal row as solver-quality baseline evidence. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | `paired_zero_acp_blind_loop_non_native_goal_no_uplift` | Stop using more ACP blind-loop repeats as primary Codex Goal evidence; implement a native SkillsBench app-server Goal worker first. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | `paired_zero_acp_blind_loop_non_native_goal_no_uplift` | Keep as a stability canary only until the native SkillsBench app-server Goal worker exists. |

## What This Changes

Terminal-Bench and SWE-Marathon have crossed the important infrastructure
line: app-server Goal can start, run, reach verifier, and produce compact
official closeouts. `nginx-request-logging` now provides a current-route pass
control, while `multi-source-data-merger` shows a current-route zero that needs
phase or treatment comparison before route-quality claims. `rust-c-compiler`
r2 also clears the previous SWE-Marathon setup blocker. These current failures
are no longer setup blockers; the next missing piece is solution-phase
attribution.

SkillsBench is different. The ACP rows prove that setup, prewarm, rounds, and
official scoring can complete. The native app-server Goal canary proves host
worker connection, but it still lacks public worker turn trace materialization.
The next engineering slice should therefore be the native worker trace path,
not another same-policy repeat.

## Durable Rule

Do not rotate merely because a row has a compact result. Rotate only after the
case has a refined attribution and one of these is true:

- the next obligation is a different benchmark lane;
- the failure is already precise enough for a treatment/control comparison;
- the current lane is blocked on a named reducer or worker capability.
