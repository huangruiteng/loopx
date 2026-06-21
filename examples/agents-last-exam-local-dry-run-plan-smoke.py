#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_agents_last_exam_local_dry_run_plan  # noqa: E402


def assert_no_execution(payload: dict[str, object]) -> None:
    adapter_plan = payload["adapter_plan"]
    assert isinstance(adapter_plan, dict)
    assert adapter_plan["mode"] == "contract_only_no_execution"
    assert adapter_plan["will_start_container"] is False
    assert adapter_plan["will_read_task_body"] is False
    assert adapter_plan["will_invoke_model_api"] is False
    assert adapter_plan["will_upload"] is False
    assert adapter_plan["will_submit"] is False
    assert adapter_plan["will_capture_screenshot"] is False
    assert adapter_plan["will_record_credentials"] is False
    assert adapter_plan["will_record_local_paths"] is False
    read_boundary = payload["read_boundary"]
    assert isinstance(read_boundary, dict)
    assert read_boundary["compact_only"] is True
    assert read_boundary["task_text_read"] is False
    assert read_boundary["raw_artifacts_read"] is False
    assert read_boundary["local_paths_recorded"] is False
    assert read_boundary["container_started"] is False


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
        "decision": {
            "next_allowed_action": "run_no_upload_adapter_dry_run",
        },
        "read_boundary": {
            "compact_only": True,
            "task_text_read": False,
            "raw_artifacts_read": False,
            "local_paths_recorded": False,
        },
    }


def run_fixture_smoke() -> None:
    ready = build_agents_last_exam_local_dry_run_plan(preflight=ready_preflight())
    assert ready["schema_version"] == "agents_last_exam_local_dry_run_plan_v0"
    assert ready["ready"] is True
    assert ready["first_blocker"] == "ready_for_contract_only_dry_run_plan"
    assert ready["decision"]["next_allowed_action"] == "run_operator_authorized_no_upload_ale_adapter_dry_run"
    assert ready["paired_run_requirements"]["same_task"] is True
    assert ready["paired_run_requirements"]["baseline_arm"] == "hardened-codex"
    assert ready["paired_run_requirements"]["treatment_arm"] == "codex-loopx"
    assert_no_execution(ready)

    blocked_preflight = ready_preflight()
    blocked_preflight["ready"] = False
    blocked_preflight["first_blocker"] = "docker_image_missing"
    blocked_preflight["provider"]["required_image"]["present"] = False
    blocked = build_agents_last_exam_local_dry_run_plan(preflight=blocked_preflight)
    assert blocked["ready"] is False
    assert blocked["first_blocker"] == "docker_image_missing"
    assert blocked["decision"]["next_allowed_action"] == "repair_ale_local_dry_run_plan_blocker"
    assert_no_execution(blocked)


def run_cli_smoke() -> None:
    base_cmd = [
        sys.executable,
        "-m",
        "loopx.cli",
        "--format",
        "json",
        "benchmark",
        "ale-local-dry-run-plan",
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
    print("agents-last-exam-local-dry-run-plan-smoke ok")
