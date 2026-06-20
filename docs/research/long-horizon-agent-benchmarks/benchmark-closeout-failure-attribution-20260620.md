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
| `swe-marathon` | `find-network-alignments` | Harbor host Codex app-server Goal | `0.0`, `official_verifier_solution_failure` | `official_zero_native_goal_first_closeout_needs_solution_phase_counters` | Teach the Harbor/SWE-Marathon reducer to preserve public-safe edit/test/verify phase counters before treating this as model-capability evidence. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | `paired_zero_acp_blind_loop_non_native_goal_no_uplift` | Stop using more ACP blind-loop repeats as primary Codex Goal evidence; implement a native SkillsBench app-server Goal worker first. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | `paired_zero_acp_blind_loop_non_native_goal_no_uplift` | Keep as a stability canary only until the native SkillsBench app-server Goal worker exists. |

## What This Changes

Terminal-Bench and SWE-Marathon have crossed the important infrastructure
line: app-server Goal can start, run, reach verifier, and produce compact
official closeouts. Their current failures are no longer setup blockers.
The next missing piece is solution-phase attribution.

SkillsBench is different. The two latest cases prove that setup, prewarm, ACP
rounds, and official scoring can complete. They do not prove native Codex Goal
behavior, because the route is still BenchFlow ACP blind-loop. The next
engineering slice should therefore be a native app-server Goal worker, not
another same-policy repeat.

## Durable Rule

Do not rotate merely because a row has a compact result. Rotate only after the
case has a refined attribution and one of these is true:

- the next obligation is a different benchmark lane;
- the failure is already precise enough for a treatment/control comparison;
- the current lane is blocked on a named reducer or worker capability.
