#!/usr/bin/env python3
"""Smoke-test the benchmark e2e owner decision packet."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "benchmark_e2e_owner_decision_v0"
SELECTED_ROUTE = "swe_bench_pro_one_instance_private_pilot"
REMOTE_ROUTE = "remote_gpu_route_b_noauth_helper"
LOCAL_ROUTE = "local_docker_trusted_host_codex"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"

FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "command_argv",
    "credential",
    "environment",
    "file_content",
    "gold_patch",
    "local_path",
    "password",
    "patch_content",
    "problem_statement",
    "raw_artifact",
    "raw_output",
    "raw_patch",
    "screenshot",
    "session",
    "solution",
    "task_body",
    "task_file",
    "test_body",
    "test_list",
    "test_patch",
    "trajectory",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "~/.codex/auth.json",
    ".codex/auth.json",
    "CODEX_ACCESS_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "docker pull",
    "docker run",
    "docker compose",
)


def key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def leaf(path: str) -> str:
    segment = path.rsplit(".", 1)[-1]
    if "[" in segment:
        segment = segment.split("[", 1)[0]
    return segment.lower()


def build_owner_decision() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "owner_decision": {
            "proceed_real_e2e": True,
            "local_docker_allowed": True,
            "remote_gpu_dev_host_allowed": True,
            "credential_strategy_delegated_to_codex": True,
            "small_public_context_reads_delegated": True,
        },
        "selected_route": {
            "route": SELECTED_ROUTE,
            "benchmark_id": "swe-bench-pro",
            "route_order": 1,
            "execution_scope_approved": True,
            "one_bounded_pilot_only": True,
        },
        "provider_policy": {
            "allowed_surfaces": [LOCAL_ROUTE, REMOTE_ROUTE],
            "trusted_codex_surface": "local_host_only",
            "remote_helper_allowed": True,
            "remote_model_or_codex_invocation_allowed": False,
            "local_codex_auth_copied_to_remote": False,
            "remote_codex_home_synced": False,
            "credential_values_read": False,
            "credential_values_copied": False,
            "shell_history_copied": False,
            "local_runtime_history_copied": False,
        },
        "execution_boundary": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "raw_task_material_public": False,
            "generated_patch_public": False,
            "official_score_claim_before_local_evaluation": False,
            "leaderboard_claim_allowed": False,
            "public_artifacts_hash_count_only": True,
        },
        "next_worker_contract": {
            "launch_one_pilot_if_ready": True,
            "write_compact_blocker_if_not_ready": True,
            "avoid_new_benchmark_scouting_until_route_resolves": True,
            "compact_run_schema": "benchmark_run_v0",
            "compact_result_schema": "benchmark_result_v0",
        },
        "this_packet_actions": {
            "benchmark_run_started": False,
            "docker_image_acquired": False,
            "container_started": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "patch_evaluated": False,
            "private_material_read": False,
            "upload_invoked": False,
            "submit_invoked": False,
            "public_ranking_path_touched": False,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "owner_gate_resolution",
            "value": 1.0,
            "components": {
                "gate_resolved": 1.0,
                "route_preserved": 1.0,
                "credential_boundary": 1.0,
                "next_worker_actionability": 1.0,
            },
        },
    }


def assert_public_safe(payload: dict[str, Any]) -> None:
    key_hits = [path for path in key_paths(payload) if leaf(path) in FORBIDDEN_KEYS]
    assert not key_hits, key_hits
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    packet = build_owner_decision()
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["owner_decision"]["proceed_real_e2e"] is True, packet
    assert packet["owner_decision"]["local_docker_allowed"] is True, packet
    assert packet["owner_decision"]["remote_gpu_dev_host_allowed"] is True, packet
    assert packet["selected_route"]["route"] == SELECTED_ROUTE, packet
    assert packet["selected_route"]["execution_scope_approved"] is True, packet
    assert LOCAL_ROUTE in packet["provider_policy"]["allowed_surfaces"], packet
    assert REMOTE_ROUTE in packet["provider_policy"]["allowed_surfaces"], packet
    assert packet["provider_policy"]["trusted_codex_surface"] == "local_host_only", packet
    assert packet["provider_policy"]["remote_model_or_codex_invocation_allowed"] is False, packet
    assert packet["provider_policy"]["local_codex_auth_copied_to_remote"] is False, packet
    assert packet["provider_policy"]["credential_values_read"] is False, packet
    assert packet["execution_boundary"]["no_upload"] is True, packet
    assert packet["execution_boundary"]["no_submit"] is True, packet
    assert packet["execution_boundary"]["leaderboard_claim_allowed"] is False, packet
    for action, happened in packet["this_packet_actions"].items():
        assert happened is False, (action, packet)
    assert packet["control_plane_score"]["value"] == 1.0, packet
    assert_public_safe(packet)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "selected_route": SELECTED_ROUTE,
        "execution_scope_approved": True,
        "local_docker_allowed": True,
        "remote_gpu_route_b_allowed": True,
        "remote_codex_auth_sync_allowed": False,
        "benchmark_run_started": False,
        "codex_cli_invoked": False,
        "model_api_invoked": False,
        "container_started": False,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
