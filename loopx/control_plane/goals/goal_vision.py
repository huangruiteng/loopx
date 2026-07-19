from __future__ import annotations

from typing import Any

from ...feedback import validate_public_safe_text
from .goal_vision_state import (
    GOAL_VISION_DEFAULT_STATE,
    normalize_goal_vision_state,
)
from .goal_vision_policy import normalize_goal_vision_advancement_policy


GOAL_VISION_REPLAN_SCHEMA_VERSION = "goal_vision_replan_contract_v0"
GOAL_PATH_DELTA_SCHEMA_VERSION = "goal_path_delta_v0"
GOAL_VISION_BUDGET_ERROR = "vision_budget_exceeded"


GOAL_VISION_FIELD_LIMITS: dict[str, int] = {
    "vision_summary": 420,
    "role_scope": 280,
    "acceptance_summary": 420,
    "advancement_policy": 32,
    "replan_trigger_summary": 240,
    "dreaming_policy": 240,
    "last_patch_summary": 240,
}
GOAL_VISION_TOTAL_LIMIT = 1200
GOAL_PATH_DELTA_OUTCOMES = frozenset(
    {"continue", "replan", "wait", "no_change", "ask_human", "stop"}
)
GOAL_PATH_DELTA_SCALAR_LIMITS: dict[str, int] = {
    "prior_assumption": 220,
    "observed_reality": 220,
    "reentry_condition": 180,
}
GOAL_PATH_DELTA_LIST_LIMITS: dict[str, tuple[int, int]] = {
    "retained": (3, 120),
    "changed": (3, 120),
    "stopped": (3, 120),
    "unresolved_questions": (2, 140),
    "evidence_refs": (4, 140),
}
GOAL_PATH_DELTA_BUDGET_LIMITS = {
    "path_delta.outcome": 32,
    **{
        f"path_delta.{field}": limit
        for field, limit in GOAL_PATH_DELTA_SCALAR_LIMITS.items()
    },
    **{
        f"path_delta.{field}[]": item_limit
        for field, (_, item_limit) in GOAL_PATH_DELTA_LIST_LIMITS.items()
    },
}
GOAL_VISION_BUDGET_COMPACT_FIELDS = (
    "schema_version",
    "status",
    "field_usage",
    "total_limit",
    "total_usage",
)


class GoalVisionBudgetError(ValueError):
    def __init__(
        self,
        *,
        field: str,
        used: int,
        limit: int,
        suggestion: str | None = None,
    ) -> None:
        self.field = field
        self.used = used
        self.limit = limit
        self.suggestion = suggestion
        message = f"{GOAL_VISION_BUDGET_ERROR}: {field} uses {used} chars; limit is {limit}"
        if suggestion:
            message += f"; suggested compact value: {suggestion!r}"
        else:
            message += "; shorten one or more vision fields before retrying"
        super().__init__(message)


def _suggest_compact_text(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3].rstrip() + "..."


def _bounded_public_text(*, field: str, value: Any, limit: int) -> str:
    text = " ".join(str(value or "").strip().split())
    validate_public_safe_text(f"agent_vision.{field}", text)
    if len(text) > limit:
        raise GoalVisionBudgetError(
            field=field,
            used=len(text),
            limit=limit,
            suggestion=_suggest_compact_text(text, limit=limit),
        )
    return text


def _packet_text(packet: dict[str, Any], field: str, *, limit: int) -> str | None:
    value = packet.get(field)
    if value is None:
        return None
    text = _bounded_public_text(field=field, value=value, limit=limit)
    return text or None


def _compact_public_text(value: Any, *, limit: int) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    return text[:limit]


def _compact_goal_path_delta(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    schema_version = (
        _compact_public_text(value.get("schema_version"), limit=80)
        or GOAL_PATH_DELTA_SCHEMA_VERSION
    )
    compact: dict[str, Any] = {"schema_version": schema_version}
    outcome = _compact_public_text(value.get("outcome"), limit=32)
    if outcome in GOAL_PATH_DELTA_OUTCOMES:
        compact["outcome"] = outcome
    for field, limit in GOAL_PATH_DELTA_SCALAR_LIMITS.items():
        text = _compact_public_text(value.get(field), limit=limit)
        if text:
            compact[field] = text
    for field, (max_items, item_limit) in GOAL_PATH_DELTA_LIST_LIMITS.items():
        raw_items = value.get(field)
        if not isinstance(raw_items, list):
            continue
        items = [
            text
            for item in raw_items[:max_items]
            if (text := _compact_public_text(item, limit=item_limit))
        ]
        if items:
            compact[field] = items
    return compact if len(compact) > 1 else None


def _normalize_goal_path_delta(value: Any) -> tuple[dict[str, Any] | None, dict[str, int]]:
    if value is None:
        return None, {}
    if not isinstance(value, dict):
        raise ValueError("agent_vision.path_delta must be a JSON object")

    outcome = str(value.get("outcome") or "").strip().lower().replace("-", "_")
    if outcome not in GOAL_PATH_DELTA_OUTCOMES:
        raise ValueError(
            "agent_vision.path_delta.outcome must be one of: "
            + ", ".join(sorted(GOAL_PATH_DELTA_OUTCOMES))
        )

    normalized: dict[str, Any] = {
        "schema_version": GOAL_PATH_DELTA_SCHEMA_VERSION,
        "outcome": outcome,
    }
    field_usage = {"path_delta.outcome": len(outcome)}
    for field, limit in GOAL_PATH_DELTA_SCALAR_LIMITS.items():
        raw_value = value.get(field)
        if raw_value is None:
            continue
        text = _bounded_public_text(
            field=f"path_delta.{field}", value=raw_value, limit=limit
        )
        if not text:
            continue
        normalized[field] = text
        field_usage[f"path_delta.{field}"] = len(text)

    for field, (max_items, item_limit) in GOAL_PATH_DELTA_LIST_LIMITS.items():
        raw_items = value.get(field)
        if raw_items is None:
            continue
        if not isinstance(raw_items, list):
            raise ValueError(f"agent_vision.path_delta.{field} must be a JSON array")
        if len(raw_items) > max_items:
            raise ValueError(
                f"agent_vision.path_delta.{field} has {len(raw_items)} items; "
                f"limit is {max_items}"
            )
        items: list[str] = []
        for index, item in enumerate(raw_items):
            text = _bounded_public_text(
                field=f"path_delta.{field}[{index}]",
                value=item,
                limit=item_limit,
            )
            if text:
                items.append(text)
                field_usage[f"path_delta.{field}[{index}]"] = len(text)
        if items:
            normalized[field] = items

    if "prior_assumption" not in normalized or "observed_reality" not in normalized:
        raise ValueError(
            "agent_vision.path_delta requires prior_assumption and observed_reality"
        )
    if not any(normalized.get(field) for field in ("retained", "changed", "stopped")):
        raise ValueError(
            "agent_vision.path_delta requires at least one retained, changed, or "
            "stopped item"
        )
    return normalized, field_usage


def compact_goal_vision_packet(value: Any) -> dict[str, Any] | None:
    """Return the public read-path shape of an agent goal-vision packet."""

    if not isinstance(value, dict):
        return None
    compact: dict[str, Any] = {}
    for field in ("schema_version", "goal_id", "agent_id", "state"):
        text = _compact_public_text(value.get(field), limit=120)
        if text:
            compact[field] = text

    patch = value.get("vision_patch") if isinstance(value.get("vision_patch"), dict) else {}
    compact_patch: dict[str, str] = {}
    for field, limit in GOAL_VISION_FIELD_LIMITS.items():
        text = _compact_public_text(patch.get(field), limit=limit)
        if text:
            compact_patch[field] = text
    if compact_patch:
        compact["vision_patch"] = compact_patch

    path_delta = _compact_goal_path_delta(value.get("path_delta"))
    if path_delta:
        compact["path_delta"] = path_delta

    todo_delta: list[str] = []
    raw_todo_delta = value.get("todo_delta")
    if isinstance(raw_todo_delta, list):
        for item in raw_todo_delta[:8]:
            text = _compact_public_text(item, limit=80)
            if text:
                todo_delta.append(text)
    if todo_delta:
        compact["todo_delta"] = todo_delta

    budget = value.get("vision_budget") if isinstance(value.get("vision_budget"), dict) else {}
    compact_budget = {
        field: budget[field]
        for field in GOAL_VISION_BUDGET_COMPACT_FIELDS
        if field in budget
    }
    if compact_budget:
        compact["vision_budget"] = compact_budget

    validation = value.get("validation") if isinstance(value.get("validation"), dict) else {}
    compact_validation = {
        field: validation[field]
        for field in ("budget_checked", "budget_status", "write_correctness_checked")
        if field in validation
    }
    if compact_validation:
        compact["validation"] = compact_validation

    return compact or None


def normalize_goal_vision_packet(
    packet: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None,
) -> dict[str, Any]:
    if not isinstance(packet, dict):
        raise ValueError("agent_vision must be a JSON object")

    source = packet.get("vision_patch") if isinstance(packet.get("vision_patch"), dict) else packet
    packet_goal_id = str(packet.get("goal_id") or "").strip()
    if packet_goal_id and packet_goal_id != goal_id:
        raise ValueError(f"agent_vision goal_id {packet_goal_id!r} does not match {goal_id!r}")

    packet_agent_id = str(packet.get("agent_id") or "").strip()
    if agent_id and packet_agent_id and packet_agent_id != agent_id:
        raise ValueError(
            f"agent_vision agent_id {packet_agent_id!r} does not match {agent_id!r}"
        )
    resolved_agent_id = agent_id or packet_agent_id
    if not resolved_agent_id:
        raise ValueError("agent_vision requires agent_id from packet or --agent-id")
    validate_public_safe_text("agent_vision.agent_id", resolved_agent_id)

    state = normalize_goal_vision_state(
        _bounded_public_text(
            field="state",
            value=packet.get("state") or GOAL_VISION_DEFAULT_STATE,
            limit=80,
        )
    )
    vision_patch: dict[str, str] = {}
    field_usage: dict[str, int] = {}
    for field, limit in GOAL_VISION_FIELD_LIMITS.items():
        text = _packet_text(source, field, limit=limit)
        if text is None:
            continue
        if field == "advancement_policy":
            text = normalize_goal_vision_advancement_policy(text)
        vision_patch[field] = text
        field_usage[field] = len(text)

    if not vision_patch:
        raise ValueError("agent_vision must include at least one bounded vision field")

    path_delta, path_delta_usage = _normalize_goal_path_delta(packet.get("path_delta"))
    field_usage.update(path_delta_usage)

    total_usage = sum(field_usage.values())
    if total_usage > GOAL_VISION_TOTAL_LIMIT:
        raise GoalVisionBudgetError(
            field="total_agent_vision",
            used=total_usage,
            limit=GOAL_VISION_TOTAL_LIMIT,
        )

    todo_delta: list[str] = []
    raw_todo_delta = packet.get("todo_delta")
    if isinstance(raw_todo_delta, list):
        for item in raw_todo_delta[:8]:
            text = _bounded_public_text(field="todo_delta", value=item, limit=80)
            if text:
                todo_delta.append(text)

    validation = (
        dict(packet.get("validation"))
        if isinstance(packet.get("validation"), dict)
        else {}
    )
    validation.update(
        {
            "budget_checked": True,
            "budget_status": "ok",
            "write_correctness_checked": bool(
                validation.get("write_correctness_checked")
            ),
        }
    )

    normalized = {
        "schema_version": GOAL_VISION_REPLAN_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": resolved_agent_id,
        "state": state,
        "vision_patch": vision_patch,
        "todo_delta": todo_delta,
        "vision_budget": {
            "schema_version": "goal_vision_budget_v0",
            "status": "ok",
            "field_limits": {
                **GOAL_VISION_FIELD_LIMITS,
                **GOAL_PATH_DELTA_BUDGET_LIMITS,
            },
            "field_usage": field_usage,
            "total_limit": GOAL_VISION_TOTAL_LIMIT,
            "total_usage": total_usage,
        },
        "validation": validation,
    }
    if path_delta:
        normalized["path_delta"] = path_delta
    return normalized
