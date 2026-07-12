from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from ...agent_registry import load_goal_from_registry
from ...explore_graph import compact_explore_graph_policy


EXPLORE_GRAPH_ACTIVATION_SCHEMA_VERSION = "loopx_explore_graph_activation_v0"

def sync_explore_graph_after_material_refresh(
    *,
    registry_path: Path,
    goal_id: str,
    agent_id: str | None = None,
    project: Path | None = None,
    state_file: Path | None = None,
    syncer: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Flush an enabled graph after the goal-level refresh transaction.

    Explore Graph activation is independent from Explore Harness planning.  A
    configured graph reuses the existing idempotent projection/sink adapter;
    disabled or absent policy performs no graph reads or writes.
    """

    goal = load_goal_from_registry(registry_path, goal_id)
    policy = compact_explore_graph_policy(
        goal.get("explore_graph") if isinstance(goal, dict) else None
    )
    base = {
        "ok": True,
        "schema_version": EXPLORE_GRAPH_ACTIVATION_SCHEMA_VERSION,
        "goal_id": goal_id,
        "enabled": policy["enabled"],
        "trigger": "material_refresh",
    }
    if goal is None:
        return {**base, "ok": False, "status": "goal_not_found"}
    if not policy["enabled"]:
        return {**base, "status": "disabled"}

    if syncer is None:
        from ...presentation.sinks.lark.explore_results import (
            sync_issue_fix_explore_on_material_change,
        )

        syncer = sync_issue_fix_explore_on_material_change

    try:
        result = syncer(
            registry_path=registry_path,
            goal_id=goal_id,
            agent_id=agent_id,
            project=project,
            state_file=state_file,
            execute=True,
        )
    except Exception as exc:
        return {
            **base,
            "ok": False,
            "status": "sync_failed",
            "error_type": type(exc).__name__,
        }

    projection = (
        result.get("projection")
        if isinstance(result.get("projection"), Mapping)
        else {}
    )
    return {
        **base,
        "ok": result.get("ok") is True,
        "status": str(result.get("status") or "unknown"),
        "applicable": projection.get("applicable"),
        "material_change": projection.get("material_change"),
        "material_event_count": projection.get("material_event_count"),
        "appended_event_count": projection.get("appended_event_count"),
        "needs_row_sync": result.get("needs_row_sync"),
        "needs_visual_sync": result.get("needs_visual_sync"),
        "semantic_digest": result.get("semantic_digest"),
    }
