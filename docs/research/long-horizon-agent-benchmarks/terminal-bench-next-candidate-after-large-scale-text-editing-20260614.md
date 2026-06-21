# Terminal-Bench Next Candidate After Large-Scale-Text-Editing 2026-06-14

Checked at: 2026-06-14T07:53:51+08:00.

This packet advances the Terminal-Bench P0 after the
`large-scale-text-editing` compact paired closeout and the follow-up
`require_existing_codex` worker-startup blocker. It is a public-safe routing
and strict no-run preflight packet. It does not read task instructions, hidden
tests, solution files, raw logs, Docker logs, Codex transcripts,
trajectories, credentials, environment values, or private runner roots. It
does not upload, share, submit, or make leaderboard claims.

## Routing Input

The latest `large-scale-text-editing` compact evidence is not a reason to
repeat the same task immediately:

- Codex goal-mode baseline closed with official score `0.0`;
- `codex-loopx` treatment also closed with official score `0.0`;
- the treatment worker bridge did not reach the required in-case LoopX
  CLI counter trace;
- the current active P0 records the same-task repeat as blocked until Codex is
  usable before worker start or worker CLI counter trace reaches the minimum;
- the compact route should therefore choose a fresh material-ready case rather
  than spending another turn on the same worker-startup blocker.

The blocker is useful evidence about the runner surface, but it is not a
benchmark success, an official-score improvement, or a public claim.

## Candidate Audit

The previous post-`regex-log` packet named this fallback order if
`large-scale-text-editing` launch readiness changed:

1. `git-multibranch`;
2. `nginx-request-logging`;
3. `headless-terminal`;
4. `mteb-retrieve`;
5. write a compact blocker and rerank benchmark families.

This turn reran strict no-run preflights for the first three fallback
candidates with the current comparison shape: Codex CLI goal mode versus
`codex-loopx`.

| Candidate | Codex goal-mode baseline | `codex-loopx` treatment | Notes |
| --- | --- | --- | --- |
| `git-multibranch` | ready | ready | Source-control workflow, high fit for restart/state and validation behavior. |
| `nginx-request-logging` | ready | ready | Config/debugging fallback. |
| `headless-terminal` | ready | ready | Terminal/UI-like fallback. |

For all six preflight surfaces, strict preflight reported:

- `task_material_readiness_status=ready`;
- `task_material_ready=true`;
- `no_upload_boundary=true`;
- `submit_eligible=false`;
- `auth_values_recorded=false`;
- `raw_paths_recorded=false`;
- `worker_bridge_requested=true` for the treatment arm;
- `worker_bridge_requested=false` for the Codex goal-mode baseline.

The preflights were written to a local-private temporary evidence directory.
Public docs record only compact booleans and task ids.

## Selection

Select `git-multibranch` as the next Terminal-Bench candidate.

Rationale:

- it is the first fallback from the previous public-safe routing packet;
- both arms are material-ready under strict no-run preflight;
- it avoids immediate repetition of the current `large-scale-text-editing`
  worker-startup blocker;
- its source-control shape is likely to expose state, validation, and
  rollback/restart behavior without depending on heavyweight model downloads
  or brute-force resource use;
- it preserves the corrected comparison baseline: Codex CLI goal mode versus
  `codex-loopx`.

## Next Allowed Action

Run exactly one private no-upload paired pilot for `terminal-bench@2.0` /
`git-multibranch`:

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
- treating compact preflight readiness as a benchmark score.

## Smoke

```bash
python3 examples/terminal-bench-candidate-routing-packets-smoke.py
```
