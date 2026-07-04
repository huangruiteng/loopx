from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


def project_asset_handoff_state(
    *,
    ready: bool,
    project_asset: dict[str, Any],
    latest_runs: list[dict[str, Any]] | None,
    compact_execution_profile: Callable[[dict[str, Any] | None], dict[str, Any]],
    parse_timestamp: Callable[[Any], datetime | None],
    is_handoff_ready_run: Callable[[dict[str, Any]], bool],
    is_custom_post_handoff_work_run: Callable[[dict[str, Any]], bool],
    is_status_neutral_run: Callable[[dict[str, Any]], bool],
    compact_post_handoff_run: Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]],
    small_delivery_batch_scale_streak: Callable[[list[dict[str, Any]]], int],
    outcome_floor_configured: Callable[[dict[str, Any] | None], bool],
    outcome_gap_streak: Callable[[list[dict[str, Any]], dict[str, Any] | None], int],
) -> dict[str, Any]:
    runs = [run for run in latest_runs or [] if isinstance(run, dict)]
    profile = compact_execution_profile(
        project_asset.get("execution_profile")
        if isinstance(project_asset.get("execution_profile"), dict)
        else None
    )
    parsed_runs = [
        (run, parse_timestamp(run.get("generated_at")))
        for run in runs
    ]
    parsed_runs = [(run, generated_at) for run, generated_at in parsed_runs if generated_at]
    parsed_runs.sort(key=lambda item: item[1], reverse=True)

    handoff_run: dict[str, Any] | None = None
    handoff_at: datetime | None = None
    for run, generated_at in parsed_runs:
        if is_handoff_ready_run(run):
            handoff_run = run
            handoff_at = generated_at
            break

    post_handoff_run: dict[str, Any] | None = None
    recent_post_handoff_runs: list[dict[str, Any]] = []
    if handoff_at is None and ready:
        recent_post_handoff_runs = [
            run
            for run, _generated_at in parsed_runs
            if is_custom_post_handoff_work_run(run)
        ]
        if recent_post_handoff_runs:
            post_handoff_run = recent_post_handoff_runs[0]
        latest_validation = (
            project_asset.get("latest_validation")
            if isinstance(project_asset.get("latest_validation"), dict)
            else {}
        )
        if latest_validation and post_handoff_run is None:
            latest_validation_run = {
                "generated_at": latest_validation.get("generated_at"),
                "classification": latest_validation.get("classification"),
            }
            if is_custom_post_handoff_work_run(latest_validation_run):
                post_handoff_run = latest_validation_run
                recent_post_handoff_runs = [latest_validation_run]
            else:
                handoff_at = parse_timestamp(latest_validation.get("generated_at"))
                handoff_run = latest_validation_run

    if handoff_at is not None and post_handoff_run is None:
        for run, generated_at in parsed_runs:
            if generated_at <= handoff_at:
                continue
            if is_status_neutral_run(run) or is_handoff_ready_run(run):
                continue
            recent_post_handoff_runs.append(run)
        if recent_post_handoff_runs:
            post_handoff_run = recent_post_handoff_runs[0]

    if post_handoff_run and not recent_post_handoff_runs:
        recent_post_handoff_runs = [post_handoff_run]
    if len(recent_post_handoff_runs) > 3:
        recent_post_handoff_runs = recent_post_handoff_runs[:3]

    if post_handoff_run:
        handoff_status = "post_handoff_run_seen"
    elif ready:
        handoff_status = "ready_waiting_for_run"
    else:
        handoff_status = "not_ready"

    state: dict[str, Any] = {
        "handoff_status": handoff_status,
        "post_handoff_run_seen": bool(post_handoff_run),
    }
    if handoff_run and handoff_run.get("generated_at"):
        state["handoff_ready_at"] = handoff_run.get("generated_at")
    if handoff_run and handoff_run.get("classification"):
        state["handoff_ready_classification"] = handoff_run.get("classification")
    if post_handoff_run:
        state["post_handoff_latest_run"] = compact_post_handoff_run(post_handoff_run, profile)
    if recent_post_handoff_runs:
        state["post_handoff_recent_runs"] = [
            compact_post_handoff_run(run, profile)
            for run in recent_post_handoff_runs
        ]
        state["post_handoff_small_scale_streak"] = small_delivery_batch_scale_streak(
            recent_post_handoff_runs
        )
        if outcome_floor_configured(profile):
            state["post_handoff_outcome_gap_streak"] = outcome_gap_streak(
                recent_post_handoff_runs,
                profile,
            )
    return state


def project_asset_handoff_readiness(
    item: dict[str, Any],
    *,
    latest_runs: list[dict[str, Any]] | None,
    project_asset_handoff_check_projection: Callable[[dict[str, Any]], dict[str, Any] | None],
    handoff_budget_contract: Callable[[], dict[str, Any]],
    project_asset_handoff_state: Callable[
        ...,
        dict[str, Any],
    ],
) -> dict[str, Any] | None:
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return None

    check_projection = project_asset_handoff_check_projection(item)
    if not check_projection:
        return None
    checks = check_projection["checks"]
    goal_id = str(item.get("goal_id") or "").strip()
    readiness: dict[str, Any] = {
        "ready": all(checks.values()),
        "codex_ready": bool(check_projection.get("codex_ready")),
        "source": "project_asset",
        "quota_state": check_projection.get("quota_state") or "unknown",
        "handoff_interface_budget": handoff_budget_contract(),
        "checks": checks,
    }
    readiness.update(
        project_asset_handoff_state(
            ready=bool(check_projection.get("state_trace_ready")),
            project_asset=project_asset,
            latest_runs=latest_runs,
        )
    )
    if goal_id:
        readiness["next_probe"] = f"loopx review-packet --goal-id {goal_id} --handoff-only"
    return readiness
