from __future__ import annotations

from typing import Any

from ..todos.contract import normalize_todo_claimed_by
from .monitor_poll import QUOTA_MONITOR_POLL_CLASSIFICATION


def goal_latest_runs(status_payload: dict[str, Any], *, goal_id: str) -> list[dict[str, Any]]:
    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    goal = next(
        (
            candidate
            for candidate in goals
            if isinstance(candidate, dict) and str(candidate.get("id") or "") == goal_id
        ),
        None,
    )
    if not isinstance(goal, dict):
        return []
    runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    return [run for run in runs if isinstance(run, dict)]


def recent_external_monitor_observation_unchanged(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None = None,
    scan_limit: int = 8,
) -> dict[str, Any] | None:
    safe_agent_id = normalize_todo_claimed_by(agent_id)
    for run in goal_latest_runs(status_payload, goal_id=goal_id)[: max(1, scan_limit)]:
        run_agent_id = normalize_todo_claimed_by(run.get("agent_id"))
        if safe_agent_id and run_agent_id and run_agent_id != safe_agent_id:
            continue
        if str(run.get("classification") or "") != QUOTA_MONITOR_POLL_CLASSIFICATION:
            continue
        monitor_event = run.get("monitor_event") if isinstance(run.get("monitor_event"), dict) else {}
        monitor_mode = str(monitor_event.get("monitor_mode") or "").strip()
        health_check = str(run.get("health_check") or "").strip().lower()
        if monitor_event.get("material_change") is True:
            return None
        monitor_unchanged = (
            monitor_mode.endswith("_observed_without_material_transition")
            or "monitor observation unchanged" in health_check
            or "due monitor observation unchanged" in health_check
            or "external monitor observation unchanged" in health_check
        )
        if monitor_unchanged:
            return {
                "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
                "generated_at": run.get("generated_at"),
                "agent_id": run_agent_id or None,
                "monitor_mode": monitor_mode or "monitor_observed_without_material_transition",
                "reason": "recent monitor observation was unchanged",
            }
    return None
