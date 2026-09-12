from __future__ import annotations

import shlex
from collections.abc import Mapping
from typing import Any

from ..agents.capability_gate import runtime_capabilities_for_cli_projection
from ..scheduler.execution_context import (
    SchedulerExecutionContextResolution,
    render_scheduler_execution_args,
)
from ..todos.contract import normalize_todo_id
from .action_selection_contract import action_portfolio_requires_explicit_selection


RUNTIME_CAPABILITY_REENTRY_SCHEMA_VERSION = "runtime_capability_reentry_v0"


def build_runtime_capability_reentry_packet(
    payload: Mapping[str, Any],
    *,
    available_capabilities: Any,
    scheduler_execution_context: (
        Mapping[str, Any] | SchedulerExecutionContextResolution | None
    ),
    turn_instance_id: str | None = None,
    runtime_root: str | None = None,
) -> dict[str, Any] | None:
    """Project verified runtime-capability re-entry without persisting a grant."""

    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), Mapping)
        else {}
    )
    # An empty gap has no re-entry work; avoid a runtime hop on the healthy path.
    if not capability_gate.get("repair_missing"):
        return None

    try:
        scheduler_args = shlex.split(
            render_scheduler_execution_args(
                scheduler_execution_context=scheduler_execution_context,
            )
        )
    except ValueError:
        return None
    if not scheduler_args:
        return None

    selected_todo = (
        payload.get("selected_todo")
        if isinstance(payload.get("selected_todo"), Mapping)
        else {}
    )
    goal_id = str(payload.get("goal_id") or "<GOAL_ID>")
    agent_identity = (
        payload.get("agent_identity")
        if isinstance(payload.get("agent_identity"), Mapping)
        else {}
    )
    agent_id = str(agent_identity.get("agent_id") or "").strip()
    base_args = [
        "loopx",
        *(
            ["--runtime-root", str(runtime_root)]
            if str(runtime_root or "").strip()
            else []
        ),
        "--format",
        "json",
        "quota",
        "should-run",
        "--goal-id",
        goal_id,
    ]
    if agent_id:
        base_args.extend(["--agent-id", agent_id])
    if turn_instance_id:
        base_args.extend(["--turn-instance-id", turn_instance_id])
    from ..effect_runtime import effect_runtime_result

    receipt = payload.get("heartbeat_receipt") or {}
    identity = receipt.get("settlement_identity") or {}
    response = effect_runtime_result("agent.capability_gate.evaluate", {
        "schema_version": "capability_gate_request_v0",
        "operation": "reentry",
        "gate": dict(capability_gate),
        "available": runtime_capabilities_for_cli_projection(available_capabilities),
        "selection_required": action_portfolio_requires_explicit_selection(payload),
        "selected_todo_id": normalize_todo_id(selected_todo.get("todo_id")),
        "receipt_todo_id": normalize_todo_id(identity.get("todo_id")),
        "command_prefix": base_args,
        "scheduler_args": scheduler_args,
    })
    if not isinstance(response, dict) or response.get("schema_version") != "capability_gate_result_v0":
        raise TypeError("invalid typed capability re-entry result")
    result = response["result"]
    if result is None:
        return None
    for candidate in result["candidates"]:
        candidate["command"] = shlex.join(candidate.pop("command_argv"))
    return result
