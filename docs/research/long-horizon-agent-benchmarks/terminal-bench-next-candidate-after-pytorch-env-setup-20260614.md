# Terminal-Bench Next Candidate After Pytorch Env Setup 2026-06-14

Checked at: 2026-06-14T08:56:00+08:00.

This packet repairs the Terminal-Bench P0 after the
`pytorch-model-recovery` environment setup gate. It is a public-safe selection
and strict no-run preflight packet. It does not read task instructions, hidden
tests, solution files, raw logs, Docker logs, Codex transcripts, trajectories,
credentials, or environment values. It does not upload, share, submit, or make
leaderboard claims.

## Routing Input

The `pytorch-model-recovery` same-task repeat is blocked:

- compact paired and treatment-repeat results attributed the failure to
  `environment_setup_failed_before_worker`;
- a real local no-upload/no-submit Harbor NOP environment setup probe repeated
  the same pre-worker failure;
- the probe invoked no Codex worker, model API, verifier, upload, or
  leaderboard submission;
- lifecycle routing keeps `environment_setup_repeat_allowed=false` and
  `repeat_allowed=false` for same-task retry.

Therefore the next action should not repeat `pytorch-model-recovery` or return
to an exhausted earlier case. The allowed P0 lane is to select a fresh
material-ready official Terminal-Bench case with the current paired baseline:
Codex goal mode versus `codex-loopx`.

## Self-Repair Finding

Reject the stale `db-wal-recovery` open todo from the active state.

Rationale:

- `db-wal-recovery` already has a current Codex goal-mode versus
  `codex-loopx` paired compact closeout;
- the compact review recorded baseline official score `1.0`,
  treatment official score `0.0`, and routed away from same-task repeat;
- a later public-safe packet selected `build-cython-ext` after that review, so
  reselecting `db-wal-recovery` would duplicate an already-consumed candidate.

This is a control-plane projection repair, not a benchmark result. It keeps the
automation from spending a real run on stale todo text.

## Candidate Audit

Consumed or blocked current-protocol cases include:

- `install-windows-3.11`, `financial-document-processor`,
  `multi-source-data-merger`, `db-wal-recovery`, and `build-cython-ext` with
  current paired compact evidence;
- `pytorch-model-recovery`, blocked by repeated pre-worker environment setup
  failure before Codex/model/verifier start;
- `fix-code-vulnerability` and `modernize-scientific-stack`, whose Codex
  goal-mode baselines passed and therefore skipped treatment under the
  baseline-failure gate;
- `llm-inference-batching-scheduler`, blocked by verifier/platform attribution;
- older paired or blocker evidence for `compile-compcert`,
  `git-leak-recovery`, `qemu-alpine-ssh`, `qemu-startup`,
  `custom-memory-heap-crash`, `cobol-modernization`, and
  `polyglot-rust-c`.

Two fresh candidates were strict-preflighted with the current paired baseline
shape:

| Candidate | Codex goal-mode baseline | Codex loopx treatment | Notes |
| --- | --- | --- | --- |
| `make-doom-for-mips` | ready | ready | System/build task likely to expose setup, compilation, and long-horizon debugging failure modes. |
| `regex-log` | ready | ready | Material-ready, but likely narrower and less diagnostic than a system/build case. |

For both candidates and both arms, strict preflight reported:

- `task_material_readiness_status=ready`;
- `no_upload_boundary=true`;
- `submit_eligible=false`;
- `auth_values_recorded=false`;
- `raw_paths_recorded=false`;
- no Harbor task run, Codex worker, model API, upload, or leaderboard action.

## Selection

Select `make-doom-for-mips` as the next Terminal-Bench candidate.

Rationale:

- it is material-ready under strict no-run preflight for both arms;
- no current paired closeout was found in the active-state and private-run
  directory audit;
- its system/build shape is more likely than `regex-log` to expose failures
  LoopX should help recover or classify;
- it preserves the corrected baseline definition: Codex CLI goal mode versus
  `codex-loopx`, not bare Codex or an older hardened baseline.

## Strict Preflight Summary

For `terminal-bench@2.0` / `make-doom-for-mips`:

| Arm | ready | task material | no upload | submit eligible | auth values recorded | raw paths recorded | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | ready | true | false | false | false | false |
| Codex loopx treatment | true | ready | true | false | false | false | true |

The baseline preflight reported
`ready_for_private_managed_no_upload_pilot_review` with
`loopx_access_packet_absent=true` and
`loopx_cli_bridge_absent=true`.

The treatment preflight reported the active-user assisted treatment contract
with the active worker bridge requested. Its expected pre-run blocker is
`missing_real_assisted_worker_observation`, which is normal before a real
treatment worker starts and observes a post-start simulator message.

## Next Allowed Action

Run exactly one private no-upload paired pilot for `terminal-bench@2.0` /
`make-doom-for-mips`:

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
- treating old hardened or bare-Codex evidence as equivalent to the current
  Codex goal-mode baseline.

## Smoke

```bash
python3 examples/terminal-bench-candidate-routing-packets-smoke.py
```
