#!/usr/bin/env python3
"""Reduce Terminal-Bench startup/materialization evidence into a compact blocker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.terminal_bench import (  # noqa: E402
    build_terminal_bench_result_finalization_gate,
    summarize_terminal_bench_post_launch_materialization,
)
from loopx.benchmark_core.io import load_json_object  # noqa: E402


STARTUP_BLOCKER_CLASSES = {
    "jobs_dir_missing",
    "job_root_missing",
    "job_lock_missing",
    "detached_worker_ended_without_jobs_dir",
    "detached_worker_ended_without_job_root",
    "detached_worker_ended_without_trial_result",
    "detached_worker_ended_active_without_trial_result",
    "stale_active_job_without_trial_result",
}

POST_LAUNCH_PUBLIC_FIELDS = (
    "schema_version",
    "checked",
    "ready_for_launch_state",
    "ready_for_compact_result_ingest",
    "ready_for_compact_failure_marker",
    "first_blocker",
    "job_name",
    "jobs_dir_present",
    "job_root_present",
    "job_lock_present",
    "job_result_present",
    "job_result_finished",
    "job_result_updated_at_present",
    "job_updated_age_seconds",
    "job_active_stale_seconds_threshold",
    "job_running_trial_count",
    "job_pending_trial_count",
    "job_active_without_trial_result",
    "job_stale_active_without_trial_result",
    "trial_result_present_count",
    "candidate_job_root_count",
    "worker_materialization_probe_only",
    "probe_contract_result_present",
    "external_handle_kind",
    "external_handle_state",
    "external_handle_observed",
    "external_handle_terminal",
    "compact_failure_class",
    "compact_monitor_class",
    "next_observation_action",
    "resume_recommended",
    "active_job_resume_contract",
    "raw_paths_recorded",
    "raw_logs_read",
    "raw_task_text_read",
    "trajectory_read",
    "raw_external_handle_payload_recorded",
    "stale_active_reconcile_requested",
)

COMPOSE_SETUP_PUBLIC_FIELDS = (
    "schema_version",
    "status",
    "route",
    "failure_class",
    "runner_prerequisite_status",
    "task_setup_preflight_status",
    "runner_error_len_bucket",
    "next_diagnostic_action",
    "compose_setup_failure",
    "unclassified_compose_failure",
    "docker_daemon_unavailable",
    "volume_mount_failure",
    "environment_setup_failure",
    "agent_rounds_started",
    "official_score_missing",
    "official_result_json_materialized",
    "case_attempt_budget_should_count",
    "runner_launch_preflight_passed",
    "apt_setup_risk_detected",
    "apt_retry_patch_required",
    "staged_task_prepared",
    "task_skills_removed",
    "codex_acp_runtime_tools_patch_applied",
    "resource_cap_applied",
    "raw_error_recorded",
    "raw_logs_read",
    "raw_task_text_read",
    "raw_trajectory_read",
)

NO_REBUILD_GUARD_PUBLIC_FIELDS = (
    "schema_version",
    "ok",
    "first_blocker",
    "private_root_recorded",
    "apply",
    "manager_file_count",
    "patched_file_count",
)

TASK_IMAGE_BOOTSTRAP_PUBLIC_FIELDS = (
    "schema_version",
    "ok",
    "first_blocker",
    "execute",
    "private_work_dir_recorded",
    "apt_packages",
    "required_commands",
    "apt_mirror_host",
    "security_mirror_host",
    "use_host_network",
    "timeout_sec",
    "build_returncode",
    "command_checks",
)


def _load_optional_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    return load_json_object(Path(path))


def _compact_fields(value: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: value[field] for field in fields if field in value}


def _compact_boundary(value: dict[str, Any]) -> dict[str, bool]:
    boundary = value.get("boundary")
    if not isinstance(boundary, dict):
        boundary = value
    return {
        "raw_logs_read": boundary.get("raw_logs_read") is True,
        "raw_task_text_read": boundary.get("raw_task_text_read") is True,
        "trajectory_read": boundary.get("trajectory_read") is True,
        "raw_trajectory_read": boundary.get("raw_trajectory_read") is True,
        "credential_values_read": boundary.get("credential_values_read") is True,
        "private_paths_recorded": boundary.get("private_paths_recorded") is True,
    }


def _compact_compose_setup(value: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_fields(value, COMPOSE_SETUP_PUBLIC_FIELDS)
    if compact:
        compact["boundary"] = _compact_boundary(value)
    return compact


def _compact_no_rebuild_guard(value: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_fields(value, NO_REBUILD_GUARD_PUBLIC_FIELDS)
    contract = value.get("contract")
    if isinstance(contract, dict):
        compact["contract"] = {
            "no_rebuild_implies_compose_no_build": (
                contract.get("no_rebuild_implies_compose_no_build") is True
            ),
            "score_or_task_behavior_changed": (
                contract.get("score_or_task_behavior_changed") is True
            ),
            "runner_surface_changed": contract.get("runner_surface_changed", ""),
        }
    files = value.get("files")
    if isinstance(files, list):
        compact["file_statuses"] = [
            {
                "status": file.get("status", ""),
                "patchable": file.get("patchable") is True,
                "patched": file.get("patched") is True,
            }
            for file in files
            if isinstance(file, dict)
        ][:8]
    if compact:
        compact["boundary"] = _compact_boundary(value)
    return compact


def _compact_task_image_bootstrap(value: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_fields(value, TASK_IMAGE_BOOTSTRAP_PUBLIC_FIELDS)
    contract = value.get("contract")
    if isinstance(contract, dict):
        compact["contract"] = {
            "score_or_task_behavior_changed": (
                contract.get("score_or_task_behavior_changed") is True
            ),
            "runner_surface_changed": contract.get("runner_surface_changed", ""),
            "case_runtime_agent_install_forbidden": (
                contract.get("case_runtime_agent_install_forbidden") is True
            ),
        }
    if compact:
        compact["boundary"] = _compact_boundary(value)
    return compact


def _compact_post_launch(post_launch: dict[str, Any]) -> dict[str, Any]:
    compact = {
        field: post_launch[field]
        for field in POST_LAUNCH_PUBLIC_FIELDS
        if field in post_launch
    }
    marker = post_launch.get("compact_failure_marker")
    if isinstance(marker, dict):
        compact["compact_failure_marker"] = {
            key: value
            for key, value in marker.items()
            if key
            in {
                "failure_class",
                "evidence_kind",
                "external_handle_state",
                "launch_state_countable",
                "job_result_present",
                "job_result_finished",
                "job_running_trial_count",
                "job_pending_trial_count",
                "job_result_updated_at_present",
                "job_updated_age_seconds",
                "job_active_stale_seconds_threshold",
                "trial_result_present_count",
                "worker_materialization_probe_only",
                "probe_contract_result_present",
                "case_attempt_countable",
                "ledger_attempt_kind",
                "terminal_closeout",
                "next_allowed_action",
            }
        }
    return compact


def _reason_codes(
    *,
    compact_post_launch: dict[str, Any],
    compose_setup: dict[str, Any],
    no_rebuild_guard: dict[str, Any],
    task_image_bootstrap: dict[str, Any],
    compose_startup_blocker: bool,
) -> list[str]:
    reasons: list[str] = []
    if compact_post_launch:
        reasons.append("post_launch_materialization_present")
    if compose_setup:
        reasons.append("compose_setup_diagnostic_present")
    if compose_setup.get("apt_retry_patch_required") is True:
        reasons.append("apt_retry_patch_required")
    if compose_setup.get("apt_setup_risk_detected") is True:
        reasons.append("apt_setup_risk_detected")
    if no_rebuild_guard:
        reasons.append("no_rebuild_guard_diagnostic_present")
    if no_rebuild_guard.get("first_blocker"):
        reasons.append(str(no_rebuild_guard["first_blocker"]))
    elif no_rebuild_guard.get("ok") is True:
        reasons.append("no_rebuild_guard_ready")
    if task_image_bootstrap:
        reasons.append("fast_mirror_bootstrap_diagnostic_present")
    if task_image_bootstrap.get("first_blocker"):
        reasons.append(str(task_image_bootstrap["first_blocker"]))
    elif task_image_bootstrap.get("ok") is True:
        reasons.append("fast_mirror_bootstrap_fallback_available")
    if compose_startup_blocker:
        reasons.append("post_launch_compose_startup_blocker")
    return reasons


def _build_cause_fix_decision(
    *,
    compact_post_launch: dict[str, Any],
    compose_setup: dict[str, Any],
    no_rebuild_guard: dict[str, Any],
    task_image_bootstrap: dict[str, Any],
    compose_startup_blocker: bool,
    base_next_action: str,
) -> dict[str, Any]:
    reason_codes = _reason_codes(
        compact_post_launch=compact_post_launch,
        compose_setup=compose_setup,
        no_rebuild_guard=no_rebuild_guard,
        task_image_bootstrap=task_image_bootstrap,
        compose_startup_blocker=compose_startup_blocker,
    )
    classification = "continue_compact_observation"
    next_action = base_next_action

    if compact_post_launch.get("ready_for_compact_result_ingest") is True:
        classification = "compact_result_ready"
        next_action = "ingest_compact_terminal_bench_result"
    elif no_rebuild_guard.get("first_blocker"):
        classification = "no_rebuild_guard_blocker"
        next_action = "apply_terminal_bench_no_rebuild_guard"
    elif task_image_bootstrap.get("first_blocker"):
        classification = "fast_mirror_bootstrap_blocker"
        next_action = "repair_terminal_bench_fast_mirror_bootstrap"
    elif (
        compose_setup.get("apt_retry_patch_required") is True
        or compose_setup.get("apt_setup_risk_detected") is True
    ):
        classification = "fast_mirror_bootstrap_recommended"
        next_action = "run_terminal_bench_fast_mirror_task_image_bootstrap"
    elif compose_setup.get("compose_setup_failure") is True:
        classification = str(
            compose_setup.get("failure_class") or "compose_setup_failure"
        )
        next_action = str(
            compose_setup.get("next_diagnostic_action")
            or "repair_terminal_bench_compose_setup"
        )
    elif compose_startup_blocker:
        classification = "post_launch_compose_startup_blocker"
        next_action = "repair_terminal_bench_compose_startup"
    elif compact_post_launch.get("resume_recommended") is True:
        classification = "resume_or_poll_materialized_job"
        next_action = "resume_or_poll_materialized_job"

    return {
        "schema_version": "terminal_bench_compose_cause_fix_decision_v0",
        "classification": classification,
        "next_action": next_action,
        "reason_codes": reason_codes,
        "checked_surfaces": {
            "post_launch_materialization": bool(compact_post_launch),
            "compose_setup_diagnostic": bool(compose_setup),
            "no_rebuild_guard": bool(no_rebuild_guard),
            "fast_mirror_task_image_bootstrap": bool(task_image_bootstrap),
        },
    }


def _load_post_launch(args: argparse.Namespace) -> dict[str, Any]:
    if args.post_launch_json:
        return load_json_object(Path(args.post_launch_json))
    if not args.jobs_dir:
        return {}
    return summarize_terminal_bench_post_launch_materialization(
        args.jobs_dir,
        job_name=args.job_name,
        detached_process_state=args.detached_process_state,
        reconcile_stale_active=args.reconcile_stale_active,
    )


def build_reduction(args: argparse.Namespace) -> dict[str, Any]:
    post_launch = _load_post_launch(args)
    compact_post_launch = _compact_post_launch(post_launch)
    compose_setup = _compact_compose_setup(_load_optional_json(args.compose_setup_json))
    no_rebuild_guard = _compact_no_rebuild_guard(
        _load_optional_json(args.no_rebuild_guard_json)
    )
    task_image_bootstrap = _compact_task_image_bootstrap(
        _load_optional_json(args.task_image_bootstrap_json)
    )
    failure_class = str(
        compact_post_launch.get("compact_failure_class")
        or compact_post_launch.get("first_blocker")
        or ""
    )
    finalization_gate = build_terminal_bench_result_finalization_gate(post_launch)
    compose_startup_blocker = failure_class in STARTUP_BLOCKER_CLASSES
    if compact_post_launch.get("ready_for_compact_result_ingest") is True:
        next_action = "ingest_compact_terminal_bench_result"
    elif compact_post_launch.get("resume_recommended") is True:
        next_action = "resume_or_poll_materialized_job"
    elif compose_startup_blocker:
        next_action = "repair_terminal_bench_compose_startup"
    else:
        next_action = "continue_compact_observation"
    cause_fix_decision = _build_cause_fix_decision(
        compact_post_launch=compact_post_launch,
        compose_setup=compose_setup,
        no_rebuild_guard=no_rebuild_guard,
        task_image_bootstrap=task_image_bootstrap,
        compose_startup_blocker=compose_startup_blocker,
        base_next_action=next_action,
    )
    evidence_surfaces = [
        name
        for name, present in {
            "post_launch_json": bool(args.post_launch_json),
            "jobs_dir_summary": bool(args.jobs_dir),
            "compose_setup_json": bool(args.compose_setup_json),
            "no_rebuild_guard_json": bool(args.no_rebuild_guard_json),
            "task_image_bootstrap_json": bool(args.task_image_bootstrap_json),
        }.items()
        if present
    ]

    return {
        "schema_version": "terminal_bench_compose_startup_reducer_v0",
        "ok": bool(
            post_launch or compose_setup or no_rebuild_guard or task_image_bootstrap
        ),
        "input_surface": (
            "post_launch_json"
            if args.post_launch_json
            else "jobs_dir_summary"
            if args.jobs_dir
            else "compact_diagnostics"
        ),
        "evidence_surfaces": evidence_surfaces,
        "compose_startup_blocker": compose_startup_blocker,
        "blocker_class": failure_class,
        "next_action": cause_fix_decision["next_action"],
        "ready_for_compact_result_ingest": (
            compact_post_launch.get("ready_for_compact_result_ingest") is True
        ),
        "ready_for_compact_failure_marker": (
            compact_post_launch.get("ready_for_compact_failure_marker") is True
        ),
        "post_launch_materialization": compact_post_launch,
        "compose_setup_diagnostic": compose_setup,
        "no_rebuild_guard": no_rebuild_guard,
        "task_image_bootstrap": task_image_bootstrap,
        "cause_fix_decision": cause_fix_decision,
        "result_finalization_gate": finalization_gate,
        "boundary": {
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "credential_values_read": False,
            "private_paths_recorded": False,
            "command_argv_recorded": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Reduce Terminal-Bench launch/materialization state into a compact "
            "startup blocker or result-ingest action without reading raw logs."
        )
    )
    parser.add_argument("--post-launch-json")
    parser.add_argument("--compose-setup-json")
    parser.add_argument("--no-rebuild-guard-json")
    parser.add_argument("--task-image-bootstrap-json")
    parser.add_argument("--jobs-dir")
    parser.add_argument("--job-name")
    parser.add_argument(
        "--detached-process-state",
        choices=("unknown", "running", "ended"),
        default="unknown",
    )
    parser.add_argument("--reconcile-stale-active", action="store_true")
    parser.add_argument("--output-json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    if not any(
        (
            args.post_launch_json,
            args.jobs_dir,
            args.compose_setup_json,
            args.no_rebuild_guard_json,
            args.task_image_bootstrap_json,
        )
    ):
        parser.error(
            "provide at least one of --post-launch-json, --jobs-dir, "
            "--compose-setup-json, --no-rebuild-guard-json, or "
            "--task-image-bootstrap-json"
        )

    payload = build_reduction(args)
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
