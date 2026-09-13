"""Fixture smoke for the derived Goal artifact lifecycle projection.

Proves milestone, guard and next-transition derivation from synthetic goal
payloads, including the negative cases the RFC requires: an unreached
milestone, and a blocking guard with no legal transition.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.goals.artifact_lifecycle import (
    GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION,
    GUARD_KIND_EVIDENCE,
    GUARD_KIND_OWNER_DECISION,
    PHASE_CLOSED,
    PHASE_CLOSING,
    PHASE_QUALIFYING,
    PHASE_STARTING,
    PHASE_WAITING_OWNER,
    build_goal_artifact_lifecycle_projection,
)

GOAL_ID = "artifact-lifecycle-fixture"

# Substrings that must never appear in a public projection.
FORBIDDEN_LEAKS = (
    "/Users/",
    "/private/",
    "sk-",
    "ghp_",
    "BEGIN PRIVATE KEY",
    "raw_evidence_body",
)


def assert_no_public_leak(projection: dict) -> None:
    rendered = json.dumps(projection, ensure_ascii=False)
    for token in FORBIDDEN_LEAKS:
        assert token not in rendered, (token, rendered)


def assert_starting_phase_without_work() -> None:
    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        user_todo_summary={"gate_open_items": [], "open_count": 0},
        agent_todo_summary={"open_count": 0},
        run_history={"latest_runs": []},
    )
    assert projection["schema_version"] == (
        GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION
    ), projection
    assert projection["lifecycle_phase"] == PHASE_STARTING, projection
    assert projection["milestones"] == [], projection
    assert projection["guards"] == [], projection
    assert projection["next_transitions"] == [], projection
    assert_no_public_leak(projection)


def assert_declared_milestone_stays_unreached_while_gapped() -> None:
    """A declared marker with an open acceptance gap is not reached."""

    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={
            "id": GOAL_ID,
            "status": "active",
            "acceptance": {"milestones": ["environment_ready", "baseline_pass"]},
        },
        agent_todo_summary={"open_count": 2},
        run_history={"latest_runs": []},
        acceptance_gaps=[
            {"kind": "vision_acceptance_gap", "agent_id": "agent-a"},
        ],
    )
    reached = {item["id"]: item["reached"] for item in projection["milestones"]}
    assert reached == {"environment_ready": False, "baseline_pass": False}, projection
    assert projection["lifecycle_phase"] == PHASE_QUALIFYING, projection
    assert_no_public_leak(projection)


def assert_evidence_milestone_reached_from_run_history() -> None:
    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        agent_todo_summary={"open_count": 1},
        run_history={
            "latest_runs": [
                {
                    "delivery_outcome": "primary_goal_outcome",
                    "delivery_batch_scale": "multi_surface",
                    "evidence_ref": "run:abc123",
                },
                {"delivery_outcome": "surface_only"},
            ]
        },
    )
    assert len(projection["milestones"]) == 1, projection
    milestone = projection["milestones"][0]
    assert milestone["reached"] is True, projection
    assert milestone["reached_evidence_refs"] == ["run:abc123"], projection
    assert milestone["source"] == "evidence", projection
    assert_no_public_leak(projection)


def assert_open_owner_gate_blocks_the_next_transition() -> None:
    """The RFC's example: a milestone is reached but the owner gate is open."""

    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        user_todo_summary={
            "open_count": 1,
            "gate_open_items": [
                {
                    "todo_id": "todo_gate_baseline",
                    "task_class": "user_gate",
                    "action_kind": "approve_baseline",
                    "blocks_agent": "agent-a",
                }
            ],
        },
        agent_todo_summary={"open_count": 2},
        run_history={
            "latest_runs": [
                {
                    "delivery_outcome": "primary_goal_outcome",
                    "delivery_batch_scale": "multi_surface",
                    "evidence_ref": "run:baseline",
                }
            ]
        },
        work_lane_contract={"lane": "advancement_task", "obligation": "advance_one_bounded_segment"},
    )
    assert projection["lifecycle_phase"] == PHASE_WAITING_OWNER, projection
    guard = projection["guards"][0]
    assert guard["kind"] == GUARD_KIND_OWNER_DECISION, projection
    assert guard["blocked"] is True, projection
    assert guard["owner"] == "user", projection
    assert guard["decision_scope"] == "approve_baseline", projection
    # A blocking guard admits no other transition, even with a selected lane.
    transitions = projection["next_transitions"]
    assert len(transitions) == 1, projection
    assert transitions[0]["reason_codes"] == ["guard_open"], projection
    assert transitions[0]["target_phase"] == PHASE_WAITING_OWNER, projection
    assert_no_public_leak(projection)


def assert_evidence_guard_is_required_and_owned_by_the_agent() -> None:
    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        user_todo_summary={"open_count": 0},
        agent_todo_summary={"open_count": 1},
        run_history={"latest_runs": []},
        acceptance_gaps=[{"kind": "vision_acceptance_gap", "agent_id": "agent-a"}],
    )
    guard = projection["guards"][0]
    assert guard["kind"] == GUARD_KIND_EVIDENCE, projection
    assert guard["evidence_required"] is True, projection
    assert guard["owner"] == "agent", projection
    assert projection["lifecycle_phase"] == PHASE_QUALIFYING, projection
    assert_no_public_leak(projection)


def assert_closing_then_closed_phase() -> None:
    closing = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        user_todo_summary={"gate_open_items": []},
        agent_todo_summary={"open_count": 0},
        run_history={
            "latest_runs": [
                {
                    "delivery_outcome": "primary_goal_outcome",
                    "delivery_batch_scale": "multi_surface",
                }
            ]
        },
    )
    assert closing["lifecycle_phase"] == PHASE_CLOSING, closing
    assert closing["next_transitions"][0]["target_phase"] == PHASE_CLOSED, closing

    closed = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "closed"},
        agent_todo_summary={"open_count": 0},
    )
    assert closed["lifecycle_phase"] == PHASE_CLOSED, closed
    assert closed["next_transitions"] == [], closed
    assert_no_public_leak(closed)


def assert_projection_is_pure_and_reads_no_state() -> None:
    """Same inputs must produce the same projection, with no side effects."""

    kwargs = {
        "goal_id": GOAL_ID,
        "goal": {"id": GOAL_ID, "status": "active"},
        "user_todo_summary": {"open_count": 0, "gate_open_items": []},
        "agent_todo_summary": {"open_count": 3},
        "run_history": {"latest_runs": []},
    }
    first = build_goal_artifact_lifecycle_projection(**kwargs)
    second = build_goal_artifact_lifecycle_projection(**kwargs)
    assert first == second, (first, second)
    assert first["lifecycle_phase"] == PHASE_QUALIFYING, first


def main() -> int:
    assert_starting_phase_without_work()
    assert_declared_milestone_stays_unreached_while_gapped()
    assert_evidence_milestone_reached_from_run_history()
    assert_open_owner_gate_blocks_the_next_transition()
    assert_evidence_guard_is_required_and_owned_by_the_agent()
    assert_closing_then_closed_phase()
    assert_projection_is_pure_and_reads_no_state()
    print("goal-artifact-lifecycle-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
