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

from loopx.control_plane.goals.artifact_lifecycle import (  # noqa: E402 - source-checkout entrypoint
    GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION,
    GUARD_KIND_EVIDENCE,
    GUARD_KIND_OWNER_DECISION,
    PHASE_CLOSED,
    PHASE_CLOSING,
    PHASE_QUALIFYING,
    PHASE_STARTING,
    PHASE_WAITING_OWNER,
    _compact_text,
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
    assert guard["decision_scope"] is None, projection
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


def assert_unreached_milestone_blocks_closeout() -> None:
    """An unclaimed-acceptance Goal must not be told to close."""

    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={
            "id": GOAL_ID,
            "status": "active",
            "acceptance": {"milestones": ["baseline_pass"]},
        },
        user_todo_summary={"gate_open_items": []},
        agent_todo_summary={"open_count": 0},
        run_history={"latest_runs": []},
    )
    assert projection["lifecycle_phase"] == PHASE_QUALIFYING, projection
    transitions = projection["next_transitions"]
    assert transitions, projection
    assert transitions[0]["target_phase"] != PHASE_CLOSED, projection
    assert transitions[0]["reason_codes"] == ["milestone_unreached"], projection


def assert_reached_milestones_still_allow_closeout() -> None:
    """The same inputs with evidence present do reach the closing phase."""

    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={
            "id": GOAL_ID,
            "status": "active",
            "acceptance": {"milestones": ["primary_goal_outcome"]},
        },
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
    assert projection["lifecycle_phase"] == PHASE_CLOSING, projection
    assert projection["next_transitions"][0]["target_phase"] == PHASE_CLOSED, projection


def assert_private_values_are_redacted_or_dropped() -> None:
    """A run-history reference is free text; private values must not survive."""

    projection = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID,
        goal={"id": GOAL_ID, "status": "active"},
        agent_todo_summary={"open_count": 1},
        run_history={
            "latest_runs": [
                {
                    "delivery_outcome": "primary_goal_outcome",
                    "delivery_batch_scale": "multi_surface",
                    "evidence_ref": "/Users/private-owner/.ssh/id_rsa",
                    "recommended_action": (
                        "publish ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345 and "
                        "see /private/var/folders/secret/notes.md"
                    ),
                }
            ]
        },
    )
    rendered = json.dumps(projection, ensure_ascii=False)
    for leaked in (
        "/Users/private-owner",
        "/private/var/folders",
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    ):
        assert leaked not in rendered, (leaked, rendered)

    # Unsafe references are withheld by the same validator as other status
    # projections; no local path is retained even as a truncated fragment.
    assert _compact_text("/Users/private-owner/notes.md") is None
    assert _compact_text("token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345") is None
    assert _compact_text("/private/var/folders/x/secret.md") is None


def assert_batch_scale_never_promotes_an_outcome() -> None:
    """The batch scale describes delivery width; it is not Goal evidence.

    Regression for the counterexample the review raised: a `surface_only` run
    also carrying `delivery_batch_scale=multi_surface` must not become a reached
    milestone, because the canonical typed rule
    (`MATERIAL_DELIVERY_OUTCOMES`) excludes `surface_only`.
    """

    for scale in ("single_surface", "multi_surface"):
        for outcome in ("surface_only", "", "bogus", "multi_surface"):
            projection = build_goal_artifact_lifecycle_projection(
                goal_id=GOAL_ID,
                goal={"id": GOAL_ID, "status": "active"},
                run_history={
                    "latest_runs": [
                        {
                            "delivery_outcome": outcome,
                            "delivery_batch_scale": scale,
                            "run_id": "run-1",
                        }
                    ]
                },
            )
            assert projection["milestones"] == [], (outcome, scale, projection["milestones"])
    # Every canonical material outcome still counts, at any scale.
    for scale in ("single_surface", "multi_surface"):
        for outcome in ("outcome_gap", "outcome_progress", "primary_goal_outcome"):
            projection = build_goal_artifact_lifecycle_projection(
                goal_id=GOAL_ID,
                goal={"id": GOAL_ID, "status": "active"},
                run_history={
                    "latest_runs": [
                        {
                            "delivery_outcome": outcome,
                            "delivery_batch_scale": scale,
                            "run_id": "run-1",
                        }
                    ]
                },
            )
            reached = [item for item in projection["milestones"] if item["reached"]]
            assert [item["id"] for item in reached] == [outcome], (outcome, scale, reached)


def assert_status_collection_attaches_a_readable_readout() -> None:
    """The RFC's smallest slice includes one readout in status markdown.

    Drives the same seam `loopx status` uses: collection attaches the
    projection, the presentation renderer prints it. The projection is derived
    from already-collected payloads, so this asserts no extra IO is required.
    """

    from loopx.control_plane.goals.artifact_lifecycle import (
        attach_goal_artifact_lifecycle_projections,
    )
    from loopx.presentation.renderers.status_markdown import render_status_markdown

    payload = {
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "status": "active",
                    "acceptance": {"milestones": ["baseline_pass"]},
                }
            ]
        },
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "user_todos": {
                        "items": [
                            {
                                "todo_id": "todo_gate",
                                "task_class": "user_gate",
                                "text": "approve the release",
                                "status": "open",
                                "action_kind": "publish",
                            }
                        ]
                    },
                    "agent_todos": {"open_count": 0},
                }
            ]
        },
    }
    attach_goal_artifact_lifecycle_projections(payload, history={"goals": []})
    goal = payload["run_history"]["goals"][0]
    projection = goal["artifact_lifecycle"]
    assert projection["schema_version"] == GOAL_ARTIFACT_LIFECYCLE_PROJECTION_SCHEMA_VERSION
    assert projection["lifecycle_phase"] == PHASE_WAITING_OWNER, projection
    assert [guard["id"] for guard in projection["guards"]] == ["todo_gate"]
    markdown = render_status_markdown(payload)
    assert "artifact lifecycle: phase=waiting_owner" in markdown, markdown
    assert "blocked by owner_decision (user): todo_gate" in markdown, markdown
    assert_no_public_leak(projection)


def assert_the_two_goal_projections_stay_distinct() -> None:
    """The lifecycle contract and the narrow acceptance observation must not mix.

    `#4248` shipped `goal_acceptance_observation_projection_v0` as bounded
    historical evidence and guarded that it is not the full lifecycle contract.
    Both now ship, so each renderer must refuse the other's schema rather than
    print a half-understood payload under its own heading.
    """

    from loopx.presentation.renderers.goal_acceptance_observation_markdown import (
        append_goal_acceptance_observation_markdown,
    )
    from loopx.presentation.renderers.goal_artifact_lifecycle_markdown import (
        append_goal_artifact_lifecycle_markdown,
    )

    lifecycle = build_goal_artifact_lifecycle_projection(
        goal_id=GOAL_ID, goal={"id": GOAL_ID, "status": "active"}
    )
    narrow = {
        "schema_version": "goal_acceptance_observation_projection_v0",
        "guards": [],
        "acceptance_gaps": [],
        "historical_progress": [],
    }
    # Each renderer prints only its own contract, whichever key carries it.
    for goal in ({"artifact_lifecycle": narrow}, {"artifact_lifecycle": {}}):
        lines: list[str] = []
        append_goal_artifact_lifecycle_markdown(lines, goal)
        assert lines == [], (goal, lines)
    for goal in ({"acceptance_observation": lifecycle}, {"acceptance_observation": {}}):
        lines = []
        append_goal_acceptance_observation_markdown(lines, goal)
        assert lines == [], (goal, lines)
    # And the lifecycle renderer does print its own contract.
    lines = []
    append_goal_artifact_lifecycle_markdown(lines, {"artifact_lifecycle": lifecycle})
    assert any("artifact lifecycle" in line for line in lines), lines
    # The phase/milestone/transition vocabulary belongs to the lifecycle alone.
    assert {"lifecycle_phase", "milestones", "next_transitions"} <= set(lifecycle)
    assert {"lifecycle_phase", "milestones", "next_transitions"}.isdisjoint(narrow)


def assert_control_plane_imports_no_presentation_module() -> None:
    """The projection may not depend outward on the presentation layer."""

    import ast

    source = (
        REPO_ROOT / "loopx" / "control_plane" / "goals" / "artifact_lifecycle.py"
    ).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    offenders = [name for name in imported if "presentation" in name]
    assert offenders == [], offenders


def main() -> int:
    assert_starting_phase_without_work()
    assert_declared_milestone_stays_unreached_while_gapped()
    assert_evidence_milestone_reached_from_run_history()
    assert_open_owner_gate_blocks_the_next_transition()
    assert_evidence_guard_is_required_and_owned_by_the_agent()
    assert_closing_then_closed_phase()
    assert_projection_is_pure_and_reads_no_state()
    assert_unreached_milestone_blocks_closeout()
    assert_reached_milestones_still_allow_closeout()
    assert_private_values_are_redacted_or_dropped()
    assert_batch_scale_never_promotes_an_outcome()
    assert_status_collection_attaches_a_readable_readout()
    assert_control_plane_imports_no_presentation_module()
    assert_the_two_goal_projections_stay_distinct()
    print("goal-artifact-lifecycle-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
