from __future__ import annotations

from typing import Any, Callable, Optional


PublicSafeText = Callable[..., Optional[str]]
ActionAlignment = Callable[[Any, Any], bool]
TimestampParser = Callable[[Any], Any]


def is_status_neutral_run(
    run: dict[str, Any],
    *,
    status_neutral_classifications: set[str],
    agent_lane_progress_scope: str,
) -> bool:
    return (
        str(run.get("classification") or "") in status_neutral_classifications
        or str(run.get("progress_scope") or "") == agent_lane_progress_scope
    )


def latest_agent_lane_run(
    goal: dict[str, Any],
    *,
    agent_lane_progress_scope: str,
) -> dict[str, Any] | None:
    runs = goal.get("latest_runs")
    if not isinstance(runs, list):
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("progress_scope") or "") == agent_lane_progress_scope:
            return run
    return None


def compact_agent_lane_recommendation(
    run: dict[str, Any] | None,
    *,
    agent_lane_progress_scope: str,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    action = public_safe_compact_text(run.get("recommended_action"), limit=220)
    if not action:
        return None
    compact: dict[str, Any] = {
        "schema_version": "agent_lane_recommendation_v0",
        "progress_scope": agent_lane_progress_scope,
        "recommended_action": action,
    }
    for field in (
        "agent_id",
        "agent_lane",
        "classification",
        "generated_at",
        "delivery_batch_scale",
        "delivery_outcome",
    ):
        if run.get(field) is not None:
            compact[field] = run.get(field)
    return compact


def latest_run_recommended_action_for_projection(
    *,
    current_status_run: dict[str, Any] | None,
    agent_lane_recommendation: dict[str, Any] | None,
    active_state_next_action: Any = None,
    limit: int = 320,
    public_safe_compact_text: PublicSafeText,
    actions_are_projection_aligned: ActionAlignment,
    parse_timestamp: TimestampParser,
) -> tuple[str | None, str | None]:
    latest_action = public_safe_compact_text(
        current_status_run.get("recommended_action")
        if isinstance(current_status_run, dict)
        else None,
        limit=limit,
    )
    if not isinstance(agent_lane_recommendation, dict):
        return latest_action, "latest_status_run" if latest_action else None

    lane_action = public_safe_compact_text(
        agent_lane_recommendation.get("recommended_action"),
        limit=limit,
    )
    if not lane_action:
        return latest_action, "latest_status_run" if latest_action else None
    if not active_state_next_action or not actions_are_projection_aligned(
        active_state_next_action,
        lane_action,
    ):
        return latest_action, "latest_status_run" if latest_action else None

    latest_aligned = bool(
        latest_action
        and actions_are_projection_aligned(active_state_next_action, latest_action)
    )
    lane_dt = parse_timestamp(agent_lane_recommendation.get("generated_at"))
    latest_dt = parse_timestamp(
        current_status_run.get("generated_at")
        if isinstance(current_status_run, dict)
        else None
    )
    lane_is_newer = bool(lane_dt and latest_dt and lane_dt >= latest_dt)
    if not latest_action or not latest_aligned or lane_is_newer:
        return lane_action, "agent_lane_recommendation"
    return latest_action, "latest_status_run"
