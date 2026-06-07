# Long-Horizon Agent Benchmark Roadmap

Goal Harness needs an external validity track beyond local regression smokes. The
long-term target is to run, improve, and eventually publish on public
long-horizon agent benchmarks while preserving the product thesis: agents should
work through durable state, gates, evidence, and recovery rather than through
prompt bloat or raw chat history. When human-agent collaboration is evaluated,
Goal Harness should supply its own bounded operator simulator as an overlay,
not require the benchmark itself to provide a user simulator.

## Thesis

Goal Harness should be evaluated as an agent control plane, not merely as a
project dashboard. A credible benchmark result should show whether the harness
improves:

- task success over long horizons;
- recovery after stale state, failed workers, or interrupted sessions;
- operator-simulator coordination quality in assisted-mode runs;
- policy and tool-use correctness;
- public-safe evidence and writeback discipline;
- overhead in time, tokens, and extra steps.

The goal is not to game a leaderboard. The goal is to produce reproducible
evidence that durable control-plane structure improves real agent work, then use
that evidence to guide product design and, if strong enough, a paper.

## Benchmark Shortlist

Before choosing a benchmark, maintain a paper-and-runner dossier. The dossier
should answer:

- Which recent SOTA long-horizon agent papers use this benchmark?
- Does the benchmark report Codex CLI, Claude Code, Gemini CLI, OpenHands,
  Mini-SWE-Agent, Terminus, OpenClaw, or another reproducible executor?
- Is the implementation open-source and runnable from a clean checkout?
- Does the official protocol allow a custom wrapper around the agent, or only a
  fixed agent submission?
- Are there hidden tests, exploit scans, or anti-reward-hacking safeguards?
- Can Goal Harness add event-ledger/restartability instrumentation without
  changing the scoring protocol?
- Can a separate assisted-mode study add a bounded operator simulator without
  confusing the result with the official leaderboard protocol?

Initial paper and benchmark scan:

| Candidate | Why it matters | Codex / executor signal | Current posture |
| --- | --- | --- | --- |
| SWE-Marathon | Ultra-long-horizon SWE tasks, multi-hour wall-clock horizon, hidden tests, exploit scans, open benchmark code. | Public leaderboard includes GPT/Codex CLI entries. | Strong primary candidate; verify runner setup and allowed wrapper boundary first. |
| Terminal-Bench 2.0 | Hard realistic CLI tasks; measures terminal operation, recovery, and state management. | Paper/leaderboards report Codex CLI, Claude Code, Gemini CLI, OpenHands, Mini-SWE-Agent, Terminus/Goose-style agents. | Strong primary candidate; likely easiest Codex CLI baseline path. |
| LongCLI-Bench | Long-horizon command-line programming tasks with fine-grained failure analysis and human-agent collaboration findings. | Reports Codex-family model results; executor openness must be verified. | Candidate for research comparison after primary lane. |
| RoadmapBench | Long-horizon software evolution across version upgrades; large multi-file change targets. | Codex executor support not yet verified. | Watchlist; high fit if runner and baseline are reproducible. |
| WildClawBench | Real-world long-horizon tasks in reproducible containers with actual CLI agent harnesses. | Search results indicate Codex / Claude Code / OpenClaw / Hermes style executors. | Promising but new; verify paper, code, and scoring before adoption. |
| Tau2/Tau3 | User-agent-policy interaction with simulator and tools. | Useful for simulator research, not headline long-horizon evidence. | Secondary simulator research track only. |

### Primary: Long-Horizon Engineering Leaderboards

Use Terminal-Bench 2.0, SWE-Marathon, and HORIZON/METR-style software
engineering leaderboards as the main external target. These are closer to the
hard long-horizon claim: sustained CLI or software-engineering work, many tool
steps, real validation, restartability pressure, and visible comparison against
native agent surfaces such as Codex CLI.

Sources:

- Terminal-Bench 2.0 paper: https://arxiv.org/abs/2601.11868
- Epoch Terminal-Bench page: https://epoch.ai/benchmarks/terminal-bench/
- SWE-Marathon: https://www.swe-marathon.org/
- HORIZON leaderboard: https://horizonbench.org/

Initial fit:

- Terminal-Bench evaluates agents in terminal environments and includes Codex
  CLI as a relevant agent surface.
- SWE-Marathon and HORIZON-style benchmarks are closer to the target claim:
  ultra-long-horizon software work rather than short interaction episodes.
- These benchmarks can support a leaderboard-oriented track where Goal Harness
  wraps the worker without changing the official task, scoring, or allowed
  tools.
- They directly test the control-plane value proposition: state truth,
  validation discipline, restartability, bounded context, and recovery after
  failed or interrupted worker steps.

### Secondary: Tau-Style Simulator Research Track

Use tau-bench / tau2-bench / tau3-bench as simulator and collaboration research
material, not as the primary long-horizon leaderboard target. Tau-style
benchmarks are useful because they explicitly contain a language agent,
simulated user, policy constraints, domain tools, and multi-turn task
completion, but the typical task horizon is shorter than the engineering
benchmarks above, and their built-in simulator is not a substitute for a Goal
Harness operator-simulator overlay on engineering benchmarks.

Sources:

- tau-bench paper: https://arxiv.org/abs/2406.12045
- tau-bench site and leaderboard: https://taubench.com/
- tau2 / tau3 repository: https://github.com/sierra-research/tau2-bench
- tau2-bench paper: https://arxiv.org/abs/2506.07982

Initial fit:

- The user simulator is first-class, so Goal Harness can learn simulator
  evaluation patterns before applying its own operator simulator to engineering
  benchmarks.
- Airline/retail/banking-style domains resemble enterprise project workflows:
  policy adherence, tool updates, multi-turn clarification, and final state
  verification.
- The benchmark can support an A/B study: stock agent versus Goal Harness
  wrapped agent, with identical task/user-simulator settings.
- It is a good substrate for a paper section on user-simulator fidelity, but it
  should not be used as the headline evidence for long-horizon engineering
  ability.

### Watchlist: Additional Long-Horizon SWE Benchmarks

Track other long-horizon coding benchmarks as candidates once the primary
engineering lane is running. The selection dossier should decide whether any of
these have enough reproducibility, Codex CLI support, and public scoring
credibility to become a second official target.

Sources:

- LongCLI-Bench paper: https://arxiv.org/abs/2602.14337
- RoadmapBench paper: https://arxiv.org/abs/2605.15846
- WildClawBench paper: https://arxiv.org/abs/2605.10912
- SWE-EVO paper: https://arxiv.org/abs/2512.18470
- RALPHBench: https://www.ralphbench.org/

Initial fit:

- These may be useful for paper breadth, but each needs contamination,
  reproducibility, scoring, and setup-cost review before adoption.

### Later: Browser and Desktop Benchmarks

WebArena, VisualWebArena, and OSWorld are useful later-stage benchmarks for
browser/computer-use agents. They are lower priority for the first integration
because Goal Harness currently has stronger leverage on state, quota, gates,
and user-agent coordination than on visual desktop control.

Sources:

- WebArena paper: https://arxiv.org/abs/2307.13854
- OSWorld paper: https://arxiv.org/abs/2404.07972

## Goal Harness Operator Simulator Program

Goal Harness needs its own operator simulator for assisted long-horizon
benchmark studies. This is different from choosing benchmarks that already have
a user simulator. The benchmark selection should optimize for hard long-horizon
engineering work and Codex/executor compatibility; the operator simulator is a
Goal Harness overlay used to study supervised execution.

There are three result modes:

- **Official leaderboard mode:** run the benchmark exactly as prescribed. Goal
  Harness may only wrap the worker for logging, restartability, event ledger,
  evidence, and cost/state accounting. No operator-simulator hinting,
  approvals, or extra task guidance is allowed.
- **Passive control-plane mode:** keep the same autonomous worker decisions, but
  record richer Goal Harness state, Goal Tick phases, validation, and restart
  artifacts. This measures whether the control plane improves auditability and
  recovery without changing task policy.
- **Assisted operator-simulator mode:** add a bounded simulated operator that
  can approve plans, ask for scope clarification, decide whether to continue
  after failed validation, and correct obvious process drift under a fixed
  intervention budget. This mode measures human-agent collaboration and must be
  reported separately from official leaderboard scores.

The first operator-simulator matrix should compare:

- same-family simulator and agent;
- stronger simulator with weaker agent;
- weaker simulator with stronger agent;
- Codex CLI worker with a non-Codex simulator;
- Doubao 2.0 style simulator or worker where available;
- deterministic scripted user for reproducibility checks.

The simulator contract should record:

- model or simulator identity;
- whether the simulator can see only public task state and worker artifacts;
- cooperation level;
- ambiguity and correction behavior;
- tool/state grounding;
- conversation length;
- simulator-induced failure labels.

The operator simulator must not act as an oracle. It must not see hidden tests,
expected solutions, benchmark answer keys, private project data, or any state
that the benchmark protocol would forbid the agent from using. A Goal Harness
result must not claim official long-horizon benchmark improvement if the gain
comes from assisted operator-simulator intervention.

## Goal Harness Integration

The benchmark adapter should add control-plane structure without changing the
benchmark's scoring rules:

- register each benchmark suite as a public-safe authority source;
- record `benchmark_run_v0` events with benchmark id, task split, mode, agent,
  optional operator simulator, seed, score, wall time, token/cost estimate, and
  artifacts;
- write Goal Tick phases for read_state, propose_step, execute, validate,
  critic, and writeback;
- keep a restartable run ledger so interrupted workers can resume from current
  state instead of chat history;
- compare native, passive control-plane, and assisted operator-simulator modes
  using identical benchmark tasks and model settings where the protocol allows;
- forbid private project data, internal sessions, credentials, and benchmark
  answer leakage.

## Milestones

### P0: Selection Dossier

Produce a public-safe benchmark selection dossier that ranks Terminal-Bench,
SWE-Marathon, HORIZON/METR-style leaderboards, LongCLI-Bench, SWE-EVO,
RALPHBench, tau3/tau2, WebArena, and OSWorld by fit, setup cost, Codex CLI
relevance, true horizon length, scoring credibility, leaderboard compliance,
user-simulator relevance, and publishability.

The dossier must read the SOTA papers or official benchmark reports first. It
should not select a benchmark only because it sounds aligned with Goal Harness.
The first recommendation must explicitly name the expected executor path:
native Codex CLI, a benchmark-provided Codex adapter, or a small public-safe
Goal Harness passive wrapper around an official executor.

### P1: Official Long-Horizon Engineering Pilot

Run the first small official-protocol pilot on Terminal-Bench, SWE-Marathon, or
another selected long-horizon engineering benchmark:

- stock/native agent path;
- Goal Harness wrapped worker path;
- identical task, model, allowed tools, environment, and scoring;
- no user-simulator overlay if the official benchmark protocol does not allow
  it;
- event ledger and restartability instrumentation around the worker rather than
  benchmark-internal scoring changes.

The pilot is successful when it produces comparable official metrics and a
restartable Goal Harness event ledger without changing task answers, tests, or
benchmark policy.

### P1: Operator-Simulator Overlay Pilot

After the first official-protocol engineering pilot, run an assisted overlay on
the same or similar long-horizon task slice:

- fixed operator-simulator model and intervention budget;
- no access to hidden tests, expected solutions, or benchmark answer keys;
- allowed interventions limited to plan approval, scope clarification,
  continue/stop decisions, validation triage, and process-drift correction;
- separate reporting from official leaderboard metrics;
- comparison against native and passive control-plane modes.

This pilot answers whether Goal Harness can model supervised long-horizon work,
not whether the base agent is autonomous SOTA.

### P2: Tau Simulator Research Pilot

Run a small tau-style pilot as a user-simulator research slice:

- one domain first;
- one public split or a small representative subset;
- fixed simulator model and seed policy;
- baseline stock agent;
- Goal Harness wrapped agent;
- identical scoring harness.

This pilot should be labeled as collaboration/user-simulator evidence, not as
the headline long-horizon leaderboard result.

### P1: User-Simulator Ablation

Run the same task slice under at least two user-simulator settings. Record
whether failures are caused by the agent, the simulator, policy ambiguity,
tool-state mismatch, or orchestration overhead.

### P1: Codex CLI Engineering Baseline

Run the selected engineering pilot with native Codex CLI and a Goal Harness
wrapped Codex CLI worker. Measure completion, validation, restartability,
stale-state errors, overhead, and evidence quality.

### P2: Reproducible Benchmark Pack

Create a benchmark pack that can be rerun from a clean checkout with explicit
model/provider configuration, no private data, and deterministic public-safe
artifact paths.

### P2: Publication Readiness

Prepare a paper-style report once the A/B results show a real signal. The report
should include negative results, overhead, failure taxonomy, user-simulator
limitations, and benchmark-integrity safeguards.

## Active Agent Todo Seed

- [ ] [P1] Write the benchmark selection dossier with the shortlist, scoring
  criteria, setup cost, SOTA paper usage, open-source runner status, Codex CLI
  or Codex-adapter baseline availability, operator-simulator overlay
  feasibility, and first recommended benchmark.
- [ ] [P1] Run or dry-run the selected long-horizon engineering benchmark setup
  first, likely Terminal-Bench / SWE-Marathon / HORIZON style, and identify the
  smallest official-protocol pilot slice that can compare native agent versus
  Goal Harness wrapped agent.
- [ ] [P1] Specify the user-simulator ablation matrix and failure taxonomy,
  including same-model, stronger-simulator, weaker-simulator, deterministic
  scripted-user settings, visibility limits, and intervention budgets for the
  Goal Harness operator-simulator overlay.
- [ ] [P2] Define `benchmark_run_v0` and Goal Tick writeback fields for public
  benchmark runs, then connect them to status/history without adding prompt
  branches.
- [ ] [P2] Add a low-frequency Codex CLI benchmark lane for Terminal-Bench or a
  comparable long-horizon SWE benchmark, keeping local smokes deterministic.
- [ ] [P2] Run or dry-run tau2/tau3 only as a simulator research pilot, not as
  the headline long-horizon leaderboard target.

## Non-Goals

- Do not use private user sessions or internal project history as benchmark
  tasks.
- Do not alter benchmark scoring, leak expected answers, or prompt around task
  labels.
- Do not make recurring heartbeat prompts benchmark-specific.
- Do not optimize only for leaderboard rank while losing state truth, user
  coordination, safety, or reproducibility.
