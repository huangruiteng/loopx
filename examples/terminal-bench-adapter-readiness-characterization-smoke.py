#!/usr/bin/env python3
"""Characterize Terminal-Bench adapter readiness before refactoring.

This smoke is intentionally builder-only: it does not launch Harbor,
Terminal-Bench, Docker, Codex, model APIs, uploads, or submissions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE,
    TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
    TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION,
    build_terminal_bench_benchmark_run,
    build_terminal_bench_environment_setup_probe_gate,
    build_terminal_bench_loopx_access_packet,
    build_terminal_bench_loopx_cli_bridge_contract,
    build_terminal_bench_managed_harbor_command,
)
from loopx.status import compact_benchmark_run  # noqa: E402


FORBIDDEN_TEXT = [
    "/" + "Users/",
    "/" + "tmp/",
    ".local/benchmark-runs",
    "OPENAI" + "_API_KEY=",
    "ARK" + "_API_KEY=",
    "CODEX" + "_AUTH_JSON_PATH=",
    "auth.json" + "\":",
    "raw" + "_thread",
    "session" + "_history",
    "trajectory" + "_path",
    "raw" + "_verifier_output",
    "verifier" + "_output_path",
    "verifier" + "_output_text",
    "lark" + "office",
    "fei" + "shu.cn",
    "sk-" + "example",
    "-----BEGIN",
]


def assert_public_safe(payload: object, *, limit: int = 36000) -> None:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < limit, len(text)


def assert_preflight_characterization_gate() -> None:
    previous_run = {
        "schema_version": "benchmark_run_v0",
        "environment_setup_failure_context": {
            "schema_version": "terminal_bench_environment_setup_readiness_preflight_v0",
            "surface": "harbor_environment_setup",
            "failure_kind": "environment_setup_failed_before_worker",
            "diagnostic_granularity": "compact_counts_only_no_raw_logs",
            "environment_setup_present": True,
            "worker_trace_present": False,
            "next_probe": "environment_setup_readiness_preflight_before_repeat",
        },
    }
    gate = build_terminal_bench_environment_setup_probe_gate(
        preflight={"ready": True},
        previous_benchmark_run=previous_run,
        harbor_run_help_text=(
            "harbor run --agent nop --disable-verification --upload "
            "--jobs-dir <dir>"
        ),
    )
    assert gate["schema_version"] == "terminal_bench_environment_setup_probe_gate_v0", gate
    assert gate["preflight_ready"] is True, gate
    assert gate["previous_environment_setup_failure_present"] is True, gate
    assert gate["environment_setup_probe_allowed"] is True, gate
    assert gate["same_task_repeat_allowed"] is False, gate
    assert gate["probe_contract"]["agent"] == "nop", gate
    assert gate["probe_contract"]["codex_invoked"] is False, gate
    assert gate["probe_contract"]["no_upload"] is True, gate
    assert gate["probe_contract"]["submit_eligible"] is False, gate
    assert gate["read_boundary"]["raw_logs_read"] is False, gate
    assert gate["read_boundary"]["task_text_read"] is False, gate
    assert gate["read_boundary"]["trajectory_read"] is False, gate
    assert gate["read_boundary"]["credential_values_recorded"] is False, gate
    assert_public_safe(gate)


def assert_no_submit_command_boundary() -> None:
    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        loopx_access_packet_mode=TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
        job_name="terminal_bench_readiness_characterization",
    )
    command_text = " ".join(command)
    assert command[:4] == ["uvx", "--from", command[2], "harbor"], command
    assert "run" in command, command
    assert "--upload" not in command, command
    assert "--submit" not in command, command
    assert "loopx_cli_bridge_enabled=true" in command, command
    assert "loopx_access_packet_mode=compact" in command, command
    assert "CODEX_FORCE_AUTH_JSON=true" in command, command
    try:
        build_terminal_bench_managed_harbor_command(no_upload=False)
    except ValueError as exc:
        assert "no-upload only" in str(exc), exc
    else:
        raise AssertionError("no_upload=False must be rejected")
    assert_public_safe(command_text)


def assert_cli_bridge_and_access_packet() -> None:
    contract = build_terminal_bench_loopx_cli_bridge_contract(
        goal_id="terminal-bench-readiness-fixture",
        registry="<registry>",
        runtime_root="<runtime-root>",
        benchmark_run_json="<benchmark-run-v0.json>",
        classification="terminal_bench_readiness_characterization",
        bridge_available=True,
    )
    assert contract["schema_version"] == TERMINAL_BENCH_LOOPX_CLI_BRIDGE_CONTRACT_VERSION, contract
    assert contract["bridge_available"] is True, contract
    assert contract["bridge_surface"] == "host_agent_loopx_cli_bridge_v0", contract
    assert contract["command_templates"]["append_benchmark_run"][-1] == "--dry-run", contract
    assert contract["boundary"]["real_run"] is False, contract
    assert contract["boundary"]["runs_terminal_bench"] is False, contract

    packet = build_terminal_bench_loopx_access_packet(
        packet_mode=TERMINAL_BENCH_LOOPX_ACCESS_PACKET_MODE_COMPACT,
        goal_id="terminal-bench-readiness-fixture",
        cli_bridge_available=True,
        classification="terminal_bench_readiness_characterization",
    )
    assert "packet_mode: compact" in packet, packet
    assert f"loopx_interface_surface: {TERMINAL_BENCH_CODEX_WORKER_CLI_BRIDGE_SURFACE}" in packet, packet
    assert "loopx_cli_bridge_command_check:" in packet, packet
    assert "loopx_cli_bridge_command_append_benchmark_run:" in packet, packet
    assert "loopx_cli_bridge_command_status:" not in packet, packet
    assert "optional_status_quota_todo_history_commands_omitted_from_prompt: true" in packet, packet
    assert "worker_benchmark_run_json_submit_eligible_must_be_false: true" in packet, packet
    assert "worker_benchmark_run_json_runner_no_upload_boundary_overrides_worker_guess: true" in packet, packet
    assert_public_safe({"contract": contract, "packet": packet})


def assert_benchmark_run_builder_contract() -> None:
    run = build_terminal_bench_benchmark_run(
        mode="codex-loopx",
        cli_bridge_contract=True,
        cli_bridge_trace={
            "bridge_available": True,
            "loopx_cli_calls": {"check": 1, "append_benchmark_run": 1},
            "loopx_state_reads": 1,
            "loopx_state_writes": 0,
            "case_result_writeback": "append_benchmark_run_dry_run",
            "counter_trust_level": "readiness_characterization_fixture",
        },
    )
    assert run["schema_version"] == "benchmark_run_v0", run
    assert run["real_run"] is False, run
    assert run["submit_eligible"] is False, run
    assert run["leaderboard_evidence"] is False, run
    assert run["official_task_score"]["kind"] == "not_run", run
    assert run["authorization"]["real_case_execution_authorized"] is False, run
    assert run["authorization"]["submit_eligible"] is False, run
    assert run["validation"]["cli_bridge_contract_checked"] is True, run
    assert run["validation"]["append_benchmark_run_dry_run_only"] is True, run
    assert run["validation"]["no_real_codex_invoked"] is True, run
    assert run["validation"]["no_harbor_or_terminal_bench_invoked"] is True, run
    assert run["validation"]["no_model_api_invoked"] is True, run
    assert run["redaction"]["secret_values_recorded"] is False, run
    assert run["redaction"]["raw_sessions_recorded"] is False, run
    assert run["trials"][0]["trajectory_present"] is False, run
    assert run["trials"][0]["verifier_reward_present"] is False, run
    assert run["runner_loopx_cli_call_total"] == 6, run

    compact = compact_benchmark_run(run)
    assert compact, run
    assert compact["submit_eligible"] is False, compact
    assert compact["leaderboard_evidence"] is False, compact
    assert compact["real_run"] is False, compact
    assert_public_safe({"run": run, "compact": compact})


def main() -> None:
    assert_preflight_characterization_gate()
    assert_no_submit_command_boundary()
    assert_cli_bridge_and_access_packet()
    assert_benchmark_run_builder_contract()
    print("terminal-bench-adapter-readiness-characterization-smoke ok")


if __name__ == "__main__":
    main()
