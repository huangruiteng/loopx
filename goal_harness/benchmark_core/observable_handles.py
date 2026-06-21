from __future__ import annotations

from typing import Any, Mapping


BENCHMARK_OBSERVABLE_HANDLE_POLICY_SCHEMA_VERSION = (
    "benchmark_observable_handle_policy_v0"
)


_RESULT_CLOSEOUT_STATUS_VALUES = {
    "completed",
    "complete",
    "passed",
    "failed",
    "scored",
    "score_ready",
}


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
    pid_alive = run_snapshot.get("pid_alive") is True

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
