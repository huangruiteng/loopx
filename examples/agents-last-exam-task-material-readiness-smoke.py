#!/usr/bin/env python3
"""Smoke-test public-safe ALE task material readiness gates."""

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
    build_agents_last_exam_baked_task_input_scan,
    build_agents_last_exam_baked_task_input_readiness,
    build_agents_last_exam_task_material_readiness,
)

TASK_ID = "computing_math/os_log_permission_guard_v1"


def make_source(root: Path) -> Path:
    source = root / "agents-last-exam"
    task = source / "tasks" / "computing_math" / "os_log_permission_guard_v1"
    scripts = task / "scripts"
    selected = source / "selected_tasks" / "unlicensed"
    scripts.mkdir(parents=True)
    selected.mkdir(parents=True)
    (source / "selected_tasks").mkdir(exist_ok=True)
    (task / "task_card.json").write_text(
        json.dumps({"prompt": "SECRET_TASK_BODY_SHOULD_NOT_LEAK"}) + "\n",
        encoding="utf-8",
    )
    (scripts / "score_os_log_permissions.py").write_text(
        "# SECRET_SCRIPT_BODY_SHOULD_NOT_LEAK\n",
        encoding="utf-8",
    )
    (source / "selected_tasks" / "linux_only.txt").write_text(
        f"{TASK_ID}\n",
        encoding="utf-8",
    )
    (selected / "near-term.txt").write_text(f"{TASK_ID}\n", encoding="utf-8")
    return source


def assert_public_safe(payload: dict[str, object], temp_root: Path) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        str(temp_root),
        "SECRET_TASK_BODY_SHOULD_NOT_LEAK",
        "SECRET_SCRIPT_BODY_SHOULD_NOT_LEAK",
        "secret/gcp_key.json",
        "task_card.json/",
        "trajectory.json",
        "screenshot.png",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["task_body_read"] is False
    assert boundary["task_card_content_read"] is False
    assert boundary["script_content_read"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["container_started"] is False
    task_data = payload.get("task_data")
    if isinstance(task_data, dict):
        assert task_data["credential_values_read"] is False
        assert task_data["credential_values_recorded"] is False
        assert task_data["local_paths_recorded"] is False
        assert task_data["gcs_sa_key_path_recorded"] is False
        local_staging = task_data.get("local_task_data_staging")
        if isinstance(local_staging, dict):
            assert local_staging["credential_values_read"] is False
            assert local_staging["credential_values_recorded"] is False
            assert local_staging["local_paths_recorded"] is False
            assert local_staging["task_data_content_read"] is False
            assert local_staging["archive_content_read"] is False


def assert_baked_probe_public_safe(payload: dict[str, object]) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        "/media/user/data/agenthle",
        "task_card.json",
        "trajectory.json",
        "screenshot.png",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["task_run_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["task_data_content_read"] is False
    assert boundary["directory_listed"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["codex_prompt_sent"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False


def assert_baked_scan_public_safe(payload: dict[str, object], temp_root: Path) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        str(temp_root),
        "/media/user/data/agenthle",
        "task_card.json",
        "trajectory.json",
        "screenshot.png",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["task_run_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["task_data_content_read"] is False
    assert boundary["directory_listed"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["codex_prompt_sent"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False
    probe = payload["probe"]
    assert isinstance(probe, dict)
    assert probe["expected_path_recorded"] is False
    assert probe["stdout_recorded"] is False
    assert probe["stderr_recorded"] is False
    assert probe["command_argv_recorded"] is False


def make_baked_probe(*, ready: bool) -> dict[str, object]:
    return {
        "schema_version": "agents_last_exam_baked_task_input_readiness_v0",
        "benchmark_id": "agents-last-exam",
        "ready": ready,
        "first_blocker": None
        if ready
        else "baked_task_input_missing",
        "blockers": []
        if ready
        else ["baked_task_input_missing"],
        "task": {
            "task_id": TASK_ID.replace("/", "__"),
            "category": "computing_math",
            "name": "os_log_permission_guard_v1",
        },
        "image": {"present": True, "image_ref": "agentslastexam__ale-kasm_latest"},
        "probe": {
            "kind": "docker_shell_test_directory_only",
            "attempted": True,
            "container_started": True,
            "baked_input_present": ready,
            "baked_input_readable": ready,
            "return_code_zero": ready,
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
            "container_started": True,
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


def run_function_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-task-material-") as tmp:
        temp_root = Path(tmp)
        source = make_source(temp_root)
        disabled_probe = build_agents_last_exam_baked_task_input_readiness(
            selected_task_id=TASK_ID,
            image_metadata={
                "image_ref": "agentslastexam/ale-kasm:latest",
                "present": False,
                "probe_available": False,
                "first_blocker": "docker_run_probe_disabled",
            },
        )
        assert disabled_probe["ready"] is False, disabled_probe
        assert disabled_probe["first_blocker"] == "docker_run_probe_disabled", disabled_probe
        assert_baked_probe_public_safe(disabled_probe)

        baked_scan = build_agents_last_exam_baked_task_input_scan(
            source_root=str(source),
            selected_task_lists=["linux_only.txt"],
            image_metadata={
                "image_ref": "agentslastexam/ale-kasm:latest",
                "present": True,
                "probe_available": True,
            },
            probe_results={TASK_ID: True},
        )
        assert baked_scan["ready"] is True, baked_scan
        assert baked_scan["candidates"]["eligible_baked_input_candidates"] == [TASK_ID], baked_scan
        assert_baked_scan_public_safe(baked_scan, temp_root)

        missing_scan = build_agents_last_exam_baked_task_input_scan(
            source_root=str(source),
            selected_task_lists=["linux_only.txt"],
            image_metadata={
                "image_ref": "agentslastexam/ale-kasm:latest",
                "present": True,
                "probe_available": True,
            },
            probe_results={TASK_ID: False},
        )
        assert missing_scan["ready"] is False, missing_scan
        assert missing_scan["first_blocker"] == "no_baked_input_candidate_found", missing_scan
        assert_baked_scan_public_safe(missing_scan, temp_root)

        payload = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
        )
        assert payload["schema_version"] == "agents_last_exam_task_material_readiness_v0", payload
        assert payload["ready"] is True, payload
        assert payload["first_blocker"] == "ready_for_local_no_upload_ale_task_gate", payload
        task = payload["task"]
        assert isinstance(task, dict)
        assert task["task_card_json_present"] is True, payload
        assert task["scripts_dir_present"] is True, payload
        assert task["scorer_script_count"] == 1, payload
        task_data = payload["task_data"]
        assert isinstance(task_data, dict)
        assert task_data["checked"] is False, payload
        public_lists = payload["public_task_lists"]
        assert isinstance(public_lists, dict)
        assert public_lists["present_count"] == 2, payload
        assert_public_safe(payload, temp_root)

        missing_baked = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            requires_task_data=True,
            task_data_source="baked_in_sandbox",
            enforce_task_data_source=True,
        )
        assert missing_baked["ready"] is False, missing_baked
        assert missing_baked["first_blocker"] == "baked_task_input_not_verified", missing_baked
        assert_public_safe(missing_baked, temp_root)

        failed_baked_probe = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            requires_task_data=True,
            task_data_source="baked_in_sandbox",
            baked_task_input_readiness=make_baked_probe(ready=False),
            enforce_task_data_source=True,
        )
        assert failed_baked_probe["ready"] is False, failed_baked_probe
        assert failed_baked_probe["first_blocker"] == "baked_task_input_missing", failed_baked_probe
        assert failed_baked_probe["task_data"]["baked_input_probe_declared"] is True, failed_baked_probe
        assert_public_safe(failed_baked_probe, temp_root)

        ready_baked_probe = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            requires_task_data=True,
            task_data_source="baked_in_sandbox",
            baked_task_input_readiness=make_baked_probe(ready=True),
            enforce_task_data_source=True,
        )
        assert ready_baked_probe["ready"] is True, ready_baked_probe
        assert ready_baked_probe["task_data"]["baked_input_present"] is True, ready_baked_probe
        assert ready_baked_probe["task_data"]["baked_input_probe_ready"] is True, ready_baked_probe
        assert_public_safe(ready_baked_probe, temp_root)

        missing_local = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            selected_task_lists=["linux_only.txt"],
            requires_task_data=True,
            task_data_source="local:task-data",
            enforce_task_data_source=True,
        )
        assert missing_local["ready"] is False, missing_local
        assert (
            missing_local["first_blocker"] == "local_task_data_directory_not_verified"
        ), missing_local
        assert missing_local["task_data"]["local_task_data_source"] is True, missing_local
        assert (
            missing_local["task_data"]["local_task_data_staging"]["route"]
            == "gated_huggingface_archive"
        ), missing_local
        assert (
            missing_local["task_data"]["local_task_data_staging"][
                "dataset_label"
            ]
            == "agents-last-exam-data-archive"
        ), missing_local
        assert (
            missing_local["task_data"]["local_task_data_staging"][
                "auth_status_checked"
            ]
            is False
        ), missing_local
        assert (
            "local_task_data_gated_huggingface_access_not_verified"
            in missing_local["task_data"]["local_task_data_staging"]["blockers"]
        ), missing_local
        assert missing_local["task_data"]["local_task_data_path_recorded"] is False, missing_local
        assert missing_local["task_data"]["local_task_data_content_read"] is False, missing_local
        assert_public_safe(missing_local, temp_root)

        (source / "task-data").mkdir()
        ready_local = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            selected_task_lists=["linux_only.txt"],
            requires_task_data=True,
            task_data_source="local:task-data",
            enforce_task_data_source=True,
        )
        assert ready_local["ready"] is True, ready_local
        assert ready_local["task_data"]["local_task_data_source_safe"] is True, ready_local
        assert ready_local["task_data"]["local_task_data_present"] is True, ready_local
        assert (
            ready_local["task_data"]["local_task_data_staging"]["ready"] is True
        ), ready_local
        assert_public_safe(ready_local, temp_root)

        official_gcs = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
            requires_task_data=True,
            task_data_source="gs://ale-data-public",
            gcs_sa_key="secret/gcp_key.json",
            gcs_sa_key_present=True,
            enforce_task_data_source=True,
        )
        assert official_gcs["ready"] is True, official_gcs
        assert official_gcs["task_data"]["official_gcs_source"] is True, official_gcs
        assert official_gcs["task_data"]["gcs_sa_key_present"] is True, official_gcs
        assert_public_safe(official_gcs, temp_root)

        missing_card = (
            source
            / "tasks"
            / "computing_math"
            / "os_log_permission_guard_v1"
            / "task_card.json"
        )
        missing_card.unlink()
        blocked = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
        )
        assert blocked["ready"] is False, blocked
        assert blocked["first_blocker"] == "task_card_json_missing", blocked
        assert_public_safe(blocked, temp_root)

        unsafe = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id="../private/task",
        )
        assert unsafe["ready"] is False, unsafe
        assert unsafe["first_blocker"] == "selected_task_id_not_public_safe", unsafe
        assert_public_safe(unsafe, temp_root)


def run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-task-material-cli-") as tmp:
        temp_root = Path(tmp)
        source = make_source(temp_root)
        baked_probe_path = temp_root / "baked-probe.json"
        baked_probe_path.write_text(
            json.dumps(make_baked_probe(ready=True)),
            encoding="utf-8",
        )
        probe_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-baked-task-input-readiness",
                "--selected-task-id",
                TASK_ID,
                "--no-docker-run",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        probe_payload = json.loads(probe_result.stdout)
        assert probe_payload["ok"] is True, probe_payload
        assert probe_payload["ready"] is False, probe_payload
        assert_baked_probe_public_safe(probe_payload)

        scan_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-baked-task-input-scan",
                "--source-root",
                str(source),
                "--selected-task-list",
                "linux_only.txt",
                "--no-docker-run",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        scan_payload = json.loads(scan_result.stdout)
        assert scan_payload["ok"] is True, scan_payload
        assert scan_payload["ready"] is False, scan_payload
        assert scan_payload["first_blocker"] == "docker_run_probe_disabled", scan_payload
        assert_baked_scan_public_safe(scan_payload, temp_root)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-task-material-readiness",
                "--source-root",
                str(source),
                "--selected-task-id",
                TASK_ID,
                "--requires-task-data",
                "true",
                "--task-data-source",
                "baked_in_sandbox",
                "--baked-task-input-readiness-json",
                str(baked_probe_path),
                "--enforce-task-data-source",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["ready"] is True, payload
        assert_public_safe(payload, temp_root)


if __name__ == "__main__":
    run_function_smoke()
    run_cli_smoke()
    print("agents-last-exam-task-material-readiness-smoke ok")
