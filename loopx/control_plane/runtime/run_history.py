from __future__ import annotations

from typing import Any, Callable, Optional


LatestRun = Callable[[dict[str, Any]], Optional[dict[str, Any]]]
GoalLifecycleFields = Callable[[dict[str, Any], Optional[dict[str, Any]]], dict[str, Any]]
GoalProjection = Callable[[dict[str, Any]], Optional[dict[str, Any]]]
RunCompactor = Callable[[dict[str, Any]], dict[str, Any]]
QuotaStatus = Callable[[dict[str, Any]], dict[str, Any]]
StatusNeutralRun = Callable[[dict[str, Any]], bool]


def latest_run(
    goal: dict[str, Any],
    *,
    is_status_neutral_run: StatusNeutralRun,
) -> dict[str, Any] | None:
    status_run = goal.get("latest_status_run")
    if isinstance(status_run, dict) and not is_status_neutral_run(status_run):
        return status_run

    runs = goal.get("latest_runs")
    if not isinstance(runs, list) or not runs:
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if is_status_neutral_run(run):
            continue
        return run
    return None


def build_run_history(
    history: dict[str, Any],
    *,
    latest_run: LatestRun,
    goal_lifecycle_fields: GoalLifecycleFields,
    subagent_activity_for_goal: GoalProjection,
    compact_run: RunCompactor,
    quota_status: QuotaStatus,
    display_limit: int | None = None,
) -> dict[str, Any]:
    display_limit = None if display_limit is None else max(0, display_limit)
    goals: list[dict[str, Any]] = []
    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        current_run = latest_run(goal)
        lifecycle_fields = goal_lifecycle_fields(goal, current_run)
        subagent_activity = subagent_activity_for_goal(goal)
        latest_runs = [
            compact_run(run)
            for run in goal.get("latest_runs") or []
            if isinstance(run, dict)
        ]
        if display_limit is not None:
            latest_runs = latest_runs[:display_limit]
        goals.append(
            {
                "id": goal.get("id"),
                "domain": goal.get("domain"),
                "status": goal.get("status"),
                "lifecycle_phase": lifecycle_fields["lifecycle_phase"],
                "lifecycle_flags": lifecycle_fields["lifecycle_flags"],
                "registry_member": goal.get("registry_member"),
                "legacy_runtime_goal": goal.get("legacy_runtime_goal"),
                "adapter_kind": goal.get("adapter_kind"),
                "adapter_status": goal.get("adapter_status"),
                "coordination": goal.get("coordination") if isinstance(goal.get("coordination"), dict) else None,
                "guards": goal.get("guards") if isinstance(goal.get("guards"), list) else [],
                "next_probe": goal.get("next_probe"),
                "authority_registry": goal.get("authority_registry"),
                "quota": quota_status(goal) if goal.get("registry_member") else None,
                "index_exists": goal.get("index_exists"),
                "raw_index_records": goal.get("raw_index_records"),
                "unique_runs": goal.get("unique_runs"),
                "subagent_activity": subagent_activity,
                "latest_status_run": compact_run(current_run) if current_run else None,
                "latest_runs": latest_runs,
            }
        )

    recent_runs = [
        compact_run(run)
        for run in history.get("runs") or []
        if isinstance(run, dict)
    ]
    if display_limit is not None:
        recent_runs = recent_runs[:display_limit]
    return {
        "available": True,
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "goals": goals,
        "recent_runs": recent_runs,
    }
