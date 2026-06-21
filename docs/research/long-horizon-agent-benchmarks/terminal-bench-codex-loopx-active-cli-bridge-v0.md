# Terminal-Bench Codex LoopX Active CLI Bridge V0

Checked at: 2026-06-08T23:18:00+08:00.

This note records the core `codex_loopx` treatment surface: Codex CLI
must receive an in-case LoopX bridge and actively call LoopX while
solving the task. The earlier runner-side bridge fixture is useful only as a
measurement probe. It is not the treatment evidence.

This slice is still no-run/no-submit. It does not run Harbor, Terminal-Bench,
Docker, real Codex workers, model APIs, uploads, shares, paid/cloud execution,
or leaderboard paths.

## Worker Bridge Packet

`GoalHarnessManagedCodex` now accepts:

```text
loopx_mode=codex_loopx
loopx_cli_bridge_enabled=true
```

When enabled, the first worker instruction contains:

```text
loopx_interface_surface: codex_worker_loopx_cli_bridge_v0
loopx_cli_bridge_available: true
loopx_cli_bridge_command_status: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' status --limit 5
loopx_cli_bridge_command_quota_should_run: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' quota should-run --goal-id '<goal-id>'
loopx_cli_bridge_command_todo_list: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' quota should-run --goal-id '<goal-id>'
loopx_cli_bridge_command_history: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' history --goal-id '<goal-id>' --limit 5
loopx_cli_bridge_command_check: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' check --scan-path '<loopx-project-root>/loopx/benchmark.py'
loopx_cli_bridge_command_append_benchmark_run: PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli --format json --registry '<loopx-runtime-root>/registry.global.json' --runtime-root '<loopx-runtime-root>' history append-benchmark-run --goal-id '<goal-id>' --benchmark-run-json /logs/agent/loopx-worker-benchmark-run.json --classification '<classification>' --dry-run
loopx_counter_trace_jsonl: /logs/agent/loopx-counter-trace.jsonl
loopx_benchmark_run_json: /logs/agent/loopx-worker-benchmark-run.json
loopx_benchmark_run_writeback_contract: loopx_worker_benchmark_run_writeback_contract_v0
worker_benchmark_run_json_schema_version: benchmark_run_v0
worker_benchmark_run_json_top_level_must_be_schema_version: true
do_not_wrap_worker_benchmark_run_json_in_benchmark_run_key: true
worker_benchmark_run_json_minimal_shape: schema_version,source_runner,benchmark_id,job_name,mode,worker_mode,real_run,submit_eligible,leaderboard_evidence,official_task_score,validation_scope,progress,validation,claim_boundary,trials
worker_benchmark_run_json_validation_scope_required: true
worker_benchmark_run_json_validation_scope_values: worker_bridge_connectivity,environment_ready,worker_case_success,official_verifier_result
worker_benchmark_run_json_bridge_connectivity_is_not_case_success: true
worker_benchmark_run_json_claim_boundary_required: true
worker_benchmark_run_json_must_omit: raw_paths,raw_logs,raw_trace,raw_task_prompt,raw_sessions,credential_values,auth_values
worker_benchmark_run_json_required_fixed_fields: real_run=true,submit_eligible=false,leaderboard_evidence=false
worker_benchmark_run_json_real_run_must_be_true: true
worker_benchmark_run_json_submit_eligible_must_be_false: true
worker_benchmark_run_json_leaderboard_evidence_must_be_false: true
worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true
run_finally_worker_benchmark_run_checkpoint: true
loopx_cli_bridge_call_policy_version: terminal_bench_loopx_cli_bridge_call_policy_v1
loopx_cli_bridge_call_policy_mode: lean_preflight_check_and_final_append
loopx_cli_bridge_default_required_calls: check,append_benchmark_run
loopx_cli_bridge_optional_blocked_or_resume_calls: status,quota_should_run,todo_list,history
loopx_cli_bridge_minimum_required_worker_calls: 1
loopx_cli_bridge_placeholder_policy_version: terminal_bench_loopx_cli_bridge_placeholder_policy_v0
loopx_cli_bridge_command_templates_require_placeholder_substitution: true
loopx_cli_bridge_quote_or_argv_execute_substituted_values: true
do_not_execute_loopx_cli_command_with_unresolved_angle_bracket_placeholders: true
episode_policy: single_codex_agent_loopx_assisted_checkpoints
episode_checkpoint_interval_seconds: 600
episode_checkpoint_scope: same_codex_agent_compact_evidence
do_not_spawn_additional_agents_for_episodes: true
runner_side_guaranteed_writeback_for_final_outcome: true
after_each_loopx_cli_call_append_compact_jsonl_to_trace: true
before_long_actions_call_loopx_check_once: true
do_not_call_status_quota_todo_history_by_default: true
call_status_quota_todo_history_only_when_blocked_or_resuming_or_schema_retry_needs_context: true
write_compact_case_result_after_final_validation_cleanup_or_terminal_blocker_only: true
do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true
emit_compact_counter_trace_for_each_loopx_cli_call: true
if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once: true
```

The placeholder command packet is public-safe. A private no-upload repeat may
substitute actual mounted paths in the worker environment, but those raw values
must stay out of public artifacts. Workers must not execute a command while
angle-bracket placeholders remain unresolved; they should substitute concrete
values first and execute with shell quoting or an argv list so placeholders are
never interpreted as shell redirection. The final `append_benchmark_run` belongs
after final validation/cleanup or after a terminal blocker decision.

## Trace Ingestion

The active bridge requires a private compact JSONL trace file, passed as
`loopx_counter_trace_json`. The Codex worker should append one compact
row for each LoopX CLI call and state read/write. After the run,
`GoalHarnessManagedCodex.populate_context_post_run()` reads that file and
projects only public-safe counters:

```text
loopx_counter_trace_row_required_fields=event,command,ok,goal_id,mode,classification
loopx_counter_trace_file_loaded=true
loopx_counter_trace_row_count=<n>
loopx_interaction_counters.loopx_cli_calls.total=<n>
```

Each CLI-call row should include the active `goal_id`, worker `mode`, and
benchmark `classification` so a compact trace proves both the call and the
LoopX context that was injected. The raw trace path and raw rows stay
private and are not copied into public LoopX docs or status.

If the Codex worker exits through an exception path such as a non-zero agent
return, `GoalHarnessManagedCodex.run()` still attempts a `run_finally` compact
worker benchmark_run checkpoint before the exception propagates. When no trace
rows exist, that checkpoint records `active_cli_bridge_no_trace` style evidence
and an interrupted worker-bridge blocker; it does not claim worker bridge
success, official reward, or leaderboard evidence.

## Worker Writeback Shape

The active worker bridge now carries a minimal `benchmark_run_v0` writeback
contract in the first instruction. This is meant to reduce schema retries at the
end of a private repeat: the worker writes compact counts, validation booleans,
`validation_scope`, `claim_boundary`, and one compact trial summary, then calls
`append_benchmark_run`. `validation_scope=worker_bridge_connectivity` can prove
the LoopX-enhanced worker bridge is connected, but it must not be treated
as case success or official verifier success. If that append is schema-rejected,
the worker rewrites the payload to the minimal shape and retries once. It must
not use raw logs, raw paths, raw traces, raw task prompts, raw session bodies,
credential values, or auth values to satisfy the retry.

## Episode Policy

Long-horizon private repeats should stay close to the Codex automation shape:
one Codex worker remains the task-solving actor, while LoopX provides
lightweight checkpoint assistance. The active bridge policy is:

```text
single_codex_agent_loopx_assisted_checkpoints
worker_topology=single_codex_agent
checkpoint_interval_seconds=600
checkpoint_surface=worker_loopx_cli_bridge_compact_jsonl
runner_side_guaranteed_writeback=true
does_not_spawn_additional_agents=true
does_not_split_task_prompt=true
does_not_change_task_solution_actor=true
```

The runner may use these compact checkpoints to observe progress or resume a
timed-out private run, but it must not reinterpret the benchmark as multiple
workers solving separate slices. Final outcome archival still belongs to the
runner-side guaranteed `benchmark_run_v0` writeback.

## Measurement Boundary

Core evidence is worker-side:

```text
worker_loopx_cli_calls.total>=1
planned_worker_loopx_cli_call_total=2
runner_loopx_cli_calls.total=0
loopx_default_required_calls=check,append_benchmark_run
loopx_optional_context_calls=status,quota_should_run,todo_list,history
loopx_state_reads>=1
loopx_state_writes=0 when append is dry-run; 1 only for execute
case_result_writeback=worker_bridge_append_benchmark_run_dry_run or worker_bridge_append_benchmark_run_execute
counter_trust_level=compact_trace_audited
```

Runner-side bridge calls are allowed only as setup or measurement probes. They
must not be counted as LoopX in-case use.

## Harbor Command Shape

The public command template consumes the generic LoopX worker bridge
install contract in `docs/worker-bridge-install-contract.md`. It must make the
bridge package and runtime root visible inside the task container. The current
Harbor adapter uses `--mounts` with placeholder same-path bind mounts, then
passes an in-container command prefix to the Codex worker:

```text
--mounts [{"read_only": true, "source": "<loopx-project-root>", "target": "<loopx-project-root>", "type": "bind"}, {"read_only": true, "source": "<loopx-runtime-root>", "target": "<loopx-runtime-root>", "type": "bind"}]
--agent-kwarg loopx_mode=codex_loopx
--agent-kwarg loopx_cli_bridge_enabled=true
--agent-kwarg loopx_command_prefix=PYTHONPATH=<loopx-project-root> python3 -m loopx.cli
--agent-kwarg loopx_registry_arg=<loopx-runtime-root>/registry.global.json
--agent-kwarg loopx_runtime_root_arg=<loopx-runtime-root>
--agent-kwarg loopx_scan_path=<loopx-project-root>/loopx/benchmark.py
--agent-kwarg loopx_benchmark_run_json=/logs/agent/loopx-worker-benchmark-run.json
--agent-kwarg loopx_counter_trace_json=/logs/agent/loopx-counter-trace.jsonl
--agent-kwarg loopx_classification=<classification>
```

This is the route to test before another private no-upload
`terminal-bench@2.0` repeat.

For private local repeats, the runner must use the LoopX private runner
environment, which prepends the probe PATH (`~/.local/bin`, Homebrew, and
system bins), and may also use the command builder's private `resolve_cli_paths`
mode. This keeps `uvx`, Docker/Colima, and Codex visible to the same Harbor
process. The public command template intentionally remains `uvx` so local
absolute paths do not enter public docs or status artifacts.

Benchmark events should record only the compact
`private_runner_launch_summary`, never the raw private env. The summary says
whether the launch used the private runner env, whether the private argv was
resolved, how many probe PATH classes were covered, the first preflight blocker,
and the no-upload boundary booleans. It must keep `raw_env_recorded=false`,
`raw_paths_recorded=false`, and `auth_values_recorded=false`.

When the sample set is a local copied dataset directory, Harbor must receive it
through `--path`, not `--dataset`; the latter is reserved for registry package
references such as `org/name@version`. The command builder chooses `--path` for
local-looking dataset strings and keeps `--dataset` for public registry names.

## Private Repeat Preflight

The benchmark wrapper now has a no-run preflight for the next private repeat:

```bash
loopx benchmark run terminal-bench \
  --mode codex-loopx \
  --preflight-guard \
  --active-cli-bridge
```

Equivalent compact form: `loopx benchmark run terminal-bench --mode codex-loopx --preflight-guard --active-cli-bridge`.

This command still does not run Harbor, Terminal-Bench, Docker task containers,
Codex workers, model APIs, uploads, or leaderboard paths. It records the planned
worker bridge route as:

```text
loopx_cli_bridge_surface=codex_worker_loopx_cli_bridge_v0
planned_worker_loopx_cli_call_total=2
worker_loopx_cli_call_total=0
runner_loopx_cli_call_total=0
```

The zero observed worker count is intentional for the preflight. The follow-up
private no-upload sample may only claim in-case LoopX use after the real
worker trace reports `worker_loopx_cli_call_total >= 1`.

## Claim Boundary

The compact claim gate is:

```text
terminal_bench_loopx_claim_gate_v0
requires_worker_loopx_cli_calls=true
required_worker_loopx_cli_call_total_min=1
reject_runner_bridge_calls_as_in_case_evidence=true
reject_codex_runtime_goal_tool_calls_as_loopx_evidence=true
uplift_claim_allowed=false
leaderboard_claim_allowed=false
```

This slice may claim:

```text
Codex worker instructions can now carry an active LoopX CLI bridge packet
with concrete command templates and compact counter extraction for worker-side
LoopX calls.
```

It must not claim:

- a real benchmark task ran;
- Codex actually called LoopX in a real case;
- official task success;
- cost or token improvement;
- leaderboard readiness;
- LoopX uplift.

## Smoke

```bash
python3 examples/terminal-bench-codex-loopx-active-cli-bridge-smoke.py
```

The smoke uses fake Harbor modules, validates worker prompt command templates,
verifies bridge metadata, checks compact worker-side counters, confirms the
private-repeat preflight claim gate, and confirms the Harbor command preview
can carry the active bridge kwargs without exposing raw private paths.
