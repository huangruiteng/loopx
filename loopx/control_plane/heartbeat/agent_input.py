"""Agent-facing projection for a generated thin heartbeat prompt."""

from __future__ import annotations

from typing import Any


HEARTBEAT_AGENT_INPUT_SCHEMA_VERSION = "heartbeat_agent_input_v1"
_AGENT_BUDGET_FIELDS = (
    "mode",
    "budget_char_count",
    "max_chars",
    "within_budget",
)


def _require_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"heartbeat agent input requires non-empty {field}")
    return value


def _project_interface_budget(payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("interface_budget")
    if not isinstance(source, dict):
        raise ValueError("heartbeat agent input requires interface_budget")
    projected = {field: source.get(field) for field in _AGENT_BUDGET_FIELDS}
    if not isinstance(projected["mode"], str):
        raise ValueError("heartbeat agent input requires interface_budget.mode")
    for field in ("budget_char_count", "max_chars"):
        if not isinstance(projected[field], int):
            raise ValueError(f"heartbeat agent input requires interface_budget.{field}")
    if not isinstance(projected["within_budget"], bool):
        raise ValueError(
            "heartbeat agent input requires interface_budget.within_budget"
        )
    return projected


def project_heartbeat_agent_input(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields needed to install or execute one thin heartbeat.

    The builder payload is intentionally richer because upgrade, diagnostics,
    and Markdown rendering consume its generator metadata.  The thin JSON CLI
    surface is an Agent input, so commands and policy already embedded in the
    task body must not be duplicated beside it.
    """

    if payload.get("thin") is not True:
        raise ValueError("heartbeat agent input projection requires thin mode")
    ok = payload.get("ok")
    if not isinstance(ok, bool):
        raise ValueError("heartbeat agent input requires boolean ok")

    projected: dict[str, Any] = {
        "schema_version": HEARTBEAT_AGENT_INPUT_SCHEMA_VERSION,
        "ok": ok,
        "goal_id": _require_string(payload, "goal_id"),
    }
    agent_id = payload.get("agent_id")
    if agent_id is not None and not isinstance(agent_id, str):
        raise ValueError("heartbeat agent input requires string or null agent_id")
    if agent_id:
        projected["agent_id"] = agent_id

    if ok:
        projected["task_body"] = _require_string(payload, "task_body")
        projected["interface_budget"] = _project_interface_budget(payload)
        turn_instance_id = payload.get("turn_instance_id")
        if turn_instance_id is not None:
            if not isinstance(turn_instance_id, str) or not turn_instance_id:
                raise ValueError(
                    "heartbeat agent input requires non-empty turn_instance_id"
                )
            projected["turn_instance_id"] = turn_instance_id
        if payload.get("bootstrap") is True:
            projected["bootstrap"] = True
        return projected

    projected["error"] = _require_string(payload, "error")
    return projected
