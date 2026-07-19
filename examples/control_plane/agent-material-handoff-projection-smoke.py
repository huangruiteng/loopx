#!/usr/bin/env python3
"""Smoke-test bounded material handoff and agent-management projection."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.agents.management_projection import (  # noqa: E402
    build_agent_management_projection,
)
from loopx.control_plane.agents.material_frontier import (  # noqa: E402
    build_agent_material_frontier,
)
from loopx.control_plane.agents.material_handoff import (  # noqa: E402
    MAX_MATERIAL_HANDOFF_REFS,
    build_material_handoff_note_v1,
    project_material_frontier_for_handoff,
)


GOAL_ID = "material-handoff-fixture"
OTHER_GOAL_ID = "other-material-handoff-fixture"
SOURCE_AGENT = "agent-builder"
SUCCESSOR_AGENT = "agent-reviewer"
SOURCE_TODO = "todo_material_source"
SUCCESSOR_TODO = "todo_material_successor"


def authority_registry() -> dict:
    materials = {
        "design-current": {
            "id": "design-current",
            "revision": "rev-2",
            "freshness": "current",
            "boundary": "public_safe",
            "gate_status": "registered",
        },
        "design-unread": {
            "id": "design-unread",
            "revision": "rev-1",
            "freshness": "current",
            "boundary": "public",
            "gate_status": "registered",
        },
        "private-runbook": {
            "id": "private-runbook",
            "revision": "rev-1",
            "freshness": "current",
            "boundary": "private_redacted",
            "gate_status": "registered",
        },
        "stale-review": {
            "id": "stale-review",
            "revision": "rev-3",
            "freshness": "stale",
            "boundary": "public",
            "gate_status": "registered",
        },
    }
    return {"project_materials": materials, "topic_authority": {}}


def material_refs() -> list[dict[str, str]]:
    return [
        {
            "material_id": "design-current",
            "relation": "required",
            "purpose": "implement the current contract",
        },
        {"material_id": "design-unread", "relation": "reviewer"},
        {"material_id": "private-runbook", "relation": "required"},
        {"material_id": "stale-review", "relation": "reviewer"},
        {"material_id": "missing-source", "relation": "required"},
    ]


def source_receipt() -> dict:
    return {
        "schema_version": "material_usage_receipt_v0",
        "receipt_id": "receipt_source_current",
        "goal_id": GOAL_ID,
        "agent_id": SOURCE_AGENT,
        "todo_id": SOURCE_TODO,
        "material_id": "design-current",
        "observed_revision": "rev-2",
        "outcome": "used",
        "recorded_at": "2026-07-19T00:00:00Z",
    }


def source_frontier() -> dict:
    return build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=SOURCE_AGENT,
        authority_registry=authority_registry(),
        todos={"todo_id": SOURCE_TODO, "material_refs": material_refs()},
        receipts=[source_receipt()],
        available_boundaries=["private_redacted"],
        generated_at="2026-07-19T00:01:00Z",
    )


def legacy_handoff_note() -> dict:
    return {
        "schema_version": "handoff_note_v0",
        "handoff_id": "handoff_material_successor",
        "todo_id": SUCCESSOR_TODO,
        "goal_id": GOAL_ID,
        "from_agent": SOURCE_AGENT,
        "to_agent": SUCCESSOR_AGENT,
        "intent": "independent_review",
        "summary": "Review the bounded implementation evidence.",
        "evidence_refs": [f"todo:{SOURCE_TODO}:evidence"],
    }


def assert_bounded_handoff() -> dict:
    frontier = source_frontier()
    compact = project_material_frontier_for_handoff(frontier)
    assert compact["schema_version"] == "agent_material_handoff_projection_v0", compact
    assert compact["material_ref_count"] == 5, compact
    assert len(compact["material_refs"]) == MAX_MATERIAL_HANDOFF_REFS, compact
    assert compact["material_refs_truncated"] is True, compact
    assert compact["summary"] == frontier["summary"], (compact, frontier)

    note = build_material_handoff_note_v1(legacy_handoff_note(), frontier)
    assert note["schema_version"] == "handoff_note_v1", note
    assert note["material_refs"] == compact["material_refs"], note
    rendered = json.dumps(note, sort_keys=True)
    for forbidden in (
        "receipt_source_current",
        "receipt_ref",
        "observed_revision",
        "required_revision",
        "boundary",
        "gate_status",
        "authority_registry",
        "available_boundaries",
    ):
        assert forbidden not in rendered, (forbidden, note)
    return note


def assert_successor_rebuilds_frontier(note: dict) -> dict:
    successor = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=SUCCESSOR_AGENT,
        authority_registry=authority_registry(),
        todos={"todo_id": SUCCESSOR_TODO, "material_refs": material_refs()},
        handoffs=[note],
        receipts=[source_receipt()],
        generated_at="2026-07-19T00:02:00Z",
    )
    items = {item["material_id"]: item for item in successor["items"]}
    assert successor["summary"]["required_count"] == 5, successor
    assert items["design-current"]["state"] == "required_unread", successor
    assert items["private-runbook"]["state"] == "inaccessible", successor
    assert items["missing-source"]["state"] == "missing", successor
    assert all("receipt_ref" not in item for item in successor["items"]), successor
    return successor


def other_goal_frontier() -> dict:
    return build_agent_material_frontier(
        goal_id=OTHER_GOAL_ID,
        agent_id=SUCCESSOR_AGENT,
        authority_registry={"project_materials": {}},
        todos={
            "todo_id": "todo_other_goal",
            "material_refs": [
                {
                    "material_id": "other-goal-only",
                    "relation": "required",
                }
            ],
        },
        generated_at="2026-07-19T00:03:00Z",
    )


def management_payload(
    *,
    frontiers: list[dict],
    goal_filter: str | None = GOAL_ID,
    goal_ids: list[str] | None = None,
    include_todo: bool = True,
) -> dict:
    payload = {
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "coordination": {"registered_agents": [SUCCESSOR_AGENT]},
                }
                for goal_id in (goal_ids or [GOAL_ID])
            ]
        },
        "todo_index": {
            "items": (
                [
                    {
                        "role": "agent",
                        "todo_id": SUCCESSOR_TODO,
                        "goal_id": GOAL_ID,
                        "status": "open",
                        "task_class": "advancement_task",
                        "action_kind": "independent_review",
                        "claimed_by": SUCCESSOR_AGENT,
                        "text": "Review the material-aware handoff.",
                        "handoff_note": legacy_handoff_note(),
                    }
                ]
                if include_todo
                else []
            )
        },
        "agent_material_frontiers": frontiers,
    }
    if goal_filter:
        payload["goal_filter"] = goal_filter
    return payload


def assert_agent_management_cold_path(successor: dict) -> None:
    payload = management_payload(frontiers=[successor])
    projection = build_agent_management_projection(payload)
    row = projection["agents"][0]
    assert row["agent_id"] == SUCCESSOR_AGENT, row
    assert (
        row["material_frontier"]["schema_version"]
        == "agent_material_handoff_projection_v0"
    ), row
    assert row["material_frontier"]["summary"] == successor["summary"], row
    assert row["handoff_note"]["schema_version"] == "handoff_note_v1", row
    assert row["handoff_note"]["material_refs"] == row["material_frontier"]["material_refs"], row

    other = other_goal_frontier()
    exact = build_agent_management_projection(
        management_payload(frontiers=[successor, other])
    )["agents"][0]
    exact_material_ids = {
        ref["material_id"] for ref in exact["material_frontier"]["material_refs"]
    }
    assert "design-current" in exact_material_ids, exact
    assert "other-goal-only" not in exact_material_ids, exact

    cross_goal = build_agent_management_projection(
        management_payload(frontiers=[other])
    )["agents"][0]
    assert "material_frontier" not in cross_goal, cross_goal
    assert "handoff_note" not in cross_goal, cross_goal

    current_todo = build_agent_management_projection(
        management_payload(
            frontiers=[other, successor],
            goal_filter=None,
            goal_ids=[GOAL_ID, OTHER_GOAL_ID],
        )
    )["agents"][0]
    assert current_todo["material_frontier"]["summary"] == successor["summary"], current_todo

    ambiguous = build_agent_management_projection(
        management_payload(
            frontiers=[successor, other],
            goal_filter=None,
            goal_ids=[GOAL_ID, OTHER_GOAL_ID],
            include_todo=False,
        )
    )["agents"][0]
    assert "material_frontier" not in ambiguous, ambiguous

    payload.pop("agent_material_frontiers")
    legacy = build_agent_management_projection(payload)["agents"][0]
    assert "material_frontier" not in legacy, legacy
    assert "handoff_note" not in legacy, legacy


def main() -> int:
    note = assert_bounded_handoff()
    successor = assert_successor_rebuilds_frontier(note)
    assert_agent_management_cold_path(successor)
    print("agent-material-handoff-projection-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
