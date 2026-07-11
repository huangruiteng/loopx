from __future__ import annotations

import hashlib
import re
from typing import Any

from .contract import (
    normalize_todo_action_kind,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_excluded_agents,
    normalize_todo_id,
    normalize_todo_id_list,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
)


TODO_HANDOFF_NOTE_SCHEMA_VERSION = "handoff_note_v0"
_AK_SK_PATTERN = re.compile(r"(?i)\b(?:ak|sk|access[_-]?key|secret[_-]?key)\b\s*[:=]\s*\S+")


def _compact_text(value: Any, *, limit: int = 220) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text or _AK_SK_PATTERN.search(text):
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _raw_handoff(item: dict[str, Any]) -> dict[str, Any]:
    handoff = item.get("handoff") or item.get("handoff_note")
    return handoff if isinstance(handoff, dict) else {}


def _handoff_id(item: dict[str, Any]) -> str:
    todo_id = normalize_todo_id(item.get("todo_id"))
    if todo_id:
        return f"handoff_{todo_id.removeprefix('todo_')}"
    digest = hashlib.sha1(
        str(
            (
                item.get("goal_id"),
                item.get("role"),
                item.get("index"),
                item.get("text") or item.get("title"),
            )
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"handoff_{digest}"


def _first_text(item: dict[str, Any], *keys: str, limit: int = 220) -> str | None:
    handoff = _raw_handoff(item)
    for key in keys:
        value = handoff.get(key) if key in handoff else item.get(key)
        text = _compact_text(value, limit=limit)
        if text:
            return text
    return None


def _evidence_refs(item: dict[str, Any], *, todo_id: str | None) -> list[str]:
    refs: list[str] = []
    handoff = _raw_handoff(item)
    raw_refs = handoff.get("evidence_refs") or item.get("evidence_refs")
    if isinstance(raw_refs, (list, tuple, set)):
        for raw in raw_refs:
            ref = _compact_text(raw, limit=180)
            if ref and ref not in refs:
                refs.append(ref)

    if item.get("evidence") and todo_id:
        refs.append(f"todo:{todo_id}:evidence")
    if item.get("note") and todo_id:
        refs.append(f"todo:{todo_id}:note")
    latest_event_kind = _compact_text(item.get("latest_event_kind"), limit=80)
    if latest_event_kind and todo_id:
        refs.append(f"rollout_event:{latest_event_kind}:{todo_id}")
    return refs[:6]


def _unresolved_decisions(item: dict[str, Any]) -> list[dict[str, str]]:
    decisions: list[dict[str, str]] = []
    for scope in normalize_todo_required_decision_scopes(item.get("required_decision_scopes")):
        decisions.append(scope)
    single = normalize_todo_decision_scope(item.get("decision_scope"))
    if single:
        identity = (single.get("kind"), single.get("granularity"), single.get("scope_key"))
        if not any(
            (item.get("kind"), item.get("granularity"), item.get("scope_key")) == identity
            for item in decisions
        ):
            decisions.append(single)
    return decisions


def build_todo_handoff_note(
    item: dict[str, Any],
    *,
    goal_id: str | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    """Project an existing todo/history/evidence row into a typed handoff note.

    The note is a read model: it does not create a dispatcher queue, comment
    stream, approval state, or runtime task separate from the source todo.
    """

    if not isinstance(item, dict):
        return None
    handoff = _raw_handoff(item)
    todo_id = normalize_todo_id(item.get("todo_id"))
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    excluded_agents = normalize_todo_excluded_agents(item.get("excluded_agents"))
    from_agent = normalize_todo_claimed_by(
        handoff.get("from_agent") or item.get("agent_id")
    )
    explicit_to_agent = normalize_todo_blocks_agent(handoff.get("to_agent"))
    successor_todo_ids = normalize_todo_id_list(item.get("successor_todo_ids"))
    unblocks_todo_id = normalize_todo_id(item.get("unblocks_todo_id"))
    superseded_by = normalize_todo_id(item.get("superseded_by"))
    has_handoff_signal = bool(
        handoff
        or excluded_agents
        or successor_todo_ids
        or unblocks_todo_id
        or superseded_by
    )
    if not has_handoff_signal:
        return None
    to_agent = explicit_to_agent or claimed_by

    intent = (
        _first_text(item, "intent", limit=80)
        or normalize_todo_action_kind(item.get("action_kind"))
        or _compact_text(item.get("task_class"), limit=80)
        or "continue"
    )
    blocked_on = (
        _first_text(item, "blocked_on", limit=180)
        or normalize_todo_resume_when(item.get("resume_when"))
        or (f"todo:{unblocks_todo_id}" if unblocks_todo_id else None)
        or (f"todo:{superseded_by}" if superseded_by else None)
    )
    payload: dict[str, Any] = {
        "schema_version": TODO_HANDOFF_NOTE_SCHEMA_VERSION,
        "handoff_id": _handoff_id(item),
        "todo_id": todo_id,
        "goal_id": _compact_text(goal_id or item.get("goal_id"), limit=180),
        "from_agent": from_agent,
        "to_agent": to_agent,
        "intent": intent,
        "summary": _first_text(item, "summary", "note", "reason", "evidence", "title", "text", limit=280),
        "evidence_refs": _evidence_refs(item, todo_id=todo_id),
        "unresolved_decisions": _unresolved_decisions(item),
        "blocked_on": blocked_on,
        "suggested_next_action": _first_text(item, "suggested_next_action", "title", "text", limit=260),
        "source": _compact_text(source or item.get("source"), limit=120),
    }
    if successor_todo_ids:
        payload["successor_todo_ids"] = successor_todo_ids
    if unblocks_todo_id:
        payload["unblocks_todo_id"] = unblocks_todo_id
    if excluded_agents:
        payload["excluded_agents"] = excluded_agents
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def attach_todo_handoff_note(
    item: dict[str, Any],
    *,
    goal_id: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    note = build_todo_handoff_note(item, goal_id=goal_id, source=source)
    if note:
        item["handoff_note"] = note
    return item
