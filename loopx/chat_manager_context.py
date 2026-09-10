"""Per-turn evidence from Core, scoped before any Goal is read."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .chat_manager import manager_model_config
from .goal_portfolio import build_goal_portfolio
from .chat import redact_local_paths


def manager_turn_context(
    registry_path: Path | None, session: dict[str, Any], runtime_root: Path
) -> dict[str, Any]:
    owner_scope = session.get("channel_id") == "manager"
    scope = None if owner_scope else [str(session.get("goal_id") or "")]
    if registry_path is None:
        return {
            "schema_version": "manager_turn_context_v1",
            "coverage": {"discovered": None, "verified": 0},
            "goals": [],
            "warnings": ["registry_unavailable"],
        }
    portfolio = build_goal_portfolio(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
        goal_ids=scope,
        limit=128,
    )
    labels: dict[str, str] = {}
    try:
        raw = registry_path.read_bytes()
        if (
            portfolio.get("inventory_revision")
            == "sha256:" + hashlib.sha256(raw).hexdigest()
        ):
            for goal in json.loads(raw).get("goals", []):
                if isinstance(goal, dict) and (owner_scope or goal.get("id") in scope):
                    labels[str(goal.get("id"))] = redact_local_paths(
                        str(
                            goal.get("display_name")
                            or goal.get("domain")
                            or goal.get("id")
                            or ""
                        ),
                        protected_paths=[Path(str(goal.get("repo") or "."))],
                    )[:100]
    except (OSError, ValueError, TypeError):
        pass
    rows = []
    for row in portfolio.get("goals", []):
        rows.append(
            {
                "goal_id": row["goal_id"],
                "host_id": row.get("host_id"),
                "project_id": row.get("project_id"),
                "agent_coverage": row.get("agent_coverage"),
                "description": labels.get(row["goal_id"]),
                "quality": row.get("quality"),
                "progress": row.get("progress", "unknown"),
                "source": row.get("source"),
                "warnings": row.get("warnings", []),
                "agents": [
                    {
                        "agent_id": a.get("agent_id"),
                        "source_verified": a.get("source_verified"),
                        "waiting_on": a.get("waiting_on"),
                        "owner_gate_ids": a.get("owner_gate_ids", []),
                        "todo_count_in_projection": len(a.get("todos", [])),
                    }
                    for a in row.get("agents", [])
                ],
                "deliveries": row.get("deliveries", []),
            }
        )
    return {
        "schema_version": "manager_turn_context_v1",
        "scope": "owner_global" if owner_scope else "external_goal_scope",
        "model_defaults": manager_model_config(),
        "snapshot_id": portfolio.get("snapshot_id"),
        "collected_at": portfolio.get("collected_at"),
        "collection_completed_at": portfolio.get("collection_completed_at"),
        "coverage": portfolio.get("coverage"),
        "goals": rows,
        "warnings": portfolio.get("warnings", []),
        "limitations": portfolio.get("limitations", []),
    }
