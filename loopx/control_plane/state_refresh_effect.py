"""Exactly-once Turn effect wrapper for the state refresh writer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..file_lock import exclusive_file_lock
from .turn_effect import (
    find_turn_effect_record,
    normalize_turn_effect_key,
    require_matching_turn_effect,
    turn_effect_input_hash,
)
from .work_items.delivery_batch_scale import require_delivery_batch_scale
from .work_items.delivery_outcome import require_delivery_outcome


def refresh_state_run(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    goal_id: str,
    project: Path | None,
    state_file: Path | None,
    classification: str,
    recommended_action: str | None,
    next_action: str | None = None,
    delivery_batch_scale: str | None = None,
    delivery_outcome: str | None = None,
    delivery_workspace_path: Path | None = None,
    todo_id: str | None = None,
    turn_instance_id: str | None = None,
    agent_id: str | None = None,
    agent_lane: str | None = None,
    progress_scope: str | None = None,
    autonomous_replan_recorded: bool = False,
    repair_delta_kinds: list[str] | None = None,
    agent_vision_packet: dict[str, Any] | None = None,
    merge_agent_vision_patch: bool = False,
    vision_unchanged_reason: str | None = None,
    dry_run: bool,
    sync_global: bool = True,
    turn_effect_key: str | None = None,
) -> dict[str, Any]:
    # Imported lazily so loopx.state_refresh can preserve its public function
    # while this module wraps the already-initialized core writer.
    from .. import state_refresh as state_refresh_core

    normalized_effect_key = normalize_turn_effect_key(turn_effect_key)
    effect_input_hash: str | None = None
    effect_runtime_root: Path | None = None
    safe_effect_goal_id: str | None = None
    if normalized_effect_key is not None:
        safe_effect_goal_id = state_refresh_core.validate_goal_id_path_segment(goal_id)
        effect_registry = state_refresh_core.load_registry(registry_path)
        effect_runtime_root = state_refresh_core.resolve_runtime_root(
            effect_registry,
            runtime_root_override,
        ).expanduser().resolve()
        _registry_goal, effect_project, effect_state_file = (
            state_refresh_core.resolve_goal_state(
                registry=effect_registry,
                goal_id=safe_effect_goal_id,
                project_override=project,
                state_file_override=state_file,
            )
        )
        effect_input_hash = turn_effect_input_hash(
            {
                "registry_path": str(registry_path.expanduser().resolve()),
                "runtime_root": str(effect_runtime_root),
                "goal_id": safe_effect_goal_id,
                "project": (
                    str(effect_project.expanduser().resolve())
                    if effect_project
                    else None
                ),
                "state_file": str(effect_state_file.expanduser().resolve()),
                "classification": classification,
                "recommended_action": recommended_action,
                "next_action": (
                    state_refresh_core.normalize_next_action_text(next_action)
                    if next_action
                    else None
                ),
                "delivery_batch_scale": (
                    require_delivery_batch_scale(delivery_batch_scale).value
                    if delivery_batch_scale
                    else None
                ),
                "delivery_outcome": (
                    require_delivery_outcome(delivery_outcome).value
                    if delivery_outcome
                    else None
                ),
                "delivery_workspace_path": (
                    str(delivery_workspace_path.expanduser().resolve())
                    if delivery_workspace_path
                    else None
                ),
                "todo_id": todo_id,
                "turn_instance_id": turn_instance_id,
                "agent_id": (agent_id or "").strip() or None,
                "agent_lane": (agent_lane or "").strip() or None,
                "progress_scope": state_refresh_core.normalize_progress_scope(
                    progress_scope
                ),
                "autonomous_replan_recorded": autonomous_replan_recorded,
                "repair_delta_kinds": state_refresh_core.normalize_repair_delta_kinds(
                    repair_delta_kinds
                ),
                "agent_vision_packet": agent_vision_packet,
                "merge_agent_vision_patch": merge_agent_vision_patch,
                "vision_unchanged_reason": (
                    state_refresh_core.normalize_vision_unchanged_reason(
                        vision_unchanged_reason
                    )
                ),
                "dry_run": dry_run,
                "sync_global": sync_global,
            }
        )

    def write_once() -> dict[str, Any]:
        return state_refresh_core._refresh_state_run(
            registry_path=registry_path,
            runtime_root_override=runtime_root_override,
            goal_id=goal_id,
            project=project,
            state_file=state_file,
            classification=classification,
            recommended_action=recommended_action,
            next_action=next_action,
            delivery_batch_scale=delivery_batch_scale,
            delivery_outcome=delivery_outcome,
            delivery_workspace_path=delivery_workspace_path,
            todo_id=todo_id,
            turn_instance_id=turn_instance_id,
            agent_id=agent_id,
            agent_lane=agent_lane,
            progress_scope=progress_scope,
            autonomous_replan_recorded=autonomous_replan_recorded,
            repair_delta_kinds=repair_delta_kinds,
            agent_vision_packet=agent_vision_packet,
            merge_agent_vision_patch=merge_agent_vision_patch,
            vision_unchanged_reason=vision_unchanged_reason,
            dry_run=dry_run,
            sync_global=sync_global,
            _turn_effect_key=normalized_effect_key,
            _effect_input_hash=effect_input_hash,
        )

    if normalized_effect_key is None or dry_run:
        return write_once()

    assert effect_runtime_root is not None
    assert safe_effect_goal_id is not None
    index_path = (
        effect_runtime_root
        / "goals"
        / safe_effect_goal_id
        / "runs"
        / "index.jsonl"
    )
    with exclusive_file_lock(
        index_path,
        agent_id=agent_id,
        operation="refresh_state_turn_effect",
    ):
        existing = find_turn_effect_record(index_path, normalized_effect_key)
        if existing is not None:
            assert effect_input_hash is not None
            require_matching_turn_effect(existing, effect_input_hash)
            return {
                "ok": existing.get("turn_effect_result_ok") is not False,
                "dry_run": False,
                "appended": False,
                "idempotent": True,
                "idempotent_replay": True,
                "registry": str(registry_path),
                "runtime_root": str(effect_runtime_root),
                "goal_id": safe_effect_goal_id,
                "classification": existing.get("classification"),
                "generated_at": existing.get("generated_at"),
                "json_path": existing.get("json_path"),
                "markdown_path": existing.get("markdown_path"),
                "index_path": str(index_path),
                "turn_effect_key": normalized_effect_key,
                "effect_input_hash": effect_input_hash,
            }
        return write_once()
