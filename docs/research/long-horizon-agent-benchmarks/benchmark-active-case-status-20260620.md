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

Latest batch id: `parallel-benchmark-20260621T134151-markerfix`.

| Benchmark | Case | Route / Arm | Compact Status | Current Status | Next Action |
| --- | --- | --- | --- | --- | --- |
| `terminal-bench@2.0` | `multi-source-data-merger` | host Codex app-server Goal baseline observation | compact official score `0.0`; ledger upserted under `terminal-bench-multi-source-data-merger-app-server-goal-20260620T235333Z` as `codex_app_server_goal_observation`; raw transcript not recorded | completed: the cloud app-server Goal rerun reached official scoring and failed verification | Treat as a current-route baseline observation for this historical pass/control case, not a paired comparison. Do not infer runner breakage from score alone; compare against the previous current-protocol pass rows before selecting a treatment or alternate pass-control case. |
| `terminal-bench@2.0` | `nginx-request-logging` | host Codex app-server Goal alternate pass/control observation | compact official score `1.0`; ledger upserted under `terminal-bench-nginx-request-logging-app-server-goal-20260621T001123Z` as `codex_app_server_goal_observation`; raw transcript not recorded | completed: the cloud app-server Goal route reached official scoring and passed | Treat as a route sanity pass: current app-server Goal can solve at least one historical pass/control case. Next Terminal-Bench work should avoid another identical observation-only pass and instead choose treatment or a case with unresolved route/debug value. |
| `skillsbench@1.1` | `react-performance-debugging` | native app-server Goal baseline, high reasoning | compact official score `0.0`; ledger upserted under `skillsbench-react-performance-native-goal-20260620T235333Z`; failure attribution `skillsbench_runner_error`; public compact shows host worker connected but no public worker turn trace | completed as route/runner observation, not solver-quality evidence | Repair or explain native worker trace materialization before treating this as a SkillsBench quality baseline; do not launch more native SkillsBench cases through this route until the worker trace reaches turn-start/turn-complete evidence or writes a precise blocker. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | native app-server Goal baseline, marker-completion handoff | compact official score `0.0`; ledger upserted under `parallel-benchmark-20260621T134151-markerfix`; failure attribution `official_score_zero_case_failure`; worker completion marker observed and deleted; no raw transcript recorded | completed: the native SkillsBench route now reaches official closeout instead of stopping at worker handoff | Treat as handoff repair evidence, not a model-quality pass. Next SkillsBench work should add public-safe solution-phase counters or run a matched treatment/next canary through the same marker route. |
| `swe-marathon` | `rust-c-compiler` | host Codex app-server Goal completion-aware, prewarmed/larger-budget r2 | compact official score `0.0`; ledger upserted under `swe-marathon-rust-c-compiler-app-server-r2-20260621T004146Z`; setup, agent execution, and official verifier completed; raw logs, task text, and trajectories not read | completed: the earlier setup blocker is superseded by a real native Goal zero-score closeout | Treat as the second SWE-Marathon native Goal baseline failure with `official_verifier_solution_failure`; next SWE work should add solution-phase counters or run a matched treatment/alternate small case under the same no-upload boundary. |
| `swe-marathon` | `rust-c-compiler` | LoopX packet-only observation, host app-server Goal with compact access packet | compact official score `0.0`; ledger upserted under `swe-marathon-rust-c-compiler-treatment-20260621T060729Z`; LoopX packet injected, completion marker observed, bridge request count `70`; raw logs, task text, trajectories, and loop-controller trace not read/recorded | completed: packet-only route reached official verifier, but it is not the prompt-driven polling test arm | Treat as route-safety evidence only. The comparable test arm still needs prompt-driven polling with scheduled continuations, blinded official feedback, and public-safe controller trace. |
| `swe-marathon` | `zstd-decoder` | host Codex app-server Goal baseline r2 | compact official score `1.0`; ledger upserted under `swe-marathon-zstd-decoder-baseline-r2-20260621T062826Z`; `loopx_inside_case=false`; raw logs, task text, and trajectories not read | completed: baseline pass/control reached official scoring and passed | Treat as the first clean SWE-Marathon native Goal baseline pass. Next comparable work is the same-case LoopX prompt-polling test with scheduled continuations and public-safe controller trace. |
| `swe-marathon` | `zstd-decoder` | LoopX prompt-driven polling treatment, case-local GH CLI lifecycle | compact official score `0.0`; ledger upserted under `swe-marathon-zstd-decoder-gh-prompt-polling-pr433-20260621T110515Z`; `loopx_inside_case=true`; worker bridge verified; case-local GH lifecycle observed with public trace and 12 GH CLI calls; first blocker `harbor_prompt_polling_round_timeout_before_completion`; raw logs, task text, trajectories, and verifier output not read | completed: prompt-driven treatment reached official scoring and scored below the native Goal baseline, but the comparison is timeout-confounded | Treat as product-path verified, timeout-confounded negative evidence, not as uplift or stable GH-caused regression. Baseline used a 3600s wall limit and ran 1071.022472s; treatment used the official 900s limit, observed one polling round, no follow-up prompts, and stopped at 923.370177s. Next SWE work should match timeout envelopes or add public-safe solution/round-timeout counters before changing the main claim table. |
| `terminal-bench@2.0` | `build-cython-ext` | host Codex app-server Goal, marker/official-verifier gated | latest observe-only compact official score `1.0`; ledger upserted under `terminal-bench-build-cython-ext-app-server-observe-pr346-r1-20260621T203200Z`; earlier completion-aware r2 scored `0.0`; raw transcript not recorded | completed: the observe-only native Goal closeout recovered the historical pass-case result while preserving public compact boundaries | Treat as a pass-case route canary. Do not spend another primary slot retrying the same route; next Terminal-Bench work should launch a treatment arm or move to a different historical pass/control case. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | BenchFlow ACP blind-loop baseline | compact official score `0.0`; ledger upserted under `gh-skillsbench-llm-prefix-cloud-pair-r1-20260620` | completed | Treat as no-uplift runtime-refactor sanity, not as native Codex Goal baseline evidence. |
| `skillsbench@1.1` | `llm-prefix-cache-replay` | LoopX blind-loop treatment | compact official score `0.0`; ledger upserted under `gh-skillsbench-llm-prefix-cloud-pair-r1-20260620` | completed | Pair with the baseline row as `paired_no_score_uplift`; next SkillsBench work should either implement the app-server Goal surface or pick the next ACP-compatible canary explicitly as non-native-Goal evidence. |
| `swe-marathon` | `find-network-alignments` | host Codex app-server Goal through Harbor bridge | compact official score `0.0`; ledger upserted under `gh-swe-find-network-alignments-host-app-server-goal-r6-20260620`; `thread/goal/get` confirmed `active`; `turn/start` id present; raw transcript not recorded; bridge responses observed | completed: app-server route reached Harbor environment operation, agent execution, verifier, and job closeout; official verifier returned `0.0` | Treat as a real native Goal baseline result with `official_verifier_solution_failure`; next SWE-Marathon work should either run a second small case or compare a treatment under the same no-upload boundary. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | BenchFlow ACP blind-loop baseline | compact official score `0.0`; ledger upserted under `gh-skillsbench-tictoc-cloud-pair-r2-20260620` | completed as r2; r1 duplicate rerun may continue as background validation | Treat as ACP-compatible baseline evidence: runner/verifier completed, but the selected case did not score. |
| `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | LoopX blind-loop treatment | compact official score `0.0`; ledger upserted under `gh-skillsbench-tictoc-cloud-pair-r2-20260620` | completed as r2; r1 duplicate rerun may continue as background validation | Pair with the ACP baseline as `paired_no_score_uplift`; next SkillsBench work should rotate to another early case or implement a native app-server Goal worker surface. |
| `skillsbench@1.1` | `llm-prefix-cache-replay`, `tictoc-unnecessary-abort-detection` | native app-server Goal baseline | post-PR-353 compact pair ledgered under `skillsbench-native-goal-post353-20260620T220003Z`; both invoke native Goal and connect the host worker; public controller trace present; public worker trace count `0` | completed as route/runner observation: both rows classify as `skillsbench_runner_error`, not solver-quality evidence | Repair or explicitly classify missing public worker trace before using native Goal as the SkillsBench quality baseline; next SkillsBench slot should either fix worker trace or select a different canary with the repaired trace path. |

Failure-attribution update:

- `build-cython-ext` is now a native Goal pass-case canary under the
  observe-only app-server route: the latest compact closeout scored `1.0`,
  while the earlier completion-aware rerun scored `0.0`. Treat the difference
  as runner/route phase evidence, not as a task-difficulty blocker.
- `multi-source-data-merger` rerun under the cloud app-server Goal baseline
  reached official scoring but returned `0.0` with
  `official_verifier_solution_failure`. This is a current-route baseline
  failure for a historical pass/control case, not a setup blocker.
- `nginx-request-logging` under the same cloud app-server Goal route reached
  official scoring and passed at `1.0`. This is current route evidence that
  app-server Goal can complete at least one Terminal-Bench pass/control case;
  `multi-source-data-merger` should be treated as case-specific or phase-
  specific until a paired treatment/alternate route explains it.
- `find-network-alignments` is now classified as
  `official_zero_native_goal_first_closeout_needs_solution_phase_counters`.
- `rust-c-compiler` r2 superseded the earlier setup blocker: the
  prewarmed/larger-budget app-server Goal route reached setup, agent execution,
  official verifier, and job closeout, then scored `0.0` with
  `official_verifier_solution_failure`. Treat it as native Goal solution
  evidence needing phase attribution, not as Docker capacity evidence.
- `rust-c-compiler` packet-only LoopX observation also reached official
  verifier and scored `0.0` with `official_verifier_solution_failure`.
  Classify it as route-safety evidence, not as the prompt-driven polling test
  arm. A comparable test needs scheduled continuation prompts with official
  feedback blinded and public-safe controller trace. The next SWE-Marathon slot
  should either run that prompt-polling test or move to another CPU/no-CUA
  baseline case such as `zstd-decoder`, not repeat the same packet-only route
  blindly.
- `zstd-decoder` now has the first clean SWE-Marathon native Goal baseline pass
  and a prompt-driven LoopX treatment closeout. Baseline r2 reached
  official score `1.0`; the GH treatment reached official scoring with a
  verified case-local lifecycle and 12 public-safe GH CLI calls, but returned
  `0.0` with first blocker
  `harbor_prompt_polling_round_timeout_before_completion`. Treat it as
  product-path verified, timeout-confounded negative evidence: the baseline
  used a 3600s wall limit and ran 1071.022472s, while treatment used the
  official 900s limit, observed one polling round, emitted no follow-up prompt,
  and stopped at 923.370177s. This proves the treatment path ran, not that GH
  caused a stable regression.
- `react-performance-debugging` has a native app-server Goal compact
  closeout at `0.0` with `skillsbench_runner_error`. The public compact proves
  host worker connection but not turn-start/turn-complete worker trace
  materialization, so classify it as route/runner evidence rather than model
  solving evidence.
- `llm-prefix-cache-replay` under the marker-completion native app-server Goal
  worker now reaches official SkillsBench closeout at `0.0` with
  `official_score_zero_case_failure`. This supersedes the worker-handoff
  blocker for that route; the next missing signal is public-safe solution-phase
  attribution, not another connectivity retry.
- both SkillsBench pairs are classified as
  `paired_zero_acp_blind_loop_non_native_goal_no_uplift`; the next primary
  SkillsBench engineering slice is to compare native marker-route case behavior
  against treatment or phase counters instead of repeating ACP blind-loop
  evidence.

## Rerun Queue After App-Server Sync

The queue below is the near-term order for rerunning earlier cases under the
current host-runtime protocol. It should be updated after every compact result
or blocker.

| Priority | Benchmark | Case | Reason To Rerun | Required Before Launch |
| --- | --- | --- | --- | --- |
| P0 | `terminal-bench@2.0` | `build-cython-ext` | route canary with historical pass and latest observe-only native Goal result `1.0` | route canary complete; next slot should be treatment or a different historical pass/control case, not another route-readiness retry. |
| P0 | `terminal-bench@2.0` | `multi-source-data-merger` | latest cloud app-server Goal baseline reached official scoring but failed at `0.0` | compare with previous current-protocol pass rows; next slot should be treatment or alternate pass/control rather than another identical baseline retry. |
| P0 | `terminal-bench@2.0` | `nginx-request-logging` | latest cloud app-server Goal observation reached official score `1.0` | complete for route sanity; do not rerun immediately unless a future regression needs a fast pass/control guard. |
| P0 | `swe-marathon` | `find-network-alignments` | first active SWE-Marathon cloud case completed at official score `0.0` | completed baseline; next slot should be a second small case or matching treatment arm. |
| P0 | `swe-marathon` | `rust-c-compiler` | official README example and CPU-oriented case; r2 setup/agent/verifier completed at official score `0.0`; packet-only LoopX observation also completed at `0.0` | route-safety observation recorded; comparable test requires prompt-driven polling with controller trace before any no-uplift claim. |
| P0 | `swe-marathon` | `zstd-decoder` | no-internet CPU-only case in the first full-suite subset; native Goal baseline r2 passed at official score `1.0`; prompt-driven LoopX treatment completed at `0.0` with verified case-local lifecycle but unequal timeout envelope | paired evidence recorded as product-path verified, timeout-confounded negative; next slot should match timeout envelopes or add solution/timeout counters before claiming treatment value or stable regression. |
| P0 | `skillsbench@1.1` | `llm-prefix-cache-replay` | runtime-refactor pair completed at `0.0/0.0`; marker-completion native Goal rerun reached official closeout at `0.0` | do not rerun solely for handoff; add public-safe solution-phase counters, run matched treatment, or choose a new canary through the repaired marker route. |
| P0 | `skillsbench@1.1` | `react-performance-debugging` | native app-server Goal canary closed at `0.0` with `skillsbench_runner_error`; host worker connected but no public worker turn trace materialized | repair or explicitly gate native worker trace materialization before launching additional SkillsBench native Goal cases. |
| P1 | `skillsbench@1.1` | `tictoc-unnecessary-abort-detection` | previously setup-blocked; useful verifier/runtime canary | compact closeout produced `0.0/0.0`; do not spend another primary slot here unless using it as a duplicate stability check. |
| P1 | `terminal-bench@2.0` | `make-doom-for-mips` | timeout/continuation attribution candidate | timeout phase attribution and app-server route canary complete. |
| P1 | `terminal-bench@2.0` | `mteb-retrieve` | environment setup blocker candidate | environment setup preflight proves the task reaches agent or writes a compact blocker. |
| P1 | `skillsbench@1.1` | `travel-planning` | recent cloud case completed at `0.0`; good low-risk sanity/control case | decide whether the next run is ACP control or native Goal route experiment. |
| P2 | `terminal-bench@2.0` | `large-scale-text-editing` | historical pass/non-regression control | rerun only after the app-server route needs another pass-case control. |

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
