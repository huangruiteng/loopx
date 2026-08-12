from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_state_refresh_output_projections(
    *,
    record: dict[str, Any],
    registry_path: Path,
    runtime_root: Path,
    project: Path | None,
    json_path: Path,
    markdown_path: Path,
    index_path: Path,
    dry_run: bool,
    autonomous_replan_recorded_requested: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Project one refresh record into its compact index and CLI response."""

    record_state = record.get("state") if isinstance(record.get("state"), dict) else {}
    record_frontmatter = record_state.get("frontmatter") or {}
    index_record = {
        field: record[field]
        for field in (
            "generated_at", "goal_id", "classification", "recommended_action",
            "recommended_action_source", "health_check",
        )
    }
    index_record.update({
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "state": {
            "sha256_16": record_state.get("sha256_16"),
            "frontmatter": {"updated_at": record_frontmatter.get("updated_at")},
        },
        "runtime_projection_route": record["runtime_projection_route"],
    })
    for field in (
        "delivery_batch_scale",
        "delivery_outcome",
        "delivery_workspace",
        "settlement_identity",
        "turn_instance_id",
        "todo_id",
    ):
        if field in record:
            index_record[field] = record[field]

    replan_ack = record.get("autonomous_replan_ack") or {}
    if autonomous_replan_recorded_requested:
        index_record["autonomous_replan_ack"] = replan_ack
        if replan_ack.get("requested_classification"):
            index_record["requested_classification"] = replan_ack["requested_classification"]

    agent_vision = record.get("agent_vision")
    if isinstance(agent_vision, dict):
        index_record["agent_vision"] = {
            field: agent_vision.get(field)
            for field in (
                "schema_version", "agent_id", "state", "vision_patch",
                "todo_delta", "vision_budget",
            )
        }
        if isinstance(agent_vision.get("path_delta"), dict):
            index_record["agent_vision"]["path_delta"] = agent_vision["path_delta"]

    for field in ("vision_checkpoint", "progress_scope", "agent_id", "agent_lane"):
        if field in record:
            index_record[field] = record[field]

    payload: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "appended": not dry_run,
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "project": str(project) if project else None,
    }
    payload.update({
        field: record.get(field)
        for field in ("goal_id", "classification", "progress_scope", "agent_id", "agent_lane")
    })
    payload.update({
        "autonomous_replan_recorded": bool(replan_ack.get("recorded")),
        "autonomous_replan_recorded_requested": autonomous_replan_recorded_requested,
        "repair_delta_contract": replan_ack.get("delta_contract"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
    })
    payload.update({
        field: record.get(field)
        for field in (
            "agent_vision", "vision_checkpoint", "recommended_action",
            "recommended_action_source", "active_state_next_action_update",
            "generated_at", "health_check",
        )
    })
    payload.update(record)
    return index_record, payload


def append_state_refresh_index(
    index_path: Path,
    index_record: dict[str, Any],
    *,
    turn_effect_result_ok: bool | None = None,
) -> None:
    if turn_effect_result_ok is not None:
        index_record["turn_effect_result_ok"] = turn_effect_result_ok
    with index_path.open("a", encoding="utf-8") as index_file:
        index_file.write(json.dumps(index_record, ensure_ascii=False) + "\n")
