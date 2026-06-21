# Benchmark Report Chain Map V0

Checked at: 2026-06-08T01:45:00+08:00.

This map is the compact reviewer handoff for the deterministic benchmark
reporting pipeline. It ties the existing fixture-backed event and consumer
schemas into one chain so a future worker can continue from current evidence
without rereading every design note.

It is not a benchmark result, runner setup guide, submission plan, or new status
schema. It only names the existing public-safe reporting order and the minimum
handoff fields that should be visible before any larger pilot is considered.

## Chain Order

The chain should be read in this order:

1. `benchmark_run_v0`: one compact run row per benchmark mode or fixture mode.
2. `benchmark_result_v0`: the native task-score and control-plane score shell
   for one scenario or comparison slice.
3. `benchmark_comparison_v0`: the paired baseline/treatment comparison with
   separate official-score and control-plane deltas.
4. `benchmark_comparison_decision_note_v0`: a derived claim-boundary and
   next-decision hint from the comparison summary.
5. `benchmark_experiment_report_v0`: the report surface that keeps official
   score, passive control-plane score, assisted-mode state, overhead, failures,
   reproducibility, claim boundary, negative results, and next decision apart.
6. `benchmark_experiment_report_readiness_note_v0`: a derived readiness and
   authorization hint from the compact report summary.
7. `benchmark_experiment_report_replay_decision_v0`: the smallest next-run
   decision for fixture replay, operator review, or deferral.

## Reviewer Handoff Fields

A compact handoff should expose these fields before a worker decides what to do
next:

| Field | Meaning |
| --- | --- |
| `official_score` | Whether benchmark-native score evidence exists and whether it is eligible for official comparison. |
| `control_plane_score` | Whether LoopX coordination evidence exists and which dimensions it supports. |
| `readiness` | Whether the current report is readiness-only, control-plane-only, failure-analysis, or candidate official evidence. |
| `authorization` | Whether the next action is fixture-only, operator-review, no-submit setup, or deferred. |
| `replay_decision` | Whether to replay a fixture, request review, defer, or stop. |
| `next_run_mode` | The next allowed run mode, if any, expressed without private runner state. |
| `negative_evidence_layers` | The evidence layers that currently block stronger claims. |
| `must_not_claim` | Claims the current evidence cannot support. |
| `stop_condition` | The condition that prevents the next worker from escalating scope. |

## Boundaries

This chain map is limited to fixture, status, and review-packet contracts. It
must not:

- run a real benchmark;
- invoke Docker, cloud sandboxes, paid compute, Codex, model APIs, or simulator
  workers;
- read hidden tests, expected solutions, private traces, raw runner logs,
  local artifact paths, or raw session records;
- upload, submit, or claim leaderboard evidence;
- replace the benchmark's native scoring protocol;
- create a new approval path for external execution.

## Acceptance

The chain is acceptable when:

- the seven schema nodes above appear in order;
- README and roadmap surfaces link this map as the reviewer-facing
  consolidation point;
- the status contract names the map as an explanatory handoff, not a new event;
- smoke coverage proves the map has the required fields and boundary clauses;
- missing fields lead to a contract or fixture repair, not to real benchmark
  execution.
