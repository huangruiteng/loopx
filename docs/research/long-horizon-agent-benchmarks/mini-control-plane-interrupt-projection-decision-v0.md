# Mini Control Plane Interrupt Projection Decision V0

Checked at: 2026-06-08T02:41:00+08:00

## Decision

`benchmark_interrupt_comparison_summary_v0` remains research-only for now.

Do not project it into LoopX status or review-packet hot paths until a
project agent actually needs the signal outside the research folder, or until a
real passive benchmark run produces comparable interrupt/recovery evidence.

## Why

- The summary is useful evidence, but it is still fixture-only.
- The current hot-path review-packet handoff JSON has narrow remaining field
  headroom, so adding a new top-level projection would increase interface
  pressure without a demonstrated consumer.
- The existing artifact already preserves the key signal: official score delta,
  control-plane delta, restart/resume evidence, validation attribution, overhead,
  and claim boundary.
- Keeping it research-only reduces control-plane complexity while retaining a
  clear upgrade path.

## Projection Gate

Project it only if one of these happens:

- a project agent cannot reliably find or use the research artifact through the
  current handoff chain;
- a real no-submit runner output or passive benchmark run needs the same
  interrupt summary shape;
- repeated heartbeats show agents re-deriving the same interrupt comparison
  instead of reusing this artifact.

If the gate opens, project only a compact read-only shape:

- `schema_version`;
- `official_task_score_delta`;
- `control_plane_score_delta`;
- `restart_resume_evidence`;
- `failure_attribution`;
- `claim_boundary`.

Do not add raw rows, changed files, private traces, local paths, benchmark logs,
or leaderboard language.

## Boundary

No real benchmark runner, Terminal-Bench, Harbor, Docker/cloud runner,
Codex/model API, paid compute, private trace, raw benchmark log, local artifact
path, model-backed simulator, or leaderboard claim is involved.

## Smoke

```bash
python3 examples/mini-control-plane-interrupt-projection-decision-smoke.py
```
