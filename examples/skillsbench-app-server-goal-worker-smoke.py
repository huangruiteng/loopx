#!/usr/bin/env python3
"""Smoke-test the SkillsBench native Codex app-server Goal worker seam."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark import (  # noqa: E402
    SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION,
    build_skillsbench_app_server_goal_worker_contract,
    build_skillsbench_benchmark_run,
    skillsbench_route_contract,
)


ROUTE = "codex-app-server-goal-baseline"


def assert_plan_prerequisites(plan: dict[str, Any]) -> None:
    prereq = plan["runner_prerequisites"]
    assert plan["route"] == ROUTE, plan
    assert plan["agent"] == "codex-app-server-goal", plan
    assert prereq["agent_execution_mode"] == "host_codex_app_server_goal_worker", prereq
    assert prereq["codex_acp_runtime_container_bootstrap"] is False, prereq
    assert prereq["codex_acp_runtime_dependency_preflight"] is False, prereq
    assert prereq["container_codex_acp_install_skipped"] is True, prereq
    assert prereq["codex_app_server_goal_worker_adapter_present"] is True, prereq
    assert prereq["codex_app_server_goal_worker_turn_start_required"] is True, prereq
    assert prereq["codex_app_server_goal_worker_goal_get_required"] is True, prereq
    assert (
        prereq["codex_app_server_goal_worker_runner_integration_ready"] is False
    ), prereq


def test_route_contract_requires_native_goal_proof() -> None:
    contract = skillsbench_route_contract(ROUTE)
    assert contract["native_goal_mode_requested"] is True, contract
    assert contract["native_goal_mode_invoked"] is True, contract
    assert contract["codex_acp_protocol_used"] is False, contract
    assert "thread_goal_set_get" in contract["native_goal_mode_confirmation_status"], contract
    assert contract["reward_feedback_forwarded"] is False, contract


def test_worker_contract_is_public_safe() -> None:
    payload = build_skillsbench_app_server_goal_worker_contract(
        task_id="llm-prefix-cache-replay",
        model="gpt-5.5",
    )
    assert (
        payload["schema_version"]
        == SKILLSBENCH_APP_SERVER_GOAL_WORKER_CONTRACT_SCHEMA_VERSION
    ), payload
    assert payload["ready"] is True, payload
    assert payload["runner_integration_ready"] is False, payload
    assert payload["worker_adapter"]["worker_surface"] == "codex_app_server", payload
    assert "turn/start" in payload["worker_adapter"]["native_goal_methods_required"], payload
    assert payload["proof_required"]["thread_goal_get"] is True, payload
    assert payload["proof_required"]["turn_start"] is True, payload
    assert payload["boundary"]["raw_task_text_read_into_public_state"] is False, payload
    assert payload["worker_plan"]["claim_boundary"]["requires_turn_start_evidence"] is True, payload


def test_skeleton_marks_app_server_goal_actor() -> None:
    run = build_skillsbench_benchmark_run(route=ROUTE, task_id="llm-prefix-cache-replay")
    counters = run["interaction_counters"]
    policy = run["episode_policy"]
    assert run["source_runner"] == "goal_harness_skillsbench_host_codex_app_server_goal_worker", run
    assert counters["native_goal_mode_requested"] is True, counters
    assert counters["native_goal_mode_invoked"] is True, counters
    assert counters["codex_acp_protocol_used"] is False, counters
    assert policy["outer_controller"] == "codex_app_server_goal_worker", policy
    assert policy["inner_case_actor"] == "host_codex_app_server_goal_worker", policy


def test_launcher_plan_only_uses_native_worker_route() -> None:
    with tempfile.TemporaryDirectory(prefix="skillsbench-app-goal-plan-") as tmp:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
                "--task-id",
                "llm-prefix-cache-replay",
                "--route",
                ROUTE,
                "--jobs-dir",
                str(Path(tmp) / "jobs"),
                "--plan-only",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    plan = payload["launch_plan"]
    assert_plan_prerequisites(plan)
    contract = plan["app_server_goal_worker_contract"]
    assert contract["route"] == ROUTE, contract
    assert contract["worker_plan"]["schema_version"] == "codex_app_server_goal_worker_v0", contract


def test_host_worker_contract_only_cli() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_host_codex_goal_worker.py"),
            "--task-id",
            "tictoc-unnecessary-abort-detection",
            "--contract-only",
        ],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    contract = payload["worker_contract"]
    assert contract["route"] == ROUTE, contract
    assert contract["worker_adapter"]["script"] == "scripts/skillsbench_host_codex_goal_worker.py", contract


def test_full_run_fails_closed_until_worker_is_wired() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "skillsbench_automation_loop.py"),
            "--task-id",
            "llm-prefix-cache-replay",
            "--route",
            ROUTE,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2, result
    payload = json.loads(result.stderr)
    assert payload["error_type"] == "SkillsBenchNativeGoalWorkerIntegrationPending", payload
    assert "codex-acp" in payload["reason"], payload


if __name__ == "__main__":
    test_route_contract_requires_native_goal_proof()
    test_worker_contract_is_public_safe()
    test_skeleton_marks_app_server_goal_actor()
    test_launcher_plan_only_uses_native_worker_route()
    test_host_worker_contract_only_cli()
    test_full_run_fails_closed_until_worker_is_wired()
    print("skillsbench-app-server-goal-worker smoke ok")
