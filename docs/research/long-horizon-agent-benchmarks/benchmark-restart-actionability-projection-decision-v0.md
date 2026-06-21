# Benchmark Restart Actionability Projection Decision V0

Checked at: 2026-06-08T03:28:00+08:00.

## Decision

`benchmark_restart_actionability_v0` remains research/docs-only for now.

Do not project it into LoopX status, review-packet, project-asset, or
handoff hot paths until a real restarted-worker consumer needs the signal
outside this research folder, an approved no-submit setup check produces compact
public evidence, or repeated heartbeats show agents re-deriving the same
actionability boundary instead of reusing the artifact.

## Why

- The fixture is useful restartability evidence, but it is still fixture-only.
- The selected action is intentionally a local smoke command, not benchmark
  runner authorization, setup execution, official score evidence, or a
  leaderboard-adjacent result.
- The current active-state todo and research README already make the artifact
  findable for the next worker without adding another top-level status or
  review-packet field.
- The review-packet handoff JSON has narrow top-level headroom. Adding a
  projection now would spend scarce interface budget before proving a
  project-agent consumer exists.
- Keeping it docs-only avoids making a safe fixture command look like
  permission to run Terminal-Bench, Harbor, Docker, Codex/model APIs,
  cloud/paid compute, external evaluators, setup checks, or leaderboard paths.

## Projection Gate

Project it only if one of these happens:

- a restarted worker cannot reliably find or use the research artifact through
  the current active-state / research README handoff;
- an approved no-submit setup check or passive benchmark wrapper needs a compact
  actionability summary to avoid re-reading raw setup context;
- a report consumer needs the actionability decision to connect reconstructed
  history to a later public `benchmark_run_v0` / `benchmark_result_v0` row;
- repeated heartbeat turns re-create the same command/blocker boundary instead
  of reusing `benchmark-restart-actionability-v0.md`.

If the gate opens, project only a compact read-only shape:

- `schema_version`;
- `source_schema_version`;
- `readiness`;
- `authorization`;
- `replay_decision`;
- `next_run_mode`;
- `selected_action_kind`;
- `selected_action_allowed`;
- `selected_action_command_count`;
- `blocked_external_action_count`;
- `claim_boundary`;
- `stop_condition`.

Do not add raw commands, raw logs, private traces, host paths, local artifact
paths, task outputs, official scores, approval claims, runner output, setup
execution results, or leaderboard language.

## Boundary

No Terminal-Bench or Harbor runner execution, Docker, Codex/model API, cloud
sandbox, paid compute, external evaluator, private trace, raw runner log, local
artifact path, operator-approval claim, setup execution, or leaderboard path is
involved.

## Smoke

```bash
python3 examples/benchmark-restart-actionability-projection-decision-smoke.py
```
