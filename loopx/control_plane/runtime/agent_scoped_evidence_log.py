from __future__ import annotations

import re
import shlex
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "agent_scoped_evidence_log_v0"
REQUIRED_READ_SCHEMA_VERSION = "loopx_agent_required_read_v0"

_AK_SK_PATTERN = re.compile(r"(?i)\b(?:ak|sk|access[_-]?key|secret[_-]?key)\b\s*[:=]\s*\S+")


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _compact_text(value: Any, *, limit: int = 220) -> str | None:
    text = " ".join(str(value or "").split())
    if not text:
        return None
    if _AK_SK_PATTERN.search(text):
        return None
    return text[:limit]


def _normalize_event_kind(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _safe_rollout_event_row(event: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": "rollout_event_log",
        "recorded_at": event.get("recorded_at"),
        "event_id": event.get("event_id"),
        "event_kind": event.get("event_kind"),
    }
    for key in (
        "status",
        "agent_id",
        "todo_id",
        "classification",
        "delivery_outcome",
        "benchmark_id",
        "case_id",
        "run_id",
    ):
        safe = _compact_text(event.get(key), limit=180)
        if safe:
            row[key] = safe
    summary = _compact_text(event.get("summary"), limit=360)
    if summary:
        row["summary"] = summary
    for key in ("lane", "state_transition", "causality", "code_refs", "handoff"):
        value = event.get(key)
        if isinstance(value, dict):
            row[key] = value
    return row


def _safe_run_history_row(run: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "source": "run_history",
        "recorded_at": run.get("generated_at"),
        "run_ref": run.get("generated_at"),
    }
    for key in (
        "goal_id",
        "agent_id",
        "agent_lane",
        "classification",
        "delivery_outcome",
        "delivery_batch_scale",
        "progress_scope",
        "health_check",
    ):
        safe = _compact_text(run.get(key), limit=260 if key == "health_check" else 180)
        if safe:
            row[key] = safe
    action = _compact_text(run.get("recommended_action"), limit=360)
    if action:
        row["recommended_action"] = action
    return row


def _event_matches(
    event: Mapping[str, Any],
    *,
    agent_id: str,
    todo_id: str | None,
    event_kinds: set[str],
    since: datetime | None,
) -> bool:
    if str(event.get("agent_id") or "") != agent_id:
        return False
    if todo_id and str(event.get("todo_id") or "") != todo_id:
        return False
    if event_kinds and _normalize_event_kind(str(event.get("event_kind") or "")) not in event_kinds:
        return False
    if since is not None:
        recorded_at = _parse_timestamp(event.get("recorded_at"))
        if recorded_at is None or recorded_at < since:
            return False
    return True


def _run_mentions_todo(run: Mapping[str, Any], todo_id: str) -> bool:
    needles = (
        run.get("todo_id"),
        run.get("classification"),
        run.get("recommended_action"),
        run.get("health_check"),
    )
    return any(todo_id in str(value or "") for value in needles)


def _run_matches(
    run: Mapping[str, Any],
    *,
    goal_id: str,
    agent_id: str,
    todo_id: str | None,
    since: datetime | None,
) -> bool:
    if str(run.get("goal_id") or goal_id) != goal_id:
        return False
    if str(run.get("agent_id") or "") != agent_id:
        return False
    if todo_id and not _run_mentions_todo(run, todo_id):
        return False
    if since is not None:
        recorded_at = _parse_timestamp(run.get("generated_at"))
        if recorded_at is None or recorded_at < since:
            return False
    return True


def _sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (str(row.get("recorded_at") or ""), str(row.get("source") or ""))


def build_agent_scoped_evidence_log_command(
    *,
    goal_id: str,
    agent_id: str,
    todo_id: str | None = None,
    cli_bin: str = "loopx",
    output_format: str = "json",
    limit: int = 24,
) -> str:
    safe_goal_id = _compact_text(goal_id, limit=180)
    safe_agent_id = _compact_text(agent_id, limit=180)
    if not safe_goal_id:
        raise ValueError("goal_id is required")
    if not safe_agent_id:
        raise ValueError("agent_id is required")
    safe_todo_id = _compact_text(todo_id, limit=180) if todo_id else None
    parts = [
        cli_bin or "loopx",
        "--format",
        output_format or "json",
        "evidence-log",
        "--goal-id",
        safe_goal_id,
        "--agent-id",
        safe_agent_id,
        "--thin",
        "--limit",
        str(max(0, int(limit))),
    ]
    if safe_todo_id:
        parts.extend(["--todo-id", safe_todo_id])
    return " ".join(shlex.quote(part) for part in parts)


def build_agent_scoped_required_read(
    *,
    goal_id: str,
    agent_id: str | None,
    todo_id: str | None = None,
    reason: str = "read this agent's thin public-safe evidence ledger before replan",
    cli_bin: str = "loopx",
    limit: int = 24,
) -> dict[str, Any] | None:
    safe_agent_id = _compact_text(agent_id, limit=180) if agent_id else None
    if not safe_agent_id:
        return None
    command = build_agent_scoped_evidence_log_command(
        goal_id=goal_id,
        agent_id=safe_agent_id,
        todo_id=todo_id,
        cli_bin=cli_bin,
        limit=limit,
    )
    return {
        "schema_version": REQUIRED_READ_SCHEMA_VERSION,
        "kind": "agent_scoped_evidence_log",
        "goal_id": _compact_text(goal_id, limit=180),
        "agent_id": safe_agent_id,
        "todo_id": _compact_text(todo_id, limit=180) if todo_id else None,
        "mode": "thin",
        "command": command,
        "reason": _compact_text(reason, limit=180),
        "other_agent_policy": "frontier_only",
    }


def _other_agent_frontier(
    runs: Iterable[Mapping[str, Any]],
    *,
    goal_id: str,
    agent_id: str,
    limit: int,
) -> dict[str, Any]:
    latest_by_agent: dict[str, dict[str, Any]] = {}
    for run in runs:
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        other_agent = _compact_text(run.get("agent_id"), limit=120)
        if not other_agent or other_agent == agent_id:
            continue
        current = latest_by_agent.get(other_agent)
        if current is None or str(run.get("generated_at") or "") > str(current.get("recorded_at") or ""):
            row = _safe_run_history_row(run)
            row["agent_id"] = other_agent
            latest_by_agent[other_agent] = row
    rows = sorted(latest_by_agent.values(), key=_sort_key, reverse=True)[: max(0, limit)]
    return {
        "schema_version": "other_agent_frontier_v0",
        "policy": "goal_frontier_only",
        "item_count": len(rows),
        "items": rows,
    }


def build_agent_scoped_evidence_log(
    *,
    goal_id: str,
    agent_id: str,
    rollout_events: Iterable[Mapping[str, Any]],
    history_runs: Iterable[Mapping[str, Any]],
    todo_id: str | None = None,
    since: str | None = None,
    event_kinds: Iterable[str] | None = None,
    limit: int = 24,
) -> dict[str, Any]:
    """Build a public-safe, agent-scoped ledger for replan and handoff reads."""

    safe_goal_id = _compact_text(goal_id, limit=180)
    safe_agent_id = _compact_text(agent_id, limit=180)
    if not safe_goal_id:
        raise ValueError("goal_id is required")
    if not safe_agent_id:
        raise ValueError("agent_id is required")
    safe_todo_id = _compact_text(todo_id, limit=180) if todo_id else None
    since_dt = _parse_timestamp(since)
    if since and since_dt is None:
        raise ValueError(f"invalid --since timestamp: {since}")
    normalized_kinds = {
        _normalize_event_kind(kind)
        for kind in event_kinds or []
        if _normalize_event_kind(kind)
    }
    max_rows = max(0, int(limit))

    event_rows = [
        _safe_rollout_event_row(event)
        for event in rollout_events
        if _event_matches(
            event,
            agent_id=safe_agent_id,
            todo_id=safe_todo_id,
            event_kinds=normalized_kinds,
            since=since_dt,
        )
    ]
    run_list = [dict(run) for run in history_runs]
    run_rows = [
        _safe_run_history_row(run)
        for run in run_list
        if _run_matches(
            run,
            goal_id=safe_goal_id,
            agent_id=safe_agent_id,
            todo_id=safe_todo_id,
            since=since_dt,
        )
    ]
    ledger_rows = sorted([*event_rows, *run_rows], key=_sort_key, reverse=True)[:max_rows]

    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "mode": "thin",
        "goal_id": safe_goal_id,
        "agent_id": safe_agent_id,
        "todo_id": safe_todo_id,
        "since": since if since_dt else None,
        "event_kinds": sorted(normalized_kinds),
        "limit": max_rows,
        "source_refs": [
            "rollout_event_log.public_safe_view",
            "compact_run_history.public_refs",
        ],
        "rollout_event_count": len(event_rows),
        "run_history_ref_count": len(run_rows),
        "ledger": ledger_rows,
        "other_agent_frontier": _other_agent_frontier(
            run_list,
            goal_id=safe_goal_id,
            agent_id=safe_agent_id,
            limit=3,
        ),
        "boundary": {
            "raw_task_text_recorded": False,
            "raw_logs_recorded": False,
            "raw_trajectory_recorded": False,
            "raw_session_transcript_recorded": False,
            "credential_values_recorded": False,
            "absolute_paths_recorded": False,
            "other_agent_event_stream_expanded": False,
        },
    }
