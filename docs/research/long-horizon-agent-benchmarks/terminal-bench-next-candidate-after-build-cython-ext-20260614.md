# Terminal-Bench Next Candidate After Build-Cython-Ext 2026-06-14

Checked at: 2026-06-14T06:48:00+08:00.

This packet advances the Terminal-Bench P0 after the `build-cython-ext` paired
compact review. It is a public-safe selection and strict no-run preflight
packet. It does not read task instructions, hidden tests, solution files, raw
logs, Docker logs, Codex transcripts, trajectories, credentials, or
environment values. It does not upload, share, submit, or make leaderboard
claims.

## Routing Input

The compact paired run for `build-cython-ext` closed with:

- Codex goal-mode baseline official score `1.0`;
- Codex loopx treatment official score `1.0`;
- compact-only verifier-attribution review;
- `raw_artifacts_read=false`;
- `repeat_allowed=false`;
- `new_candidate_allowed=true`;
- routing action `select_new_material_ready_case_no_score_failure`.

Therefore the next action should not repeat `build-cython-ext` or claim
treatment lift from it. The allowed P0 lane is selecting a different
material-ready case with a better chance of exposing a Codex goal-mode baseline
failure or a LoopX control-plane advantage.

## Candidate Audit

The recent material-ready queue is now mostly consumed:

- `install-windows-3.11`, `financial-document-processor`,
  `multi-source-data-merger`, `db-wal-recovery`, and `build-cython-ext` have
  current paired compact evidence under the Codex goal-mode versus
  `codex-loopx` comparison shape;
- `kv-store-grpc` already consumed a fresh attempt as a compact
  post-launch-materialization blocker and should not be treated as fresh;
- `custom-memory-heap-crash`, `git-leak-recovery`, `cobol-modernization`,
  `polyglot-rust-c`, and `compile-compcert` have older compact paired
  evidence or blocker history and should not be reselected without a specific
  repeat hypothesis;
- `security-celery-redis-rce` previously failed the material-ready gate.

The remaining high-signal lane is a protocol-calibration case with known
old-protocol failure evidence but no current Codex goal-mode paired closeout.
`pytorch-model-recovery` has compact old bare-Codex hard-case evidence with
official score `0.0`, but that evidence is not equivalent to the current
baseline definition and should not be used as a treatment claim.

## Selection

Select `pytorch-model-recovery` as the next Terminal-Bench candidate.

Rationale:

- it has prior compact low-success signal, so it is more likely to expose the
  failure modes LoopX is meant to make recoverable;
- cross-history screening found no current Codex goal-mode versus
  `codex-loopx` paired closeout for this task;
- both arms passed the current strict no-run preflight with locally resolved
  task material;
- it keeps the corrected baseline definition: Codex CLI goal mode versus
  `codex-loopx`, not bare Codex or an older hardened baseline.

## Strict Preflight Summary

For `terminal-bench@2.0` / `pytorch-model-recovery`:

| Arm | ready | task material | no upload | submit eligible | auth values recorded | raw paths recorded | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | ready | true | false | false | false | false |
| Codex loopx treatment | true | ready | true | false | false | false | true |

The baseline preflight reported
`ready_for_private_managed_no_upload_pilot_review` with
`loopx_access_packet_absent=true` and
`loopx_cli_bridge_absent=true`.

The treatment preflight reported the active-user assisted treatment contract:
the private launch surface is ready, the worker bridge is requested, the
simulator-to-worker update channel is available, and the expected pre-run
blocker is `missing_real_assisted_worker_observation`. That blocker is
normal before launching a real treatment worker; it prevents assisted-score
claims until a post-start worker observation is actually ingested.

## Next Allowed Action

Run exactly one private no-upload protocol-calibration paired pilot for
`terminal-bench@2.0` / `pytorch-model-recovery`:

1. run the Codex goal-mode baseline with no LoopX access packet or
   worker bridge;
2. run the `codex-loopx` treatment with the active worker bridge and
   active-user assisted treatment path;
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
- publishing paper-style uplift claims from this single candidate;
- treating old bare-Codex failure evidence as equivalent to the current Codex
  goal-mode baseline.

## Smoke

```bash
python3 examples/terminal-bench-candidate-routing-packets-smoke.py
```
