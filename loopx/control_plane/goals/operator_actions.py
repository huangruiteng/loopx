from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Any

from ..effect_runtime import EffectRuntimeRejected, effect_runtime_result
from ...registry import registry_goals
from .activation import GoalActivationState, goal_activation_state
from .activation_service import _source_and_target


GOAL_ACTION_PROJECTION_REQUEST_SCHEMA_VERSION = (
    "loopx_goal_action_projection_request_v1"
)
GOAL_ACTION_CATALOG_SCHEMA_VERSION = "loopx_goal_action_catalog_v1"


def _goal(payload: Mapping[str, Any], goal_id: str) -> Mapping[str, Any]:
    goal = next(
        (
            item
            for item in registry_goals(dict(payload))
            if str(item.get("id") or "") == goal_id
        ),
        None,
    )
    if goal is None:
        raise ValueError(f"goal id not found in registry: {goal_id}")
    return goal


def build_goal_action_catalog(
    *,
    registry_path: Path,
    goal_id: str,
    operator_gate_required: bool = False,
    runtime_root_override: str | None = None,
) -> dict[str, Any]:
    """Adapt one stable registry snapshot into the TS-owned action catalog."""

    normalized_goal_id = str(goal_id or "").strip()
    if not normalized_goal_id:
        raise ValueError("goal id is required")
    requested_registry = Path(registry_path).expanduser().resolve()
    requested_payload = json.loads(requested_registry.read_text(encoding="utf-8"))
    requested_goal = _goal(requested_payload, normalized_goal_id)
    current_state = goal_activation_state(requested_goal)
    target_state = (
        GoalActivationState.STOPPED
        if current_state is GoalActivationState.ACTIVE
        else GoalActivationState.ACTIVE
    )
    authority_route = _source_and_target(
        registry_path=requested_registry,
        goal_id=normalized_goal_id,
        target_state=target_state,
        runtime_root_override=runtime_root_override,
    )
    source_bytes = authority_route.source_registry.read_bytes()
    source_payload = json.loads(source_bytes)
    source_state = goal_activation_state(_goal(source_payload, normalized_goal_id))
    fingerprint = hashlib.sha256(source_bytes).hexdigest()
    try:
        result = effect_runtime_result(
            "goal.operator_actions.project",
            {
                "schema_version": GOAL_ACTION_PROJECTION_REQUEST_SCHEMA_VERSION,
                "goal_id": normalized_goal_id,
                "activation_state": source_state.value,
                "state_fingerprint": fingerprint,
                "operator_gate_required": bool(operator_gate_required),
            },
        )
    except EffectRuntimeRejected as exc:
        raise ValueError(str(exc)) from None
    if not isinstance(result, Mapping) or (
        result.get("schema_version") != GOAL_ACTION_CATALOG_SCHEMA_VERSION
    ):
        raise RuntimeError("TypeScript Goal action catalog shape mismatch")
    actions = result.get("actions")
    if not isinstance(actions, list) or not all(
        isinstance(item, Mapping) for item in actions
    ):
        raise RuntimeError("TypeScript Goal action list shape mismatch")
    return dict(result)


def render_goal_action_catalog_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Actions",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- goal: `{payload.get('goal_id')}`",
        f"- activation_state: `{payload.get('activation_state')}`",
    ]
    actions = payload.get("actions")
    if isinstance(actions, list):
        lines.extend(["", "## Available actions", ""])
        for action in actions:
            if isinstance(action, Mapping):
                lines.append(
                    f"- `{action.get('action_id')}` — {action.get('label')}"
                )
    if payload.get("error"):
        lines.extend(["", f"Error: {payload.get('error')}"])
    return "\n".join(lines).rstrip() + "\n"
