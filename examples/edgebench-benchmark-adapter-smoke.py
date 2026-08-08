#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.benchmark_adapters.edgebench import (  # noqa: E402
    EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS,
    build_edgebench_sforge_preflight,
    build_edgebench_sforge_run_plan,
    reduce_edgebench_final_result,
)


def assert_boundary(payload: dict[str, object]) -> None:
    boundary = payload["boundary"]
    assert isinstance(boundary, dict)
    assert boundary["container_started"] is False
    assert boundary["task_body_read"] is False
    assert boundary["hidden_tests_read"] is False
    assert boundary["model_api_invoked"] is False
    assert boundary["raw_logs_read"] is False
    assert boundary["raw_trajectory_read"] is False
    assert boundary["credential_values_recorded"] is False
    assert boundary["local_paths_recorded"] is False
    assert boundary["command_argv_recorded"] is False
    assert boundary["upload_invoked"] is False
    assert boundary["submit_invoked"] is False
    assert boundary["leaderboard_evidence"] is False


def ready_preflight() -> dict[str, object]:
    return build_edgebench_sforge_preflight(
        task_id="ad_placement_optimization",
        backend="docker",
        linux_host=True,
        sforge_available=True,
        container_runtime_available=True,
        task_catalog_ready=True,
        task_images_ready=True,
        judge_ready=True,
    )


def test_contracts() -> None:
    ready = ready_preflight()
    assert ready["ready"] is True
    assert ready["open_task_count"] == 51
    assert ready["first_blocker"] == "ready_for_edgebench_run_plan"
    assert ready["score_policy"]["selection"] == "best_submission_over_time"
    assert_boundary(ready)

    blocked = build_edgebench_sforge_preflight(
        task_id="ad_placement_optimization",
        backend="docker",
        linux_host=True,
        sforge_available=False,
        container_runtime_available=False,
        task_catalog_ready=False,
        task_images_ready=False,
        judge_ready=False,
    )
    assert blocked["ready"] is False
    assert blocked["first_blocker"] == "sforge_not_available"
    assert_boundary(blocked)

    plan = build_edgebench_sforge_run_plan(
        preflight=ready,
        agent="codex",
        model="gpt-5.5",
        timeout_seconds=7_200,
        run_id="edgebench-smoke-001",
    )
    assert plan["ready"] is True
    assert plan["runner"]["entrypoint"] == "sforge run"
    assert plan["runner"]["required_secret_names"] == ["SFORGE_AGENT_API_KEY"]
    assert plan["evaluation"]["official_setting"] is False
    assert plan["evaluation"]["leaderboard_eligible"] is False
    assert_boundary(plan)

    forged = build_edgebench_sforge_run_plan(
        preflight={
            "ready": True,
            "task_id": "ad_placement_optimization",
            "backend": "docker",
        },
        agent="codex",
        model="gpt-5.5",
        timeout_seconds=7_200,
        run_id="edgebench-smoke-forged",
    )
    assert forged["ready"] is False
    assert forged["first_blocker"] == "edgebench_preflight_contract_invalid"
    assert_boundary(forged)

    try:
        build_edgebench_sforge_run_plan(
            preflight=ready,
            agent="codex",
            model="gpt-5.5",
            timeout_seconds=EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS + 1,
            run_id="edgebench-smoke-002",
        )
    except ValueError as exc:
        assert "timeout_seconds" in str(exc)
    else:
        raise AssertionError("run plan accepted a budget above 12 hours")

    compact = reduce_edgebench_final_result(
        task_id="ad_placement_optimization",
        run_id="edgebench-smoke-001",
        result={
            "best_score": 62.9,
            "best_pass_rate": 0.8,
            "best_round": "agent-4",
            "total_rounds": 7,
            "agent_submissions": 4,
            "auto_submissions": 3,
            "runtime_seconds": 7_199.5,
            "resume_count": 1,
            "timed_out": True,
            "agent_output": "must not be projected",
            "archive_size_bytes": 1234,
        },
    )
    assert compact["countable"] is True
    assert compact["metrics"] == {
        "best_score": 62.9,
        "best_pass_rate": 0.8,
        "best_round": "agent-4",
        "total_rounds": 7,
        "agent_submissions": 4,
        "auto_submissions": 3,
        "runtime_seconds": 7_199.5,
        "resume_count": 1,
        "timed_out": True,
    }
    assert "agent_output" not in json.dumps(compact)
    assert "archive_size_bytes" not in json.dumps(compact)
    assert_boundary(compact)

    mismatched = reduce_edgebench_final_result(
        task_id="ad_placement_optimization",
        run_id="edgebench-smoke-mismatch",
        result={
            "best_score": 62.9,
            "total_rounds": 7,
            "agent_submissions": 4,
            "auto_submissions": 2,
            "runtime_seconds": 7_199.5,
        },
    )
    assert mismatched["countable"] is False
    assert mismatched["first_blocker"] == "edgebench_submission_rounds_mismatch"
    assert_boundary(mismatched)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli() -> None:
    preflight = run_cli(
        "benchmark",
        "edgebench-preflight",
        "--task-id",
        "ad_placement_optimization",
        "--no-environment-probe",
    )
    assert preflight.returncode == 0, preflight.stderr
    blocked = json.loads(preflight.stdout)
    assert blocked["ok"] is True
    assert blocked["ready"] is False
    assert blocked["first_blocker"] == "edgebench_linux_host_required"
    assert_boundary(blocked)

    required = run_cli(
        "benchmark",
        "edgebench-preflight",
        "--task-id",
        "ad_placement_optimization",
        "--no-environment-probe",
        "--require-ready",
    )
    assert required.returncode == 1
    assert json.loads(required.stdout)["error"] == "edgebench_linux_host_required"

    with tempfile.TemporaryDirectory(prefix="loopx-edgebench-smoke-") as temp_dir:
        root = Path(temp_dir)
        preflight_path = root / "preflight.json"
        preflight_path.write_text(json.dumps(ready_preflight()), encoding="utf-8")
        plan = run_cli(
            "benchmark",
            "edgebench-run-plan",
            "--preflight-json",
            str(preflight_path),
            "--agent",
            "codex",
            "--model",
            "gpt-5.5",
            "--run-id",
            "edgebench-smoke-001",
            "--timeout-seconds",
            "7200",
            "--require-ready",
        )
        assert plan.returncode == 0, plan.stderr
        plan_payload = json.loads(plan.stdout)
        assert plan_payload["ok"] is True
        assert plan_payload["ready"] is True
        assert_boundary(plan_payload)

        result_path = root / "final_result.json"
        result_path.write_text(
            json.dumps(
                {
                    "best_score": 62.9,
                    "best_pass_rate": 0.8,
                    "best_round": "agent-4",
                    "total_rounds": 7,
                    "agent_submissions": 4,
                    "auto_submissions": 3,
                    "runtime_seconds": 7199.5,
                    "resume_count": 1,
                    "timed_out": True,
                }
            ),
            encoding="utf-8",
        )
        reduced = run_cli(
            "benchmark",
            "edgebench-result-reduce",
            "--result-json",
            str(result_path),
            "--task-id",
            "ad_placement_optimization",
            "--run-id",
            "edgebench-smoke-001",
            "--require-countable",
        )
        assert reduced.returncode == 0, reduced.stderr
        reduced_payload = json.loads(reduced.stdout)
        assert reduced_payload["ok"] is True
        assert reduced_payload["countable"] is True
        assert_boundary(reduced_payload)


def main() -> int:
    test_contracts()
    test_cli()
    print("edgebench-benchmark-adapter-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
