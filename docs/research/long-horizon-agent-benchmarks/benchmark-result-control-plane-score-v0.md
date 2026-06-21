# Benchmark Result Control-Plane Score V0

Checked at: 2026-06-08T00:05:00+08:00

## Purpose

`benchmark_result_v0` keeps benchmark-native task success separate from Goal
Harness coordination value. The native score belongs in `official_task_score`.
LoopX-specific value belongs in `control_plane_score` and must not be
presented as official benchmark or leaderboard uplift.

This document defines the minimal public `control_plane_score_core_v0` schema
used by the deterministic `mini_control_plane_repair_v0` fixture. It is small
on purpose: add new required dimensions only after a fixture or official runner
probe proves that the missing dimension changes a decision.

## Score Shape

`benchmark_result_v0.control_plane_score` uses:

| Field | Rule |
| --- | --- |
| `schema_version` | `control_plane_score_core_v0`. |
| `kind` | `core_v0`. |
| `aggregation` | `unweighted_mean`. |
| `components` | Object containing exactly the eight core components below. |
| `component_order` | The same eight component ids, in stable display order. |
| `value` | Mean of component values, rounded to three decimals. |

Each component is normalized to `0.0..1.0`; `1.0` means that dimension is
clean for the current public fixture.

## Core Components

| Component | Meaning |
| --- | --- |
| `restartability` | Another worker can reconstruct current task state from public artifacts or events. |
| `stale_state_avoidance` | The worker did not trust stale latest-run or stale todo text over current state. |
| `evidence_discipline` | Validation evidence exists and the successful run has no unhandled validation failure. |
| `boundary_safety` | The run did not touch forbidden private fixture surfaces. |
| `writeback_quality` | LoopX mode wrote enough durable state/events to continue. |
| `gate_compliance` | Owner-only or human-gated todo text remained preserved. |
| `failure_attribution` | Failures or stalls have compact labels, and successful runs are attribution-clean. |
| `overhead` | Coordination overhead stayed bounded and no quota spend happened before validation. |

## Claim Boundary

- `official_task_score` answers whether the benchmark task passed.
- `control_plane_score` answers whether LoopX improved coordination,
  recovery, evidence, and governance around that task.
- A positive `control_plane_score` delta is not an official leaderboard claim.
- Real Terminal-Bench, Harbor, Docker, Codex/model API, cloud, paid compute, or
  leaderboard paths require explicit operator approval.

## Verifier Attribution Routing

`benchmark_verifier_attribution_review_v0` is a compact-only review over
`benchmark_run_v0` rows. It does not open raw verifier logs, task text,
trajectories, Harbor job directories, Docker, model APIs, or upload paths.

The review keeps human-readable `decision` fields and also emits a
machine-readable `routing` object:

| Field | Meaning |
| --- | --- |
| `treatment_eligible` | A treatment run may proceed because the baseline failure is not a verifier/platform caveat. |
| `repeat_allowed` | The same task may be repeated under the current protocol. |
| `new_candidate_allowed` | The runner may move to another material-ready hard case. |
| `requires_verifier_preflight_repair` | The baseline compact labels indicate verifier dependency/platform repair or finer compact verifier evidence is needed before same-task repeat. |
| `blocked_action_scope` | Which action class is blocked, for example `treatment_and_same_task_repeat`. |
| `next_allowed_action` | Stable action token for automation, such as `repair_verifier_preflight_or_select_new_material_ready_case`. |

This routing prevents a failed baseline caused by verifier dependency or
platform setup from being misread as a LoopX treatment opportunity.

## Smoke

The deterministic fixture is:

```bash
python3 examples/codex-cli-long-run-benchmark-smoke.py
python3 examples/benchmark-claim-review-smoke.py
```

The smoke verifies that with/without LoopX results keep
`official_task_score_delta == 0.0` while the with-harness path has a higher
`control_plane_score.value`. The claim-review smoke also verifies verifier
attribution routing for treatment, repeat, and new-candidate decisions.
