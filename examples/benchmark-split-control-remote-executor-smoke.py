#!/usr/bin/env python3
"""Smoke-test the shared split-control remote benchmark executor gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark_core import (  # noqa: E402
    BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION,
    build_split_control_remote_executor_readiness,
)


FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "password",
    "secret",
)


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, sort_keys=True)
    leaked = [item for item in FORBIDDEN_TEXT if item in text]
    assert not leaked, leaked


def test_remote_codex_is_not_required_for_split_control() -> None:
    payload = build_split_control_remote_executor_readiness(
        local_agent={
            "codex_cli_available": True,
            "goal_harness_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
            "hf_available": True,
            "huggingface_cli_available": True,
            "high_capacity_storage_available": True,
            "codex_available": False,
            "codex_acp_available": False,
            "node_available": False,
            "npm_available": False,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": False,
                "task_data_ready": True,
                "known_blockers": ["harbor_or_runner_wrapper_missing"],
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": False,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "agents-last-exam@local-docker": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": False,
                "known_blockers": ["ale_image_or_task_data_missing"],
            },
        },
    )
    assert (
        payload["schema_version"]
        == BENCHMARK_SPLIT_CONTROL_REMOTE_EXECUTOR_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "split_control_adapter_missing", payload
    assert payload["local_agent"]["ready"] is True, payload
    assert payload["remote_executor"]["base_ready"] is True, payload
    assert payload["remote_executor"]["remote_agent_components_blocking"] is False, payload
    assert payload["remote_executor"]["remote_agent_components_missing"] == {
        "codex_available": True,
        "codex_acp_available": True,
    }, payload
    assert payload["boundary"]["codex_auth_sync_allowed"] is False, payload
    assert payload["boundary"]["remote_codex_invocation_allowed"] is False, payload
    assert payload["boundary"]["remote_codex_acp_invocation_allowed"] is False, payload
    assert payload["boundary"]["remote_model_api_invocation_allowed"] is False, payload
    for status in payload["benchmark_statuses"]:
        assert status["remote_codex_required"] is False, status
        assert status["remote_codex_acp_required"] is False, status
        assert status["remote_codex_missing_is_blocker"] is False, status
        assert "remote_codex_missing" not in status["blockers"], status
    assert_public_safe(payload)


def test_ready_parallel_batch_size_is_capped() -> None:
    payload = build_split_control_remote_executor_readiness(
        benchmark_ids=("terminal-bench@2.0", "skillsbench@1.1"),
        max_parallel_cases=4,
        local_agent={
            "codex_cli_available": True,
            "goal_harness_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
        },
    )
    assert payload["ready"] is True, payload
    assert payload["first_blocker"] == "ready_for_parallel_remote_executor_rotation", payload
    assert payload["parallel_policy"]["suggested_next_batch_size"] == 2, payload
    assert payload["next_action"] == "launch bounded parallel remote-executor batch", payload
    assert_public_safe(payload)


def test_partial_ready_subset_can_launch_without_remote_codex() -> None:
    payload = build_split_control_remote_executor_readiness(
        max_parallel_cases=4,
        local_agent={
            "codex_cli_available": True,
            "goal_harness_available": True,
            "codex_auth_ready": True,
            "codex_auth_local_only": True,
            "model_invocation_local": True,
        },
        remote_executor={
            "docker_available": True,
            "python_available": True,
            "git_available": True,
            "rsync_available": True,
            "codex_available": False,
            "codex_acp_available": False,
        },
        adapter_readiness={
            "terminal-bench@2.0": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "skillsbench@1.1": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": True,
            },
            "agents-last-exam@local-docker": {
                "split_control_adapter_ready": True,
                "runner_tooling_ready": True,
                "task_data_ready": False,
                "known_blockers": ["ale_task_data_staging_venue_missing"],
            },
        },
    )
    assert payload["ready"] is False, payload
    assert payload["first_blocker"] == "remote_task_data_or_image_missing", payload
    assert payload["next_action"] == "launch bounded parallel remote-executor batch", payload
    matrix = payload["readiness_matrix"]
    assert matrix["has_launchable_subset"] is True, payload
    assert matrix["ready_benchmark_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], payload
    assert matrix["blocked_benchmark_ids"] == [
        "agents-last-exam@local-docker"
    ], payload
    assert matrix["next_ready_batch_benchmark_ids"] == [
        "terminal-bench@2.0",
        "skillsbench@1.1",
    ], payload
    assert matrix["next_repair_target"] == {
        "benchmark_id": "agents-last-exam@local-docker",
        "first_blocker": "remote_task_data_or_image_missing",
        "blockers": [
            "remote_task_data_or_image_missing",
            "ale_task_data_staging_venue_missing",
        ],
    }, payload
    assert payload["parallel_policy"]["suggested_next_batch_size"] == 2, payload
    assert payload["remote_executor"]["remote_agent_components_blocking"] is False, payload
    assert_public_safe(payload)


def main() -> int:
    test_remote_codex_is_not_required_for_split_control()
    test_ready_parallel_batch_size_is_capped()
    test_partial_ready_subset_can_launch_without_remote_codex()
    print("benchmark-split-control-remote-executor-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
