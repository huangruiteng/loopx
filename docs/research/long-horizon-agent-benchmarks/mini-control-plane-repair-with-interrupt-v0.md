# Mini Control Plane Repair With Interrupt V0

Checked at: 2026-06-08T02:18:00+08:00

## Purpose

`mini_control_plane_repair_with_interrupt_v0` is the deterministic recovery
slice for the local LoopX benchmark program. It keeps the same
implementation puzzle as `mini_control_plane_repair_v0`, but adds controlled
long-horizon failure pressure around the worker instead of making the coding
task harder.

The slice exists to prove LoopX control-plane value before any real
Terminal-Bench, Harbor, Docker, Codex/model API, cloud, paid-compute, private
trace, raw benchmark log, local artifact path, or leaderboard path is used.

## Fixture Events

The targeted smoke exercises four public-safe events:

| Event | Control-Plane Value |
| --- | --- |
| `worker_kill_after_partial_goal_tick_writeback` | A later worker can resume from a public partial Goal Tick artifact. |
| `stale_latest_run_trap` | Current active state and Agent Todo beat stale latest-run prose. |
| `forced_validation_failure_before_success` | The report preserves the first failed phase instead of hiding the failed validation. |
| `human_gate_resume_after_state_policy_quota_authority_recheck` | Resume applies only after state, policy, quota, and authority are reread. |

## Result Shape

The compact report slice uses `schema_version =
mini_control_plane_repair_with_interrupt_v0` and carries:

- `official_task_score`: deterministic task pass/fail for the local fixture;
- `control_plane_score`: `control_plane_score_core_v0`, kept separate from
  official score;
- `interrupt_events`: the ordered recovery pressure events;
- `first_failed_phase`: expected to be `validate`;
- `resume_decision_applied_after_recheck`: expected to be true;
- `side_effect_audit_passed`: expected to be true;
- `failure_attribution_labels`: must include `validation`;
- `spend_count` and `spend_before_validation_count`: spend happens once after
  validation and writeback, never before validation.

## Boundary

No real benchmark runner, model-backed simulator, Docker/cloud runner, private
trace, raw benchmark log, local artifact path, or leaderboard claim is involved.
The fixture is a local deterministic smoke that validates restartability,
stale-state avoidance, evidence discipline, gate compliance, side-effect audit,
and failure attribution.

## Smoke

```bash
python3 examples/mini-control-plane-repair-with-interrupt-smoke.py
```
