from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..runtime.public_safety import public_safe_compact_text
from .material_frontier import AGENT_MATERIAL_FRONTIER_SCHEMA_VERSION


MATERIAL_HANDOFF_NOTE_SCHEMA_VERSION = "handoff_note_v1"
MATERIAL_HANDOFF_PROJECTION_SCHEMA_VERSION = "agent_material_handoff_projection_v0"
MAX_MATERIAL_HANDOFF_REFS = 4

_FRONTIER_STATES = {
    "current",
    "inaccessible",
    "missing",
    "required_unread",
    "stale",
}
_HANDOFF_NOTE_FIELDS = (
    "handoff_id",
    "todo_id",
    "goal_id",
    "from_agent",
    "to_agent",
    "intent",
    "summary",
    "evidence_refs",
    "unresolved_decisions",
    "blocked_on",
    "suggested_next_action",
    "source",
    "successor_todo_ids",
    "unblocks_todo_id",
    "excluded_agents",
)


def _safe_text(value: Any, *, field: str, limit: int = 220) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    if len(text) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    if public_safe_compact_text(text, limit=limit) != text:
        raise ValueError(f"{field} must be public-safe")
    return text


def _required_text(value: Any, *, field: str, limit: int = 220) -> str:
    text = _safe_text(value, field=field, limit=limit)
    if not text:
        raise ValueError(f"{field} is required")
    return text


def project_material_frontier_for_handoff(
    frontier: Mapping[str, Any],
) -> dict[str, Any]:
    """Reduce a full frontier to bounded requirement refs and state counts."""

    if str(frontier.get("schema_version") or "") != AGENT_MATERIAL_FRONTIER_SCHEMA_VERSION:
        raise ValueError(
            "material handoff requires an agent_material_frontier_v0 packet"
        )
    raw_items = frontier.get("items")
    if not isinstance(raw_items, list) or any(
        not isinstance(item, Mapping) for item in raw_items
    ):
        raise ValueError("agent material frontier items must be a list of objects")

    counts = {state: 0 for state in _FRONTIER_STATES}
    material_refs: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for raw_item in raw_items:
        material_id = _required_text(
            raw_item.get("material_id"),
            field="material handoff material_id",
            limit=180,
        )
        if material_id in seen_ids:
            continue
        seen_ids.add(material_id)
        state = _required_text(
            raw_item.get("state"),
            field=f"material handoff state for {material_id}",
            limit=40,
        )
        if state not in _FRONTIER_STATES:
            raise ValueError(f"unsupported material frontier state: {state}")
        counts[state] += 1

        if len(material_refs) >= MAX_MATERIAL_HANDOFF_REFS:
            continue
        material_ref: dict[str, str] = {"material_id": material_id}
        relation = _safe_text(
            raw_item.get("relation"),
            field=f"material handoff relation for {material_id}",
            limit=80,
        )
        purpose = _safe_text(
            raw_item.get("purpose"),
            field=f"material handoff purpose for {material_id}",
            limit=220,
        )
        if relation:
            material_ref["relation"] = relation
        if purpose:
            material_ref["purpose"] = purpose
        material_refs.append(material_ref)

    summary = {
        "required_count": len(seen_ids),
        "current_count": counts["current"],
        "stale_count": counts["stale"],
        "missing_count": counts["missing"],
        "inaccessible_count": counts["inaccessible"],
        "required_unread_count": counts["required_unread"],
    }
    return {
        "schema_version": MATERIAL_HANDOFF_PROJECTION_SCHEMA_VERSION,
        "summary": summary,
        "material_ref_count": len(seen_ids),
        "material_refs": material_refs,
        "material_refs_truncated": len(seen_ids) > len(material_refs),
    }


def build_material_handoff_note_v1(
    handoff_note: Mapping[str, Any],
    frontier: Mapping[str, Any],
) -> dict[str, Any]:
    """Attach a bounded frontier projection to an existing typed handoff note."""

    if str(handoff_note.get("schema_version") or "") not in {
        "handoff_note_v0",
        MATERIAL_HANDOFF_NOTE_SCHEMA_VERSION,
    }:
        raise ValueError("material handoff requires a typed handoff_note_v0 or v1")
    projection = project_material_frontier_for_handoff(frontier)
    payload = {
        key: handoff_note[key]
        for key in _HANDOFF_NOTE_FIELDS
        if handoff_note.get(key) not in (None, "", [], {})
    }
    payload.update(
        {
            "schema_version": MATERIAL_HANDOFF_NOTE_SCHEMA_VERSION,
            "material_frontier_summary": projection["summary"],
            "material_ref_count": projection["material_ref_count"],
            "material_refs": projection["material_refs"],
            "material_refs_truncated": projection["material_refs_truncated"],
        }
    )
    return payload
