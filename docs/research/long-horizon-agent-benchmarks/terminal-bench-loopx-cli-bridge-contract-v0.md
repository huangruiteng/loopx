# Terminal-Bench LoopX CLI Bridge Contract V0

Checked at: 2026-06-08T23:06:00+08:00.

This note defines the first host-agent LoopX CLI bridge contract for the
requested `codex_loopx` arm. It is still no-run/no-submit: it does not
run Harbor, Terminal-Bench tasks, Docker task containers, Codex workers, model
APIs, uploads, shares, paid/cloud execution, or leaderboard paths.

The contract exists to move the next implementation step from prose to an
executable mapping. Current access-packet V0 remains
`prompt_packet_only_no_cli_bridge`; this bridge contract describes the exact CLI
surface that must become available before a real `codex_loopx` run can
claim LoopX interface use.

## Contract Shape

`loopx.benchmark.build_terminal_bench_loopx_cli_bridge_contract`
returns:

```text
schema_version=terminal_bench_loopx_cli_bridge_contract_v0
bridge_surface=host_agent_loopx_cli_bridge_v0
bridge_available=false
logical_commands=status, quota_should_run, todo_list, history, check, append_benchmark_run
```

The public fixture uses placeholders only:

```text
goal_id=<goal-id>
registry_arg=<registry>
runtime_root_arg=<runtime-root>
scan_path=<public-scan-path>
benchmark_run_json=<benchmark-run-v0.json>
classification=<classification>
```

The executable smoke substitutes temporary local paths, runs the command
templates, and keeps those paths out of public docs.

## Runner Fixture Surface

`loopx benchmark run terminal-bench --mode codex-loopx
--cli-bridge-contract` now wires the contract into the benchmark runner fixture.
This path still does not execute a Terminal-Bench task or Codex worker. It runs
the six LoopX CLI logical mappings on the host agent and records only the
compact public-safe result:

```text
mode=codex_loopx_cli_bridge_contract_fixture
loopx_cli_bridge_contract_available=true
loopx_cli_bridge_trace_observed=true
loopx_cli_bridge_scope=host_agent_runner_fixture_no_terminal_bench_worker
loopx_cli_calls.total=6
loopx_state_reads=5
loopx_state_writes=0
case_result_writeback=bridge_append_benchmark_run_dry_run
counter_trust_level=runner_bridge_contract_fixture_observed
```

This deliberately keeps `loopx_cli_bridge_available` for the worker case
separate from `loopx_cli_bridge_contract_available` for the host runner
fixture. The former remains false until the bridge is actually exposed inside a
Terminal-Bench worker run.

## Logical Command Mapping

| Logical command | CLI mapping |
| --- | --- |
| `status` | `loopx --format json --registry <registry> --runtime-root <runtime-root> status --limit 5` |
| `quota_should_run` | `loopx --format json --registry <registry> --runtime-root <runtime-root> quota should-run --goal-id <goal-id>` |
| `todo_list` | Same `quota should-run` call, reading `user_todo_summary` and `agent_todo_summary`, until a dedicated todo-list read command exists. |
| `history` | `loopx --format json --registry <registry> --runtime-root <runtime-root> history --goal-id <goal-id> --limit 5` |
| `check` | `loopx --format json --registry <registry> --runtime-root <runtime-root> check --scan-path <public-scan-path>` |
| `append_benchmark_run` | `loopx --format json --registry <registry> --runtime-root <runtime-root> history append-benchmark-run --goal-id <goal-id> --benchmark-run-json <benchmark-run-v0.json> --classification <classification> --dry-run` |

`append_benchmark_run` is dry-run in the bridge fixture. A real bridge may add
`--execute` only after the worker has validated the case result, the
no-upload/public-boundary checks pass, and the runner is ready to emit compact
trace rows.

## Enable Conditions

The contract may flip `loopx_cli_bridge_available` from `false` to `true`
only when all of these are true:

- the LoopX CLI is importable or present on the agent host `PATH`;
- the registry and runtime root are mounted for the agent-host bridge;
- read commands can return compact JSON without raw private paths in public
  artifacts;
- write commands are gated by validation and no-upload boundary checks;
- every logical bridge call emits a compact trace row that can feed
  `loopx_cli_calls`, `loopx_state_reads`, and
  `loopx_state_writes`.

## Stop Conditions

Stop before:

- treating this contract as a real Terminal-Bench or Codex run;
- claiming official task score, cost/token improvement, leaderboard readiness,
  or uplift from the bridge fixture;
- exposing raw registry paths, runtime paths, sessions, task prompts, task
  artifacts, logs, credentials, or auth files in public docs;
- enabling `--execute` writeback in a worker bridge without validation and
  no-upload checks.

## Smoke

```bash
python3 examples/terminal-bench-loopx-cli-bridge-contract-smoke.py
python3 examples/terminal-bench-loopx-cli-bridge-runner-smoke.py
```

The smoke validates the public contract, executes the six logical CLI mappings
against a temporary local LoopX registry, builds compact interaction
counters, verifies the `benchmark run terminal-bench --cli-bridge-contract`
runner projection, and confirms the bridge fixture remains no-run/no-submit.
