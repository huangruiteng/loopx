# Terminal-Bench Next Candidate Selection 2026-06-14

Checked at: 2026-06-14T04:10:00+08:00.

This packet advances the Terminal-Bench P0 after the
`llm-inference-batching-scheduler` verifier-attribution routing repair. It is a
no-run, no-upload, public-safe candidate selection packet. It does not run
Harbor, Terminal-Bench tasks, Docker task containers, Codex workers, model APIs,
uploads, shares, or leaderboard submission.

## Routing Input

The compact verifier-attribution review for
`llm-inference-batching-scheduler` says:

- `treatment_eligible=false`;
- `repeat_allowed=false`;
- `new_candidate_allowed=true`;
- `requires_verifier_preflight_repair=true`;
- `next_allowed_action=repair_verifier_preflight_or_select_new_material_ready_case`.

Therefore the next benchmark action must not run a treatment or same-task
repeat for `llm-inference-batching-scheduler` until its verifier preflight is
repaired. The safe P0 lane is to select a fresh material-ready hard case, or to
repair verifier preflight before returning to that task.

## Source Boundaries

Selection used only compact control-plane surfaces:

- local task ids from the cached official `terminal-bench@2.0` material;
- paired-run directory names to exclude already attempted tasks;
- active-state and run-history compact summaries to exclude previously closed
  benchmark evidence, including tasks whose old artifacts are no longer visible
  in the current private job directory listing;
- existing compact candidate-screen summaries;
- strict no-run preflight summaries for candidate names.

The selection did not read task instructions, hidden tests, solution files, raw
logs, Docker logs, Codex transcripts, trajectories, credentials, environment
values, or local private paths. It did not start task containers or workers.

## Candidate State

The local cache exposes 89 official task ids. Existing paired-run directories
exclude 22 previously attempted task ids or repeats. Prior fresh-candidate
screens were also consumed: their ready candidates have already been attempted
except `security-celery-redis-rce`, which was not material-ready in the latest
screen.

Five cached candidates were strict-preflighted with the correct paired baseline
shape:

| Candidate | Codex goal-mode baseline | LoopX treatment | Notes |
| --- | --- | --- | --- |
| `compile-compcert` | ready | ready | Rejected after cross-history audit: already closed as a true-long paired case. |
| `install-windows-3.11` | ready | ready | System-state recovery; likely high environment friction. |
| `financial-document-processor` | ready | ready | Multi-step document/data processing candidate. |
| `multi-source-data-merger` | ready | ready | Integration/data-merging candidate. |
| `pytorch-model-recovery` | ready | ready | ML debugging/recovery candidate. |

For all five candidates and both arms, the strict preflight summary reported:

- `task_material_readiness_status=ready`;
- `no_upload_boundary=true`;
- `submit_eligible=false`;
- `auth_values_recorded=false`;
- `raw_paths_recorded=false`;
- no real runner, real Codex worker, model API, upload, or leaderboard action.

## Self-Repair Finding

Reject `compile-compcert` from this launch.

Rationale:

- The previous selection treated current paired-run directory names as the only
  attempted-task exclusion surface.
- The active state and run history already contain compact evidence that
  `compile-compcert` closed as a true-long paired `terminal-bench@2.0` case,
  with a recorded instruction not to relaunch it as the next candidate.
- Therefore `compile-compcert` is
  `rejected_already_completed_true_long`, even though strict no-run preflight
  can still verify that both arms are material-ready.

This is a candidate-selection control-plane repair, not a benchmark run. It did
not invoke Harbor, Docker, Codex, model APIs, uploads, or any task container.

## Selection

Select `install-windows-3.11` as the next Terminal-Bench candidate.

Rationale:

- It is material-ready under strict no-run preflight for both arms.
- Cross-history search found no active-state or run-history evidence for
  `install-windows-3.11`, unlike `compile-compcert` and
  `pytorch-model-recovery`.
- Its system-state recovery shape is likely to stress long-horizon environment,
  dependency, and verifier reasoning.
- It avoids the current `llm-inference-batching-scheduler` verifier-preflight
  blocker without discarding that blocker.

If `install-windows-3.11` becomes blocked before launch, use this fallback
order:

1. `financial-document-processor`;
2. `multi-source-data-merger`;
3. repair the `llm-inference-batching-scheduler` verifier preflight;
4. run a fresh public-safe candidate screen before choosing any task with prior
   compact benchmark evidence.

## Next Allowed Action

Run exactly one private no-upload paired pilot for
`terminal-bench@2.0` / `install-windows-3.11`:

1. run the Codex goal-mode baseline, with no LoopX access packet or
   worker bridge;
2. run the `codex-loopx` treatment with the active worker bridge and
   active-user assisted treatment path;
3. ingest only compact Harbor results after completion or compact blocker;
4. write one compact comparison with official score, failure attribution,
   worker writeback, LoopX call counters, claim boundary, no-upload
   boundary, and submit-disabled status.

Use the `benchmark_verifier_attribution_review_v0` routing after the run before
any same-task repeat or treatment claim.

## Stop Conditions

Stop before:

- reading raw task instructions, hidden tests, solution files, trajectories,
  raw logs, Docker logs, or Codex transcripts;
- copying credential values or Codex auth material;
- changing benchmark task files, tests, scoring, prompts, or resources;
- uploading, sharing, submitting, or making leaderboard claims;
- publishing paper-style uplift claims from this single candidate;
- relaunching `llm-inference-batching-scheduler` without verifier preflight
  repair or a new explicit attribution hypothesis.

## Smoke

```bash
python3 examples/terminal-bench-candidate-routing-packets-smoke.py
```
