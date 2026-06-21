# Terminal-Bench LoopX Access Packet V0

Checked at: 2026-06-08T20:55:00+08:00.

This note defines the first no-run access packet for the requested
`codex_loopx` treatment arm. It exists because Codex runtime
`create_goal` / `update_goal` calls are not LoopX calls. Current V0 is
truthfully classified as `prompt_packet_only_no_cli_bridge`: the worker can
receive LoopX instructions, but Terminal-Bench does not yet expose a
callable LoopX CLI bridge inside the case. A later true interface arm
must prove bridge availability and actual LoopX interactions separately
from Codex runtime goal tools.

This is a fixture and schema slice only. It does not run Harbor,
Terminal-Bench, Docker, Codex workers, model APIs, uploads, shares, or
leaderboard paths.

## Packet Template

The worker packet is intentionally short and public-safe:

```text
LoopX Access Packet V0
mode: codex_loopx
goal_id: <goal-id>
loopx_interface_surface: prompt_packet_only_no_cli_bridge
loopx_cli_bridge_available: false
loopx_cli_bridge_contract: terminal_bench_loopx_cli_bridge_contract_v0
declared_loopx_interface_commands: status, quota_should_run, todo_list, history, check, append_benchmark_run
if_cli_bridge_available_use_lean_check_and_final_append_policy: true
status_quota_todo_history_are_optional_blocked_or_resume_calls: true
write_compact_case_result_through_loopx_when_bridge_available: true
loopx_cli_bridge_command_templates_require_placeholder_substitution: true
do_not_execute_loopx_cli_command_with_unresolved_angle_bracket_placeholders: true
do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true
count_codex_runtime_goal_tools_separately_from_loopx_calls: true
do_not_claim_loopx_cli_calls_without_bridge_or_trace: true
do_not_record_private_paths_credentials_raw_sessions_or_raw_task_logs: true
do_not_require_a_hardcoded_tool_call_before_reasoning: true
report_interaction_counters_after_the_case: true
```

The packet tells Codex the declared LoopX command vocabulary and the
current bridge boundary. It does not force a hardcoded call before reasoning.
The runner still needs to count what the worker actually called, and zero
LoopX CLI calls must remain zero until a bridge or trusted compact trace
exists. When a bridge is available, command strings are templates: the worker
must substitute placeholders before execution, quote substituted path values or
use argv execution, and reserve `append_benchmark_run` for final validation,
cleanup, or terminal-blocker writeback.

The referenced bridge contract is
`terminal-bench-loopx-cli-bridge-contract-v0.md`; it is executable as a
host-agent CLI fixture, but it does not make this prompt packet a real
Terminal-Bench worker bridge by itself.

## Interaction Counters

Every `codex_loopx` fixture or real result should include:

| Field | Meaning |
| --- | --- |
| `prompt_policy_injected` | A worker policy packet was added. |
| `harness_skill_or_packet_injected` | The packet or equivalent skill was actually given to the worker. |
| `codex_runtime_goal_tool_calls` | Codex runtime tools such as `create_goal` and `update_goal`. |
| `loopx_cli_calls` | LoopX CLI or wrapper calls such as `status`, `history`, `check`, or compact writeback. |
| `loopx_state_reads` | Reads of LoopX registry, active state, todo, history, or status surfaces. |
| `loopx_state_writes` | LoopX writeback actions from inside the worker. |
| `case_result_writeback` | Whether the worker wrote a compact LoopX result or only the runner did. |
| `counter_trust_level` | Whether the values are fixture-declared, runner-parsed, or trace-audited. |

For this no-run access packet fixture, `loopx_cli_calls.total=0` is the
expected value. It means no CLI bridge or worker trace has been observed. The
fixture proves that the access packet and counter schema are ready; a later
bridge fixture or real case must prove actual interface use.

## Public Fixture Shape

`loopx.benchmark.build_terminal_bench_loopx_access_packet_fixture`
returns:

```text
schema_version=terminal_bench_loopx_access_packet_fixture_v0
arm=codex_loopx
loopx_inside_case=true
case_semantics_changed_by_harness=true
official_score_comparable_to_native_codex=false
model_plus_harness_pair=true
loopx_interface_surface=prompt_packet_only_no_cli_bridge
loopx_interfaces_available=false
loopx_cli_bridge_available=false
loopx_actual_use_observed=false
real_run=false
submit_eligible=false
```

The fixture is not official-score evidence and is not comparable to native
Codex. It is a wiring contract for the next runner step.

## Compact History Projection

`benchmark_run_v0` compaction now preserves `interaction_counters` so status and
history readers can see, at minimum:

```text
codex_runtime_goal_tool_calls.total
loopx_cli_calls.total
loopx_state_reads
loopx_state_writes
harness_skill_or_packet_injected
case_result_writeback
```

This makes LoopX interface usage an observable metric instead of a chat
interpretation.

## Stop Conditions

Stop before:

- treating `create_goal` or `update_goal` as LoopX CLI calls;
- treating prompt-packet-only V0 as proof that LoopX CLI was used;
- claiming a no-run access packet proves LoopX task uplift;
- submitting, uploading, or publishing leaderboard artifacts;
- recording raw runner logs, raw Codex sessions, raw task prompts, local paths,
  credentials, auth files, Docker logs, or private task artifacts in public
  notes;
- using passive observer events as inside-case LoopX evidence.

## Smoke

```bash
python3 examples/terminal-bench-loopx-access-packet-smoke.py
```

The smoke validates the packet text, fixture counters, public-safety boundary,
and compact `benchmark_run_v0` counter projection.
