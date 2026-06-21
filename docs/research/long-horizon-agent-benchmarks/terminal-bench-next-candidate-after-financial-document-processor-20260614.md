# Terminal-Bench Next Candidate After Financial-Document-Processor 2026-06-14

Checked at: 2026-06-14T05:09:00+08:00.

This packet advances the Terminal-Bench P0 after the
`financial-document-processor` paired compact result. It is a public-safe
selection and preflight packet. It does not read task instructions, hidden
tests, solution files, raw logs, Docker logs, Codex transcripts, trajectories,
credentials, or environment values. It does not upload, share, submit, or make
leaderboard claims.

## Routing Input

The compact paired run for `financial-document-processor` closed with:

- Codex goal-mode baseline official score `1.0`;
- Codex loopx treatment official score `1.0`;
- compact-only verifier-attribution review;
- `raw_artifacts_read=false`;
- no same-task uplift claim;
- no same-task repeat value.

Therefore the next action should not repeat `financial-document-processor` or
claim treatment lift from it. The allowed P0 lane is selecting a fresh
material-ready Terminal-Bench case and running the same no-upload paired pilot
protocol.

## Selection

Select `multi-source-data-merger` as the next Terminal-Bench candidate.

Rationale:

- It was the next fallback in the public-safe candidate queue after
  `financial-document-processor`.
- Cross-history search found no compact benchmark-run evidence for
  `multi-source-data-merger`; prior references were only candidate/routing
  mentions.
- It is an integration/data-merging task, which is a better fit for long-horizon
  control-plane value than repeating an already both-pass case.
- Strict no-run preflight was ready for both the Codex goal-mode baseline and
  the LoopX treatment.

## Strict Preflight Summary

For `terminal-bench@2.0` / `multi-source-data-merger`:

| Arm | ready | task material | no upload | submit eligible | auth values recorded | raw paths recorded | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | ready | true | false | false | false | false |
| Codex loopx treatment | true | ready | true | false | false | false | true |

The preflight used the LoopX Terminal-Bench preflight guard with
`--require-task-material-ready`. It records booleans and task ids only.

## Next Allowed Action

Run exactly one private no-upload paired pilot for
`terminal-bench@2.0` / `multi-source-data-merger`:

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
- repeating `financial-document-processor` unless a new compact attribution
  question is defined.
