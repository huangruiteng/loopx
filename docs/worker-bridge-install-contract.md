# Goal Harness Worker Bridge Install Contract

Goal Harness worker bridge is the generic contract for making the Goal Harness
CLI available inside an isolated executor, benchmark task container, or runner
worker.

The contract is runner-agnostic. It does not run a benchmark, start a model, or
upload results. It only declares the worker-visible surfaces that a runner must
provide:

```text
schema_version=goal_harness_worker_bridge_install_contract_v0
bridge_surface=goal_harness_worker_bridge_source_mount_v0
install_mode=source_mount_read_only_pythonpath
```

## Contract Shape

The default public-safe preview is:

```bash
goal-harness worker-bridge contract --format json
```

It emits:

```text
mounts:
- source=<goal-harness-project-root> target=<goal-harness-project-root> read_only=true
- source=<goal-harness-runtime-root> target=<goal-harness-runtime-root> read_only=true

goal_harness_command_prefix=PYTHONPATH='<goal-harness-project-root>' python3 -m goal_harness.cli
goal_harness_registry_arg=<goal-harness-runtime-root>/registry.global.json
goal_harness_runtime_root_arg=<goal-harness-runtime-root>
goal_harness_scan_path=<goal-harness-project-root>/goal_harness/benchmark.py
goal_harness_benchmark_run_json=/logs/agent/goal-harness-worker-benchmark-run.json
goal_harness_benchmark_run_schema_version=benchmark_run_v0
goal_harness_benchmark_run_writeback_contract=goal_harness_worker_benchmark_run_writeback_contract_v0
goal_harness_counter_trace_json=/logs/agent/goal-harness-counter-trace.jsonl
```

The placeholder paths are public-safe. A private runner may substitute actual
host paths at launch time, but raw substituted paths must stay out of public
docs, status, benchmark reports, and claim artifacts.

For active-user assisted treatments, the runner may add one extra writable bind
mount for the simulator feed:

```text
source=<active-user-host-dir> target=/goal-harness-active-user read_only=false
goal_harness_active_user_feed_jsonl=/goal-harness-active-user/goal-harness-active-user-interventions.jsonl
goal_harness_active_user_observation_json=/goal-harness-active-user/goal-harness-active-user-observation.json
```

This mount is the host-side coordination surface for appending a post-start
simulator intervention while the worker polls `active-user-observe`. Public
summaries may record that the writable mount was requested and count it, but
must not record the raw host source path.

## Runner Adapter Rule

A runner adapter should translate this contract into its native worker launch
surface. For Harbor/Terminal-Bench this means:

- pass `mounts` through Harbor `--mounts`;
- pass `agent_kwargs` through Harbor `--agent-kwarg`;
- leave `goal_harness_counter_trace_json` on the worker agent log surface;
- only claim in-case Goal Harness use after the worker trace contains at least
  one Goal Harness CLI call.

The contract intentionally avoids hardcoding Terminal-Bench. Other runners can
consume the same payload and map it to their own container, virtualenv, or
sidecar setup.

## Pre-Worker Agent Setup

The Goal Harness worker bridge starts only after the benchmark runner has
prepared the task container and installed the selected agent runtime. A failure
in that pre-worker setup layer is not evidence that the worker ignored Goal
Harness; the worker has not entered its `run()` method yet.

Runner adapters should classify those failures separately from in-worker
interrupts:

```text
worker_start_status=pre_worker_agent_setup_failed
worker_checkpoint_not_expected_before_agent_setup=true
```

For Harbor/Terminal-Bench managed Codex, the custom agent keeps Harbor's Codex
install semantics but hardens the common minimal-image dependency surface. The
generic setup contract is:

- install shell and archive prerequisites before nvm or Codex install
  (`bash`, `ca-certificates`, `curl`, `git`, `xz`, `tar`, `gzip`, `ripgrep`);
- use a preinstalled `node` plus `npm` when the task image already provides
  them, instead of forcing nvm;
- fall back to nvm only when `node` or `npm` is missing;
- symlink `node`, `npm`, and `codex` onto the default command path when present.

This is a worker-entry reliability contract only. It does not change the task
prompt, tests, scoring, resources, upload policy, or Goal Harness in-case
interaction requirements.

## Outcome And Interrupt Policy

Worker bridge verification is separate from official benchmark completion. A
worker may prove that it can call the Goal Harness CLI while the enclosing
runner still has not returned a score. Record that state with:

```bash
goal-harness worker-bridge outcome --format json \
  --worker-cli-call-total 4 \
  --counter-trace-present \
  --interrupted \
  --interrupt-reason controller_interrupt_after_wall_time_limit \
  --wall-time-seconds 720
```

This emits `goal_harness_worker_bridge_outcome_v0` with:

```text
worker_bridge_verified=true
runner_return_status=interrupted_after_worker_bridge_success
official_score_status=blocked_pending_runner_return
changes_official_benchmark_timeout=false
changes_official_task_resources=false
leaderboard_claim_allowed=false
true_long_task_bar_seconds=1800
true_long_task_bar_met=false
```

The wall-time policy is a controller-side evidence/accounting policy only. It
does not change benchmark task files, prompts, tests, resources, official
timeouts, scoring, runner behavior, or upload behavior. Public claims may say
that the worker bridge was verified from compact in-worker CLI counts; they must
not claim official reward completion, leaderboard readiness, or baseline uplift.
For Terminal-Bench runner ingest, the same compact policy also records whether
the observed wall time or the effective agent-timeout tier reaches the true
long-task threshold (`>=1800s`) so sample-speed calibration cannot be mistaken
for long-horizon evidence.

## Worker-Side Benchmark Run Writeback

When the worker can write an agent-log artifact but the enclosing runner has
not yet appended Goal Harness history, the worker should emit a compact
`benchmark_run_v0` payload:

```bash
goal-harness worker-bridge benchmark-run --format json \
  --worker-cli-call-total 4 \
  --counter-trace-present \
  --interrupted \
  --interrupt-reason controller_interrupt_after_wall_time_limit \
  --wall-time-seconds 720 \
  > /logs/agent/goal-harness-worker-benchmark-run.json
```

That JSON is the generic payload for
`goal_harness_benchmark_run_json=/logs/agent/goal-harness-worker-benchmark-run.json`.
It includes `worker_bridge_outcome`, compact progress counters, validation
booleans, stop conditions, and no-upload claim boundaries. A controller or
runner may later append it with:

```bash
goal-harness history append-benchmark-run \
  --goal-id <goal-id> \
  --benchmark-run-json /logs/agent/goal-harness-worker-benchmark-run.json \
  --classification <classification> \
  --execute
```

The writeback payload is public-safe by construction: it records compact
counts, booleans, and labels only. It must not include local paths, raw traces,
Docker logs, Codex session bodies, credentials, auth values, provider billing
exports, or raw task artifacts.

The install contract also exposes
`goal_harness_worker_benchmark_run_writeback_contract_v0`, a compact schema hint
for worker prompts and runner adapters. Its minimum public shape is:

```text
schema_version=benchmark_run_v0
source_runner=<public-runner-label>
benchmark_id=<public-benchmark-label>
job_name=<public-job-label>
mode=<public-mode-label>
worker_mode=<public-worker-mode-label>
real_run=true
submit_eligible=false
leaderboard_evidence=false
official_task_score=<compact score or not-claimed kind>
progress=<compact counts>
validation=<compact booleans>
trials=<compact trial summaries>
```

Write this object at the top level of
`goal_harness_benchmark_run_json`. Do not wrap it as
`{"benchmark_run": {...}}`; runner-side ingest can normalize that historical
envelope, but worker prompts should emit the direct `benchmark_run_v0` shape so
schema counters remain unambiguous.

If `history append-benchmark-run` rejects the worker payload for schema shape,
the worker should rewrite a minimal `benchmark_run_v0` from compact counters and
retry once. The retry must still omit raw paths, raw logs, raw traces, raw task
prompts, raw session bodies, credential values, and auth values.

## Validation

```bash
python3 examples/worker-bridge-install-contract-smoke.py
```

The smoke checks the module builders, CLI JSON output, outcome projection,
worker-side benchmark run writeback, public/private boundary, and the first
Terminal-Bench adapter consumer.
