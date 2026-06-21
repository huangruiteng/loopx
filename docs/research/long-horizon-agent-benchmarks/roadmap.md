# Long-Horizon Agent Benchmark Roadmap

LoopX needs an external validity track beyond local regression smokes. The
long-term target is to run, improve, and eventually publish on public
long-horizon agent benchmarks while preserving the product thesis: agents should
work through durable state, gates, evidence, and recovery rather than through
prompt bloat or raw chat history. When human-agent collaboration is evaluated,
LoopX should supply its own bounded operator simulator as an overlay,
not require the benchmark itself to provide a user simulator.

## Thesis

LoopX should be evaluated as an agent control plane, not merely as a
project dashboard. A credible benchmark result should show whether the harness
improves:

- task success over long horizons;
- recovery after stale state, failed workers, or interrupted sessions;
- autonomous continuation from a durable backlog instead of waiting for the user
  to restate strategy;
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
- Can LoopX add event-ledger/restartability instrumentation without
  changing the scoring protocol?
- Can a separate assisted-mode study add a bounded operator simulator without
  confusing the result with the official leaderboard protocol?
- What Codex goal-mode baseline failures are observable before any LoopX
  treatment, and which of those failures are plausibly addressable by
  control-plane state, todo, checkpoint, replan, validation, writeback, or
  failure attribution?

Initial paper and benchmark scan:

| Candidate | Why it matters | Codex / executor signal | Current posture |
| --- | --- | --- | --- |
| SWE-Marathon | Ultra-long-horizon SWE tasks, multi-hour wall-clock horizon, hidden tests, exploit scans, open benchmark code. | Public leaderboard includes GPT/Codex CLI entries. | Strong primary candidate; verify runner setup and allowed wrapper boundary first. |
| Terminal-Bench 2.0 | Hard realistic CLI tasks; measures terminal operation, recovery, and state management. | Paper/leaderboards report Codex CLI, Claude Code, Gemini CLI, OpenHands, Mini-SWE-Agent, Terminus/Goose-style agents. | Strong primary candidate; likely easiest Codex CLI baseline path. |
| LongCLI-Bench | Long-horizon command-line programming tasks with fine-grained failure analysis and human-agent collaboration findings. | Reports Codex-family model results; executor openness must be verified. | Candidate for research comparison after primary lane. |
| RoadmapBench | Long-horizon software evolution across version upgrades; large multi-file change targets. | Codex executor support not yet verified. | Watchlist; high fit if runner and baseline are reproducible. |
| WildClawBench | Real-world long-horizon tasks in reproducible containers with actual CLI agent harnesses. | Search results indicate Codex / Claude Code / OpenClaw / Hermes style executors. | Promising but new; verify paper, code, and scoring before adoption. |
| Tau2/Tau3 | User-agent-policy interaction with simulator and tools. | Useful for simulator research, not headline long-horizon evidence. | Secondary simulator research track only. |

### Universal: Baseline Failure-Case Mining

Every benchmark lane must pass the same selection gate before LoopX
treatment runs. The goal is not to spend on benchmarks where the base agent only
fails because of raw model capability, hidden-test ambiguity, missing domain
knowledge, flaky infrastructure, or an unobservable evaluator.

For each candidate, first gather public-safe Codex goal-mode baseline failure
evidence:

- stable task or case handle, redacted when needed;
- runner/scaffold, dataset revision, repository commit, model, timeout, seed,
  resource envelope, and allowed tools;
- terminal phase: setup, task understanding, planning, tool use, environment
  triage, artifact production, validation, verifier, timeout, or writeback;
- failure class: stale assumption, lost state, duplicated work, missing
  validation, premature stop, over-broad edit/action, poor evidence trail,
  source/coverage drift, skill/tool routing miss, artifact provenance gap,
  policy/gate miss, failure-attribution gap, or ordinary model miss;
- control-plane leverage: whether LoopX could plausibly change the
  outcome through state truth, todo continuity, checkpoint/restart, bounded
  replan, validation discipline, policy/gate handling, public-safe writeback, or
  compact failure attribution.

Only control-plane-addressable failures advance to paired treatment. The paired
repeat must preserve the benchmark task, prompt, tests, scorer, image, timeout,
model, runner source, Codex goal-mode invocation surface, and publication
boundary. If the goal-mode baseline failure is not control-plane-addressable,
record it as negative selection evidence and choose a different case rather
than forcing a treatment run.

This gate applies to all benchmark families:

| Family | Baseline failure to mine first | LoopX leverage if present |
| --- | --- | --- |
| Terminal / CLI / SWE | Long validation loops, dependency triage, stale state, repeated failed fixes, timeout after drift | checkpoint/replan, validation discipline, compact run ledger, failure attribution |
| Skill benchmarks | Wrong skill chosen, missing skill provenance, unsafe skill reuse, negative transfer | skill-state review, provenance gates, routed-skill exposure trace |
| Search / research | Coverage gaps, lost source checklist, weak citation trail, stale source reuse | evidence map, source checklist recovery, citation/writeback discipline |
| Spreadsheet / data / DS | Lost notebook/file state, unverified transformations, artifact mismatch, weak provenance | artifact registry, validation checklist, restartable data pipeline trace |
| Simulator / policy tasks | Policy ambiguity, simulator-induced failure, tool-state mismatch | separated agent/simulator attribution, policy gate, assisted-mode boundary |
| GUI / desktop | Unobservable side effects, flaky UI state, screenshot/action trace gaps | only after trace publicness and side-effect audit are reliable |

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
- These benchmarks can support a leaderboard-oriented track where LoopX
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

- The user simulator is first-class, so LoopX can learn simulator
  evaluation patterns before applying its own operator simulator to engineering
  benchmarks.
- Airline/retail/banking-style domains resemble enterprise project workflows:
  policy adherence, tool updates, multi-turn clarification, and final state
  verification.
- The benchmark can support an A/B study: stock agent versus LoopX
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
because LoopX currently has stronger leverage on state, quota, gates,
and user-agent coordination than on visual desktop control.

Sources:

- WebArena paper: https://arxiv.org/abs/2307.13854
- OSWorld paper: https://arxiv.org/abs/2404.07972

## LoopX Operator Simulator Program

LoopX needs its own operator simulator for assisted long-horizon
benchmark studies. This is different from choosing benchmarks that already have
a user simulator. The benchmark selection should optimize for hard long-horizon
engineering work and Codex/executor compatibility; the operator simulator is a
LoopX overlay used to study supervised execution.

There are three result modes:

- **Official leaderboard mode:** run the benchmark exactly as prescribed. Goal
  Harness may only wrap the worker for logging, restartability, event ledger,
  evidence, and cost/state accounting. No operator-simulator hinting,
  approvals, or extra task guidance is allowed.
- **Passive control-plane mode:** keep the same autonomous worker decisions, but
  record richer LoopX state, Goal Tick phases, validation, and restart
  artifacts. This measures whether the control plane improves auditability and
  recovery without changing task policy. It is also the first test of whether
  LoopX helps without any operator simulator: if passive mode cannot
  improve restartability, stale-state avoidance, continuation quality, or
  failure attribution over Codex CLI goal mode, the operator-simulator work is not
  yet grounded.
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
that the benchmark protocol would forbid the agent from using. A LoopX
result must not claim official long-horizon benchmark improvement if the gain
comes from assisted operator-simulator intervention.

## Passive Baseline Hypotheses

Before using an operator simulator, LoopX should prove or falsify a
passive-control-plane benefit against Codex CLI goal mode. The benchmark program
should track these hypotheses:

- **H1: Restartability.** A killed or timed-out worker can resume from the
  public run ledger and active state with less duplicated work than Codex CLI
  goal mode alone.
- **H2: Stale-state avoidance.** The worker trusts current authority and
  validation state over stale plans, stale latest-run text, or old todos more
  often than Codex CLI goal mode alone.
- **H3: Continuation quality.** After a completed slice, the next autonomous
  turn selects a high-value follow-up from durable backlog/state instead of
  waiting for the human to re-prompt the same strategic objective.
- **H4: Evidence discipline.** Work steps produce decision-ready validation,
  blocker, or failure-attribution events rather than transcript-only claims.
- **H5: Bounded overhead.** Extra state reads, Goal Tick rows, and writebacks do
  not erase the reliability gain through excessive wall time or token cost.

The assisted operator-simulator track should start only after the passive
baseline has at least one credible result or a documented negative result that
explains why supervision is needed.

## Autonomous Planning Triggers

Long-horizon research cannot rely on the user to notice every stagnation point.
LoopX should trigger a planning refresh when the current control plane
shows that execution is no longer converting intent into evidence.

Planning refresh is not a license to expand scope every turn. It is a bounded
meta-step that re-reads authority, run history, benchmark evidence, open todos,
and recent failures, then decides whether to keep the current todo, split it,
add a new todo, retire stale work, or request an operator decision.

This is control-plane planning, not task-policy planning. The refresh may
repair the execution track when the project stops converting intent into
evidence, but the worker model still owns belief synthesis and the concrete
implementation/debug strategy inside the authorized boundary. LoopX can
say "this todo is stale; split it and validate the next slice with command X."
It should not silently decide the semantic solution to the task or rewrite
project direction as if a dreaming or replan proposal were already approved.

Initial trigger conditions:

- **Periodic research review:** every 20-30 visible turns or durable run events
  in the same long-horizon research topic.
- **No-progress streak:** three consecutive eligible turns with no committed
  artifact, no benchmark evidence, no validated blocker, and no state-changing
  writeback.
- **Repeated-action loop:** the same recommended action appears across three or
  more latest runs without a new validation result or blocker.
- **Phase transition:** the project moves from roadmap to setup, setup to pilot,
  pilot to A/B result, or result to paper/readiness.
- **Backlog mismatch:** status shows no open agent todo, or only broad/open-ended
  todos, while run history still contains unresolved benchmark or planning work.
- **Evidence contradiction:** benchmark output, paper survey, or executor
  compatibility evidence contradicts the current roadmap assumption.

The planning refresh output should be public-safe and structured:

- keep / split / add / retire / ask-decision action;
- affected todo ids or titles;
- reason for trigger;
- evidence references;
- next bounded validation command;
- stop condition;
- whether the next turn is implementation, setup, paper survey, or observation.

This mechanism is part of the benchmark program itself: one result dimension is
whether LoopX can autonomously maintain a useful research agenda over
many turns without drifting into prompt-only planning or waiting for the user to
restate the strategy.

Planning outputs should carry their authority level:

| Authority level | Meaning | Default consumer behavior |
| --- | --- | --- |
| `control_signal` | A guard, quota, freshness, or safety fact that constrains the next run. | Obey before delivery or ask the user/controller if blocked. |
| `bounded_replan_obligation` | A required control-plane repair slice, such as todo split, blocker writeback, or state rebase. | Execute one validated repair slice, then write back or record why blocked. |
| `proposal` | A dreaming/exploration/research suggestion that may improve future work. | Route to operator/controller review before making it active project truth. |
| `agent_policy_choice` | A concrete task-solving strategy chosen from current belief. | Belongs to the worker inside the current authorized boundary. |

## LoopX Integration

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
user-simulator relevance, baseline failure observability, control-plane
addressability, and publishability.

The dossier must read the SOTA papers or official benchmark reports first. It
should not select a benchmark only because it sounds aligned with LoopX.
The first recommendation must explicitly name the expected executor path:
Codex CLI goal mode, a benchmark-provided Codex adapter with an equivalent goal
surface, or a small public-safe LoopX passive wrapper around an official
executor.

### P1: Official Long-Horizon Engineering Pilot

Run the first small official-protocol pilot on Terminal-Bench, SWE-Marathon, or
another selected long-horizon engineering benchmark:

- stock/native agent path;
- LoopX wrapped worker path;
- identical task, model, allowed tools, environment, and scoring;
- no user-simulator overlay if the official benchmark protocol does not allow
  it;
- event ledger and restartability instrumentation around the worker rather than
  benchmark-internal scoring changes.

The pilot is successful when it produces comparable official metrics and a
restartable LoopX event ledger without changing task answers, tests, or
benchmark policy.

The first pilot must begin with a baseline failure record or a documented
hard-case prior. LoopX treatment is justified only when that baseline
evidence names a control-plane-addressable failure class.

### P1: Passive LoopX Baseline

Run the same selected engineering slice in at least two autonomous modes:

- Codex CLI goal mode without LoopX state;
- Codex CLI goal mode with a passive LoopX wrapper.

No operator-simulator intervention is allowed. Compare task success,
restartability, stale-state errors, duplicated work after interruption,
validation quality, failure attribution, and overhead. This is the first proof
point for whether LoopX helps by itself.

### P1: Planning-Trigger Regression

Add a synthetic long-horizon research fixture that simulates repeated eligible
turns, a no-progress streak, and a repeated recommended action. The fixture
should prove that LoopX emits a bounded planning-refresh todo instead of
quietly looping or relying on the user to re-plan.

### P1: Operator-Simulator Overlay Pilot

After the first official-protocol engineering pilot, run an assisted overlay on
the same or similar long-horizon task slice:

- fixed operator-simulator model and intervention budget;
- no access to hidden tests, expected solutions, or benchmark answer keys;
- allowed interventions may be proactive user-style injections, including
  directive strategy redirects, validation triage, continue/stop decisions, and
  process-drift correction, as long as every message passes the no-oracle
  visibility audit and stays within frequency and token budgets;
- separate reporting from official leaderboard metrics;
- comparison against native and passive control-plane modes.

This pilot answers whether LoopX can model supervised long-horizon work,
not whether the base agent is autonomous SOTA. The first deterministic
active-user assisted pilot remains a deterministic active-user assisted pilot
fixture: it uses a previously failed compact Terminal-Bench case to validate
intervention budgets, no-oracle audits, and score-claim separation before any
model-backed simulator or real assisted runner path.

### P2: Tau Simulator Research Pilot

Run a small tau-style pilot as a user-simulator research slice:

- one domain first;
- one public split or a small representative subset;
- fixed simulator model and seed policy;
- baseline stock agent;
- LoopX wrapped agent;
- identical scoring harness.

This pilot should be labeled as collaboration/user-simulator evidence, not as
the headline long-horizon leaderboard result.

### P1: User-Simulator Ablation

Run the same task slice under at least two user-simulator settings. Record
whether failures are caused by the agent, the simulator, policy ambiguity,
tool-state mismatch, or orchestration overhead.

### P1: Codex Goal Engineering Baseline

Run the selected engineering pilot against real Codex Goal mode and a Goal
Harness wrapped Codex worker. The baseline is not a Codex CLI polling loop and
not a prompt that merely begins with `/goal`; it must show that Codex entered a
persistent goal state through a supported surface. If no stable benchmark-runner
trigger exists yet, park the A/B comparison and keep only runner readiness,
task-data, or trigger-validation work active. Measure completion, validation,
restartability, stale-state errors, overhead, and evidence quality only after
that baseline is proven.

### P1/P2: Cross-Benchmark Failure-Case Gate

For every new benchmark family, run a small baseline failure-mining pass before
any LoopX treatment. The output should be a public-safe failure taxonomy,
a short list of control-plane-addressable cases, and an explicit negative list
of cases rejected because their failures are model-only, environment-only,
oracle/hidden-test ambiguous, or not observable enough. Do not spend treatment
runs until the baseline evidence explains why state, todo, checkpoint, replan,
validation discipline, policy gates, writeback, or failure attribution could
change the result.

### P2: Reproducible Benchmark Pack

Create a benchmark pack that can be rerun from a clean checkout with explicit
model/provider configuration, no private data, and deterministic public-safe
artifact paths.

### P2: Publication Readiness

Prepare a paper-style report once the A/B results show a real signal. The report
should include negative results, overhead, failure taxonomy, user-simulator
limitations, and benchmark-integrity safeguards. Use
`benchmark-experiment-report-template-v0.md` to keep official leaderboard
scores, passive control-plane metrics, assisted operator-simulator ablations,
cost/latency overhead, failure taxonomy, reproducibility artifacts, claim
boundaries, negative results, and next decisions in separate sections.
Use `benchmark-report-chain-map-v0.md` as the reviewer-facing consolidation
point before larger pilots: it lists the fixture-backed order from
`benchmark_run_v0` through `benchmark_experiment_report_replay_decision_v0`,
the fields a worker may trust, and the boundary that keeps chain repair
separate from external benchmark execution.

## Active Agent Todo Seed

- [ ] [P0] Prove the Terminal-Bench 2.0 private/no-upload baseline trigger for
  real Codex Goal mode before any paired treatment: identify the supported
  runner invocation surface, show persistent goal-state evidence, and only then
  run the selected first case (`fix-code-vulnerability` unless the runner
  blocker forces a backup). If the trigger is not stable, record the precise
  trigger gap and do not treat a slash-prefix prompt or polling loop as the
  baseline.
- [ ] [P0] If the Terminal-Bench goal-mode baseline failure is
  control-plane-addressable, run the matched `codex-loopx` treatment on
  the same case with task, prompt, tests, scorer, image, timeout, model, runner
  source, and publication boundary unchanged. If it is not addressable, record
  the negative selection and move to the next selected case.
- [ ] [P0] Promote the baseline-failure gate into the benchmark event/report
  contract: every future benchmark run should expose baseline failure class,
  control-plane addressability, treatment eligibility, and negative-selection
  reason without adding benchmark-specific prompt branches.
- [ ] [P1] Build the WildClawBench adapter dossier under the same failure-first
  gate: identify runner entry, task schema, scoring, baseline failure signals,
  side-effect audit shape, trace publicness, and one possible canary only if the
  failure is control-plane-addressable.
- [ ] [P1] Keep SkillsBench on the AgentLoop / skill-runtime lane. Mine only
  skill-routing, skill-provenance, unsafe-reuse, or negative-transfer failures;
  do not spend LoopX long-horizon treatment unless the failure requires
  skill-state review, provenance gates, or exposure/writeback tracing.
- [ ] [P1/P2] Put WideSearch / DeepWideSearch, SpreadsheetBench, DSBench, and
  tau-style simulator tasks behind the same baseline-failure gate. For each,
  define the family-specific failure classes before any paired LoopX
  treatment.
- [ ] [P1] Keep the autonomous planning-trigger regression in the product track:
  after repeated no-progress, phase transition, backlog mismatch, or evidence
  contradiction, LoopX should split/add/retire todos and emit the next
  bounded validation command.
- [ ] [P2] Triage Agents' Last Exam only after the first Terminal-Bench paired
  pilot or a documented Terminal-Bench blocker. Build an adapter dossier before
  any cloud sandbox, GUI, model API, paid compute, or leaderboard path.

## Non-Goals

- Do not use private user sessions or internal project history as benchmark
  tasks.
- Do not alter benchmark scoring, leak expected answers, or prompt around task
  labels.
- Do not make recurring heartbeat prompts benchmark-specific.
- Do not optimize only for leaderboard rank while losing state truth, user
  coordination, safety, or reproducibility.
