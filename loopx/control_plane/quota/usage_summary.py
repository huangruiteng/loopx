from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable


USAGE_PROXY_NOTE = "run-history proxy; excludes token counts and raw thread logs"

ParseTimestamp = Callable[[Any], Any]


def quota_spend_slots(run: dict[str, Any]) -> int:
    classification = str(run.get("classification") or "")
    if classification not in {"quota_slot_spent", "quota_slot_voided"}:
        return 0
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    raw_slots = quota_event.get("slots", 1)
    try:
        slots = max(0, int(raw_slots))
    except (TypeError, ValueError):
        slots = 1
    if classification == "quota_slot_voided" or str(quota_event.get("event_type") or "") == "quota_slot_voided":
        return -slots
    return slots


def is_automation_run(run: dict[str, Any]) -> bool:
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    source = str(quota_event.get("source") or run.get("source") or "").lower()
    if source in {"heartbeat", "automation", "cron"}:
        return True
    if "heartbeat" in source or "automation" in source:
        return True
    return str(run.get("classification") or "") in {"quota_slot_spent", "quota_slot_voided"}


def is_progress_signal_run(run: dict[str, Any]) -> bool:
    classification = str(run.get("classification") or "")
    return bool(classification and classification not in {"quota_slot_spent", "quota_slot_voided", "state_refreshed"})


def blank_usage_goal(goal_id: str) -> dict[str, Any]:
    return {
        "goal_id": goal_id,
        "runs_24h": 0,
        "runs_7d": 0,
        "quota_spend_slots_24h": 0,
        "quota_spend_slots_7d": 0,
        "automation_run_count_24h": 0,
        "automation_run_count_7d": 0,
        "progress_signal_run_count_24h": 0,
        "progress_signal_run_count_7d": 0,
        "project_share_24h": 0.0,
    }


def build_usage_summary(
    history: dict[str, Any],
    *,
    parse_timestamp: ParseTimestamp,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    totals = {
        "runs_24h": 0,
        "runs_7d": 0,
        "quota_spend_slots_24h": 0,
        "quota_spend_slots_7d": 0,
        "automation_run_count_24h": 0,
        "automation_run_count_7d": 0,
        "progress_signal_run_count_24h": 0,
        "progress_signal_run_count_7d": 0,
    }
    goals: dict[str, dict[str, Any]] = {}
    sample_count = 0

    for run in history.get("runs") or []:
        if not isinstance(run, dict):
            continue
        sample_count += 1
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        goal_id = str(run.get("goal_id") or "unknown-goal")
        goal = goals.setdefault(goal_id, blank_usage_goal(goal_id))
        slots = quota_spend_slots(run)
        automation_event = is_automation_run(run)
        progress_signal = is_progress_signal_run(run)

        if generated_at >= cutoff_7d:
            totals["runs_7d"] += 1
            goal["runs_7d"] += 1
            totals["quota_spend_slots_7d"] += slots
            goal["quota_spend_slots_7d"] += slots
            if automation_event:
                totals["automation_run_count_7d"] += 1
                goal["automation_run_count_7d"] += 1
            if progress_signal:
                totals["progress_signal_run_count_7d"] += 1
                goal["progress_signal_run_count_7d"] += 1
        if generated_at >= cutoff_24h:
            totals["runs_24h"] += 1
            goal["runs_24h"] += 1
            totals["quota_spend_slots_24h"] += slots
            goal["quota_spend_slots_24h"] += slots
            if automation_event:
                totals["automation_run_count_24h"] += 1
                goal["automation_run_count_24h"] += 1
            if progress_signal:
                totals["progress_signal_run_count_24h"] += 1
                goal["progress_signal_run_count_24h"] += 1

    if totals["runs_24h"]:
        for goal in goals.values():
            goal["project_share_24h"] = round(goal["runs_24h"] / totals["runs_24h"], 3)

    goal_rows = sorted(
        goals.values(),
        key=lambda item: (
            item["runs_24h"],
            item["quota_spend_slots_24h"],
            item["runs_7d"],
            item["goal_id"],
        ),
        reverse=True,
    )
    return {
        "available": True,
        "source": "run_history",
        "generated_at": now.isoformat(),
        "sample_run_count": sample_count,
        "proxy_note": USAGE_PROXY_NOTE,
        "totals": totals,
        "goals": goal_rows,
    }
