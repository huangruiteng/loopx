#!/usr/bin/env python3
"""Smoke-test codex_loopx active worker CLI bridge packet."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HELPER = REPO_ROOT / "examples" / "terminal-bench-managed-codex-custom-agent-smoke.py"
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-codex-loopx-active-cli-bridge-v0.md"
README = TOPIC_DIR / "README.md"

FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "ARK" + "_BASE_URL=",
    "DOUBAO" + "_MODEL=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]

REQUIRED_DOC_SNIPPETS = [
    "Terminal-Bench Codex LoopX Active CLI Bridge V0",
    "loopx_cli_bridge_enabled=true",
    "codex_worker_loopx_cli_bridge_v0",
    "loopx_cli_bridge_available: true",
    "loopx_cli_bridge_command_status",
    "loopx_cli_bridge_command_append_benchmark_run",
    "loopx_counter_trace_jsonl",
    "loopx_benchmark_run_writeback_contract",
    "worker_benchmark_run_json_schema_version: benchmark_run_v0",
    "worker_benchmark_run_json_top_level_must_be_schema_version: true",
    "do_not_wrap_worker_benchmark_run_json_in_benchmark_run_key: true",
    "worker_benchmark_run_json_minimal_shape",
    "worker_benchmark_run_json_validation_scope_required: true",
    "worker_benchmark_run_json_bridge_connectivity_is_not_case_success: true",
    "worker_benchmark_run_json_claim_boundary_required: true",
    "worker_benchmark_run_json_required_fixed_fields: real_run=true,submit_eligible=false,leaderboard_evidence=false",
    "worker_benchmark_run_json_submit_eligible_must_be_false: true",
    "worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true",
    "run_finally_worker_benchmark_run_checkpoint: true",
    "loopx_cli_bridge_call_policy_mode: lean_preflight_check_and_final_append",
    "loopx_cli_bridge_placeholder_policy_version: terminal_bench_loopx_cli_bridge_placeholder_policy_v0",
    "loopx_cli_bridge_command_templates_require_placeholder_substitution: true",
    "do_not_execute_loopx_cli_command_with_unresolved_angle_bracket_placeholders: true",
    "do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true",
    "do_not_call_status_quota_todo_history_by_default: true",
    "if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once",
    "single_codex_agent_loopx_assisted_checkpoints",
    "do_not_spawn_additional_agents_for_episodes: true",
    "--mounts",
    "<loopx-project-root>",
    "PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli",
    "/logs/agent/loopx-counter-trace.jsonl",
    "worker_loopx_cli_calls.total>=1",
    "planned_worker_loopx_cli_call_total=2",
    "runner_loopx_cli_calls.total=0",
    "--preflight-guard --active-cli-bridge",
    "private_runner_launch_summary",
    "terminal_bench_loopx_claim_gate_v0",
    "python3 examples/terminal-bench-codex-loopx-active-cli-bridge-smoke.py",
]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def helper_module() -> Any:
    return load_module(HELPER, "terminal_bench_managed_codex_custom_agent_smoke_helper_active")


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 24000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-codex-loopx-active-cli-bridge-v0.md" in readme, readme
    assert_public_safe(text)


def counter_trace() -> list[dict[str, Any]]:
    return [
        {
            "kind": "loopx_cli_call",
            "command": "check",
            "ok": True,
            "goal_id": "terminal-bench-fixture",
            "mode": "codex_loopx",
            "classification": "terminal_bench_fixture_active_bridge_v0",
        },
        {
            "kind": "loopx_cli_call",
            "command": "append_benchmark_run",
            "ok": True,
            "dry_run": True,
            "goal_id": "terminal-bench-fixture",
            "mode": "codex_loopx",
            "classification": "terminal_bench_fixture_active_bridge_v0",
        },
        {"kind": "loopx_state_read", "surface": "check"},
    ]


def assert_active_bridge_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        loopx_mode="codex_loopx",
        goal_id="terminal-bench-fixture",
        loopx_cli_bridge_enabled=True,
    )
    assert "LoopX Access Packet V0" in instruction, instruction
    assert "loopx_interface_surface: codex_worker_loopx_cli_bridge_v0" in instruction, instruction
    assert "loopx_cli_bridge_available: true" in instruction, instruction
    assert "loopx_cli_bridge_command_status:" in instruction, instruction
    assert "loopx_cli_bridge_command_quota_should_run:" in instruction, instruction
    assert "loopx_cli_bridge_command_todo_list:" in instruction, instruction
    assert "loopx_cli_bridge_command_history:" in instruction, instruction
    assert "loopx_cli_bridge_command_check:" in instruction, instruction
    assert "loopx_cli_bridge_command_append_benchmark_run:" in instruction, instruction
    assert "loopx_counter_trace_jsonl:" in instruction, instruction
    assert "loopx_benchmark_run_json:" in instruction, instruction
    assert (
        "loopx_benchmark_run_writeback_contract: "
        "loopx_worker_benchmark_run_writeback_contract_v0"
    ) in instruction, instruction
    assert "worker_benchmark_run_json_schema_version: benchmark_run_v0" in instruction, instruction
    assert (
        "worker_benchmark_run_json_top_level_must_be_schema_version: true"
        in instruction
    ), instruction
    assert (
        "do_not_wrap_worker_benchmark_run_json_in_benchmark_run_key: true"
        in instruction
    ), instruction
    assert "worker_benchmark_run_json_minimal_shape:" in instruction, instruction
    assert (
        "worker_benchmark_run_json_validation_scope_required: true"
        in instruction
    ), instruction
    assert (
        "worker_benchmark_run_json_validation_scope_values: "
        "worker_bridge_connectivity,environment_ready,worker_case_success,"
        "official_verifier_result"
    ) in instruction, instruction
    assert (
        "worker_benchmark_run_json_bridge_connectivity_is_not_case_success: true"
        in instruction
    ), instruction
    assert (
        "worker_benchmark_run_json_claim_boundary_required: true"
        in instruction
    ), instruction
    assert (
        "worker_benchmark_run_json_claim_boundary_required_fields: "
        "bridge_connectivity_claim_allowed,case_success_claim_allowed,"
        "official_score_claim_allowed,leaderboard_claim_allowed,"
        "forbidden_claims"
    ) in instruction, instruction
    assert "worker_benchmark_run_json_must_omit:" in instruction, instruction
    assert (
        "worker_benchmark_run_json_required_fixed_fields: "
        "real_run=true,submit_eligible=false,leaderboard_evidence=false"
    ) in instruction, instruction
    assert (
        "worker_benchmark_run_json_submit_eligible_must_be_false: true"
        in instruction
    ), instruction
    assert (
        "worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true"
        in instruction
    ), instruction
    assert "raw_task_prompt" in instruction and "credential_values" in instruction, instruction
    assert (
        "if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once: true"
        in instruction
    ), instruction
    assert (
        "loopx_cli_bridge_call_policy_mode: lean_preflight_check_and_final_append"
        in instruction
    ), instruction
    assert "loopx_cli_bridge_default_required_calls: check,append_benchmark_run" in instruction, instruction
    assert (
        "loopx_cli_bridge_command_templates_require_placeholder_substitution: true"
        in instruction
    ), instruction
    assert (
        "do_not_execute_loopx_cli_command_with_unresolved_angle_bracket_placeholders: true"
        in instruction
    ), instruction
    assert (
        "do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true"
        in instruction
    ), instruction
    assert "do_not_call_status_quota_todo_history_by_default: true" in instruction, instruction
    assert (
        "before_long_actions_call_loopx_status_quota_todo_history_check: true"
        not in instruction
    ), instruction
    assert "episode_policy: single_codex_agent_loopx_assisted_checkpoints" in instruction, instruction
    assert "episode_checkpoint_scope: same_codex_agent_compact_evidence" in instruction, instruction
    assert "do_not_spawn_additional_agents_for_episodes: true" in instruction, instruction
    assert "after_each_loopx_cli_call_append_compact_jsonl_to_trace: true" in instruction, instruction
    assert "loopx_counter_trace_row_required_fields: event,command,ok,goal_id,mode,classification" in instruction, instruction
    assert "loopx_counter_trace_context_goal_id: terminal-bench-fixture" in instruction, instruction
    assert "loopx_counter_trace_context_mode: codex_loopx" in instruction, instruction
    assert "emit_compact_counter_trace_for_each_loopx_cli_call: true" in instruction, instruction
    assert "<loopx-project-root>" in instruction, instruction
    assert "<loopx-runtime-root>" in instruction, instruction
    assert "python3 -m loopx.cli" in instruction, instruction
    assert "/logs/agent/loopx-counter-trace.jsonl" in instruction, instruction
    assert task in instruction, instruction
    assert_public_safe(instruction)

    with tempfile.TemporaryDirectory(prefix="loopx-counter-trace-") as tmp:
        trace_path = Path(tmp) / "counter-trace.jsonl"
        benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
        agent = module.GoalHarnessManagedCodex(
            logs_dir=Path("logs"),
            model_name="gpt-5.5",
            loopx_mode="codex_loopx",
            loopx_goal_id="terminal-bench-fixture",
            loopx_cli_bridge_enabled=True,
            loopx_benchmark_run_json=str(benchmark_run_path),
            loopx_counter_trace_json=str(trace_path),
        )
        context = helper.FakeAgentContext()
        asyncio.run(agent.run(task, object(), context))
        assert agent.received_instruction is not None
        assert "loopx_cli_bridge_available: true" in agent.received_instruction
        assert "loopx_counter_trace_jsonl:" in agent.received_instruction
        assert context.is_empty(), context.metadata

        trace_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in counter_trace()),
            encoding="utf-8",
        )
        loaded_trace = module.load_loopx_counter_trace_file(trace_path)
        assert loaded_trace[0]["goal_id"] == "terminal-bench-fixture", loaded_trace
        assert loaded_trace[0]["mode"] == "codex_loopx", loaded_trace
        assert (
            loaded_trace[0]["classification"]
            == "terminal_bench_fixture_active_bridge_v0"
        ), loaded_trace
        agent.populate_context_post_run(context)
        assert benchmark_run_path.exists(), benchmark_run_path
        benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
        from loopx.status import compact_benchmark_run

        compact_run = compact_benchmark_run(benchmark_run)
        assert compact_run is not None, benchmark_run
        assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
        assert benchmark_run["source_runner"] == "terminal_bench_worker_bridge", benchmark_run
        assert benchmark_run["worker_loopx_cli_call_total"] == 2, benchmark_run
        assert benchmark_run["loopx_worker_cli_bridge_trace_observed"] is True, benchmark_run
        assert benchmark_run["episode_policy"]["worker_topology"] == "single_codex_agent", benchmark_run
        assert benchmark_run["episode_policy"]["does_not_spawn_additional_agents"] is True, benchmark_run
        outcome = benchmark_run["worker_bridge_outcome"]
        assert outcome["worker_bridge_verified"] is True, benchmark_run
        assert outcome["runner_return_status"] == "pending_after_worker_bridge_success", benchmark_run
        assert outcome["official_score_status"] == "blocked_pending_runner_return", benchmark_run
        assert compact_run["worker_bridge_outcome"]["worker_bridge_verified"] is True, compact_run
        assert compact_run["worker_bridge_outcome"]["worker_loopx_cli_call_total"] == 2, compact_run
        assert (
            compact_run["episode_policy"]["mode"]
            == "single_codex_agent_loopx_assisted_checkpoints"
        ), compact_run
        assert compact_run["episode_policy"]["does_not_split_task_prompt"] is True, compact_run
        assert compact_run["validation"]["all_passed"] is True, compact_run
        assert_public_safe(benchmark_run)
        assert_public_safe(compact_run)
    loopx = context.metadata["loopx"]
    assert loopx["mode"] == "codex_loopx", loopx
    assert loopx["loopx_interface_surface"] == "codex_worker_loopx_cli_bridge_v0", loopx
    assert loopx["loopx_cli_bridge_available"] is True, loopx
    assert loopx["loopx_prompt_only_until_cli_bridge"] is False, loopx
    assert (
        loopx["loopx_cli_bridge_call_policy_mode"]
        == "lean_preflight_check_and_final_append"
    ), loopx
    assert loopx["loopx_cli_bridge_default_required_calls"] == [
        "check",
        "append_benchmark_run",
    ], loopx
    assert loopx["loopx_cli_bridge_optional_context_calls"] == [
        "status",
        "quota_should_run",
        "todo_list",
        "history",
    ], loopx
    assert loopx["loopx_cli_bridge_required_call_minimum"] == 1, loopx
    assert set(loopx["available_loopx_interface_commands"]) == {
        "status",
        "quota_should_run",
        "todo_list",
        "history",
        "check",
        "append_benchmark_run",
    }, loopx
    assert loopx["loopx_cli_bridge_command_prefix_present"] is True, loopx
    assert loopx["loopx_counter_trace_jsonl_declared"] is True, loopx
    assert loopx["loopx_counter_trace_file_loaded"] is True, loopx
    assert loopx["loopx_counter_trace_row_count"] == len(counter_trace()), loopx
    assert loopx["loopx_benchmark_run_json_declared"] is True, loopx
    assert loopx["loopx_benchmark_run_json_written"] is True, loopx
    assert (
        loopx["loopx_run_finally_benchmark_run_json_written"] is True
    ), loopx
    assert (
        loopx["loopx_benchmark_run_writeback_status"]
        == "worker_bridge_benchmark_run_written"
    ), loopx
    assert loopx["loopx_worker_cli_call_total"] == 2, loopx
    assert loopx["loopx_worker_benchmark_run_schema_version"] == "benchmark_run_v0", loopx
    episode_policy = loopx["loopx_episode_policy"]
    assert episode_policy["mode"] == "single_codex_agent_loopx_assisted_checkpoints", episode_policy
    assert episode_policy["worker_topology"] == "single_codex_agent", episode_policy
    assert episode_policy["does_not_change_task_solution_actor"] is True, episode_policy
    counters = loopx["loopx_interaction_counters"]
    assert counters["loopx_cli_calls"]["total"] == 2, counters
    assert counters["loopx_cli_calls"]["check"] == 1, counters
    assert counters["loopx_cli_calls"]["append_benchmark_run"] == 1, counters
    assert counters["loopx_state_reads"] == 1, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "worker_bridge_append_benchmark_run_dry_run", counters
    assert counters["counter_trust_level"] == "compact_trace_audited", counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 0, counters
    assert_public_safe(loopx)


def assert_no_packet_ablation_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        loopx_mode="codex_loopx",
        goal_id="terminal-bench-fixture",
        loopx_cli_bridge_enabled=True,
        loopx_access_packet_mode="none",
    )
    assert "LoopX access packet for this case" not in instruction, instruction
    assert "LoopX Access Packet V0" not in instruction, instruction
    assert "loopx_cli_bridge_command_check:" not in instruction, instruction
    assert "loopx_cli_bridge_command_append_benchmark_run:" not in instruction, instruction
    assert "LoopX operating rules for this case:" in instruction, instruction
    assert task in instruction, instruction
    assert_public_safe(instruction)

    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        loopx_mode="codex_loopx",
        loopx_goal_id="terminal-bench-fixture",
        loopx_cli_bridge_enabled=True,
        loopx_access_packet_mode="none",
    )
    context = helper.FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction is not None
    assert "LoopX Access Packet V0" not in agent.received_instruction
    assert context.is_empty(), context.metadata
    agent.populate_context_post_run(context)
    loopx = context.metadata["loopx"]
    assert loopx["mode"] == "codex_loopx", loopx
    assert loopx["loopx_access_packet_mode"] == "none", loopx
    assert loopx["loopx_access_packet_injected"] is False, loopx
    assert loopx["loopx_interface_surface"] == "managed_policy_prompt_only", loopx
    assert loopx["loopx_cli_bridge_available"] is False, loopx
    assert loopx["loopx_cli_bridge_contract"] is None, loopx
    assert loopx["available_loopx_interface_commands"] == [], loopx
    assert loopx["declared_loopx_interface_commands"] == [], loopx
    assert loopx["loopx_access_packet_schema_version"] is None, loopx
    assert loopx["loopx_cli_bridge_default_required_calls"] == [], loopx
    assert loopx["loopx_cli_bridge_required_call_minimum"] == 0, loopx
    assert_public_safe(loopx)


def assert_hardened_baseline_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        loopx_mode="hardened_codex_baseline",
        loopx_access_packet_mode="none",
        loopx_cli_bridge_enabled=True,
    )
    assert instruction == task, instruction

    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        loopx_mode="hardened_codex_baseline",
        loopx_access_packet_mode="none",
        loopx_cli_bridge_enabled=True,
    )
    context = helper.FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction == task, agent.received_instruction
    assert context.is_empty(), context.metadata
    agent.populate_context_post_run(context)
    loopx = context.metadata["loopx"]
    assert loopx["mode"] == "hardened_codex_baseline", loopx
    assert loopx["loopx_access_packet_mode"] == "none", loopx
    assert loopx["loopx_access_packet_injected"] is False, loopx
    assert (
        loopx["loopx_interface_surface"]
        == "hardened_codex_baseline_no_loopx_state"
    ), loopx
    assert loopx["loopx_cli_bridge_available"] is False, loopx
    assert loopx["case_semantics_changed_by_harness"] is False, loopx
    assert loopx["loopx_inside_case"] is False, loopx
    assert loopx["official_score_comparable_to_native_codex"] is False, loopx
    assert loopx["model_plus_harness_pair"] is False, loopx
    assert loopx["control_plane_score_applicable"] is False, loopx
    assert loopx["startup_surface_calibration"] is False, loopx
    assert loopx["hardened_install_surface"] is True, loopx
    assert loopx["hardened_install_baseline"] is True, loopx
    assert loopx["official_score_comparable_to_loopx_treatment"] is True, loopx
    assert loopx["task_prompt_changed_by_loopx_policy"] is False, loopx
    counters = loopx["loopx_interaction_counters"]
    assert counters["prompt_policy_injected"] is False, counters
    assert counters["harness_skill_or_packet_injected"] is False, counters
    assert counters["loopx_cli_calls"]["total"] == 0, counters
    assert counters["loopx_state_reads"] == 0, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "hardened_codex_baseline_runner_only", counters
    assert (
        counters["counter_trust_level"]
        == "hardened_codex_baseline_no_loopx_state"
    ), counters
    assert_public_safe(loopx)


def assert_active_bridge_run_finally_checkpoint_on_agent_error() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_run = module.Codex.run

    async def failing_run(self: Any, instruction: str, environment: object, context: Any) -> None:
        self.received_instruction = instruction
        raise RuntimeError("simulated nonzero agent exit")

    module.Codex.run = failing_run
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-run-finally-") as tmp:
            benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
            trace_path = Path(tmp) / "counter-trace.jsonl"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=Path("logs"),
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_benchmark_run_json=str(benchmark_run_path),
                loopx_counter_trace_json=str(trace_path),
            )
            context = helper.FakeAgentContext()
            try:
                asyncio.run(agent.run("Solve the task.", object(), context))
            except RuntimeError as exc:
                assert str(exc) == "simulated nonzero agent exit", exc
            else:
                raise AssertionError("failing fake Codex run should raise")

            assert context.is_empty(), context.metadata
            assert benchmark_run_path.exists(), benchmark_run_path
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
            checkpoint = benchmark_run["worker_bridge_checkpoint"]
            assert checkpoint["checkpoint_kind"] == "run_finally", checkpoint
            assert checkpoint["interrupted"] is True, checkpoint
            assert checkpoint["trace_row_count"] == 0, checkpoint
            outcome = benchmark_run["worker_bridge_outcome"]
            assert outcome["worker_bridge_verified"] is False, outcome
            assert outcome["counter_trace_present"] is False, outcome
            assert outcome["wall_time_policy"]["interrupted"] is True, outcome
            assert (
                outcome["wall_time_policy"]["interrupt_reason"]
                == "agent_run_exception_or_nonzero_exit"
            ), outcome
            assert benchmark_run["validation"]["worker_bridge_trace_observed"] is False, benchmark_run
            assert (
                benchmark_run["validation"]["runner_return_completed_or_blocker_recorded"]
                is False
            ), benchmark_run

            from loopx.status import compact_benchmark_run

            compact = compact_benchmark_run(benchmark_run)
            assert compact is not None, benchmark_run
            assert compact["worker_bridge_outcome"]["worker_bridge_verified"] is False, compact
            assert compact["worker_bridge_outcome"]["wall_time_policy"]["interrupted"] is True, compact
            assert_public_safe(benchmark_run)
            assert_public_safe(compact)
    finally:
        module.Codex.run = original_run


def assert_active_bridge_preflight_failure_writes_startup_blocker() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_root = module.Codex.exec_as_root

    async def failing_exec_as_root(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "root",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "loopx-runtime-preflight-fails" in command:
            raise RuntimeError("simulated runtime preflight failure")
        return await original_exec_as_root(self, environment, command, env, cwd, timeout_sec)

    module.Codex.exec_as_root = failing_exec_as_root
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-preflight-blocker-") as tmp:
            benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
            trace_path = Path(tmp) / "counter-trace.jsonl"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=Path("logs"),
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_runtime_preflight_command=(
                    "loopx-runtime-preflight-fails"
                ),
                loopx_benchmark_run_json=str(benchmark_run_path),
                loopx_counter_trace_json=str(trace_path),
            )
            context = helper.FakeAgentContext()
            try:
                asyncio.run(agent.run("Solve the task.", object(), context))
            except RuntimeError as exc:
                assert str(exc) == "simulated runtime preflight failure", exc
            else:
                raise AssertionError("failing runtime preflight should raise")

            assert agent.received_instruction is None, agent.received_instruction
            assert context.is_empty(), context.metadata
            assert benchmark_run_path.exists(), benchmark_run_path
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
            assert benchmark_run["first_blocker"] == "runtime_preflight_failed", benchmark_run
            assert benchmark_run["repeat_blocked_by"] == "runtime_preflight_failed", benchmark_run
            assert (
                benchmark_run["pre_worker_startup_blocker"]
                == "runtime_preflight_failed"
            ), benchmark_run
            checkpoint = benchmark_run["worker_bridge_checkpoint"]
            assert checkpoint["checkpoint_kind"] == "pre_worker_startup_blocker", checkpoint
            assert checkpoint["pre_worker_startup_blocker"] == "runtime_preflight_failed", checkpoint
            outcome = benchmark_run["worker_bridge_outcome"]
            assert outcome["worker_bridge_verified"] is False, outcome
            assert outcome["pre_worker_startup_blocker"] == "runtime_preflight_failed", outcome
            assert (
                outcome["wall_time_policy"]["interrupt_reason"]
                == "runtime_preflight_failed"
            ), outcome
            assert (
                benchmark_run["validation"]["runner_return_completed_or_blocker_recorded"]
                is True
            ), benchmark_run
            assert benchmark_run["validation"]["worker_startup_blocker_recorded"] is True, benchmark_run

            from loopx.status import compact_benchmark_run

            compact = compact_benchmark_run(benchmark_run)
            assert compact is not None, benchmark_run
            assert compact["first_blocker"] == "runtime_preflight_failed", compact
            assert compact["repeat_blocked_by"] == "runtime_preflight_failed", compact
            assert (
                compact["worker_bridge_outcome"]["pre_worker_startup_blocker"]
                == "runtime_preflight_failed"
            ), compact
            assert_public_safe(benchmark_run)
            assert_public_safe(compact)
    finally:
        module.Codex.exec_as_root = original_exec_as_root


def assert_active_bridge_install_failure_writes_startup_blocker() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_root = module.Codex.exec_as_root

    async def failing_exec_as_root(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "root",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        raise RuntimeError("simulated worker install failure")

    module.Codex.exec_as_root = failing_exec_as_root
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-install-blocker-") as tmp:
            benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
            trace_path = Path(tmp) / "counter-trace.jsonl"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=Path("logs"),
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_benchmark_run_json=str(benchmark_run_path),
                loopx_counter_trace_json=str(trace_path),
            )
            try:
                asyncio.run(agent.install(object()))
            except RuntimeError as exc:
                assert str(exc) == "simulated worker install failure", exc
            else:
                raise AssertionError("failing worker install should raise")

            assert agent.received_instruction is None, agent.received_instruction
            assert benchmark_run_path.exists(), benchmark_run_path
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
            expected_blocker = "worker_install_failed_package_manager_preinstall"
            assert benchmark_run["first_blocker"] == expected_blocker, benchmark_run
            assert benchmark_run["repeat_blocked_by"] == expected_blocker, benchmark_run
            assert benchmark_run["pre_worker_startup_blocker"] == expected_blocker, benchmark_run
            checkpoint = benchmark_run["worker_bridge_checkpoint"]
            assert checkpoint["checkpoint_kind"] == "pre_worker_startup_blocker", checkpoint
            assert checkpoint["interrupted"] is True, checkpoint
            assert checkpoint["trace_row_count"] == 0, checkpoint
            assert checkpoint["pre_worker_startup_blocker"] == expected_blocker, checkpoint
            outcome = benchmark_run["worker_bridge_outcome"]
            assert outcome["worker_bridge_verified"] is False, outcome
            assert outcome["pre_worker_startup_blocker"] == expected_blocker, outcome
            assert (
                outcome["wall_time_policy"]["interrupt_reason"]
                == expected_blocker
            ), outcome
            assert (
                benchmark_run["validation"]["runner_return_completed_or_blocker_recorded"]
                is True
            ), benchmark_run
            assert benchmark_run["validation"]["worker_startup_blocker_recorded"] is True, benchmark_run

            from loopx.status import compact_benchmark_run

            compact = compact_benchmark_run(benchmark_run)
            assert compact is not None, benchmark_run
            assert compact["first_blocker"] == expected_blocker, compact
            assert compact["repeat_blocked_by"] == expected_blocker, compact
            assert (
                compact["worker_bridge_outcome"]["pre_worker_startup_blocker"]
                == expected_blocker
            ), compact
            assert_public_safe(benchmark_run)
            assert_public_safe(compact)
    finally:
        module.Codex.exec_as_root = original_exec_as_root


def assert_default_worker_paths_map_to_logs_dir_for_install_blocker() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def failing_exec_as_agent(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        raise RuntimeError("simulated missing existing codex")

    module.Codex.exec_as_agent = failing_exec_as_agent
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-default-log-map-") as tmp:
            logs_dir = Path(tmp) / "agent"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_codex_install_strategy=(
                    module.TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
                ),
                loopx_codex_preflight_timeout_sec="45",
            )
            assert (
                agent.loopx_benchmark_run_json
                == "/logs/agent/loopx-worker-benchmark-run.json"
            ), agent.loopx_benchmark_run_json
            try:
                asyncio.run(agent.install(object()))
            except RuntimeError as exc:
                assert str(exc) == "simulated missing existing codex", exc
            else:
                raise AssertionError("failing require-existing install should raise")

            benchmark_run_path = logs_dir / "loopx-worker-benchmark-run.json"
            assert benchmark_run_path.exists(), benchmark_run_path
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
            assert (
                benchmark_run["first_blocker"]
                == "codex_cli_not_on_path"
            ), benchmark_run
            assert (
                benchmark_run["worker_bridge_checkpoint"]["checkpoint_kind"]
                == "pre_worker_startup_blocker"
            ), benchmark_run
            assert (
                benchmark_run["worker_bridge_checkpoint"]["pre_worker_startup_blocker"]
                == "codex_cli_not_on_path"
            ), benchmark_run
            assert (
                benchmark_run["validation"]["runner_return_completed_or_blocker_recorded"]
                is True
            ), benchmark_run
            assert_public_safe(benchmark_run)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_baseline_require_existing_writes_setup_diagnostic() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def failing_exec_as_agent(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        raise RuntimeError("simulated missing existing codex")

    module.Codex.exec_as_agent = failing_exec_as_agent
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-baseline-setup-") as tmp:
            logs_dir = Path(tmp) / "agent"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode=module.CODEX_GOAL_MODE_BASELINE_MODE,
                loopx_access_packet_mode=(
                    module.TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE
                ),
                loopx_cli_bridge_enabled=False,
                loopx_codex_install_strategy=(
                    module.TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
                ),
            )
            try:
                asyncio.run(agent.install(object()))
            except RuntimeError as exc:
                assert str(exc) == "simulated missing existing codex", exc
            else:
                raise AssertionError("baseline require-existing install should raise")

            diagnostic_path = (
                logs_dir / module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            )
            assert diagnostic_path.exists(), diagnostic_path
            diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            assert (
                diagnostic["schema_version"]
                == module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA
            ), diagnostic
            assert diagnostic["first_blocker"] == "codex_cli_not_on_path", diagnostic
            assert (
                diagnostic["pre_worker_startup_blocker"]
                == "codex_cli_not_on_path"
            ), diagnostic
            assert diagnostic["loopx_mode"] == module.CODEX_GOAL_MODE_BASELINE_MODE
            assert diagnostic["loopx_access_packet_mode"] == "none", diagnostic
            assert diagnostic["raw_paths_recorded"] is False, diagnostic
            assert diagnostic["raw_logs_read"] is False, diagnostic
            assert diagnostic["command_output_recorded"] is False, diagnostic
            assert not (logs_dir / "loopx-worker-benchmark-run.json").exists()
            assert_public_safe(diagnostic)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_agent_codex_install_split_stage_routes_blocker() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def failing_agent_install(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "loopx_codex_usable" in command:
            return types.SimpleNamespace(
                return_code=0,
                stdout="loopx_codex_missing\n",
                stderr="",
            )
        if "loopx_node_npm_ready" in command:
            return types.SimpleNamespace(
                return_code=0,
                stdout="loopx_node_npm_ready\n",
                stderr="",
            )
        if "npm install -g" in command:
            raise RuntimeError("simulated npm install failure")
        return types.SimpleNamespace(return_code=0, stdout="", stderr="")

    module.Codex.exec_as_agent = failing_agent_install
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-agent-install-") as tmp:
            benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
            logs_dir = Path(tmp) / "logs"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_benchmark_run_json=str(benchmark_run_path),
            )
            try:
                asyncio.run(agent.install(object()))
            except RuntimeError as exc:
                assert str(exc) == "simulated npm install failure", exc
            else:
                raise AssertionError("failing agent install should raise")

            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            expected_blocker = "worker_install_failed_agent_codex_install_npm_existing"
            assert benchmark_run["first_blocker"] == expected_blocker, benchmark_run
            assert (
                benchmark_run["pre_worker_startup_blocker"] == expected_blocker
            ), benchmark_run
            setup_path = logs_dir / module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            setup = json.loads(setup_path.read_text(encoding="utf-8"))
            assert setup["first_blocker"] == expected_blocker, setup
            assert_public_safe(benchmark_run)
            assert_public_safe(setup)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_require_existing_codex_version_probe_blocker() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def version_probe_fails(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "codex --version >/dev/null" in command:
            raise RuntimeError("simulated unusable existing codex")
        return types.SimpleNamespace(return_code=0, stdout="/usr/local/bin/codex\n", stderr="")

    module.Codex.exec_as_agent = version_probe_fails
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-version-probe-") as tmp:
            logs_dir = Path(tmp) / "agent"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
                loopx_codex_install_strategy=(
                    module.TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
                ),
            )
            try:
                asyncio.run(agent.install(object()))
            except RuntimeError as exc:
                assert str(exc) == "simulated unusable existing codex", exc
            else:
                raise AssertionError("failing version probe should raise")

            benchmark_run_path = logs_dir / "loopx-worker-benchmark-run.json"
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert (
                benchmark_run["first_blocker"]
                == "codex_cli_version_probe_failed"
            ), benchmark_run
            assert (
                benchmark_run["pre_worker_startup_blocker"]
                == "codex_cli_version_probe_failed"
            ), benchmark_run
            assert_public_safe(benchmark_run)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_require_existing_codex_preflight_success_contract() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def existing_codex_ok(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "command -v codex" in command:
            return types.SimpleNamespace(return_code=0, stdout="/opt/codex/bin/codex\n", stderr="")
        return types.SimpleNamespace(return_code=0, stdout="codex 0.0.0-fixture\n", stderr="")

    module.Codex.exec_as_agent = existing_codex_ok
    try:
        agent = module.GoalHarnessManagedCodex(
            logs_dir=Path("logs"),
            model_name="gpt-5.5",
            loopx_mode="codex_loopx",
            loopx_goal_id="terminal-bench-fixture",
            loopx_cli_bridge_enabled=True,
            loopx_codex_install_strategy=(
                module.TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
            ),
        )
        asyncio.run(agent.install(object()))
        calls = agent.exec_calls
        assert [call["user"] for call in calls] == ["agent", "agent", "root"], calls
        assert calls[0]["command"] == "set -euo pipefail; command -v codex", calls
        assert calls[0]["timeout_sec"] == 45, calls
        assert "codex --version >/dev/null 2>&1" in calls[1]["command"], calls
        assert calls[1]["timeout_sec"] == 45, calls
        assert "BIN_PATH=/opt/codex/bin/codex" in calls[2]["command"], calls
        assert "ln -sf" in calls[2]["command"], calls
        assert calls[2]["timeout_sec"] == 45, calls
        assert_public_safe(" ".join(call["command"] for call in calls))
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_worker_materialization_probe_accepts_require_existing_success() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def existing_codex_ok(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "command -v codex" in command:
            return types.SimpleNamespace(
                return_code=0, stdout="/opt/codex/bin/codex\n", stderr=""
            )
        return types.SimpleNamespace(return_code=0, stdout="codex fixture\n", stderr="")

    module.Codex.exec_as_agent = existing_codex_ok
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-worker-existing-") as tmp:
            root = Path(tmp)
            logs_dir = root / "logs"
            benchmark_run_path = root / "worker-materialization-probe.json"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode=module.CODEX_GOAL_MODE_BASELINE_MODE,
                loopx_ablation_mode="codex_goal_mode_baseline",
                loopx_access_packet_mode=(
                    module.TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE
                ),
                loopx_codex_install_strategy=(
                    module.TERMINAL_BENCH_CODEX_INSTALL_STRATEGY_REQUIRE_EXISTING
                ),
                loopx_worker_materialization_probe_only=True,
                loopx_benchmark_run_json=str(benchmark_run_path),
            )
            asyncio.run(agent.install(object()))
            setup_path = logs_dir / module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            setup = json.loads(setup_path.read_text(encoding="utf-8"))
            assert setup["first_blocker"] == "codex_require_existing_preflight_ok", setup
            assert setup["pre_worker_startup_blocker"] == "none", setup

            context = helper.FakeAgentContext()
            asyncio.run(agent.run("Solve the private task.", object(), context))
            benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
            assert benchmark_run["first_blocker"] == "none", benchmark_run
            outcome = benchmark_run["worker_bridge_outcome"]
            assert outcome["runner_return_status"] == (
                "worker_materialization_probe_completed"
            ), outcome
            assert outcome["worker_bridge_materialization_status"] == (
                "worker_codex_materialization_verified"
            ), outcome
            assert benchmark_run["validation"]["worker_bridge_repeat_ready"] is True, (
                benchmark_run["validation"]
            )
            assert_public_safe(setup)
            assert_public_safe(benchmark_run)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_managed_codex_install_hardening_contract() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    agent = module.GoalHarnessManagedCodex(logs_dir=Path("logs"), model_name="gpt-5.5")

    asyncio.run(agent.install(object()))
    calls = agent.exec_calls
    assert len(calls) == 10, calls
    root_install = calls[0]
    agent_codex_probe = calls[1]
    agent_runtime_probe = calls[2]
    root_node_path_repair = calls[3]
    agent_runtime_probe_after_repair = calls[4]
    nvm_bootstrap = calls[5]
    nvm_node = calls[6]
    npm_after_nvm = calls[7]
    codex_version_probe = calls[8]
    root_symlink = calls[9]
    assert root_install["user"] == "root", calls
    for call in (
        agent_codex_probe,
        agent_runtime_probe,
        agent_runtime_probe_after_repair,
        nvm_bootstrap,
        nvm_node,
        npm_after_nvm,
        codex_version_probe,
    ):
        assert call["user"] == "agent", calls
    assert root_node_path_repair["user"] == "root", calls
    assert root_symlink["user"] == "root", calls

    root_command = root_install["command"]
    for package in (
        "bash",
        "ca-certificates",
        "curl",
        "git",
        "nodejs",
        "npm",
        "xz-utils",
        "tar",
        "gzip",
        "ripgrep",
    ):
        assert package in root_command, root_command
    assert "apk add --no-cache bash curl nodejs npm ripgrep" in root_command, root_command
    assert "continuing with existing worker tools" in root_command, root_command
    assert root_install["env"] == {"DEBIAN_FRONTEND": "noninteractive"}, root_install

    agent_codex_probe_command = agent_codex_probe["command"]
    assert "loopx_codex_usable" in agent_codex_probe_command, agent_codex_probe_command
    assert "loopx_codex_missing" in agent_codex_probe_command, agent_codex_probe_command
    assert "command -v codex" in agent_codex_probe_command, agent_codex_probe_command
    assert "codex --version >/dev/null 2>&1" in agent_codex_probe_command, agent_codex_probe_command

    agent_runtime_probe_command = agent_runtime_probe["command"]
    assert "loopx_node_npm_ready" in agent_runtime_probe_command, agent_runtime_probe_command
    assert "loopx_node_npm_missing" in agent_runtime_probe_command, agent_runtime_probe_command
    assert "command -v node" in agent_runtime_probe_command, agent_runtime_probe_command
    assert "command -v npm" in agent_runtime_probe_command, agent_runtime_probe_command

    node_path_repair_command = root_node_path_repair["command"]
    assert "loopx_worker_node_runtime_path_repair_attempted" in node_path_repair_command, node_path_repair_command
    assert "mkdir -p /usr/local/bin" in node_path_repair_command, node_path_repair_command
    assert "/usr/bin/nodejs" in node_path_repair_command, node_path_repair_command
    assert "/usr/local/bin/$bin" in node_path_repair_command, node_path_repair_command
    assert "ln -sf" in node_path_repair_command, node_path_repair_command

    agent_runtime_probe_after_repair_command = agent_runtime_probe_after_repair["command"]
    assert "hash -r" in agent_runtime_probe_after_repair_command, agent_runtime_probe_after_repair_command
    assert "loopx_node_npm_ready" in agent_runtime_probe_after_repair_command, agent_runtime_probe_after_repair_command
    assert "loopx_node_npm_missing" in agent_runtime_probe_after_repair_command, agent_runtime_probe_after_repair_command

    nvm_bootstrap_command = nvm_bootstrap["command"]
    assert "curl unavailable for NVM bootstrap" in nvm_bootstrap_command, nvm_bootstrap_command
    assert "raw.githubusercontent.com/nvm-sh/nvm" in nvm_bootstrap_command, nvm_bootstrap_command

    nvm_node_command = nvm_node["command"]
    assert "NVM failed to install" in nvm_node_command, nvm_node_command
    assert "NVM failed to load" in nvm_node_command, nvm_node_command
    assert "nvm install 22" in nvm_node_command, nvm_node_command
    assert "nvm alias default 22" in nvm_node_command, nvm_node_command

    npm_after_nvm_command = npm_after_nvm["command"]
    assert "NPM_CONFIG_REGISTRY" in npm_after_nvm_command, npm_after_nvm_command
    assert "https://registry.npmjs.org" in npm_after_nvm_command, npm_after_nvm_command
    assert 'NPM_CONFIG_PREFIX="${HOME}/.loopx-codex"' in npm_after_nvm_command, npm_after_nvm_command
    assert 'mkdir -p "$NPM_CONFIG_PREFIX"' in npm_after_nvm_command, npm_after_nvm_command
    assert (
        'npm install -g --registry "$NPM_CONFIG_REGISTRY" @openai/codex@latest'
        in npm_after_nvm_command
    ), npm_after_nvm_command

    codex_version_probe_command = codex_version_probe["command"]
    assert "codex --version" in codex_version_probe_command, codex_version_probe_command
    assert "hash -r" in codex_version_probe_command, codex_version_probe_command

    symlink_command = root_symlink["command"]
    assert "for bin in node npm codex" in symlink_command, symlink_command
    assert "/home/*/.loopx-codex/bin" in symlink_command, symlink_command
    assert "/home/*/.nvm/versions/node/*/bin" in symlink_command, symlink_command
    assert "/usr/local/bin/$bin" in symlink_command, symlink_command
    assert_public_safe(
        root_command
        + agent_codex_probe_command
        + agent_runtime_probe_command
        + node_path_repair_command
        + agent_runtime_probe_after_repair_command
        + nvm_bootstrap_command
        + nvm_node_command
        + npm_after_nvm_command
        + codex_version_probe_command
        + symlink_command
    )


def assert_agent_node_runtime_path_repair_uses_existing_npm() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_exec_as_agent = module.Codex.exec_as_agent

    async def repair_then_runtime_ready(
        self: Any,
        environment: object,
        command: str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        timeout_sec: int | None = None,
    ) -> Any:
        self.exec_calls.append(
            {
                "user": "agent",
                "command": command,
                "env": env or {},
                "cwd": cwd,
                "timeout_sec": timeout_sec,
            }
        )
        if "loopx_codex_usable" in command:
            return types.SimpleNamespace(
                return_code=0,
                stdout="loopx_codex_missing\n",
                stderr="",
            )
        if "loopx_node_npm_ready" in command:
            runtime_probe_count = sum(
                "loopx_node_npm_ready" in call["command"]
                for call in self.exec_calls
                if call["user"] == "agent"
            )
            if runtime_probe_count == 1:
                return types.SimpleNamespace(
                    return_code=0,
                    stdout="loopx_node_npm_missing\n",
                    stderr="",
                )
            return types.SimpleNamespace(
                return_code=0,
                stdout="loopx_node_npm_ready\n",
                stderr="",
            )
        if "npm install -g" in command:
            return types.SimpleNamespace(return_code=0, stdout="installed\n", stderr="")
        if "codex --version" in command:
            return types.SimpleNamespace(return_code=0, stdout="codex fixture\n", stderr="")
        return types.SimpleNamespace(return_code=0, stdout="", stderr="")

    module.Codex.exec_as_agent = repair_then_runtime_ready
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-node-path-repair-") as tmp:
            logs_dir = Path(tmp) / "logs"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=logs_dir,
                model_name="gpt-5.5",
                loopx_mode="codex_loopx",
                loopx_goal_id="terminal-bench-fixture",
                loopx_cli_bridge_enabled=True,
            )
            asyncio.run(agent.install(object()))
            commands = [call["command"] for call in agent.exec_calls]
            assert any(
                "loopx_worker_node_runtime_path_repair_attempted" in command
                for command in commands
            ), commands
            assert any("npm install -g" in command for command in commands), commands
            assert not any("nvm install 22" in command for command in commands), commands
            setup_path = logs_dir / module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
            setup = json.loads(setup_path.read_text(encoding="utf-8"))
            assert setup["interrupted"] is False, setup
            assert setup["first_blocker"] == "codex_runtime_install_or_preflight_ok", setup
            assert setup["pre_worker_startup_blocker"] == "none", setup
            assert_public_safe(" ".join(commands))
            assert_public_safe(setup)
    finally:
        module.Codex.exec_as_agent = original_exec_as_agent


def assert_worker_materialization_probe_only_contract() -> None:
    helper = helper_module()
    module = helper.load_agent_module()

    with tempfile.TemporaryDirectory(prefix="loopx-worker-materialization-") as tmp:
        root = Path(tmp)
        logs_dir = root / "logs"
        benchmark_run_path = root / "worker-materialization-probe.json"
        agent = module.GoalHarnessManagedCodex(
            logs_dir=logs_dir,
            model_name="gpt-5.5",
            loopx_mode=module.CODEX_GOAL_MODE_BASELINE_MODE,
            loopx_ablation_mode="codex_goal_mode_baseline",
            loopx_access_packet_mode=(
                module.TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE
            ),
            loopx_worker_materialization_probe_only=True,
            loopx_benchmark_run_json=str(benchmark_run_path),
        )
        asyncio.run(agent.install(object()))
        setup_path = logs_dir / module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_FILE
        assert setup_path.exists(), setup_path
        setup = json.loads(setup_path.read_text(encoding="utf-8"))
        assert setup["schema_version"] == (
            module.TERMINAL_BENCH_WORKER_SETUP_DIAGNOSTIC_SCHEMA
        ), setup
        assert setup["interrupted"] is False, setup
        assert setup["pre_worker_startup_blocker"] == "none", setup

        context = helper.FakeAgentContext()
        asyncio.run(agent.run("Solve the private task.", object(), context))
        assert agent.received_instruction is None, agent.received_instruction
        assert context.is_empty(), context.metadata
        assert benchmark_run_path.exists(), benchmark_run_path
        benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
        assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
        assert benchmark_run["source_runner"] == (
            "terminal_bench_worker_materialization_probe"
        ), benchmark_run
        assert benchmark_run["mode"] == (
            "codex_goal_mode_baseline_worker_materialization_probe"
        ), benchmark_run
        assert benchmark_run["real_run"] is False, benchmark_run
        assert benchmark_run["worker_materialization_real_probe"] is True, benchmark_run
        assert benchmark_run["submit_eligible"] is False, benchmark_run
        assert benchmark_run["official_task_score"]["kind"] == (
            "not_run_worker_materialization_probe"
        ), benchmark_run
        assert benchmark_run["first_blocker"] == "none", benchmark_run
        outcome = benchmark_run["worker_bridge_outcome"]
        assert outcome["worker_bridge_verified"] is False, outcome
        assert outcome["runner_return_status"] == (
            "worker_materialization_probe_completed"
        ), outcome
        assert outcome["worker_bridge_materialization_status"] == (
            "worker_codex_materialization_verified"
        ), outcome
        assert outcome["worker_setup_diagnostic_file_count"] == 1, outcome
        assert outcome["worker_setup_diagnostic_schema_ok_count"] == 1, outcome
        validation = benchmark_run["validation"]
        assert validation["validation_scope"] == (
            "worker_codex_materialization_probe"
        ), validation
        assert validation["worker_bridge_materialized_when_required"] is True, validation
        assert validation["worker_bridge_repeat_ready"] is True, validation
        assert validation["no_model_task_solution_invoked"] is True, validation

        from loopx.status import compact_benchmark_run

        compact = compact_benchmark_run(benchmark_run)
        assert compact is not None, benchmark_run
        assert compact["worker_bridge_outcome"][
            "worker_bridge_materialization_status"
        ] == "worker_codex_materialization_verified", compact
        assert compact["validation"]["all_passed"] is True, compact
        assert_public_safe(benchmark_run)
        assert_public_safe(compact)


def assert_harbor_command_preview() -> None:
    from loopx.benchmark import (
        TERMINAL_BENCH_EXTRA_PROBE_PATHS,
        build_terminal_bench_private_runner_env,
        build_terminal_bench_private_runner_launch,
        build_terminal_bench_managed_harbor_command,
        resolve_terminal_bench_runner_binary,
        summarize_terminal_bench_private_runner_launch,
    )

    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    baseline_command = build_terminal_bench_managed_harbor_command(
        loopx_mode="hardened_codex_baseline",
        loopx_ablation_mode="hardened_codex_baseline",
        loopx_access_packet_mode="none",
    )
    private_command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        resolve_cli_paths=True,
    )
    local_dataset_command = build_terminal_bench_managed_harbor_command(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    local_dataset_batch_command = build_terminal_bench_managed_harbor_command(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        task_id=None,
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    materialization_probe_command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_goal_mode_baseline",
        loopx_ablation_mode="codex_goal_mode_baseline",
        loopx_access_packet_mode="none",
        worker_materialization_probe_only=True,
    )
    joined = " ".join(command)
    private_env = build_terminal_bench_private_runner_env()
    assert command[0] == "uvx", command
    assert private_command[0] == resolve_terminal_bench_runner_binary("uvx"), private_command
    assert "--dataset" in command and "--path" not in command, command
    assert "--path" in local_dataset_command and "--dataset" not in local_dataset_command, local_dataset_command
    assert "--include-task-name" in local_dataset_command, local_dataset_command
    assert "--path" in local_dataset_batch_command, local_dataset_batch_command
    assert "--include-task-name" not in local_dataset_batch_command, local_dataset_batch_command
    assert "loopx_cli_bridge_enabled=true" in local_dataset_batch_command, local_dataset_batch_command
    assert (
        "loopx_worker_materialization_probe_only=true"
        in materialization_probe_command
    ), materialization_probe_command
    for probe_path in TERMINAL_BENCH_EXTRA_PROBE_PATHS:
        assert str(Path(probe_path).expanduser()) in private_env["PATH"], private_env["PATH"]
    launch = build_terminal_bench_private_runner_launch(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    mode_launch = build_terminal_bench_private_runner_launch(
        mode="codex-loopx",
        loopx_cli_bridge_enabled=True,
    )
    batch_launch = build_terminal_bench_private_runner_launch(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        task_id=None,
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    active_user_launch = build_terminal_bench_private_runner_launch(
        mode="codex-loopx",
        loopx_cli_bridge_enabled=True,
        loopx_active_user_intervention_enabled=True,
    )
    assert "--include-task-name" not in batch_launch["argv"], batch_launch["argv"]
    assert "--path" in batch_launch["argv"], batch_launch["argv"]
    batch_mounts = json.loads(batch_launch["argv"][batch_launch["argv"].index("--mounts") + 1])
    assert all(Path(mount["source"]).is_absolute() for mount in batch_mounts), batch_mounts
    assert all(Path(mount["target"]).is_absolute() for mount in batch_mounts), batch_mounts
    assert "<loopx-project-root>" not in json.dumps(batch_mounts), batch_mounts
    assert "<loopx-runtime-root>" not in json.dumps(batch_mounts), batch_mounts
    batch_agent_kwargs = [
        item
        for index, item in enumerate(batch_launch["argv"])
        if index > 0 and batch_launch["argv"][index - 1] == "--agent-kwarg"
    ]
    assert not any("<loopx-project-root>" in item for item in batch_agent_kwargs), batch_agent_kwargs
    assert not any("<loopx-runtime-root>" in item for item in batch_agent_kwargs), batch_agent_kwargs
    active_user_mounts = json.loads(
        active_user_launch["argv"][active_user_launch["argv"].index("--mounts") + 1]
    )
    assert active_user_mounts[-1]["target"] == "/loopx-active-user", active_user_mounts
    assert active_user_mounts[-1]["read_only"] is False, active_user_mounts
    assert "<active-user-host-dir>" not in json.dumps(active_user_mounts), active_user_mounts
    launch_summary = summarize_terminal_bench_private_runner_launch(launch)
    active_user_summary = summarize_terminal_bench_private_runner_launch(active_user_launch)
    assert launch_summary["schema_version"] == "terminal_bench_private_runner_launch_summary_v0", launch_summary
    assert launch_summary["launch_schema_version"] == "terminal_bench_private_runner_launch_v0", launch_summary
    assert launch_summary["uses_private_runner_env"] is True, launch_summary
    assert launch_summary["argv_binary_name"] == "uvx", launch_summary
    assert launch_summary["argv_binary_resolved_for_private_launch"] is True, launch_summary
    assert launch_summary["no_upload_boundary"] is True, launch_summary
    assert launch_summary["submit_eligible"] is False, launch_summary
    assert launch_summary["env_probe_path_coverage_count"] == 3, launch_summary
    assert launch_summary["auth_values_recorded"] is False, launch_summary
    assert launch_summary["raw_env_recorded"] is False, launch_summary
    assert launch_summary["raw_paths_recorded"] is False, launch_summary
    closeout = launch_summary["closeout_command_templates"]
    assert closeout["schema_version"] == "terminal_bench_run_ledger_closeout_v0", closeout
    assert closeout["history_append"] is True, closeout
    assert closeout["run_ledger_update"] is True, closeout
    assert closeout["atomic_ledger_upsert"] is True, closeout
    assert "--update-run-ledger" in closeout["argv_template"], closeout
    assert "<private-job-dir>" in closeout["argv_template"], closeout
    assert_public_safe(json.dumps(closeout, sort_keys=True))
    assert active_user_summary["active_user_writable_mount_requested"] is True, active_user_summary
    assert active_user_summary["active_user_writable_mount_count"] == 1, active_user_summary
    assert active_user_summary["raw_paths_recorded"] is False, active_user_summary
    assert_public_safe(active_user_summary)
    assert_public_safe(launch_summary)
    assert "loopx_mode=codex_loopx" in command, command
    assert "loopx_mode=codex_loopx" in mode_launch["argv"], mode_launch["argv"]
    assert "loopx_cli_bridge_enabled=true" in mode_launch["argv"], mode_launch["argv"]
    assert "loopx_mode=hardened_codex_baseline" in baseline_command, baseline_command
    assert "loopx_ablation_mode=hardened_codex_baseline" in baseline_command, baseline_command
    assert "loopx_access_packet_mode=none" in baseline_command, baseline_command
    assert "loopx_cli_bridge_enabled=true" not in baseline_command, baseline_command
    assert "--mounts" not in baseline_command, baseline_command
    assert_public_safe(" ".join(baseline_command))
    assert "--mounts" in command, command
    mounts = json.loads(command[command.index("--mounts") + 1])
    assert mounts == [
        {
            "read_only": True,
            "source": "<loopx-project-root>",
            "target": "<loopx-project-root>",
            "type": "bind",
        },
        {
            "read_only": True,
            "source": "<loopx-runtime-root>",
            "target": "<loopx-runtime-root>",
            "type": "bind",
        },
    ], mounts
    assert "loopx_cli_bridge_enabled=true" in command, command
    assert (
        "loopx_command_prefix="
        "PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli"
    ) in command, command
    assert any(
        item.startswith("loopx_runtime_preflight_command=")
        and "apt-get install -y python3" in item
        for item in command
    ), command
    assert (
        "loopx_registry_arg="
        "<loopx-runtime-root>/registry.global.json"
    ) in command, command
    assert "loopx_runtime_root_arg=<loopx-runtime-root>" in command, command
    assert (
        "loopx_scan_path=<loopx-project-root>/loopx/benchmark.py"
    ) in command, command
    assert (
        "loopx_benchmark_run_json="
        "/logs/agent/loopx-worker-benchmark-run.json"
    ) in command, command
    assert "loopx_benchmark_run_schema_version=benchmark_run_v0" in command, command
    assert (
        "loopx_benchmark_run_writeback_contract="
        "loopx_worker_benchmark_run_writeback_contract_v0"
    ) in command, command
    assert (
        "loopx_counter_trace_json="
        "/logs/agent/loopx-counter-trace.jsonl"
    ) in command, command
    assert sum("loopx_benchmark_run_json=" in arg for arg in command) == 1, command
    assert "--upload" not in command and "--share-org" not in command, command
    assert_public_safe(joined)


def assert_active_bridge_preflight_event() -> None:
    from loopx.benchmark import build_terminal_bench_benchmark_run
    from loopx.status import compact_benchmark_run

    event = build_terminal_bench_benchmark_run(
        mode="codex-loopx",
        preflight_guard=True,
        active_cli_bridge_preflight=True,
        preflight_surface={
            "runner_surface": {
                "uvx_cli_present": True,
                "uvx_version_probe_ok": True,
                "runner_binary_resolution_policy": (
                    "prepend_probe_path_or_use_resolved_runner_binary_for_private_runs"
                ),
            },
            "execution_surface": {
                "docker_cli_present": True,
                "docker_server_available": True,
            },
            "codex_surface": {
                "codex_cli_present": True,
                "codex_version_probe_ok": True,
                "auth_values_read": False,
            },
            "boundary": {
                "no_upload": True,
                "submit_eligible": False,
            },
        },
    )
    compact = compact_benchmark_run(event)
    assert compact is not None, event
    preview_command = event["managed_runner_command_preview"]
    assert "--agent-timeout-multiplier" in preview_command, preview_command
    assert (
        preview_command[preview_command.index("--agent-timeout-multiplier") + 1] == "8"
    ), preview_command
    launch_summary = event["private_runner_launch_summary"]
    assert launch_summary["schema_version"] == "terminal_bench_private_runner_launch_summary_v0", launch_summary
    assert launch_summary["uses_private_runner_env"] is True, launch_summary
    assert launch_summary["argv_binary_resolved_for_private_launch"] is True, launch_summary
    assert launch_summary["env_probe_path_coverage_count"] == 3, launch_summary
    assert launch_summary["no_upload_boundary"] is True, launch_summary
    assert launch_summary["raw_env_recorded"] is False, launch_summary
    assert (
        launch_summary["closeout_command_templates"]["run_ledger_update"] is True
    ), launch_summary
    assert compact["mode"] == "codex_loopx_active_cli_bridge_preflight", compact
    compact_launch = compact["private_runner_launch_summary"]
    assert compact_launch["uses_private_runner_env"] is True, compact_launch
    assert compact_launch["argv_binary_resolved_for_private_launch"] is True, compact_launch
    assert compact_launch["env_probe_path_coverage_count"] == 3, compact_launch
    assert compact_launch["raw_env_recorded"] is False, compact_launch
    assert (
        compact_launch["closeout_command_templates"]["run_ledger_update"] is True
    ), compact_launch
    assert (
        "--update-run-ledger"
        in compact_launch["closeout_command_templates"]["argv_template"]
    ), compact_launch
    assert compact["loopx_cli_bridge_surface"] == "codex_worker_loopx_cli_bridge_v0", compact
    assert compact["loopx_worker_cli_bridge_available"] is True, compact
    assert compact["loopx_worker_cli_bridge_trace_observed"] is False, compact
    assert compact["runner_loopx_cli_call_total"] == 0, compact
    assert compact["worker_loopx_cli_call_total"] == 0, compact
    assert compact["planned_worker_loopx_cli_call_total"] == 2, compact
    assert compact["required_worker_loopx_cli_call_total_min"] == 1, compact
    assert (
        compact["episode_policy"]["mode"]
        == "single_codex_agent_loopx_assisted_checkpoints"
    ), compact
    assert compact["episode_policy"]["does_not_spawn_additional_agents"] is True, compact
    counters = compact["interaction_counters"]
    assert counters["loopx_cli_calls"]["total"] == 0, counters
    assert counters["case_result_writeback"] == "not_observed_active_cli_bridge_preflight", counters
    assert counters["counter_trust_level"] == "active_bridge_preflight_no_worker_trace", counters
    guard = compact["preflight_guard"]
    assert guard["schema_version"] == "terminal_bench_codex_loopx_active_cli_bridge_preflight_v0", guard
    assert guard["active_cli_bridge_enabled"] is True, guard
    assert guard["runner_binary_resolution_policy"] == (
        "prepend_probe_path_or_use_resolved_runner_binary_for_private_runs"
    ), guard
    assert guard["uvx_cli_present"] is True, guard
    assert guard["uvx_version_probe_ok"] is True, guard
    assert guard["docker_cli_present"] is True, guard
    assert guard["docker_server_available"] is True, guard
    assert guard["codex_cli_present"] is True, guard
    assert guard["codex_version_probe_ok"] is True, guard
    assert guard["claim_requires_worker_cli_calls"] is True, guard
    assert guard["required_worker_loopx_cli_call_total_min"] == 1, guard
    claim_gate = compact["claim_gate"]
    assert claim_gate["schema_version"] == "terminal_bench_loopx_claim_gate_v0", claim_gate
    assert claim_gate["requires_worker_loopx_cli_calls"] is True, claim_gate
    assert claim_gate["reject_runner_bridge_calls_as_in_case_evidence"] is True, claim_gate
    assert claim_gate["reject_codex_runtime_goal_tool_calls_as_loopx_evidence"] is True, claim_gate
    assert_public_safe(compact)


def assert_cli_help_exposes_active_bridge_flag() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "benchmark",
            "run",
            "terminal-bench",
            "--help",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "--active-cli-bridge" in result.stdout, result.stdout
    assert "--worker-materialization-probe-only" in result.stdout, result.stdout


def main() -> None:
    assert_doc_contract()
    assert_active_bridge_prompt_and_metadata()
    assert_no_packet_ablation_prompt_and_metadata()
    assert_hardened_baseline_prompt_and_metadata()
    assert_active_bridge_run_finally_checkpoint_on_agent_error()
    assert_active_bridge_preflight_failure_writes_startup_blocker()
    assert_active_bridge_install_failure_writes_startup_blocker()
    assert_default_worker_paths_map_to_logs_dir_for_install_blocker()
    assert_baseline_require_existing_writes_setup_diagnostic()
    assert_agent_codex_install_split_stage_routes_blocker()
    assert_require_existing_codex_version_probe_blocker()
    assert_require_existing_codex_preflight_success_contract()
    assert_worker_materialization_probe_accepts_require_existing_success()
    assert_managed_codex_install_hardening_contract()
    assert_agent_node_runtime_path_repair_uses_existing_npm()
    assert_worker_materialization_probe_only_contract()
    assert_harbor_command_preview()
    assert_active_bridge_preflight_event()
    assert_cli_help_exposes_active_bridge_flag()
    print("terminal-bench-codex-loopx-active-cli-bridge-smoke ok worker_cli_calls=2")


if __name__ == "__main__":
    main()
