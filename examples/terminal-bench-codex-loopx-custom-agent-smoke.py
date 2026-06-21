#!/usr/bin/env python3
"""Smoke-test codex_loopx custom-agent prompt and counters."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-codex-loopx-custom-agent-v0.md"
README = TOPIC_DIR / "README.md"
MANAGED_AGENT_SMOKE = REPO_ROOT / "examples" / "terminal-bench-managed-codex-custom-agent-smoke.py"

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
    "Terminal-Bench Codex LoopX Custom Agent V0",
    "loopx_mode=codex_loopx",
    "LoopX Access Packet V0",
    "loopx_interface_surface: prompt_packet_only_no_cli_bridge",
    "loopx_cli_bridge_available: false",
    "loopx_cli_bridge_contract: terminal_bench_loopx_cli_bridge_contract_v0",
    "declared_loopx_interface_commands",
    "extract_loopx_interaction_counters_from_trace",
    "counter_trust_level=compact_trace_audited",
    "runtime_metadata_prompt_only_no_cli_bridge",
    "--agent-kwarg loopx_mode=codex_loopx",
    "python3 examples/terminal-bench-codex-loopx-custom-agent-smoke.py",
]


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 22000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-codex-loopx-custom-agent-v0.md" in readme, readme
    assert_public_safe(text)


def helper_module() -> Any:
    return load_module(MANAGED_AGENT_SMOKE, "terminal_bench_managed_codex_custom_agent_smoke_helper")


def counter_trace() -> list[dict[str, str]]:
    return [
        {"kind": "loopx_cli_call", "command": "status"},
        {"kind": "loopx_cli_call", "command": "quota_should_run"},
        {"kind": "loopx_cli_call", "command": "todo_list"},
        {"kind": "loopx_cli_call", "command": "history"},
        {"kind": "loopx_cli_call", "command": "check"},
        {"kind": "loopx_cli_call", "command": "append_benchmark_run"},
        {"kind": "loopx_state_read", "surface": "status"},
        {"kind": "loopx_state_read", "surface": "quota"},
        {"kind": "loopx_state_read", "surface": "todo"},
        {"kind": "loopx_state_read", "surface": "history"},
        {"kind": "loopx_state_write", "action": "append_benchmark_run"},
        {"kind": "codex_runtime_goal_tool_call", "name": "create_goal"},
        {"kind": "case_result_writeback", "target": "worker_loopx_writeback"},
    ]


def assert_counters(counters: dict[str, Any]) -> None:
    assert counters["schema_version"] == "terminal_bench_loopx_interaction_counters_v0", counters
    assert counters["prompt_policy_injected"] is True, counters
    assert counters["harness_skill_or_packet_injected"] is True, counters
    assert counters["codex_runtime_goal_tool_calls"]["create_goal"] == 1, counters
    assert counters["codex_runtime_goal_tool_calls"]["update_goal"] == 0, counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 1, counters
    assert counters["loopx_cli_calls"]["total"] == 6, counters
    assert counters["loopx_cli_calls"]["status"] == 1, counters
    assert counters["loopx_cli_calls"]["append_benchmark_run"] == 1, counters
    assert counters["loopx_state_reads"] == 4, counters
    assert counters["loopx_state_writes"] == 1, counters
    assert counters["case_result_writeback"] == "worker_loopx_writeback", counters
    assert counters["counter_trust_level"] == "compact_trace_audited", counters
    assert counters["raw_trace_recorded"] is False, counters
    assert counters["raw_task_prompt_recorded"] is False, counters
    assert_public_safe(counters)


def assert_command_preview() -> None:
    from loopx.benchmark import (
        build_terminal_bench_benchmark_run,
        build_terminal_bench_managed_harbor_command,
    )

    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        job_name="terminal_bench_sample_build_cython_ext_codex_loopx_pilot",
    )
    assert "loopx_mode=codex_loopx" in command, command
    assert "loopx_goal_id=<goal-id>" in command, command
    assert "--upload" not in command, command
    assert "--share-org" not in command, command

    event = build_terminal_bench_benchmark_run(mode="codex-loopx")
    preview = event["managed_runner_command_preview"]
    assert "loopx_mode=codex_loopx" in preview, preview
    assert event["real_run"] is False, event
    assert event["submit_eligible"] is False, event
    assert_public_safe({"command": command, "event": event})


def assert_prompt_and_metadata() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        loopx_mode="codex_loopx",
        goal_id="terminal-bench-fixture",
    )
    assert "LoopX Access Packet V0" in instruction, instruction
    assert "mode: codex_loopx" in instruction, instruction
    assert "available_loopx_interfaces" not in instruction, instruction
    assert "loopx_interface_surface: prompt_packet_only_no_cli_bridge" in instruction, instruction
    assert "loopx_cli_bridge_available: false" in instruction, instruction
    assert "loopx_cli_bridge_contract: terminal_bench_loopx_cli_bridge_contract_v0" in instruction, instruction
    assert "declared_loopx_interface_commands" in instruction, instruction
    assert "create_goal" not in instruction, instruction
    assert task in instruction, instruction

    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        loopx_mode="codex_loopx",
        loopx_goal_id="terminal-bench-fixture",
        loopx_counter_trace=counter_trace(),
    )
    context = helper.FakeAgentContext()
    asyncio.run(agent.run(task, object(), context))
    assert agent.received_instruction is not None
    assert "LoopX Access Packet V0" in agent.received_instruction
    assert context.is_empty(), context.metadata

    agent.populate_context_post_run(context)
    loopx = context.metadata["loopx"]
    assert loopx["mode"] == "codex_loopx", loopx
    assert loopx["loopx_access_packet_injected"] is True, loopx
    assert loopx["loopx_access_packet_schema_version"] == "terminal_bench_loopx_access_packet_v0", loopx
    assert loopx["loopx_interface_surface"] == "prompt_packet_only_no_cli_bridge", loopx
    assert loopx["loopx_cli_bridge_available"] is False, loopx
    assert loopx["loopx_cli_bridge_contract"] == "terminal_bench_loopx_cli_bridge_contract_v0", loopx
    assert loopx["loopx_prompt_only_until_cli_bridge"] is True, loopx
    assert loopx["available_loopx_interface_commands"] == [], loopx
    assert set(loopx["declared_loopx_interface_commands"]) == {
        "status",
        "quota_should_run",
        "todo_list",
        "history",
        "check",
        "append_benchmark_run",
    }, loopx
    assert loopx["raw_interaction_trace_recorded"] is False, loopx
    assert loopx["raw_managed_prompt_recorded"] is False, loopx
    assert loopx["context_post_run_ingested"] is True, loopx
    assert loopx["loopx_counter_trace_schema_version"] == "terminal_bench_loopx_counter_trace_v0", loopx
    assert_counters(loopx["loopx_interaction_counters"])
    assert_public_safe(loopx)

    prompt_only_agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        loopx_mode="codex_loopx",
        loopx_goal_id="terminal-bench-fixture",
    )
    prompt_only_context = helper.FakeAgentContext()
    asyncio.run(prompt_only_agent.run(task, object(), prompt_only_context))
    prompt_only_agent.populate_context_post_run(prompt_only_context)
    prompt_only_counters = prompt_only_context.metadata["loopx"][
        "loopx_interaction_counters"
    ]
    assert prompt_only_counters["loopx_cli_calls"]["total"] == 0, prompt_only_counters
    assert prompt_only_counters["case_result_writeback"] == "not_observed_prompt_only_no_cli_bridge", prompt_only_counters
    assert prompt_only_counters["counter_trust_level"] == "runtime_metadata_prompt_only_no_cli_bridge", prompt_only_counters
    assert_public_safe(prompt_only_context.metadata["loopx"])


def assert_active_user_private_observe_prompt() -> None:
    helper = helper_module()
    module = helper.load_agent_module()
    task = "Build the extension and make the test pass."
    observe_command = (
        "PYTHONPATH=/loopx-source python3 -m loopx.cli "
        "worker-bridge active-user-observe "
        "--feed-jsonl /loopx-active-user/loopx-active-user-interventions.jsonl "
        "--worker-start-seq <worker-start-seq> "
        "--observation-json /loopx-active-user/loopx-active-user-observation.json "
        "--format json"
    )
    instruction = module.build_managed_terminal_bench_instruction(
        task,
        loopx_mode="codex_loopx",
        goal_id="terminal-bench-active-user-fixture",
        loopx_cli_bridge_enabled=True,
        loopx_classification="terminal_bench_active_user_fixture_v0",
        loopx_active_user_intervention_enabled=True,
        loopx_active_user_feed_jsonl=(
            "/loopx-active-user/loopx-active-user-interventions.jsonl"
        ),
        loopx_active_user_observation_json=(
            "/loopx-active-user/loopx-active-user-observation.json"
        ),
        loopx_active_user_observe_command=observe_command,
    )
    assert "Active-user observe checkpoint for this case:" in instruction, instruction
    assert "Before broad task work, run this exact command once:" in instruction, instruction
    assert "--worker-start-seq 0" in instruction, instruction
    assert "<worker-start-seq>" not in instruction, instruction
    assert "<active-user-observe-command-redacted>" in instruction, instruction
    assert "command=active_user_observe" in instruction, instruction
    assert '"command": "active_user_observe"' in instruction, instruction
    assert "active_user_worker_must_poll_after_start: true" in instruction, instruction
    assert_public_safe(instruction)

    counters = module.extract_loopx_interaction_counters_from_trace(
        [
            {
                "kind": "loopx_cli_call",
                "command": "active_user_observe",
                "ok": True,
                "goal_id": "terminal-bench-active-user-fixture",
                "mode": "codex_loopx",
                "classification": "terminal_bench_active_user_fixture_v0",
            }
        ],
        prompt_policy_injected=True,
        harness_skill_or_packet_injected=True,
    )
    assert counters["loopx_cli_calls"]["active_user_observe"] == 1, counters
    assert counters["loopx_cli_calls"]["total"] == 1, counters
    assert counters["loopx_state_reads"] == 1, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["counter_trust_level"] == "compact_trace_audited", counters
    assert_public_safe(counters)


def assert_active_user_launch_kwargs_consumed() -> None:
    from loopx.worker_bridge import (
        WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION,
        build_worker_bridge_install_contract,
    )

    helper = helper_module()
    module = helper.load_agent_module()
    contract = build_worker_bridge_install_contract(
        classification="terminal_bench_active_user_fixture_v0",
        active_user_host_dir="<active-user-host-dir>",
    )
    agent_kwargs = dict(contract["agent_kwargs"])
    agent = module.GoalHarnessManagedCodex(
        logs_dir=Path("logs"),
        model_name="gpt-5.5",
        loopx_mode="codex_loopx",
        loopx_goal_id="terminal-bench-active-user-fixture",
        loopx_cli_bridge_enabled=True,
        loopx_active_user_intervention_enabled=True,
        **agent_kwargs,
    )
    leaked = sorted(
        key for key in agent.kwargs if str(key).startswith("loopx_")
    )
    assert leaked == [], leaked
    assert agent.loopx_benchmark_run_schema_version == "benchmark_run_v0", (
        agent.__dict__
    )
    assert (
        agent.loopx_benchmark_run_writeback_contract
        == WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION
    ), agent.__dict__
    context = helper.FakeAgentContext()
    asyncio.run(
        agent.run("Build the extension and make the test pass.", object(), context)
    )
    agent.populate_context_post_run(context)
    metadata = context.metadata["loopx"]
    assert metadata["loopx_benchmark_run_schema_version"] == "benchmark_run_v0", (
        metadata
    )
    assert (
        metadata["loopx_benchmark_run_writeback_contract"]
        == WORKER_BRIDGE_BENCHMARK_RUN_WRITEBACK_CONTRACT_VERSION
    ), metadata
    assert_public_safe(metadata)


def main() -> None:
    assert_doc_contract()
    assert_command_preview()
    assert_prompt_and_metadata()
    assert_active_user_private_observe_prompt()
    assert_active_user_launch_kwargs_consumed()
    print(
        "terminal-bench-codex-loopx-custom-agent-smoke ok "
        "cli_calls=6 runtime_goal_calls=1 active_user_observe=1 "
        "launch_kwargs=consumed"
    )


if __name__ == "__main__":
    main()
