from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Mapping


BENCHMARK_OBSERVABLE_HANDLE_POLICY_SCHEMA_VERSION = (
    "benchmark_observable_handle_policy_v0"
)
BENCHMARK_LAUNCH_OBSERVABLE_HANDLE_SCHEMA_VERSION = (
    "benchmark_launch_observable_handle_v0"
)


_DEFAULT_LAUNCH_READ_BOUNDARY = {
    "compact_only": True,
    "raw_logs_read": False,
    "raw_task_text_read": False,
    "raw_artifacts_read": False,
    "trajectory_read": False,
    "local_paths_recorded": False,
    "private_handle_values_recorded": False,
    "scheduler_payload_recorded": False,
}

_LAUNCH_PROCESS_STATES = {
    "not_started",
    "queued",
    "starting",
    "running",
    "ended",
    "missing",
    "not_found",
    "unknown",
}


def _public_safe_label(value: Any, *, fallback: str = "", limit: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    text = text.replace("\\", "/").split("/")[-1]
    text = re.sub(r"[^A-Za-z0-9._:-]+", "-", text).strip("-._:")
    if not text:
        return fallback
    return text[:limit]


def _public_safe_ref_items(values: Any, *, limit: int = 12) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        items = [values]
    else:
        try:
            items = list(values)
        except TypeError:
            items = [values]
    safe_items: list[str] = []
    for item in items:
        safe = _public_safe_label(item, limit=160)
        if safe and safe not in safe_items:
            safe_items.append(safe)
        if len(safe_items) >= limit:
            break
    return safe_items


def _launch_read_boundary(read_boundary: Mapping[str, Any] | None) -> dict[str, bool]:
    boundary = dict(_DEFAULT_LAUNCH_READ_BOUNDARY)
    if not isinstance(read_boundary, Mapping):
        return boundary
    if read_boundary.get("task_text_read") is True:
        boundary["raw_task_text_read"] = True
    if read_boundary.get("raw_logs_read") is True:
        boundary["raw_logs_read"] = True
    if read_boundary.get("raw_artifacts_read") is True:
        boundary["raw_artifacts_read"] = True
    if read_boundary.get("trajectory_read") is True:
        boundary["trajectory_read"] = True
    if read_boundary.get("local_paths_recorded") is True:
        boundary["local_paths_recorded"] = True
    if read_boundary.get("private_handle_values_recorded") is True:
        boundary["private_handle_values_recorded"] = True
    if read_boundary.get("compact_only") is False:
        boundary["compact_only"] = False
    return boundary


def build_benchmark_launch_observable_handle(
    *,
    benchmark_id: str,
    launch_mode: str,
    run_label: str | None = None,
    job_basename: str | None = None,
    process_state: str = "not_started",
    pid_recorded: bool = False,
    pid_alive: bool | None = None,
    compact_artifact_refs: Any = None,
    allowed_poll_command: str = "benchmark_run_status_snapshot",
    scheduler_kind: str = "manual",
    will_execute: bool = False,
    read_boundary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return public-safe launch handle metadata for benchmark artifacts.

    Launch artifacts should expose enough shape for a heartbeat or developer to
    poll the run without preserving raw scheduler payloads, shell argv, local
    paths, logs, task text, trajectories, or private handle values.
    """

    state = _public_safe_label(process_state, fallback="unknown", limit=40)
    if state not in _LAUNCH_PROCESS_STATES:
        state = "unknown"
    safe_job_basename = _public_safe_label(job_basename or run_label, limit=160)
    safe_run_label = _public_safe_label(run_label or safe_job_basename, limit=160)
    poll_label = _public_safe_label(
        allowed_poll_command,
        fallback="benchmark_run_status_snapshot",
        limit=120,
    )
    refs = _public_safe_ref_items(compact_artifact_refs)
    monitor_poll_allowed = will_execute is True and state in {
        "queued",
        "starting",
        "running",
    }
    return {
        "schema_version": BENCHMARK_LAUNCH_OBSERVABLE_HANDLE_SCHEMA_VERSION,
        "benchmark_id": _public_safe_label(benchmark_id, fallback="benchmark", limit=80),
        "launch_mode": _public_safe_label(launch_mode, fallback="unknown", limit=80),
        "scheduler_kind": _public_safe_label(scheduler_kind, fallback="manual", limit=80),
        "will_execute": will_execute is True,
        "observable_handle": {
            "kind": "pid_file" if pid_recorded else "job_basename",
            "state": state,
            "run_label": safe_run_label,
            "job_basename": safe_job_basename,
            "pid_recorded": pid_recorded is True,
            "pid_alive": pid_alive if isinstance(pid_alive, bool) else None,
            "raw_handle_payload_recorded": False,
            "private_handle_values_recorded": False,
        },
        "compact_artifact_refs": refs,
        "compact_artifact_ref_count": len(refs),
        "allowed_poll_command": {
            "command_label": poll_label,
            "argv_recorded": False,
            "raw_command_recorded": False,
            "requires_private_paths": False,
        },
        "monitor_poll_allowed": monitor_poll_allowed,
        "read_boundary": _launch_read_boundary(read_boundary),
        "boundary": {
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "raw_trajectory_recorded": False,
            "local_paths_recorded": False,
            "scheduler_payload_recorded": False,
            "credential_values_recorded": False,
        },
    }


_RESULT_CLOSEOUT_STATUS_VALUES = {
    "completed",
    "complete",
    "passed",
    "failed",
    "scored",
    "score_ready",
}


def write_benchmark_run_observable_status(
    *,
    jobs_dir: Any,
    job_name: Any,
    status: str,
    record_pid: bool = False,
) -> None:
    """Write compact run-handle files used by public-safe status snapshots."""

    jobs_dir_text = str(jobs_dir or "").strip()
    job_name_text = str(job_name or "").strip()
    if not jobs_dir_text or not job_name_text:
        return
    try:
        job_dir = Path(jobs_dir_text).expanduser() / job_name_text
        job_dir.mkdir(parents=True, exist_ok=True)
        safe_status = re.sub(r"[^A-Za-z0-9_.=:-]+", "-", str(status).strip())
        (job_dir / "status.env").write_text(
            (safe_status or "unknown") + "\n",
            encoding="utf-8",
        )
        if record_pid:
            (job_dir / "pid.private").write_text(
                f"{os.getpid()}\n",
                encoding="utf-8",
            )
    except OSError:
        return


def _summary_items(run_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    compact_results = run_snapshot.get("compact_results")
    if not isinstance(compact_results, list):
        return items
    for result in compact_results:
        if not isinstance(result, Mapping):
            continue
        summary = result.get("summary")
        if isinstance(summary, Mapping):
            items.append(dict(summary))
    return items


def _has_compact_result_closeout(summary: Mapping[str, Any]) -> bool:
    status = str(summary.get("official_score_status") or "").strip().lower()
    if status in _RESULT_CLOSEOUT_STATUS_VALUES:
        return True
    for field in (
        "official_score",
        "official_task_score",
        "accuracy",
        "n_resolved",
        "n_unresolved",
    ):
        if summary.get(field) is not None:
            return True
    return False


def _has_compact_failure_closeout(summary: Mapping[str, Any]) -> bool:
    if summary.get("ready_for_compact_failure_marker") is True:
        return True
    if summary.get("terminal_closeout") is True:
        return True
    for field in (
        "compact_failure_class",
        "failure_class",
        "score_failure_attribution",
    ):
        value = str(summary.get(field) or "").strip()
        if value and value.lower() not in {"none", "null", "no_failure"}:
            return True
    return False


def build_benchmark_observable_handle_policy(
    run_snapshot: Mapping[str, Any],
    *,
    scheduler_kind: str = "launchd",
) -> dict[str, Any]:
    """Return a public-safe polling/cleanup policy for a benchmark run handle.

    The policy consumes the compact status snapshot shape produced by
    `scripts/benchmark_run_status_snapshot.py`. It does not inspect raw logs,
    trajectories, local paths, Docker state, or scheduler payloads.
    """

    compact_summaries = _summary_items(run_snapshot)
    compact_result_closeout = any(
        _has_compact_result_closeout(summary) for summary in compact_summaries
    )
    compact_failure_closeout = any(
        _has_compact_failure_closeout(summary) for summary in compact_summaries
    )
    terminal_closeout = compact_result_closeout or compact_failure_closeout
    exists = run_snapshot.get("exists") is True
    pid_present = bool(str(run_snapshot.get("pid") or "").strip())
    status_text = str(run_snapshot.get("status") or "").strip().lower()
    terminal_status = (
        status_text.startswith("rc=")
        or status_text.startswith("exception=")
        or status_text
        in {
            "complete",
            "completed",
            "done",
            "failed",
            "interrupted",
            "terminated",
        }
    )
    pid_alive = run_snapshot.get("pid_alive") is True and not terminal_status

    if pid_alive:
        handle_state = "running"
    elif pid_present:
        handle_state = "ended"
    elif exists:
        handle_state = "missing"
    else:
        handle_state = "not_found"

    missing_terminal_evidence = exists and not terminal_closeout and not pid_alive
    cleanup_required = terminal_closeout or missing_terminal_evidence
    monitor_poll_allowed = exists and not cleanup_required and pid_alive
    blocker_required = missing_terminal_evidence

    if terminal_closeout:
        next_action = "disable_one_shot_scheduler_label_and_ingest_compact_closeout"
    elif blocker_required:
        next_action = "write_precise_missing_or_ended_handle_blocker_before_rerun"
    elif monitor_poll_allowed:
        next_action = "poll_observable_handle"
    elif not exists:
        next_action = "write_missing_run_directory_blocker"
    else:
        next_action = "continue_compact_observation"

    return {
        "schema_version": BENCHMARK_OBSERVABLE_HANDLE_POLICY_SCHEMA_VERSION,
        "scheduler_kind": str(scheduler_kind or "unknown"),
        "one_shot_expected": True,
        "keep_alive_allowed": False,
        "duplicate_rerun_allowed": False,
        "run_label_present": bool(str(run_snapshot.get("label") or "").strip()),
        "observable_handle": {
            "kind": "pid_file" if pid_present else "run_label",
            "state": handle_state,
            "pid_recorded": pid_present,
            "pid_alive": pid_alive,
            "raw_handle_payload_recorded": False,
        },
        "terminal_closeout": terminal_closeout,
        "compact_result_closeout": compact_result_closeout,
        "compact_failure_closeout": compact_failure_closeout,
        "cleanup_required": cleanup_required,
        "disable_scheduler_label_required": cleanup_required,
        "unload_launchd_label_required": cleanup_required
        and str(scheduler_kind or "").lower() == "launchd",
        "monitor_poll_allowed": monitor_poll_allowed,
        "blocker_required_before_rerun": blocker_required,
        "next_action": next_action,
        "boundary": {
            "compact_only": True,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "trajectory_read": False,
            "local_paths_recorded": False,
            "scheduler_payload_recorded": False,
        },
    }
