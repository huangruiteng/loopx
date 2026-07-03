from __future__ import annotations

from typing import Any


DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE = 12
DEFAULT_MONITOR_SIGNAL_WAITING_ON = "monitor_signal"
DEFAULT_MONITOR_DISPLAY_STOP_CONDITION = (
    "stop until a material monitor transition, regression, or concrete blocker appears"
)


def completed_todo_archive_warning(
    agent_todos: dict[str, Any] | None,
    *,
    max_active_done_todos: int = DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
) -> dict[str, Any] | None:
    if not isinstance(agent_todos, dict):
        return None
    try:
        done_count = int(agent_todos.get("done_count") or 0)
    except (TypeError, ValueError):
        done_count = 0
    if done_count <= max_active_done_todos:
        return None
    try:
        open_count = int(agent_todos.get("open_count") or 0)
    except (TypeError, ValueError):
        open_count = 0
    return {
        "kind": "completed_agent_todo_archive_required",
        "requires_archive": True,
        "archive_section": "Completed Work Archive",
        "active_done_count": done_count,
        "active_open_count": open_count,
        "max_active_done_count": max_active_done_todos,
        "recommended_action": (
            "move older completed Agent Todo entries into a dedicated Completed Work Archive "
            "until the active Agent Todo section keeps only current open work and a small recent-done tail"
        ),
    }


def project_asset_owner(
    waiting_on: str,
    *,
    monitor_signal_waiting_on: str = DEFAULT_MONITOR_SIGNAL_WAITING_ON,
) -> str:
    if waiting_on == "codex":
        return "codex"
    if waiting_on == "external_evidence":
        return "external_evidence"
    if waiting_on == monitor_signal_waiting_on:
        return monitor_signal_waiting_on
    if waiting_on == "controller":
        return "controller"
    if waiting_on == "user_or_controller":
        return "user_or_controller"
    return waiting_on or "unknown"


def project_asset_gate(
    *,
    waiting_on: str,
    operator_question: str | None,
    missing_gates: list[str] | None,
    status: str,
    monitor_signal_waiting_on: str = DEFAULT_MONITOR_SIGNAL_WAITING_ON,
) -> str:
    if operator_question:
        return "operator_question"
    if missing_gates:
        return str(missing_gates[0])
    if waiting_on in {"user_or_controller", "controller"}:
        return status or waiting_on
    if waiting_on == "external_evidence":
        return "external_evidence"
    if waiting_on == monitor_signal_waiting_on:
        return "none"
    return "none"


def project_asset_stop_condition(
    *,
    waiting_on: str,
    next_handoff_condition: str | None,
    agent_command: str | None,
    monitor_signal_waiting_on: str = DEFAULT_MONITOR_SIGNAL_WAITING_ON,
    monitor_display_stop_condition: str = DEFAULT_MONITOR_DISPLAY_STOP_CONDITION,
) -> str:
    if next_handoff_condition:
        return next_handoff_condition
    if waiting_on == "user_or_controller":
        return "stop until the user or controller decision is recorded"
    if waiting_on == "controller":
        return "stop until the controller or owner resolves this gate"
    if waiting_on == "external_evidence":
        return "stop until external evidence changes"
    if waiting_on == monitor_signal_waiting_on:
        return monitor_display_stop_condition
    if agent_command:
        return "stop if the command fails or needs write, production, or additional approval"
    return "stop if the next action needs reward, gate approval, write control, or production access"


def project_asset_support_mode(
    *,
    waiting_on: str,
    operator_question: str | None,
    missing_gates: list[str] | None,
    status: str,
    recommended_action: str,
    agent_command: str | None,
    monitor_signal_waiting_on: str = DEFAULT_MONITOR_SIGNAL_WAITING_ON,
) -> str:
    surface = " ".join(
        str(value or "")
        for value in (status, recommended_action, agent_command, " ".join(missing_gates or []))
    ).lower()
    if "reward" in surface:
        return "reward_capture"
    if operator_question or missing_gates or waiting_on in {"user_or_controller", "controller"}:
        return "decision_support"
    if waiting_on in {"external_evidence", monitor_signal_waiting_on}:
        return "read_only_observer"
    if agent_command or waiting_on == "codex":
        return "selective_assist"
    return "read_only_observer"
