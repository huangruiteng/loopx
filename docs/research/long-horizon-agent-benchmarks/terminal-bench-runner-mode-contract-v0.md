# Terminal-Bench Runner Mode Contract V0

Checked at: 2026-06-08T18:48:19+08:00.

This note answers the core Goal Harness research runner-integration question for
`goal-harness benchmark run terminal-bench ...`: the current core comparison is
`codex-goal-mode` versus `codex-goal-harness`. The first arm is the true Codex
baseline for this Goal Harness experiment because it gives Codex its own goal
mode/runtime goal affordances but injects no Goal Harness state. The second arm
is the `Codex goal mode + Goal Harness` treatment.

This is a no-run contract. It does not run Harbor, Terminal-Bench, Docker,
Codex, model APIs, cloud sandboxes, paid compute, uploads, shares, or
leaderboard paths.

## Layers

| Layer | Meaning | May affect official task semantics |
| --- | --- | --- |
| Parent runner control plane | Select task slice, create run id, recheck quota/gates, invoke Harbor, ingest structured results, write compact Goal Harness history. | No |
| Codex goal-mode baseline | Run Codex with its native goal-mode affordance under the original benchmark task and no Goal Harness packet, skill, CLI bridge, or state. | Yes, to the extent Codex goal mode itself is part of the declared baseline surface |
| Goal Harness treatment worker | Give the same goal-capable Codex worker Goal Harness todo/state/checkpoint/replan surfaces and evaluate `Codex goal mode + Goal Harness` as the agent-harness pair. | Yes, as the core experimental mode |
| Hardened/bare calibration | Optional startup/install/environment control that withholds both Codex goal-mode instructions and Goal Harness state. | No |

The parent runner control plane may exist for all modes. The important
question is whether the benchmark case itself receives Goal Harness-managed
context or intervention.

## Modes

The future CLI should expose explicit modes:

```text
goal-harness benchmark run terminal-bench \
  --mode codex-goal-mode | codex-goal-harness
```

| Mode | Case worker | Goal Harness around case | Goal Harness inside case | Primary use |
| --- | --- | --- | --- | --- |
| `codex-goal-mode` | Codex worker runs with the same model/auth/env and the Codex native goal-mode surface declared by runner preflight. Access packet mode is `none`. | Parent runner only. | None. | True Codex baseline for this experiment. |
| `codex-goal-harness` | The same goal-mode Codex worker receives the Goal Harness access packet/bridge surface. | Parent runner plus managed checkpoints/writeback. | Yes: todo/state/checkpoint/replan may be available. | Core Goal Harness experiment: the `Codex goal mode + Goal Harness` agent-harness pair. |
| `hardened-codex` | Optional calibration worker with the same install/env but no Codex goal-mode instruction and no Goal Harness state. | Parent runner only. | None. | Startup/install/debug control only; not the primary baseline. |

`codex-goal-mode` is the right paired baseline because it asks whether Goal
Harness adds value beyond Codex's own long-running goal execution mode. The
runner must verify the local invocation surface before launching real work; if
the installed CLI exposes goal mode through config, interactive startup, or a
future flag rather than a literal `--goal` option, record that invocation in the
run preflight instead of inventing a command.

`codex-goal-harness` is intentionally a different agent mode. It may
still use the benchmark's official verifier, but it must be reported as
`worker_mode=codex_goal_harness_cli` or equivalent. Its result is not a native
Codex CLI baseline.

## Why Not Keep Bare Codex

The old `bare-codex` path tested Harbor's native `--agent codex` startup
surface. It is no longer a primary baseline because the Goal Harness treatment
is supposed to compete with Codex's own goal-mode execution, not with an
underpowered no-goal worker. Comparing treatment against bare Codex would mix
native goal-mode value with Goal Harness value.

Keep native/bare evidence only as legacy startup debugging if an existing run
already produced it. Do not launch it as part of the current main protocol.

Run both arms in parallel on the same selected hard task whenever resources
allow. That makes task drift, verifier drift, and runner conditions easier to
compare.

## Per-Case Invariants

For `codex-goal-mode`, each case must preserve:

- benchmark task prompt unchanged;
- tests, scoring, resources, timeout, dataset, and runner source unchanged;
- same model, auth strategy, and hardened install strategy unless an ablation
  field records the change;
- no Goal Harness review-packet, active-state, todo, report, or checkpoint text
  injected into the benchmark task instruction;
- Codex goal-mode invocation captured in runner preflight;
- no upload, share, publish, or leaderboard flag unless a separate publication
  gate is explicitly opened;
- raw logs, raw Codex sessions, Docker logs, local paths, auth material, and
  task artifacts remain private.

For `codex-goal-harness`, each case must additionally record:

- `case_semantics_changed_by_harness=true`;
- the Goal Harness state surfaces available to the worker;
- intervention/checkpoint/replan counts;
- human or simulator intervention policy if present;
- claim boundary that this is a `model + harness` pair, not native Codex.

## Event Fields

Compact benchmark events should include these mode fields:

| Field | Example |
| --- | --- |
| `runner_control_plane` | `goal_harness_parent_runner` |
| `worker_mode` | `codex_goal_mode_baseline` or `codex_goal_harness_cli` |
| `case_semantics_changed_by_harness` | `false` for goal-mode baseline, `true` for treatment |
| `goal_harness_inside_case` | `false` for goal-mode baseline, `true` for treatment |
| `official_score_comparable_to_native_codex` | `false` for both current arms |
| `official_score_comparable_to_goal_harness_treatment` | `true` for the goal-mode baseline |
| `codex_goal_mode_enabled` | `true` for both primary arms |
| `control_plane_score_applicable` | `false` for goal-mode baseline, `true` for treatment |
| `leaderboard_evidence` | `false` until an explicit publication gate exists |

## Recommended Implementation Order

1. Implement the Codex goal-mode baseline no-run fixture and command envelope.
2. Implement the `codex-goal-harness` worker bridge fixture and command
   envelope.
3. Implement the private no-upload runner wrapper with the two primary modes.
4. Run paired parallel hard-task experiments and compare score, closure,
   counters, and wall-time policy.

## Stop Conditions

Stop before:

- reintroducing `bare-codex` as a primary baseline;
- injecting Goal Harness state into a goal-mode baseline case;
- calling `codex-goal-harness` a native Codex baseline;
- running full `terminal-bench@2.0`;
- adding upload/share/leaderboard behavior;
- copying credentials, raw logs, raw sessions, Docker logs, host paths, or task
  artifacts into public artifacts;
- claiming official leaderboard uplift, benchmark pass/fail improvement, or
  paper-ready evidence from this contract.

## Smoke

```bash
python3 examples/terminal-bench-runner-mode-contract-smoke.py
```

The smoke validates the document, constructs the mode contract payload, checks
the per-mode semantics flags, and proves the contract remains public-safe and
no-run/no-submit.
