# Mini Control Plane Interrupt Comparison Summary V0

Checked at: 2026-06-08T02:36:00+08:00

## Purpose

`benchmark_interrupt_comparison_summary_v0` is a compact research summary that
compares the existing non-interrupt `mini_control_plane_repair_v0` fixture with
the interrupt/recovery `mini_control_plane_repair_with_interrupt_v0` fixture.

The summary exists to make the control-plane evidence readable without adding a
new CLI command, status field, or benchmark runner path. It is a fixture-only
artifact for deciding whether this interrupt evidence should later be projected
through status or review packets.

## Summary Fields

- `official_task_score_delta`: remains separate from control-plane evidence and
  should stay zero for this local deterministic pair.
- `control_plane_score_delta`: compares the local
  `control_plane_score_core_v0` values between the non-interrupt and interrupt
  fixture modes.
- `control_plane_component_deltas`: shows which components changed under
  interrupt pressure.
- `restart_resume_evidence`: records interrupt events, resume-after-recheck,
  first failed phase, side-effect audit, and spend-after-validation discipline.
- `failure_attribution`: records new labels introduced by the interrupt slice,
  especially validation pressure.
- `overhead`: compares wall time, writeback count, spend count, and validation
  failures.
- `claim_boundary`: states what the local fixture may and must not claim.

## Interpretation

The useful signal is not an official score uplift. The useful signal is that the
same local task can succeed while LoopX records the interruption,
stale-state trap, validation failure, human-gate resume recheck, side-effect
audit, and spend discipline as separate control-plane evidence.

If this summary becomes useful for project agents, the next product step should
be a compact status or review-packet projection. If not, it should remain a
research artifact and avoid expanding the hot-path interface.

## Boundary

No real benchmark runner, Terminal-Bench, Harbor, Docker/cloud runner,
Codex/model API, paid compute, private trace, raw benchmark log, local artifact
path, model-backed simulator, or leaderboard claim is involved.

## Smoke

```bash
python3 examples/mini-control-plane-interrupt-comparison-summary-smoke.py
```
