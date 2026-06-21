# Terminal-Bench Runner Mode Contract V0

Checked at: 2026-06-08T18:48:19+08:00.

This note answers the core LoopX research runner-integration question for
`loopx benchmark run terminal-bench ...`: the current core comparison is
`codex-goal-mode` versus `codex-loopx`. The first arm is the true Codex
baseline for this LoopX experiment because it gives Codex its own goal
mode/runtime goal affordances but injects no LoopX state. The second arm
is the `Codex goal mode + LoopX` treatment.

This is a no-run contract. It does not run Harbor, Terminal-Bench, Docker,
Codex, model APIs, cloud sandboxes, paid compute, uploads, shares, or
leaderboard paths.

## Layers

| Layer | Meaning | May affect official task semantics |
| --- | --- | --- |
| Parent runner control plane | Select task slice, create run id, recheck quota/gates, invoke Harbor, ingest structured results, write compact LoopX history. | No |
| Codex goal-mode baseline | Run Codex with its native goal-mode affordance under the original benchmark task and no LoopX packet, skill, CLI bridge, or state. | Yes, to the extent Codex goal mode itself is part of the declared baseline surface |
| LoopX treatment worker | Give the same goal-capable Codex worker LoopX todo/state/checkpoint/replan surfaces and evaluate `Codex goal mode + LoopX` as the agent-harness pair. | Yes, as the core experimental mode |
| Hardened/bare calibration | Optional startup/install/environment control that withholds both Codex goal-mode instructions and LoopX state. | No |

The parent runner control plane may exist for all modes. The important
question is whether the benchmark case itself receives LoopX-managed
context or intervention.

## Modes

The future CLI should expose explicit modes:

```text
loopx benchmark run terminal-bench \
  --mode codex-goal-mode | codex-loopx
```

| Mode | Case worker | LoopX around case | LoopX inside case | Primary use |
| --- | --- | --- | --- | --- |
| `codex-goal-mode` | Codex worker runs with the same model/auth/env and the Codex native goal-mode surface declared by runner preflight. Access packet mode is `none`. | Parent runner only. | None. | True Codex baseline for this experiment. |
| `codex-loopx` | The same goal-mode Codex worker receives the LoopX access packet/bridge surface. | Parent runner plus managed checkpoints/writeback. | Yes: todo/state/checkpoint/replan may be available. | Core LoopX experiment: the `Codex goal mode + LoopX` agent-harness pair. |
| `hardened-codex` | Optional calibration worker with the same install/env but no Codex goal-mode instruction and no LoopX state. | Parent runner only. | None. | Startup/install/debug control only; not the primary baseline. |

`codex-goal-mode` is the right paired baseline because it asks whether Goal
Harness adds value beyond Codex's own long-running goal execution mode. The
runner must verify the local invocation surface before launching real work; if
the installed CLI exposes goal mode through config, interactive startup, or a
future flag rather than a literal `--goal` option, record that invocation in the
run preflight instead of inventing a command.

Current no-upload launch contract materializes the baseline through the Harbor
custom-agent import path with `loopx_mode=codex_goal_mode_baseline`,
`loopx_access_packet_mode=none`, no worker bridge, and
`codex_goal_mode_invocation_surface=slash_command`. The worker instruction starts
with Codex CLI `/goal`, then the original benchmark task instruction follows.
This is still a baseline arm: it must not read LoopX state or expose a
LoopX access packet inside the case.

`codex-loopx` is intentionally a different agent mode. It may
still use the benchmark's official verifier, but it must be reported as
`worker_mode=codex_loopx_cli` or equivalent. Its result is not a native
Codex CLI baseline.

## Why Not Keep Bare Codex

The old `bare-codex` path tested Harbor's native `--agent codex` startup
surface. It is no longer a primary baseline because the LoopX treatment
is supposed to compete with Codex's own goal-mode execution, not with an
underpowered no-goal worker. Comparing treatment against bare Codex would mix
native goal-mode value with LoopX value.

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
- no LoopX review-packet, active-state, todo, report, or checkpoint text
  injected into the benchmark task instruction;
- Codex goal-mode invocation captured in runner preflight;
- no upload, share, publish, or leaderboard flag unless a separate publication
  gate is explicitly opened;
- raw logs, raw Codex sessions, Docker logs, local paths, auth material, and
  task artifacts remain private.

For `codex-loopx`, each case must additionally record:

- `case_semantics_changed_by_harness=true`;
- the LoopX state surfaces available to the worker;
- intervention/checkpoint/replan counts;
- human or simulator intervention policy if present;
- claim boundary that this is a `model + harness` pair, not native Codex.

## Event Fields

Compact benchmark events should include these mode fields:

| Field | Example |
| --- | --- |
| `runner_control_plane` | `loopx_parent_runner` |
| `worker_mode` | `codex_goal_mode_baseline` or `codex_loopx_cli` |
| `case_semantics_changed_by_harness` | `false` for goal-mode baseline, `true` for treatment |
| `loopx_inside_case` | `false` for goal-mode baseline, `true` for treatment |
| `official_score_comparable_to_native_codex` | `false` for both current arms |
| `official_score_comparable_to_loopx_treatment` | `true` for the goal-mode baseline |
| `codex_goal_mode_enabled` | `true` for both primary arms |
| `control_plane_score_applicable` | `false` for goal-mode baseline, `true` for treatment |
| `leaderboard_evidence` | `false` until an explicit publication gate exists |

## Recommended Implementation Order

1. Implement the Codex goal-mode baseline no-run fixture, command envelope, and
   private no-upload launch summary.
2. Implement the `codex-loopx` worker bridge fixture and command
   envelope.
3. Implement the private no-upload runner wrapper with the two primary modes.
4. Run paired parallel hard-task experiments and compare score, closure,
   counters, and wall-time policy.

## Stop Conditions

Stop before:

- reintroducing `bare-codex` as a primary baseline;
- injecting LoopX state into a goal-mode baseline case;
- calling `codex-loopx` a native Codex baseline;
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
