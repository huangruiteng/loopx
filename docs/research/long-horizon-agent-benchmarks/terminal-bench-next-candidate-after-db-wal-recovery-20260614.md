# Terminal-Bench Next Candidate After DB-WAL-Recovery 2026-06-14

Checked at: 2026-06-14T05:50:00+08:00.

This packet advances the Terminal-Bench P0 after the `db-wal-recovery` paired
compact review. It is a public-safe selection and strict no-run preflight
packet. It does not read task instructions, hidden tests, solution files, raw
logs, Docker logs, Codex transcripts, trajectories, credentials, or environment
values. It does not upload, share, submit, or make leaderboard claims.

## Routing Input

The compact paired run for `db-wal-recovery` closed with:

- Codex goal-mode baseline official score `1.0`;
- Codex loopx treatment official score `0.0`;
- compact-only verifier-attribution review;
- treatment caveat `verifier_platform_probe_failure`;
- no same-task treatment claim;
- no same-task repeat;
- routing action `select_new_material_ready_case_no_score_failure`.

Therefore the next action should not repeat `db-wal-recovery`, should not claim
LoopX lift from it, and should select a different material-ready case.

## Candidate Audit

The current selection pass rejected already-closed or lower-signal candidates:

- `custom-memory-heap-crash` already has completed paired official evidence;
- `pytorch-model-cli` already produced a paired negative control-plane repair
  path and should not be conflated with `pytorch-model-recovery`;
- `pytorch-model-recovery` has older bare-Codex failure evidence, but the known
  attribution is dependency-install failure under the old protocol, so it is a
  second-choice failure-mode assistance case rather than the next protocol
  calibration candidate;
- `kv-store-grpc` remains a viable backup, but its last compact state was the
  same post-launch materialization blocker class as `build-cython-ext`.

The highest-value remaining candidate is `build-cython-ext`: it is
material-ready under the current preflight guard, has unresolved official
Terminal-Bench materialization/control-plane value from the earlier run history,
and exercises the kind of compile/runtime setup surface where Codex goal mode
can fail before a verifier score becomes meaningful.

## Selection

Select `build-cython-ext` as the next Terminal-Bench candidate.

Rationale:

- It is not a same-task repeat after `db-wal-recovery`.
- It is material-ready for `terminal-bench@2.0` under the current strict
  preflight guard.
- It preserves the corrected baseline definition: Codex CLI goal mode versus
  `codex-loopx`, not bare Codex versus a harnessed worker.
- It is better suited than already-completed candidates for testing whether
  LoopX improves launch discipline, compact blocker capture, and
  recovery from setup-heavy benchmark failures.

## Strict Preflight Summary

For `terminal-bench@2.0` / `build-cython-ext`:

| Arm | dry-run ok | task material required | no upload boundary | submit eligible | auth values read | real runner invoked | real Codex invoked | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | true | true | false | false | false | false | absent |
| Codex loopx treatment | true | true | true | false | false | false | false | requested; minimum worker calls `1` |

Both arms reported `ready_for_private_managed_no_upload_pilot_review`. The
preflight used the LoopX Terminal-Bench preflight guard with
`--require-task-material-ready`; it records booleans and task ids only.

## Next Allowed Action

Run exactly one private no-upload paired pilot for `terminal-bench@2.0` /
`build-cython-ext`:

1. run the Codex goal-mode baseline without a LoopX access packet or
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
- changing benchmark task files, tests, scoring, prompts, resources, or
  timeouts;
- uploading, sharing, submitting, or making leaderboard claims;
- publishing uplift claims from this single candidate;
- treating launch success, process spawn, or dry-run readiness as a benchmark
  score.
