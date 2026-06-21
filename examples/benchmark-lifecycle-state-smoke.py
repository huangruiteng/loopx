#!/usr/bin/env python3
"""Smoke-test compact benchmark lifecycle-state routing."""

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

from loopx.benchmark import (  # noqa: E402
    TERMINAL_BENCH_HARBOR_REF,
    build_benchmark_claim_review,
    build_benchmark_learning_ledger,
    build_benchmark_lifecycle_state,
    build_terminal_bench_result_finalization_gate,
    build_terminal_bench_environment_setup_probe_gate,
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preflight_ready() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_preflight_fixture_v0",
        "ready": True,
        "first_blocker": "ready_for_private_managed_no_upload_pilot_review",
    }


def wrapped_preflight_event() -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": "benchmark_run_append_preview_v0",
        "benchmark_run": {
            "schema_version": "benchmark_run_v0",
            "source_runner": "loopx_terminal_bench_preflight_fixture",
            "benchmark_id": "terminal-bench@2.0",
            "mode": "codex_loopx_active_cli_bridge_preflight",
            "real_run": False,
            "submit_eligible": False,
            "first_blocker": "ready_for_private_managed_no_upload_pilot_review",
            "preflight_guard": {
                "schema_version": "terminal_bench_codex_loopx_active_cli_bridge_preflight_v0",
                "first_blocker": "ready_for_private_managed_no_upload_pilot_review",
            },
            "private_runner_launch_summary": {
                "schema_version": "terminal_bench_private_runner_launch_summary_v0",
                "ready": True,
                "first_blocker": "ready_for_private_managed_no_upload_pilot_review",
                "task_material_ready": True,
            },
        },
    }


def launch_started(root: Path) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_launch_fixture_v0",
        "process_started": True,
        "pid": 12345,
        "private_job_dir": str(root / "private" / "jobs"),
    }


def materialization_missing() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": False,
        "ready_for_compact_result_ingest": False,
        "first_blocker": "job_root_missing",
        "jobs_dir_present": True,
        "job_root_present": False,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }


def materialization_ready() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": True,
        "ready_for_compact_result_ingest": True,
        "first_blocker": "ready_for_compact_result_ingest",
        "jobs_dir_present": True,
        "job_root_present": True,
        "job_lock_present": True,
        "job_result_present": True,
        "trial_result_present_count": 1,
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }


def materialization_stale_active_failure_marker() -> dict[str, Any]:
    return {
        "schema_version": "terminal_bench_post_launch_materialization_v0",
        "checked": True,
        "ready_for_launch_state": True,
        "ready_for_compact_result_ingest": False,
        "ready_for_compact_failure_marker": True,
        "first_blocker": "stale_active_job_without_trial_result",
        "job_name": "terminal_bench_multi_source_data_merger_codex_goal_mode_baseline",
        "jobs_dir_present": True,
        "job_root_present": True,
        "job_lock_present": True,
        "job_result_present": True,
        "job_active_without_trial_result": True,
        "job_stale_active_without_trial_result": True,
        "trial_result_present_count": 0,
        "external_handle_kind": "detached_worker_process",
        "external_handle_state": "ended",
        "external_handle_terminal": True,
        "compact_failure_class": "stale_active_job_without_trial_result",
        "compact_failure_marker": {
            "schema_version": "terminal_bench_compact_failure_marker_v0",
            "failure_class": "stale_active_job_without_trial_result",
            "evidence_kind": "compact_stale_active_job_reconciliation",
            "external_handle_kind": "detached_worker_process",
            "external_handle_state": "ended",
            "external_handle_terminal": True,
            "terminal_closeout": True,
            "terminal_state": "terminal_compact_failure",
            "lifecycle_stage": "result_finalization",
            "ledger_attempt_kind": "runner_closeout_attempt",
            "runner_attempt_countable": True,
            "launch_state_countable": True,
            "case_attempt_countable": False,
            "benchmark_budget_countable": False,
            "next_allowed_action": "repair_result_finalization_closeout_contract_before_rerun",
            "job_result_present": True,
            "trial_result_present_count": 0,
            "raw_paths_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
        },
        "raw_paths_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "trajectory_read": False,
    }


def materialization_ended_active_failure_marker() -> dict[str, Any]:
    payload = json.loads(json.dumps(materialization_stale_active_failure_marker()))
    payload["first_blocker"] = "detached_worker_ended_active_without_trial_result"
    payload["job_stale_active_without_trial_result"] = False
    payload["job_updated_age_seconds"] = 42.0
    payload["compact_failure_class"] = (
        "detached_worker_ended_active_without_trial_result"
    )
    marker = payload["compact_failure_marker"]
    marker["failure_class"] = "detached_worker_ended_active_without_trial_result"
    marker["evidence_kind"] = "detached_worker_active_job_without_trial_result"
    marker["job_updated_age_seconds"] = 42.0
    return payload


def benchmark_run(
    mode: str,
    score: float,
    *,
    failure_labels: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "benchmark_run_v0",
        "source_runner": "harbor",
        "benchmark_id": "terminal-bench@2.0",
        "job_name": f"terminal-bench-2-0-compact-fixture-{mode}",
        "mode": mode,
        "real_run": True,
        "submit_eligible": False,
        "leaderboard_evidence": False,
        "official_task_score": {
            "kind": "terminal_bench_verifier_reward",
            "value": score,
            "passed": score >= 1,
        },
        "failure_attribution_labels": failure_labels or [],
        "read_boundary": {
            "raw_artifacts_read": False,
            "task_text_read": False,
        },
    }


def environment_setup_failed_benchmark_run() -> dict[str, Any]:
    payload = benchmark_run("codex-loopx", 0.0)
    context = {
        "schema_version": "terminal_bench_environment_setup_failure_context_v0",
        "surface": "harbor_environment_setup",
        "failure_kind": "environment_setup_runtime_error_before_worker",
        "diagnostic_granularity": "phase_fields_only_no_raw_logs",
        "exception_type": "RuntimeError",
        "timeout_signal": "no_timeout_exception_type",
        "resource_signal": "not_observable_from_phase_fields",
        "environment_setup_duration_tier": "three_to_ten_minutes",
        "next_probe": "environment_setup_readiness_preflight_before_repeat",
        "environment_setup_present": True,
        "environment_setup_started": True,
        "environment_setup_finished": True,
        "agent_setup_started": False,
        "agent_execution_started": False,
        "worker_trace_present": False,
        "worker_benchmark_run_present": False,
        "environment_setup_duration_seconds": 211.0,
    }
    payload.update(
        {
            "first_blocker": "environment_setup_failed_before_worker",
            "repeat_blocked_by": "environment_setup_failed_before_worker",
            "worker_bridge_materialization_status": "environment_setup_failed_before_worker",
            "worker_bridge_materialization_blocker": "environment_setup_failed_before_worker",
            "environment_setup_failure_before_worker_count": 1,
            "environment_setup_failure_context": context,
            "trials": [
                {
                    "task_id": "pytorch-model-recovery",
                    "worker_start_status": "environment_setup_failed_before_worker",
                    "trajectory_present": False,
                    "trial_result_present": True,
                    "environment_setup_failure_context": context,
                }
            ],
        }
    )
    return payload


def environment_setup_probe_benchmark_run() -> dict[str, Any]:
    payload = benchmark_run("harbor_observed", 0.0)
    payload.update(
        {
            "worker_mode": "nop",
            "trials": [
                {
                    "task_id": "mteb-retrieve",
                    "worker_start_status": "environment_setup_probe_materialized",
                    "exception_type": "RuntimeError",
                    "trajectory_present": False,
                    "verifier_reward_present": False,
                    "artifact_manifest_present": True,
                    "trial_result_present": True,
                }
            ],
        }
    )
    return payload


def harbor_run_help_with_nop_probe_route() -> str:
    return """
Usage: harbor run [OPTIONS]

Options:
  --agent [oracle|nop|codex]
  --disable-verification / --enable-verification
  --env [docker|daytona]
  --upload
"""


def comparison() -> dict[str, Any]:
    return {
        "schema_version": "benchmark_comparison_v0",
        "task_id": "terminal-bench@2.0/compact-fixture",
        "comparison_id": "lifecycle-startup-failure",
        "benchmark_id": "terminal-bench@2.0",
        "baseline_scenario_id": "hardened-codex",
        "treatment_scenario_id": "codex-loopx",
        "official_task_score_delta": -1.0,
        "control_plane_score_delta": 0.0,
        "failure_attribution_labels": ["treatment_pre_worker_agent_setup_failed"],
        "claim_boundary": {
            "leaderboard_claim_allowed": False,
            "official_score_uplift_claim_allowed": False,
            "raw_trace_excluded": True,
        },
    }


def assert_no_private_surface(payload: dict[str, Any] | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
    forbidden = [
        "/" + "Users/",
        "/" + "tmp/",
        "private/jobs",
        "private_job_dir",
        "OPENAI" + "_API_KEY",
        "auth.json",
        "trajectory.json",
    ]
    leaked = [needle for needle in forbidden if needle in text]
    assert not leaked, leaked


def test_launched_process_without_materialization_is_not_countable() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-lifecycle-state-") as tmp:
        payload = build_benchmark_lifecycle_state(
            preflight=preflight_ready(),
            launch=launch_started(Path(tmp)),
            post_launch_materialization=materialization_missing(),
        )
    assert payload["current_phase"] == "launched_process", payload
    assert payload["first_blocker"] == "post_launch_materialization_missing", payload
    assert payload["gates"]["launch_state_countable"] is False, payload
    assert payload["gates"]["compact_result_ingest_allowed"] is False, payload
    assert payload["gates"]["budget_count_allowed"] is False, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
    assert_no_private_surface(payload)


def test_post_launch_failure_marker_waits_for_ledger_ingest() -> None:
    payload = build_benchmark_lifecycle_state(
        preflight=preflight_ready(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_stale_active_failure_marker(),
    )
    assert payload["current_phase"] == "compact_failure_marker_ready", payload
    assert payload["first_blocker"] == (
        "compact_failure_marker_ledger_ingest_required"
    ), payload
    assert payload["next_required_transition"] == (
        "compact_failure_marker_ledger_ingest"
    ), payload
    assert payload["gates"]["compact_result_ingest_allowed"] is False, payload
    assert payload["gates"]["compact_failure_marker_ready"] is True, payload
    assert payload["gates"]["terminal_closeout"] is True, payload
    assert payload["gates"]["case_attempt_countable"] is False, payload
    assert payload["gates"]["benchmark_budget_countable"] is False, payload
    assert payload["gates"]["budget_count_allowed"] is False, payload
    assert_no_private_surface(payload)


def test_terminal_bench_result_finalization_gate_blocks_until_repair() -> None:
    payload = build_terminal_bench_result_finalization_gate(
        materialization_stale_active_failure_marker()
    )
    assert payload["schema_version"] == "terminal_bench_result_finalization_gate_v0", payload
    assert payload["result_finalization_repair_required"] is True, payload
    assert payload["launch_materialization_repair_required"] is False, payload
    assert payload["repaired_baseline_rerun_allowed"] is False, payload
    assert payload["repair_class"] == "runner_result_finalization", payload
    assert payload["decision"] == "repair_result_finalization_before_rerun", payload
    assert payload["root_cause"] == (
        "harbor_job_left_active_after_detached_worker_ended_without_trial_result"
    ), payload
    assert payload["next_allowed_action"] == (
        "repair_result_finalization_closeout_contract_before_rerun"
    ), payload
    assert payload["gate_conditions"]["launch_state_countable"] is True, payload
    assert payload["gate_conditions"]["external_handle_terminal"] is True, payload
    assert payload["gate_conditions"]["no_trial_result"] is True, payload
    assert payload["gate_conditions"]["terminal_closeout"] is True, payload
    assert payload["gate_conditions"]["case_attempt_countable"] is False, payload
    assert payload["closeout_contract"]["ledger_attempt_kind"] == (
        "runner_closeout_attempt"
    ), payload
    assert payload["closeout_contract"]["benchmark_budget_countable"] is False, payload
    assert payload["rerun_constraints"]["baseline_only"] is True, payload
    assert payload["rerun_constraints"]["require_no_treatment_or_uplift_claim"] is True, payload
    assert payload["read_boundary"]["raw_artifacts_read"] is False, payload
    assert_no_private_surface(payload)


def test_terminal_bench_result_finalization_gate_accepts_ended_active_marker() -> None:
    payload = build_terminal_bench_result_finalization_gate(
        materialization_ended_active_failure_marker()
    )
    assert payload["result_finalization_repair_required"] is True, payload
    assert payload["launch_materialization_repair_required"] is False, payload
    assert payload["repaired_baseline_rerun_allowed"] is False, payload
    assert payload["repair_class"] == "runner_result_finalization", payload
    assert payload["decision"] == "repair_result_finalization_before_rerun", payload
    assert payload["root_cause"] == (
        "detached_worker_ended_while_harbor_job_remained_active_without_trial_result"
    ), payload
    assert payload["gate_conditions"]["terminal_closeout"] is True, payload
    assert payload["gate_conditions"]["case_attempt_countable"] is False, payload
    assert payload["gate_conditions"]["benchmark_budget_countable"] is False, payload
    lifecycle = build_benchmark_lifecycle_state(
        post_launch_materialization=materialization_ended_active_failure_marker()
    )
    assert lifecycle["current_phase"] == "compact_failure_marker_ready", lifecycle
    assert lifecycle["gates"]["terminal_closeout"] is True, lifecycle
    assert lifecycle["gates"]["case_attempt_countable"] is False, lifecycle
    assert lifecycle["gates"]["benchmark_budget_countable"] is False, lifecycle
    assert_no_private_surface(payload)
    assert_no_private_surface(lifecycle)

    blocked = build_terminal_bench_result_finalization_gate(
        materialization_ended_active_failure_marker(),
        max_repaired_baseline_reruns=0,
    )
    assert blocked["decision"] == "repair_result_finalization_before_rerun", blocked
    assert blocked["repaired_baseline_rerun_allowed"] is False, blocked
    assert blocked["root_cause"] == (
        "detached_worker_ended_while_harbor_job_remained_active_without_trial_result"
    ), blocked
    assert blocked["gate_conditions"]["case_attempt_countable"] is False, blocked
    assert_no_private_surface(blocked)


def test_budget_count_requires_compact_ledger_gate() -> None:
    baseline = benchmark_run("hardened-codex", 1.0)
    treatment = benchmark_run(
        "codex-loopx",
        0.0,
        failure_labels=["treatment_pre_worker_agent_setup_failed"],
    )
    paired = comparison()
    claim_review = build_benchmark_claim_review(
        paired,
        benchmark_runs=[baseline, treatment],
    )
    ledger = build_benchmark_learning_ledger(
        paired,
        benchmark_runs=[baseline, treatment],
    )
    without_ledger = build_benchmark_lifecycle_state(
        preflight=preflight_ready(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_ready(),
        benchmark_run=treatment,
        benchmark_comparison=paired,
        claim_review=claim_review,
    )
    assert without_ledger["first_blocker"] == "benchmark_learning_ledger_missing", without_ledger
    assert without_ledger["gates"]["budget_count_allowed"] is False, without_ledger

    with_ledger = build_benchmark_lifecycle_state(
        preflight=preflight_ready(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_ready(),
        benchmark_run=treatment,
        benchmark_comparison=paired,
        claim_review=claim_review,
        learning_ledger=ledger,
    )
    assert with_ledger["current_phase"] == "budget_counted", with_ledger
    assert with_ledger["first_blocker"] == "ready_for_budget_count", with_ledger
    assert with_ledger["gates"]["budget_count_allowed"] is True, with_ledger
    assert with_ledger["gates"]["new_candidate_allowed"] is False, with_ledger
    assert_no_private_surface(with_ledger)


def test_environment_setup_failure_blocks_same_task_repeat() -> None:
    payload = build_benchmark_lifecycle_state(
        preflight=wrapped_preflight_event(),
        benchmark_run=environment_setup_failed_benchmark_run(),
    )
    setup = payload["environment_setup_readiness_preflight"]
    assert payload["current_phase"] == "result_ingested", payload
    assert payload["next_required_transition"] == "environment_setup_repeat_cleared", payload
    assert payload["first_blocker"] == "environment_setup_readiness_preflight_required", payload
    assert payload["gates"]["environment_setup_repeat_allowed"] is False, payload
    assert payload["gates"]["repeat_allowed"] is False, payload
    assert setup["previous_failure_observed"] is True, payload
    assert setup["no_run_preflight_ready"] is True, payload
    assert setup["same_task_repeat_allowed"] is False, payload
    assert setup["next_allowed_action"] == (
        "run_setup_only_environment_preflight_or_select_new_material_ready_case"
    ), payload
    assert setup["read_boundary"]["raw_logs_read"] is False, payload
    assert setup["read_boundary"]["docker_logs_read"] is False, payload
    assert_no_private_surface(payload)


def test_environment_setup_probe_gate_allows_nop_probe_not_repeat() -> None:
    payload = build_terminal_bench_environment_setup_probe_gate(
        dataset="terminal-bench@2.0",
        task_id="pytorch-model-recovery",
        preflight=wrapped_preflight_event(),
        previous_benchmark_run=environment_setup_failed_benchmark_run(),
        harbor_run_help_text=harbor_run_help_with_nop_probe_route(),
    )
    capability = payload["harbor_run_help_capability"]
    contract = payload["probe_contract"]
    assert payload["environment_setup_probe_allowed"] is True, payload
    assert payload["nop_disable_verification_probe_allowed"] is True, payload
    assert payload["direct_setup_only_route_allowed"] is False, payload
    assert payload["same_task_repeat_allowed"] is False, payload
    assert payload["next_allowed_action"] == (
        "run_nop_disable_verification_environment_setup_probe"
    ), payload
    assert capability["raw_help_recorded"] is False, payload
    assert payload["probe_command_template"][2] == TERMINAL_BENCH_HARBOR_REF, payload
    assert "harbor@pinned" not in payload["probe_command_template"], payload
    assert contract["agent"] == "nop", payload
    assert contract["codex_invoked"] is False, payload
    assert contract["verifier_disabled"] is True, payload
    assert contract["no_upload"] is True, payload
    assert contract["submit_eligible"] is False, payload
    assert_no_private_surface(payload)


def test_environment_setup_probe_result_is_lifecycle_terminal_for_probe() -> None:
    payload = build_benchmark_lifecycle_state(
        preflight=wrapped_preflight_event(),
        launch={"schema_version": "benchmark_launch_fixture_v0", "process_started": True},
        post_launch_materialization=materialization_ready(),
        benchmark_run=environment_setup_probe_benchmark_run(),
    )
    probe = payload["environment_setup_probe_result"]
    assert payload["current_phase"] == "environment_setup_probe_completed", payload
    assert payload["next_required_transition"] == "case_repeat_decision", payload
    assert payload["first_blocker"] == (
        "environment_setup_probe_exception_requires_interpretation"
    ), payload
    assert payload["gates"]["environment_setup_probe_completed"] is True, payload
    assert payload["gates"]["case_attempt_countable"] is False, payload
    assert payload["gates"]["benchmark_budget_countable"] is False, payload
    assert payload["gates"]["repeat_allowed"] is False, payload
    assert probe["task_id"] == "mteb-retrieve", payload
    assert probe["probe_materialized"] is True, payload
    assert probe["exception_present"] is True, payload
    assert probe["probe_outcome"] == "materialized_with_exception", payload
    assert probe["repeat_blocked_by"] == (
        "environment_setup_probe_exception_requires_interpretation"
    ), payload
    assert probe["next_allowed_action"] == (
        "classify_environment_setup_probe_exception_before_same_task_repeat"
    ), payload
    assert probe["same_task_repeat_allowed"] is False, payload
    assert probe["read_boundary"]["raw_logs_read"] is False, payload
    assert_no_private_surface(payload)


def test_cli_lifecycle_state_budget_gate() -> None:
    with tempfile.TemporaryDirectory(prefix="benchmark-lifecycle-state-cli-") as tmp:
        root = Path(tmp)
        preflight_path = root / "preflight.json"
        launch_path = root / "launch.json"
        missing_path = root / "post_launch_missing.json"
        ready_path = root / "post_launch_ready.json"
        run_path = root / "run.json"
        finalization_path = root / "post_launch_finalization.json"
        setup_failure_path = root / "setup_failure_run.json"
        setup_probe_path = root / "setup_probe_run.json"
        comparison_path = root / "comparison.json"
        claim_path = root / "claim_review.json"
        ledger_path = root / "ledger.json"

        baseline = benchmark_run("hardened-codex", 1.0)
        treatment = benchmark_run(
            "codex-loopx",
            0.0,
            failure_labels=["treatment_pre_worker_agent_setup_failed"],
        )
        paired = comparison()
        claim_review = build_benchmark_claim_review(
            paired,
            benchmark_runs=[baseline, treatment],
        )
        ledger = build_benchmark_learning_ledger(
            paired,
            benchmark_runs=[baseline, treatment],
        )

        write_json(preflight_path, preflight_ready())
        write_json(launch_path, launch_started(root))
        write_json(missing_path, materialization_missing())
        write_json(ready_path, materialization_ready())
        write_json(finalization_path, materialization_stale_active_failure_marker())
        write_json(run_path, treatment)
        write_json(setup_failure_path, environment_setup_failed_benchmark_run())
        write_json(setup_probe_path, environment_setup_probe_benchmark_run())
        write_json(comparison_path, paired)
        write_json(claim_path, claim_review)
        write_json(ledger_path, ledger)

        blocked = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--launch-json",
                str(launch_path),
                "--post-launch-json",
                str(missing_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        blocked_payload = json.loads(blocked.stdout)
        assert blocked.returncode == 1, blocked.stdout
        assert blocked_payload["ok"] is False, blocked_payload
        assert blocked_payload["first_blocker"] == "post_launch_materialization_missing", blocked_payload
        assert blocked_payload["gates"]["budget_count_allowed"] is False, blocked_payload
        assert_no_private_surface(blocked.stdout)

        allowed = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--launch-json",
                str(launch_path),
                "--post-launch-json",
                str(ready_path),
                "--benchmark-run-json",
                str(run_path),
                "--benchmark-comparison-json",
                str(comparison_path),
                "--claim-review-json",
                str(claim_path),
                "--benchmark-learning-ledger-json",
                str(ledger_path),
                "--require-budget-count-allowed",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        allowed_payload = json.loads(allowed.stdout)
        assert allowed_payload["ok"] is True, allowed_payload
        assert allowed_payload["current_phase"] == "budget_counted", allowed_payload
        assert allowed_payload["gates"]["budget_count_allowed"] is True, allowed_payload
        assert_no_private_surface(allowed.stdout)

        setup_blocked = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--benchmark-run-json",
                str(setup_failure_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        setup_payload = json.loads(setup_blocked.stdout)
        assert setup_payload["ok"] is True, setup_payload
        assert setup_payload["first_blocker"] == (
            "environment_setup_readiness_preflight_required"
        ), setup_payload
        assert setup_payload["next_required_transition"] == (
            "environment_setup_repeat_cleared"
        ), setup_payload
        assert setup_payload["gates"]["environment_setup_repeat_allowed"] is False, setup_payload
        assert setup_payload["environment_setup_readiness_preflight"]["task_id"] == (
            "pytorch-model-recovery"
        ), setup_payload
        assert_no_private_surface(setup_blocked.stdout)

        setup_probe = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "lifecycle-state",
                "--preflight-json",
                str(preflight_path),
                "--launch-json",
                str(launch_path),
                "--post-launch-json",
                str(ready_path),
                "--benchmark-run-json",
                str(setup_probe_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        setup_probe_payload = json.loads(setup_probe.stdout)
        assert setup_probe_payload["current_phase"] == (
            "environment_setup_probe_completed"
        ), setup_probe_payload
        assert setup_probe_payload["next_required_transition"] == (
            "case_repeat_decision"
        ), setup_probe_payload
        assert setup_probe_payload["first_blocker"] == (
            "environment_setup_probe_exception_requires_interpretation"
        ), setup_probe_payload
        assert setup_probe_payload["gates"]["environment_setup_probe_completed"] is True, (
            setup_probe_payload
        )
        assert setup_probe_payload["environment_setup_probe_result"][
            "probe_outcome"
        ] == "materialized_with_exception", setup_probe_payload
        assert_no_private_surface(setup_probe.stdout)

        setup_gate = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "environment-setup-gate",
                "terminal-bench",
                "--include-task-name",
                "pytorch-model-recovery",
                "--preflight-json",
                str(preflight_path),
                "--benchmark-run-json",
                str(setup_failure_path),
                "--harbor-run-help-text",
                harbor_run_help_with_nop_probe_route(),
                "--require-probe-allowed",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        setup_gate_payload = json.loads(setup_gate.stdout)
        assert setup_gate_payload["ok"] is True, setup_gate_payload
        assert setup_gate_payload["environment_setup_probe_allowed"] is True, setup_gate_payload
        assert setup_gate_payload["same_task_repeat_allowed"] is False, setup_gate_payload
        assert setup_gate_payload["probe_command_template"][2] == TERMINAL_BENCH_HARBOR_REF, setup_gate_payload
        assert setup_gate_payload["probe_contract"]["agent"] == "nop", setup_gate_payload
        assert setup_gate_payload["read_boundary"]["raw_help_recorded"] is False, setup_gate_payload
        assert_no_private_surface(setup_gate.stdout)

        finalization_gate = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "result-finalization-gate",
                "terminal-bench",
                "--post-launch-json",
                str(finalization_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        finalization_payload = json.loads(finalization_gate.stdout)
        assert finalization_payload["ok"] is True, finalization_payload
        assert finalization_payload["repaired_baseline_rerun_allowed"] is False, finalization_payload
        assert finalization_payload["decision"] == (
            "repair_result_finalization_before_rerun"
        ), finalization_payload
        assert finalization_payload["repair_class"] == (
            "runner_result_finalization"
        ), finalization_payload
        assert finalization_payload["gate_conditions"]["no_trial_result"] is True, finalization_payload
        assert finalization_payload["gate_conditions"]["terminal_closeout"] is True, finalization_payload
        assert finalization_payload["closeout_contract"]["ledger_attempt_kind"] == (
            "runner_closeout_attempt"
        ), finalization_payload
        assert finalization_payload["read_boundary"]["raw_artifacts_read"] is False, finalization_payload
        assert_no_private_surface(finalization_gate.stdout)

        required_finalization_gate = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "result-finalization-gate",
                "terminal-bench",
                "--post-launch-json",
                str(finalization_path),
                "--require-rerun-allowed",
            ],
            cwd=REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        assert required_finalization_gate.returncode != 0, (
            required_finalization_gate.stdout
            + required_finalization_gate.stderr
        )
        required_payload = json.loads(required_finalization_gate.stdout)
        assert required_payload["ok"] is False, required_payload
        assert required_payload["error"] == (
            "result_finalization_repair_required_before_rerun"
        ), required_payload
        assert required_payload["repaired_baseline_rerun_allowed"] is False, (
            required_payload
        )
        assert_no_private_surface(required_finalization_gate.stdout)

        blocked_finalization_gate = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "--format",
                "json",
                "benchmark",
                "result-finalization-gate",
                "terminal-bench",
                "--post-launch-json",
                str(finalization_path),
                "--max-repaired-baseline-reruns",
                "0",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        blocked_finalization_payload = json.loads(blocked_finalization_gate.stdout)
        assert blocked_finalization_payload["decision"] == (
            "repair_result_finalization_before_rerun"
        ), blocked_finalization_payload
        assert blocked_finalization_payload["repaired_baseline_rerun_allowed"] is False, blocked_finalization_payload
        assert blocked_finalization_payload["next_allowed_action"] == (
            "repair_result_finalization_closeout_contract_before_rerun"
        ), blocked_finalization_payload
        assert blocked_finalization_payload["closeout_contract"]["terminal_closeout"] is True, blocked_finalization_payload
        assert_no_private_surface(blocked_finalization_gate.stdout)


def main() -> int:
    test_launched_process_without_materialization_is_not_countable()
    test_post_launch_failure_marker_waits_for_ledger_ingest()
    test_terminal_bench_result_finalization_gate_blocks_until_repair()
    test_terminal_bench_result_finalization_gate_accepts_ended_active_marker()
    test_budget_count_requires_compact_ledger_gate()
    test_environment_setup_failure_blocks_same_task_repeat()
    test_environment_setup_probe_gate_allows_nop_probe_not_repeat()
    test_environment_setup_probe_result_is_lifecycle_terminal_for_probe()
    test_cli_lifecycle_state_budget_gate()
    print("benchmark-lifecycle-state-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
