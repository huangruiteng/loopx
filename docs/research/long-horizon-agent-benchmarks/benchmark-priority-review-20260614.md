# Benchmark Priority Review 2026-06-14

Refreshed: 2026-06-20 to add FrontierSWE and re-rank heavy SWE candidates
after the cloud-host Codex benchmark route became the default execution path.

This review re-ranks benchmark lanes by the corrected baseline definition:
Codex CLI goal mode versus a LoopX assisted Codex worker. It uses only
public-safe compact run ledger entries and public leaderboard/source evidence;
it does not rely on raw task text, hidden tests, private trajectories, Docker
logs, credentials, uploads, or public leaderboard submissions.

## Baseline Evidence Classes

Use four separate evidence classes when ranking benchmark lanes:

1. `direct_codex_goal_mode_low`: a direct Codex CLI or Codex goal-mode baseline
   is already low enough to leave room for LoopX.
2. `direct_codex_frontier_stress`: the benchmark has direct Codex leaderboard
   rows and strong long-horizon fit, but this repo has not yet mined a local
   Codex goal-mode baseline failure.
3. `selected_hard_subset_low`: the public aggregate may be high, but local
   selected cases show Codex goal-mode failures that can be mined safely.
4. `adjacent_agent_low_no_clean_codex`: the benchmark is promising because
   other agents fail often, but a clean Codex goal-mode baseline must be mined
   before treatment.

Runner/setup failures are not model capability failures. They are still P0 when
they block all benchmark progress, but they should not be counted as case-level
Codex weakness until the worker reaches the task.

## Current Codex Baseline Signals

| Rank | Benchmark lane | Evidence class | Codex baseline signal | Current interpretation | Next move |
| --- | --- | --- | --- | --- | --- |
| 1 | Terminal-Bench selected hard subset | `selected_hard_subset_low` | Official full leaderboard is high for Codex CLI, but the local selected ledger has only 3 passing Codex goal-mode baseline cases among 11 unique selected cases; many failures are setup/model-route blockers rather than task failures. | Keep as the immediate engineering lane because the dedicated cloud host, runner, ledger, compact attribution, and no-upload smoke path are closest to producing comparable evidence. Do not treat full Terminal-Bench as low-baseline. | Finish the cloud-host no-upload smoke and compact reducer path, then mine one attributable baseline failure before treatment. |
| 2 | SkillsBench / skill-runtime lane | `direct_codex_goal_mode_low` | Public SkillsBench reports GPT-5.5 Codex at 46.8% without skills and 66.5% with skills. | Strong direct evidence that skill/context routing can move outcomes. More relevant to LoopX skill provenance, safe reuse, negative transfer, and exposure/writeback than Terminal-Bench style terminal work. | Keep as the second near-term execution lane; repair verifier dependency/prewarm issues on the cloud host before broad runs. |
| 3 | SWE-Marathon | `direct_codex_goal_mode_low` | Prior scan records Codex CLI + GPT-5.5 at 12.0% pass@1, and the paper reports no evaluated configuration above 30% pass@1. | Best strategic heavy-SWE target for long-horizon state, restartability, self-verification, and premature-stop failures. The new cloud route removes the old local Colima capacity blocker from the primary path, but the Harbor fork and multi-hour task cost still require a launch packet. | Refresh the existing setup-readiness note against the dedicated ECS route and produce a no-execution launch packet before any scored run. |
| 4 | FrontierSWE | `direct_codex_frontier_stress` | Public FrontierSWE leaderboard includes GPT-5.5 via Codex and GPT-5.4 via Codex rows. Public framing gives agents up to roughly 20 hours per task. | Excellent high-end stress test for LoopX's long-horizon control-plane thesis, especially performance engineering, computational science, and ML-research tasks. It is not yet the fastest execution lane because this repo has no local checkout, task inventory, no-upload command boundary, or compact reducer. | Add as a P1 readiness lane: inspect the official repo/Harbor extension/task inventory and write a no-execution launch packet after the shared cloud benchmark substrate is proven. |
| 5 | AgentIssue-Bench | `adjacent_agent_low_no_clean_codex` | Prior scan found no clean official Codex CLI score; published/leaderboard evidence for other agents is only 0.67% to 4.67% correct resolution. | Very high product fit for agent-runtime bugs, provider/tool failures, and workflow repair. Current local pilot showed a source-alignment blocker, not a benchmark-level conclusion. | Keep focused on one selected tag and align patch generation to the buggy source snapshot before any broader run. |
| 6 | PerfBench | `adjacent_agent_low_no_clean_codex` | Prior scan found no direct Codex CLI score; OpenHands-style baseline is about 3%, specialized performance agent about 20%. | Strong validation/profiling loop and likely control-plane leverage, but setup/toolchain cost is less known. | Add setup-readiness and one cheap sample route after Terminal-Bench/SkillsBench cloud smokes are stable. |
| 7 | ALE | `adjacent_agent_low_no_clean_codex` | ALE is promising for objective-driven long-horizon algorithm work, but the local repo does not yet have direct Codex goal-mode baseline evidence, and the current route is blocked on large Docker image acquisition. | Keep in rotation because it tests different failure modes from SWE tasks, but do not let image-pull substrate issues starve closer benchmark lanes. | Let the large image pull continue in the background; resume only after image availability and a no-upload smoke are proven. |
| 8 | SWE-Bench Pro public / WildClawBench / APEX / TheAgentCompany | `adjacent_agent_low_no_clean_codex` | Public sources are valuable, but clean Codex goal-mode baseline rows or local baseline-failure mining plans are not yet established in this repo. | Useful later SWE/professional-agent lanes, but less urgent than the cloud execution substrate and the two direct Codex long-horizon SWE candidates. | Keep as dossier/watchlist lanes until each has a clean Codex goal-mode baseline failure-mining plan. |

## Terminal-Bench Local Ledger Recheck

The local selected Terminal-Bench ledger should be interpreted as a hard-case
mining set, not as an aggregate benchmark score:

| Bucket | Cases | Meaning |
| --- | --- | --- |
| Passed Codex goal-mode baseline | `nginx-request-logging`, `path-tracing`, `regex-log` | Not current treatment priority unless a separate control-plane failure is found. |
| Runner/setup blocked | `build-cython-ext`, `financial-document-processor`, `large-scale-text-editing`, `multi-source-data-merger` | Repair the Codex worker startup/model-route path before using these as capability evidence. |
| Attribution gate | `headless-terminal` | Baseline is 0.0 but needs compact verifier attribution before treatment. |
| Case/solution-level failures worth studying | `install-windows-3.11`, `make-doom-for-mips`, `pytorch-model-recovery` | Best current Terminal-Bench candidates for failure-class research once startup alignment is clean. |

Strict selected-case pass rate is 3/11, but that number is deliberately biased
toward hard cases and polluted by runner/setup blockers. The more important
signal is the mix: setup timeout is now the immediate control-plane blocker,
while exception/timeout cases remain the next LoopX uplift candidates.

## Updated Priority Order

1. `P0` Finish the cloud-host Terminal-Bench no-upload smoke and compact
   reducer path. This proves the shared ECS + Codex CLI + Docker + ledger
   substrate before heavier benchmark families consume time.
2. `P0/P1` Repair the SkillsBench verifier dependency/prewarm path on the
   cloud host and mine one baseline failure with compact attribution.
3. `P1` Refresh SWE-Marathon against the dedicated ECS route and keep it as the
   highest strategic low-baseline heavy-SWE candidate.
4. `P1` Add FrontierSWE setup-readiness and a no-execution launch packet. It is
   a high-end long-horizon stress lane with direct Codex leaderboard evidence,
   but it must not start real tasks until runner/no-upload boundaries are
   mapped.
5. `P1` Resume the one-tag AgentIssue-Bench lane only after aligning patch
   generation to the benchmark buggy source snapshot.
6. `P1/P2` Keep ALE in background rotation while the large image pull and local
   Docker route are resolved; do not count image-pull failure as agent
   capability evidence.
7. `P1/P2` Add PerfBench setup-readiness after Terminal-Bench and SkillsBench
   smokes stabilize.
8. `P2` Keep SWE-Bench Pro, WildClawBench, APEX, and TheAgentCompany as
   dossier/watchlist lanes until each has a clean Codex goal-mode baseline
   failure-mining plan.

## Planning Rule

Do not rank benchmark families by public accuracy alone. Rank by:

- low or failure-rich Codex goal-mode baseline evidence;
- whether failures are observable without reading hidden/private material;
- whether LoopX could plausibly change the outcome through state,
  todo/checkpoint discipline, validation, replan, tool/skill provenance,
  writeback, or failure attribution;
- setup readiness and no-upload/no-submit safety;
- whether the result can be reduced into `benchmark_run_v0` and the run ledger.
