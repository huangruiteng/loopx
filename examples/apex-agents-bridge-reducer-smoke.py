#!/usr/bin/env python3
"""Smoke-test the no-run APEX-Agents host-Codex bridge/reducer contract."""

from __future__ import annotations

import hashlib
import json
from typing import Any


BENCHMARK_RUN_SCHEMA = "benchmark_run_v0"
BENCHMARK_RESULT_SCHEMA = "benchmark_result_v0"
CONTROL_PLANE_SCORE_SCHEMA = "control_plane_score_core_v0"
SOURCE_RUNNER = "archipelago"
BENCHMARK_ID = "apex-agents"
BENCHMARK_REVISION = "92c86856cf1b11f9833a8a076b3a45a63afa3929"
ARCHIPELAGO_COMMIT = "77a872577ce1b33cb71817465e844e52eadd3cbe"
MODE = "host_codex_external_mcp_adapter"
CONTROL_PLANE_SCORE_COMPONENTS = (
    "restartability",
    "stale_state_avoidance",
    "evidence_discipline",
    "boundary_safety",
    "writeback_quality",
    "gate_compliance",
    "failure_attribution",
    "overhead",
)
FORBIDDEN_PUBLIC_KEYS = {
    "api_key",
    "access_token",
    "authorization",
    "credential_value",
    "dataset_row",
    "gold",
    "hidden_reference",
    "instruction",
    "local_path",
    "password",
    "prompt",
    "raw_message",
    "raw_messages",
    "rubric",
    "screenshot",
    "session",
    "solution",
    "task_body",
    "task_file",
    "trajectory",
    "world_file",
}
FORBIDDEN_PUBLIC_TEXT = (
    "/" + "Users/",
    "~/.codex",
    ".codex/auth.json",
    "OPENAI_API_KEY",
    "CODEX_ACCESS_TOKEN",
    "ANTHROPIC_API_KEY",
    "GOOGLE_API_KEY",
    "HF_TOKEN",
    "hf_hub_download",
    "snapshot_download",
    "docker compose up",
    "leaderboard",
    "submission",
)


def stable_hash(label: str, value: str) -> str:
    return hashlib.sha256(f"{label}:{value}".encode("utf-8")).hexdigest()


def public_key_paths(value: Any, *, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.append(path)
            paths.extend(public_key_paths(child, prefix=path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, child in enumerate(value):
            paths.extend(public_key_paths(child, prefix=f"{prefix}[{index}]"))
        return paths
    return []


def make_private_no_run_fixture() -> dict[str, Any]:
    mcp_readiness = {
        "browser": "configured_not_started",
        "desktop": "configured_not_started",
        "email": "configured_not_started",
        "filesystem": "configured_not_started",
        "spreadsheet": "configured_not_started",
        "terminal": "configured_not_started",
    }
    return {
        "schema_version": "apex_agents_bridge_fixture_v0",
        "source_runner": SOURCE_RUNNER,
        "benchmark_id": BENCHMARK_ID,
        "benchmark_revision": BENCHMARK_REVISION,
        "archipelago_commit": ARCHIPELAGO_COMMIT,
        "mode": MODE,
        "selected_task": {
            "selector_hash": stable_hash("task-selector", "apex-fixture-task-0001"),
            "domain": "consulting",
            "world_selector_hash": stable_hash("world-selector", "apex-fixture-world-0001"),
        },
        "provider": {
            "kind": "archipelago_provider_fixture",
            "dataset_material_loaded": False,
            "docker_started": False,
            "dependencies_installed": False,
            "mcp_readiness": mcp_readiness,
        },
        "bridge": {
            "kind": MODE,
            "codex_surface": "local_cli",
            "model_label": "gpt-5.5-xhigh",
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "credential_material_copied": False,
            "raw_artifact_material_public": False,
        },
        "private_trajectory_metadata": {
            "available": False,
            "message_count": 0,
            "tool_call_count": 0,
            "redacted_event_count": 0,
            "raw_messages_present": False,
        },
        "grading_summary": {
            "grader_invoked": False,
            "official_final_score": None,
            "criterion_count": None,
            "criterion_pass_count": None,
            "exception_type": "not_run_fixture_only",
        },
        "forbidden_actions": {
            "hf_dataset_access": False,
            "task_material_access": False,
            "docker_start": False,
            "dependency_install": False,
            "codex_or_model_call": False,
            "real_grading": False,
            "upload": False,
            "submit": False,
            "leaderboard_touch": False,
            "credential_read": False,
            "raw_artifact_read": False,
            "shared_host_workload_inspection": False,
        },
    }


def reduce_to_benchmark_run(fixture: dict[str, Any]) -> dict[str, Any]:
    mcp_items = sorted(fixture["provider"]["mcp_readiness"].items())
    return {
        "schema_version": BENCHMARK_RUN_SCHEMA,
        "source_runner": fixture["source_runner"],
        "benchmark_id": fixture["benchmark_id"],
        "benchmark_revision": fixture["benchmark_revision"],
        "archipelago_commit": fixture["archipelago_commit"],
        "mode": fixture["mode"],
        "real_run": False,
        "dry_run": True,
        "task_selector_kind": "redacted_single_task",
        "task_selector_hash": fixture["selected_task"]["selector_hash"],
        "domain": fixture["selected_task"]["domain"],
        "world_selector_hash": fixture["selected_task"]["world_selector_hash"],
        "agent": {
            "codex_surface": fixture["bridge"]["codex_surface"],
            "model_label": fixture["bridge"]["model_label"],
        },
        "provider": {
            "dataset_material_loaded": False,
            "docker_started": False,
            "dependencies_installed": False,
            "mcp_server_total": len(mcp_items),
            "mcp_ready_count": sum(1 for _, status in mcp_items if status == "ready"),
            "mcp_readiness_hash": stable_hash("mcp-readiness", json.dumps(mcp_items, sort_keys=True)),
        },
        "progress": {
            "n_total_trials": 1,
            "n_completed_trials": 0,
            "n_errored_trials": 0,
            "n_running_trials": 0,
            "n_pending_trials": 1,
            "n_cancelled_trials": 0,
            "n_retries": 0,
        },
        "metrics": {
            "input_tokens": 0,
            "cache_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        },
        "trials": [
            {
                "task_hash": fixture["selected_task"]["selector_hash"],
                "runner_status": "blocked",
                "final_score": None,
                "criterion_count": None,
                "criterion_pass_count": None,
                "exception_type": fixture["grading_summary"]["exception_type"],
                "public_artifact_count": 0,
            }
        ],
        "validation": {
            "no_upload": True,
            "no_submit": True,
            "no_public_ranking_path": True,
            "raw_artifacts_private": True,
            "dataset_material_private": True,
            "codex_cli_invoked": False,
            "model_api_invoked": False,
            "docker_started": False,
            "archipelago_imported": False,
        },
        "stop_conditions": [
            "owner_approval_required_for_gated_dataset",
            "owner_approval_required_for_real_task_material",
            "owner_approval_required_for_docker_or_model_execution",
        ],
    }


def reduce_to_benchmark_result(fixture: dict[str, Any]) -> dict[str, Any]:
    components = {
        "restartability": 1.0,
        "stale_state_avoidance": 1.0,
        "evidence_discipline": 1.0,
        "boundary_safety": 1.0,
        "writeback_quality": 1.0,
        "gate_compliance": 1.0,
        "failure_attribution": 1.0,
        "overhead": 1.0,
    }
    return {
        "schema_version": BENCHMARK_RESULT_SCHEMA,
        "task_id": "apex_agents_redacted_single_task_fixture",
        "scenario_id": "host_codex_external_mcp_adapter_no_run",
        "worker_mode": "deterministic_fixture",
        "harness_identity": "loopx",
        "worker_surface": "host_codex_cli_external_mcp_adapter",
        "terminal_state": "blocked_before_private_material",
        "official_task_score": {
            "kind": "apex_agents_official_score",
            "status": "not_run",
            "final_score": None,
            "criterion_count": None,
            "criterion_pass_count": None,
        },
        "control_plane_score": {
            "schema_version": CONTROL_PLANE_SCORE_SCHEMA,
            "kind": "core_v0",
            "aggregation": "unweighted_mean",
            "value": sum(components.values()) / len(components),
            "components": components,
            "component_order": list(CONTROL_PLANE_SCORE_COMPONENTS),
        },
        "validation_pass_count": 9,
        "validation_fail_count": 0,
        "forbidden_access_count": 0,
        "raw_artifact_public_count": 0,
        "private_material_public_count": 0,
        "side_effect_audit_passed": True,
        "claim_boundary": {
            "official_score_claim_allowed": False,
            "control_plane_score_claim_allowed": True,
            "real_run_claim_allowed": False,
        },
        "failure_attribution_labels": [
            fixture["grading_summary"]["exception_type"],
            "waiting_for_owner_gates_before_real_run",
        ],
    }


def assert_no_forbidden_public_fields(payload: dict[str, Any]) -> None:
    key_hits = []
    for path in public_key_paths(payload):
        normalized = path.rsplit(".", 1)[-1].strip("[]").lower()
        if normalized in FORBIDDEN_PUBLIC_KEYS:
            key_hits.append(path)
    assert not key_hits, key_hits


def assert_public_safe(payload: dict[str, Any]) -> None:
    assert_no_forbidden_public_fields(payload)
    rendered = json.dumps(payload, sort_keys=True)
    leaked = [marker for marker in FORBIDDEN_PUBLIC_TEXT if marker in rendered]
    assert not leaked, leaked


def run_smoke() -> dict[str, Any]:
    fixture = make_private_no_run_fixture()
    run_event = reduce_to_benchmark_run(fixture)
    result_event = reduce_to_benchmark_result(fixture)

    assert run_event["schema_version"] == BENCHMARK_RUN_SCHEMA, run_event
    assert result_event["schema_version"] == BENCHMARK_RESULT_SCHEMA, result_event
    assert result_event["control_plane_score"]["schema_version"] == CONTROL_PLANE_SCORE_SCHEMA, result_event
    assert run_event["real_run"] is False, run_event
    assert run_event["dry_run"] is True, run_event
    assert run_event["source_runner"] == SOURCE_RUNNER, run_event
    assert run_event["mode"] == MODE, run_event
    assert run_event["validation"]["archipelago_imported"] is False, run_event
    assert run_event["validation"]["docker_started"] is False, run_event
    assert run_event["validation"]["model_api_invoked"] is False, run_event
    assert run_event["provider"]["dataset_material_loaded"] is False, run_event
    assert run_event["progress"]["n_pending_trials"] == 1, run_event
    assert run_event["trials"][0]["runner_status"] == "blocked", run_event
    assert result_event["official_task_score"]["status"] == "not_run", result_event
    assert result_event["claim_boundary"]["official_score_claim_allowed"] is False, result_event
    assert result_event["claim_boundary"]["real_run_claim_allowed"] is False, result_event
    assert result_event["claim_boundary"]["control_plane_score_claim_allowed"] is True, result_event
    assert result_event["forbidden_access_count"] == 0, result_event
    assert tuple(result_event["control_plane_score"]["component_order"]) == CONTROL_PLANE_SCORE_COMPONENTS

    for action, happened in fixture["forbidden_actions"].items():
        assert happened is False, (action, fixture)
    assert fixture["private_trajectory_metadata"]["raw_messages_present"] is False, fixture
    assert_public_safe(run_event)
    assert_public_safe(result_event)

    return {
        "ok": True,
        "classification": "apex_agents_bridge_reducer_fixture_v0",
        "source_runner": SOURCE_RUNNER,
        "benchmark_id": BENCHMARK_ID,
        "benchmark_revision": BENCHMARK_REVISION,
        "archipelago_commit": ARCHIPELAGO_COMMIT,
        "events": [run_event["schema_version"], result_event["schema_version"]],
        "real_run": False,
        "dataset_material_loaded": False,
        "docker_started": False,
        "codex_cli_invoked": False,
        "model_api_invoked": False,
        "official_task_score_status": result_event["official_task_score"]["status"],
        "control_plane_score_value": result_event["control_plane_score"]["value"],
        "forbidden_access_count": result_event["forbidden_access_count"],
    }


def main() -> None:
    print(json.dumps(run_smoke(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
