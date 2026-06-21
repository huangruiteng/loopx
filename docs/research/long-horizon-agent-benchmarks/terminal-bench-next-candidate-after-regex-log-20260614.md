# Terminal-Bench Next Candidate After Regex-Log 2026-06-14

Checked at: 2026-06-14T13:12:00+08:00.

This packet advances the Terminal-Bench P0 after the restarted `regex-log`
paired compact closeout. It is a public-safe source-boundary and selection
packet. It does not read task instructions, hidden tests, solution files, raw
logs, Docker logs, Codex transcripts, trajectories, credentials, environment
values, or private runner roots. It does not upload, share, submit, or make
leaderboard claims.

## Routing Input

The restarted private no-upload `terminal-bench@2.0` / `regex-log` pair closed
with:

- Codex goal-mode baseline official score `1.0`;
- `codex-loopx` treatment official score `1.0`;
- official score delta `0.0`;
- treatment worker bridge verified with two LoopX CLI calls;
- compact runner invariants clean;
- no raw logs, task text, trajectory, transcript, credential, upload, submit,
  or leaderboard surface used;
- compact claim review `loop_validation_no_score_uplift`;
- learning-ledger routing `repeat_allowed=false` and
  `new_candidate_allowed=true`.

Therefore the next action should not repeat `regex-log` unless a named
cost-control hypothesis exists. The safe P0 lane is to select a stronger
material-ready case under the current comparison shape: Codex CLI goal mode
versus `codex-loopx`.

## Source Boundary Gate

Before selection, the candidate source-boundary guard was run on the planned
selection inputs:

- active-state summary;
- public benchmark research README;
- current public next-candidate packets;
- the candidate-source-boundary smoke.

The guard reported `clean=true`, `allowed_source_count=5`,
`blocked_source_count=0`, and `path_recorded=false`.

The follow-up task-id scan used only cached official task directory names and
presence checks for `instruction.md` and `task.toml`. It did not open those
files or record local paths.

## Candidate Audit

The current material-ready queue from recent public packets is exhausted or
blocked:

- `install-windows-3.11`, `financial-document-processor`,
  `multi-source-data-merger`, `db-wal-recovery`, `build-cython-ext`,
  `pytorch-model-recovery`, `make-doom-for-mips`, and `regex-log` already have
  current compact evidence or compact blockers under the corrected
  Codex-goal-mode comparison.
- `pytorch-model-recovery` same-task repeat remains blocked by repeated
  pre-worker environment setup failure.
- `make-doom-for-mips` repeat remains blocked without a named cost-control
  hypothesis.

A name-only cached official task-id scan found 88 material-ready local
Terminal-Bench task ids. Sixty of those task ids were not mentioned in the
active state. Eight fresh unmentioned candidates were strict-preflighted with
the current paired baseline shape:

| Candidate | Codex goal-mode baseline | `codex-loopx` treatment | Notes |
| --- | --- | --- | --- |
| `headless-terminal` | ready | ready | Terminal/UI-like candidate, but less likely to stress multi-step editing. |
| `git-multibranch` | ready | ready | Source-control candidate and first fallback. |
| `large-scale-text-editing` | ready | ready | Long-context editing candidate with high LoopX fit. |
| `nginx-request-logging` | ready | ready | Config/debugging candidate and second fallback. |
| `mteb-retrieve` | ready | ready | Retrieval/ML candidate, possible external-package friction. |
| `hf-model-inference` | ready | ready | ML inference candidate, possible model/runtime friction. |
| `path-tracing` | ready | ready | Graphics/build candidate, potentially long but less control-plane-specific. |
| `password-recovery` | ready | ready | Security/search candidate, possible brute-force resource risk. |

For all eight candidates and both arms, strict preflight reported:

- `task_material_readiness_status=ready`;
- `task_material_ready=true`;
- `no_upload_boundary=true`;
- `submit_eligible=false`;
- `auth_values_recorded=false`;
- `raw_paths_recorded=false`;
- `validation_passed=true`.

For all `codex-loopx` treatment arms, the active worker bridge was
requested and the worker mount surface was ready.

## Selection

Select `large-scale-text-editing` as the next Terminal-Bench candidate.

Rationale:

- it is material-ready for both arms under the strict no-upload preflight;
- it is not mentioned in the active state, so it is fresher than the recently
  exhausted queue and older protocol-calibration cases;
- its long-context editing shape is more likely than `regex-log` to expose
  stale context, restart, validation, and compact writeback failure modes that
  LoopX is meant to reduce;
- it avoids model-download-heavy and brute-force-shaped candidates while still
  being more diagnostic than another narrow parser/log case;
- it preserves the corrected comparison baseline: Codex CLI goal mode versus
  `codex-loopx`.

Fallback order if launch readiness changes:

1. `git-multibranch`;
2. `nginx-request-logging`;
3. `headless-terminal`;
4. `mteb-retrieve`;
5. write a compact blocker and rerank benchmark families instead of repeating
   `regex-log`.

## Next Allowed Action

Run exactly one private no-upload paired pilot for `terminal-bench@2.0` /
`large-scale-text-editing`:

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
- recursing private runner roots or raw trial directories;
- copying credential values or Codex auth material;
- changing benchmark task files, tests, scoring, prompts, resources, or
  timeouts;
- uploading, sharing, submitting, or making leaderboard claims;
- publishing paper-style uplift claims from this single candidate;
- treating launch success, process spawn, or dry-run readiness as a benchmark
  score.

## Smoke

```bash
python3 examples/terminal-bench-candidate-routing-packets-smoke.py
```
