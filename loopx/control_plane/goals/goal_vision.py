from __future__ import annotations

from typing import Any

from ...feedback import validate_public_safe_text


GOAL_VISION_REPLAN_SCHEMA_VERSION = "goal_vision_replan_contract_v0"
GOAL_VISION_BUDGET_ERROR = "vision_budget_exceeded"

GOAL_VISION_FIELD_LIMITS: dict[str, int] = {
    "vision_summary": 420,
    "role_scope": 280,
    "acceptance_summary": 420,
    "replan_trigger_summary": 240,
    "dreaming_policy": 240,
    "last_patch_summary": 240,
}
GOAL_VISION_TOTAL_LIMIT = 1200
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

    state = _bounded_public_text(
        field="state",
        value=packet.get("state") or "vision_patch_proposed",
        limit=80,
    )
    vision_patch: dict[str, str] = {}
    field_usage: dict[str, int] = {}
    for field, limit in GOAL_VISION_FIELD_LIMITS.items():
        text = _packet_text(source, field, limit=limit)
        if text is None:
            continue
        vision_patch[field] = text
        field_usage[field] = len(text)

    if not vision_patch:
        raise ValueError("agent_vision must include at least one bounded vision field")

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

    return {
        "schema_version": GOAL_VISION_REPLAN_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": resolved_agent_id,
        "state": state,
        "vision_patch": vision_patch,
        "todo_delta": todo_delta,
        "vision_budget": {
            "schema_version": "goal_vision_budget_v0",
            "status": "ok",
            "field_limits": dict(GOAL_VISION_FIELD_LIMITS),
            "field_usage": field_usage,
            "total_limit": GOAL_VISION_TOTAL_LIMIT,
            "total_usage": total_usage,
        },
        "validation": validation,
    }
