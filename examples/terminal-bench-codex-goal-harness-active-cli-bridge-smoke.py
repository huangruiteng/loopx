#!/usr/bin/env python3
"""Smoke-test codex_goal_harness active worker CLI bridge packet."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HELPER = REPO_ROOT / "examples" / "terminal-bench-managed-codex-custom-agent-smoke.py"
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-codex-goal-harness-active-cli-bridge-v0.md"
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
    "Terminal-Bench Codex Goal Harness Active CLI Bridge V0",
    "goal_harness_cli_bridge_enabled=true",
    "codex_worker_goal_harness_cli_bridge_v0",
    "goal_harness_cli_bridge_available: true",
    "goal_harness_cli_bridge_command_status",
    "goal_harness_cli_bridge_command_append_benchmark_run",
    "goal_harness_counter_trace_jsonl",
    "goal_harness_benchmark_run_writeback_contract",
    "worker_benchmark_run_json_schema_version: benchmark_run_v0",
    "worker_benchmark_run_json_top_level_must_be_schema_version: true",
    "do_not_wrap_worker_benchmark_run_json_in_benchmark_run_key: true",
    "worker_benchmark_run_json_minimal_shape",
    "run_finally_worker_benchmark_run_checkpoint: true",
    "goal_harness_cli_bridge_call_policy_mode: lean_preflight_check_and_final_append",
    "goal_harness_cli_bridge_placeholder_policy_version: terminal_bench_goal_harness_cli_bridge_placeholder_policy_v0",
    "goal_harness_cli_bridge_command_templates_require_placeholder_substitution: true",
    "do_not_execute_goal_harness_cli_command_with_unresolved_angle_bracket_placeholders: true",
    "do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true",
    "do_not_call_status_quota_todo_history_by_default: true",
    "if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once",
    "single_codex_agent_goal_harness_assisted_checkpoints",
    "do_not_spawn_additional_agents_for_episodes: true",
    "--mounts",
    "<goal-harness-project-root>",
    "PYTHONPATH='<goal-harness-project-root>' python3 -m goal_harness.cli",
    "/logs/agent/goal-harness-counter-trace.jsonl",
    "worker_goal_harness_cli_calls.total>=1",
    "planned_worker_goal_harness_cli_call_total=2",
    "runner_goal_harness_cli_calls.total=0",
    "--preflight-guard --active-cli-bridge",
    "private_runner_launch_summary",
    "terminal_bench_goal_harness_claim_gate_v0",
    "python3 examples/terminal-bench-codex-goal-harness-active-cli-bridge-smoke.py",
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
    assert "terminal-bench-codex-goal-harness-active-cli-bridge-v0.md" in readme, readme
    assert_public_safe(text)


def counter_trace() -> list[dict[str, Any]]:
    return [
        {
            "kind": "goal_harness_cli_call",
            "command": "check",
            "ok": True,
            "goal_id": "terminal-bench-fixture",
            "mode": "codex_goal_harness",
            "classification": "terminal_bench_fixture_active_bridge_v0",
        },
        {
            "kind": "goal_harness_cli_call",
            "command": "append_benchmark_run",
            "ok": True,
            "dry_run": True,
            "goal_id": "terminal-bench-fixture",
            "mode": "codex_goal_harness",
            "classification": "terminal_bench_fixture_active_bridge_v0",
        },
        {"kind": "goal_harness_state_read", "surface": "check"},
    ]


def assert_active_bridge_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        goal_harness_mode="codex_goal_harness",
        goal_id="terminal-bench-fixture",
        goal_harness_cli_bridge_enabled=True,
    )
    assert "Goal Harness Access Packet V0" in instruction, instruction
    assert "goal_harness_interface_surface: codex_worker_goal_harness_cli_bridge_v0" in instruction, instruction
    assert "goal_harness_cli_bridge_available: true" in instruction, instruction
    assert "goal_harness_cli_bridge_command_status:" in instruction, instruction
    assert "goal_harness_cli_bridge_command_quota_should_run:" in instruction, instruction
    assert "goal_harness_cli_bridge_command_todo_list:" in instruction, instruction
    assert "goal_harness_cli_bridge_command_history:" in instruction, instruction
    assert "goal_harness_cli_bridge_command_check:" in instruction, instruction
    assert "goal_harness_cli_bridge_command_append_benchmark_run:" in instruction, instruction
    assert "goal_harness_counter_trace_jsonl:" in instruction, instruction
    assert "goal_harness_benchmark_run_json:" in instruction, instruction
    assert (
        "goal_harness_benchmark_run_writeback_contract: "
        "goal_harness_worker_benchmark_run_writeback_contract_v0"
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
    assert "worker_benchmark_run_json_must_omit:" in instruction, instruction
    assert "raw_task_prompt" in instruction and "credential_values" in instruction, instruction
    assert (
        "if_append_benchmark_run_schema_rejected_rewrite_minimal_benchmark_run_v0_and_retry_once: true"
        in instruction
    ), instruction
    assert (
        "goal_harness_cli_bridge_call_policy_mode: lean_preflight_check_and_final_append"
        in instruction
    ), instruction
    assert "goal_harness_cli_bridge_default_required_calls: check,append_benchmark_run" in instruction, instruction
    assert (
        "goal_harness_cli_bridge_command_templates_require_placeholder_substitution: true"
        in instruction
    ), instruction
    assert (
        "do_not_execute_goal_harness_cli_command_with_unresolved_angle_bracket_placeholders: true"
        in instruction
    ), instruction
    assert (
        "do_not_call_append_benchmark_run_before_final_validation_cleanup_or_blocker_decision: true"
        in instruction
    ), instruction
    assert "do_not_call_status_quota_todo_history_by_default: true" in instruction, instruction
    assert (
        "before_long_actions_call_goal_harness_status_quota_todo_history_check: true"
        not in instruction
    ), instruction
    assert "episode_policy: single_codex_agent_goal_harness_assisted_checkpoints" in instruction, instruction
    assert "episode_checkpoint_scope: same_codex_agent_compact_evidence" in instruction, instruction
    assert "do_not_spawn_additional_agents_for_episodes: true" in instruction, instruction
    assert "after_each_goal_harness_cli_call_append_compact_jsonl_to_trace: true" in instruction, instruction
    assert "goal_harness_counter_trace_row_required_fields: event,command,ok,goal_id,mode,classification" in instruction, instruction
    assert "goal_harness_counter_trace_context_goal_id: terminal-bench-fixture" in instruction, instruction
    assert "goal_harness_counter_trace_context_mode: codex_goal_harness" in instruction, instruction
    assert "emit_compact_counter_trace_for_each_goal_harness_cli_call: true" in instruction, instruction
    assert "<goal-harness-project-root>" in instruction, instruction
    assert "<goal-harness-runtime-root>" in instruction, instruction
    assert "python3 -m goal_harness.cli" in instruction, instruction
    assert "/logs/agent/goal-harness-counter-trace.jsonl" in instruction, instruction
    assert task in instruction, instruction
    assert_public_safe(instruction)

    with tempfile.TemporaryDirectory(prefix="goal-harness-counter-trace-") as tmp:
        trace_path = Path(tmp) / "counter-trace.jsonl"
        benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
        agent = module.GoalHarnessManagedCodex(
            logs_dir=Path("logs"),
            model_name="gpt-5.5",
            goal_harness_mode="codex_goal_harness",
            goal_harness_goal_id="terminal-bench-fixture",
            goal_harness_cli_bridge_enabled=True,
            goal_harness_benchmark_run_json=str(benchmark_run_path),
            goal_harness_counter_trace_json=str(trace_path),
        )
        context = helper.FakeAgentContext()
        asyncio.run(agent.run(task, object(), context))
        assert agent.received_instruction is not None
        assert "goal_harness_cli_bridge_available: true" in agent.received_instruction
        assert "goal_harness_counter_trace_jsonl:" in agent.received_instruction
        assert context.is_empty(), context.metadata

        trace_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in counter_trace()),
            encoding="utf-8",
        )
        loaded_trace = module.load_goal_harness_counter_trace_file(trace_path)
        assert loaded_trace[0]["goal_id"] == "terminal-bench-fixture", loaded_trace
        assert loaded_trace[0]["mode"] == "codex_goal_harness", loaded_trace
        assert (
            loaded_trace[0]["classification"]
            == "terminal_bench_fixture_active_bridge_v0"
        ), loaded_trace
        agent.populate_context_post_run(context)
        assert benchmark_run_path.exists(), benchmark_run_path
        benchmark_run = json.loads(benchmark_run_path.read_text(encoding="utf-8"))
        from goal_harness.status import compact_benchmark_run

        compact_run = compact_benchmark_run(benchmark_run)
        assert compact_run is not None, benchmark_run
        assert benchmark_run["schema_version"] == "benchmark_run_v0", benchmark_run
        assert benchmark_run["source_runner"] == "terminal_bench_worker_bridge", benchmark_run
        assert benchmark_run["worker_goal_harness_cli_call_total"] == 2, benchmark_run
        assert benchmark_run["goal_harness_worker_cli_bridge_trace_observed"] is True, benchmark_run
        assert benchmark_run["episode_policy"]["worker_topology"] == "single_codex_agent", benchmark_run
        assert benchmark_run["episode_policy"]["does_not_spawn_additional_agents"] is True, benchmark_run
        outcome = benchmark_run["worker_bridge_outcome"]
        assert outcome["worker_bridge_verified"] is True, benchmark_run
        assert outcome["runner_return_status"] == "pending_after_worker_bridge_success", benchmark_run
        assert outcome["official_score_status"] == "blocked_pending_runner_return", benchmark_run
        assert compact_run["worker_bridge_outcome"]["worker_bridge_verified"] is True, compact_run
        assert compact_run["worker_bridge_outcome"]["worker_goal_harness_cli_call_total"] == 2, compact_run
        assert (
            compact_run["episode_policy"]["mode"]
            == "single_codex_agent_goal_harness_assisted_checkpoints"
        ), compact_run
        assert compact_run["episode_policy"]["does_not_split_task_prompt"] is True, compact_run
        assert compact_run["validation"]["all_passed"] is True, compact_run
        assert_public_safe(benchmark_run)
        assert_public_safe(compact_run)
    goal_harness = context.metadata["goal_harness"]
    assert goal_harness["mode"] == "codex_goal_harness", goal_harness
    assert goal_harness["goal_harness_interface_surface"] == "codex_worker_goal_harness_cli_bridge_v0", goal_harness
    assert goal_harness["goal_harness_cli_bridge_available"] is True, goal_harness
    assert goal_harness["goal_harness_prompt_only_until_cli_bridge"] is False, goal_harness
    assert (
        goal_harness["goal_harness_cli_bridge_call_policy_mode"]
        == "lean_preflight_check_and_final_append"
    ), goal_harness
    assert goal_harness["goal_harness_cli_bridge_default_required_calls"] == [
        "check",
        "append_benchmark_run",
    ], goal_harness
    assert goal_harness["goal_harness_cli_bridge_optional_context_calls"] == [
        "status",
        "quota_should_run",
        "todo_list",
        "history",
    ], goal_harness
    assert goal_harness["goal_harness_cli_bridge_required_call_minimum"] == 1, goal_harness
    assert set(goal_harness["available_goal_harness_interface_commands"]) == {
        "status",
        "quota_should_run",
        "todo_list",
        "history",
        "check",
        "append_benchmark_run",
    }, goal_harness
    assert goal_harness["goal_harness_cli_bridge_command_prefix_present"] is True, goal_harness
    assert goal_harness["goal_harness_counter_trace_jsonl_declared"] is True, goal_harness
    assert goal_harness["goal_harness_counter_trace_file_loaded"] is True, goal_harness
    assert goal_harness["goal_harness_counter_trace_row_count"] == len(counter_trace()), goal_harness
    assert goal_harness["goal_harness_benchmark_run_json_declared"] is True, goal_harness
    assert goal_harness["goal_harness_benchmark_run_json_written"] is True, goal_harness
    assert (
        goal_harness["goal_harness_run_finally_benchmark_run_json_written"] is True
    ), goal_harness
    assert (
        goal_harness["goal_harness_benchmark_run_writeback_status"]
        == "worker_bridge_benchmark_run_written"
    ), goal_harness
    assert goal_harness["goal_harness_worker_cli_call_total"] == 2, goal_harness
    assert goal_harness["goal_harness_worker_benchmark_run_schema_version"] == "benchmark_run_v0", goal_harness
    episode_policy = goal_harness["goal_harness_episode_policy"]
    assert episode_policy["mode"] == "single_codex_agent_goal_harness_assisted_checkpoints", episode_policy
    assert episode_policy["worker_topology"] == "single_codex_agent", episode_policy
    assert episode_policy["does_not_change_task_solution_actor"] is True, episode_policy
    counters = goal_harness["goal_harness_interaction_counters"]
    assert counters["goal_harness_cli_calls"]["total"] == 2, counters
    assert counters["goal_harness_cli_calls"]["check"] == 1, counters
    assert counters["goal_harness_cli_calls"]["append_benchmark_run"] == 1, counters
    assert counters["goal_harness_state_reads"] == 1, counters
    assert counters["goal_harness_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "worker_bridge_append_benchmark_run_dry_run", counters
    assert counters["counter_trust_level"] == "compact_trace_audited", counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 0, counters
    assert_public_safe(goal_harness)


def assert_no_packet_ablation_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        goal_harness_mode="codex_goal_harness",
        goal_id="terminal-bench-fixture",
        goal_harness_cli_bridge_enabled=True,
        goal_harness_access_packet_mode="none",
    )
    assert "Goal Harness access packet for this case" not in instruction, instruction
    assert "Goal Harness Access Packet V0" not in instruction, instruction
    assert "goal_harness_cli_bridge_command_check:" not in instruction, instruction
    assert "goal_harness_cli_bridge_command_append_benchmark_run:" not in instruction, instruction
    assert "Goal Harness operating rules for this case:" in instruction, instruction
    assert task in instruction, instruction
    assert_public_safe(instruction)

    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        goal_harness_mode="codex_goal_harness",
        goal_harness_goal_id="terminal-bench-fixture",
        goal_harness_cli_bridge_enabled=True,
        goal_harness_access_packet_mode="none",
    )
    context = helper.FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction is not None
    assert "Goal Harness Access Packet V0" not in agent.received_instruction
    assert context.is_empty(), context.metadata
    agent.populate_context_post_run(context)
    goal_harness = context.metadata["goal_harness"]
    assert goal_harness["mode"] == "codex_goal_harness", goal_harness
    assert goal_harness["goal_harness_access_packet_mode"] == "none", goal_harness
    assert goal_harness["goal_harness_access_packet_injected"] is False, goal_harness
    assert goal_harness["goal_harness_interface_surface"] == "managed_policy_prompt_only", goal_harness
    assert goal_harness["goal_harness_cli_bridge_available"] is False, goal_harness
    assert goal_harness["goal_harness_cli_bridge_contract"] is None, goal_harness
    assert goal_harness["available_goal_harness_interface_commands"] == [], goal_harness
    assert goal_harness["declared_goal_harness_interface_commands"] == [], goal_harness
    assert goal_harness["goal_harness_access_packet_schema_version"] is None, goal_harness
    assert goal_harness["goal_harness_cli_bridge_default_required_calls"] == [], goal_harness
    assert goal_harness["goal_harness_cli_bridge_required_call_minimum"] == 0, goal_harness
    assert_public_safe(goal_harness)


def assert_hardened_baseline_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        goal_harness_mode="hardened_codex_baseline",
        goal_harness_access_packet_mode="none",
        goal_harness_cli_bridge_enabled=True,
    )
    assert instruction == task, instruction

    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        goal_harness_mode="hardened_codex_baseline",
        goal_harness_access_packet_mode="none",
        goal_harness_cli_bridge_enabled=True,
    )
    context = helper.FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction == task, agent.received_instruction
    assert context.is_empty(), context.metadata
    agent.populate_context_post_run(context)
    goal_harness = context.metadata["goal_harness"]
    assert goal_harness["mode"] == "hardened_codex_baseline", goal_harness
    assert goal_harness["goal_harness_access_packet_mode"] == "none", goal_harness
    assert goal_harness["goal_harness_access_packet_injected"] is False, goal_harness
    assert (
        goal_harness["goal_harness_interface_surface"]
        == "hardened_codex_baseline_no_goal_harness_state"
    ), goal_harness
    assert goal_harness["goal_harness_cli_bridge_available"] is False, goal_harness
    assert goal_harness["case_semantics_changed_by_harness"] is False, goal_harness
    assert goal_harness["goal_harness_inside_case"] is False, goal_harness
    assert goal_harness["official_score_comparable_to_native_codex"] is False, goal_harness
    assert goal_harness["model_plus_harness_pair"] is False, goal_harness
    assert goal_harness["control_plane_score_applicable"] is False, goal_harness
    assert goal_harness["startup_surface_calibration"] is False, goal_harness
    assert goal_harness["hardened_install_surface"] is True, goal_harness
    assert goal_harness["hardened_install_baseline"] is True, goal_harness
    assert goal_harness["official_score_comparable_to_goal_harness_treatment"] is True, goal_harness
    assert goal_harness["task_prompt_changed_by_goal_harness_policy"] is False, goal_harness
    counters = goal_harness["goal_harness_interaction_counters"]
    assert counters["prompt_policy_injected"] is False, counters
    assert counters["harness_skill_or_packet_injected"] is False, counters
    assert counters["goal_harness_cli_calls"]["total"] == 0, counters
    assert counters["goal_harness_state_reads"] == 0, counters
    assert counters["goal_harness_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "hardened_codex_baseline_runner_only", counters
    assert (
        counters["counter_trust_level"]
        == "hardened_codex_baseline_no_goal_harness_state"
    ), counters
    assert_public_safe(goal_harness)


def assert_active_bridge_run_finally_checkpoint_on_agent_error() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    original_run = module.Codex.run

    async def failing_run(self: Any, instruction: str, environment: object, context: Any) -> None:
        self.received_instruction = instruction
        raise RuntimeError("simulated nonzero agent exit")

    module.Codex.run = failing_run
    try:
        with tempfile.TemporaryDirectory(prefix="goal-harness-run-finally-") as tmp:
            benchmark_run_path = Path(tmp) / "worker-benchmark-run.json"
            trace_path = Path(tmp) / "counter-trace.jsonl"
            agent = module.GoalHarnessManagedCodex(
                logs_dir=Path("logs"),
                model_name="gpt-5.5",
                goal_harness_mode="codex_goal_harness",
                goal_harness_goal_id="terminal-bench-fixture",
                goal_harness_cli_bridge_enabled=True,
                goal_harness_benchmark_run_json=str(benchmark_run_path),
                goal_harness_counter_trace_json=str(trace_path),
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

            from goal_harness.status import compact_benchmark_run

            compact = compact_benchmark_run(benchmark_run)
            assert compact is not None, benchmark_run
            assert compact["worker_bridge_outcome"]["worker_bridge_verified"] is False, compact
            assert compact["worker_bridge_outcome"]["wall_time_policy"]["interrupted"] is True, compact
            assert_public_safe(benchmark_run)
            assert_public_safe(compact)
    finally:
        module.Codex.run = original_run


def assert_managed_codex_install_hardening_contract() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    agent = module.GoalHarnessManagedCodex(logs_dir=Path("logs"), model_name="gpt-5.5")

    asyncio.run(agent.install(object()))
    calls = agent.exec_calls
    assert len(calls) == 3, calls
    root_install = calls[0]
    agent_install = calls[1]
    root_symlink = calls[2]
    assert root_install["user"] == "root", calls
    assert agent_install["user"] == "agent", calls
    assert root_symlink["user"] == "root", calls

    root_command = root_install["command"]
    for package in ("bash", "ca-certificates", "curl", "git", "xz-utils", "tar", "gzip", "ripgrep"):
        assert package in root_command, root_command
    assert "apk add --no-cache bash curl nodejs npm ripgrep" in root_command, root_command
    assert root_install["env"] == {"DEBIAN_FRONTEND": "noninteractive"}, root_install

    agent_command = agent_install["command"]
    assert "command -v codex" in agent_command, agent_command
    assert "codex_is_usable()" in agent_command, agent_command
    assert "if codex_is_usable; then" in agent_command, agent_command
    assert "codex --version >/dev/null 2>&1" in agent_command, agent_command
    assert "Codex CLI missing or version check failed" in agent_command, agent_command
    assert "command -v node" in agent_command, agent_command
    assert "command -v npm" in agent_command, agent_command
    assert "NVM failed to install" in agent_command, agent_command
    assert "NVM failed to load" in agent_command, agent_command
    assert "npm install -g @openai/codex@latest" in agent_command, agent_command
    assert "codex --version" in agent_command, agent_command
    assert "hash -r" in agent_command, agent_command

    symlink_command = root_symlink["command"]
    assert "for bin in node npm codex" in symlink_command, symlink_command
    assert "/usr/local/bin/$bin" in symlink_command, symlink_command
    assert_public_safe(root_command + agent_command + symlink_command)


def assert_harbor_command_preview() -> None:
    from goal_harness.benchmark import (
        TERMINAL_BENCH_EXTRA_PROBE_PATHS,
        build_terminal_bench_private_runner_env,
        build_terminal_bench_private_runner_launch,
        build_terminal_bench_managed_harbor_command,
        resolve_terminal_bench_runner_binary,
        summarize_terminal_bench_private_runner_launch,
    )

    command = build_terminal_bench_managed_harbor_command(
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
    )
    baseline_command = build_terminal_bench_managed_harbor_command(
        goal_harness_mode="hardened_codex_baseline",
        goal_harness_ablation_mode="hardened_codex_baseline",
        goal_harness_access_packet_mode="none",
    )
    private_command = build_terminal_bench_managed_harbor_command(
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
        resolve_cli_paths=True,
    )
    local_dataset_command = build_terminal_bench_managed_harbor_command(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
    )
    local_dataset_batch_command = build_terminal_bench_managed_harbor_command(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        task_id=None,
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
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
    assert "goal_harness_cli_bridge_enabled=true" in local_dataset_batch_command, local_dataset_batch_command
    for probe_path in TERMINAL_BENCH_EXTRA_PROBE_PATHS:
        assert str(Path(probe_path).expanduser()) in private_env["PATH"], private_env["PATH"]
    launch = build_terminal_bench_private_runner_launch(
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
    )
    mode_launch = build_terminal_bench_private_runner_launch(
        mode="codex-goal-harness",
        goal_harness_cli_bridge_enabled=True,
    )
    batch_launch = build_terminal_bench_private_runner_launch(
        dataset=str(REPO_ROOT / ".local" / "harbor-datasets" / "terminal-bench-sample-gh-e2e-subset"),
        task_id=None,
        goal_harness_mode="codex_goal_harness",
        goal_harness_cli_bridge_enabled=True,
    )
    active_user_launch = build_terminal_bench_private_runner_launch(
        mode="codex-goal-harness",
        goal_harness_cli_bridge_enabled=True,
        goal_harness_active_user_intervention_enabled=True,
    )
    assert "--include-task-name" not in batch_launch["argv"], batch_launch["argv"]
    assert "--path" in batch_launch["argv"], batch_launch["argv"]
    batch_mounts = json.loads(batch_launch["argv"][batch_launch["argv"].index("--mounts") + 1])
    assert all(Path(mount["source"]).is_absolute() for mount in batch_mounts), batch_mounts
    assert all(Path(mount["target"]).is_absolute() for mount in batch_mounts), batch_mounts
    assert "<goal-harness-project-root>" not in json.dumps(batch_mounts), batch_mounts
    assert "<goal-harness-runtime-root>" not in json.dumps(batch_mounts), batch_mounts
    batch_agent_kwargs = [
        item
        for index, item in enumerate(batch_launch["argv"])
        if index > 0 and batch_launch["argv"][index - 1] == "--agent-kwarg"
    ]
    assert not any("<goal-harness-project-root>" in item for item in batch_agent_kwargs), batch_agent_kwargs
    assert not any("<goal-harness-runtime-root>" in item for item in batch_agent_kwargs), batch_agent_kwargs
    active_user_mounts = json.loads(
        active_user_launch["argv"][active_user_launch["argv"].index("--mounts") + 1]
    )
    assert active_user_mounts[-1]["target"] == "/goal-harness-active-user", active_user_mounts
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
    assert active_user_summary["active_user_writable_mount_requested"] is True, active_user_summary
    assert active_user_summary["active_user_writable_mount_count"] == 1, active_user_summary
    assert active_user_summary["raw_paths_recorded"] is False, active_user_summary
    assert_public_safe(active_user_summary)
    assert_public_safe(launch_summary)
    assert "goal_harness_mode=codex_goal_harness" in command, command
    assert "goal_harness_mode=codex_goal_harness" in mode_launch["argv"], mode_launch["argv"]
    assert "goal_harness_cli_bridge_enabled=true" in mode_launch["argv"], mode_launch["argv"]
    assert "goal_harness_mode=hardened_codex_baseline" in baseline_command, baseline_command
    assert "goal_harness_ablation_mode=hardened_codex_baseline" in baseline_command, baseline_command
    assert "goal_harness_access_packet_mode=none" in baseline_command, baseline_command
    assert "goal_harness_cli_bridge_enabled=true" not in baseline_command, baseline_command
    assert "--mounts" not in baseline_command, baseline_command
    assert_public_safe(" ".join(baseline_command))
    assert "--mounts" in command, command
    mounts = json.loads(command[command.index("--mounts") + 1])
    assert mounts == [
        {
            "read_only": True,
            "source": "<goal-harness-project-root>",
            "target": "<goal-harness-project-root>",
            "type": "bind",
        },
        {
            "read_only": True,
            "source": "<goal-harness-runtime-root>",
            "target": "<goal-harness-runtime-root>",
            "type": "bind",
        },
    ], mounts
    assert "goal_harness_cli_bridge_enabled=true" in command, command
    assert (
        "goal_harness_command_prefix="
        "PYTHONPATH='<goal-harness-project-root>' python3 -m goal_harness.cli"
    ) in command, command
    assert any(
        item.startswith("goal_harness_runtime_preflight_command=")
        and "apt-get install -y python3" in item
        for item in command
    ), command
    assert (
        "goal_harness_registry_arg="
        "<goal-harness-runtime-root>/registry.global.json"
    ) in command, command
    assert "goal_harness_runtime_root_arg=<goal-harness-runtime-root>" in command, command
    assert (
        "goal_harness_scan_path=<goal-harness-project-root>/goal_harness/benchmark.py"
    ) in command, command
    assert (
        "goal_harness_benchmark_run_json="
        "/logs/agent/goal-harness-worker-benchmark-run.json"
    ) in command, command
    assert "goal_harness_benchmark_run_schema_version=benchmark_run_v0" in command, command
    assert (
        "goal_harness_benchmark_run_writeback_contract="
        "goal_harness_worker_benchmark_run_writeback_contract_v0"
    ) in command, command
    assert (
        "goal_harness_counter_trace_json="
        "/logs/agent/goal-harness-counter-trace.jsonl"
    ) in command, command
    assert sum("goal_harness_benchmark_run_json=" in arg for arg in command) == 1, command
    assert "--upload" not in command and "--share-org" not in command, command
    assert_public_safe(joined)


def assert_active_bridge_preflight_event() -> None:
    from goal_harness.benchmark import build_terminal_bench_benchmark_run
    from goal_harness.status import compact_benchmark_run

    event = build_terminal_bench_benchmark_run(
        mode="codex-goal-harness",
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
        preview_command[preview_command.index("--agent-timeout-multiplier") + 1] == "4"
    ), preview_command
    launch_summary = event["private_runner_launch_summary"]
    assert launch_summary["schema_version"] == "terminal_bench_private_runner_launch_summary_v0", launch_summary
    assert launch_summary["uses_private_runner_env"] is True, launch_summary
    assert launch_summary["argv_binary_resolved_for_private_launch"] is True, launch_summary
    assert launch_summary["env_probe_path_coverage_count"] == 3, launch_summary
    assert launch_summary["no_upload_boundary"] is True, launch_summary
    assert launch_summary["raw_env_recorded"] is False, launch_summary
    assert compact["mode"] == "codex_goal_harness_active_cli_bridge_preflight", compact
    compact_launch = compact["private_runner_launch_summary"]
    assert compact_launch["uses_private_runner_env"] is True, compact_launch
    assert compact_launch["argv_binary_resolved_for_private_launch"] is True, compact_launch
    assert compact_launch["env_probe_path_coverage_count"] == 3, compact_launch
    assert compact_launch["raw_env_recorded"] is False, compact_launch
    assert compact["goal_harness_cli_bridge_surface"] == "codex_worker_goal_harness_cli_bridge_v0", compact
    assert compact["goal_harness_worker_cli_bridge_available"] is True, compact
    assert compact["goal_harness_worker_cli_bridge_trace_observed"] is False, compact
    assert compact["runner_goal_harness_cli_call_total"] == 0, compact
    assert compact["worker_goal_harness_cli_call_total"] == 0, compact
    assert compact["planned_worker_goal_harness_cli_call_total"] == 2, compact
    assert compact["required_worker_goal_harness_cli_call_total_min"] == 1, compact
    assert (
        compact["episode_policy"]["mode"]
        == "single_codex_agent_goal_harness_assisted_checkpoints"
    ), compact
    assert compact["episode_policy"]["does_not_spawn_additional_agents"] is True, compact
    counters = compact["interaction_counters"]
    assert counters["goal_harness_cli_calls"]["total"] == 0, counters
    assert counters["case_result_writeback"] == "not_observed_active_cli_bridge_preflight", counters
    assert counters["counter_trust_level"] == "active_bridge_preflight_no_worker_trace", counters
    guard = compact["preflight_guard"]
    assert guard["schema_version"] == "terminal_bench_codex_goal_harness_active_cli_bridge_preflight_v0", guard
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
    assert guard["required_worker_goal_harness_cli_call_total_min"] == 1, guard
    claim_gate = compact["claim_gate"]
    assert claim_gate["schema_version"] == "terminal_bench_goal_harness_claim_gate_v0", claim_gate
    assert claim_gate["requires_worker_goal_harness_cli_calls"] is True, claim_gate
    assert claim_gate["reject_runner_bridge_calls_as_in_case_evidence"] is True, claim_gate
    assert claim_gate["reject_codex_runtime_goal_tool_calls_as_goal_harness_evidence"] is True, claim_gate
    assert_public_safe(compact)


def assert_cli_help_exposes_active_bridge_flag() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "goal_harness.cli",
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


def main() -> None:
    assert_doc_contract()
    assert_active_bridge_prompt_and_metadata()
    assert_no_packet_ablation_prompt_and_metadata()
    assert_hardened_baseline_prompt_and_metadata()
    assert_active_bridge_run_finally_checkpoint_on_agent_error()
    assert_managed_codex_install_hardening_contract()
    assert_harbor_command_preview()
    assert_active_bridge_preflight_event()
    assert_cli_help_exposes_active_bridge_flag()
    print("terminal-bench-codex-goal-harness-active-cli-bridge-smoke ok worker_cli_calls=2")


if __name__ == "__main__":
    main()
