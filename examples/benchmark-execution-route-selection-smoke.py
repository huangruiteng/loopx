#!/usr/bin/env python3
"""Smoke-test the no-run benchmark execution route selection packet."""

from __future__ import annotations

import json
from typing import Any


PACKET_SCHEMA = "benchmark_execution_route_selection_v0"
SELECTED_ROUTE = "swe_bench_pro_one_instance_private_pilot"
DEFERRED_ROUTE = "theagentcompany_single_task_host_codex_pilot"
CONTROL_SCORE_SCHEMA = "control_plane_score_core_v0"

FORBIDDEN_KEYS = {
    "api_key",
    "access_token",
    "authorization",
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
    "~/.codex",
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


def build_route_selection() -> dict[str, Any]:
    return {
        "schema_version": PACKET_SCHEMA,
        "selected_route": SELECTED_ROUTE,
        "selected_route_reason": "lowest_ready_integration_surface",
        "route_rankings": [
            {
                "route": SELECTED_ROUTE,
                "rank": 1,
                "benchmark_id": "swe-bench-pro",
                "prior_packets_ready": [
                    "selected_row_compaction",
                    "one_instance_launch_packet",
                    "one_instance_execution_gate_packet",
                ],
                "selected_instance_ready": True,
                "selected_image_metadata_ready": True,
                "runner_source_ready": True,
                "single_task_scope_ready": True,
                "service_stack_required": False,
                "action_adapter_required_before_selection": False,
                "public_artifact_chain_ready": True,
                "integration_surface_score": 2,
                "blocking_boundaries": [
                    "private_sample_reduction",
                    "trusted_local_patch_generation",
                    "selected_image_acquisition",
                    "selected_container_start",
                    "official_patch_evaluation",
                ],
            },
            {
                "route": DEFERRED_ROUTE,
                "rank": 2,
                "benchmark_id": "theagentcompany",
                "prior_packets_ready": [
                    "setup_readiness",
                    "source_preflight",
                    "single_task_host_codex_gate_packet",
                ],
                "selected_instance_ready": False,
                "selected_image_metadata_ready": False,
                "runner_source_ready": True,
                "single_task_scope_ready": False,
                "service_stack_required": True,
                "action_adapter_required_before_selection": True,
                "public_artifact_chain_ready": True,
                "integration_surface_score": 5,
                "blocking_boundaries": [
                    "service_stack_setup",
                    "single_task_private_selection",
                    "task_material_access",
                    "host_codex_action_adapter",
                    "private_artifact_reduction",
                ],
            },
        ],
        "deferred_options": [
            {
                "route": "another_reachable_low_success_gate_packet",
                "reason": "defer_until_execution_scope_is_rejected_or_stalls",
            }
        ],
        "execution_scope_contract": {
            "required_before_real_run": True,
            "real_run_authorized_now": False,
            "no_public_score_claim": True,
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "codex_auth_local_only": True,
            "codex_auth_copied": False,
            "credentials_read": False,
        },
        "this_packet_actions": {
            "benchmark_run_started": False,
            "private_material_read": False,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "patch_generated": False,
            "image_acquired": False,
            "container_started": False,
            "patch_evaluated": False,
            "service_stack_started": False,
            "raw_artifacts_read": False,
        },
        "control_plane_score": {
            "schema_version": CONTROL_SCORE_SCHEMA,
            "kind": "route_selection_gate",
            "value": 1.0,
            "components": {
                "route_selected": 1.0,
                "boundary_safety": 1.0,
                "public_artifact_ready": 1.0,
                "failure_attribution": 1.0,
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
    packet = build_route_selection()
    rankings = packet["route_rankings"]
    selected = rankings[0]
    deferred = rankings[1]
    assert packet["schema_version"] == PACKET_SCHEMA, packet
    assert packet["selected_route"] == SELECTED_ROUTE, packet
    assert selected["route"] == SELECTED_ROUTE, packet
    assert selected["selected_instance_ready"] is True, packet
    assert selected["selected_image_metadata_ready"] is True, packet
    assert selected["service_stack_required"] is False, packet
    assert selected["integration_surface_score"] < deferred["integration_surface_score"], packet
    assert deferred["route"] == DEFERRED_ROUTE, packet
    assert deferred["service_stack_required"] is True, packet
    assert deferred["selected_instance_ready"] is False, packet
    assert packet["execution_scope_contract"]["required_before_real_run"] is True, packet
    assert packet["execution_scope_contract"]["real_run_authorized_now"] is False, packet
    assert packet["execution_scope_contract"]["credentials_read"] is False, packet
    for action, happened in packet["this_packet_actions"].items():
        assert happened is False, (action, packet)
    assert packet["control_plane_score"]["value"] == 1.0, packet
    assert_public_safe(packet)
    return {
        "ok": True,
        "classification": PACKET_SCHEMA,
        "selected_route": packet["selected_route"],
        "deferred_route": DEFERRED_ROUTE,
        "real_run_authorized_now": False,
        "benchmark_run_started": False,
        "codex_cli_invoked": False,
        "model_api_invoked": False,
        "container_started": False,
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
