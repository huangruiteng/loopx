#!/usr/bin/env python3
"""Smoke-test the Terminal-Bench LoopX access packet fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION,
    TERMINAL_BENCH_LOOPX_INTERFACE_SURFACE,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_loopx_access_packet,
    build_terminal_bench_loopx_access_packet_fixture,
    build_terminal_bench_managed_harbor_command,
)
from loopx.status import compact_benchmark_run  # noqa: E402


TOPIC_DIR = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"
DOC = TOPIC_DIR / "terminal-bench-loopx-access-packet-v0.md"
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
    "Terminal-Bench LoopX Access Packet V0",
    "codex_loopx",
    "create_goal",
    "update_goal",
    "LoopX Access Packet V0",
    "loopx_interface_surface: prompt_packet_only_no_cli_bridge",
    "loopx_cli_bridge_available: false",
    "loopx_cli_bridge_contract: terminal_bench_loopx_cli_bridge_contract_v0",
    "declared_loopx_interface_commands",
    "loopx_cli_calls.total=0",
    "terminal_bench_loopx_access_packet_fixture_v0",
    "loopx_actual_use_observed=false",
    "interaction_counters",
    "compact `benchmark_run_v0` counter projection",
    "python3 examples/terminal-bench-loopx-access-packet-smoke.py",
]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 18000, len(text)


def assert_doc_contract() -> None:
    text = DOC.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_DOC_SNIPPETS if snippet not in text]
    assert not missing, missing
    assert "terminal-bench-loopx-access-packet-v0.md" in readme, readme
    assert_public_safe(text)


def assert_packet(packet: str) -> None:
    assert packet.startswith("LoopX Access Packet V0"), packet
    assert "packet_mode: full" in packet, packet
    for command in TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS:
        assert command in packet, packet
    assert "available_loopx_interfaces" not in packet, packet
    assert f"loopx_interface_surface: {TERMINAL_BENCH_LOOPX_INTERFACE_SURFACE}" in packet, packet
    assert "loopx_cli_bridge_available: false" in packet, packet
    assert f"loopx_cli_bridge_contract: {TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION}" in packet, packet
    assert "declared_loopx_interface_commands" in packet, packet
    assert "create_goal" not in packet, packet
    assert "update_goal" not in packet, packet
    assert "hardcoded_tool_call" in packet, packet
    assert_public_safe(packet)


def assert_compact_bridge_packet() -> None:
    packet = build_terminal_bench_loopx_access_packet(
        packet_mode=TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
        cli_bridge_available=True,
    )
    assert packet.startswith("LoopX Access Packet V0"), packet
    assert "packet_mode: compact" in packet, packet
    assert "loopx_cli_bridge_available: true" in packet, packet
    assert "loopx_cli_bridge_command_check:" in packet, packet
    assert "loopx_cli_bridge_command_append_benchmark_run:" in packet, packet
    assert "loopx_cli_bridge_command_status:" not in packet, packet
    assert "loopx_cli_bridge_command_quota_should_run:" not in packet, packet
    assert "loopx_cli_bridge_command_todo_list:" not in packet, packet
    assert "loopx_cli_bridge_command_history:" not in packet, packet
    assert "loopx_access_packet_compact_mode: true" in packet, packet
    assert "optional_status_quota_todo_history_commands_omitted_from_prompt: true" in packet, packet
    assert "runner_side_archive_remains_authoritative_for_final_outcome: true" in packet, packet
    assert "loopx_cli_bridge_default_required_calls: check,append_benchmark_run" in packet, packet
    assert (
        "worker_benchmark_run_json_required_fixed_fields: "
        "real_run=true,submit_eligible=false,leaderboard_evidence=false"
    ) in packet, packet
    assert (
        "worker_benchmark_run_json_submit_eligible_must_be_false: true"
        in packet
    ), packet
    assert (
        "worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true"
        in packet
    ), packet
    assert "do_not_call_status_quota_todo_history_by_default: true" not in packet, packet
    assert_public_safe(packet)


def assert_compact_runner_kwarg() -> None:
    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        loopx_access_packet_mode=(
            TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT
        ),
    )
    assert "loopx_access_packet_mode=compact" in command, command
    assert "loopx_cli_bridge_enabled=true" in command, command
    assert_public_safe(command)


def assert_none_packet_mode() -> None:
    packet = build_terminal_bench_loopx_access_packet(
        packet_mode=TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE,
        cli_bridge_available=True,
    )
    assert packet.startswith("LoopX Access Packet V0"), packet
    assert "packet_mode: none" in packet, packet
    assert "loopx_access_packet_disabled: true" in packet, packet
    assert "loopx_interface_surface: none_runner_archive_only" in packet, packet
    assert "loopx_cli_bridge_available: false" in packet, packet
    assert "loopx_cli_bridge_contract: none" in packet, packet
    assert "worker_receives_no_loopx_cli_templates: true" in packet, packet
    assert "worker_receives_no_loopx_access_packet: true" in packet, packet
    assert "loopx_cli_bridge_command_check:" not in packet, packet
    assert "loopx_cli_bridge_command_append_benchmark_run:" not in packet, packet

    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        loopx_access_packet_mode=(
            TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_NONE
        ),
    )
    assert "loopx_access_packet_mode=none" in command, command
    assert "loopx_cli_bridge_enabled=true" in command, command
    assert_public_safe(packet)
    assert_public_safe(command)


def assert_counter_payload(counters: dict[str, Any]) -> None:
    assert counters["schema_version"] == "terminal_bench_loopx_interaction_counters_v0", counters
    assert counters["prompt_policy_injected"] is True, counters
    assert counters["harness_skill_or_packet_injected"] is True, counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 0, counters
    assert counters["loopx_cli_calls"]["total"] == 0, counters
    assert counters["loopx_state_reads"] == 0, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["raw_trace_recorded"] is False, counters
    assert counters["raw_task_prompt_recorded"] is False, counters
    assert_public_safe(counters)


def assert_fixture() -> None:
    fixture = build_terminal_bench_loopx_access_packet_fixture()
    assert fixture["schema_version"] == "terminal_bench_loopx_access_packet_fixture_v0", fixture
    assert fixture["arm"] == "codex_loopx", fixture
    packet = fixture["access_packet"]
    assert packet["interface_surface"] == TERMINAL_BENCH_LOOPX_INTERFACE_SURFACE, packet
    assert packet["loopx_interfaces_available"] is False, packet
    assert packet["loopx_cli_bridge_available"] is False, packet
    assert packet["loopx_cli_bridge_contract"] == TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION, packet
    assert packet["prompt_packet_only_until_cli_bridge"] is True, packet
    assert packet["hardcoded_tool_call_required"] is False, packet
    assert packet["worker_may_choose_when_to_call"] is True, packet
    assert packet["interfaces_available"] == [], packet
    assert set(packet["interfaces_declared"]) == set(TERMINAL_BENCH_LOOPX_ACCESS_PACKET_COMMANDS), packet

    mode_contract = fixture["mode_contract"]
    assert mode_contract["loopx_inside_case"] is True, mode_contract
    assert mode_contract["case_semantics_changed_by_harness"] is True, mode_contract
    assert mode_contract["official_score_comparable_to_native_codex"] is False, mode_contract
    assert mode_contract["loopx_actual_use_observed"] is False, mode_contract
    assert mode_contract["loopx_interface_surface"] == TERMINAL_BENCH_LOOPX_INTERFACE_SURFACE, mode_contract
    assert mode_contract["loopx_cli_bridge_available"] is False, mode_contract
    assert mode_contract["worker_trace_observed"] is False, mode_contract

    boundary = fixture["boundary"]
    assert boundary["real_run"] is False, boundary
    assert boundary["submit_eligible"] is False, boundary
    assert boundary["raw_sessions_recorded"] is False, boundary
    assert boundary["host_paths_recorded"] is False, boundary

    assert_counter_payload(fixture["interaction_counters"])
    assert_public_safe(fixture)


def assert_compact_projection() -> None:
    event = build_terminal_bench_benchmark_run(mode="loopx-managed-codex")
    compact = compact_benchmark_run(event)
    assert compact, event
    counters = compact.get("interaction_counters")
    assert isinstance(counters, dict), compact
    assert counters["prompt_policy_injected"] is True, counters
    assert counters["harness_skill_or_packet_injected"] is False, counters
    assert counters["codex_runtime_goal_tool_calls"]["total"] == 0, counters
    assert counters["loopx_cli_calls"]["total"] == 0, counters
    assert counters["loopx_state_reads"] == 0, counters
    assert counters["loopx_state_writes"] == 0, counters
    assert counters["case_result_writeback"] == "runner_only", counters
    assert_public_safe(compact)


def main() -> None:
    assert_doc_contract()
    assert_packet(build_terminal_bench_loopx_access_packet())
    assert_compact_bridge_packet()
    assert_compact_runner_kwarg()
    assert_none_packet_mode()
    assert_fixture()
    assert_compact_projection()
    print("terminal-bench-loopx-access-packet-smoke ok cli_calls=0 compact_counters=1")


if __name__ == "__main__":
    main()
