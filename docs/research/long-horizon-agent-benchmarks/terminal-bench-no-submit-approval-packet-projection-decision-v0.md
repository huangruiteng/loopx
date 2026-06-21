# Terminal-Bench No-Submit Approval Packet Projection Decision V0

Checked at: 2026-06-08T02:56:00+08:00.

## Decision

`terminal_bench_no_submit_approval_packet_v0` remains research/docs-only for
now.

Do not project it into LoopX status, review-packet, or project-asset
handoff hot paths until a real agent consumer needs the packet outside this
research folder, an approved no-submit setup check produces compact public
evidence, or repeated heartbeats show agents re-deriving the same gate boundary.

## Why

- The packet is an operator gate artifact, not runner output or benchmark
  evidence.
- The packet's current state is intentionally non-executable:
  `approval_state=requested`, `execution_authorized=false`,
  `submit_eligible=false`, and `real_run=false`.
- The current review-packet handoff JSON has only narrow top-level field
  headroom. Adding another projection would spend scarce interface budget before
  proving a project-agent consumer exists.
- The research artifact already preserves the practical signal: exact candidate
  command shapes, forbidden surfaces, side-effect budget, expected public
  artifacts, stop conditions, and compact `benchmark_run_v0` /
  `benchmark_result_v0` ingestion rules.
- Keeping it docs-only avoids making an unapproved future setup check look like
  a delivery approval, runner result, or leaderboard-adjacent signal.

## Projection Gate

Project it only if one of these happens:

- a project agent cannot reliably find or use the packet through the current
  handoff chain;
- the operator explicitly approves a no-submit setup check and compact public
  evidence needs to enter run history;
- a passive benchmark wrapper or report consumer needs a compact approval-boundary
  summary to avoid mixing readiness evidence with official score evidence;
- repeated heartbeat turns re-create the same command/forbidden-surface list
  instead of reusing this artifact.

If the gate opens, project only a compact read-only shape:

- `schema_version`;
- `approval_state`;
- `execution_authorized`;
- `submit_eligible`;
- `real_run`;
- `candidate_command_count`;
- `forbidden_surface_count`;
- `expected_public_artifact_count`;
- `claim_boundary`;
- `next_required_operator_action`.

Do not add raw commands, raw logs, private traces, host paths, local artifact
paths, task outputs, official scores, approval claims, runner output, or
leaderboard language.

## Boundary

No Terminal-Bench or Harbor runner execution, Docker, Codex/model API,
cloud sandbox, paid compute, private trace, raw runner log, local artifact
path, operator-approval claim, setup execution, or leaderboard path is involved.

## Smoke

```bash
python3 examples/terminal-bench-no-submit-approval-packet-projection-decision-smoke.py
```
