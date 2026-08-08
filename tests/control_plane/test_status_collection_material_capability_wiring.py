from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane import status_collection
from loopx.control_plane.agents.management_projection import (
    build_agent_management_projection,
)
from loopx.control_plane.runtime.status_projection_cache import (
    status_projection_cache_key,
)


GOAL_ID = "material-capability-fixture"
AGENT_ID = "agent-reviewer"


def _context(tmp_path: Path) -> status_collection.StatusCollectionContext:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    return status_collection.StatusCollectionContext(
        load_registry=lambda _path: {"common_runtime_root": str(runtime_root)},
        resolve_runtime_root=lambda _registry, _override, **_kwargs: runtime_root,
        collect_global_registry_health=lambda **_kwargs: {
            "ok": True,
            "current_registry_is_global": True,
        },
        collect_history=lambda **_kwargs: {
            "goal_count": 1,
            "run_count": 0,
            "goals": [],
        },
        check_contract=lambda **_kwargs: {
            "ok": True,
            "summary": "ok",
            "errors": [],
            "warnings": [],
            "checks": [],
        },
        build_attention_queue=lambda **_kwargs: {"items": [], "item_count": 0},
        build_runtime_summaries=lambda **_kwargs: {
            "run_history": {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "coordination": {"registered_agents": [AGENT_ID]},
                    }
                ]
            },
            "todo_index": {
                "items": [
                    {
                        "role": "agent",
                        "todo_id": "todo_material_review",
                        "goal_id": GOAL_ID,
                        "status": "open",
                        "task_class": "advancement_task",
                        "claimed_by": AGENT_ID,
                        "text": "Review the material-aware handoff.",
                        "handoff_note": {
                            "schema_version": "handoff_note_v0",
                            "handoff_id": "handoff_material_review",
                            "todo_id": "todo_material_review",
                            "goal_id": GOAL_ID,
                            "from_agent": "agent-builder",
                            "to_agent": AGENT_ID,
                            "intent": "independent_review",
                            "summary": "Review the bounded implementation evidence.",
                        },
                    }
                ]
            },
            "agent_material_frontiers": [
                {
                    "schema_version": "agent_material_frontier_v0",
                    "goal_id": GOAL_ID,
                    "agent_id": AGENT_ID,
                    "items": [
                        {
                            "material_id": "runtime-contract",
                            "state": "required_unread",
                            "relation": "required",
                            "purpose": "review the current contract",
                        }
                    ],
                }
            ],
        },
        build_promotion_gate=lambda **_kwargs: {},
        build_status_contract=lambda: {"schema_version": "fixture"},
        build_contract_health_projection=lambda _contract: {},
        build_agent_management_projection=build_agent_management_projection,
        status_control_plane_context_limit=5,
        max_todo_index_items=5,
    )


def _collect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    available_capabilities: Any,
) -> dict[str, Any]:
    monkeypatch.setattr(
        status_collection,
        "collect_runtime_projection_route_diagnostics",
        lambda **_kwargs: {"available": False},
    )
    return status_collection.collect_status(
        registry_path=tmp_path / "registry.json",
        runtime_root_override=None,
        scan_roots=[tmp_path],
        limit=5,
        context=_context(tmp_path),
        goal_id=GOAL_ID,
        available_capabilities=available_capabilities,
    )


def test_status_collection_keeps_material_projection_default_off(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _collect(tmp_path, monkeypatch, available_capabilities=["network"])

    row = payload["agent_management_projection"]["agents"][0]
    assert "material_frontier" not in row
    assert "handoff_note" not in row
    assert "presentation_surfaces" not in payload


def test_status_collection_forwards_material_capability_to_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _collect(
        tmp_path,
        monkeypatch,
        available_capabilities=["network", "material-lifecycle"],
    )

    projection = payload["agent_management_projection"]
    row = projection["agents"][0]
    assert row["material_frontier"]["schema_version"] == (
        "agent_material_handoff_projection_v0"
    )
    assert row["handoff_note"]["schema_version"] == "handoff_note_v1"
    assert projection["source_summary"]["material_frontier_count"] == 1


def test_status_projection_cache_separates_capability_envelopes(
    tmp_path: Path,
) -> None:
    kwargs = {
        "registry_path": tmp_path / "registry.json",
        "runtime_root": tmp_path / "runtime",
        "scan_roots": [tmp_path],
        "limit": 5,
        "include_task_graph": False,
        "goal_id": GOAL_ID,
    }

    default_key = status_projection_cache_key(**kwargs)
    material_key = status_projection_cache_key(
        **kwargs,
        available_capabilities=["material_lifecycle"],
    )
    material_alias_key = status_projection_cache_key(
        **kwargs,
        available_capabilities=[
            "network",
            "material-lifecycle",
            "material_lifecycle",
        ],
    )
    material_reordered_key = status_projection_cache_key(
        **kwargs,
        available_capabilities=["material_lifecycle", "network"],
    )

    assert default_key != material_key
    assert material_key != material_alias_key
    assert material_alias_key == material_reordered_key
