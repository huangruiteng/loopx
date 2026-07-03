from __future__ import annotations

import re
from typing import Any


DEFAULT_MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE = 12
DEFAULT_MONITOR_SIGNAL_WAITING_ON = "monitor_signal"
DEFAULT_MONITOR_DISPLAY_STOP_CONDITION = (
    "stop until a material monitor transition, regression, or concrete blocker appears"
)
TODO_PROJECTION_VIEW_SCHEMA_VERSION = "todo_projection_view_v0"
TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION = "todo_projection_detail_pointer_v0"
PROJECT_ASSET_TODO_PROJECTION_GAP_SCHEMA_VERSION = "project_asset_todo_projection_gap_v0"
PROJECT_ASSET_HANDOFF_STATE_TRACE_CHECK_KEYS = (
    "project_asset_backed",
    "same_source_should_run",
    "handoff_has_next_action",
    "handoff_has_stop_condition",
    "handoff_sanitized_surface",
)
LOCAL_PATH_SURFACE_PATTERN = re.compile(
    r"(?<!<)/(?:Users|Volumes|var/folders|tmp|private/tmp)/[^\s`'\"<>]+"
)
SECRET_LIKE_SURFACE_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+[a-z0-9._~+/=-]{16,}|"
    r"(?<![a-z0-9_])(?:ak|sk)[-_=:][a-z0-9_=-]{10,}|"
    r"\btoken\s*[=:]\s*[^\s`'\"<>]{12,})"
)


def _compact_text(text: str, *, limit: int) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def project_asset_public_safe_compact_text(value: Any, *, limit: int = 220) -> str | None:
    text = _compact_text(str(value or ""), limit=limit)
    if not text:
        return None
    if LOCAL_PATH_SURFACE_PATTERN.search(text) or SECRET_LIKE_SURFACE_PATTERN.search(text):
        return None
    return text


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


def project_asset_quota_summary(quota: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(quota, dict):
        return None
    summary: dict[str, Any] = {
        "compute": quota.get("compute"),
        "state": quota.get("state"),
        "spent_slots": quota.get("spent_slots"),
        "allowed_slots": quota.get("allowed_slots"),
    }
    if quota.get("reason"):
        summary["reason"] = _compact_text(str(quota.get("reason") or ""), limit=220)
    return summary


def project_asset_latest_validation(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    signal: dict[str, Any] = {}
    for field in ("generated_at", "classification"):
        value = run.get(field)
        if value:
            signal[field] = value
    summary = run.get("health_check") or run.get("recommended_action")
    if summary:
        signal["summary"] = _compact_text(str(summary), limit=260)
    return signal or None


def project_asset_summary_is_public_safe(project_asset: dict[str, Any]) -> bool:
    text = repr(project_asset)
    return not LOCAL_PATH_SURFACE_PATTERN.search(text) and not SECRET_LIKE_SURFACE_PATTERN.search(text)


def project_asset_handoff_check_projection(item: dict[str, Any]) -> dict[str, Any] | None:
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return None

    quota = project_asset.get("quota") if isinstance(project_asset.get("quota"), dict) else {}
    if not quota and isinstance(item.get("quota"), dict):
        quota = item["quota"]

    next_action = str(project_asset.get("next_action") or "").strip()
    item_action = str(item.get("recommended_action") or "").strip()
    stop_condition = str(project_asset.get("stop_condition") or "").strip()
    quota_state = str(quota.get("state") or "").strip()
    waiting_on = str(item.get("waiting_on") or "").strip()
    codex_ready = waiting_on == "codex" and quota_state == "eligible"
    checks = {
        "project_asset_backed": True,
        "same_source_should_run": bool(
            quota and next_action and (not item_action or item_action == next_action)
        ),
        "codex_ready": codex_ready,
        "handoff_has_next_action": bool(next_action),
        "handoff_has_stop_condition": bool(stop_condition),
        "handoff_sanitized_surface": project_asset_summary_is_public_safe(project_asset),
    }
    return {
        "checks": checks,
        "codex_ready": codex_ready,
        "quota_state": quota_state or "unknown",
        "state_trace_ready": all(
            checks[key] for key in PROJECT_ASSET_HANDOFF_STATE_TRACE_CHECK_KEYS
        ),
    }


def project_asset_next_safe_command(agent_command: str | None) -> str | None:
    if not agent_command:
        return None
    return project_asset_public_safe_compact_text(agent_command, limit=320)


def build_project_asset(
    *,
    status: str,
    waiting_on: str,
    recommended_action: str,
    operator_question: str | None,
    agent_command: str | None,
    missing_gates: list[str] | None,
    next_handoff_condition: str | None,
) -> dict[str, Any]:
    asset = {
        "owner": project_asset_owner(waiting_on),
        "gate": project_asset_gate(
            waiting_on=waiting_on,
            operator_question=operator_question,
            missing_gates=missing_gates,
            status=status,
        ),
        "support_mode": project_asset_support_mode(
            waiting_on=waiting_on,
            operator_question=operator_question,
            missing_gates=missing_gates,
            status=status,
            recommended_action=recommended_action,
            agent_command=agent_command,
        ),
        "next_action": recommended_action,
        "stop_condition": project_asset_stop_condition(
            waiting_on=waiting_on,
            next_handoff_condition=next_handoff_condition,
            agent_command=agent_command,
        ),
    }
    next_safe_command = project_asset_next_safe_command(agent_command)
    if next_safe_command:
        asset["next_safe_command"] = next_safe_command
    return asset


def project_asset_todo_projection_metadata(
    *,
    role: str | None,
    item_limit: int,
    deferred_item_limit: int,
) -> dict[str, dict[str, Any]]:
    todo_role = str(role or "").strip().lower()
    if todo_role == "user":
        canonical_source = "attention_queue.items[].user_todos"
    elif todo_role == "agent":
        canonical_source = "attention_queue.items[].agent_todos"
    else:
        canonical_source = "attention_queue.items[].{user_todos,agent_todos}"
    return {
        "projection_view": {
            "schema_version": TODO_PROJECTION_VIEW_SCHEMA_VERSION,
            "view": "project_asset_overview",
            "truth": "derived",
            "canonical_source": canonical_source,
            "item_limit": item_limit,
            "deferred_item_limit": deferred_item_limit,
        },
        "detail_pointer": {
            "schema_version": TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
            "cold_path": "loopx status --format json",
            "active_state_source": "registry goal state_file",
            "full_list_included": False,
        },
    }


def project_asset_todo_projection_gap(
    *,
    user_todos: dict[str, Any] | None,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    missing_roles: list[str] = []
    if not isinstance(user_todos, dict):
        missing_roles.append("user")
    if not isinstance(agent_todos, dict):
        missing_roles.append("agent")
    if not missing_roles:
        return None
    return {
        "schema_version": PROJECT_ASSET_TODO_PROJECTION_GAP_SCHEMA_VERSION,
        "kind": "project_asset_todo_projection_gap",
        "missing_roles": missing_roles,
        "source": "active_state_todo_projection",
        "recommended_action": (
            "add parseable User Todo / Agent Todo sections or repair the active state_file "
            "before treating this project_asset as first-screen complete"
        ),
    }
