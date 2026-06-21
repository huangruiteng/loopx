#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark import build_agents_last_exam_local_launch_packet  # noqa: E402
from loopx.benchmark import (  # noqa: E402
    AGENTS_LAST_EXAM_CASE_GOAL_ID,
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
)
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
)

OFFICIAL_REPO = "https://github.com/rdi-berkeley/agents-last-exam.git"


def make_source_root(root: Path) -> Path:
    source_root = root / "ale-source"
    (source_root / "ale_run").mkdir(parents=True)
    (source_root / "ale_run" / "__init__.py").write_text("", encoding="utf-8")
    (source_root / "example_exp.yaml").write_text("name: fixture\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=source_root, check=True, capture_output=True)
    subprocess.run(["git", "config", "gc.auto", "0"], cwd=source_root, check=True)
    subprocess.run(
        ["git", "config", "gc.autoDetach", "false"],
        cwd=source_root,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "loopx@example.invalid"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "LoopX Smoke"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "remote", "add", "origin", OFFICIAL_REPO], cwd=source_root, check=True)
    subprocess.run(["git", "add", "ale_run/__init__.py", "example_exp.yaml"], cwd=source_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "branch", "--set-upstream-to", "origin/main", current_branch],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    return source_root


def advance_origin_main_without_advancing_head(source_root: Path) -> None:
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    (source_root / "upstream-only.txt").write_text("new upstream fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "upstream-only.txt"], cwd=source_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "upstream fixture"],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    upstream_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=source_root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", upstream_head],
        cwd=source_root,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "update-ref", f"refs/heads/{current_branch}", head_before],
        cwd=source_root,
        check=True,
        capture_output=True,
    )


def ready_image_metadata() -> dict[str, object]:
    return {
        "image_ref": "agentslastexam/ale-kasm:latest",
        "present": True,
        "probe_available": True,
        "architecture": "arm64",
        "os": "linux",
        "size_bytes": 5_461_758_836,
        "first_blocker": None,
    }


def blocked_image_metadata() -> dict[str, object]:
    return {
        "image_ref": "ale-ubuntu22-docker:latest",
        "present": False,
        "probe_available": True,
        "first_blocker": "docker_image_missing",
    }


def assert_no_execution(payload: dict[str, object]) -> None:
    launch_packet = payload["launch_packet"]
    assert isinstance(launch_packet, dict)
    assert launch_packet["will_execute"] is False
    assert launch_packet["will_start_container"] is False
    assert launch_packet["will_read_task_body"] is False
    assert launch_packet["will_invoke_model_api"] is False
    assert launch_packet["will_upload"] is False
    assert launch_packet["will_submit"] is False
    assert launch_packet["will_capture_screenshot"] is False
    assert launch_packet["will_record_credentials"] is False
    assert launch_packet["will_record_local_paths"] is False
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["screenshot_captured"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["hidden_references_allowed"] is False
    assert boundary["production_actions_allowed"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False
    source_lock = payload["source_lock"]
    assert isinstance(source_lock, dict)
    assert source_lock["source_root_path_recorded"] is False
    assert source_lock["fetch_origin_attempted"] in {False, True}
    runner = payload["runner"]
    assert isinstance(runner, dict)
    assert runner["source_root_path_recorded"] is False
    assert runner["command_argv_recorded"] is False
    spec = payload["experiment_spec"]
    assert isinstance(spec, dict)
    assert spec["content_read"] is False
    assert spec["source_root_path_recorded"] is False
    assert spec["external_root_path_recorded"] is False
    case_state = payload["case_state_init_contract"]
    assert isinstance(case_state, dict)
    assert (
        case_state["schema_version"] == BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
    ), case_state
    assert case_state["benchmark_case_goal_id"] == AGENTS_LAST_EXAM_CASE_GOAL_ID
    assert case_state["case_state_path"] == AGENTS_LAST_EXAM_CASE_STATE_PATH
    assert case_state["case_state_path"].startswith("/app/.codex/goals/")
    assert case_state["case_state_path"].endswith("/ACTIVE_GOAL_STATE.md")
    assert case_state["init_required_before_worker"] is True
    assert case_state["initialized_by_launch_packet"] is False
    assert case_state["init_stage"] == "before_codex_worker_start"
    assert case_state["surrogate_state_files_allowed"] is False
    assert case_state["raw_task_text_required_for_init"] is False
    assert case_state["local_paths_recorded"] is False
    assert ".loopx-case-state.md" not in json.dumps(case_state, sort_keys=True)
    for field in (
        "case_goal_state_init_required",
        "case_goal_state_initialized_before_agent",
        "case_goal_state_init_status",
        "case_goal_state_schema_version",
        "case_goal_state_path",
    ):
        assert field in case_state["proof_fields"], case_state


def run_fixture_smoke() -> None:
    tmp = tempfile.mkdtemp()
    try:
        source_root = make_source_root(Path(tmp))
        payload = build_agents_last_exam_local_launch_packet(
            source_root=str(source_root),
            experiment_spec_relative_path="example_exp.yaml",
            selected_task_id="computing_math/os_log_permission_guard_v1",
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_command_label="python-m-ale-run",
            operator_authorized=True,
            allow_public_task_material=True,
            image_metadata=ready_image_metadata(),
            alternate_image_metadata=blocked_image_metadata(),
        )
        assert payload["schema_version"] == "agents_last_exam_local_launch_packet_v0"
        assert payload["ready"] is True
        assert payload["first_blocker"] == "ready_for_operator_triggered_no_upload_ale_dry_run"
        assert payload["source_lock"]["remote_matches_expected"] is True
        assert payload["source_lock"]["head_matches_upstream"] is True
        assert payload["runner"]["python_module_available"] is True
        assert payload["experiment_spec"]["exists"] is True
        assert_no_execution(payload)

        external_spec_root = Path(tmp) / "loopx-ale-wrapper"
        external_spec_root.mkdir()
        (external_spec_root / "host_codex_spec.yaml").write_text(
            "name: host_codex_fixture\n",
            encoding="utf-8",
        )
        external_spec = build_agents_last_exam_local_launch_packet(
            source_root=str(source_root),
            experiment_spec_root=str(external_spec_root),
            experiment_spec_relative_path="host_codex_spec.yaml",
            selected_task_id="computing_math/os_log_permission_guard_v1",
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_command_label="python-m-ale-run",
            operator_authorized=True,
            allow_public_task_material=True,
            image_metadata=ready_image_metadata(),
            alternate_image_metadata=blocked_image_metadata(),
        )
        assert external_spec["ready"] is True
        assert external_spec["experiment_spec"]["exists"] is True
        assert external_spec["experiment_spec"]["root_kind"] == "external_spec_root"
        assert external_spec["experiment_spec"]["external_root_declared"] is True
        assert_no_execution(external_spec)

        fresh_required = build_agents_last_exam_local_launch_packet(
            source_root=str(source_root),
            experiment_spec_relative_path="example_exp.yaml",
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_command_label="python-m-ale-run",
            operator_authorized=True,
            allow_public_task_material=True,
            require_upstream_current=True,
            image_metadata=ready_image_metadata(),
            alternate_image_metadata=blocked_image_metadata(),
        )
        assert fresh_required["ready"] is True
        assert fresh_required["source_lock"]["require_upstream_current"] is True
        assert_no_execution(fresh_required)

        advance_origin_main_without_advancing_head(source_root)
        stale_source = build_agents_last_exam_local_launch_packet(
            source_root=str(source_root),
            experiment_spec_relative_path="example_exp.yaml",
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_command_label="python-m-ale-run",
            operator_authorized=True,
            allow_public_task_material=True,
            require_upstream_current=True,
            image_metadata=ready_image_metadata(),
            alternate_image_metadata=blocked_image_metadata(),
        )
        assert stale_source["ready"] is False
        assert stale_source["first_blocker"] == "source_root_behind_upstream"
        assert stale_source["source_lock"]["head_matches_upstream"] is False
        assert stale_source["source_lock"]["upstream_behind_count"] == 1
        assert_no_execution(stale_source)

        missing_spec = build_agents_last_exam_local_launch_packet(
            source_root=str(source_root),
            experiment_spec_relative_path="missing.yaml",
            runner_binary="python3",
            runner_python_module="ale_run",
            runner_command_label="python-m-ale-run",
            operator_authorized=True,
            allow_public_task_material=True,
            image_metadata=ready_image_metadata(),
            alternate_image_metadata=blocked_image_metadata(),
        )
        assert missing_spec["ready"] is False
        assert missing_spec["first_blocker"] == "experiment_spec_file_missing"
        assert_no_execution(missing_spec)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_cli_smoke() -> None:
    tmp = tempfile.mkdtemp()
    try:
        source_root = make_source_root(Path(tmp))
        external_spec_root = Path(tmp) / "loopx-ale-wrapper"
        external_spec_root.mkdir()
        (external_spec_root / "host_codex_spec.yaml").write_text(
            "name: host_codex_fixture\n",
            encoding="utf-8",
        )
        base_cmd = [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "benchmark",
            "ale-local-launch-packet",
            "--source-root",
            str(source_root),
            "--experiment-spec",
            "example_exp.yaml",
            "--runner-binary",
            "python3",
            "--runner-python-module",
            "ale_run",
            "--runner-command-label",
            "python-m-ale-run",
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
        assert payload["experiment_spec"]["exists"] is True
        assert_no_execution(payload)

        external_cmd = [
            *base_cmd[: base_cmd.index("--experiment-spec") + 2],
            "--experiment-spec-root",
            str(external_spec_root),
            *base_cmd[base_cmd.index("--experiment-spec") + 2 :],
        ]
        spec_index = external_cmd.index("--experiment-spec") + 1
        external_cmd[spec_index] = "host_codex_spec.yaml"
        external_result = subprocess.run(
            external_cmd,
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        external_payload = json.loads(external_result.stdout)
        assert external_payload["ok"] is True
        assert external_payload["experiment_spec"]["root_kind"] == "external_spec_root"
        assert external_payload["experiment_spec"]["external_root_declared"] is True
        assert external_payload["experiment_spec"]["exists"] is True
        assert_no_execution(external_payload)

        fresh_required = subprocess.run(
            [*base_cmd, "--require-upstream-current"],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        fresh_payload = json.loads(fresh_required.stdout)
        assert fresh_payload["ok"] is True
        assert fresh_payload["source_lock"]["head_matches_upstream"] is True
        assert_no_execution(fresh_payload)

        advance_origin_main_without_advancing_head(source_root)
        stale = subprocess.run(
            [*base_cmd, "--require-upstream-current", "--require-ready"],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert stale.returncode == 1
        stale_payload = json.loads(stale.stdout)
        assert stale_payload["ok"] is False
        assert stale_payload["error"] == "source_root_behind_upstream"
        assert_no_execution(stale_payload)

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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    run_fixture_smoke()
    run_cli_smoke()
    print("agents-last-exam-local-launch-packet-smoke ok")
