# Terminal-Bench Treatment Arm Taxonomy V0

Checked at: 2026-06-08T20:45:00+08:00.

This note fixes the treatment-arm naming after the first managed Codex sample
trace showed Codex runtime `create_goal` / `update_goal` calls. Those calls are
not Goal Harness CLI calls and must not be counted as evidence that the worker
used the Goal Harness registry, todo, status, quota, or history interfaces.

This is a no-run taxonomy note. It does not run Harbor, Terminal-Bench, Docker,
Codex, model APIs, uploads, shares, or leaderboard paths.

## Correct Arms

| Arm | Worker condition | Goal Harness inside case | Official score comparable to native Codex | Primary question |
| --- | --- | --- | --- | --- |
| `codex_goal_mode` | Codex CLI runs with the declared native goal-mode surface and no Goal Harness packet, skill, CLI bridge, or state. | No | No, unless the goal-mode prompt/tool surface is declared as native for that benchmark baseline. | Can Codex's own goal mode solve the same hard task without Goal Harness help? |
| `codex_goal_harness` | The same goal-mode Codex worker receives a Goal Harness access packet or skill plus real Goal Harness interfaces. Current V0 is only `prompt_packet_only_no_cli_bridge` until that bridge exists. | Yes, only after bridge/trace evidence | No | Does Goal Harness improve monitored long-horizon execution beyond Codex goal mode? |
| `hardened_codex_calibration` | The custom Codex install hardening receives the original benchmark task prompt unchanged and no Codex goal-mode instruction, Goal Harness packet, skill, CLI bridge, or state. | No | No; startup/install/debug control only. | Is a failure caused by install/startup/environment rather than goal-mode or Goal Harness behavior? |
| `passive_goal_harness_observer` | Native Codex solves the unchanged task while Goal Harness observes outside the case. | No | Yes | Can Goal Harness observe and write back evidence without perturbing the case? |

The old label `goal-harness-managed-codex` is too broad. It must be split into
at least `codex_goal_mode` and `codex_goal_harness` unless the worker trace
shows real Goal Harness interface use.

## Interaction Counters

Each real or fixture result should report these counters separately:

| Counter | Counts | Example |
| --- | --- | --- |
| `prompt_policy_injected` | A Goal Harness or goal-mode instruction packet was added to the task prompt. | `true` |
| `codex_runtime_goal_tool_calls` | Codex runtime goal tools, not Goal Harness APIs. | `create_goal=1`, `update_goal=1` |
| `goal_harness_cli_calls` | Calls to public Goal Harness CLI commands. | `status=1`, `todo=1`, `refresh_state=1` |
| `goal_harness_state_reads` | Reads of registry, active state, todo, history, or review packet through Goal Harness. | `2` |
| `goal_harness_state_writes` | Goal Harness writeback actions initiated from inside the worker. | `1` |
| `harness_skill_or_packet_injected` | Whether the worker received the Goal Harness access instructions. | `true` |
| `case_result_writeback` | Where the final compact result was written. | `runner_only` or `worker_goal_harness_writeback` |
| `codex_goal_mode_enabled` | Whether the arm used the declared Codex goal-mode invocation surface. | `true` for `codex_goal_mode` and `codex_goal_harness` |
| `primary_paired_baseline` | Whether the arm is the paired baseline for Goal Harness uplift analysis. | `true` for `codex_goal_mode` |
| `calibration_only` | Whether the arm is only a startup/install/environment control. | `true` for `hardened_codex_calibration` |

`codex_runtime_goal_tool_calls` is useful, but it is not Goal Harness usage.
For the first managed sample trace, the correct public-safe classification is:

```text
codex_runtime_goal_tool_calls=2
goal_harness_cli_calls=0
goal_harness_state_reads=0
goal_harness_state_writes=0
```

That trace can support a `codex_goal_mode` observation, not a claim that
`codex_goal_harness` was validated.

## Required Goal Harness Access Packet

The `codex_goal_harness` arm should inject a short access packet or skill at
the first worker query. While V0 has no CLI bridge, the packet must say
`goal_harness_interface_surface=prompt_packet_only_no_cli_bridge` and
`goal_harness_cli_bridge_available=false`. Once a bridge exists, the packet
should tell the worker:

- which Goal Harness mode is active;
- which CLI commands or wrapper interfaces are declared and actually available;
- when to call `status`, `todo`, `history`, `check`, or result writeback;
- how to keep private traces, credentials, local paths, and raw task artifacts
  out of public artifacts;
- how to report compact counters and blockers.

The packet should not force a hardcoded tool call. Codex should decide when to
use the interface, but the runner must count whether it actually did.

## Stop Conditions

Stop before:

- calling Codex runtime goal tools Goal Harness calls;
- treating prompt-policy-only or prompt-packet-only mode as validated
  `codex_goal_harness` interface use;
- mixing passive observer evidence with inside-case worker evidence;
- claiming leaderboard, paper, or uplift evidence from one sample;
- copying raw runner logs, raw Codex output, sessions, local paths,
  credentials, auth files, Docker logs, or task artifacts into public notes.

## Smoke

```bash
python3 examples/terminal-bench-treatment-arm-taxonomy-smoke.py
```

The smoke validates the arm split, counter semantics, public-safety boundary,
and the rule that `create_goal` / `update_goal` are Codex runtime goal-tool
calls unless a real Goal Harness interface was used.
