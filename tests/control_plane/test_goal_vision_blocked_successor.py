from __future__ import annotations

import pytest

from loopx.cli_commands.status import attach_agent_lane_next_actions
from loopx.control_plane.goals.goal_frontier import (
    build_goal_frontier_projection_context_from_status,
)
from loopx.control_plane.quota.markdown import render_quota_should_run_markdown
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.presentation.renderers.status_markdown import render_status_markdown
from loopx.quota import build_quota_should_run


GOAL_ID = "vision-blocked-successor-fixture"
AGENT_ID = "codex-side-agent"
PRIMARY_AGENT = "codex-primary-agent"
BLOCKER_ID = "todo_exact_blocker"
WAITING_ID = "todo_waiting_successor"


def _vision_run(
    *,
    state: str = "vision_drift_detected",
    missing_checkpoint: bool = False,
) -> dict:
    run = {
        "classification": "vision_blocked_successor_fixture",
        "generated_at": "2026-07-16T00:00:00+00:00",
        "agent_id": AGENT_ID,
        "progress_scope": "agent_lane",
        "agent_vision": {
            "schema_version": "goal_vision_replan_contract_v0",
            "agent_id": AGENT_ID,
            "state": state,
            "vision_patch": {
                "acceptance_summary": "Deliver the exact successor after its prerequisite clears.",
                "replan_trigger_summary": "The successor acceptance remains open.",
                "advancement_policy": "repeat_until_closed",
            },
        },
    }
    if missing_checkpoint:
        run["vision_checkpoint"] = {
            "schema_version": "vision_checkpoint_v0",
            "agent_id": AGENT_ID,
            "required": True,
            "satisfied": False,
            "decision": "missing_required",
            "triggers": [{"kind": "material_delivery_outcome"}],
        }
    return run


def _status_payload(
    *,
    blocker_status: str = "open",
    waiting_status: str = "open",
    blocker_task_class: str = "advancement_task",
    vision_state: str = "vision_drift_detected",
    missing_checkpoint: bool = False,
) -> dict:
    blocker = quota_todo_item(
        todo_id=BLOCKER_ID,
        index=1,
        text="[P0] Complete the exact prerequisite.",
        status=blocker_status,
        task_class=blocker_task_class,
        claimed_by=PRIMARY_AGENT,
        successor_todo_ids=[WAITING_ID],
    )
    waiting = quota_todo_item(
        todo_id=WAITING_ID,
        index=2,
        text="[P0] Resume the exact successor.",
        status=waiting_status,
        claimed_by=AGENT_ID,
        resume_when=f"todo_done:{BLOCKER_ID}",
    )
    agent_todos = quota_todo_summary([blocker, waiting], role="agent")
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Resume the exact successor after its prerequisite clears.",
        agent_todos=agent_todos,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [PRIMARY_AGENT, AGENT_ID],
        },
        latest_runs=[
            _vision_run(
                state=vision_state,
                missing_checkpoint=missing_checkpoint,
            )
        ],
    )


def _quota(payload: dict) -> dict:
    return build_quota_should_run(payload, goal_id=GOAL_ID, agent_id=AGENT_ID)


@pytest.mark.parametrize("waiting_status", ["open", "deferred"])
def test_exact_blocked_successor_defers_only_open_vision_gap(
    waiting_status: str,
) -> None:
    guard = _quota(_status_payload(waiting_status=waiting_status))

    assert guard["decision"] == "agent_scope_wait"
    assert guard["should_run"] is False
    assert guard["normal_delivery_allowed"] is False
    assert guard.get("autonomous_replan_obligation") is None
    frontier = guard["goal_frontier_projection"]
    assert frontier["acceptance_gaps"] == []
    assert frontier["replan_required"] is False
    assert "vision_blocked_successor_wait" in frontier["autonomy_blockers"]
    wait = frontier["vision_wait_state"]
    assert wait["schema_version"] == "goal_vision_wait_state_v0"
    assert wait["selected_todo_id"] == WAITING_ID
    assert wait["selected_todo_status"] == waiting_status
    assert wait["resume_when"] == f"todo_done:{BLOCKER_ID}"
    assert wait["resume_condition"]["target_todo_id"] == BLOCKER_ID
    assert wait["resume_condition"]["satisfied"] is False
    assert wait["deferred_acceptance_gap_count"] == 1
    assert wait["automatic_resume"] is True
    assert guard["vision_wait_state"] == wait
    assert guard["agent_scope_frontier"]["action"] == "agent_scope_wait"
    assert guard["agent_scope_frontier"].get("requires_replan") is not True
    assert guard["agent_scope_frontier"]["blocked_successor_wait_candidates"][0][
        "todo_id"
    ] == WAITING_ID
    assert guard["agent_lane_frontier_hint"]["reason_code"] == (
        "blocked_successor_resume_pending"
    )
    assert guard["interaction_contract"]["agent_channel"]["vision_wait_state"] == wait
    cli_wait = guard["interaction_contract"]["cli_channel"]["vision_wait_state"]
    assert cli_wait["selected_todo_id"] == WAITING_ID
    assert cli_wait["automatic_resume"] is True
    assert "vision_continuation_audit" not in guard

    markdown = render_quota_should_run_markdown(guard)
    assert (
        "vision_wait_state: state=waiting "
        f"todo_id={WAITING_ID} resume_when=todo_done:{BLOCKER_ID} "
        "automatic_resume=True"
    ) in markdown


def test_status_projects_exact_blocker_and_resume_contract() -> None:
    payload = _status_payload(waiting_status="deferred")
    attach_agent_lane_next_actions(payload, agent_id=AGENT_ID)

    item = payload["attention_queue"]["items"][0]
    wait = item["goal_frontier_projection"]["vision_wait_state"]
    assert wait["selected_todo_id"] == WAITING_ID
    assert item["project_asset"]["goal_frontier_projection"]["vision_wait_state"] == wait
    markdown = render_status_markdown(payload)
    assert (
        "vision_wait_state: state=waiting "
        f"todo_id={WAITING_ID} resume_when=todo_done:{BLOCKER_ID} "
        "automatic_resume=True"
    ) in markdown


def test_cleared_blocker_restores_normal_open_successor_routing() -> None:
    guard = _quota(_status_payload(blocker_status="done"))

    assert guard["decision"] == "run"
    assert guard["normal_delivery_allowed"] is True
    assert guard["selected_todo"]["todo_id"] == WAITING_ID
    assert guard["agent_lane_next_action"]["resume_ready"] is True
    assert "vision_wait_state" not in guard
    assert "vision_wait_state" not in guard["goal_frontier_projection"]
    assert guard["goal_frontier_projection"]["acceptance_gaps"][0]["kind"] == (
        "vision_acceptance_gap"
    )
    assert guard["vision_continuation_audit"]["required"] is True


def test_missing_checkpoint_is_not_hidden_by_blocked_successor() -> None:
    guard = _quota(_status_payload(missing_checkpoint=True))

    assert guard["decision"] == "autonomous_replan_required"
    assert "vision_wait_state" not in guard
    gap_kinds = {
        gap["kind"] for gap in guard["goal_frontier_projection"]["acceptance_gaps"]
    }
    assert "vision_checkpoint_missing" in gap_kinds
    assert guard["vision_continuation_audit"]["required"] is True


def test_closed_stage_successor_gap_is_not_hidden_by_blocked_successor() -> None:
    payload = _status_payload(vision_state="vision_closed")
    item = payload["attention_queue"]["items"][0]
    context = build_goal_frontier_projection_context_from_status(
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        status_payload=payload,
        item=item,
        project_asset=item["project_asset"],
        user_todo_summary=item["user_todos"],
        agent_todo_summary=item["agent_todos"],
        work_lane_contract={"lane": "advancement_task", "must_attempt_work": True},
        neutral_replan_ack_classifications=set(),
        registered_agent_ids=[PRIMARY_AGENT, AGENT_ID],
        goal_status="active",
    )

    frontier = context["goal_frontier_projection"]
    assert "vision_wait_state" not in frontier
    assert frontier["replan_required"] is True
    assert {
        gap["kind"] for gap in frontier["acceptance_gaps"]
    } == {"vision_successor_required"}


def test_standing_monitor_prerequisite_keeps_dedicated_repair_route() -> None:
    guard = _quota(
        _status_payload(
            blocker_task_class="continuous_monitor",
            vision_state="retired",
        )
    )

    assert guard["decision"] == "run"
    assert "vision_wait_state" not in guard
    assert guard["work_lane_contract"]["obligation"] == (
        "repair_resume_gate_or_close_standing_monitor"
    )
    assert "resume_blocked_by_open_monitor" in guard["work_lane_contract"][
        "reason_codes"
    ]
    assert guard["selected_todo"]["todo_id"] == WAITING_ID
