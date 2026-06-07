# Paper And Runner Dossier

Checked at: 2026-06-07T20:10:51+08:00.

This dossier ranks candidate long-horizon agent benchmarks for Goal Harness
research. It is a research artifact, not a product implementation plan. Any
Goal Harness feature discovered here should be split into normal product code,
examples, or contract docs outside this topic folder.

## Current Recommendation

Use Terminal-Bench 2.0 as the first official-runner probe, then SWE-Marathon as
the first heavy long-horizon software-engineering probe. The next milestone is
not another broad survey; it is a first official-pilot decision packet that
freezes what a compliant Terminal-Bench pilot must collect before any real
Terminal-Bench, Docker, model API, cloud sandbox, or leaderboard path is
invoked.

The reason is pragmatic. Terminal-Bench has an open runner, Docker-style
terminal tasks, verified leaderboard entries, and visible Codex/Codex-adjacent
agent rows. It is the fastest way to test whether a passive Goal Harness wrapper
can add restartability, state truth, event ledgers, and failure attribution
without changing the official scoring protocol.

SWE-Marathon is closer to the user's paper-level ambition because the tasks are
explicitly ultra-long software-engineering work, but it is heavier: the public
repo uses a Harbor fork, task execution is likely expensive, and some log
access is gated by external credentials. It should be the second lane after the
Terminal-Bench wrapper boundary is understood.

## Ranking

| Rank | Candidate | Use | Why |
| --- | --- | --- | --- |
| 1 | Terminal-Bench 2.0 | First official-runner probe | Open benchmark repo, terminal task model, verified leaderboard, visible Codex entries, and a protocol that already treats agent tools as part of the scored system. |
| 2 | SWE-Marathon | First heavy SWE probe | Strongest fit for hours-to-days software-engineering work; public repo and 20 ultra-long tasks, but setup and cost are heavier. |
| 3 | LongCLI-Bench | Paper hypothesis and failure-analysis source | Directly studies long-horizon CLI programming, step-level failures, and human-agent collaboration gains; runner openness still needs verification before it becomes an execution lane. |
| 4 | WildClawBench | Native-runtime comparison lane | Promising because it evaluates real CLI harnesses including Codex-style harnesses in reproducible containers, but it is very new and needs protocol/code review. |
| 5 | HORIZON / METR-style signals | Diagnostic and positioning signal | Useful to explain long-horizon degradation and compare across domains, but currently better as a leaderboard/diagnostic reference than as the first runnable Goal Harness integration. |
| 6 | RoadmapBench / SWE-EVO | Software-evolution watchlist | Strong long-horizon SWE framing around version upgrades and multi-step codebase evolution, but runner maturity and Codex CLI compatibility need review before they displace Terminal-Bench. |
| 7 | ALE-Bench | Objective-driven algorithm lane | Good future lane for scored iterative search and restart discipline, but requires heavier compute and stricter benchmark-surface controls. |
| 8 | OSWorld / WebArena / TheAgentCompany | Cross-surface and simulator design references | Useful for GUI/web/workplace environment design and user-simulator thinking, but not the first Goal Harness engineering runner. |
| 9 | RALPHBench | Extremely long-horizon watchlist | Potentially close to the paper ambition and advertises Codex rows, but it is pre-launch enough to treat as monitoring input, not a first execution lane. |
| 10 | Tau-style suites | Simulator research only | Valuable for user-simulator design, but not the headline long-horizon engineering benchmark. |

## Source Notes

### Terminal-Bench 2.0

Evidence:

- Official Epoch page describes a task as an instruction, Docker environment,
  and test script, and says models are paired with agent tools such as Claude
  Code, OpenAI Codex CLI, Terminus, and Goose.
- Terminal-Bench paper presents 89 hard terminal-environment tasks with
  verification tests and reports frontier models and agents below 65 percent.
- Official leaderboard page for `terminal-bench@2.0` shows verified GPT-5.3
  Codex rows including Simple Codex and Terminus 2.
- GitHub repo describes Terminal-Bench as evaluating real-world end-to-end
  terminal tasks autonomously.

Fit for Goal Harness:

- Strong first target for passive Goal Harness because the benchmark already
  separates agent tool/scaffold from model.
- Goal Harness can wrap around run setup, event ledger, restart state,
  validation evidence, and failure attribution while preserving official task
  scoring.
- The benchmark explicitly forbids timeout/resource modification in leaderboard
  submissions, so Goal Harness integration must avoid changing resource budget
  or task files.

Open questions:

- Determine whether a passive wrapper can be submitted as a custom agent or
  must be used only for local A/B studies.
- Check whether Harbor's custom-agent path can launch Codex CLI directly or
  needs a small adapter.

Sources:

- https://epoch.ai/benchmarks/terminal-bench/
- https://arxiv.org/abs/2601.11868
- https://www.tbench.ai/leaderboard/terminal-bench/2.0
- https://github.com/harbor-framework/terminal-bench

### SWE-Marathon

Evidence:

- Public repo asks whether agents can complete ultra-long-horizon software
  work.
- Repo uses a Harbor fork, includes tasks, rubrics, scripts, and Apache 2.0
  licensing.
- Hugging Face dataset page says there are 20 ultra-long software-engineering
  tasks, each with a containerized environment, precise instruction,
  comprehensive tests, and an oracle/reference solution.
- Dataset page says tasks are intended for evaluating agents on realistic
  long-horizon hours-to-days software-engineering tasks end-to-end in a
  sandboxed environment.

Fit for Goal Harness:

- Strongest research target once Terminal-Bench wrapper mechanics are known.
- Directly tests multi-hour/multi-day continuation, state handoff, validation
  discipline, and restartability.
- Likely a good paper target because Goal Harness's thesis is about reducing
  coordination load and preserving durable state over long projects.

Risks:

- Higher cost and wall-clock time.
- Public repo's sample command shows Claude Code; Codex CLI compatibility needs
  runner inspection before making claims.
- Some trajectory-log access requires external credentials, so early work
  should use public task files and local dry-runs only.

Sources:

- https://github.com/abundant-ai/swe-marathon
- https://www.swe-marathon.org/
- https://huggingface.co/datasets/rdesai2/swe-marathon

### LongCLI-Bench

Evidence:

- ArXiv paper introduces 20 long-horizon CLI programming tasks from computer
  science assignments and real-world workflows.
- It covers from-scratch implementation, feature addition, bug fixing, and
  refactoring.
- It reports state-of-the-art pass rates below 20 percent, with many tasks
  stalling before 30 percent completion.
- It finds human-agent collaboration through plan injection and interactive
  guidance improves outcomes, which aligns with Goal Harness's supervised
  long-horizon thesis.

Fit for Goal Harness:

- Excellent source for paper framing and failure taxonomy.
- Useful for designing operator-simulator experiments because it explicitly
  discusses collaborative guidance.

Risk:

- Runner/code availability and Codex CLI baseline need verification before it
  becomes an execution target.

Source:

- https://arxiv.org/abs/2602.14337

### WildClawBench

Evidence:

- ArXiv paper frames the gap as existing benchmarks being too synthetic,
  short-horizon, mock-service based, or final-answer oriented.
- It contains 60 human-authored tasks with roughly 8 minutes average wall time
  and more than 20 tool calls.
- It runs in reproducible Docker containers hosting actual CLI harnesses such
  as OpenClaw, Claude Code, Codex, or Hermes Agent.
- It reports harness choice alone can shift one model by up to 18 points.

Fit for Goal Harness:

- Useful after Terminal-Bench because it emphasizes native runtime and harness
  effects, which is exactly where Goal Harness should claim value.

Risk:

- Very new; code, scoring, and leaderboard stability need review before a
  serious run.

Source:

- https://arxiv.org/abs/2605.10912

### HORIZON / METR-style Signals

Evidence:

- HORIZON paper studies long-horizon failure behavior across domains and uses
  trajectory-grounded failure attribution.
- HORIZON site presents itself as a live ranking for frontier models and agents
  on long-horizon software engineering, with METR-Horizon as the primary signal
  and Terminal-Bench plus SWE-style benchmarks as secondary signals.

Fit for Goal Harness:

- Use as a positioning and diagnostic source, not first runner.
- The failure-attribution angle is useful for Goal Harness result reports.

Sources:

- https://arxiv.org/abs/2604.11978
- https://horizonbench.org/

### LongDS-Bench

Evidence:

- ArXiv paper introduces long-horizon, multi-turn data analysis tasks requiring
  agents to maintain, update, restore, and compose evolving analytical states.
- It reports performance degradation over late turns and argues the bottleneck
  is maintaining correct analytical state rather than merely increasing steps.

Fit for Goal Harness:

- Watchlist for state-truth research after engineering benchmark lanes run.
- Relevant to Goal Harness because it isolates state maintenance failures.

Source:

- https://arxiv.org/abs/2605.30434

### RoadmapBench

Evidence:

- ArXiv introduces 115 long-horizon coding tasks grounded in real open-source
  version upgrades across 17 repositories and 5 programming languages.
- Each task starts from a source-version snapshot and asks the agent to
  implement the target-version functionality from a multi-target roadmap.
- The paper reports a median modification footprint of 3,700 lines across 51
  files and a strongest-model solve rate of 39.1 percent.

Fit for Goal Harness:

- Strong paper-framing candidate because it directly evaluates sustained
  multi-target software development rather than single GitHub issues.
- A good later probe for state handoff, backlog decomposition, and regression
  avoidance once the simpler Terminal-Bench official boundary is understood.

Risk:

- Runner and Codex CLI adapter status need inspection before it becomes an
  execution lane.

Source:

- https://arxiv.org/abs/2605.15846

### SWE-EVO

Evidence:

- Public repo frames SWE-EVO as a benchmark for autonomous software evolution
  tasks where agents interpret high-level software requirement specifications,
  plan multi-step changes, and navigate large repositories.
- The repo supports evaluation through OpenHands and SWE-agent scaffolds.

Fit for Goal Harness:

- Useful as a second-wave software-evolution benchmark if RoadmapBench proves
  too new or unavailable.
- The high-level requirement plus multi-version evolution shape matches Goal
  Harness's todo, evidence, and state-truth control-plane thesis.

Risk:

- Existing public scaffold references OpenHands and SWE-agent, not Codex CLI,
  so adapter work must stay behind a protocol review.

Sources:

- https://github.com/SWE-EVO/SWE-EVO
- https://arxiv.org/abs/2512.18470

### ALE-Bench

Evidence:

- ALE-Bench is an official benchmark for long-horizon objective-driven
  algorithm engineering.
- The repo provides an evaluation toolkit and recommends consistent specified
  AWS instances for fair reproducible comparisons.
- The repo explicitly warns agents not to access private seeds or private input
  fields during experiments.

Fit for Goal Harness:

- Good future lane for restartability and evidence discipline because score
  feedback, iterative testing, and forbidden private surfaces are central.

Risk:

- Higher compute cost and benchmark-governance burden than Terminal-Bench.
- It should not be used until Goal Harness can prove side-effect and forbidden
  surface audits on a smaller runner.

Sources:

- https://github.com/SakanaAI/ALE-Bench
- https://arxiv.org/abs/2506.09050

### OSWorld / WebArena / TheAgentCompany

Evidence:

- OSWorld provides a real computer environment and 369 real-world computer
  tasks with setup and execution-based evaluation scripts.
- WebArena is a standalone, self-hostable web environment for autonomous web
  agents.
- TheAgentCompany models a software-company workplace where agents browse the
  web, write code, run programs, and communicate with simulated coworkers.

Fit for Goal Harness:

- These are not the first engineering-runner target, but they are strong design
  references for user-simulator overlays, multi-surface traces, checkpointed
  evaluation, and operator communication.
- TheAgentCompany is the best nearby reference for simulator design because it
  includes simulated coworker communication and checkpoint-style partial credit.

Risk:

- OSWorld and WebArena shift the problem toward GUI/browser automation, which
  could expand Goal Harness before the terminal/SWE control-plane claims are
  measured.

Sources:

- https://os-world.github.io/
- https://github.com/xlang-ai/osworld
- https://github.com/web-arena-x/webarena
- https://openreview.net/pdf?id=LZnKNApvhG

### RALPHBench

Evidence:

- RALPHBench describes extremely long-horizon SWE tasks requiring 1,000 to
  10,000+ steps and hours-to-days execution.
- Its site marks the benchmark as v0.1 pre-launch and says task registry and
  benchmark results are still coming soon, while also showing early Codex,
  Claude Code, and Gemini CLI rows.

Fit for Goal Harness:

- Monitor as a high-ambition external benchmark candidate and paper-positioning
  signal.

Risk:

- Because it is pre-launch, it is not a stable first runner. Treat it as a
  watchlist item until task data, runner code, scoring, and provenance stabilize.

Source:

- https://www.ralphbench.org/

## First Official-Pilot Decision Packet

Decision id: `terminal_bench_official_pilot_decision_packet_v0`.

Terminal-Bench remains the first official-pilot target because it is the
smallest credible public benchmark where Goal Harness can be measured as a
control plane around an existing Codex-capable terminal agent protocol. The
pilot should prove that Goal Harness can add durable state, restart evidence,
event-ledger writeback, stale-state checks, and failure attribution without
changing the benchmark's task files, timeouts, resources, scoring, or
leaderboard submission rules.

Use this packet as the gate before any real execution:

| Field | Decision |
| --- | --- |
| Pilot benchmark | `terminal-bench@2.0` through Harbor or another official Terminal-Bench 2.0 path. |
| Executor target | Native Codex CLI if the official custom-agent/import path can launch it; otherwise local passive Goal Harness wrapper for A/B measurement only. |
| Required prior artifact | `terminal_bench_probe_v0`, `passive-baseline-protocol-v0.md`, and `terminal-bench-official-pilot-readiness-v0.md` are the current public-safe setup/protocol artifacts. |
| First allowed action | A no-submit boundary probe that records runner source, runner version or commit, agent command boundary, submit eligibility, future event shape, and exact stop condition. |
| First forbidden action | Running a real Terminal-Bench task, starting Docker, invoking Codex/model APIs, using cloud sandboxes, or uploading leaderboard traces without explicit authorization. |
| Official score fields | Benchmark-native pass/fail or accuracy, task id or split, repetitions, model/agent tuple, runner source, and whether the run is submit-eligible. |
| Goal Harness score fields | restartability, stale-state avoidance, event-ledger completeness, evidence discipline, boundary safety, writeback quality, failure attribution, and overhead. |
| Pairing rule | Every official-task result should be paired with a compact `benchmark_run_v0` event for `bare_codex_cli` or `passive_goal_harness_wrapper`, then summarized through `benchmark_result_v0`. |
| Stop condition | Stop if compliance would require changing official timeouts/resources/scoring, reading private logs, using credentials, or making public claims from local-only evidence. |

The first measurable outcome is not leaderboard uplift. It is a public-safe
decision trace proving whether Goal Harness can collect comparable control-plane
evidence around the official runner. Do not start SWE-Marathon until the
Terminal-Bench wrapper boundary is known.

## Current No-Submit Boundary Probe

The next public-safe probe is `terminal-bench-no-submit-boundary-probe-v0.md`.
It emits a `runner_boundary_probe_v0` payload: public runner identity, planned
mode boundaries for `bare_codex_cli` and `passive_goal_harness_wrapper`, hard
`submit_eligible = false` / `real_run = false` flags, and the future
`benchmark_run_v0` plus `benchmark_result_v0` event shape. This is a no-submit
boundary probe, not task evidence.

## Next Execution Slice

The next bounded implementation/research slice should be:

1. Keep the no-submit boundary probe smoke-backed and current with the inspected
   runner boundary.
2. If explicit authorization arrives, perform a no-submit runner setup check
   that records source/version/task placeholder/command boundary, then stop
   before any real task execution.
3. Keep SWE-Marathon, RoadmapBench, SWE-EVO, ALE-Bench, OSWorld, WebArena,
   TheAgentCompany, RALPHBench, and tau-style suites as ranked follow-up lanes
   until the first Terminal-Bench official-pilot boundary is validated.
