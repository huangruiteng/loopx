#!/usr/bin/env python3
"""Smoke-test the generic LoopX worker bridge/install contract."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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
    "sk-" + "example",
    "tok" + "en=",
    "-----BEGIN",
]


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in text]
    assert not leaked, leaked
    assert len(text) < 16000, len(text)


def assert_contract(payload: dict) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "loopx_worker_bridge_install_contract_v0", payload
    assert payload["bridge_surface"] == "loopx_worker_bridge_source_mount_v0", payload
    assert payload["install_mode"] == "source_mount_read_only_pythonpath", payload
    assert payload["runtime_policy"] == "ensure_python3_before_worker_cli_bridge", payload
    assert "apt-get install -y python3" in payload["runtime_preflight_command"], payload
    assert "importlib.import_module" in payload["runtime_preflight_command"], payload
    assert payload["mounts"] == [
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
    ], payload
    agent_kwargs = payload["agent_kwargs"]
    assert (
        agent_kwargs["loopx_command_prefix"]
        == "PYTHONPATH='<loopx-project-root>' python3 -m loopx.cli"
    ), payload
    assert (
        agent_kwargs["loopx_runtime_preflight_command"]
        == payload["runtime_preflight_command"]
    ), payload
    assert (
        agent_kwargs["loopx_registry_arg"]
        == "<loopx-runtime-root>/registry.global.json"
    ), payload
    assert (
        agent_kwargs["loopx_counter_trace_json"]
        == "/logs/agent/loopx-counter-trace.jsonl"
    ), payload
    assert (
        agent_kwargs["loopx_active_user_feed_jsonl"]
        == "/logs/agent/loopx-active-user-interventions.jsonl"
    ), payload
    assert (
        agent_kwargs["loopx_active_user_observation_json"]
        == "/logs/agent/loopx-active-user-observation.json"
    ), payload
    assert (
        agent_kwargs["loopx_active_user_channel_surface"]
        == "loopx_active_user_external_update_loop_v0"
    ), payload
    assert "active-user-observe" in agent_kwargs["loopx_active_user_observe_command"], payload
    assert payload["active_user_external_update_mount"] == {
        "enabled": False,
        "target": None,
        "read_only": None,
        "raw_host_path_recorded": False,
    }, payload
    assert agent_kwargs["loopx_benchmark_run_schema_version"] == "benchmark_run_v0", payload
    assert (
        agent_kwargs["loopx_benchmark_run_writeback_contract"]
        == "loopx_worker_benchmark_run_writeback_contract_v0"
    ), payload
    writeback = payload["benchmark_run_writeback_contract"]
    assert writeback["schema_version"] == "loopx_worker_benchmark_run_writeback_contract_v0", payload
    assert writeback["benchmark_run_schema_version"] == "benchmark_run_v0", payload
    assert writeback["benchmark_run_json"] == "/logs/agent/loopx-worker-benchmark-run.json", payload
    assert writeback["counter_trace_json"] == "/logs/agent/loopx-counter-trace.jsonl", payload
    assert set(writeback["required_top_level_fields"]) == {
        "schema_version",
        "source_runner",
        "benchmark_id",
        "job_name",
        "mode",
        "worker_mode",
        "real_run",
        "submit_eligible",
        "leaderboard_evidence",
        "official_task_score",
        "validation_scope",
        "progress",
        "validation",
        "claim_boundary",
        "trials",
    }, payload
    assert writeback["validation_scope_contract"] == {
        "field": "validation_scope",
        "recommended_values": [
            "worker_bridge_connectivity",
            "environment_ready",
            "worker_case_success",
            "official_verifier_result",
        ],
        "connectivity_is_not_case_success": True,
        "legacy_unscoped_passed_validation_is_ambiguous": True,
    }, payload
    assert set(writeback["claim_boundary_required_fields"]) == {
        "bridge_connectivity_claim_allowed",
        "case_success_claim_allowed",
        "official_score_claim_allowed",
        "leaderboard_claim_allowed",
        "forbidden_claims",
    }, payload
    assert set(writeback["forbidden_public_fields"]) == {
        "raw_paths",
        "raw_logs",
        "raw_trace",
        "raw_task_prompt",
        "raw_sessions",
        "credential_values",
        "auth_values",
    }, payload
    assert (
        writeback["retry_policy"]["on_append_benchmark_run_schema_rejected"]
        == "rewrite_minimal_benchmark_run_v0_and_retry_once"
    ), payload
    assert writeback["retry_policy"]["do_not_retry_with_raw_logs_or_raw_paths"] is True, payload


def assert_active_user_writable_mount_contract() -> None:
    from loopx.worker_bridge import build_worker_bridge_install_contract

    payload = build_worker_bridge_install_contract(
        active_user_host_dir="<active-user-host-dir>",
    )
    mounts = payload["mounts"]
    assert mounts[-1] == {
        "read_only": False,
        "source": "<active-user-host-dir>",
        "target": "/loopx-active-user",
        "type": "bind",
    }, payload
    assert payload["active_user_external_update_mount"] == {
        "enabled": True,
        "target": "/loopx-active-user",
        "read_only": False,
        "raw_host_path_recorded": False,
    }, payload
    agent_kwargs = payload["agent_kwargs"]
    assert (
        agent_kwargs["loopx_active_user_feed_jsonl"]
        == "/loopx-active-user/loopx-active-user-interventions.jsonl"
    ), payload
    assert (
        agent_kwargs["loopx_active_user_observation_json"]
        == "/loopx-active-user/loopx-active-user-observation.json"
    ), payload
    assert (
        "--feed-jsonl /loopx-active-user/loopx-active-user-interventions.jsonl"
        in agent_kwargs["loopx_active_user_observe_command"]
    ), payload
    assert_public_safe(payload)
    active_user_channel = payload["active_user_intervention_channel_contract"]
    assert (
        active_user_channel["schema_version"]
        == "loopx_active_user_intervention_channel_contract_v0"
    ), payload
    assert (
        active_user_channel["channel_surface"]
        == "loopx_active_user_external_update_loop_v0"
    ), payload
    assert active_user_channel["mode"] == "audited_external_update_loop", payload
    assert active_user_channel["frequency_budget"]["max_interventions_per_task"] == 3, payload
    assert active_user_channel["claim_boundary"]["direct_codex_chat_injection"] is False, payload
    assert active_user_channel["claim_boundary"]["worker_pull_required"] is True, payload
    assert payload["boundary"]["no_upload"] is True, payload
    assert_public_safe(payload)


def assert_outcome(payload: dict) -> None:
    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "loopx_worker_bridge_outcome_v0", payload
    assert payload["bridge_surface"] == "loopx_worker_bridge_source_mount_v0", payload
    assert payload["worker_bridge_verified"] is True, payload
    assert payload["runner_return_status"] == "interrupted_after_worker_bridge_success", payload
    assert payload["official_score_status"] == "blocked_pending_runner_return", payload
    assert payload["worker_loopx_cli_call_total"] == 4, payload
    assert payload["required_worker_loopx_cli_call_total_min"] == 1, payload
    assert payload["counter_trace_present"] is True, payload
    assert payload["runner_return_completed"] is False, payload
    assert payload["official_score_completed"] is False, payload
    assert payload["side_effect_audit_passed"] is True, payload
    policy = payload["wall_time_policy"]
    assert policy["schema_version"] == "loopx_worker_bridge_wall_time_policy_v0", payload
    assert policy["interrupted"] is True, payload
    assert policy["wall_time_seconds"] == 720.0, payload
    assert policy["wall_time_limit_seconds"] == 900.0, payload
    assert policy["changes_official_benchmark_timeout"] is False, payload
    assert policy["changes_official_task_resources"] is False, payload
    assert policy["leaderboard_claim_allowed"] is False, payload
    assert set(payload["failure_attribution_labels"]) == {
        "worker_bridge_install_verified",
        "runner_return_pending",
        "controller_interrupt",
        "official_score_pending",
    }, payload
    assert "official_reward_complete" in payload["claim_boundary"]["forbidden_claims"], payload
    assert "leaderboard_ready" in payload["claim_boundary"]["forbidden_claims"], payload
    assert payload["claim_boundary"]["bridge_connectivity_claim_allowed"] is True, payload
    assert payload["claim_boundary"]["case_success_claim_allowed"] is False, payload
    assert payload["claim_boundary"]["official_score_claim_allowed"] is False, payload
    assert payload["raw_paths_recorded"] is False, payload
    assert payload["raw_trace_recorded"] is False, payload
    assert payload["credential_values_recorded"] is False, payload
    assert_public_safe(payload)


def assert_benchmark_run(payload: dict) -> None:
    from loopx.status import compact_benchmark_run

    assert payload["ok"] is True, payload
    assert payload["schema_version"] == "benchmark_run_v0", payload
    assert payload["source_runner"] == "worker_bridge_runner", payload
    assert payload["mode"] == "codex_loopx_active_worker", payload
    assert payload["loopx_inside_case"] is True, payload
    assert payload["submit_eligible"] is False, payload
    assert payload["leaderboard_evidence"] is False, payload
    assert payload["worker_loopx_cli_call_total"] == 4, payload
    assert payload["validation_scope"] == "worker_bridge_connectivity", payload
    assert payload["case_success_claimed"] is False, payload
    assert payload["official_verifier_validation_present"] is False, payload
    outcome = payload["worker_bridge_outcome"]
    assert outcome["worker_bridge_verified"] is True, payload
    assert outcome["runner_return_status"] == "interrupted_after_worker_bridge_success", payload
    assert outcome["official_score_status"] == "blocked_pending_runner_return", payload
    validation = payload["validation"]
    assert validation["validation_scope"] == "worker_bridge_connectivity", payload
    assert validation["bridge_connected"] is True, payload
    assert validation["case_success_claimed"] is False, payload
    assert validation["official_verifier_validation_present"] is False, payload
    assert validation["runner_return_completed_or_blocker_recorded"] is True, payload
    assert validation["official_score_completed_or_not_claimed"] is True, payload
    assert payload["progress"]["n_cancelled_trials"] == 1, payload

    compact = compact_benchmark_run(payload)
    assert compact is not None, payload
    assert compact["worker_bridge_outcome"]["worker_bridge_verified"] is True, compact
    assert compact["worker_bridge_outcome"]["worker_loopx_cli_call_total"] == 4, compact
    assert compact["validation"]["all_passed"] is True, compact
    assert_public_safe(payload)
    assert_public_safe(compact)


def assert_module_contract() -> None:
    from loopx.worker_bridge import (
        build_worker_bridge_benchmark_run,
        build_worker_bridge_benchmark_run_from_counters,
        build_worker_bridge_benchmark_run_writeback_contract,
        build_worker_bridge_install_contract,
        build_worker_bridge_outcome,
        write_worker_bridge_benchmark_run_file,
    )

    assert_contract(build_worker_bridge_install_contract())
    writeback_contract = build_worker_bridge_benchmark_run_writeback_contract()
    assert writeback_contract["schema_version"] == "loopx_worker_benchmark_run_writeback_contract_v0", writeback_contract
    assert writeback_contract["benchmark_run_schema_version"] == "benchmark_run_v0", writeback_contract
    assert writeback_contract["required_fixed_fields"] == {
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
    }, writeback_contract
    assert_public_safe(writeback_contract)
    assert_outcome(
        build_worker_bridge_outcome(
            worker_loopx_cli_call_total=4,
            counter_trace_present=True,
            interrupted=True,
            interrupt_reason="controller_interrupt_after_wall_time_limit",
            wall_time_seconds=720,
            wall_time_limit_seconds=900,
        )
    )
    generic_payload = build_worker_bridge_benchmark_run_from_counters(
        {"loopx_cli_calls": {"total": 3}},
        counter_trace_present=True,
    )
    assert generic_payload["worker_loopx_cli_call_total"] == 3, generic_payload
    assert generic_payload["worker_bridge_outcome"]["worker_bridge_verified"] is True, generic_payload
    with tempfile.TemporaryDirectory(prefix="loopx-worker-bridge-") as tmp:
        output_path = Path(tmp) / "worker-benchmark-run.json"
        assert write_worker_bridge_benchmark_run_file(output_path, generic_payload)
        written_payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert written_payload["schema_version"] == "benchmark_run_v0", written_payload
        assert written_payload["worker_loopx_cli_call_total"] == 3, written_payload
        assert_public_safe(written_payload)
    assert_benchmark_run(
        build_worker_bridge_benchmark_run(
            worker_loopx_cli_call_total=4,
            counter_trace_present=True,
            interrupted=True,
            interrupt_reason="controller_interrupt_after_wall_time_limit",
            wall_time_seconds=720,
            wall_time_limit_seconds=900,
        )
    )


def assert_cli_contract() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "worker-bridge",
            "contract",
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert_contract(payload)


def assert_cli_outcome() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "worker-bridge",
            "outcome",
            "--format",
            "json",
            "--worker-cli-call-total",
            "4",
            "--counter-trace-present",
            "--interrupted",
            "--interrupt-reason",
            "controller_interrupt_after_wall_time_limit",
            "--wall-time-seconds",
            "720",
            "--wall-time-limit-seconds",
            "900",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert_outcome(payload)


def assert_cli_benchmark_run() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "worker-bridge",
            "benchmark-run",
            "--format",
            "json",
            "--worker-cli-call-total",
            "4",
            "--counter-trace-present",
            "--interrupted",
            "--interrupt-reason",
            "controller_interrupt_after_wall_time_limit",
            "--wall-time-seconds",
            "720",
            "--wall-time-limit-seconds",
            "900",
        ],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert_benchmark_run(payload)


def assert_terminal_bench_adapter_consumes_contract() -> None:
    from loopx.benchmark import build_terminal_bench_managed_harbor_command

    command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
    )
    active_user_command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        loopx_active_user_intervention_enabled=True,
    )
    extended_timeout_command = build_terminal_bench_managed_harbor_command(
        loopx_mode="codex_loopx",
        loopx_cli_bridge_enabled=True,
        agent_timeout_multiplier=2.0,
    )
    assert "--mounts" in command, command
    assert "--agent-timeout-multiplier" not in command, command
    assert "--agent-timeout-multiplier" in extended_timeout_command, extended_timeout_command
    assert extended_timeout_command[
        extended_timeout_command.index("--agent-timeout-multiplier") + 1
    ] == "2", extended_timeout_command
    mounts = json.loads(command[command.index("--mounts") + 1])
    assert mounts[0]["source"] == "<loopx-project-root>", command
    assert mounts[1]["source"] == "<loopx-runtime-root>", command
    active_user_mounts = json.loads(
        active_user_command[active_user_command.index("--mounts") + 1]
    )
    assert active_user_mounts[-1] == {
        "read_only": False,
        "source": "<active-user-host-dir>",
        "target": "/loopx-active-user",
        "type": "bind",
    }, active_user_mounts
    assert (
        "loopx_active_user_feed_jsonl="
        "/loopx-active-user/loopx-active-user-interventions.jsonl"
    ) in active_user_command, active_user_command
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
    assert_public_safe(" ".join(command))


def main() -> int:
    assert_module_contract()
    assert_active_user_writable_mount_contract()
    assert_cli_contract()
    assert_cli_outcome()
    assert_cli_benchmark_run()
    assert_terminal_bench_adapter_consumes_contract()
    print(
        "worker-bridge-install-contract-smoke ok "
        "outcome=interrupted_after_worker_bridge_success benchmark_run=compactable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
