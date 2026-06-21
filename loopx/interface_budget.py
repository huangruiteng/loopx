from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_INTERFACE_BUDGET_FRESHNESS_HOURS = 24
INTERFACE_BUDGET_CADENCE_SOURCE = "interface_budget_drift_check"


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _metric_headroom(surface: dict[str, Any], value_key: str, limit_key: str) -> dict[str, Any] | None:
    value = _number(surface.get(value_key))
    limit = _number(surface.get(limit_key))
    if value is None or limit is None:
        return None
    remaining = limit - value
    ratio = remaining / limit if limit > 0 else None
    return {
        "metric": value_key,
        "value": int(value) if value.is_integer() else value,
        "limit": int(limit) if limit.is_integer() else limit,
        "remaining": int(remaining) if remaining.is_integer() else remaining,
        "headroom_ratio": _round_ratio(ratio),
        "within_budget": remaining >= 0,
    }


def surface_headroom(surface: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(surface, dict):
        return None
    metrics = [
        _metric_headroom(surface, "json_chars", "max_json_chars"),
        _metric_headroom(surface, "nested_keys", "max_nested_keys"),
        _metric_headroom(surface, "top_level_keys", "max_top_level_keys"),
    ]
    metrics = [metric for metric in metrics if metric]
    if not metrics:
        return None
    tightest = min(
        metrics,
        key=lambda metric: float(metric.get("headroom_ratio") or 0),
    )
    return {
        "surface": str(surface.get("surface") or "unknown"),
        "within_budget": all(metric.get("within_budget") is True for metric in metrics),
        "minimum_headroom_ratio": tightest.get("headroom_ratio"),
        "tightest_metric": tightest.get("metric"),
        "headroom_remaining": tightest.get("remaining"),
    }


def build_interface_budget_cadence(
    surfaces: list[dict[str, Any]],
    *,
    checked_at: str,
    now: datetime | str | None = None,
    freshness_hours: int = DEFAULT_INTERFACE_BUDGET_FRESHNESS_HOURS,
) -> dict[str, Any]:
    checked_dt = parse_timestamp(checked_at)
    now_dt = parse_timestamp(now) if now is not None else datetime.now(timezone.utc)
    headrooms = [
        headroom
        for surface in surfaces
        if isinstance(surface, dict)
        for headroom in [surface_headroom(surface)]
        if headroom
    ]
    tightest = min(
        headrooms,
        key=lambda item: float(item.get("minimum_headroom_ratio") or 0),
    ) if headrooms else None
    next_due_dt = (
        checked_dt + timedelta(hours=max(1, int(freshness_hours)))
        if checked_dt is not None
        else None
    )
    overdue = bool(next_due_dt and now_dt and now_dt >= next_due_dt)
    within_budget = bool(headrooms) and all(item.get("within_budget") is True for item in headrooms)
    recommendation = (
        "quiet_skip_until_next_check_due"
        if within_budget and not overdue
        else "rerun_hot_path_interface_budget_smoke"
    )
    return {
        "source": INTERFACE_BUDGET_CADENCE_SOURCE,
        "checked_at": checked_at,
        "freshness_hours": max(1, int(freshness_hours)),
        "next_check_due_at": next_due_dt.isoformat() if next_due_dt else None,
        "overdue": overdue,
        "within_budget": within_budget,
        "surface_count": len(headrooms),
        "minimum_headroom_ratio": tightest.get("minimum_headroom_ratio") if tightest else None,
        "tightest_surface": tightest.get("surface") if tightest else None,
        "tightest_metric": tightest.get("tightest_metric") if tightest else None,
        "headroom_remaining": tightest.get("headroom_remaining") if tightest else None,
        "recommendation": recommendation,
    }


def compact_interface_budget_cadence(
    value: dict[str, Any],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    checked_at = str(value.get("checked_at") or "").strip()
    next_due_at = str(value.get("next_check_due_at") or "").strip()
    checked_dt = parse_timestamp(checked_at)
    next_due_dt = parse_timestamp(next_due_at)
    now_dt = parse_timestamp(now) if now is not None else datetime.now(timezone.utc)
    overdue = bool(next_due_dt and now_dt and now_dt >= next_due_dt)
    within_budget = value.get("within_budget") is True
    recommendation = str(value.get("recommendation") or "").strip()
    if within_budget and not overdue:
        recommendation = recommendation or "quiet_skip_until_next_check_due"
    else:
        recommendation = recommendation or "rerun_hot_path_interface_budget_smoke"

    compact = {
        "source": str(value.get("source") or INTERFACE_BUDGET_CADENCE_SOURCE),
        "checked_at": checked_at or None,
        "freshness_hours": value.get("freshness_hours"),
        "next_check_due_at": next_due_at or None,
        "overdue": overdue,
        "within_budget": within_budget,
        "surface_count": value.get("surface_count"),
        "minimum_headroom_ratio": value.get("minimum_headroom_ratio"),
        "tightest_surface": value.get("tightest_surface"),
        "tightest_metric": value.get("tightest_metric"),
        "headroom_remaining": value.get("headroom_remaining"),
        "recommendation": recommendation,
    }
    if checked_dt is None:
        compact["checked_at"] = checked_at or None
    return {key: current for key, current in compact.items() if current is not None}


def interface_budget_cadence_from_run(
    run: dict[str, Any],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    cadence = run.get("interface_budget_cadence")
    if isinstance(cadence, dict):
        compact = compact_interface_budget_cadence(cadence, now=now)
        if compact:
            compact["run_generated_at"] = run.get("generated_at")
            compact["run_classification"] = run.get("classification")
        return compact
    surfaces = run.get("interface_budget_surfaces")
    if isinstance(surfaces, list) and run.get("generated_at"):
        summary = build_interface_budget_cadence(
            [surface for surface in surfaces if isinstance(surface, dict)],
            checked_at=str(run.get("generated_at")),
            now=now,
        )
        summary["run_generated_at"] = run.get("generated_at")
        summary["run_classification"] = run.get("classification")
        return summary
    return None


def interface_budget_cadence_for_runs(
    runs: list[dict[str, Any]],
    *,
    now: datetime | str | None = None,
) -> dict[str, Any] | None:
    for run in runs:
        cadence = interface_budget_cadence_from_run(run, now=now)
        if cadence:
            return cadence
    return None
