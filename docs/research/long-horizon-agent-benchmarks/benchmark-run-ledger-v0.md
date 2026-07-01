# Benchmark Run Ledger v0

`benchmark_run_ledger_v0` is the operator-visible index for benchmark case
evidence. It answers four questions without reading raw benchmark artifacts:

- which benchmark cases have been run;
- which arm ran (`codex_goal_mode_baseline`, `codex_loopx_treatment`,
  calibration baselines, or another benchmark adapter arm);
- what compact score/failure class was recorded;
- which compact/public artifact handle can be used for public-safe follow-up.

The ledger is intentionally separate from `benchmark_learning_ledger_v0`.
`benchmark_run_ledger_v0` is the inventory of case attempts. The learning ledger
is the budget/counting decision after a comparison or failure attribution is
reviewed.

The ledger is also intentionally separate from `benchmark_case_analysis_v0`.
`benchmark_case_analysis_v0` is the durable interpretation layer for useful
cases: positive uplift assets, treatment regressions, no-uplift controls, and
infrastructure lessons. A completed case should first land in this run ledger,
then receive a case-analysis entry when it teaches a reusable optimization or
routing lesson.

## Files

- Machine source: `benchmark-run-ledger.json`
- Human view: `benchmark-run-ledger.md`
- Canonical global source: `docs/research/long-horizon-agent-benchmarks/benchmark-run-ledger.json`

Benchmark launchers may also materialize a run-group/local
`remote-ledger/benchmark-run-ledger.json` so interrupted or remote workspaces can
resume with the current view. That local ledger is not canonical by itself. A
run-group ledger should inherit the canonical global ledger before its first
write, then upsert each terminal compact closeout back into the canonical global
ledger. If a run-group ledger contains rows that the canonical global ledger
does not, treat that as a sync gap rather than as two independent result
sources.

Both files are generated from compact `benchmark_run_v0` events. The Markdown
view is for humans; the JSON is the source of truth.

## Update Rule

Every completed benchmark case ingest should upsert one run row:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run terminal-bench \
  --goal-id loopx-meta \
  --harbor-job-dir <private-job-dir> \
  --update-run-ledger \
  --execute
```

The command appends the compact run to LoopX history and updates the
ledger in the same operator action. Dry-runs preview the ledger row but do not
write it.

If the compact `benchmark_run_v0` event already exists, for example in run
history or a benchmark adapter closeout artifact, upsert the ledger without
reopening raw runner artifacts:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run-ledger-upsert \
  --benchmark-run-json <compact-benchmark-run-v0.json> \
  --run-group-id <stable-run-group-id> \
  --execute
```

Closeout agents should also run the compact drift check before deciding a case
is fully recorded:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run-ledger-check \
  --goal-id loopx-meta \
  --history-limit 500
```

The check compares recent compact `benchmark_run_v0` run-history events against
`benchmark-run-ledger.json`. It reports `benchmark_run_ledger_drift_v0` with
missing compact run rows and `run-ledger-upsert` catch-up command templates.
It is read-only and compact-only: it does not open raw logs, task text,
trajectories, Docker, model APIs, uploads, or verifier output. This is the
default posthoc guard for missed closeout writeback across Terminal-Bench,
SkillsBench, and future benchmark adapters.

If a case never reaches `benchmark_run_v0` but the post-launch compact poller
has produced a terminal compact failure marker, upsert that marker directly
instead of faking an official score:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run-ledger-upsert \
  --post-launch-json <terminal-bench-post-launch-compact-json> \
  --run-group-id <stable-run-group-id> \
  --arm-id codex_goal_mode_baseline \
  --execute
```

This route is for runner/worker finalization states such as
`stale_active_job_without_trial_result`. It records the attempt as a blocked
runner/setup closeout, keeps the official score missing, and must not be used
as case-success evidence.

Terminal-Bench private no-upload launch summaries also expose
`closeout_command_templates` with the same `--update-run-ledger` route. A
runner, heartbeat observer, or case-closeout agent should treat that template as
the canonical post-run ingest path instead of relying on chat memory. For
non-Harbor adapters or historical compact events, use `run-ledger-upsert` as the
canonical catch-up path.

SkillsBench uses the same compact ledger route. The no-run adapter skeleton is
available for route inspection:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run skillsbench \
  --goal-id loopx-meta \
  --skillsbench-route codex-goal-mode-baseline \
  --include-task-name citation-check
```

This command is not case evidence: it does not run BenchFlow, Docker, Codex, a
model API, or leaderboard upload. Real SkillsBench runner closeout should write
or provide a compact `benchmark_run_v0`, then call `benchmark run-ledger-upsert`.
The ledger infers route arms such as `codex_goal_mode_baseline`,
`loopx_automation_loop_treatment`, and `curated_skills_baseline` from
compact run modes.

## Current View And Archive

Old runs should not pollute the current operator view after the team switches
to a new benchmark route. Mark obsolete rows archived instead of deleting them:

```bash
PYTHONPATH=<loopx-repo> python3 -m loopx.cli \
  benchmark run-ledger-archive \
  --benchmark-id skillsbench@1.1 \
  --archive-all-matching-benchmark \
  --keep-run-group-contains <current-run-group-substring> \
  --reason "<public-safe archive reason>" \
  --execute
```

Archived rows remain in `benchmark-run-ledger.json` with
`archive_state=archived`, `archive_reason`, `archive_batch_id`, and
`archived_at`. The generated Markdown excludes archived rows from default
`Case Decisions`, `Repair Backlog`, and `Runs`, and instead renders a compact
`Archived Run Summary`. This keeps old experiments traceable without letting
obsolete route attempts dominate current counts.

## Schema

Top-level fields:

- `schema_version`: always `benchmark_run_ledger_v0`.
- `updated_at`: local timestamp of the last ledger write.
- `update_policy`: compact public/private boundary.
- `benchmarks`: map from `benchmark_id` to case records.

Each run row records:

- `run_id`: deterministic compact identity for idempotent upserts.
- `benchmark_id`, `case_id`, `case_ids`.
- `run_group_id`, `arm_id`, `mode`, `job_name`.
- `status`, `score_status`, `official_score`, `official_passed`.
- `failure_class`, `failure_scope`, optional `failure_labels`.
- `loopx_inside_case`, `worker_bridge_status`, `agent_model`.
- `artifact_refs`: public-safe compact/public artifact references only. Raw
  `result.json`, raw logs, trajectories, task text, credentials, uploads,
  absolute paths, and private local run-root paths are not recorded. If a
  compact/public artifact lives under a private local run root, only its
  basename may be recorded.
- optional archive fields: `archive_state=archived`, `archive_reason`,
  `archive_batch_id`, and `archived_at`.

Each case also has `latest_decision`, derived from the current rows:

- `baseline_failed_treatment_candidate`
- `baseline_failed_requires_attribution`
- `baseline_passed_not_current_treatment_priority`
- `baseline_blocked_by_runner_or_setup`
- `paired_baseline_blocked_by_runner_or_setup`
- `paired_treatment_blocked_by_runner_or_setup`
- `paired_result_blocked_by_verifier_or_infra`
- `paired_result_requires_attribution`
- `paired_treatment_improved`
- `paired_no_score_uplift`
- `paired_treatment_regressed`
- `paired_result_needs_score_review`
- `single_arm_recorded`

`latest_decision` may also include `case_routing`, a compact case-history
taxonomy used to avoid blind relaunches when the newest paired decision hides an
older durable signal. Current routing classes include:

- `case_exception_research`: a compact exception attribution asset is needed
  before repeating the case.
- `case_timeout_research`: one solver-timeout signal exists and needs timeout
  context review.
- `timeout_tier_policy_candidate`: repeated solver-timeout signals indicate the
  case needs an explicit timeout tier or continuation-cadence decision before
  another run.
- `bridge_connected_no_uplift`: the LoopX bridge reached the worker, but
  the official score still did not improve; reruns should analyze solution
  quality or case fit rather than treat the route as a bridge repair.

## Boundary

The ledger must not contain raw logs, task prompts, trajectories, credentials,
uploads, hidden test material, absolute local paths, private local run-root
paths, or raw runner result paths. It may contain relative references to
checked-in docs or compact/public artifact handles such as
`benchmark_run.compact.json`; private local run roots must be represented by a
redacted compact handle or omitted.

When a reducer reads raw runner artifacts to classify a failure, it must record
only compact labels such as `codex_model_access_unsupported_for_account` or
`agent_timeout_before_solution_completion`.
