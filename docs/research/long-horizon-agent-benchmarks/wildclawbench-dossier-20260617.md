# WildClawBench Dossier 2026-06-17

Checked at: 2026-06-17T01:18:00+08:00.

This is a public-safe route dossier only. It does not run WildClawBench,
OpenClaw, Codex, Docker, model APIs, search APIs, judge models, uploads,
leaderboard submissions, hidden refs, raw task data, raw trajectories, logs,
screenshots, credentials, or private artifacts.

## Source Boundary

Public sources consulted:

- official repository: https://github.com/internlm/WildClawBench
- project site / leaderboard: https://internlm.github.io/WildClawBench/
- paper HTML: https://arxiv.org/html/2605.10912v1
- paper abstract: https://arxiv.org/abs/2605.10912

## What It Is

WildClawBench is a native-runtime benchmark for long-horizon CLI agents. The
released benchmark describes 60 human-authored bilingual tasks across six
categories, with 26 multimodal tasks. The paper reports that tasks average
roughly 8 minutes and more than 20 tool calls per run.

The benchmark is unusually relevant to LoopX because it evaluates the
same task suite across multiple agent harnesses: OpenClaw, Claude Code, Codex,
and Hermes Agent. The public leaderboard also exposes a harness-comparison
table for the same model across those harnesses.

## Why It Matches LoopX

WildClawBench tests three things LoopX cares about more directly than
another same-policy SkillsBench rerun:

1. Harness effects are first-class. The paper reports that switching harness
   alone can shift a model by up to 18 points, and the site publishes per-model
   harness comparison rows.
2. Side effects are part of scoring. The grading stack combines deterministic
   checks, environment-state auditing of actions and side effects, and LLM/VLM
   judging only where semantic checks need it.
3. The runtime is close to real agent work. Tasks run in Docker containers with
   real tools such as shell, browser, file system, email, calendar, and
   optional skills rather than mock APIs.

This makes WildClawBench a better next hypothesis source for LoopX than
continuing to mine already-classified SkillsBench controls. SkillsBench is
still useful for prompt/round-policy regressions, but the current queue already
has baseline-solved, neutral, positive-control, regression, and setup-blocker
cases. WildClawBench more directly asks whether the control layer around an
agent changes work completion, side effects, cost, and traceability.

## Baseline Failure Class To Look For

The useful failure class is not simply "agent gets task wrong." The Goal
Harness-specific target is:

- same model, comparable task, different harness or control layer;
- final score differs, or side-effect auditing differs;
- trace evidence shows stale state, weak recovery, premature stop, unsafe side
  effect, missing artifact, or poor validation discipline;
- LoopX can plausibly help through state truth, todo/replan structure,
  compact evidence, permission gates, or restartable execution.

Good first cases would be tasks where a baseline agent exits early, performs
the wrong side effect, misses an audit requirement, or produces plausible
output without the required artifact/state change.

## No-Upload Feasibility

WildClawBench is not immediately eligible for a no-upload autonomous official
run under the current LoopX standing policy.

Reasons:

- official run examples require model API access through OpenRouter-style
  endpoints;
- search tasks require a Brave Search API key;
- judge-based metrics may call a judge model;
- data preparation may download external assets, including YouTube videos and
  SAM3 weights;
- official leaderboard or personal leaderboard submission paths exist and must
  stay out of autonomous execution.

Safe near-term work is therefore source/readiness only:

1. pin the repository and paper version;
2. inspect task metadata and runner scripts without task execution;
3. identify a tiny subset that does not require search, YouTube, or judge-model
   calls;
4. define a compact reducer schema for harness comparison, side-effect audits,
   cost/time, and trace category counters;
5. stop before Docker task execution, model calls, uploads, or public claims.

## Recommendation

Use WildClawBench as the next benchmark route dossier, not as the next scored
run.

Recommended next step:

- write a no-run setup-readiness scan for the official repository, focusing on
  task metadata visibility, runner command shape, required external services,
  single-task dry-run boundaries, and compact artifact schema.

Do not launch a WildClawBench run until the scan identifies a task slice that
can run locally without uploads, leaderboard submission, hidden grader leakage,
or unauthorized API/search/judge calls.

## Current Queue Decision

This dossier closes the rerank question:

- do not launch the matching `suricata-custom-exfil` treatment because the
  repaired baseline passed at official `1.0` in round 1;
- do not keep repeating same-policy SkillsBench controls without a new prompt
  or stop-policy hypothesis;
- keep Terminal-Bench attribution repairs separate from this lane;
- make the next benchmark research batch a WildClawBench setup-readiness scan.

