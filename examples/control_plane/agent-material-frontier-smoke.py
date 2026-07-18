#!/usr/bin/env python3
"""Smoke-test the read-only agent material frontier contract."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.agents.material_frontier import (  # noqa: E402
    build_agent_material_frontier,
)


GOAL_ID = "material-frontier-fixture"
AGENT_ID = "agent-builder"
SUCCESSOR_ID = "agent-reviewer"
TODO_ID = "todo_material_frontier"


def authority_registry() -> dict:
    return {
        "project_materials": {
            "design-contract": {
                "id": "design-contract",
                "revision": "rev-2",
                "freshness": "current",
                "boundary": "public_safe",
                "gate_status": "registered",
                "source_ref_redacted": "registered-public-source",
            },
            "private-runbook": {
                "id": "private-runbook",
                "revision": "rev-1",
                "freshness": "current",
                "boundary": "private_redacted",
                "gate_status": "registered",
                "source_ref_redacted": "registered-private-source",
            },
            "stale-review": {
                "id": "stale-review",
                "revision": "rev-3",
                "freshness": "stale",
                "boundary": "public",
                "gate_status": "registered",
            },
        },
        "topic_authority": {
            "runtime-design": "design-contract",
        },
    }


def requirements() -> tuple[dict, dict, dict, dict]:
    profile = {
        "agent_id": AGENT_ID,
        "material_topics": ["runtime-design"],
    }
    vision = {
        "vision_id": "vision_material_frontier",
        "material_refs": [
            {
                "material_id": "design-contract",
                "relation": "reviewer",
                "purpose": "review the current contract",
            }
        ],
    }
    todo = {
        "todo_id": TODO_ID,
        "material_refs": [
            {
                "material_id": "design-contract",
                "relation": "required",
                "purpose": "implement the current revision",
            },
            {"material_id": "private-runbook", "relation": "required"},
            {"material_id": "stale-review", "relation": "reviewer"},
            {"material_id": "missing-source", "relation": "required"},
        ],
        "evidence_refs": ["run:evidence-does-not-prove-a-read"],
    }
    handoff = {
        "schema_version": "handoff_note_v1",
        "handoff_id": "handoff_material_frontier",
        "todo_id": TODO_ID,
        "material_refs": copy.deepcopy(todo["material_refs"]),
    }
    return profile, vision, todo, handoff


def receipt(
    *,
    agent_id: str,
    material_id: str,
    observed_revision: str,
    receipt_id: str,
) -> dict:
    return {
        "schema_version": "material_usage_receipt_v0",
        "receipt_id": receipt_id,
        "goal_id": GOAL_ID,
        "agent_id": agent_id,
        "todo_id": TODO_ID,
        "material_id": material_id,
        "relation": "required",
        "observed_revision": observed_revision,
        "outcome": "used",
        "evidence_ref": f"todo:{TODO_ID}:evidence",
        "recorded_at": "2026-07-19T00:00:00Z",
    }


def by_material(frontier: dict) -> dict[str, dict]:
    return {item["material_id"]: item for item in frontier["items"]}


def assert_derivation_and_boundaries() -> dict:
    profile, vision, todo, handoff = requirements()
    receipts = [
        receipt(
            agent_id=AGENT_ID,
            material_id="design-contract",
            observed_revision="rev-2",
            receipt_id="receipt_current",
        ),
        receipt(
            agent_id=AGENT_ID,
            material_id="stale-review",
            observed_revision="rev-3",
            receipt_id="receipt_authority_stale",
        ),
        receipt(
            agent_id=SUCCESSOR_ID,
            material_id="design-contract",
            observed_revision="rev-2",
            receipt_id="receipt_other_agent",
        ),
    ]
    frontier = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=authority_registry(),
        agent_profile=profile,
        todos=[todo],
        vision=vision,
        handoffs=[handoff],
        receipts=receipts,
        generated_at="2026-07-19T00:01:00Z",
    )
    items = by_material(frontier)
    assert frontier["schema_version"] == "agent_material_frontier_v0", frontier
    assert frontier["summary"] == {
        "required_count": 4,
        "current_count": 1,
        "stale_count": 1,
        "missing_count": 1,
        "inaccessible_count": 1,
        "required_unread_count": 0,
    }, frontier
    assert items["design-contract"]["state"] == "current", items
    assert items["design-contract"]["relation"] == "required", items
    assert {binding["kind"] for binding in items["design-contract"]["bound_by"]} == {
        "profile",
        "vision",
        "todo",
        "handoff",
    }, items
    assert items["private-runbook"]["state"] == "inaccessible", items
    assert items["stale-review"]["state"] == "stale", items
    assert items["missing-source"]["state"] == "missing", items
    assert "source_ref_redacted" not in json.dumps(frontier, sort_keys=True), frontier
    assert frontier["truth_contract"] == {
        "authority_is_goal_owned": True,
        "projection_is_read_only": True,
        "introduces_task_runtime": False,
        "grants_cross_agent_authority": False,
        "evidence_log_implies_material_read": False,
        "raw_source_body_recorded": False,
    }, frontier
    return frontier


def assert_revision_lifecycle() -> None:
    _, _, todo, _ = requirements()
    unread = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=authority_registry(),
        todos={
            "todo_id": TODO_ID,
            "material_refs": [todo["material_refs"][0]],
            "evidence_refs": ["run:still-not-a-receipt"],
        },
        receipts=[
            {
                "receipt_id": "evidence_shaped_like_receipt",
                "goal_id": GOAL_ID,
                "agent_id": AGENT_ID,
                "todo_id": TODO_ID,
                "material_id": "design-contract",
                "observed_revision": "rev-2",
                "outcome": "used",
                "recorded_at": "2026-07-19T00:01:30Z",
            }
        ],
        generated_at="2026-07-19T00:02:00Z",
    )
    assert by_material(unread)["design-contract"]["state"] == "required_unread", unread

    current_receipt = receipt(
        agent_id=AGENT_ID,
        material_id="design-contract",
        observed_revision="rev-2",
        receipt_id="receipt_revision_lifecycle",
    )
    current = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=authority_registry(),
        todos={"todo_id": TODO_ID, "material_refs": [todo["material_refs"][0]]},
        receipts=[current_receipt],
        generated_at="2026-07-19T00:03:00Z",
    )
    assert by_material(current)["design-contract"]["state"] == "current", current

    advanced_authority = authority_registry()
    advanced_authority["project_materials"]["design-contract"]["revision"] = "rev-3"
    stale = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=advanced_authority,
        todos={"todo_id": TODO_ID, "material_refs": [todo["material_refs"][0]]},
        receipts=[current_receipt],
        generated_at="2026-07-19T00:04:00Z",
    )
    assert by_material(stale)["design-contract"]["state"] == "stale", stale


def assert_profile_topic_defaults_to_watcher() -> None:
    profile, _, _, _ = requirements()
    frontier = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=authority_registry(),
        agent_profile=profile,
        generated_at="2026-07-19T00:04:30Z",
    )
    item = by_material(frontier)["design-contract"]
    assert item["relation"] == "watcher", item
    assert item["state"] == "required_unread", item
    assert item["bound_by"] == [{"kind": "profile", "ref": AGENT_ID}], item


def assert_handoff_preserves_refs_without_authority_or_receipts() -> None:
    _, _, todo, handoff = requirements()
    source = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry=authority_registry(),
        todos=todo,
        handoffs=handoff,
        receipts=[
            receipt(
                agent_id=AGENT_ID,
                material_id="design-contract",
                observed_revision="rev-2",
                receipt_id="receipt_source_agent",
            )
        ],
        available_boundaries=["private_redacted"],
        generated_at="2026-07-19T00:05:00Z",
    )
    successor = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=SUCCESSOR_ID,
        authority_registry=authority_registry(),
        handoffs=handoff,
        receipts=[],
        available_boundaries=["private_redacted"],
        generated_at="2026-07-19T00:06:00Z",
    )
    assert set(by_material(source)) == set(by_material(successor)), (source, successor)
    assert by_material(successor)["design-contract"]["state"] == "required_unread", successor
    assert by_material(successor)["design-contract"]["required_revision"] == "rev-2", successor
    assert successor["truth_contract"]["grants_cross_agent_authority"] is False, successor


def assert_compact_authority_fails_closed() -> None:
    try:
        build_agent_material_frontier(
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
            authority_registry={"project_material_count": 4},
            todos={"todo_id": TODO_ID, "material_refs": ["design-contract"]},
        )
    except ValueError as exc:
        assert "canonical authority_registry.project_materials" in str(exc), exc
    else:
        raise AssertionError("compact authority summary must not be treated as canonical material truth")

    try:
        build_agent_material_frontier(
            goal_id=GOAL_ID,
            agent_id=AGENT_ID,
            authority_registry=authority_registry(),
            agent_profile={
                "agent_id": AGENT_ID,
                "material_topics": ["unregistered-topic"],
            },
        )
    except ValueError as exc:
        assert "material topic is not registered" in str(exc), exc
    else:
        raise AssertionError("an unknown profile topic must not produce an empty frontier")

    unknown_boundary = build_agent_material_frontier(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        authority_registry={
            "project_materials": {
                "boundary-unknown": {
                    "id": "boundary-unknown",
                    "revision": "rev-1",
                }
            },
            "topic_authority": {},
        },
        todos={
            "todo_id": TODO_ID,
            "material_refs": ["boundary-unknown"],
        },
    )
    assert by_material(unknown_boundary)["boundary-unknown"]["state"] == "inaccessible"


def assert_public_fixture(frontier: dict) -> None:
    rendered = json.dumps(frontier, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "/Users/",
        "/private/",
        "/tmp/",
        "lark" + "office",
        "Authorization",
        "Bearer ",
        "AK=",
        "SK=",
    ):
        assert forbidden not in rendered, forbidden


def main() -> int:
    frontier = assert_derivation_and_boundaries()
    assert_revision_lifecycle()
    assert_profile_topic_defaults_to_watcher()
    assert_handoff_preserves_refs_without_authority_or_receipts()
    assert_compact_authority_fails_closed()
    assert_public_fixture(frontier)
    print("agent-material-frontier-smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
