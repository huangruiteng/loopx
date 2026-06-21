# Automation Loop Treatment Case Selection 2026-06-14

This note updates the benchmark route after the treatment definition changed.
It uses compact LoopX ledger summaries plus public SkillsBench metadata
only. It does not read raw task prompts, hidden tests, trajectories, raw logs,
credentials, Docker logs, or local private run contents.

## Treatment Definition

The first real treatment route is no longer "Codex goal mode plus LoopX
packet." It is:

- outer controller: LoopX automation heartbeat loop;
- inner case actor: ordinary/non-goal-mode Codex CLI execution;
- control-plane surface: LoopX CLI status, quota, todo, ledger,
  compact observation, self-repair, and termination writeback;
- result record: benchmark ledger row containing baseline result, treatment
  result, compact artifacts, heartbeat count, per-heartbeat observation class,
  and termination reason.

Codex goal mode remains useful as a failure-mining baseline. The separate
experiment "Codex goal mode plus LoopX skill/CLI" stays parked until the
automation-loop route has clean evidence.

## Terminal-Bench Candidate Set

Source: `benchmark-run-ledger.json` / `benchmark-run-ledger.md`, updated
`2026-06-14T21:22:08+08:00`.

Use Terminal-Bench selected cases as a failure-class mining set, not as an
aggregate benchmark estimate. Current best candidates:

Stop rule: Terminal-Bench is now a bounded engineering lane, not the whole
benchmark program. Study fewer than 10 additional selected cases in this
family. After one repaired P0 rerun proves a compact baseline failure is
attributed and control-plane-addressable, run at most the matching treatment
pilot, then shift priority to SkillsBench.

| Candidate | Compact baseline signal | Why it is useful for automation-loop treatment | Route |
| --- | --- | --- | --- |
| `pytorch-model-recovery` | Codex goal-mode baseline `0.0`; paired treatment `0.0`; compact failure class `agent_exception_before_solution_completion`. | Good for exception attribution, replan, and case-level self-repair hypotheses. | P0/P1 after compact exception hypothesis. |
| `make-doom-for-mips` | Codex goal-mode baseline `0.0`; paired treatment `0.0`; compact failure class `agent_timeout_before_solution_completion`. | Good for long-horizon heartbeat observation, progress/no-progress detection, and timeout-tier policy. | P0/P1 after timeout policy decision. |
| `headless-terminal` | Codex goal-mode baseline `0.0`; failure class `score_failure_unattributed`. | Good for verifier-attribution repair before any treatment launch. | P0 compact attribution first, then decide treatment. |
| `install-windows-3.11` | Codex goal-mode baseline `0.0`; treatment `0.0`; compact worker/verifier alignment blocker. | Good for worker self-validation versus official verifier-facing evidence alignment. | P1 after alignment guard. |

Setup/model-route cases remain important runner repair probes, but should not
be counted as case-capability failures until the worker reaches the task:

- `build-cython-ext`: setup-timeout repair profile required;
- `large-scale-text-editing`: setup-timeout repair profile required;
- `financial-document-processor`: model-access repair route required;
- `multi-source-data-merger`: model-access repair route required.

## SkillsBench Candidate Plan

LoopX now has a public-safe SkillsBench compact adapter skeleton and
ledger route. The adapter does not run SkillsBench by itself; it defines the
family, arm, route, redaction boundary, and `benchmark_run_v0` shape so that a
real runner can later write compact baseline/treatment outcomes into the same
benchmark ledger used by Terminal-Bench.

Public source facts:

- SkillsBench is a skills-focused benchmark for agent behavior and skill use.
- The public task registry lists 87 merged tasks.
- The official getting-started flow uses BenchFlow/Harbor-format tasks with
  Docker and `benchflow run` / `benchflow eval create`.
- The current v1.1 release pins 87 active tasks and 14 excluded
  credential-dependent or integration-incompatible tasks.

Initial SkillsBench mining targets should prefer self-contained, diverse,
public task ids from the v1.1 active set. Start with one task per failure
surface rather than picking by domain popularity:

| Candidate | Category | Difficulty | Why it is useful |
| --- | --- | --- | --- |
| `debug-trl-grpo` | software-engineering | hard | Software/debugging route with likely tool-use and iterative validation pressure. |
| `dapt-intrusion-detection` | cybersecurity | hard | Data/tool workflow with clear verifier and nontrivial artifact handling. |
| `3d-scan-calc` | industrial-physical-systems | hard | Binary parsing plus geometry; good for skill/tool provenance and deterministic checks. |
| `citation-check` | office-white-collar | medium | Document/citation workflow; good for skill retrieval, provenance, and false-positive control. |

Implemented adapter boundary:

- `loopx benchmark run skillsbench` builds a no-run
  `benchmark_run_v0` skeleton for route planning and dry-run inspection.
- Supported routes are `codex-goal-mode-baseline`,
  `automation-loop-treatment`, and `curated-skills-baseline`.
- The automation-loop treatment route means outer LoopX heartbeat
  automation plus ordinary/non-goal-mode Codex CLI inside the case.
- `benchmark_run_ledger_v0` infers `loopx_automation_loop_treatment`
  and `curated_skills_baseline` arms from compact run modes.
- The smoke `examples/skillsbench-benchmark-run-smoke.py` verifies that
  compact SkillsBench baseline/treatment rows can produce a paired improvement
  decision without raw task, solution, trajectory, log, credential, Docker, or
  leaderboard material.

Before any real treatment, the next runner step must:

- run or ingest a real compact no-skill Codex goal-mode baseline result without
  raw task/log leakage;
- mark credential-dependent or integration-incompatible tasks as excluded
  rather than failed;
- preserve the route distinction between no-skill baseline, curated-skill
  baseline, and LoopX automation-loop treatment;
- launch automation-loop treatment only after the baseline failure is
  attributable and control-plane-addressable.

## Next Execution Order

Use an alternating refinement cadence instead of staying on one benchmark
family until exhaustion:

1. Terminal-Bench slice: run one base+test pair on a baseline-failing or
   baseline-weak case, ingest compact `benchmark_run_v0` rows into the run
   ledger, and close with a concrete attribution/uplift/no-uplift hypothesis.
2. SkillsBench slice: run one no-skill Codex goal-mode baseline and one
   automation-loop treatment pair on a self-contained case, using compact
   ledger writeback only. If the baseline is not attributable or
   control-plane-addressable, close the slice as a blocker instead of forcing
   treatment.
3. Repeat the Terminal-Bench / SkillsBench alternation while it produces useful
   runner repair, failure attribution, or treatment hypotheses. Do not broaden
   either family beyond a small selected set before each pair has taught
   something concrete.
4. AgentIssue-Bench resumes only on the single-tag source-alignment lane after
   the alternating pilot has at least one compact closeout in each family.
5. SWE-Marathon returns after capacity route proof.
