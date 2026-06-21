#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import (  # noqa: E402
    build_agents_last_exam_local_runner_readiness,
)


def ready_preflight() -> dict[str, object]:
    return {
        "schema_version": "agents_last_exam_local_preflight_v0",
        "benchmark_id": "agents-last-exam",
        "task_id": "computing_math__os_log_permission_guard_v1",
        "snapshot": "cpu-free-ubuntu",
        "provider": {
            "kind": "docker",
            "no_cloud": True,
            "required_image": {
                "image_ref": "agentslastexam__ale-kasm-latest",
                "present": True,
                "probe_available": True,
                "architecture": "arm64",
                "os": "linux",
                "size_bytes": 5_461_758_836,
                "first_blocker": None,
            },
            "alternate_image": {
                "image_ref": "ale-ubuntu22-docker-latest",
                "present": False,
                "probe_available": True,
                "first_blocker": "docker_image_missing",
            },
        },
        "disk_headroom": {
            "free_gib": 33.0,
            "total_gib": 460.0,
            "used_percent": 93.0,
            "path_recorded": False,
        },
        "ready": True,
        "first_blocker": "ready_for_local_no_upload_preflight",
        "boundary": {
            "local_only": True,
            "no_cloud": True,
            "no_upload": True,
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
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }


def assert_no_execution(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["model_api_allowed"] is False
    assert boundary["upload_allowed"] is False
    assert boundary["submit_allowed"] is False
    assert boundary["leaderboard_evidence"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["hidden_references_allowed"] is False
    assert boundary["production_actions_allowed"] is False
    assert boundary["local_paths_recorded"] is False
    read_boundary = payload["read_boundary"]
    assert isinstance(read_boundary, dict)
    assert read_boundary["compact_only"] is True
    assert read_boundary["task_text_read"] is False
    assert read_boundary["raw_artifacts_read"] is False
    assert read_boundary["local_paths_recorded"] is False
    assert read_boundary["container_started"] is False
    runner_probe = payload["runner_probe"]
    assert isinstance(runner_probe, dict)
    assert runner_probe["binary_path_recorded"] is False
    assert runner_probe["command_argv_recorded"] is False
    if "source_root_path_recorded" in runner_probe:
        assert runner_probe["source_root_path_recorded"] is False


def run_fixture_smoke() -> None:
    ready = build_agents_last_exam_local_runner_readiness(
        preflight=ready_preflight(),
        runner_binary="python3",
        runner_python_module="json",
        runner_command_label="ale-local-no-upload-dry-run",
        operator_authorized=True,
        allow_public_task_material=True,
    )
    assert ready["schema_version"] == "agents_last_exam_local_runner_readiness_v0"
    assert ready["ready"] is True
    assert ready["first_blocker"] == "ready_for_local_ale_dry_run_runner"
    assert ready["decision"]["next_allowed_action"] == "run_configured_no_upload_ale_local_dry_run"
    assert ready["boundary"]["operator_authorized_local_container_start"] is True
    assert ready["boundary"]["operator_authorized_public_task_material"] is True
    assert_no_execution(ready)

    missing_runner = build_agents_last_exam_local_runner_readiness(
        preflight=ready_preflight(),
        operator_authorized=True,
        allow_public_task_material=True,
    )
    assert missing_runner["ready"] is False
    assert missing_runner["first_blocker"] == "runner_command_missing"
    assert "runner_binary_missing" in missing_runner["blockers"]
    assert_no_execution(missing_runner)

    with tempfile.TemporaryDirectory() as tmp:
        source_root = Path(tmp)
        (source_root / "ale_run").mkdir()
        (source_root / "ale_run" / "__init__.py").write_text("", encoding="utf-8")
        source_ready = build_agents_last_exam_local_runner_readiness(
            preflight=ready_preflight(),
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_source_root=str(source_root),
            runner_command_label="ale-local-no-upload-dry-run",
            operator_authorized=True,
            allow_public_task_material=True,
        )
        assert source_ready["ready"] is True
        assert source_ready["runner_probe"]["source_root_declared"] is True
        assert source_ready["runner_probe"]["source_root_available"] is True
        assert source_ready["runner_probe"]["source_root_path_recorded"] is False
        assert_no_execution(source_ready)

    missing_module = build_agents_last_exam_local_runner_readiness(
        preflight=ready_preflight(),
        runner_binary="python3",
        runner_command_label="ale-local-no-upload-dry-run",
        operator_authorized=True,
        allow_public_task_material=True,
    )
    assert missing_module["ready"] is False
    assert "runner_python_module_missing" in missing_module["blockers"]
    assert_no_execution(missing_module)

    unapproved = build_agents_last_exam_local_runner_readiness(
        preflight=ready_preflight(),
        runner_binary="python3",
        runner_python_module="json",
        runner_command_label="ale-local-no-upload-dry-run",
    )
    assert unapproved["ready"] is False
    assert unapproved["first_blocker"] == "operator_authorization_missing"
    assert "public_task_material_authorization_missing" in unapproved["blockers"]
    assert_no_execution(unapproved)


def run_cli_smoke() -> None:
    base_cmd = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--format",
        "json",
        "benchmark",
        "ale-local-runner-readiness",
        "--selected-task-id",
        "computing_math/os_log_permission_guard_v1",
        "--runner-binary",
        "python3",
        "--runner-python-module",
        "ale_run",
        "--runner-source-root",
        str(REPO_ROOT),
        "--runner-command-label",
        "ale-local-no-upload-dry-run",
        "--operator-authorized",
        "--allow-public-task-material",
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
    assert payload["runner_probe"]["python_module"] == "ale_run"
    assert payload["runner_probe"]["python_module_available"] is False
    assert payload["runner_probe"]["source_root_declared"] is True
    assert payload["runner_probe"]["source_root_path_recorded"] is False
    assert_no_execution(payload)

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
    assert_no_execution(required_payload)


if __name__ == "__main__":
    run_fixture_smoke()
    run_cli_smoke()
    print("agents-last-exam-local-runner-readiness-smoke ok")
