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

    return {
        "schema_version": "terminal_bench_compose_startup_reducer_v0",
        "ok": bool(post_launch),
        "input_surface": (
            "post_launch_json" if args.post_launch_json else "jobs_dir_summary"
        ),
        "compose_startup_blocker": compose_startup_blocker,
        "blocker_class": failure_class,
        "next_action": next_action,
        "ready_for_compact_result_ingest": (
            compact_post_launch.get("ready_for_compact_result_ingest") is True
        ),
        "ready_for_compact_failure_marker": (
            compact_post_launch.get("ready_for_compact_failure_marker") is True
        ),
        "post_launch_materialization": compact_post_launch,
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

    if not args.post_launch_json and not args.jobs_dir:
        parser.error("provide --post-launch-json or --jobs-dir")

    payload = build_reduction(args)
    rendered = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output_json:
        Path(args.output_json).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
