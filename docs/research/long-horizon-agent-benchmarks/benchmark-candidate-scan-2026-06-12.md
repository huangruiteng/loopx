# Benchmark Candidate Scan 2026-06-12

Checked at: 2026-06-12T13:45:00+08:00.

This note updates the long-horizon benchmark backlog after the Agents' Last
Exam local/GCP blocker. It is a research and planning artifact only. It does
not run benchmarks, Docker tasks, model APIs, cloud sandboxes, uploads,
leaderboard submission, hidden tests, raw trajectories, screenshots, or
credentials.

## Current Decision Context

Agents' Last Exam remains the best conceptual fit for real professional
long-horizon work, but the official path still appears GCP/GCE-centered for
formal sandbox execution. We should pause ALE execution until either:

- the upstream project documents a local/non-GCP route; or
- the user explicitly authorizes cloud setup and cost.

Public issue filed upstream:

- https://github.com/rdi-berkeley/agents-last-exam/issues/9

`SakanaAI/ALE-Bench` is not the same benchmark. It is an AtCoder/AHC algorithmic
engineering benchmark and should not be treated as Agents' Last Exam evidence.

## Selection Criteria

The next benchmark lane should optimize for:

- low enough frontier-agent success that LoopX has room to matter;
- task horizons long enough to stress stale state, restartability,
  self-verification, and premature stopping;
- public, reproducible local or Docker execution before paid cloud;
- objective scoring or replayable graders;
- compatibility with Codex CLI or a straightforward custom-agent wrapper;
- public-safe artifacts that can be written into LoopX state without
  copying hidden refs, raw trajectories, private data, or credentials.

Quota rule: do not spend scarce benchmark quota on aggregate runs. Spend only
after a setup-readiness scan or pilot plan shows the run can plausibly produce a
verified improvement, a clear negative result, or a reusable failure
attribution.

## Codex CLI Evidence Audit

Use direct Codex CLI scores as a routing preference, not as the only admission
criterion. Some promising benchmarks publish OpenAI-model scores under a
different harness, or low-success evidence from other software agents, but do
not yet give a clean Codex CLI baseline.

| Candidate | Direct Codex CLI score? | Public evidence to use |
| --- | --- | --- |
| SWE-Marathon | Yes. | Public score trackers synced from the official leaderboard report `Codex CLI + GPT-5.5` at `12.0%` pass@1, while the paper says no evaluated configuration exceeds 30% pass@1. |
| Terminal-Bench 2.0 | Yes, but high on aggregate. | Official leaderboard shows `Codex CLI + GPT-5.5` at `82.2% +/- 2.2`, so only hand-picked hard/long cases are useful for LoopX. |
| AgentIssue-Bench | No direct Codex CLI score found in the paper scan. | Current paper / leaderboard evidence evaluates Agentless, AutoCodeRover, and SWE-agent with GPT-4o / Claude-3.5 Sonnet; correct resolution is only `0.67%` to `4.67%`. Treat as domain-relevant but not Codex-proven. |
| PerfBench | No direct Codex CLI score found in the paper scan. | Paper evaluates OpenHands and OpenHands-Perf-Agent with GPT-4.1 / Claude Sonnet 4; success is about `3%` baseline and `20%` with performance-aware tooling. |
| SWE-Bench Pro public | Not cleanly Codex CLI in the official Scale page. | The public page reports resolve-rate methodology and model leaderboard data; third-party summaries often mention GPT/Codex variants, but this should be treated as model/harness-specific until verified from the source row. |
| APEX-Agents | No Codex CLI-specific row found. | Paper reports model-agent pass@1 with a 24.0% top score; Artificial Analysis reports newer model-level scores such as GPT-5.5 xhigh at 37.7%, not a local Codex CLI harness. |
| TheAgentCompany / AppWorld / OSWorld | No direct Codex CLI score found in this scan. | Useful only after a separate runner-specific Codex feasibility scan. |

## Recommended Shortlist

| Rank | Candidate | Public difficulty signal | Setup posture | LoopX leverage | Recommendation |
| --- | --- | --- | --- | --- | --- |
| 1 | SWE-Marathon | 20 ultra-long software-engineering tasks; current agent configs remain below reliable completion, with reported pass@1 below 30%. | New; needs runner and wrapper audit. | Directly targets self-verification, recovery, premature termination, multi-stage objectives, and large-codebase continuation. | First new setup-readiness scan. |
| 2 | AgentIssue-Bench | 50 reproducible agent-system issue tasks; current reported SE-agent correct resolution rates are only 0.67%-4.67%, but no direct Codex CLI score found yet. | Local/Docker in shape, but official helpers need a safety wrapper before shared-host use. | Very close to LoopX itself: memory, tool, provider, workflow, and agent-runtime bugs. | Second scan should produce a one-tag no-run launch packet before any pull/run. |
| 3 | PerfBench | 81 real .NET performance bug tasks; baseline OpenHands ~3%, performance-specialized agent ~20%. | Likely local/Docker with .NET and benchmarking costs. | Strong validation loop: benchmark design, regression avoidance, output processing, performance attribution. | Strong pilot candidate after setup cost check. |
| 4 | SWE-Bench Pro public | 1,865 tasks across 41 repos; public leaderboard notes top models around 23% on public set versus 70%+ on SWE-bench Verified. | Docker-based environments; public dataset and trajectories. | Long-horizon professional SWE, contamination-resistant, clear fail-to-pass/pass-to-pass scoring. | Good larger lane after small setup probe. |
| 5 | MLE-bench | 75 Kaggle competitions; best reported o1-preview + AIDE gets bronze-level in 16.9% of competitions. | Data and compute heavier, but not GCP-specific by nature. | Long ML engineering loops, experiment tracking, validation discipline. | Keep as medium-cost ML lane; start with a tiny no-leaderboard subset only. |
| 6 | TheAgentCompany | Self-contained software-company environment; competitive agents complete about 24%-30% of tasks. | Local/cloud servers; browser/code/program/coworker stack. | Strong product fit for durable workplace state, but integration surface is heavier than CLI/SWE lanes. | Third-phase cross-app lane. |
| 7 | APEX-Agents | 480 cross-application professional-services tasks; paper reports 24.0% top Pass@1, live leaderboard currently shows stronger newer models but still below saturation. | Open data/code/Archipelago; likely heavier app/workspace setup. | Excellent professional-work target, less directly Codex-CLI-first. | Watch and scan after SWE lanes. |
| 8 | Terminal-Bench hard subset | Terminal-Bench 2.0 has 89 tasks, but current full-board Codex CLI/GPT-5.5 is already above 80%. | Already partially integrated in LoopX. | Still useful only on selected hard/long cases where control-plane failures show up. | Continue only selected hard cases; avoid full aggregate quota. |
| 9 | AppWorld | 750 tasks over 9 apps / 457 APIs; GPT-4o reported ~49% normal, ~30% challenge. | Local synthetic app/API world. | Good deterministic simulator track, but less obviously low-success for current Codex. | Secondary simulator/control-plane lane. |
| 10 | OSWorld / OS-Marathon | OSWorld originally low, but modern computer-use agents may be much stronger; OS-Marathon reports 0% on some repetitive long-horizon settings. | GUI/desktop setup; less Codex-CLI-native. | Useful after LoopX has a computer-use/operator-simulator story. | Later, not first. |

## Why These Beat ALE For The Next Immediate Slice

ALE is appealing because it covers real professional workflows, but the current
blocker is infrastructure access, not task selection. The next slice should use
a benchmark where we can independently do all of the following on this machine
or a simple Docker host:

1. clone and pin the benchmark;
2. run no-model/no-submit setup checks;
3. run one tiny public sample or dry-run;
4. connect a Codex CLI or custom-agent wrapper;
5. write compact `benchmark_run_v0` / `benchmark_result_v0` evidence.

SWE-Marathon, AgentIssue-Bench, PerfBench, and SWE-Bench Pro have clearer paths
to that sequence than ALE right now.

## Proposed Next Work Batch

Do not start with a real scored run. Start with a public-safe setup-readiness
batch:

1. SWE-Marathon scan:
   - clone/pin upstream if available;
   - read official README and runner docs;
   - identify agent interface, timeout/cost knobs, hidden-test boundaries, and
     whether Codex CLI can be wrapped;
   - write a route dossier and stop before model execution.
2. AgentIssue-Bench scan:
   - verify task environments and public tests;
   - check whether tasks are small enough for a first local pilot;
   - record issue categories that map to LoopX product weaknesses.
3. PerfBench scan:
   - verify .NET toolchain/Docker feasibility on this host;
   - identify benchmark-output schema and no-regression checks;
   - decide whether one sample can be used as a cheap validation loop.

Only after one of those scans produces a clean route should we spend a fresh
benchmark quota slot on a paired run.

## Source Notes

- Terminal-Bench site and 2.0 leaderboard:
  https://www.tbench.ai/ and
  https://www.tbench.ai/leaderboard/terminal-bench/2.0
- Terminal-Bench 2.0 paper:
  https://arxiv.org/html/2601.11868v1
- SWE-Marathon:
  https://swe-marathon.vercel.app/ and
  https://arxiv.org/html/2606.07682v1
- AgentIssue-Bench:
  https://arxiv.org/pdf/2505.20749 and
  https://alfin06.github.io/AgentIssue-Bench-Leaderboard/
- PerfBench:
  https://arxiv.org/abs/2509.24091
- SWE-Bench Pro public leaderboard and paper:
  https://labs.scale.com/leaderboard/swe_bench_pro_public and
  https://arxiv.org/abs/2509.16941
- MLE-bench:
  https://github.com/openai/mle-bench and
  https://openreview.net/forum?id=6s5uXNWGIh
- TheAgentCompany:
  https://github.com/TheAgentCompany/TheAgentCompany and
  https://arxiv.org/html/2412.14161v1
- APEX-Agents:
  https://www.mercor.com/apex/apex-agents-leaderboard/ and
  https://arxiv.org/abs/2601.14242
- AppWorld:
  https://arxiv.org/abs/2407.18901
- OSWorld:
  https://arxiv.org/abs/2404.07972

## Claim Boundary

This scan ranks candidate lanes, not benchmark performance. It should not be
used to claim LoopX improves any benchmark. The next evidence-producing
step is setup-readiness, not a scored run.
