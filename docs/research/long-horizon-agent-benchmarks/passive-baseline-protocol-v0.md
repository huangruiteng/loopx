# Passive Baseline Protocol V0

Checked at: 2026-06-07T20:05:00+08:00

## Purpose

This protocol is the first LoopX baseline that answers whether the
control plane helps without any operator simulator. It compares the same
autonomous engineering slice in two modes:

- `codex_goal_mode_baseline`: Codex CLI or a deterministic Codex-like fixture
  runs through the declared Codex goal-mode baseline surface and receives no
  LoopX registry, quota, review packet, Goal Tick output, or runtime
  writeback surface.
- `passive_loopx_wrapper`: the same goal-mode worker and task are
  wrapped with LoopX state, quota, review packet, Goal Tick phases,
  validation writeback, and run-history append support, but no simulated
  operator intervention is allowed.

The protocol is deliberately passive. It may record and validate control-plane
events, but it must not change task prompts, benchmark tests, scoring, resource
limits, timeouts, hidden answers, or official runner behavior. In this mode, no
simulated operator intervention is allowed.

## Fixture Order

Start local and deterministic before invoking official benchmark runners:

1. Run `mini_control_plane_repair_v0` with the existing deterministic worker
   pair from `examples/codex-cli-long-run-benchmark-smoke.py`.
2. Produce `benchmark_result_v0` for both modes and a
   `benchmark_comparison_v0` summary.
3. Verify both modes use the same task id, worker surface, validation contract,
   and official-task score layer.
4. Require the with-harness mode to improve only control-plane dimensions:
   restartability, stale-state avoidance, continuation quality, evidence
   discipline, writeback quality, failure attribution, or spend discipline.
5. Append one compact `benchmark_run_v0` row per mode through
   `loopx history append-benchmark-run`.
6. Inspect status/run history for two benchmark rows and no private surface.

Only after this deterministic fixture is stable should the same mode pair move
to a real Terminal-Bench or Harbor pilot.

## Required Measurements

Each paired result must preserve these fields:

| Field | Rule |
| --- | --- |
| `scenario_id` | `codex_goal_mode_baseline` or `passive_loopx_wrapper`. |
| `task_id` | Same task id for both modes. |
| `worker_surface` | Same worker class unless the experiment explicitly records an ablation. |
| `codex_goal_mode_enabled` | `true` for both primary modes. |
| `official_task_score` | Native or deterministic task score; local fixture should keep the delta at `0`. |
| `control_plane_score` | LoopX coordination score; passive wrapper may improve this. |
| `restartability` | Whether another worker can resume from public artifacts. |
| `stale_state_avoidance` | Whether current state beats stale latest-run or stale todo text. |
| `continuation_quality` | Whether the next action is durable and specific. |
| `evidence_discipline` | Whether validation/failure evidence exists outside chat. |
| `writeback_quality` | Whether state/run history records enough context to continue. |
| `failure_attribution` | Compact cause labels when the run fails or stalls. |
| `overhead` | Step, wall-time, spend, and writeback overhead. |

The local fixture may encode these dimensions through
`benchmark_result_v0.control_plane_score.components`. The runtime history row
uses compact `benchmark_run_v0` so dashboard/status can count and route it
without reading raw benchmark logs.

## Append Command

For each mode:

```bash
loopx history append-benchmark-run \
  --goal-id <goal-id> \
  --benchmark-run-json <benchmark-run-v0.json> \
  --classification benchmark_run_v0 \
  --recommended-action "inspect passive baseline pair and continue only after both modes are present" \
  --delivery-batch-scale implementation \
  --delivery-outcome primary_goal_outcome \
  --execute
```

The JSON object must already be public-safe and compactable. The append command
will compact it again before writing. This is a control-plane observation row,
not a benchmark submission.

## Stop Conditions

Stop before:

- invoking real Terminal-Bench, Harbor, Docker, Codex, cloud sandboxes, model
  APIs, or paid external compute from an automatic heartbeat;
- using a user or operator simulator;
- changing benchmark prompt, task, tests, timeout, resource, scoring, or upload
  behavior;
- claiming or implying official leaderboard uplift from this local fixture. Do
  not claim official leaderboard improvement from passive baseline control-plane
  evidence alone;
- copying raw session history, private docs, credentials, local user paths,
  internal identifiers, or raw runner logs into public artifacts.

## Current Smoke

The protocol smoke is:

```bash
python3 examples/passive-baseline-protocol-smoke.py
```

It writes two deterministic public-safe `benchmark_run_v0` fixtures, appends
them through the LoopX history CLI, and proves status can see two
benchmark rows without reading real runner output.

The broader local A/B capability smoke remains:

```bash
python3 examples/codex-cli-long-run-benchmark-smoke.py
```

That smoke emits `benchmark_result_v0` for with/without LoopX and keeps
both official-task scores equal while requiring a positive
`control_plane_score` delta.
