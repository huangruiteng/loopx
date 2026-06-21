#!/usr/bin/env python3
"""Smoke-test the compact ALE validation-run gate."""

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
    AGENTS_LAST_EXAM_CASE_GOAL_ID,
    AGENTS_LAST_EXAM_CASE_STATE_PATH,
    build_agents_last_exam_task_material_readiness,
    build_agents_last_exam_validation_run_gate,
)
from loopx.benchmark_case_state import (  # noqa: E402
    BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION,
    benchmark_case_active_state_init_contract,
)

TASK_ID = "computing_math/os_log_permission_guard_v1"
TASK_LABEL = "computing_math__os_log_permission_guard_v1"
HYPOTHESIS = (
    "LoopX should improve ALE validation by requiring task material, "
    "host Codex route, exact dry-run, and compact result reducer readiness."
)


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


def false_boundary() -> dict[str, object]:
    return {
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
        "raw_output_recorded": False,
    }


def make_host_no_task_payload() -> dict[str, object]:
    return {
        "schema_version": "agents_last_exam_host_codex_cua_no_task_smoke_v0",
        "ready": True,
        "first_blocker": "ready_for_task_level_ale_codex_dry_run_gate",
        "boundary": false_boundary(),
    }


def make_exact_dry_run_payload(task_label: str = TASK_LABEL) -> dict[str, object]:
    return {
        "schema_version": "agents_last_exam_local_exact_dry_run_result_v0",
        "ready": True,
        "first_blocker": "ready_for_compact_ale_dry_run_result_ingest",
        "expected": {
            "agent": "host_codex",
            "task": task_label,
        },
        "boundary": false_boundary(),
    }


def make_launch_packet_payload(
    *,
    fresh_source: bool = False,
    source_lock_overrides: dict[str, object] | None = None,
    include_case_state_contract: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "agents_last_exam_local_launch_packet_v0",
        "ready": True,
        "first_blocker": "ready_for_operator_triggered_no_upload_ale_dry_run",
        "boundary": false_boundary(),
    }
    if include_case_state_contract:
        payload["case_state_init_contract"] = (
            benchmark_case_active_state_init_contract(
                benchmark_id="agents-last-exam",
                goal_id=AGENTS_LAST_EXAM_CASE_GOAL_ID,
                case_state_path=AGENTS_LAST_EXAM_CASE_STATE_PATH,
            )
        )
    if fresh_source:
        payload["source_lock"] = {
            "expected_repo": "github.com/rdi-berkeley/agents-last-exam",
            "remote": "github.com/rdi-berkeley/agents-last-exam",
            "remote_matches_expected": True,
            "head": "abc1234",
            "upstream_ref": "origin/main",
            "upstream_head": "abc1234",
            "upstream_declared": True,
            "head_matches_upstream": True,
            "upstream_ahead_count": 0,
            "upstream_behind_count": 0,
            "fetch_origin_attempted": True,
            "fetch_origin_ok": True,
            "require_upstream_current": True,
            "source_root_path_recorded": False,
        }
    if source_lock_overrides:
        source_lock = payload.setdefault("source_lock", {})
        assert isinstance(source_lock, dict)
        source_lock.update(source_lock_overrides)
    return payload


def assert_public_safe(payload: dict[str, object], temp_root: Path) -> None:
    rendered = json.dumps(payload, sort_keys=True)
    forbidden = [
        str(temp_root),
        "SECRET_TASK_BODY_SHOULD_NOT_LEAK",
        "SECRET_SCRIPT_BODY_SHOULD_NOT_LEAK",
        "task_card.json",
        "trajectory.json",
        "screenshot.png",
        "OPENAI_API_KEY",
        "CODEX_ACCESS_TOKEN",
    ]
    leaked = [item for item in forbidden if item in rendered]
    assert not leaked, leaked
    run_boundary = payload["run_boundary"]
    assert isinstance(run_boundary, dict)
    assert run_boundary["case_state_init_required_before_worker"] is True
    assert run_boundary["case_state_initialized_by_this_gate"] is False
    assert run_boundary["case_state_path"] == AGENTS_LAST_EXAM_CASE_STATE_PATH
    assert (
        run_boundary["case_state_schema_version"]
        == BENCHMARK_CASE_ACTIVE_STATE_SCHEMA_VERSION
    )
    assert run_boundary["task_run_started_by_this_gate"] is False
    assert run_boundary["container_started_by_this_gate"] is False
    assert run_boundary["model_api_invoked_by_this_gate"] is False
    assert run_boundary["codex_prompt_sent_by_this_gate"] is False
    assert run_boundary["raw_trajectory_read"] is False
    assert run_boundary["task_body_read_by_loopx"] is False
    assert run_boundary["credential_values_recorded"] is False
    assert run_boundary["local_paths_recorded"] is False


def run_function_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-validation-gate-") as tmp:
        temp_root = Path(tmp)
        source = make_source(temp_root)
        task_material = build_agents_last_exam_task_material_readiness(
            source_root=str(source),
            selected_task_id=TASK_ID,
        )
        host_no_task = make_host_no_task_payload()
        exact = make_exact_dry_run_payload()
        launch_packet = make_launch_packet_payload()

        payload = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=launch_packet,
            result_reducer_ready=True,
        )
        assert payload["schema_version"] == "agents_last_exam_validation_run_gate_v0", payload
        assert payload["ready"] is True, payload
        assert (
            payload["first_blocker"]
            == "ready_for_operator_authorized_local_no_upload_ale_validation_run"
        ), payload
        assert payload["decision"]["next_allowed_action"] == (
            "operator_authorized_local_no_upload_ale_validation_run"
        ), payload
        assert payload["readiness_inputs"]["compact_result_reducer_ready"] is True, payload
        assert payload["readiness_inputs"]["case_state_init_contract_ready"] is True, payload
        assert_public_safe(payload, temp_root)

        missing_case_state_contract = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=make_launch_packet_payload(
                include_case_state_contract=False
            ),
            result_reducer_ready=True,
        )
        assert missing_case_state_contract["ready"] is False, missing_case_state_contract
        assert (
            "case_state_init_contract_missing"
            in missing_case_state_contract["blockers"]
        ), missing_case_state_contract
        assert (
            missing_case_state_contract["readiness_inputs"][
                "case_state_init_contract_ready"
            ]
            is False
        ), missing_case_state_contract
        assert_public_safe(missing_case_state_contract, temp_root)

        no_reducer = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=launch_packet,
            result_reducer_ready=False,
        )
        assert no_reducer["ready"] is False, no_reducer
        assert no_reducer["first_blocker"] == "compact_result_reducer_not_ready", no_reducer
        assert_public_safe(no_reducer, temp_root)

        mismatch = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=make_exact_dry_run_payload(
                "computing_math__other_task"
            ),
            launch_packet=launch_packet,
            result_reducer_ready=True,
        )
        assert mismatch["ready"] is False, mismatch
        assert "selected_task_mismatch_exact_dry_run" in mismatch["blockers"], mismatch
        assert_public_safe(mismatch, temp_root)

        formal_without_fresh_source = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=launch_packet,
            result_reducer_ready=True,
            formal_score_candidate=True,
        )
        assert formal_without_fresh_source["ready"] is False, formal_without_fresh_source
        assert formal_without_fresh_source["readiness_inputs"]["fresh_source_required"] is True
        assert (
            "ale_source_freshness_not_verified"
            in formal_without_fresh_source["blockers"]
        ), formal_without_fresh_source
        assert_public_safe(formal_without_fresh_source, temp_root)

        stale_source = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=make_launch_packet_payload(
                fresh_source=True,
                source_lock_overrides={
                    "head_matches_upstream": False,
                    "upstream_behind_count": 1,
                },
            ),
            result_reducer_ready=True,
            formal_score_candidate=True,
        )
        assert stale_source["ready"] is False, stale_source
        assert "ale_source_not_at_upstream_head" in stale_source["blockers"], stale_source
        assert_public_safe(stale_source, temp_root)

        formal_ready = build_agents_last_exam_validation_run_gate(
            selected_task_id=TASK_ID,
            validation_hypothesis=HYPOTHESIS,
            task_material_readiness=task_material,
            host_codex_no_task_e2e=host_no_task,
            exact_dry_run_result=exact,
            launch_packet=make_launch_packet_payload(fresh_source=True),
            result_reducer_ready=True,
            formal_score_candidate=True,
        )
        assert formal_ready["ready"] is True, formal_ready
        assert formal_ready["readiness_inputs"]["fresh_source_ready"] is True, formal_ready
        assert_public_safe(formal_ready, temp_root)


def run_cli_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="ale-validation-gate-cli-") as tmp:
        temp_root = Path(tmp)
        source = make_source(temp_root)
        artifacts = {
            "task.json": build_agents_last_exam_task_material_readiness(
                source_root=str(source),
                selected_task_id=TASK_ID,
            ),
            "host.json": make_host_no_task_payload(),
            "dry-run.json": make_exact_dry_run_payload(),
            "launch.json": make_launch_packet_payload(fresh_source=True),
        }
        for name, payload in artifacts.items():
            (temp_root / name).write_text(json.dumps(payload), encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-validation-run-gate",
                "--selected-task-id",
                TASK_ID,
                "--validation-hypothesis",
                HYPOTHESIS,
                "--task-material-readiness-json",
                str(temp_root / "task.json"),
                "--host-codex-no-task-e2e-json",
                str(temp_root / "host.json"),
                "--exact-dry-run-json",
                str(temp_root / "dry-run.json"),
                "--launch-packet-json",
                str(temp_root / "launch.json"),
                "--result-reducer-ready",
                "--formal-score-candidate",
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
        assert payload["readiness_inputs"]["fresh_source_ready"] is True, payload
        assert payload["readiness_inputs"]["case_state_init_contract_ready"] is True, payload
        assert_public_safe(payload, temp_root)

        stale_launch = make_launch_packet_payload(
            fresh_source=True,
            source_lock_overrides={
                "fetch_origin_attempted": False,
            },
        )
        (temp_root / "stale-launch.json").write_text(
            json.dumps(stale_launch),
            encoding="utf-8",
        )
        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "ale-validation-run-gate",
                "--selected-task-id",
                TASK_ID,
                "--validation-hypothesis",
                HYPOTHESIS,
                "--task-material-readiness-json",
                str(temp_root / "task.json"),
                "--host-codex-no-task-e2e-json",
                str(temp_root / "host.json"),
                "--exact-dry-run-json",
                str(temp_root / "dry-run.json"),
                "--launch-packet-json",
                str(temp_root / "stale-launch.json"),
                "--result-reducer-ready",
                "--formal-score-candidate",
                "--require-ready",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert failed.returncode == 1, failed.stdout
        failed_payload = json.loads(failed.stdout)
        assert failed_payload["ok"] is False, failed_payload
        assert failed_payload["error"] == "ale_source_fetch_origin_not_attempted", failed_payload
        assert_public_safe(failed_payload, temp_root)


if __name__ == "__main__":
    run_function_smoke()
    run_cli_smoke()
    print("agents-last-exam-validation-run-gate-smoke ok")
