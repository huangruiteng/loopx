"""Per-turn evidence from Core, scoped before any Goal is read."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from .chat_manager import manager_model_config
from .chat_manager_details import read_manager_goal_details
from .chat_manager_history import read_manager_delivery_history
from .goal_portfolio import build_goal_portfolio
from .chat import redact_local_paths


def manager_authorization_scope_id(goal_ids: list[str]) -> str:
    """Opaque identity for the exact external Goal evidence scope."""
    normalized = sorted(set(goal_ids))
    return hashlib.sha256(
        json.dumps(normalized, separators=(",", ":")).encode()
    ).hexdigest()


def manager_turn_context(
    registry_path: Path | None,
    session: dict[str, Any],
    runtime_root: Path,
    *,
    authorized_goal_ids: list[str] | None = None,
) -> dict[str, Any]:
    owner_scope = session.get("channel_id") == "manager"
    scope = None if owner_scope else authorized_goal_ids
    if not owner_scope and not scope:
        return unavailable_manager_context("external_authorization_unavailable")
    if registry_path is None:
        return unavailable_manager_context("registry_unavailable")
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
                if isinstance(goal, dict) and (
                    owner_scope or goal.get("id") in (scope or [])
                ):
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
        history = read_manager_delivery_history(runtime_root, row["goal_id"])
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
                "recent_delivery_history": history,
                "current_todos": read_manager_goal_details(
                    registry_path, runtime_root, row["goal_id"], owner_scope=owner_scope,
                    completed_todo_ids={r["todo_id"] for r in history["deliveries"]},
                ),
            }
        )
    result = {
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
    result["portfolio_snapshot_id"] = result["snapshot_id"]
    result["collection_completed_at"] = datetime.now(timezone.utc).isoformat()
    result["snapshot_id"] = "sha256:" + hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()
    if not owner_scope:
        result["authorization_scope_id"] = manager_authorization_scope_id(scope or [])
    return result


def unavailable_manager_context(reason: str) -> dict[str, Any]:
    return {
        "schema_version": "manager_turn_context_v1",
        "coverage": {"discovered": None, "verified": 0, "complete": False},
        "goals": [],
        "warnings": [reason],
    }


def collect_manager_turn_context(
    registry_path: Path | None,
    session: dict[str, Any],
    runtime_root: Path,
    scope_resolver: Callable[[dict[str, Any]], list[str] | None] | None = None,
) -> dict[str, Any]:
    if session.get("channel_id") == "manager":
        return manager_turn_context(registry_path, session, runtime_root)

    def resolve() -> list[str] | None:
        try:
            scope = scope_resolver(session) if scope_resolver else None
            if not isinstance(scope, list) or any(
                not isinstance(g, str) for g in scope
            ):
                return None
            return sorted(set(scope))
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            return None

    before = resolve()
    context = manager_turn_context(
        registry_path,
        session,
        runtime_root,
        authorized_goal_ids=before,
    )
    if before != resolve():
        return unavailable_manager_context("external_authorization_changed")
    return context
