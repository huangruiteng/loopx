# Benchmark Active Case Status 2026-06-20

This note tracks the current cloud-host benchmark case queue after the
agent-runtime refactor and the switch to Codex app-server Goal as the default
host-agent surface. It is an operational status layer, not the final evidence
ledger.

Public boundary:

- no raw task text, raw trajectories, verifier output, raw logs, credentials,
  uploads, or leaderboard submissions are copied here;
- remote absolute paths are intentionally omitted;
- completed rows should be upserted into `benchmark-run-ledger.json` from
  compact `benchmark_run_v0` artifacts before case-analysis interpretation;
- running rows stay here until they produce a compact result or a precise
  compact blocker.

## Current Protocol

- Host-side Codex Goal baseline should use app-server Goal when available:
  `thread/start`, `thread/goal/set`, `thread/goal/get`, then `turn/start`.
- TUI `/goal` is a fallback/diagnostic surface, not the default automation
  baseline.
- Agent runtime should be a preinstalled stable layer. Case containers should
  run the task, official tests, and benchmark verifier only.
- Remote benchmark checkout patches must follow
  `docs/benchmark-developer-workflow.md#remote-checkout-patch-protocol`.
- After a compact closeout batch, write or update a public-safe rollout/debug
  layer before rotating new cases. The first such artifact is
  `benchmark-goal-rollout-debug-20260620.md`: it links compact result rows,
  GH todo/status transitions, route shape, failure attribution, and next debug
  questions without copying raw task text, logs, trajectories, verifier output,
  credentials, or private paths.
- After each compact closeout, write public-safe failure attribution before
  treating the case as done or rotating away. The first attribution artifact is
  `benchmark-closeout-failure-attribution-20260620.md`; it separates native
  app-server Goal zero-score closeouts from non-native ACP blind-loop
  no-uplift evidence and names the next reducer/worker obligation.

## Active Cloud Batch

Batch id: `parallel-benchmark-20260620T131254Z`.

| Benchmark | Case | Route / Arm | Compact Status | Current Status | Next Action |
| --- | --- | --- | --- | --- | --- |
| `terminal-bench@2.0` | `build-cython-ext` | host Codex app-server Goal, marker/official-verifier gated | latest observe-only compact official score `1.0`; ledger upserted under `terminal-bench-build-cython-ext-app-server-observe-pr346-r1-20260621T203200Z`; earlier completion-aware r2 scored `0.0`; raw transcript not recorded | completed: the observe-only native Goal closeout recovered the historical pass-case result while preserving public compact boundaries | Treat as a pass-case route canary. Do not spend another primary slot retrying the same route; next Terminal-Bench work should launch a treatment arm or move to a different historical pass/control case. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | BenchFlow ACP blind-loop baseline | compact official score `0.0`; ledger upserted under `gh-skillsbench-llm-prefix-cloud-pair-r1-20260620` | completed | Treat as no-uplift runtime-refactor sanity, not as native Codex Goal baseline evidence. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | Goal Harness blind-loop treatment | compact official score `0.0`; ledger upserted under `gh-skillsbench-llm-prefix-cloud-pair-r1-20260620` | completed | Pair with the baseline row as `paired_no_score_uplift`; next SkillsBench work should either implement the app-server Goal surface or pick the next ACP-compatible canary explicitly as non-native-Goal evidence. |
| `swe-marathon` | `find-network-alignments` | host Codex app-server Goal through Harbor bridge | compact official score `0.0`; ledger upserted under `gh-swe-find-network-alignments-host-app-server-goal-r6-20260620`; `thread/goal/get` confirmed `active`; `turn/start` id present; raw transcript not recorded; bridge responses observed | completed: app-server route reached Harbor environment operation, agent execution, verifier, and job closeout; official verifier returned `0.0` | Treat as a real native Goal baseline result with `official_verifier_solution_failure`; next SWE-Marathon work should either run a second small case or compare a treatment under the same no-upload boundary. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | BenchFlow ACP blind-loop baseline | compact official score `0.0`; ledger upserted under `gh-skillsbench-tictoc-cloud-pair-r2-20260620` | completed as r2; r1 duplicate rerun may continue as background validation | Treat as ACP-compatible baseline evidence: runner/verifier completed, but the selected case did not score. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | Goal Harness blind-loop treatment | compact official score `0.0`; ledger upserted under `gh-skillsbench-tictoc-cloud-pair-r2-20260620` | completed as r2; r1 duplicate rerun may continue as background validation | Pair with the ACP baseline as `paired_no_score_uplift`; next SkillsBench work should rotate to another early case or implement a native app-server Goal worker surface. |
| `skillsbench@1.1` | `llm-prefix-cache-replay`, `tictoc-unnecessary-abort-detection` | native app-server Goal baseline | post-PR-353 compact pair ledgered under `skillsbench-native-goal-post353-20260620T220003Z`; both invoke native Goal and connect the host worker; public controller trace present; public worker trace count `0` | completed as route/runner observation: both rows classify as `skillsbench_runner_error`, not solver-quality evidence | Repair or explicitly classify missing public worker trace before using native Goal as the SkillsBench quality baseline; next SkillsBench slot should either fix worker trace or select a different canary with the repaired trace path. |

Failure-attribution update:

- `build-cython-ext` is now a native Goal pass-case canary under the
  observe-only app-server route: the latest compact closeout scored `1.0`,
  while the earlier completion-aware rerun scored `0.0`. Treat the difference
  as runner/route phase evidence, not as a task-difficulty blocker.
- `find-network-alignments` is now classified as
  `official_zero_native_goal_first_closeout_needs_solution_phase_counters`.
- both SkillsBench pairs are classified as
  `paired_zero_acp_blind_loop_non_native_goal_no_uplift`; the next primary
  SkillsBench engineering slice is no longer "build the worker" but
  "repair or explain public worker trace materialization" for the native
  app-server Goal worker.

## Rerun Queue After App-Server Sync

The queue below is the near-term order for rerunning earlier cases under the
current host-runtime protocol. It should be updated after every compact result
or blocker.

| Priority | Benchmark | Case | Reason To Rerun | Required Before Launch |
| --- | --- | --- | --- | --- |
| P0 | `terminal-bench@2.0` | `build-cython-ext` | route canary with historical pass and latest observe-only native Goal result `1.0` | route canary complete; next slot should be treatment or a different historical pass/control case, not another route-readiness retry. |
| P0 | `swe-marathon` | `find-network-alignments` | first active SWE-Marathon cloud case completed at official score `0.0` | completed baseline; next slot should be a second small case or matching treatment arm. |
| P0 | `skillsbench@1.1` | `llm-prefix-cache-replay` | runtime-refactor pair completed at `0.0/0.0`; native Goal post-PR-353 canary connected but produced no public worker trace | no immediate same-policy rerun; repair native worker trace or choose a new canary through the repaired trace path. |
| P1 | `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | previously setup-blocked; useful verifier/runtime canary | compact closeout produced `0.0/0.0`; do not spend another primary slot here unless using it as a duplicate stability check. |
| P1 | `terminal-bench@2.0` | `make-doom-for-mips` | timeout/continuation attribution candidate | timeout phase attribution and app-server route canary complete. |
| P1 | `terminal-bench@2.0` | `mteb-retrieve` | environment setup blocker candidate | environment setup preflight proves the task reaches agent or writes a compact blocker. |
| P1 | `skillsbench@1.1` | `travel-planning` | recent cloud case completed at `0.0`; good low-risk sanity/control case | decide whether the next run is ACP control or native Goal route experiment. |
| P2 | `terminal-bench@2.0` | `multi-source-data-merger`, `nginx-request-logging`, `large-scale-text-editing` | historical pass/non-regression controls | rerun only after the app-server route needs pass-case controls. |

## Update Rule

1. Poll active cloud runs with `scripts/benchmark_run_status_snapshot.py`.
2. If a compact `benchmark_run_v0` exists, upsert it into
   `benchmark-run-ledger.json` and regenerate the Markdown ledger.
3. If no compact result exists but the run has a bounded blocker, write a
   compact blocker artifact and update this file.
4. Promote a case into `benchmark-case-analysis.json` only after the compact
   result teaches a durable routing, uplift, no-uplift, regression, or
   infrastructure lesson.
5. For closeout batches with ambiguous zero scores, update the rollout/debug
   layer before launching another rotation so future agents can inspect the GH
   state flow and runner phase boundary, not only the final score.
6. For every completed case, add or update a failure-attribution row before
   selecting the next rotation. A zero score with only
   `official_verifier_solution_failure` is not precise enough to choose the next
   case by itself.
