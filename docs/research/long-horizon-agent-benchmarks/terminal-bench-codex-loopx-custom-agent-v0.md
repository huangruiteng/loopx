# Terminal-Bench Codex LoopX Custom Agent V0

Checked at: 2026-06-08T21:12:00+08:00.

This note records the first custom-agent prompt surface for the requested
`codex_loopx` treatment arm. The default V0 path is prompt-packet only:
it changes the worker prompt and records counter semantics. The active bridge
follow-up is recorded separately in
`terminal-bench-codex-loopx-active-cli-bridge-v0.md`; it adds
`loopx_cli_bridge_enabled=true` so the Codex worker receives concrete
LoopX CLI command templates. The Harbor import path remains:

```text
loopx.terminal_bench_agent:GoalHarnessManagedCodex
```

The new mode is selected through an agent kwarg:

```text
loopx_mode=codex_loopx
```

This is still no-run/no-submit validation. It does not run Harbor,
Terminal-Bench, Docker, real Codex workers, model APIs, uploads, shares, or
leaderboard paths.

## Prompt Surface

When `loopx_mode=codex_loopx`, the custom agent injects:

```text
----- GOAL-HARNESS ACCESS PACKET -----
LoopX Access Packet V0
mode: codex_loopx
loopx_interface_surface: prompt_packet_only_no_cli_bridge
loopx_cli_bridge_available: false
loopx_cli_bridge_contract: terminal_bench_loopx_cli_bridge_contract_v0
declared_loopx_interface_commands: status, quota_should_run, todo_list, history, check, append_benchmark_run
count_codex_runtime_goal_tools_separately_from_loopx_calls: true
do_not_claim_loopx_cli_calls_without_bridge_or_trace: true
report_interaction_counters_after_the_case: true
----- END GOAL-HARNESS ACCESS PACKET -----
```

The raw prompt is not recorded in public artifacts. The adapter records only
compact booleans, schema ids, prompt length, and task hash metadata.

## Counter Extraction

The custom agent now exposes
`extract_loopx_interaction_counters_from_trace()`. It accepts compact
public trace rows such as:

```text
loopx_cli_call/status
loopx_cli_call/quota_should_run
loopx_state_read
loopx_state_write
case_result_writeback/worker_loopx_writeback
```

It produces `terminal_bench_loopx_interaction_counters_v0` while keeping
Codex runtime goal tools separate from LoopX CLI calls:

```text
codex_runtime_goal_tool_calls.total
loopx_cli_calls.total
loopx_state_reads
loopx_state_writes
case_result_writeback
counter_trust_level=compact_trace_audited
raw_trace_recorded=false
raw_task_prompt_recorded=false
```

If no compact trace is available, the adapter records
`counter_trust_level=runtime_metadata_prompt_only_no_cli_bridge` for
`codex_loopx` prompt-only runs instead of inventing calls.

## Harbor Command Shape

The command preview for `codex-loopx` includes:

```text
--agent-kwarg loopx_mode=codex_loopx
--agent-kwarg loopx_goal_id=<goal-id>
```

This gives the real Harbor custom-agent path the same treatment-arm identity as
the no-run fake-worker fixture, without making official-score or uplift claims.

## Claim Boundary

This slice may claim:

```text
The Harbor custom-agent prompt can carry a prompt-only LoopX access packet
and compact interaction-counter extraction contract for codex_loopx mode.
```

It must not claim:

- a real benchmark task ran;
- a real worker used LoopX interfaces;
- a LoopX CLI bridge was available unless
  `loopx_cli_bridge_enabled=true` and worker-side compact trace counters
  are present;
- official task success;
- cost or token improvement;
- leaderboard readiness;
- LoopX uplift.

## Smoke

```bash
python3 examples/terminal-bench-codex-loopx-custom-agent-smoke.py
```

The smoke uses fake Harbor modules, validates packet injection, verifies compact
counter extraction from public trace rows, and confirms the Harbor command
preview carries `loopx_mode=codex_loopx`.
