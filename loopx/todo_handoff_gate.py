from __future__ import annotations

from enum import Enum
from typing import Any, Iterable

from .todo_contract import (
    TODO_RESUME_KIND_TODO_DONE,
    TODO_STATUS_DEFERRED,
    TODO_STATUS_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_id,
    normalize_todo_no_followup,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
    todo_done_for_status,
)


TODO_HANDOFF_GATE_SCHEMA_VERSION = "todo_handoff_gate_v0"


class HandoffGateState(str, Enum):
    BLOCKING = "blocking"
    CLEARED_WITHOUT_SUCCESSOR = "cleared_without_successor"
    CLEARED_WITH_SUCCESSOR = "cleared_with_successor"
    CLEARED_NO_FOLLOWUP = "cleared_no_followup"
    SUPERSEDED = "superseded"
    DEFERRED = "deferred"


def _todo_status(item: dict[str, Any]) -> str:
    explicit = normalize_todo_status(item.get("status"))
    if explicit:
        return explicit
    return TODO_STATUS_DONE if item.get("done") is True else TODO_STATUS_OPEN


def _todo_done(item: dict[str, Any]) -> bool:
    return item.get("done") is True or todo_done_for_status(_todo_status(item))


def _todo_text(item: dict[str, Any]) -> str:
    return str(item.get("text") or "").strip()


def _successor_todo_ids(
    gate: dict[str, Any],
    *,
    items: list[dict[str, Any]],
) -> list[str]:
    gate_id = normalize_todo_id(gate.get("todo_id"))
    superseded_by = normalize_todo_id(gate.get("superseded_by"))
    successor_ids: list[str] = []
    if superseded_by:
        successor_ids.append(superseded_by)
    if not gate_id:
        return successor_ids

    for item in items:
        if normalize_todo_task_class(
            item.get("task_class"),
            text=_todo_text(item),
            action_kind=item.get("action_kind"),
        ) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        candidate_id = normalize_todo_id(item.get("todo_id"))
        if not candidate_id or candidate_id == gate_id:
            continue
        resume_when = normalize_todo_resume_when(item.get("resume_when")) or ""
        resume_kind, separator, resume_target = resume_when.partition(":")
        candidate_unblocks = normalize_todo_id(item.get("unblocks_todo_id"))
        if (
            candidate_id == superseded_by
            or candidate_unblocks == gate_id
            or (
                separator
                and resume_kind == TODO_RESUME_KIND_TODO_DONE
                and normalize_todo_id(resume_target) == gate_id
            )
        ):
            if candidate_id not in successor_ids:
                successor_ids.append(candidate_id)
    return successor_ids


def _handoff_gate_state(
    gate: dict[str, Any],
    *,
    successor_ids: list[str],
) -> HandoffGateState:
    status = _todo_status(gate)
    if normalize_todo_id(gate.get("superseded_by")):
        return HandoffGateState.SUPERSEDED
    if status == TODO_STATUS_DEFERRED:
        return HandoffGateState.DEFERRED
    if not _todo_done(gate):
        return HandoffGateState.BLOCKING
    if normalize_todo_no_followup(gate.get("no_followup")) is True:
        return HandoffGateState.CLEARED_NO_FOLLOWUP
    if successor_ids:
        return HandoffGateState.CLEARED_WITH_SUCCESSOR
    return HandoffGateState.CLEARED_WITHOUT_SUCCESSOR


def _compact_handoff_gate(
    gate: dict[str, Any],
    *,
    state: HandoffGateState,
    successor_ids: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": TODO_HANDOFF_GATE_SCHEMA_VERSION,
        "gate_state": state.value,
        "index": gate.get("index"),
        "done": _todo_done(gate),
        "status": _todo_status(gate),
        "text": _todo_text(gate),
        "blocks_agent": normalize_todo_blocks_agent(gate.get("blocks_agent")),
        "successor_count": len(successor_ids),
    }
    for key in (
        "todo_id",
        "role",
        "task_class",
        "action_kind",
        "claimed_by",
        "unblocks_todo_id",
        "resume_when",
        "no_followup",
        "superseded_by",
    ):
        value = gate.get(key)
        if value is not None:
            payload[key] = value
    claimed_by = normalize_todo_claimed_by(payload.get("claimed_by"))
    if claimed_by:
        payload["claimed_by"] = claimed_by
    unblocks_todo_id = normalize_todo_id(payload.get("unblocks_todo_id"))
    if unblocks_todo_id:
        payload["unblocks_todo_id"] = unblocks_todo_id
    superseded_by = normalize_todo_id(payload.get("superseded_by"))
    if superseded_by:
        payload["superseded_by"] = superseded_by
    if successor_ids:
        payload["successor_todo_ids"] = successor_ids
    return {key: value for key, value in payload.items() if value not in (None, "")}


def build_todo_handoff_gate_states(items: Iterable[Any]) -> list[dict[str, Any]]:
    """Project blocks_agent todos into a small gate state machine."""

    todo_items = [item for item in items if isinstance(item, dict)]
    gates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in todo_items:
        blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
        if not blocks_agent:
            continue
        identity = (str(item.get("todo_id") or ""), _todo_text(item))
        if identity in seen:
            continue
        seen.add(identity)
        successor_ids = _successor_todo_ids(item, items=todo_items)
        gates.append(
            _compact_handoff_gate(
                item,
                state=_handoff_gate_state(item, successor_ids=successor_ids),
                successor_ids=successor_ids,
            )
        )
    return sorted(
        gates,
        key=lambda item: (
            int(item.get("index") or 999999),
            str(item.get("todo_id") or ""),
        ),
    )
