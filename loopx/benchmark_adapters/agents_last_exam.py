from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable

from ..benchmark_case_state import (
    BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS,
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_init_contract,
    benchmark_case_active_state_path,
    benchmark_case_goal_id,
)
from ..benchmark_core.io import (
    load_json_object as _load_json_object,
    load_jsonl_objects as _load_jsonl_objects,
    optional_float as _optional_float,
)

AGENTS_LAST_EXAM_BENCHMARK_ID = "agents-last-exam"
AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION = "ale-result-ingest-contract-v0"
AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION = (
    "agents_last_exam_local_preflight_v0"
)
AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION = (
    "agents_last_exam_local_dry_run_plan_v0"
)
AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_runner_readiness_v0"
)
AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_local_source_readiness_v0"
)
AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_task_material_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_readiness_v0"
)
AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_baked_task_input_scan_v0"
)
AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION = (
    "agents_last_exam_candidate_task_data_scan_v0"
)
AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION = (
    "agents_last_exam_local_launch_packet_v0"
)
AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION = (
    "agents_last_exam_local_exact_dry_run_result_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cli_route_v0"
)
AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION = (
    "agents_last_exam_host_codex_cua_no_task_smoke_v0"
)
AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION = (
    "agents_last_exam_validation_run_gate_v0"
)
AGENTS_LAST_EXAM_TRACE_PUBLICNESS = (
    "compact_public_safe_no_task_body_no_trajectory_no_output"
)
AGENTS_LAST_EXAM_CASE_GOAL_ID = benchmark_case_goal_id(AGENTS_LAST_EXAM_BENCHMARK_ID)
AGENTS_LAST_EXAM_CASE_STATE_PATH = benchmark_case_active_state_path(
    AGENTS_LAST_EXAM_CASE_GOAL_ID
)
AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE = "agentslastexam/ale-kasm:latest"
AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE = "ale-ubuntu22-docker:latest"
AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT = "cpu-free-ubuntu"
AGENTS_LAST_EXAM_DEFAULT_REPO_URL = (
    "https://github.com/rdi-berkeley/agents-last-exam.git"
)
AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED = (
    "trajectory.json",
    "origin_log",
    "output",
)

_AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE = re.compile(
    r"^\s*(?:self\.)?REQUIRES_TASK_DATA\s*(?::[^=]+)?=\s*(True|False)\b"
)


def _agents_last_exam_public_id(value: Any, *, limit: int = 140) -> str | None:
    """Return a public-safe ALE id without preserving host paths or task bodies."""

    if not isinstance(value, str):
        return None
    text = value.strip().replace("\\", "/")
    if not text or text.startswith("/") or text.startswith("~"):
        return None
    parts = [part for part in text.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        return None
    cleaned = []
    for char in "__".join(parts):
        cleaned.append(char.lower() if char.isalnum() or char in {"-", "_", "."} else "-")
    label = "".join(cleaned).strip("-_.")
    while "--" in label:
        label = label.replace("--", "-")
    return (label or None)[:limit]

def _agents_last_exam_first_public_id(*values: Any, default: str) -> str:
    for value in values:
        label = _agents_last_exam_public_id(value)
        if label:
            return label
    return default

def _agents_last_exam_parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None

def build_agents_last_exam_local_exact_dry_run_result(
    *,
    stdout_text: str | None,
    exit_code: int | str | None,
    expected_task_id: str | None = None,
    expected_agent_id: str | None = None,
) -> dict[str, Any]:
    """Reduce ALE ``--dry-run`` stdout to a compact public-safe artifact.

    The raw stdout is intentionally not returned. The reducer keeps only
    public labels and matrix counts, so callers can persist the result without
    copying paths, task text, trajectories, screenshots, credentials, or command
    argv into LoopX state.
    """

    parsed_exit_code = _agents_last_exam_parse_int(exit_code)
    text = stdout_text if isinstance(stdout_text, str) else ""
    lines = [line.rstrip() for line in text.splitlines()]
    experiment_label: str | None = None
    environment_label: str | None = None
    environment_route_label: str | None = None
    concurrency: int | None = None
    declared_unit_count: int | None = None
    units: list[dict[str, Any]] = []
    in_units = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("experiment:"):
            experiment_label = _agents_last_exam_public_id(
                line.split(":", 1)[1],
                limit=160,
            )
            in_units = False
            continue
        if line.startswith("environment:"):
            value = line.split(":", 1)[1].strip()
            before_route, _, route = value.partition("(")
            environment_label = _agents_last_exam_public_id(
                before_route.strip(),
                limit=80,
            )
            environment_route_label = _agents_last_exam_public_id(
                route.rstrip(")").replace("->", "-to-") if route else value,
                limit=160,
            )
            in_units = False
            continue
        if line.startswith("concurrency:"):
            concurrency = _agents_last_exam_parse_int(line.split(":", 1)[1])
            in_units = False
            continue
        if line.startswith("units (") and line.endswith("):"):
            count_text = line[len("units (") : -len("):")]
            declared_unit_count = _agents_last_exam_parse_int(count_text)
            in_units = True
            continue
        if in_units:
            parts = line.split()
            if len(parts) >= 3:
                agent_label = _agents_last_exam_public_id(parts[0], limit=80)
                task_label = _agents_last_exam_public_id(parts[1], limit=180)
                variant_label = _agents_last_exam_public_id(parts[2], limit=40)
                units.append(
                    {
                        "agent": agent_label,
                        "task": task_label,
                        "variant": variant_label,
                    }
                )

    expected_task_label = _agents_last_exam_public_id(expected_task_id, limit=180)
    expected_agent_label = _agents_last_exam_public_id(expected_agent_id, limit=80)
    blockers: list[str] = []
    if parsed_exit_code != 0:
        blockers.append("ale_dry_run_exit_nonzero")
    if declared_unit_count is None:
        blockers.append("ale_dry_run_unit_count_missing")
    elif declared_unit_count != len(units):
        blockers.append("ale_dry_run_unit_count_mismatch")
    if expected_task_label and expected_task_label not in {
        str(unit.get("task") or "") for unit in units
    }:
        blockers.append("expected_task_not_in_dry_run_matrix")
    if expected_agent_label and expected_agent_label not in {
        str(unit.get("agent") or "") for unit in units
    }:
        blockers.append("expected_agent_not_in_dry_run_matrix")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_compact_ale_dry_run_result_ingest",
        "blockers": blockers,
        "exit_code": parsed_exit_code,
        "experiment": experiment_label,
        "environment": {
            "kind": environment_label,
            "route": environment_route_label,
        },
        "concurrency": concurrency,
        "unit_count_declared": declared_unit_count,
        "unit_count_parsed": len(units),
        "units": units[:50],
        "unit_list_truncated": len(units) > 50,
        "expected": {
            "agent": expected_agent_label,
            "task": expected_task_label,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_stdout_recorded": False,
        },
        "decision": {
            "next_allowed_action": "use_compact_ale_dry_run_result_for_run_gate"
            if ready
            else "repair_ale_dry_run_result_before_run_gate",
            "minimum_next_evidence": (
                "A compact ALE dry-run matrix with exit_code=0, matching expected "
                "agent/task labels, and no raw stdout/path/task-body leakage."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "raw_stdout_recorded": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_event_type_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        event_type = _agents_last_exam_public_id(
            row.get("type") or row.get("event_type") or row.get("event"),
            limit=80,
        )
        if not event_type:
            continue
        counts[event_type] = counts.get(event_type, 0) + 1
    return dict(sorted(counts.items())[:10])

def _agents_last_exam_nested(source: dict[str, Any], field: str) -> Any:
    value = source.get(field)
    if value is not None:
        return value
    unit = source.get("unit") if isinstance(source.get("unit"), dict) else {}
    value = unit.get(field)
    if value is not None:
        return value
    meta = source.get("meta") if isinstance(source.get("meta"), dict) else {}
    return meta.get(field)

def _agents_last_exam_docker_image_metadata(image_ref: str) -> dict[str, Any]:
    """Inspect local Docker image metadata without starting a container."""

    if not shutil.which("docker"):
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": False,
            "first_blocker": "docker_cli_missing",
        }
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image_ref, "--format", "{{json .}}"],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": False,
            "first_blocker": "docker_image_inspect_failed",
        }
    if result.returncode != 0 or not result.stdout.strip():
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_missing",
        }
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {
            "image_ref": image_ref,
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_inspect_not_json",
        }
    repo_digests = raw.get("RepoDigests") if isinstance(raw.get("RepoDigests"), list) else []
    metadata = raw.get("Metadata") if isinstance(raw.get("Metadata"), dict) else {}
    return {
        "image_ref": image_ref,
        "present": True,
        "probe_available": True,
        "id": _agents_last_exam_public_id(raw.get("Id"), limit=160),
        "digest": _agents_last_exam_public_id(
            next((item for item in repo_digests if isinstance(item, str)), None),
            limit=180,
        ),
        "architecture": _agents_last_exam_public_id(raw.get("Architecture"), limit=40),
        "os": _agents_last_exam_public_id(raw.get("Os"), limit=40),
        "size_bytes": int(raw.get("Size"))
        if isinstance(raw.get("Size"), int) and not isinstance(raw.get("Size"), bool)
        else None,
        "created": _agents_last_exam_public_id(raw.get("Created"), limit=80),
        "last_tag_time": _agents_last_exam_public_id(
            metadata.get("LastTagTime"),
            limit=80,
        ),
        "first_blocker": None,
    }

def _agents_last_exam_public_image_metadata(
    metadata: dict[str, Any],
    *,
    fallback_image_ref: str,
) -> dict[str, Any]:
    """Reduce Docker image metadata to compact public-safe fields."""

    image_ref = metadata.get("image_ref") or fallback_image_ref
    reduced: dict[str, Any] = {
        "image_ref": _agents_last_exam_public_id(image_ref, limit=180)
        or "image_ref_unavailable",
        "present": metadata.get("present") is True,
        "probe_available": metadata.get("probe_available") is True,
        "first_blocker": _agents_last_exam_public_id(
            metadata.get("first_blocker"),
            limit=80,
        ),
    }
    for field, limit in (
        ("id", 160),
        ("digest", 180),
        ("architecture", 40),
        ("os", 40),
        ("created", 80),
        ("last_tag_time", 80),
    ):
        value = _agents_last_exam_public_id(metadata.get(field), limit=limit)
        if value:
            reduced[field] = value
    size_bytes = metadata.get("size_bytes")
    if isinstance(size_bytes, int) and not isinstance(size_bytes, bool):
        reduced["size_bytes"] = size_bytes
    return reduced

def _agents_last_exam_disk_headroom() -> dict[str, Any]:
    usage = shutil.disk_usage(Path.cwd())
    free_gib = usage.free / (1024**3)
    total_gib = usage.total / (1024**3)
    used_pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    return {
        "free_gib": round(free_gib, 2),
        "total_gib": round(total_gib, 2),
        "used_percent": round(used_pct, 2),
        "path_recorded": False,
    }

def _agents_last_exam_disk_headroom_for_path(path: Path | None) -> dict[str, Any]:
    try:
        probe_path = path if path is not None and path.exists() else Path.cwd()
        usage = shutil.disk_usage(probe_path)
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "free_gib": None,
            "total_gib": None,
            "used_percent": None,
            "path_recorded": False,
        }
    free_gib = usage.free / (1024**3)
    total_gib = usage.total / (1024**3)
    used_pct = (usage.used / usage.total * 100.0) if usage.total else 0.0
    return {
        "checked": True,
        "free_gib": round(free_gib, 2),
        "total_gib": round(total_gib, 2),
        "used_percent": round(used_pct, 2),
        "path_recorded": False,
    }

def build_agents_last_exam_local_preflight(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a local ALE adapter preflight without task/body/run execution."""

    task_label = (
        _agents_last_exam_public_id(selected_task_id, limit=160)
        or "metadata_only_candidate"
    )
    primary_raw = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    alternate_raw = (
        alternate_image_metadata
        if isinstance(alternate_image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(alternate_image_ref)
    )
    primary = _agents_last_exam_public_image_metadata(
        primary_raw,
        fallback_image_ref=image_ref,
    )
    alternate = _agents_last_exam_public_image_metadata(
        alternate_raw,
        fallback_image_ref=alternate_image_ref,
    )
    disk = (
        disk_headroom
        if isinstance(disk_headroom, dict)
        else _agents_last_exam_disk_headroom()
    )
    no_cloud = provider_kind == "docker"
    no_upload = True
    required_image_present = primary.get("present") is True
    ready = bool(no_cloud and no_upload and required_image_present)
    if not no_cloud:
        first_blocker = "provider_is_not_local_docker"
    elif not primary.get("probe_available", True):
        first_blocker = primary.get("first_blocker") or "docker_probe_unavailable"
    elif not required_image_present:
        first_blocker = primary.get("first_blocker") or "required_docker_image_missing"
    else:
        first_blocker = "ready_for_local_no_upload_preflight"

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_PREFLIGHT_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": task_label,
        "snapshot": _agents_last_exam_public_id(snapshot, limit=80)
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "provider": {
            "kind": provider_kind,
            "no_cloud": no_cloud,
            "required_image": primary,
            "alternate_image": alternate,
        },
        "disk_headroom": disk,
        "ready": ready,
        "first_blocker": first_blocker,
        "boundary": {
            "local_only": True,
            "no_cloud": no_cloud,
            "no_upload": no_upload,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "local_paths_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_no_upload_adapter_dry_run"
            if ready
            else "repair_preflight_blocker_before_ale_run",
            "minimum_next_evidence": (
                "A no-cloud/no-upload ALE adapter dry-run that confirms local "
                "Docker provider selection and compact ingest boundaries."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "leaderboard evidence",
                "LoopX treatment advantage",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }

def build_agents_last_exam_local_dry_run_plan(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan an ALE local adapter dry-run without running the adapter."""

    preflight_payload = (
        preflight
        if isinstance(preflight, dict)
        else build_agents_last_exam_local_preflight(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
        )
    )
    boundary = (
        preflight_payload.get("boundary")
        if isinstance(preflight_payload.get("boundary"), dict)
        else {}
    )
    read_boundary = (
        preflight_payload.get("read_boundary")
        if isinstance(preflight_payload.get("read_boundary"), dict)
        else {}
    )
    forbidden_side_effects = {
        "container_started": False,
        "task_body_read": False,
        "model_api_invoked": False,
        "raw_trajectory_read": False,
        "screenshot_captured": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
        "submit_eligible": False,
        "leaderboard_evidence": False,
    }
    boundary_preserved = (
        boundary.get("local_only") is True
        and boundary.get("no_cloud") is True
        and boundary.get("no_upload") is True
        and all(
            boundary.get(field) is expected
            for field, expected in forbidden_side_effects.items()
        )
        and read_boundary.get("compact_only") is True
        and read_boundary.get("task_text_read") is False
        and read_boundary.get("raw_artifacts_read") is False
        and read_boundary.get("local_paths_recorded") is False
    )
    preflight_ready = preflight_payload.get("ready") is True
    blockers: list[str] = []
    if not preflight_ready:
        blockers.append(
            _agents_last_exam_public_id(
                preflight_payload.get("first_blocker"),
                limit=80,
            )
            or "ale_local_preflight_not_ready"
        )
    if not boundary_preserved:
        blockers.append("ale_local_boundary_not_preserved")
    ready = preflight_ready and boundary_preserved

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_DRY_RUN_PLAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": preflight_payload.get("task_id") or "metadata_only_candidate",
        "snapshot": preflight_payload.get("snapshot")
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "preflight": preflight_payload,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else "ready_for_contract_only_dry_run_plan",
        "blockers": blockers,
        "adapter_plan": {
            "mode": "contract_only_no_execution",
            "provider": "local_docker",
            "will_start_container": False,
            "will_read_task_body": False,
            "will_invoke_model_api": False,
            "will_upload": False,
            "will_submit": False,
            "will_capture_screenshot": False,
            "will_record_credentials": False,
            "will_record_local_paths": False,
            "allowed_probes": [
                "local_docker_image_inspect",
                "disk_headroom_summary",
                "public_task_id_label",
                "compact_boundary_flags",
            ],
            "required_before_real_dry_run": [
                "selected_public_task_id_label",
                "local_docker_provider_confirmed",
                "submit_eligible_false",
                "compact_result_writer_boundary_declared",
                "stop_before_task_body_or_raw_outputs",
            ],
        },
        "paired_run_requirements": {
            "same_task": True,
            "same_model": True,
            "same_sandbox_provider": True,
            "same_timeout": True,
            "same_attempt_count": True,
            "same_grading_path": True,
            "baseline_arm": "hardened-codex",
            "treatment_arm": "codex-loopx",
        },
        "claim_boundary": {
            "may_claim": [
                "ALE local adapter dry-run prerequisites are represented as a compact gate",
                "The gate did not start containers, read task bodies, invoke model APIs, upload, or submit",
                "A future real dry-run must preserve the same no-cloud/no-upload boundary",
            ],
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
                "raw trajectory or screenshot evidence",
            ],
        },
        "decision": {
            "next_allowed_action": "run_operator_authorized_no_upload_ale_adapter_dry_run"
            if ready
            else "repair_ale_local_dry_run_plan_blocker",
            "minimum_next_evidence": (
                "A real no-cloud/no-upload adapter dry-run may only proceed if "
                "it preserves the same boundary flags and produces compact "
                "run/eval/events metadata without raw task or trajectory content."
            ),
            "stop_condition": (
                "Stop before task body, hidden references, raw trajectory, "
                "screenshots, credential values, local absolute paths, model "
                "APIs, uploads, submissions, leaderboard claims, paid compute, "
                "or production actions."
            ),
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_runner_binary_probe(runner_binary: str | None) -> dict[str, Any]:
    binary = _agents_last_exam_public_id(runner_binary, limit=80)
    if not runner_binary:
        return {
            "binary": None,
            "declared": False,
            "available": False,
            "first_blocker": "runner_binary_missing",
            "path_recorded": False,
        }
    if not binary:
        return {
            "binary": None,
            "declared": True,
            "available": False,
            "first_blocker": "runner_binary_not_public_safe",
            "path_recorded": False,
        }
    if "/" in runner_binary or "\\" in runner_binary:
        return {
            "binary": binary,
            "declared": True,
            "available": False,
            "first_blocker": "runner_binary_must_be_name_not_path",
            "path_recorded": False,
        }
    available = shutil.which(runner_binary) is not None
    return {
        "binary": binary,
        "declared": True,
        "available": available,
        "first_blocker": None if available else "runner_binary_not_found",
        "path_recorded": False,
    }

def _agents_last_exam_python_module_probe(
    module_name: str | None,
    *,
    source_root: str | None = None,
) -> dict[str, Any]:
    module = _agents_last_exam_public_id(module_name, limit=100)
    source_root_declared = bool(source_root)
    source_root_available = False
    source_root_path: Path | None = None
    if source_root:
        try:
            source_root_path = Path(source_root).expanduser()
        except (OSError, RuntimeError):
            source_root_path = None
        source_root_available = bool(source_root_path and source_root_path.is_dir())
    if not module_name:
        return {
            "module": None,
            "declared": False,
            "available": False,
            "first_blocker": "runner_python_module_missing",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if source_root_declared and not source_root_available:
        return {
            "module": module,
            "declared": True,
            "available": False,
            "first_blocker": "runner_source_root_missing",
            "source_root_declared": True,
            "source_root_available": False,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if not module or "/" in module_name or "\\" in module_name:
        return {
            "module": None,
            "declared": True,
            "available": False,
            "first_blocker": "runner_python_module_not_public_safe",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    parts = module_name.split(".")
    if not parts or any(not part.isidentifier() for part in parts):
        return {
            "module": module,
            "declared": True,
            "available": False,
            "first_blocker": "runner_python_module_not_public_safe",
            "source_root_declared": source_root_declared,
            "source_root_available": source_root_available,
            "source_root_path_recorded": False,
            "path_recorded": False,
        }
    if source_root_path is not None:
        source_root_text = str(source_root_path)
        sys.path.insert(0, source_root_text)
        importlib.invalidate_caches()
        try:
            available = importlib.util.find_spec(module_name) is not None
        finally:
            try:
                sys.path.remove(source_root_text)
            except ValueError:
                pass
            importlib.invalidate_caches()
    else:
        available = importlib.util.find_spec(module_name) is not None
    return {
        "module": module,
        "declared": True,
        "available": available,
        "first_blocker": None if available else "runner_python_module_not_found",
        "source_root_declared": source_root_declared,
        "source_root_available": source_root_available,
        "source_root_path_recorded": False,
        "path_recorded": False,
    }

def _agents_last_exam_runner_binary_requires_python_module(
    runner_binary: str | None,
) -> bool:
    if not isinstance(runner_binary, str):
        return False
    binary = Path(runner_binary).name.lower()
    return binary == "python" or binary.startswith("python3")

def _agents_last_exam_codex_cli_probe(
    codex_binary: str | None,
    *,
    binary_available: bool | None = None,
    version_text: str | None = None,
) -> dict[str, Any]:
    """Probe host Codex CLI readiness without recording paths or argv."""

    runner_probe = _agents_last_exam_runner_binary_probe(codex_binary)
    unsafe_binary_blockers = {
        "runner_binary_must_be_name_not_path",
        "runner_binary_not_public_safe",
    }
    if (
        binary_available is not None
        and runner_probe.get("declared") is True
        and runner_probe.get("first_blocker") not in unsafe_binary_blockers
    ):
        runner_probe = {
            **runner_probe,
            "available": bool(binary_available),
            "first_blocker": None
            if binary_available
            else (runner_probe.get("first_blocker") or "codex_binary_not_available"),
        }

    version_label = _agents_last_exam_public_id(version_text, limit=120)
    version_probe_available = bool(version_label)
    if (
        version_text is None
        and runner_probe.get("available") is True
        and isinstance(codex_binary, str)
        and codex_binary
        and "/" not in codex_binary
        and "\\" not in codex_binary
    ):
        try:
            result = subprocess.run(
                [codex_binary, "--version"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
            )
        except Exception:
            result = None
        if result is not None and result.returncode == 0:
            version_label = _agents_last_exam_public_id(
                result.stdout.strip() or result.stderr.strip(),
                limit=120,
            )
            version_probe_available = bool(version_label)

    first_blocker = _agents_last_exam_public_id(
        runner_probe.get("first_blocker"),
        limit=80,
    )
    if runner_probe.get("available") is True and not version_probe_available:
        first_blocker = "codex_version_probe_failed"

    return {
        "binary": runner_probe.get("binary"),
        "binary_declared": runner_probe.get("declared") is True,
        "binary_available": runner_probe.get("available") is True,
        "version": version_label,
        "version_probe_available": version_probe_available,
        "binary_path_recorded": False,
        "command_argv_recorded": False,
        "first_blocker": first_blocker,
    }

def _agents_last_exam_cua_mcp_assets_probe(
    assets_root: str | None,
) -> dict[str, Any]:
    """Check local CUA MCP server assets without recording host paths."""

    if not assets_root:
        return {
            "declared": False,
            "available": False,
            "package_json_present": False,
            "server_entry_present": False,
            "package_lock_present": False,
            "path_recorded": False,
            "first_blocker": "cua_mcp_assets_root_missing",
        }
    try:
        root = Path(assets_root).expanduser()
    except (OSError, RuntimeError):
        root = None
    available = bool(root and root.is_dir())
    package_json_present = bool(root and (root / "package.json").is_file())
    package_lock_present = bool(root and (root / "package-lock.json").is_file())
    server_entry_present = bool(root and (root / "src" / "index.js").is_file())
    if not available:
        first_blocker = "cua_mcp_assets_root_not_available"
    elif not package_json_present:
        first_blocker = "cua_mcp_package_json_missing"
    elif not server_entry_present:
        first_blocker = "cua_mcp_server_entry_missing"
    else:
        first_blocker = None
    return {
        "declared": True,
        "available": available,
        "package_json_present": package_json_present,
        "server_entry_present": server_entry_present,
        "package_lock_present": package_lock_present,
        "path_recorded": False,
        "first_blocker": first_blocker,
    }

def build_agents_last_exam_host_codex_cli_route(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Gate the ALE host-Codex route before any task-level execution.

    The contract intentionally checks only host-side existence/probe facts. It
    must not read, print, copy, or persist Codex auth material or task content.
    """

    codex_probe = _agents_last_exam_codex_cli_probe(
        codex_binary,
        binary_available=codex_binary_available,
        version_text=codex_version_text,
    )
    auth_present = (
        Path.home().joinpath(".codex", "auth.json").is_file()
        if host_auth_cache_present is None
        else bool(host_auth_cache_present)
    )
    config_present = (
        Path.home().joinpath(".codex", "config.toml").is_file()
        if host_config_present is None
        else bool(host_config_present)
    )
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)

    blockers: list[str] = []
    if operator_authorized_host_codex_auth is not True:
        blockers.append("operator_authorization_missing")
    if codex_probe.get("binary_available") is not True:
        blockers.append(
            _agents_last_exam_public_id(codex_probe.get("first_blocker"), limit=80)
            or "host_codex_binary_not_available"
        )
    if codex_probe.get("version_probe_available") is not True:
        blockers.append("host_codex_version_probe_missing")
    if auth_present is not True:
        blockers.append("host_codex_auth_cache_missing")
    if require_host_config and config_present is not True:
        blockers.append("host_codex_config_missing")
    if assets_probe.get("first_blocker"):
        blockers.append(
            _agents_last_exam_public_id(assets_probe.get("first_blocker"), limit=80)
            or "cua_mcp_assets_not_ready"
        )
    if ale_sandbox_cua_smoke_ready is not True:
        blockers.append("ale_sandbox_cua_smoke_not_ready")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CLI_ROUTE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_no_task_host_codex_cua_smoke",
        "blockers": blockers,
        "route": {
            "mode": "host_codex_cli_local_executor",
            "uses_host_codex_cli": True,
            "uses_existing_host_codex_auth": True,
            "runs_codex_inside_ale_sandbox": False,
            "drives_ale_sandbox_via_cua_mcp": True,
            "upstream_sandbox_codex_agent_bypassed": True,
            "upstream_provider_key_path_required": False,
            "next_smoke": "no_task_host_codex_cli_cua_mcp_smoke",
        },
        "host_codex_cli": codex_probe,
        "host_auth": {
            "auth_cache_present": auth_present,
            "config_present": config_present,
            "config_required": require_host_config,
            "auth_values_read": False,
            "config_content_read": False,
            "credential_values_recorded": False,
            "auth_material_copied_to_sandbox": False,
            "whole_codex_dir_copied": False,
            "paths_recorded": False,
        },
        "cua_mcp_assets": assets_probe,
        "ale_sandbox": {
            "cua_smoke_ready": ale_sandbox_cua_smoke_ready is True,
            "container_started_by_this_check": False,
            "sandbox_auth_material_present": False,
            "sandbox_auth_values_read": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_no_task_host_codex_cli_cua_smoke"
            if ready
            else "repair_host_codex_cli_route_blocker",
            "minimum_next_evidence": (
                "A no-task host Codex CLI smoke using a project-local temporary "
                "Codex config and the ALE CUA MCP bridge, with no task prompt, "
                "no credential values, no upload, no submit, and compact result "
                "only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_codex_exec_surface_probe(
    codex_binary: str | None,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }
    try:
        result = subprocess.run(
            [codex_binary, "exec", "--help"],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception:
        return {
            "available": False,
            "exit_code": None,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
            "model_invoked": False,
            "first_blocker": "codex_exec_help_probe_failed",
        }
    ok = result.returncode == 0
    return {
        "available": ok,
        "exit_code": result.returncode,
        "stdout_recorded": False,
        "stderr_recorded": False,
        "command_argv_recorded": False,
        "model_invoked": False,
        "first_blocker": None if ok else "codex_exec_help_nonzero",
    }

def _agents_last_exam_codex_mcp_config_probe(
    codex_binary: str | None,
    *,
    cua_mcp_assets_root: str | None,
    cua_server_url: str,
) -> dict[str, Any]:
    codex_probe = _agents_last_exam_codex_cli_probe(codex_binary)
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if codex_probe.get("binary_available") is not True:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": codex_probe.get("first_blocker")
            or "host_codex_binary_not_available",
        }
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not isinstance(codex_binary, str) or "/" in codex_binary or "\\" in codex_binary:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "host_codex_binary_not_public_safe",
        }

    try:
        assets_root = Path(str(cua_mcp_assets_root)).expanduser().resolve()
        with tempfile.TemporaryDirectory(prefix="loopx-codex-home-") as tmp:
            codex_home = Path(tmp)
            mcp_entry = assets_root / "src" / "index.js"
            config_text = "\n".join(
                [
                    "[mcp_servers.cua]",
                    'command = "node"',
                    f'args = ["{mcp_entry}"]',
                    f'env = {{ CUA_SERVER_URL = "{cua_server_url}" }}',
                    "",
                ]
            )
            (codex_home / "config.toml").write_text(config_text, encoding="utf-8")
            env = os.environ.copy()
            env["CODEX_HOME"] = str(codex_home)
            result = subprocess.run(
                [codex_binary, "mcp", "list", "--json"],
                check=False,
                text=True,
                capture_output=True,
                timeout=20,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "server_detected": False,
            "server_enabled": False,
            "transport": None,
            "raw_output_recorded": False,
            "config_path_recorded": False,
            "mcp_server_path_recorded": False,
            "command_argv_recorded": False,
            "auth_values_read": False,
            "first_blocker": "codex_mcp_config_probe_failed",
        }

    server_detected = False
    server_enabled = False
    transport_type: str | None = None
    if result.returncode == 0:
        try:
            rows = json.loads(result.stdout)
        except json.JSONDecodeError:
            rows = []
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict) or row.get("name") != "cua":
                    continue
                server_detected = True
                server_enabled = row.get("enabled") is True
                transport = row.get("transport")
                if isinstance(transport, dict):
                    transport_type = _agents_last_exam_public_id(
                        transport.get("type"),
                        limit=40,
                    )
                break
    if result.returncode != 0:
        first_blocker = "codex_mcp_list_nonzero"
    elif not server_detected:
        first_blocker = "codex_mcp_cua_server_not_detected"
    elif not server_enabled:
        first_blocker = "codex_mcp_cua_server_not_enabled"
    elif transport_type != "stdio":
        first_blocker = "codex_mcp_cua_transport_not_stdio"
    else:
        first_blocker = None
    return {
        "available": first_blocker is None,
        "server_detected": server_detected,
        "server_enabled": server_enabled,
        "transport": transport_type,
        "raw_output_recorded": False,
        "config_path_recorded": False,
        "mcp_server_path_recorded": False,
        "command_argv_recorded": False,
        "auth_values_read": False,
        "first_blocker": first_blocker,
    }

def _agents_last_exam_fake_cua_server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("content-length") or "0")
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                request = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                request = {}
            command = request.get("command")
            if command == "get_screen_size":
                payload = {"success": True, "size": {"width": 1024, "height": 768}}
            elif command == "screenshot":
                payload = {"success": True, "image_data": "iVBORw0KGgo="}
            elif command == "get_cursor_position":
                payload = {"success": True, "position": {"x": 512, "y": 384}}
            else:
                payload = {"success": True}
            data = f"data: {json.dumps(payload)}\n\n".encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def _agents_last_exam_cua_mcp_test_probe(
    *,
    cua_mcp_assets_root: str | None,
    install_node_deps: bool = False,
) -> dict[str, Any]:
    assets_probe = _agents_last_exam_cua_mcp_assets_probe(cua_mcp_assets_root)
    if assets_probe.get("first_blocker"):
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": assets_probe.get("first_blocker")
            or "cua_mcp_assets_not_ready",
        }
    if not shutil.which("node"):
        return {
            "available": False,
            "node_available": False,
            "npm_install_attempted": False,
            "fake_cua_server_used": False,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "node_cli_missing",
        }

    server = None
    try:
        with tempfile.TemporaryDirectory(prefix="loopx-cua-mcp-") as tmp:
            work_root = Path(tmp) / "cua_mcp_server"
            shutil.copytree(str(cua_mcp_assets_root), work_root)
            node_modules = work_root / "node_modules"
            npm_install_attempted = False
            if not node_modules.is_dir():
                if not install_node_deps:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_node_modules_missing",
                    }
                if not shutil.which("npm"):
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": False,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "npm_cli_missing",
                    }
                npm_install_attempted = True
                npm_result = subprocess.run(
                    ["npm", "install", "--production", "--silent"],
                    cwd=work_root,
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=120,
                )
                if npm_result.returncode != 0:
                    return {
                        "available": False,
                        "node_available": True,
                        "npm_install_attempted": True,
                        "fake_cua_server_used": False,
                        "raw_output_recorded": False,
                        "command_argv_recorded": False,
                        "local_paths_recorded": False,
                        "first_blocker": "cua_mcp_npm_install_failed",
                    }
            server = _agents_last_exam_fake_cua_server()
            port = server.server_address[1]
            env = os.environ.copy()
            env["CUA_SERVER_URL"] = f"http://127.0.0.1:{port}"
            test_result = subprocess.run(
                ["node", "src/index.js", "--test"],
                cwd=work_root,
                check=False,
                text=True,
                capture_output=True,
                timeout=60,
                env=env,
            )
    except Exception:
        return {
            "available": False,
            "node_available": shutil.which("node") is not None,
            "npm_install_attempted": install_node_deps,
            "fake_cua_server_used": server is not None,
            "raw_output_recorded": False,
            "command_argv_recorded": False,
            "local_paths_recorded": False,
            "first_blocker": "cua_mcp_test_probe_failed",
        }
    finally:
        if server is not None:
            server.shutdown()
            server.server_close()

    ok = test_result.returncode == 0
    return {
        "available": ok,
        "node_available": True,
        "npm_install_attempted": npm_install_attempted,
        "fake_cua_server_used": True,
        "raw_output_recorded": False,
        "command_argv_recorded": False,
        "local_paths_recorded": False,
        "first_blocker": None if ok else "cua_mcp_test_nonzero",
    }

def build_agents_last_exam_host_codex_cua_no_task_smoke(
    *,
    route_gate: dict[str, Any],
    codex_exec_probe: dict[str, Any],
    mcp_config_probe: dict[str, Any],
    cua_mcp_test_probe: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if route_gate.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(route_gate.get("first_blocker"), limit=80)
            or "host_codex_route_gate_not_ready"
        )
    for probe_name, probe in (
        ("codex_exec_surface", codex_exec_probe),
        ("codex_mcp_config", mcp_config_probe),
        ("cua_mcp_bridge", cua_mcp_test_probe),
    ):
        if probe.get("available") is not True:
            blockers.append(
                _agents_last_exam_public_id(probe.get("first_blocker"), limit=80)
                or f"{probe_name}_not_ready"
            )
    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_task_level_ale_codex_dry_run_gate",
        "blockers": blockers,
        "route_gate_ready": route_gate.get("ready") is True,
        "route_gate": route_gate,
        "codex_exec_surface": codex_exec_probe,
        "codex_mcp_config": mcp_config_probe,
        "cua_mcp_bridge": cua_mcp_test_probe,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_operator_authorized_task_level_ale_codex_dry_run"
            if ready
            else "repair_no_task_host_codex_cua_smoke_blocker",
            "minimum_next_evidence": (
                "An operator-authorized task-level ALE dry-run may proceed only "
                "after compact route, Codex exec surface, Codex MCP config, and "
                "CUA MCP bridge probes are ready."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "auth_values_read": False,
            "config_content_read": False,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def build_agents_last_exam_host_codex_cua_no_task_smoke_from_environment(
    *,
    codex_binary: str | None = "codex",
    codex_binary_available: bool | None = None,
    codex_version_text: str | None = None,
    host_auth_cache_present: bool | None = None,
    host_config_present: bool | None = None,
    require_host_config: bool = False,
    cua_mcp_assets_root: str | None = None,
    cua_server_url: str = "http://127.0.0.1:8000",
    install_node_deps: bool = False,
    ale_sandbox_cua_smoke_ready: bool = False,
    operator_authorized_host_codex_auth: bool = False,
) -> dict[str, Any]:
    """Build compact no-task host Codex/CUA readiness evidence.

    This is deliberately a pre-task probe: it checks CLI/help, Codex MCP config
    loading, and the local CUA MCP bridge without sending a Codex prompt,
    reading task material, or recording auth/path/raw-output details.
    """

    route_gate = build_agents_last_exam_host_codex_cli_route(
        codex_binary=codex_binary,
        codex_binary_available=codex_binary_available,
        codex_version_text=codex_version_text,
        host_auth_cache_present=host_auth_cache_present,
        host_config_present=host_config_present,
        require_host_config=require_host_config,
        cua_mcp_assets_root=cua_mcp_assets_root,
        ale_sandbox_cua_smoke_ready=ale_sandbox_cua_smoke_ready,
        operator_authorized_host_codex_auth=operator_authorized_host_codex_auth,
    )
    codex_exec_probe = _agents_last_exam_codex_exec_surface_probe(codex_binary)
    mcp_config_probe = _agents_last_exam_codex_mcp_config_probe(
        codex_binary,
        cua_mcp_assets_root=cua_mcp_assets_root,
        cua_server_url=cua_server_url,
    )
    cua_mcp_test_probe = _agents_last_exam_cua_mcp_test_probe(
        cua_mcp_assets_root=cua_mcp_assets_root,
        install_node_deps=install_node_deps,
    )
    return build_agents_last_exam_host_codex_cua_no_task_smoke(
        route_gate=route_gate,
        codex_exec_probe=codex_exec_probe,
        mcp_config_probe=mcp_config_probe,
        cua_mcp_test_probe=cua_mcp_test_probe,
    )

def _agents_last_exam_boundary_flag(
    payload: dict[str, Any],
    key: str,
    *,
    default: bool = False,
) -> bool:
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    return bool(boundary.get(key, default))

def _agents_last_exam_ready_input(
    payload: dict[str, Any],
    *,
    schema_version: str,
    blocker_prefix: str,
) -> tuple[bool, str | None]:
    if not isinstance(payload, dict):
        return False, f"{blocker_prefix}_missing"
    if payload.get("schema_version") != schema_version:
        return False, f"{blocker_prefix}_schema_mismatch"
    if payload.get("ready") is not True:
        first_blocker = _agents_last_exam_public_id(
            payload.get("first_blocker"),
            limit=80,
        )
        return False, first_blocker or f"{blocker_prefix}_not_ready"
    return True, None

def _agents_last_exam_source_freshness_input(
    launch_packet: dict[str, Any] | None,
    *,
    required: bool,
) -> tuple[bool | None, str | None]:
    if not required:
        return None, None
    if not isinstance(launch_packet, dict):
        return False, "fresh_source_launch_packet_missing"
    source_lock = launch_packet.get("source_lock")
    if not isinstance(source_lock, dict):
        return False, "ale_source_freshness_not_verified"
    if source_lock.get("fetch_origin_attempted") is not True:
        return False, "ale_source_fetch_origin_not_attempted"
    if source_lock.get("fetch_origin_ok") is not True:
        return False, "ale_source_fetch_origin_failed"
    if source_lock.get("require_upstream_current") is not True:
        return False, "ale_source_upstream_current_not_required"
    if source_lock.get("upstream_declared") is not True:
        return False, "ale_source_upstream_missing"
    if source_lock.get("head_matches_upstream") is not True:
        return False, "ale_source_not_at_upstream_head"
    if source_lock.get("upstream_ahead_count") != 0:
        return False, "ale_source_upstream_ahead_count_nonzero"
    if source_lock.get("upstream_behind_count") != 0:
        return False, "ale_source_upstream_behind_count_nonzero"
    return True, None

def _agents_last_exam_case_state_init_contract_input(
    launch_packet: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if not isinstance(launch_packet, dict):
        return False, "launch_packet_missing_for_case_state_init_contract"
    contract = launch_packet.get("case_state_init_contract")
    if not isinstance(contract, dict):
        return False, "case_state_init_contract_missing"
    if contract.get("schema_version") != BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION:
        return False, "case_state_init_contract_schema_mismatch"
    if contract.get("benchmark_case_goal_id") != AGENTS_LAST_EXAM_CASE_GOAL_ID:
        return False, "case_state_init_contract_goal_id_mismatch"
    if contract.get("case_state_path") != AGENTS_LAST_EXAM_CASE_STATE_PATH:
        return False, "case_state_init_contract_path_mismatch"
    if contract.get("init_required_before_worker") is not True:
        return False, "case_state_init_not_required_before_worker"
    if contract.get("initialized_by_launch_packet") is not False:
        return False, "case_state_initialized_by_no_execution_packet"
    if contract.get("surrogate_state_files_allowed") is not False:
        return False, "case_state_surrogate_files_allowed"
    if contract.get("raw_task_text_required_for_init") is not False:
        return False, "case_state_init_requires_raw_task_text"
    if contract.get("local_paths_recorded") is not False:
        return False, "case_state_init_contract_local_paths_recorded"
    proof_fields = contract.get("proof_fields")
    required_fields = set(BENCHMARK_CASE_ACTIVE_STATE_PROOF_FIELDS)
    if not isinstance(proof_fields, list) or not required_fields.issubset(
        {str(field) for field in proof_fields}
    ):
        return False, "case_state_init_contract_proof_fields_incomplete"
    return True, None

def build_agents_last_exam_validation_run_gate(
    *,
    selected_task_id: str | None,
    validation_hypothesis: str | None,
    task_material_readiness: dict[str, Any],
    host_codex_no_task_e2e: dict[str, Any],
    exact_dry_run_result: dict[str, Any],
    launch_packet: dict[str, Any] | None = None,
    result_reducer_ready: bool = False,
    no_upload: bool = True,
    submit_enabled: bool = False,
    leaderboard_enabled: bool = False,
    formal_score_candidate: bool = False,
    require_fresh_source: bool = False,
    expected_formal_agent: str = "host_codex_gpt55_xhigh",
) -> dict[str, Any]:
    """Combine compact ALE readiness into a pre-run decision gate."""

    task_label = _agents_last_exam_public_id(selected_task_id, limit=180)
    hypothesis_label = _agents_last_exam_public_id(validation_hypothesis, limit=240)
    fresh_source_required = bool(formal_score_candidate or require_fresh_source)
    blockers: list[str] = []
    for payload, schema_version, prefix in (
        (
            task_material_readiness,
            AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
            "task_material_readiness",
        ),
        (
            host_codex_no_task_e2e,
            AGENTS_LAST_EXAM_HOST_CODEX_CUA_NO_TASK_SMOKE_SCHEMA_VERSION,
            "host_codex_no_task_e2e",
        ),
        (
            exact_dry_run_result,
            AGENTS_LAST_EXAM_LOCAL_EXACT_DRY_RUN_RESULT_SCHEMA_VERSION,
            "exact_dry_run_result",
        ),
    ):
        ready, blocker = _agents_last_exam_ready_input(
            payload,
            schema_version=schema_version,
            blocker_prefix=prefix,
        )
        if not ready and blocker:
            blockers.append(blocker)

    launch_packet_ready = None
    if launch_packet is not None:
        ready, blocker = _agents_last_exam_ready_input(
            launch_packet,
            schema_version=AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
            blocker_prefix="launch_packet",
        )
        launch_packet_ready = ready
        if not ready and blocker:
            blockers.append(blocker)

    fresh_source_ready, fresh_source_blocker = _agents_last_exam_source_freshness_input(
        launch_packet,
        required=fresh_source_required,
    )
    if fresh_source_blocker:
        blockers.append(fresh_source_blocker)
    case_state_contract_ready, case_state_contract_blocker = (
        _agents_last_exam_case_state_init_contract_input(launch_packet)
    )
    if case_state_contract_blocker:
        blockers.append(case_state_contract_blocker)

    if not hypothesis_label:
        blockers.append("validation_hypothesis_missing")
    if result_reducer_ready is not True:
        blockers.append("compact_result_reducer_not_ready")
    if no_upload is not True:
        blockers.append("no_upload_boundary_not_enabled")
    if submit_enabled:
        blockers.append("submit_must_remain_disabled")
    if leaderboard_enabled:
        blockers.append("leaderboard_must_remain_disabled")

    boundary_payloads = [
        ("task_material_readiness", task_material_readiness),
        ("host_codex_no_task_e2e", host_codex_no_task_e2e),
        ("exact_dry_run_result", exact_dry_run_result),
    ]
    if launch_packet is not None:
        boundary_payloads.append(("launch_packet", launch_packet))
    for name, payload in boundary_payloads:
        if _agents_last_exam_boundary_flag(payload, "credential_values_recorded"):
            blockers.append(f"{name}_credential_values_recorded")
        if _agents_last_exam_boundary_flag(payload, "local_paths_recorded"):
            blockers.append(f"{name}_local_paths_recorded")
        if _agents_last_exam_boundary_flag(payload, "raw_trajectory_read"):
            blockers.append(f"{name}_raw_trajectory_read")
        if _agents_last_exam_boundary_flag(payload, "task_body_read"):
            blockers.append(f"{name}_task_body_read")
        if _agents_last_exam_boundary_flag(payload, "screenshot_captured"):
            blockers.append(f"{name}_screenshot_captured")
        if _agents_last_exam_boundary_flag(payload, "hidden_references_allowed"):
            blockers.append(f"{name}_hidden_refs_allowed")
        if _agents_last_exam_boundary_flag(payload, "production_actions_allowed"):
            blockers.append(f"{name}_production_actions_allowed")

    expected = (
        exact_dry_run_result.get("expected")
        if isinstance(exact_dry_run_result.get("expected"), dict)
        else {}
    )
    expected_task = expected.get("task") if isinstance(expected, dict) else None
    if task_label and expected_task and task_label != expected_task:
        blockers.append("selected_task_mismatch_exact_dry_run")

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_VALIDATION_RUN_GATE_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_operator_authorized_local_no_upload_ale_validation_run",
        "blockers": blockers,
        "selected_task": {
            "task_id": task_label,
            "source": "compact_readiness_artifacts",
        },
        "validation_hypothesis": hypothesis_label,
        "readiness_inputs": {
            "task_material_ready": task_material_readiness.get("ready") is True,
            "host_codex_no_task_e2e_ready": host_codex_no_task_e2e.get("ready") is True,
            "exact_dry_run_ready": exact_dry_run_result.get("ready") is True,
            "launch_packet_ready": launch_packet_ready,
            "fresh_source_required": fresh_source_required,
            "fresh_source_ready": fresh_source_ready,
            "case_state_init_contract_ready": case_state_contract_ready,
            "compact_result_reducer_ready": result_reducer_ready is True,
        },
        "model_policy": {
            "connectivity_e2e_model": "gpt-5.3-codex-spark",
            "formal_score_agent": expected_formal_agent,
            "formal_score_candidate": bool(formal_score_candidate),
        },
        "run_boundary": {
            "local_only": True,
            "no_upload": no_upload is True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "operator_authorization_required_before_task_run": True,
            "case_state_init_required_before_worker": True,
            "case_state_initialized_by_this_gate": False,
            "case_state_path": AGENTS_LAST_EXAM_CASE_STATE_PATH,
            "case_state_schema_version": BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
            "task_run_started_by_this_gate": False,
            "container_started_by_this_gate": False,
            "model_api_invoked_by_this_gate": False,
            "codex_prompt_sent_by_this_gate": False,
            "raw_trajectory_read": False,
            "task_body_read_by_loopx": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "operator_authorized_local_no_upload_ale_validation_run"
            if ready
            else "repair_ale_validation_run_gate_blocker",
            "minimum_next_evidence": (
                "A task-level ALE run may proceed only as local/no-upload/no-submit "
                "work with compact result reduction through the ALE reducer, and "
                "with a concrete LoopX validation hypothesis recorded."
            ),
            "must_not_claim": [
                "ALE task success before compact result ingest",
                "ALE score uplift before paired evidence",
                "LoopX treatment advantage before paired evidence",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
        },
    }

def _agents_last_exam_normalized_repo_label(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith(".git"):
        text = text[:-4]
    text = text.replace("git@github.com:", "https://github.com/")
    text = text.replace("http://github.com/", "https://github.com/")
    return _agents_last_exam_public_id(text, limit=180)

def _agents_last_exam_source_git_metadata(
    source_root: str | None,
    *,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    fetch_origin: bool = False,
) -> dict[str, Any]:
    expected = _agents_last_exam_normalized_repo_label(expected_repo_url)
    source_root_declared = bool(source_root)
    source_root_path: Path | None = None
    if source_root:
        try:
            source_root_path = Path(source_root).expanduser()
        except (OSError, RuntimeError):
            source_root_path = None
    source_root_available = bool(source_root_path and source_root_path.is_dir())
    base = {
        "source_root_declared": source_root_declared,
        "source_root_available": source_root_available,
        "source_root_path_recorded": False,
        "expected_repo": expected,
        "remote": None,
        "remote_matches_expected": False,
        "head": None,
        "upstream_ref": None,
        "upstream_head": None,
        "upstream_declared": False,
        "head_matches_upstream": False,
        "upstream_ahead_count": None,
        "upstream_behind_count": None,
        "fetch_origin_attempted": False,
        "fetch_origin_ok": False,
        "git_probe_available": shutil.which("git") is not None,
        "is_git_checkout": False,
    }
    if not source_root_declared:
        return {**base, "first_blocker": "source_root_missing"}
    if not source_root_available or source_root_path is None:
        return {**base, "first_blocker": "source_root_not_available"}
    if not shutil.which("git"):
        return {**base, "first_blocker": "git_cli_missing"}

    def git_output(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root_path), *args],
                check=False,
                text=True,
                capture_output=True,
                timeout=10,
            )
        except Exception:
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None

    def git_run(*args: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "-C", str(source_root_path), *args],
                check=False,
                text=True,
                capture_output=True,
                timeout=30,
            )
        except Exception:
            return False
        return result.returncode == 0

    fetch_origin_attempted = bool(fetch_origin)
    fetch_origin_ok = git_run("fetch", "--prune", "origin") if fetch_origin else False

    top_level = git_output("rev-parse", "--show-toplevel")
    is_git_checkout = bool(top_level)
    remote = _agents_last_exam_normalized_repo_label(
        git_output("remote", "get-url", "origin")
    )
    head = _agents_last_exam_public_id(git_output("rev-parse", "HEAD"), limit=80)
    raw_upstream_ref = git_output(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    raw_upstream_head = git_output("rev-parse", "@{upstream}")
    upstream_fallback_ref = False
    if not raw_upstream_head:
        fallback_ref = "origin/main"
        fallback_head = git_output("rev-parse", fallback_ref)
        if fallback_head:
            raw_upstream_ref = fallback_ref
            raw_upstream_head = fallback_head
            upstream_fallback_ref = True
    upstream_ref = _agents_last_exam_public_id(raw_upstream_ref, limit=120)
    upstream_head = _agents_last_exam_public_id(raw_upstream_head, limit=80)
    upstream_ahead_count: int | None = None
    upstream_behind_count: int | None = None
    rev_target = raw_upstream_ref or "@{upstream}"
    rev_counts = git_output("rev-list", "--left-right", "--count", f"HEAD...{rev_target}")
    if rev_counts:
        parts = rev_counts.split()
        if len(parts) >= 2:
            try:
                upstream_ahead_count = int(parts[0])
                upstream_behind_count = int(parts[1])
            except ValueError:
                upstream_ahead_count = None
                upstream_behind_count = None
    metadata = {
        **base,
        "remote": remote,
        "remote_matches_expected": bool(remote and expected and remote == expected),
        "head": head,
        "upstream_ref": upstream_ref,
        "upstream_head": upstream_head,
        "upstream_declared": bool(upstream_ref),
        "upstream_fallback_ref": upstream_fallback_ref,
        "head_matches_upstream": bool(head and upstream_head and head == upstream_head),
        "upstream_ahead_count": upstream_ahead_count,
        "upstream_behind_count": upstream_behind_count,
        "fetch_origin_attempted": fetch_origin_attempted,
        "fetch_origin_ok": fetch_origin_ok,
        "is_git_checkout": is_git_checkout,
    }
    if not is_git_checkout:
        return {**metadata, "first_blocker": "source_root_not_git_checkout"}
    if not remote:
        return {**metadata, "first_blocker": "source_root_origin_missing"}
    if expected and remote != expected:
        return {**metadata, "first_blocker": "source_root_origin_mismatch"}
    if fetch_origin and not fetch_origin_ok:
        return {**metadata, "first_blocker": "source_root_fetch_origin_failed"}
    if not head:
        return {**metadata, "first_blocker": "source_root_head_missing"}
    return {**metadata, "first_blocker": None}

def build_agents_last_exam_local_source_readiness(
    *,
    source_root: str | None,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    runner_python_module: str = "ale_run",
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
) -> dict[str, Any]:
    """Verify a redacted public ALE source checkout contract without running ALE."""

    git_metadata = _agents_last_exam_source_git_metadata(
        source_root,
        expected_repo_url=expected_repo_url,
        fetch_origin=fetch_origin,
    )
    module_probe = _agents_last_exam_python_module_probe(
        runner_python_module,
        source_root=source_root,
    )
    blockers: list[str] = []
    if git_metadata.get("first_blocker"):
        blockers.append(str(git_metadata["first_blocker"]))
    if require_upstream_current:
        if git_metadata.get("upstream_declared") is not True:
            blockers.append("source_root_upstream_missing")
        elif git_metadata.get("head_matches_upstream") is not True:
            behind = git_metadata.get("upstream_behind_count")
            ahead = git_metadata.get("upstream_ahead_count")
            if isinstance(behind, int) and behind > 0:
                blockers.append("source_root_behind_upstream")
            elif isinstance(ahead, int) and ahead > 0:
                blockers.append("source_root_ahead_of_upstream")
            else:
                blockers.append("source_root_not_at_upstream_head")
    if module_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(module_probe.get("first_blocker"), limit=80)
            or "runner_python_module_not_available"
        )
    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_SOURCE_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_redacted_ale_source_lock",
        "blockers": blockers,
        "source": {
            "kind": "git_source_root",
            "expected_repo": git_metadata.get("expected_repo"),
            "remote": git_metadata.get("remote"),
            "remote_matches_expected": git_metadata.get("remote_matches_expected")
            is True,
            "head": git_metadata.get("head"),
            "upstream_ref": git_metadata.get("upstream_ref"),
            "upstream_head": git_metadata.get("upstream_head"),
            "upstream_declared": git_metadata.get("upstream_declared") is True,
            "upstream_fallback_ref": git_metadata.get("upstream_fallback_ref") is True,
            "head_matches_upstream": git_metadata.get("head_matches_upstream")
            is True,
            "upstream_ahead_count": git_metadata.get("upstream_ahead_count"),
            "upstream_behind_count": git_metadata.get("upstream_behind_count"),
            "fetch_origin_attempted": git_metadata.get("fetch_origin_attempted")
            is True,
            "fetch_origin_ok": git_metadata.get("fetch_origin_ok") is True,
            "require_upstream_current": bool(require_upstream_current),
            "git_probe_available": git_metadata.get("git_probe_available") is True,
            "is_git_checkout": git_metadata.get("is_git_checkout") is True,
            "source_root_declared": git_metadata.get("source_root_declared") is True,
            "source_root_available": git_metadata.get("source_root_available") is True,
            "source_root_path_recorded": False,
        },
        "runner_probe": {
            "python_module": module_probe.get("module"),
            "python_module_declared": module_probe.get("declared") is True,
            "python_module_available": module_probe.get("available") is True,
            "python_module_path_recorded": False,
            "source_root_path_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "use_redacted_source_lock_for_runner_readiness"
            if ready
            else "repair_public_ale_source_lock_before_runner_execution",
            "minimum_next_evidence": (
                "A durable public ALE checkout with matching origin, commit, and "
                "importable runner module, followed by no-upload runner readiness."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_public_task_parts(task_id: str | None) -> tuple[list[str], str | None]:
    label = _agents_last_exam_public_id(task_id, limit=180)
    if not isinstance(task_id, str) or not task_id.strip():
        return [], label
    text = task_id.strip().replace("\\", "/")
    parts = [part for part in text.split("/") if part]
    safe = (
        not text.startswith("/")
        and not text.startswith("~")
        and len(parts) == 2
        and all(part not in {".", ".."} for part in parts)
        and all(_agents_last_exam_public_id(part, limit=120) == part for part in parts)
    )
    return (parts if safe else []), label

def _agents_last_exam_public_task_list_membership(
    source_root: str | None,
    task_id: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    safe_task_id = str(task_id or "").strip().replace("\\", "/")
    memberships: dict[str, bool] = {}
    checked = 0
    present = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": [],
            "membership": memberships,
            "present_count": present,
            "path_recorded": False,
        }
    safe_lists: list[str] = []
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        safe_lists.append(label)
        if not inside_root or not candidate.is_file():
            memberships[label] = False
            continue
        checked += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            memberships[label] = False
            continue
        matched = any(line.strip().replace("\\", "/") == safe_task_id for line in lines)
        memberships[label] = matched
        if matched:
            present += 1
    return {
        "checked": checked > 0,
        "selected_task_lists": safe_lists,
        "membership": memberships,
        "present_count": present,
        "path_recorded": False,
    }

def _agents_last_exam_bool_requirement(value: bool | str | None) -> bool | None:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "required", "requires_task_data"}:
        return True
    if normalized in {"0", "false", "no", "not_required", "none"}:
        return False
    return None

def _agents_last_exam_local_task_data_staging_probe(
    *,
    source_root_path: Path | None,
    local_source_declared: bool,
    local_source_safe: bool,
    local_source_present: bool,
) -> dict[str, Any]:
    checked = bool(local_source_declared)
    fetch_script_present = False
    if source_root_path is not None and source_root_path.is_dir():
        fetch_script_present = (
            source_root_path / "scripts" / "fetch_task_data.sh"
        ).is_file()
    fetch_tool_present = shutil.which("huggingface-cli") is not None
    disk_headroom = _agents_last_exam_disk_headroom_for_path(source_root_path)
    documented_image_compressed_gib = 42
    free_gib = disk_headroom.get("free_gib")
    disk_headroom_below_documented_image = (
        isinstance(free_gib, (int, float))
        and free_gib < documented_image_compressed_gib
    )
    blockers: list[str] = []
    if checked and local_source_safe and local_source_present is not True:
        if not fetch_script_present:
            blockers.append("local_task_data_fetch_script_missing")
        if not fetch_tool_present:
            blockers.append("local_task_data_fetch_tool_missing")
        blockers.append("local_task_data_gated_huggingface_access_not_verified")
        if disk_headroom_below_documented_image:
            blockers.append(
                "local_task_data_disk_headroom_below_documented_image_pull"
            )
    return {
        "checked": checked,
        "ready": checked and not blockers if checked else None,
        "first_blocker": blockers[0] if blockers else None,
        "blockers": blockers,
        "route": "gated_huggingface_archive" if checked else None,
        "dataset_label": "agents-last-exam-data-archive" if checked else None,
        "archive_label": "ale-tasks-data.tar.gz" if checked else None,
        "fetch_script_present": fetch_script_present,
        "fetch_tool": "huggingface-cli" if checked else None,
        "fetch_tool_present": fetch_tool_present,
        "auth_status_checked": False,
        "requires_approved_huggingface_access": checked,
        "disk_headroom": disk_headroom,
        "documented_docker_image_compressed_gib": documented_image_compressed_gib,
        "disk_headroom_below_documented_image_pull": (
            disk_headroom_below_documented_image
        ),
        "local_paths_recorded": False,
        "credential_values_read": False,
        "credential_values_recorded": False,
        "task_data_content_read": False,
        "archive_content_read": False,
    }

def build_agents_last_exam_baked_task_input_readiness(
    *,
    selected_task_id: str | None,
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Probe whether an ALE Docker image contains a task baked input dir.

    This starts a tiny shell in the image to test directory existence/readability.
    It does not run the task, list files, read task data, or record the checked path.
    """

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    if docker_binary_safe and not docker_available:
        blockers.append("docker_cli_missing")

    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )
    if image.get("present") is not True:
        blockers.append(
            _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
            or "docker_image_missing"
        )

    attempted = False
    container_started = False
    baked_input_present = False
    baked_input_readable = False
    probe_return_code: int | None = None
    probe_error: str | None = None
    if not blockers and parts and docker_binary_safe:
        baked_input_path = (
            f"/media/user/data/agenthle/{parts[0]}/{parts[1]}/base/input"
        )
        attempted = True
        try:
            result = subprocess.run(
                [
                    docker_binary,
                    "run",
                    "--rm",
                    "--entrypoint",
                    "/bin/sh",
                    image_ref,
                    "-c",
                    'test -d "$1" && test -r "$1"',
                    "sh",
                    baked_input_path,
                ],
                check=False,
                text=True,
                capture_output=True,
                timeout=max(1, int(timeout_seconds)),
            )
        except subprocess.TimeoutExpired:
            probe_error = "baked_task_input_probe_timeout"
        except Exception:
            probe_error = "baked_task_input_probe_failed"
        else:
            container_started = True
            probe_return_code = result.returncode
            if result.returncode == 0:
                baked_input_present = True
                baked_input_readable = True
            else:
                probe_error = "baked_task_input_missing"
    if probe_error:
        blockers.append(probe_error)

    ready = not blockers and baked_input_present and baked_input_readable
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_sandbox_task_data_source",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "baked_input_present": baked_input_present,
            "baked_input_readable": baked_input_readable,
            "return_code_zero": probe_return_code == 0
            if probe_return_code is not None
            else None,
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }

def build_agents_last_exam_baked_task_input_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    image_metadata: dict[str, Any] | None = None,
    docker_binary: str = "docker",
    max_tasks: int = 120,
    timeout_seconds: int = 180,
    probe_results: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Scan selected public ALE tasks for baked input dirs without reading them."""

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if _agents_last_exam_public_task_parts(task_id)[0]
    ]
    max_count = max(0, int(max_tasks))
    if max_count:
        task_ids = task_ids[:max_count]
    else:
        task_ids = []
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    if not task_ids:
        blockers.append("no_selected_tasks_to_probe")

    docker_label = _agents_last_exam_public_id(docker_binary, limit=80)
    docker_binary_safe = bool(
        docker_label
        and docker_binary == docker_label
        and "/" not in docker_binary
        and "\\" not in docker_binary
    )
    if not docker_binary_safe:
        blockers.append("docker_binary_must_be_name_not_path")
    docker_available = bool(docker_binary_safe and shutil.which(docker_binary))
    raw_image_metadata = (
        image_metadata
        if isinstance(image_metadata, dict)
        else _agents_last_exam_docker_image_metadata(image_ref)
    )
    image = _agents_last_exam_public_image_metadata(
        raw_image_metadata,
        fallback_image_ref=image_ref,
    )

    fixture_probe_used = isinstance(probe_results, dict)
    if not fixture_probe_used:
        if docker_binary_safe and not docker_available:
            blockers.append("docker_cli_missing")
        if image.get("present") is not True:
            blockers.append(
                _agents_last_exam_public_id(image.get("first_blocker"), limit=80)
                or "docker_image_missing"
            )

    attempted = False
    container_started = False
    candidates: list[str] = []
    probe_error: str | None = None
    if not blockers and task_ids:
        attempted = True
        if fixture_probe_used:
            for task_id in task_ids:
                if probe_results.get(task_id) is True:
                    candidates.append(task_id)
        else:
            script = (
                'while IFS= read -r task; do '
                'category="${task%%/*}"; name="${task#*/}"; '
                'path="/media/user/data/agenthle/${category}/${name}/base/input"; '
                'if test -d "$path" && test -r "$path"; then '
                'printf "%s\\t1\\n" "$task"; else printf "%s\\t0\\n" "$task"; fi; '
                "done"
            )
            try:
                result = subprocess.run(
                    [
                        docker_binary,
                        "run",
                        "--rm",
                        "--entrypoint",
                        "/bin/sh",
                        image_ref,
                        "-c",
                        script,
                    ],
                    input="\n".join(task_ids) + "\n",
                    check=False,
                    text=True,
                    capture_output=True,
                    timeout=max(1, int(timeout_seconds)),
                )
            except subprocess.TimeoutExpired:
                probe_error = "baked_task_input_scan_timeout"
            except Exception:
                probe_error = "baked_task_input_scan_failed"
            else:
                container_started = True
                if result.returncode != 0:
                    probe_error = "baked_task_input_scan_nonzero"
                else:
                    safe_task_set = set(task_ids)
                    for line in result.stdout.splitlines():
                        raw_task_id, _, flag = line.partition("\t")
                        if flag != "1" or raw_task_id not in safe_task_set:
                            continue
                        parts, safe_label = _agents_last_exam_public_task_parts(
                            raw_task_id
                        )
                        if parts and safe_label:
                            candidates.append(raw_task_id)
    if probe_error:
        blockers.append(probe_error)
    if attempted and not candidates and not blockers:
        blockers.append("no_baked_input_candidate_found")

    ready = bool(candidates) and not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_BAKED_TASK_INPUT_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_baked_input_formal_candidate_selection",
        "blockers": blockers,
        "selected_tasks": {
            "checked": selected.get("checked") is True,
            "selected_task_lists": selected.get("selected_task_lists") or [],
            "selected_task_count": selected.get("selected_task_count"),
            "probed_task_count": len(task_ids),
            "max_tasks": max_count,
            "path_recorded": False,
        },
        "image": image,
        "probe": {
            "kind": "docker_shell_batch_test_directory_only",
            "attempted": attempted,
            "container_started": container_started,
            "fixture_probe_used": fixture_probe_used,
            "baked_input_candidate_count": len(candidates),
            "expected_path_template": "ale_task_base_input",
            "expected_path_recorded": False,
            "stdout_recorded": False,
            "stderr_recorded": False,
            "command_argv_recorded": False,
        },
        "candidates": {
            "eligible_baked_input_candidates": candidates[:25],
            "candidate_count": len(candidates),
            "task_ids_public": True,
            "task_paths_recorded": False,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": container_started,
            "task_run_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "directory_listed": False,
            "model_api_invoked": False,
            "codex_prompt_sent": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "read_boundary": {
            "compact_only": True,
            "path_existence_only": True,
            "selected_task_lists_read": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_data_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }

def _agents_last_exam_task_data_source_readiness(
    *,
    source_root: str | None,
    requires_task_data: bool | str | None,
    task_data_source: str | None,
    baked_task_input_present: bool | None,
    baked_task_input_readiness: dict[str, Any] | None,
    gcs_sa_key: str | None,
    gcs_sa_key_present: bool | None,
    enforce_task_data_source: bool,
) -> dict[str, Any]:
    requirement = _agents_last_exam_bool_requirement(requires_task_data)
    raw_source = task_data_source.strip() if isinstance(task_data_source, str) else ""
    source = _agents_last_exam_public_id(raw_source, limit=120)
    official_gcs_source = raw_source.startswith("gs://ale-data-public")
    local_source_declared = raw_source.startswith("local:")
    local_source_safe = False
    local_source_present = False
    source_root_path = None
    if local_source_declared:
        local_relative = raw_source[len("local:") :].strip().replace("\\", "/")
        parts = [part for part in local_relative.split("/") if part]
        local_source_safe = bool(
            local_relative
            and not local_relative.startswith("/")
            and not local_relative.startswith("~")
            and all(part not in {".", ".."} for part in parts)
        )
        try:
            source_root_path = Path(source_root).expanduser() if source_root else None
        except (OSError, RuntimeError):
            source_root_path = None
        if (
            local_source_safe
            and source_root_path is not None
            and source_root_path.is_dir()
        ):
            candidate = source_root_path.joinpath(*parts)
            try:
                resolved_root = source_root_path.resolve()
                resolved_candidate = candidate.resolve()
                inside_root = resolved_candidate == resolved_root or (
                    resolved_root in resolved_candidate.parents
                )
            except OSError:
                inside_root = False
            local_source_present = bool(inside_root and candidate.is_dir())
    local_staging = _agents_last_exam_local_task_data_staging_probe(
        source_root_path=source_root_path,
        local_source_declared=local_source_declared,
        local_source_safe=local_source_safe,
        local_source_present=local_source_present,
    )
    gcs_key_declared = bool(gcs_sa_key)
    gcs_key_file_present = False
    if gcs_sa_key:
        try:
            gcs_key_file_present = Path(gcs_sa_key).expanduser().is_file()
        except (OSError, RuntimeError):
            gcs_key_file_present = False
    effective_gcs_key_present = (
        bool(gcs_sa_key_present)
        if gcs_sa_key_present is not None
        else gcs_key_file_present
    )
    baked_probe_declared = isinstance(baked_task_input_readiness, dict)
    baked_probe_ready = (
        baked_task_input_readiness.get("schema_version")
        == AGENTS_LAST_EXAM_BAKED_TASK_INPUT_READINESS_SCHEMA_VERSION
        and baked_task_input_readiness.get("ready") is True
        if baked_probe_declared
        else False
    )
    effective_baked_input_present = (
        bool(baked_task_input_present)
        if baked_task_input_present is not None
        else baked_probe_ready
    )
    checked = enforce_task_data_source or requirement is not None or bool(source)
    blockers: list[str] = []
    if checked and requirement is None:
        blockers.append("task_data_requirement_unknown")
    if requirement is True:
        if not source:
            blockers.append("task_data_source_missing_for_required_task")
        elif raw_source == "baked_in_sandbox":
            if baked_probe_declared and baked_probe_ready is not True:
                blockers.append(
                    _agents_last_exam_public_id(
                        baked_task_input_readiness.get("first_blocker"),
                        limit=80,
                    )
                    or "baked_task_input_not_verified"
                )
            elif effective_baked_input_present is not True:
                blockers.append("baked_task_input_not_verified")
        elif official_gcs_source:
            if effective_gcs_key_present is not True:
                blockers.append("gcs_sa_key_presence_not_verified")
        elif local_source_declared:
            if not local_source_safe:
                blockers.append("local_task_data_source_not_public_safe")
            elif local_source_present is not True:
                blockers.append("local_task_data_directory_not_verified")
                blockers.extend(
                    blocker
                    for blocker in local_staging.get("blockers", [])
                    if isinstance(blocker, str)
                )
        elif raw_source in {"none", "local"}:
            blockers.append("task_data_source_not_sufficient_for_required_task")
        else:
            blockers.append("task_data_source_unsupported_for_required_task")
    ready = checked and not blockers
    if requirement is False:
        ready = True
    return {
        "checked": checked,
        "ready": ready,
        "first_blocker": blockers[0] if blockers else None,
        "blockers": blockers,
        "requires_task_data": requirement,
        "requires_task_data_declared": requirement is not None,
        "task_data_source": source,
        "task_data_source_declared": bool(source),
        "official_gcs_source": official_gcs_source,
        "local_task_data_source": local_source_declared,
        "local_task_data_source_safe": local_source_safe,
        "local_task_data_present": local_source_present,
        "local_task_data_staging": local_staging,
        "local_task_data_path_recorded": False,
        "local_task_data_content_read": False,
        "baked_input_present": effective_baked_input_present is True,
        "baked_input_presence_declared": baked_task_input_present is not None
        or baked_probe_declared,
        "baked_input_probe_declared": baked_probe_declared,
        "baked_input_probe_ready": baked_probe_ready,
        "gcs_sa_key_declared": gcs_key_declared or gcs_sa_key_present is not None,
        "gcs_sa_key_present": effective_gcs_key_present,
        "gcs_sa_key_path_recorded": False,
        "credential_values_read": False,
        "credential_values_recorded": False,
        "local_paths_recorded": False,
    }

def build_agents_last_exam_task_material_readiness(
    *,
    source_root: str | None,
    selected_task_id: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    requires_task_data: bool | str | None = None,
    task_data_source: str | None = None,
    baked_task_input_present: bool | None = None,
    baked_task_input_readiness: dict[str, Any] | None = None,
    gcs_sa_key: str | None = None,
    gcs_sa_key_present: bool | None = None,
    enforce_task_data_source: bool = False,
) -> dict[str, Any]:
    """Check local ALE task material existence without reading task bodies."""

    parts, task_label = _agents_last_exam_public_task_parts(selected_task_id)
    blockers: list[str] = []
    if not parts:
        blockers.append("selected_task_id_not_public_safe")
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    source_root_available = bool(root and root.is_dir())
    if not source_root_available or root is None:
        blockers.append("source_root_not_available")

    task_dir_available = False
    task_card_present = False
    scripts_dir_present = False
    scorer_script_count = 0
    task_dir_entry_count = 0
    if root is not None and source_root_available and parts:
        task_dir = root / "tasks" / parts[0] / parts[1]
        try:
            resolved_root = root.resolve()
            resolved_task_dir = task_dir.resolve()
            inside_root = resolved_task_dir == resolved_root or (
                resolved_root in resolved_task_dir.parents
            )
        except OSError:
            inside_root = False
        task_dir_available = bool(inside_root and task_dir.is_dir())
        if task_dir_available:
            task_card_present = (task_dir / "task_card.json").is_file()
            scripts_dir = task_dir / "scripts"
            scripts_dir_present = scripts_dir.is_dir()
            try:
                task_dir_entry_count = sum(1 for _ in task_dir.iterdir())
            except OSError:
                task_dir_entry_count = 0
            if scripts_dir_present:
                try:
                    scorer_script_count = sum(
                        1
                        for path in scripts_dir.iterdir()
                        if path.is_file()
                        and path.suffix == ".py"
                        and "score" in path.name.lower()
                    )
                except OSError:
                    scorer_script_count = 0
    if not task_dir_available:
        blockers.append("task_directory_missing")
    if not task_card_present:
        blockers.append("task_card_json_missing")
    if not scripts_dir_present:
        blockers.append("task_scripts_directory_missing")
    if scorer_script_count < 1:
        blockers.append("task_scorer_script_missing")

    membership = _agents_last_exam_public_task_list_membership(
        source_root,
        selected_task_id,
        selected_task_lists,
    )
    if membership.get("checked") is not True:
        blockers.append("selected_task_list_membership_not_checked")
    elif int(membership.get("present_count") or 0) < 1:
        blockers.append("selected_task_not_in_public_task_lists")
    task_data = _agents_last_exam_task_data_source_readiness(
        source_root=source_root,
        requires_task_data=requires_task_data,
        task_data_source=task_data_source,
        baked_task_input_present=baked_task_input_present,
        baked_task_input_readiness=baked_task_input_readiness,
        gcs_sa_key=gcs_sa_key,
        gcs_sa_key_present=gcs_sa_key_present,
        enforce_task_data_source=enforce_task_data_source,
    )
    if enforce_task_data_source and task_data.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(task_data.get("first_blocker"), limit=80)
            or "task_data_source_not_ready"
        )

    ready = not blockers
    return {
        "schema_version": AGENTS_LAST_EXAM_TASK_MATERIAL_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_upload_ale_task_gate",
        "blockers": blockers,
        "task": {
            "task_id": task_label,
            "category": parts[0] if parts else None,
            "name": parts[1] if parts else None,
            "task_dir_available": task_dir_available,
            "task_card_json_present": task_card_present,
            "scripts_dir_present": scripts_dir_present,
            "scorer_script_count": scorer_script_count,
            "task_dir_entry_count": task_dir_entry_count,
            "task_dir_path_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
        },
        "task_data": task_data,
        "public_task_lists": membership,
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_local_no_upload_ale_validation_run_gate"
            if ready
            else "repair_ale_task_material_readiness_blocker",
            "minimum_next_evidence": (
                "A local/no-upload ALE task gate should combine this material "
                "readiness signal with host Codex no-task E2E readiness and the "
                "compact result reducer boundary before any task-level run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_public_selected_task_scan(
    source_root: str | None,
    selected_task_lists: Iterable[str],
) -> dict[str, Any]:
    labels: list[str] = []
    task_ids: set[str] = set()
    missing_lists = 0
    checked_lists = 0
    unsafe_lists = 0
    if not source_root:
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    try:
        root = Path(source_root).expanduser()
        selected_root = root / "selected_tasks"
        resolved_root = root.resolve()
    except (OSError, RuntimeError):
        return {
            "checked": False,
            "selected_task_lists": labels,
            "selected_task_count": 0,
            "checked_list_count": 0,
            "missing_list_count": 0,
            "unsafe_list_count": 0,
            "path_recorded": False,
            "task_ids": [],
        }
    for raw_name in selected_task_lists:
        label = _agents_last_exam_public_id(raw_name, limit=120)
        if not label:
            unsafe_lists += 1
            continue
        parts = [part for part in str(raw_name).replace("\\", "/").split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts):
            labels.append(label)
            unsafe_lists += 1
            continue
        candidate = selected_root.joinpath(*parts)
        try:
            resolved_candidate = candidate.resolve()
            inside_root = resolved_candidate == resolved_root or (
                resolved_root in resolved_candidate.parents
            )
        except OSError:
            inside_root = False
        labels.append(label)
        if not inside_root or not candidate.is_file():
            missing_lists += 1
            continue
        checked_lists += 1
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            missing_lists += 1
            continue
        for line in lines:
            raw_task_id = line.strip().replace("\\", "/")
            if not raw_task_id or raw_task_id.startswith("#"):
                continue
            parts, safe_label = _agents_last_exam_public_task_parts(raw_task_id)
            if parts and safe_label:
                task_ids.add("/".join(parts))
    return {
        "checked": checked_lists > 0,
        "selected_task_lists": labels,
        "selected_task_count": len(task_ids),
        "checked_list_count": checked_lists,
        "missing_list_count": missing_lists,
        "unsafe_list_count": unsafe_lists,
        "path_recorded": False,
        "task_ids": sorted(task_ids),
    }

def _agents_last_exam_requires_task_data_line_scan(
    *,
    source_root: str | None,
    task_id: str,
    max_lines: int = 1200,
) -> dict[str, Any]:
    parts, task_label = _agents_last_exam_public_task_parts(task_id)
    if not parts:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "selected_task_id_not_public_safe",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    try:
        root = Path(source_root).expanduser() if source_root else None
    except (OSError, RuntimeError):
        root = None
    if root is None or not root.is_dir():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "source_root_not_available",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    source_file = root / "tasks" / parts[0] / parts[1] / "main.py"
    try:
        resolved_root = root.resolve()
        resolved_source_file = source_file.resolve()
        inside_root = resolved_source_file == resolved_root or (
            resolved_root in resolved_source_file.parents
        )
    except OSError:
        inside_root = False
    if not inside_root or not source_file.is_file():
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": 0,
            "first_blocker": "task_config_main_py_missing",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    scanned = 0
    try:
        with source_file.open(encoding="utf-8") as handle:
            for raw_line in handle:
                scanned += 1
                match = _AGENTS_LAST_EXAM_REQUIRES_TASK_DATA_RE.match(raw_line)
                if match:
                    requires_task_data = match.group(1) == "True"
                    return {
                        "task_id": task_label,
                        "checked": True,
                        "requires_task_data": requires_task_data,
                        "requires_task_data_declared": True,
                        "assignment_found": True,
                        "assignment_kind": "requires_task_data_bool_assignment",
                        "line_count_scanned": scanned,
                        "first_blocker": None,
                        "task_source_path_recorded": False,
                        "task_source_content_recorded": False,
                    }
                if scanned >= max_lines:
                    break
    except OSError:
        return {
            "task_id": task_label,
            "checked": False,
            "requires_task_data": None,
            "requires_task_data_declared": False,
            "assignment_found": False,
            "assignment_kind": None,
            "line_count_scanned": scanned,
            "first_blocker": "task_config_main_py_unreadable",
            "task_source_path_recorded": False,
            "task_source_content_recorded": False,
        }
    return {
        "task_id": task_label,
        "checked": True,
        "requires_task_data": True,
        "requires_task_data_declared": False,
        "assignment_found": False,
        "assignment_kind": "default_true_when_assignment_missing",
        "line_count_scanned": scanned,
        "first_blocker": None,
        "task_source_path_recorded": False,
        "task_source_content_recorded": False,
    }

def build_agents_last_exam_candidate_task_data_scan(
    *,
    source_root: str | None,
    selected_task_lists: Iterable[str] = (
        "linux_only.txt",
        "unlicensed/near-term.txt",
    ),
    allow_demo_candidate: bool = False,
) -> dict[str, Any]:
    """Scan selected ALE task configs for local no-task-data candidates.

    This is a bounded config-line scan: it extracts only a
    ``REQUIRES_TASK_DATA`` boolean assignment signal from task ``main.py`` and
    never records source paths or source text.
    """

    selected = _agents_last_exam_public_selected_task_scan(
        source_root,
        selected_task_lists,
    )
    blockers: list[str] = []
    if selected.get("checked") is not True:
        blockers.append("selected_task_lists_not_checked")
    task_ids = [
        task_id
        for task_id in selected.get("task_ids", [])
        if isinstance(task_id, str)
    ]
    if selected.get("checked") is True and not task_ids:
        blockers.append("selected_task_lists_empty")

    scan_results = [
        _agents_last_exam_requires_task_data_line_scan(
            source_root=source_root,
            task_id=task_id,
        )
        for task_id in task_ids
    ]
    checked_results = [item for item in scan_results if item.get("checked") is True]
    no_data_candidates = [
        str(item.get("task_id"))
        for item in checked_results
        if item.get("requires_task_data") is False and item.get("task_id")
    ]
    demo_no_data_candidates = [
        task_id for task_id in no_data_candidates if task_id.startswith("demo__")
    ]
    formal_no_data_candidates = [
        task_id for task_id in no_data_candidates if not task_id.startswith("demo__")
    ]
    eligible_candidates = (
        no_data_candidates if allow_demo_candidate else formal_no_data_candidates
    )
    if task_ids and not no_data_candidates:
        blockers.append("no_no_task_data_candidate_found")
    elif task_ids and not eligible_candidates:
        blockers.append("no_formal_no_task_data_candidate_found")
    ready = not blockers
    explicit_false_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is False
        and item.get("requires_task_data_declared") is True
    )
    explicit_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is True
    )
    default_true_count = sum(
        1
        for item in checked_results
        if item.get("requires_task_data") is True
        and item.get("requires_task_data_declared") is False
    )
    missing_config_count = sum(
        1 for item in scan_results if item.get("checked") is not True
    )
    return {
        "schema_version": AGENTS_LAST_EXAM_CANDIDATE_TASK_DATA_SCAN_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_no_task_data_ale_candidate_gate",
        "blockers": blockers,
        "selected_task_lists": {
            key: value
            for key, value in selected.items()
            if key != "task_ids"
        },
        "scan_summary": {
            "selected_task_count": len(task_ids),
            "task_config_checked_count": len(checked_results),
            "task_config_missing_or_unreadable_count": missing_config_count,
            "explicit_requires_task_data_false_count": explicit_false_count,
            "explicit_requires_task_data_true_count": explicit_true_count,
            "default_requires_task_data_true_count": default_true_count,
            "no_task_data_candidate_count": len(no_data_candidates),
            "formal_no_task_data_candidate_count": len(formal_no_data_candidates),
            "demo_no_task_data_candidate_count": len(demo_no_data_candidates),
            "allow_demo_candidate": bool(allow_demo_candidate),
        },
        "candidate_tasks": {
            "eligible_no_task_data_candidates": eligible_candidates[:25],
            "formal_no_task_data_candidates": formal_no_data_candidates[:25],
            "demo_no_task_data_candidates": demo_no_data_candidates[:25],
            "candidate_count_truncated": len(eligible_candidates) > 25,
            "task_ids_public_only": True,
        },
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "selected_task_list_content_recorded": False,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_output_recorded": False,
        },
        "decision": {
            "next_allowed_action": "prepare_no_task_data_formal_ale_validation_gate"
            if ready
            else "do_not_launch_formal_ale_until_task_data_substrate_is_ready",
            "minimum_next_evidence": (
                "A formal local/no-upload ALE candidate should either be listed "
                "as not requiring task data or carry a separately verified "
                "task-data source readiness signal before any model task run."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_config_line_scan": True,
            "task_config_source_content_recorded": False,
            "task_card_content_read": False,
            "script_content_read": False,
            "task_instruction_file_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def _agents_last_exam_relative_file_probe(
    source_root: str | None,
    relative_path: str | None,
    *,
    file_root: str | None = None,
) -> dict[str, Any]:
    label = _agents_last_exam_public_id(relative_path, limit=160)
    root_kind = "external_spec_root" if file_root else "source_root"
    if not relative_path:
        return {
            "relative_path": None,
            "declared": False,
            "exists": False,
            "first_blocker": "experiment_spec_missing",
            "root_kind": root_kind,
            "source_root_path_recorded": False,
            "external_root_path_recorded": False,
        }
    text = relative_path.replace("\\", "/").strip()
    parts = [part for part in text.split("/") if part]
    if text.startswith("/") or text.startswith("~") or any(
        part in {".", ".."} for part in parts
    ):
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": "experiment_spec_relative_path_not_public_safe",
            "root_kind": root_kind,
            "source_root_path_recorded": False,
            "external_root_path_recorded": False,
        }
    probe_root = file_root or source_root
    if not probe_root:
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": f"{root_kind}_missing",
            "root_kind": root_kind,
            "source_root_path_recorded": False,
            "external_root_path_recorded": False,
        }
    try:
        source_path = Path(probe_root).expanduser()
    except (OSError, RuntimeError):
        source_path = None
    if source_path is None or not source_path.is_dir():
        return {
            "relative_path": label,
            "declared": True,
            "exists": False,
            "first_blocker": f"{root_kind}_not_available",
            "root_kind": root_kind,
            "source_root_path_recorded": False,
            "external_root_path_recorded": False,
        }
    candidate = source_path.joinpath(*parts)
    try:
        resolved_source = source_path.resolve()
        resolved_candidate = candidate.resolve()
        inside_root = resolved_candidate == resolved_source or (
            resolved_source in resolved_candidate.parents
        )
    except OSError:
        inside_root = False
    exists = bool(inside_root and candidate.is_file())
    return {
        "relative_path": label,
        "declared": True,
        "exists": exists,
        "first_blocker": None if exists else "experiment_spec_file_missing",
        "root_kind": root_kind,
        "source_root_path_recorded": False,
        "external_root_path_recorded": False,
    }

def build_agents_last_exam_local_launch_packet(
    *,
    source_root: str | None,
    experiment_spec_relative_path: str | None,
    experiment_spec_root: str | None = None,
    selected_task_id: str | None = None,
    expected_repo_url: str = AGENTS_LAST_EXAM_DEFAULT_REPO_URL,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    runner_binary: str | None = "python3",
    runner_python_module: str | None = "ale_run",
    runner_command_label: str | None = "python-m-ale-run",
    operator_authorized: bool = False,
    allow_public_task_material: bool = False,
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a redacted no-execution packet for a future ALE dry-run."""

    source_readiness = build_agents_last_exam_local_source_readiness(
        source_root=source_root,
        expected_repo_url=expected_repo_url,
        runner_python_module=runner_python_module or "ale_run",
        fetch_origin=fetch_origin,
        require_upstream_current=require_upstream_current,
    )
    runner_readiness = build_agents_last_exam_local_runner_readiness(
        selected_task_id=selected_task_id,
        snapshot=snapshot,
        provider_kind=provider_kind,
        image_ref=image_ref,
        alternate_image_ref=alternate_image_ref,
        runner_binary=runner_binary,
        runner_python_module=runner_python_module,
        runner_source_root=source_root,
        runner_command_label=runner_command_label,
        operator_authorized=operator_authorized,
        allow_public_task_material=allow_public_task_material,
        image_metadata=image_metadata,
        alternate_image_metadata=alternate_image_metadata,
        disk_headroom=disk_headroom,
    )
    spec_probe = _agents_last_exam_relative_file_probe(
        source_root,
        experiment_spec_relative_path,
        file_root=experiment_spec_root,
    )
    blockers: list[str] = []
    if source_readiness.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(source_readiness.get("first_blocker"), limit=80)
            or "ale_source_not_ready"
        )
    if runner_readiness.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(runner_readiness.get("first_blocker"), limit=80)
            or "ale_runner_not_ready"
        )
    if spec_probe.get("exists") is not True:
        blockers.append(
            _agents_last_exam_public_id(spec_probe.get("first_blocker"), limit=80)
            or "experiment_spec_not_ready"
        )
    ready = not blockers
    source = (
        source_readiness.get("source")
        if isinstance(source_readiness.get("source"), dict)
        else {}
    )
    runner_probe = (
        runner_readiness.get("runner_probe")
        if isinstance(runner_readiness.get("runner_probe"), dict)
        else {}
    )
    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_LAUNCH_PACKET_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": _agents_last_exam_public_id(selected_task_id, limit=160)
        or "metadata_only_candidate",
        "snapshot": _agents_last_exam_public_id(snapshot, limit=80)
        or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_operator_triggered_no_upload_ale_dry_run",
        "blockers": blockers,
        "source_lock": {
            "expected_repo": source.get("expected_repo"),
            "remote": source.get("remote"),
            "remote_matches_expected": source.get("remote_matches_expected") is True,
            "head": source.get("head"),
            "upstream_ref": source.get("upstream_ref"),
            "upstream_head": source.get("upstream_head"),
            "upstream_declared": source.get("upstream_declared") is True,
            "head_matches_upstream": source.get("head_matches_upstream") is True,
            "upstream_ahead_count": source.get("upstream_ahead_count"),
            "upstream_behind_count": source.get("upstream_behind_count"),
            "fetch_origin_attempted": source.get("fetch_origin_attempted") is True,
            "fetch_origin_ok": source.get("fetch_origin_ok") is True,
            "require_upstream_current": source.get("require_upstream_current") is True,
            "source_root_path_recorded": False,
        },
        "runner": {
            "command_label": runner_probe.get("command_label"),
            "binary": runner_probe.get("binary"),
            "python_module": runner_probe.get("python_module"),
            "binary_available": runner_probe.get("binary_available") is True,
            "python_module_available": runner_probe.get("python_module_available")
            is True,
            "source_root_path_recorded": False,
            "command_argv_recorded": False,
        },
        "experiment_spec": {
            "relative_path": spec_probe.get("relative_path"),
            "declared": spec_probe.get("declared") is True,
            "exists": spec_probe.get("exists") is True,
            "content_read": False,
            "root_kind": spec_probe.get("root_kind"),
            "external_root_declared": bool(experiment_spec_root),
            "source_root_path_recorded": False,
            "external_root_path_recorded": False,
        },
        "launch_packet": {
            "mode": "no_execution_launch_packet",
            "command_shape": "python-m-ale-run-dry-run",
            "will_execute": False,
            "will_start_container": False,
            "will_read_task_body": False,
            "will_invoke_model_api": False,
            "will_upload": False,
            "will_submit": False,
            "will_capture_screenshot": False,
            "will_record_credentials": False,
            "will_record_local_paths": False,
        },
        "case_state_init_contract": benchmark_case_active_state_init_contract(
            benchmark_id=AGENTS_LAST_EXAM_BENCHMARK_ID,
            goal_id=AGENTS_LAST_EXAM_CASE_GOAL_ID,
            case_state_path=AGENTS_LAST_EXAM_CASE_STATE_PATH,
            initialized_by_launch_packet=False,
        ),
        "boundary": {
            "local_only": True,
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
            "command_argv_recorded": False,
        },
        "decision": {
            "next_allowed_action": "operator_trigger_exact_no_upload_ale_dry_run"
            if ready
            else "repair_ale_launch_packet_blocker_before_execution",
            "minimum_next_evidence": (
                "A human/operator-triggered ALE dry-run using the redacted source "
                "lock, runner label, and experiment spec, followed by compact "
                "run/eval/events ingest only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "experiment_spec_content_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def build_agents_last_exam_local_runner_readiness(
    *,
    selected_task_id: str | None = None,
    snapshot: str = AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    provider_kind: str = "docker",
    image_ref: str = AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    alternate_image_ref: str = AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    runner_binary: str | None = None,
    runner_python_module: str | None = None,
    runner_source_root: str | None = None,
    runner_command_label: str | None = None,
    operator_authorized: bool = False,
    allow_public_task_material: bool = False,
    fetch_origin: bool = False,
    require_upstream_current: bool = False,
    image_metadata: dict[str, Any] | None = None,
    alternate_image_metadata: dict[str, Any] | None = None,
    disk_headroom: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    dry_run_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Check whether a real local ALE dry-run runner is configured.

    This is still a no-execution gate: it may inspect Docker image metadata and
    the local PATH for a runner binary, but it does not start containers, read
    task bodies, invoke model APIs, upload, submit, or record command argv.
    """

    preflight_payload = (
        preflight
        if isinstance(preflight, dict)
        else build_agents_last_exam_local_preflight(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
        )
    )
    plan_payload = (
        dry_run_plan
        if isinstance(dry_run_plan, dict)
        else build_agents_last_exam_local_dry_run_plan(
            selected_task_id=selected_task_id,
            snapshot=snapshot,
            provider_kind=provider_kind,
            image_ref=image_ref,
            alternate_image_ref=alternate_image_ref,
            image_metadata=image_metadata,
            alternate_image_metadata=alternate_image_metadata,
            disk_headroom=disk_headroom,
            preflight=preflight_payload,
        )
    )
    runner_probe = _agents_last_exam_runner_binary_probe(runner_binary)
    module_probe = _agents_last_exam_python_module_probe(
        runner_python_module,
        source_root=runner_source_root,
    )
    source_lock = None
    if fetch_origin or require_upstream_current:
        source_lock = build_agents_last_exam_local_source_readiness(
            source_root=runner_source_root,
            runner_python_module=runner_python_module or "ale_run",
            fetch_origin=fetch_origin,
            require_upstream_current=require_upstream_current,
        )
    command_label = _agents_last_exam_public_id(
        runner_command_label
        or (
            f"{runner_probe.get('binary')}-m-{module_probe.get('module')}"
            if runner_probe.get("binary") and module_probe.get("module")
            else runner_probe.get("binary")
        ),
        limit=120,
    )
    module_required = _agents_last_exam_runner_binary_requires_python_module(
        runner_binary
    )
    blockers: list[str] = []
    if operator_authorized is not True:
        blockers.append("operator_authorization_missing")
    if allow_public_task_material is not True:
        blockers.append("public_task_material_authorization_missing")
    if plan_payload.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(plan_payload.get("first_blocker"), limit=80)
            or "ale_local_dry_run_plan_not_ready"
        )
    if not command_label:
        blockers.append("runner_command_missing")
    if runner_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(runner_probe.get("first_blocker"), limit=80)
            or "runner_binary_not_available"
        )
    if module_required and module_probe.get("declared") is not True:
        blockers.append("runner_python_module_missing")
    if module_probe.get("declared") is True and module_probe.get("available") is not True:
        blockers.append(
            _agents_last_exam_public_id(module_probe.get("first_blocker"), limit=80)
            or "runner_python_module_not_available"
        )
    if source_lock is not None and source_lock.get("ready") is not True:
        blockers.append(
            _agents_last_exam_public_id(source_lock.get("first_blocker"), limit=80)
            or "ale_source_lock_not_ready"
        )
    ready = not blockers

    return {
        "schema_version": AGENTS_LAST_EXAM_LOCAL_RUNNER_READINESS_SCHEMA_VERSION,
        "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
        "task_id": plan_payload.get("task_id") or "metadata_only_candidate",
        "snapshot": plan_payload.get("snapshot") or AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        "preflight_ready": preflight_payload.get("ready") is True,
        "dry_run_plan_ready": plan_payload.get("ready") is True,
        "runner_ready": ready,
        "ready": ready,
        "first_blocker": blockers[0]
        if blockers
        else "ready_for_local_ale_dry_run_runner",
        "blockers": blockers,
        "runner_probe": {
            "command_label": command_label,
            "binary": runner_probe.get("binary"),
            "binary_declared": runner_probe.get("declared") is True,
            "binary_available": runner_probe.get("available") is True,
            "python_module": module_probe.get("module"),
            "python_module_declared": module_probe.get("declared") is True,
            "python_module_available": module_probe.get("available") is True,
            "source_root_declared": module_probe.get("source_root_declared") is True,
            "source_root_available": module_probe.get("source_root_available") is True,
            "source_root_path_recorded": False,
            "python_module_path_recorded": False,
            "binary_path_recorded": False,
            "command_argv_recorded": False,
            "first_blocker": _agents_last_exam_public_id(
                runner_probe.get("first_blocker"),
                limit=80,
            ),
        },
        "source_lock": source_lock,
        "boundary": {
            "local_only": True,
            "no_cloud": provider_kind == "docker",
            "no_upload": True,
            "submit_eligible": False,
            "leaderboard_evidence": False,
            "operator_authorized_local_container_start": operator_authorized is True,
            "operator_authorized_public_task_material": (
                allow_public_task_material is True
            ),
            "container_started": False,
            "task_body_read": False,
            "model_api_invoked": False,
            "model_api_allowed": False,
            "upload_allowed": False,
            "submit_allowed": False,
            "raw_trajectory_read": False,
            "screenshot_captured": False,
            "credential_values_recorded": False,
            "hidden_references_allowed": False,
            "production_actions_allowed": False,
            "local_paths_recorded": False,
        },
        "decision": {
            "next_allowed_action": "run_configured_no_upload_ale_local_dry_run"
            if ready
            else "configure_verified_ale_local_runner_before_execution",
            "minimum_next_evidence": (
                "A configured local runner command label and PATH-visible runner "
                "binary, followed by one no-upload dry-run that produces compact "
                "run/eval/events metadata only."
            ),
            "must_not_claim": [
                "ALE task success",
                "ALE score uplift",
                "LoopX treatment advantage",
                "leaderboard evidence",
            ],
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
            "container_started": False,
        },
    }

def build_agents_last_exam_result_benchmark_report(
    run_dir: str | Path,
    *,
    report_id: str | None = None,
    harness_identity: str = "loopx-meta",
    runner_source: str = "ale_run_run_writer_v2",
    harness_policy_version: str = AGENTS_LAST_EXAM_RESULT_INGEST_POLICY_VERSION,
    trace_publicness: str = AGENTS_LAST_EXAM_TRACE_PUBLICNESS,
) -> dict[str, Any]:
    """Compact an ALE run directory into benchmark_experiment_report_v0.

    The compactor reads only ALE's compact top-level files: ``run.json``,
    ``eval_result.json``, and ``events.jsonl``. It deliberately does not read or
    record ``trajectory.json``, ``origin_log/``, ``output/``, task bodies,
    screenshots, credential values, or local absolute paths.
    """

    path = Path(run_dir)
    run_json = _load_json_object(path / "run.json")
    eval_result = _load_json_object(path / "eval_result.json")
    events = _load_jsonl_objects(path / "events.jsonl")
    score = _optional_float(eval_result.get("score"))
    eval_status = _agents_last_exam_public_id(eval_result.get("eval_status"), limit=80)
    run_status = _agents_last_exam_public_id(
        _agents_last_exam_nested(run_json, "status"),
        limit=80,
    )
    task_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "task_path"),
        _agents_last_exam_nested(run_json, "task_id"),
        _agents_last_exam_nested(run_json, "task"),
        default="unknown_task",
    )
    agent_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "agent_id"),
        _agents_last_exam_nested(run_json, "agent"),
        default="unknown_agent",
    )
    model_label = _agents_last_exam_first_public_id(
        _agents_last_exam_nested(run_json, "model"),
        default="unknown_model",
    )
    run_id = _agents_last_exam_public_id(
        run_json.get("run_id") or path.name,
        limit=160,
    ) or "unknown_run"
    report_label = (
        _agents_last_exam_public_id(report_id, limit=160)
        if report_id
        else f"{AGENTS_LAST_EXAM_BENCHMARK_ID}-{run_id}"
    )
    event_counts = _agents_last_exam_event_type_counts(events)
    error = eval_result.get("error") if isinstance(eval_result.get("error"), dict) else {}
    error_type = _agents_last_exam_public_id(
        error.get("type") or error.get("exception_type") or error.get("class"),
        limit=80,
    )
    duration_s = _optional_float(
        run_json.get("duration_s")
        or run_json.get("elapsed_s")
        or _agents_last_exam_nested(run_json, "duration_s")
    )
    eval_duration_s = _optional_float(eval_result.get("eval_duration_s"))
    raw_surface_presence = {
        "trajectory_json_present": (path / "trajectory.json").exists(),
        "origin_log_dir_present": (path / "origin_log").exists(),
        "output_dir_present": (path / "output").exists(),
    }
    run_json_present = bool(run_json)
    eval_result_present = bool(eval_result)
    events_jsonl_present = (path / "events.jsonl").exists()
    completed = eval_status in {"passed", "completed", "success", "ok"} or (
        score is not None and not error_type
    )
    source_events = [
        "ale run.json parsed" if run_json_present else "ale run.json missing",
        "ale eval_result.json parsed" if eval_result_present else "ale eval_result.json missing",
        "ale events.jsonl counted" if events_jsonl_present else "ale events.jsonl missing",
        "raw ALE trajectory/origin_log/output excluded",
    ]
    negative_layers = ["single_arm_no_delta", "raw_surfaces_excluded"]
    if not run_json_present:
        negative_layers.append("run_json_missing")
    if not eval_result_present:
        negative_layers.append("eval_result_missing")
    if error_type:
        negative_layers.append("eval_error_present")

    return {
        "schema_version": "benchmark_experiment_report_v0",
        "experiment_identity": {
            "report_id": report_label,
            "benchmark_id": AGENTS_LAST_EXAM_BENCHMARK_ID,
            "task_slice": task_label,
            "worker_surface": "ale_run_compact_result_ingest",
            "harness_identity": harness_identity,
            "harness_policy_version": harness_policy_version,
            "trace_publicness": trace_publicness,
        },
        "official_score": {
            "kind": "ale_eval_result" if score is not None else "ale_eval_result_missing",
            "task_id_or_split": task_label,
            "runner_source": runner_source,
            "native_score": score if score is not None else 0.0,
            "wrapped_score": score if score is not None else 0.0,
            "delta": 0.0,
            "repetitions": 1 if eval_result_present else 0,
            "submit_eligible": False,
            "leaderboard_evidence": False,
        },
        "passive_control_plane_score": {
            "restartability": 1.0 if run_json_present and events_jsonl_present else 0.5,
            "stale_state_avoidance": 1.0,
            "evidence_discipline": 1.0,
            "writeback_quality": 1.0 if eval_result_present else 0.5,
            "failure_attribution": 1.0 if error_type or completed else 0.5,
            "overhead_bounded": True,
            "regression_avoidance_passed": True,
            "source_events": source_events,
        },
        "operator_simulator_ablation": {
            "enabled": False,
            "leaderboard_evidence": False,
            "intervention_count": 0,
            "reason": "ALE compact result ingest is passive; simulator evidence must be a separate treatment layer.",
        },
        "cost_latency_overhead": {
            "duration_s": duration_s,
            "eval_duration_s": eval_duration_s,
            "event_count": len(events),
            "event_type_counts": event_counts,
            "raw_trace_recorded": False,
            "raw_output_recorded": False,
        },
        "failure_taxonomy": {
            "run_status": run_status or "unknown",
            "eval_status": eval_status or "unknown",
            "error_type": error_type or "none",
            "score_missing": score is None,
            "single_arm_no_delta": True,
        },
        "reproducibility_artifacts": {
            "run_json_present": run_json_present,
            "eval_result_json_present": eval_result_present,
            "events_jsonl_present": events_jsonl_present,
            "event_count": len(events),
            "event_type_counts": event_counts,
            "agent_id": agent_label,
            "model": model_label,
            "task_id": task_label,
            "raw_surfaces_excluded": list(AGENTS_LAST_EXAM_RAW_SURFACES_EXCLUDED),
            "raw_surface_presence_checked": raw_surface_presence,
            "raw_surface_content_recorded": False,
            "local_paths_recorded": False,
            "credential_values_recorded": False,
        },
        "claim_boundary": {
            "may_claim": [
                "ALE compact run/eval/events artifacts can be reduced to benchmark_experiment_report_v0",
                "Raw trajectory, origin logs, outputs, task bodies, screenshots, credentials, and local paths are excluded",
                "The report is a single-arm compact ingest artifact, not a paired treatment comparison",
            ],
            "must_not_claim": [
                "ALE leaderboard evidence",
                "LoopX treatment advantage",
                "baseline-versus-treatment score delta",
                "task solution quality from raw trajectory or outputs",
            ],
            "source_decision_note_schema": "agents_last_exam_result_ingest_contract_v0",
            "source_evidence_layer": "compact_run_eval_events_only",
        },
        "negative_results": {
            "null_official_delta": True,
            "failed_hypothesis_count": 0,
            "negative_evidence_layers": negative_layers,
            "overhead_regression_count": 0,
        },
        "next_decision": {
            "decision": "wire_ale_report_append_or_authorize_no_upload_dry_run",
            "minimum_next_evidence": "Append a synthetic ALE compact report through history, or run an operator-approved no-upload ALE dry-run without reading task bodies.",
            "stop_condition": "Stop before GCP setup, VM launch, model API use, paid compute, output upload, leaderboard submission, hidden refs, task solutions, task body copying, raw trajectories, screenshots, local absolute paths, credential values, or production actions.",
            "source_decision_note_schema": "benchmark_experiment_report_v0",
            "readiness_decision": "compact_ingest_ready",
            "failure_decision": "do_not_infer_pairwise_uplift_from_single_arm_ingest",
        },
        "section_count": 10,
    }
