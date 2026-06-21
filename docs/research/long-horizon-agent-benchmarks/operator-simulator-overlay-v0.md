# Operator-Simulator Overlay V0

Checked at: 2026-06-10T15:52:00+08:00.

This protocol defines the LoopX assisted operator-simulator overlay for
long-horizon benchmark research. It is not an official benchmark mode, not a
leaderboard claim, and not a replacement for the passive control-plane
baseline. It should start only after the passive baseline has produced a
credible positive or negative result.

## Purpose

The overlay studies supervised long-horizon execution: whether a bounded
simulated operator can improve restartability, stale-state avoidance, evidence
discipline, process-drift recovery, and continuation quality without acting as
an oracle. The assisted path should model a real user who may proactively
intervene, redirect, or push the worker, not only a passive reviewer waiting for
formal milestone submissions.

The default local contract schema is `operator_simulator_overlay_v0`. The
active intervention channel is `active_user_simulator_injection_v0`. A future
run should emit `operator_simulator_run_v0` rows and keep them separate from
official `benchmark_run_v0` and `benchmark_result_v0` rows.

## Comparison Modes

Report these modes separately:

- `official_or_native`: benchmark-native worker behavior with no LoopX
  policy changes and no simulated operator intervention.
- `passive_loopx_wrapper`: LoopX observes and writes control
  state, but the worker receives no operator-simulator guidance.
- `assisted_operator_simulator`: the worker may receive bounded proactive
  user-style interventions from the simulator under the visibility, frequency,
  and no-oracle rules below.

Never merge assisted-mode gains into official leaderboard scores.

## Active User Injection

The preferred first assisted path is active user injection. The simulator may
send a message even when the worker did not ask for help. Messages may be
directive, opinionated, and concrete, including strategy redirects, validation
ordering, or stop-current-path instructions. They do not need to be artificially
mild.

Control this mode through audit and frequency, not through weak wording:

- declare whether each message is proactive or worker-requested;
- cap total interventions and proactive interventions separately;
- require a minimum worker-event or time gap between proactive interventions;
- record the public-visible evidence basis used for the message;
- attach a no-oracle audit to every message;
- label any suspected oracle leak, overguidance, or simulator-induced failure.

Active injection is assisted collaboration evidence only. It may explain why an
agent recovered from a bad path, but it must not be reported as an official
benchmark-score improvement.

## Simulator Matrix

The first matrix should contain these simulator settings:

| Setting | Purpose |
| --- | --- |
| `deterministic_scripted_user` | Reproducibility and contract checks without model calls. |
| `same_family_simulator_agent` | Same model family for simulator and worker. |
| `stronger_simulator_weaker_agent` | Tests whether a stronger operator helps weaker workers. |
| `weaker_simulator_stronger_agent` | Tests whether weaker supervision adds noise. |
| `codex_worker_non_codex_simulator` | Tests cross-model supervision around Codex CLI. |
| `doubao2_simulator_or_worker` | Tests capability mismatch when Doubao 2.0 is available. |

The deterministic scripted user is the default smoke fixture. Model-backed
settings require explicit operator approval and must be reported as assisted
research, not official benchmark evidence.

## Visibility Limits

The simulator may see only:

- public task statement and benchmark-visible worker context;
- public-safe LoopX state summaries, todos, gates, review packets, and
  Goal Tick phases;
- validation output that the worker is allowed to inspect;
- public-safe artifact manifests and compact run summaries.

The simulator must not see hidden tests, expected solutions, benchmark answer
keys, private project material, credentials, raw transcript material, raw runner
logs, local host paths, or any state forbidden by the benchmark protocol.

## Intervention Budget

Every assisted run must declare an intervention budget:

- maximum simulator turns;
- maximum proactive simulator turns;
- maximum characters or tokens per intervention;
- minimum worker events or elapsed time between proactive interventions;
- allowed intervention types;
- whether the simulator may ask a clarifying question;
- stop condition after budget exhaustion.

Allowed intervention types are process-level only:

- `plan_approval`;
- `scope_clarification`;
- `active_user_instruction`;
- `strategy_redirection`;
- `continue_or_stop_after_failed_validation`;
- `validation_triage`;
- `process_drift_correction`;
- `evidence_request`;
- `handoff_quality_check`.

Forbidden intervention types include hidden-answer hints, hidden-oracle
solution steps, private-data lookup, direct code patches, tool execution on
behalf of the worker, and changes to benchmark prompts, tests, timeouts,
resources, scoring, or upload behavior.

## Failure Taxonomy

Assisted runs should label failures with one or more of:

- `simulator_oracle_leak`;
- `simulator_overguidance`;
- `simulator_underhelp`;
- `premature_stop`;
- `missed_process_drift`;
- `stale_state_reinforcement`;
- `ambiguity_injection`;
- `tool_state_mismatch`;
- `budget_exhaustion`;
- `model_capability_mismatch`;
- `policy_violation`;
- `intervention_latency`;
- `unsupported_runner_boundary`;
- `worker_ignored_valid_guidance`;
- `worker_overfit_to_guidance`.

## Output Contract

Each future assisted run should emit one compact `operator_simulator_run_v0`
row with:

- benchmark id, task id, mode, worker identity, simulator identity, and seed;
- simulator setting from the matrix above;
- visibility policy id and intervention budget;
- intervention count and allowed-type counts;
- proactive intervention count and frequency-budget audit;
- official task score reference, if a benchmark run exists;
- LoopX control-plane score reference;
- failure labels and simulator-induced error count;
- cost, wall-time, and extra-turn overhead;
- trace publicness and side-effect audit.

The row may link to official `benchmark_run_v0` rows, but it must never replace
or mutate official benchmark evidence.

## Default Smoke

The deterministic smoke is:

```bash
python3 examples/operator-simulator-overlay-smoke.py
```

It constructs a public-safe `operator_simulator_overlay_v0` plan and one
`operator_simulator_run_v0` scripted-user row. It performs no model call, no
benchmark run, no Docker or cloud sandbox use, no paid compute, and no
leaderboard upload.
