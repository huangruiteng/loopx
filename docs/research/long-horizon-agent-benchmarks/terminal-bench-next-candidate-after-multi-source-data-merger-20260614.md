# Terminal-Bench Next Candidate After Multi-Source-Data-Merger 2026-06-14

Checked at: 2026-06-14T05:24:00+08:00.

This packet advances the Terminal-Bench P0 after the
`multi-source-data-merger` paired compact result. It is a public-safe selection
and preflight packet. It does not read task instructions, hidden tests,
solution files, raw logs, Docker logs, Codex transcripts, trajectories,
credentials, or environment values. It does not upload, share, submit, or make
leaderboard claims.

## Routing Input

The compact paired run for `multi-source-data-merger` closed with:

- Codex goal-mode baseline official score `1.0`;
- Codex loopx treatment official score `1.0`;
- compact-only verifier-attribution review;
- `raw_artifacts_read=false`;
- `treatment_eligible=false`;
- `repeat_allowed=false`;
- `new_candidate_allowed=true`;
- routing action `select_new_material_ready_case_no_score_failure`.

Therefore the next action should not repeat `multi-source-data-merger` or claim
treatment lift from it. The allowed P0 lane is selecting a material-ready case
with a better chance of exposing a Codex goal-mode baseline failure or a Goal
Harness control-plane advantage.

## Candidate Audit

The direct backup queue from the older official hard-case packet is already
resolved:

- `git-leak-recovery` completed as both-pass loop-validation evidence under
  the older hardened-baseline protocol;
- `qemu-startup` has compact task-material blocker evidence;
- `qemu-alpine-ssh` completed as verifier-platform failure/writeback-loss
  evidence;
- `compile-compcert` already has true-long completion evidence.

The highest-value remaining public-safe lane is therefore a protocol
calibration case: rerun a known old-protocol recovery candidate under the
current baseline definition, Codex goal mode versus `codex-loopx`.

## Selection

Select `db-wal-recovery` as the next Terminal-Bench candidate.

Rationale:

- Under the older hardened-baseline versus LoopX active-user protocol,
  `db-wal-recovery` was a rare score-recovery case: baseline score `0.0`,
  treatment score `1.0`.
- Cross-history search found no `codex_goal_mode` baseline result for this task.
- This directly answers the current benchmark design correction: the comparison
  baseline should be Codex CLI goal mode, not bare/hardened Codex.
- Strict no-run preflight was ready for both the Codex goal-mode baseline and
  the LoopX treatment.

## Strict Preflight Summary

For `terminal-bench@2.0` / `db-wal-recovery`:

| Arm | ready | task material | no upload | submit eligible | auth values recorded | raw paths recorded | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | ready | true | false | false | false | false |
| Codex loopx treatment | true | ready | true | false | false | false | true |

The preflight used the LoopX Terminal-Bench preflight guard with
`--require-task-material-ready`. It records booleans and task ids only.

## Next Allowed Action

Run exactly one private no-upload protocol-calibration paired pilot for
`terminal-bench@2.0` / `db-wal-recovery`:

1. run the Codex goal-mode baseline with no LoopX access packet or
   worker bridge;
2. run the `codex-loopx` treatment with the active worker bridge;
3. ingest only compact Harbor results after both arms close or emit compact
   blockers;
4. run `benchmark_verifier_attribution_review_v0` before any same-task repeat
   or treatment claim.

## Stop Conditions

Stop before:

- reading raw task instructions, hidden tests, solution files, trajectories,
  raw logs, Docker logs, or Codex transcripts;
- copying credential values or Codex auth material;
- changing benchmark task files, tests, scoring, prompts, or resources;
- uploading, sharing, submitting, or making leaderboard claims;
- publishing paper-style uplift claims from this single candidate;
- treating older hardened-baseline evidence as equivalent to the current Codex
  goal-mode baseline.
