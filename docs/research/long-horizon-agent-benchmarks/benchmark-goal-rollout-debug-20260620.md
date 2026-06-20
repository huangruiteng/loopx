# Benchmark Goal Rollout Debug 2026-06-20

This note is a public-safe rollout/debug layer for the benchmark cases that
closed after the cloud-host app-server Goal pivot. It sits between two existing
layers:

- `benchmark-run-ledger.json` records compact final outcomes;
- private cloud-host artifacts and trajectories retain raw task/log/verifier
  evidence.

The missing layer was the one operators and future agents need for debugging:
what path the case took, which Goal Harness todo/status transition drove it,
where official scoring was reached, and which next question should be answered
before spending another case rotation.

Public boundary:

- no raw task text, raw trajectories, verifier output, raw logs, credentials,
  uploads, leaderboard submissions, or remote absolute paths are copied here;
- artifact references are compact logical refs only;
- this file can name case ids, compact run ids, failure classes, status
  classifications, and public-safe phase labels.

Machine-readable companion:
`benchmark-goal-rollout-debug-20260620.json`.

Failure-attribution companion:
`benchmark-closeout-failure-attribution-20260620.md`.

## Control-Plane Flow

| Time | GH classification / todo | Meaning |
| --- | --- | --- |
| `2026-06-20T23:25:02+08:00` | `benchmark_app_server_goal_runtime_lane_progress_20260620` | Three benchmark lanes were active; next action was polling Terminal-Bench, SWE-Marathon, and SkillsBench until each yielded compact result or precise blocker. |
| `2026-06-20T23:57:24+08:00` | `benchmark_cloud_goal_closeouts_pr319_merged_20260620` | PR #319 landed the app-server Goal helpers, reducers, SOP updates, and compact case closeouts. |
| `2026-06-20T23:57:59+08:00` | `benchmark_next_action_successor_sync_20260620` / `todo_9b33c85f5b7c` | Control plane moved to next case rotation. |
| `2026-06-21T00:03:04+08:00` | `todo_c5ca9f496ed6` | Owner redirected the next step from rotation to rollout/traj analysis; this todo was created and claimed by `codex-main-control`. |

The important correction is that rotation should not be treated as the next
automatic step until this rollout has been inspected. The current state tells
us "what scored"; it does not yet tell us enough about "why this was the right
next case" or "which phase failed".

## Case Rollouts

| Benchmark | Case | Route | Official Result | Rollout Read |
| --- | --- | --- | --- | --- |
| `terminal-bench@2.0` | `build-cython-ext` | host Codex app-server Goal | `0.0`, `official_verifier_solution_failure` | Native Goal route reached official Terminal-Bench closeout. Historical compact control `53729101fea3` passed this case with score `1.0`, so the current zero is not enough to call the case impossible. The missing evidence is public-safe solution-phase attribution. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | Runner and verifier reached official score after runtime-layer refactor, but this is not native app-server Goal evidence. Treat it as setup/verifier progress and weak-policy no-uplift evidence. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | BenchFlow ACP blind-loop baseline/treatment | `0.0/0.0`, `paired_no_score_uplift` | Setup/prewarm no longer blocks the case. It is currently a stability canary, not a proof that Goal Harness improves SkillsBench task outcome. |
| `swe-marathon` | `find-network-alignments` | Harbor host Codex app-server Goal | `0.0`, `official_verifier_solution_failure` | First native Goal SWE-Marathon cloud closeout. Harbor reached environment operation, agent execution, verifier, and job closeout; the next missing signal is whether the zero came from timeout/incomplete edit or wrong solution. |

## Cross-Case Findings

1. Terminal-Bench and SWE-Marathon are now real app-server Goal baseline
   closeouts. Their failures are case/solution failures, not setup blockers.
2. SkillsBench still lacks a native app-server Goal worker. Its latest rows
   prove runner/verifier readiness but should not be over-claimed as Codex
   Goal baseline evidence.
3. `official_verifier_solution_failure` is too broad for ongoing debugging.
   It should eventually split into public-safe sublabels such as
   `official_verifier_completed_zero_score`,
   `agent_goal_timeout_then_official_zero`, and
   `solution_phase_incomplete`.
4. A rollout file is the right public artifact for this gap: it can show
   control-plane phase, case route, compact result, and next debug question
   while keeping raw trajectory and verifier evidence private.

## Immediate Debug Questions

- Terminal-Bench: can the reducer expose public-safe app-server/agent phase
  counters, especially timeout versus complete-but-wrong, without copying raw
  trial fields?
- SkillsBench: should the next implementation slice be a native app-server
  Goal worker instead of more ACP blind-loop repeats?
- SWE-Marathon: can Harbor expose compact edit/test/verify phase counters so
  `official_verifier_solution_failure` is not the only post-closeout label?
- Goal Harness: should active-case status and run ledger both link to this
  rollout layer so future agents can debug the path, not only the score?

## Proposed Durable Shape

For each real benchmark case closeout, write one public-safe rollout row with:

- `benchmark_id`, `case_id`, `run_id`, route, arm, compact artifact ref;
- native Goal evidence flag;
- official score/pass/failure class/failure scope;
- phase labels such as runner preflight, app-server Goal start, agent
  execution, official verifier, ledger writeback;
- GH todo/status transitions that selected, monitored, closed, and followed up
  the run;
- next debug questions.

Raw trajectories remain private. Public trajectory summaries should be counters
only, following `goal_harness/benchmark_trajectory.py`.

The follow-up failure-attribution layer narrows these rows into concrete
obligations: Terminal-Bench and SWE-Marathon need public-safe solution-phase
counters, while SkillsBench should stop repeating ACP blind-loop pairs as the
primary Goal evidence and implement a native app-server Goal worker.
