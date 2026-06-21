#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_agents_last_exam_local_preflight  # noqa: E402


def assert_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["local_only"] is True
    assert boundary["no_cloud"] is True
    assert boundary["no_upload"] is True
    assert boundary["submit_eligible"] is False
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False
    read_boundary = payload["read_boundary"]
    assert isinstance(read_boundary, dict)
    assert read_boundary["compact_only"] is True
    assert read_boundary["task_text_read"] is False
    assert read_boundary["raw_artifacts_read"] is False
    assert read_boundary["local_paths_recorded"] is False


def run_fixture_smoke() -> None:
    ready = build_agents_last_exam_local_preflight(
        selected_task_id="computing_math/os_log_permission_guard_v1",
        image_metadata={
            "image_ref": "agentslastexam/ale-kasm:latest",
            "present": True,
            "probe_available": True,
            "architecture": "arm64",
            "os": "linux",
            "size_bytes": 5_461_758_836,
            "first_blocker": None,
        },
        alternate_image_metadata={
            "image_ref": "ale-ubuntu22-docker:latest",
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_missing",
        },
        disk_headroom={
            "free_gib": 33.0,
            "total_gib": 460.0,
            "used_percent": 93.0,
            "path_recorded": False,
        },
    )
    assert ready["schema_version"] == "agents_last_exam_local_preflight_v0"
    assert ready["ready"] is True
    assert ready["first_blocker"] == "ready_for_local_no_upload_preflight"
    assert ready["decision"]["next_allowed_action"] == "run_no_upload_adapter_dry_run"
    assert_boundary(ready)

    blocked = build_agents_last_exam_local_preflight(
        selected_task_id="computing_math/os_log_permission_guard_v1",
        image_metadata={
            "image_ref": "agentslastexam/ale-kasm:latest",
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_missing",
        },
        alternate_image_metadata={
            "image_ref": "ale-ubuntu22-docker:latest",
            "present": False,
            "probe_available": True,
            "first_blocker": "docker_image_missing",
        },
        disk_headroom={
            "free_gib": 33.0,
            "total_gib": 460.0,
            "used_percent": 93.0,
            "path_recorded": False,
        },
    )
    assert blocked["ready"] is False
    assert blocked["first_blocker"] == "docker_image_missing"
    assert blocked["decision"]["next_allowed_action"] == "repair_preflight_blocker_before_ale_run"
    assert_boundary(blocked)


def run_cli_smoke() -> None:
    base_cmd = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--format",
        "json",
        "benchmark",
        "ale-local-preflight",
        "--selected-task-id",
        "computing_math/os_log_permission_guard_v1",
        "--no-docker-probe",
    ]
    result = subprocess.run(
        base_cmd,
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["ready"] is False
    assert payload["first_blocker"] == "docker_probe_disabled"
    assert_boundary(payload)

    require_ready = subprocess.run(
        [*base_cmd, "--require-ready"],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert require_ready.returncode == 1
    required_payload = json.loads(require_ready.stdout)
    assert required_payload["ok"] is False
    assert required_payload["error"] == "docker_probe_disabled"
    assert_boundary(required_payload)


if __name__ == "__main__":
    run_fixture_smoke()
    run_cli_smoke()
    print("agents-last-exam-local-preflight-smoke ok")
