# Terminal-Bench Next Candidate After Install-Windows 2026-06-14

Checked at: 2026-06-14T04:50:00+08:00.

This packet advances the Terminal-Bench P0 after the
`install-windows-3.11` paired compact result. It is a public-safe selection and
preflight packet. It does not read task instructions, hidden tests, solution
files, raw logs, Docker logs, Codex transcripts, trajectories, credentials, or
environment values. It does not start Harbor, Terminal-Bench task containers,
Codex workers, model APIs, uploads, shares, or leaderboard submission.

## Routing Input

The compact verifier-attribution review for `install-windows-3.11` returned:

- `baseline_caveat_resolved=false`;
- `clean_model_attribution=false`;
- blocker `baseline_verifier_attribution_caveat`;
- `treatment_eligible=false`;
- `repeat_allowed=false`;
- `new_candidate_allowed=true`;
- routing action `repair_verifier_preflight_or_select_new_material_ready_case`.

Therefore the next action must not claim uplift or run a same-task repeat for
`install-windows-3.11`. The allowed P0 lane is either to repair the verifier
preflight or select a fresh material-ready Terminal-Bench case.

## Selection

Select `financial-document-processor` as the next Terminal-Bench candidate.

Rationale:

- It was the first fallback in the previous public-safe candidate packet after
  `install-windows-3.11`.
- Cross-history search found no compact run-history or active-state evidence
  for `financial-document-processor` or `multi-source-data-merger`.
- It is a multi-step document/data processing task, which is closer to the
  long-horizon control-plane target than another platform/verifier-repair loop.
- Strict no-run preflight was ready for both the Codex goal-mode baseline and
  the LoopX treatment.

## Strict Preflight Summary

For `terminal-bench@2.0` / `financial-document-processor`:

| Arm | ready | task material | no upload | submit eligible | auth values recorded | raw paths recorded | worker bridge |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Codex goal-mode baseline | true | ready | true | false | false | false | false |
| Codex loopx treatment | true | ready | true | false | false | false | true |

The preflight used the LoopX Terminal-Bench preflight guard with
`--require-task-material-ready`. It records booleans and task ids only.

## Next Allowed Action

Run exactly one private no-upload paired pilot for
`terminal-bench@2.0` / `financial-document-processor`:

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
- relaunching `install-windows-3.11` without a repaired verifier-preflight
  attribution hypothesis.
