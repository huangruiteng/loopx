# Benchmark Case Analysis v0

`benchmark_case_analysis_v0` is the durable learning layer for benchmark case
evidence. It sits above `benchmark_run_ledger_v0`.

The run ledger is the inventory: which case ran, which arm ran, score/failure
class, and compact artifact references. Case analysis is the interpretation:
why a result matters, what it says about LoopX, and which optimization
or routing decision it should inform.

## Files

- Machine source: `benchmark-case-analysis.json`
- Human view: `benchmark-case-analysis.md`

Both files must stay public-safe. They may reference compact run ids, run group
ids, benchmark ids, case ids, arm ids, official scores, compact failure classes,
and generated ledger files. They must not copy raw logs, task prompts,
trajectories, credentials, hidden tests, uploads, or absolute local paths.

## Update Rule

Whenever a benchmark pair reaches a useful conclusion, add or update one case
analysis record:

- a positive uplift case, such as baseline failure plus treatment pass;
- a treatment regression case, such as baseline partial success plus treatment
  worse score;
- a no-uplift case that changes routing priority;
- a setup/runner/verifier class that teaches a reusable infrastructure lesson.

The update should happen after compact result ingest and ledger update. If a
case is still running or only has a launcher/materialization event, keep it out
of case analysis until the compact outcome is known.

## Schema

Top-level fields:

- `schema_version`: always `benchmark_case_analysis_v0`.
- `updated_at`: local timestamp of the last analysis update.
- `source_ledgers`: durable inputs used for interpretation.
- `cases`: list of case analysis records.

Each case records:

- `analysis_id`: stable id, usually `<benchmark>__<case>__<decision>`.
- `benchmark_id`, `case_id`, `decision`, `evidence_status`.
- `scores`: compact baseline/treatment official scores and score delta.
- `arms`: compact arm ids and run ids from `benchmark-run-ledger.json`.
- `classification`: whether this is a positive asset, regression asset, or
  infrastructure lesson.
- `capability_signal`: what the case says about the treatment route.
- `control_plane_signal`: what the case says about harness/runner behavior.
- `optimization_guidance`: concrete follow-up hypotheses or design changes.
- `routing_guidance`: whether to repeat, analyze, retire, or alternate.
- `public_boundary`: compact proof that raw/private material was not copied.

When a case has been rerun under the current main comparison protocol, the
top-level `analysis_id`, `classification`, `decision`, `scores`, and `arms`
must describe that current protocol first. Older positive/regression rows stay
valuable, but they belong in explicit fields such as `legacy_positive_result`,
`legacy_reward_feedback_result`, or `legacy_blind_loop_positive_result`. Do not
mix a legacy `0.0 -> 1.0` score delta into the main table after a current
protocol rerun has shown `1.0 -> 1.0` or `0.0 -> 0.0`.

## Current Seed Cases

- `terminal-bench@2.0 / multi-source-data-merger` is a legacy positive asset
  and a current-protocol non-regression guard: the old `0.0 -> 1.0` row remains
  useful as an end-to-end pass and runner-repair lesson, but the comparable
  current protocol rerun is `1.0 -> 1.0`, so it must not be counted as current
  main-table uplift.
- `skillsbench@1.1 / debug-trl-grpo` is a treatment regression asset:
  after repairing the local Docker CPU setup blocker, the Codex goal-mode
  baseline scored `0.25`, while the automation-loop treatment scored `0.0`.

These records are intentionally paired in the analysis layer: old positive
assets show what helped under older or ablation protocols, while current
protocol rows decide the main table. Regression and no-uplift rows keep prompt,
round-policy, and product-mode claims grounded instead of broad.
