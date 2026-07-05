#!/usr/bin/env python3
"""Smoke-test SkillsBench verifier bootstrap missing-score attribution."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import compact_benchmark_run  # noqa: E402
from loopx.benchmark_adapters.skillsbench_verifier_bootstrap import (  # noqa: E402
    apply_skillsbench_verifier_bootstrap_missing_score_attribution,
)


def _missing_score_compact() -> dict:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "official_skillsbench_benchflow_launch_failure",
        "mode": "skillsbench_codex_app_server_goal_baseline",
        "route": "codex-app-server-goal-baseline",
        "dataset": "skillsbench@1.1",
        "task_id": "powerlifting-coef-calc",
        "agent": "codex",
        "model": "gpt-5.5-codex",
        "official_score_status": "missing",
        "official_score": None,
        "official_task_score": {
            "kind": "skillsbench_verifier_reward_missing",
            "value": None,
            "passed": False,
        },
        "score_failure_attribution": "skillsbench_runner_error",
        "failure_attribution_labels": [
            "official_score_missing",
            "skillsbench_runner_setup_error",
        ],
        "runner_failure": {
            "schema_version": "skillsbench_runner_failure_v0",
            "failure_class": "skillsbench_runner_error",
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        },
        "validation": {
            "raw_verifier_output_read": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
        },
    }


def _uv_bootstrap_plan() -> dict:
    return {
        "task_staging": {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": True,
            "verifier_uv_bootstrap_risk_detected": True,
            "verifier_uv_bootstrap_mirror_patch_required": True,
            "verifier_uv_bootstrap_mirror_patch_applied": True,
            "verifier_uv_bootstrap_pip_fallback_patch_applied": True,
            "verifier_uv_bootstrap_version": "0.7.13",
            "verifier_uv_bootstrap_mirror_host": "releases.astral.sh",
            "original_task_mutated": False,
        },
        "task_setup_preflight": {
            "schema_version": "skillsbench_task_setup_preflight_v0",
            "status": "verifier_bootstrap_risk_detected",
            "verifier_uv_bootstrap_risk_detected": True,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
        },
    }


def _package_install_pre_agent_plan() -> dict:
    return {
        "task_staging": {
            "schema_version": "skillsbench_task_staging_v0",
            "staged": False,
            "verifier_bootstrap_risk_detected": True,
            "verifier_bootstrap_risk_preflight_blocked": False,
            "verifier_package_install_risk_detected": True,
            "verifier_uv_bootstrap_risk_detected": False,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
        },
        "task_setup_preflight": {
            "schema_version": "skillsbench_task_setup_preflight_v0",
            "status": "verifier_bootstrap_risk_detected",
            "canonical_task_present": True,
            "dockerfile_present": True,
            "verifier_present": True,
            "verifier_bootstrap_risk_detected": True,
            "verifier_package_install_risk_detected": True,
            "verifier_external_download_risk_detected": False,
            "verifier_uv_bootstrap_risk_detected": False,
            "verifier_bootstrap_risk_categories": ["package_install"],
            "bootstrap_light_candidate_eligible": False,
            "bootstrap_light_blocking_fields": [
                "verifier_bootstrap_risk_detected",
                "verifier_package_install_risk_detected",
            ],
            "selection_recommendation": "route_to_setup_repair_or_use_fail_fast_guard",
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
        },
    }


def test_missing_score_uv_bootstrap_risk_gets_verifier_dependency_attribution() -> None:
    compact = _missing_score_compact()
    plan = _uv_bootstrap_plan()
    changed = apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        compact,
        task_staging=plan["task_staging"],
        setup_preflight=plan["task_setup_preflight"],
    )

    assert changed is True, compact
    assert compact["official_score_status"] == "missing", compact
    assert compact["official_score"] is None, compact
    assert compact["score_failure_attribution"] == (
        "verifier_dependency_install_failure"
    ), compact
    assert compact["verifier_dependency_failure_count"] == 1, compact
    assert "verifier_dependency_install_failure" in compact[
        "failure_attribution_labels"
    ], compact
    assert "verifier_uv_install_or_download_failure" in compact[
        "failure_attribution_labels"
    ], compact
    diagnostic = compact["verifier_bootstrap_diagnostic"]
    assert diagnostic["raw_verifier_output_read"] is False, diagnostic
    assert diagnostic["verifier_uv_bootstrap_version"] == "0.7.13", diagnostic
    assert (
        compact["official_task_score"]["kind"]
        == "skillsbench_verifier_bootstrap_reward_missing"
    ), compact

    reduced = compact_benchmark_run(compact)
    assert reduced is not None, compact
    assert reduced["score_failure_attribution"] == (
        "verifier_dependency_install_failure"
    ), reduced
    assert reduced["verifier_dependency_failure_count"] == 1, reduced


def test_pre_agent_package_install_risk_overrides_bridge_trace_missing() -> None:
    compact = _missing_score_compact()
    plan = _package_install_pre_agent_plan()
    compact.update(
        {
            "mode": "skillsbench_codex_cli_goal_baseline",
            "route": "codex-cli-goal-baseline",
            "task_id": "civ6-adjacency-optimizer",
            "score_failure_attribution": (
                "skillsbench_remote_bridge_agent_operation_trace_missing"
            ),
            "first_blocker": "skillsbench_remote_bridge_agent_operation_trace_missing",
            "failure_attribution_labels": [
                "skillsbench_remote_bridge_agent_operation_trace_missing",
                "skillsbench_product_mode_uncountable_treatment",
                "skillsbench_runner_setup_error",
            ],
            "task_staging": plan["task_staging"],
            "task_setup_preflight": plan["task_setup_preflight"],
            "attempt_accounting": {
                "schema_version": "skillsbench_attempt_accounting_v0",
                "attempt_lifecycle_phase": "not_started",
                "failure_class": "none",
                "failure_label": "not_run_adapter_skeleton",
            },
            "runner_failure": {
                "schema_version": "skillsbench_runner_failure_v0",
                "exception_type": "SkillsBenchSetupPreflightBlocked",
                "failure_class": (
                    "skillsbench_remote_bridge_agent_operation_trace_missing"
                ),
                "raw_error_recorded": False,
                "raw_logs_read": False,
                "raw_task_text_read": False,
                "raw_trajectory_read": False,
            },
        }
    )

    reduced = compact_benchmark_run(compact)

    assert reduced is not None, compact
    assert reduced["score_failure_attribution"] == (
        "verifier_dependency_install_failure"
    ), reduced
    assert reduced["first_blocker"] == "verifier_dependency_install_failure", reduced
    assert reduced["runner_failure"]["failure_class"] == (
        "verifier_dependency_install_failure"
    ), reduced
    assert reduced["attempt_accounting"]["failure_label"] == (
        "verifier_dependency_install_failure"
    ), reduced
    assert reduced["attempt_accounting"]["failure_class"] == (
        "job_materialization_failed"
    ), reduced
    assert "skillsbench_remote_bridge_agent_operation_trace_missing" not in reduced[
        "failure_attribution_labels"
    ], reduced
    assert "skillsbench_verifier_package_install_risk" in reduced[
        "failure_attribution_labels"
    ], reduced
    diagnostic = reduced["verifier_bootstrap_diagnostic"]
    assert diagnostic["pre_agent_setup_blocked"] is True, diagnostic
    assert diagnostic["verifier_package_install_risk_detected"] is True, diagnostic
    assert diagnostic["raw_logs_read"] is False, diagnostic
    assert diagnostic["raw_task_text_read"] is False, diagnostic
    assert diagnostic["raw_trajectory_read"] is False, diagnostic


def test_completed_score_is_not_reclassified_by_bootstrap_risk() -> None:
    compact = _missing_score_compact()
    plan = _uv_bootstrap_plan()
    compact.update(
        {
            "official_score_status": "completed",
            "official_score": 0.5,
            "official_task_score": {
                "kind": "skillsbench_verifier_reward",
                "value": 0.5,
                "passed": False,
            },
            "score_failure_attribution": "official_verifier_solution_failure",
            "failure_attribution_labels": ["official_verifier_solution_failure"],
        }
    )

    changed = apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        compact,
        task_staging=plan["task_staging"],
        setup_preflight=plan["task_setup_preflight"],
    )

    assert changed is False, compact
    assert compact["score_failure_attribution"] == (
        "official_verifier_solution_failure"
    ), compact
    assert "verifier_bootstrap_diagnostic" not in compact, compact


if __name__ == "__main__":
    test_missing_score_uv_bootstrap_risk_gets_verifier_dependency_attribution()
    test_pre_agent_package_install_risk_overrides_bridge_trace_missing()
    test_completed_score_is_not_reclassified_by_bootstrap_risk()
    print("skillsbench-verifier-bootstrap-missing-score-smoke: ok")
