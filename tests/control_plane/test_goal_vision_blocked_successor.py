from __future__ import annotations

from copy import deepcopy
import json

import pytest

from examples.control_plane.quota_plan_fixtures import (
    SCOPED_AGENT_ID,
    write_cli_fixture,
)
from loopx.cli_commands.status import attach_agent_lane_next_actions
from loopx.control_plane.goals.goal_frontier import (
    build_goal_frontier_projection_context_from_status,
)
from loopx.control_plane.quota.monitor_poll import build_quota_monitor_poll_event
from loopx.control_plane.scheduler.execution_context import (
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.control_plane.work_items.autonomous_replan_ack import (
    latest_blocked_successor_frontier_identity,
)
from loopx.presentation.renderers.status_markdown import render_status_markdown
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown
from loopx.state_refresh import build_state_refresh_record, refresh_state_run
from loopx.status import autonomous_replan_obligation_from_runs, compact_run


GOAL_ID = "vision-blocked-successor-fixture"
AGENT_ID = "codex-side-agent"
PRIMARY_AGENT = "codex-primary-agent"
BLOCKER_ID = "todo_exact_blocker"
WAITING_ID = "todo_waiting_successor"
CROSS_DOMAIN_WAITING_ID = "todo_cross_domain_waiting"
CLAIMED_WAITING_ID = "todo_claimed_waiting"
MONITOR_ID = "todo_future_monitor"
MONITOR_BLOCKED_ID = "todo_monitor_blocked_advancement"


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
    latest_runs: list[dict] | None = None,
    extra_agent_items: list[dict] | None = None,
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
    agent_todos = quota_todo_summary(
        [blocker, waiting, *(extra_agent_items or [])],
        role="agent",
    )
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Resume the exact successor after its prerequisite clears.",
        agent_todos=agent_todos,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [PRIMARY_AGENT, AGENT_ID],
        },
        latest_runs=latest_runs
        if latest_runs is not None
        else [
            _vision_run(
                state=vision_state,
                missing_checkpoint=missing_checkpoint,
            )
        ],
    )


def _cross_domain_wait_status_payload() -> dict:
    unclaimed = quota_todo_item(
        todo_id=CROSS_DOMAIN_WAITING_ID,
        index=1,
        text="[P1] Resume a benchmark-runner task owned by another lane.",
        status="deferred",
        priority="P1",
        action_kind="benchmark_runner_external_lane",
        required_capabilities=["benchmark_runner"],
        resume_when="capacity_available:benchmark_runner",
    )
    claimed = quota_todo_item(
        todo_id=CLAIMED_WAITING_ID,
        index=2,
        text="[P2] Resume this agent's release qualification successor.",
        status="deferred",
        priority="P2",
        action_kind="release_outcome_baseline_qualification",
        claimed_by=AGENT_ID,
        required_capabilities=["benchmark_runner"],
        resume_when="capacity_available:benchmark_runner",
    )
    agent_todos = quota_todo_summary([unclaimed, claimed], role="agent")
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Wait for the current agent's exact successor.",
        agent_todos=agent_todos,
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [PRIMARY_AGENT, AGENT_ID],
            "agent_profiles": {
                AGENT_ID: {
                    "schema_version": "agent_profile_v1",
                    "agent_id": AGENT_ID,
                    "profile_role": "quality-qualification",
                    "default_task_classes": [
                        "advancement_task",
                        "continuous_monitor",
                    ],
                    "vision_requirement": "required",
                    "preferred_action_kinds": ["release_outcome_baseline_*"],
                    "avoid_action_kinds": ["benchmark_runner_*"],
                }
            },
        },
        latest_runs=[_vision_run()],
    )


def _quota(payload: dict) -> dict:
    return build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=(
            GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT
        ),
    )


def _blocked_wait_polls() -> list[dict]:
    guard = _quota(_status_payload())
    return [
        build_quota_monitor_poll_event(
            guard,
            generated_at="2026-07-16T00:02:00+00:00",
        ),
        build_quota_monitor_poll_event(
            guard,
            generated_at="2026-07-16T00:01:00+00:00",
        ),
    ]


def _quota_with_replan_runs(
    runs: list[dict],
    *,
    extra_agent_items: list[dict] | None = None,
) -> dict:
    payload = _status_payload(
        latest_runs=runs,
        extra_agent_items=extra_agent_items,
    )
    item = payload["attention_queue"]["items"][0]
    obligation = autonomous_replan_obligation_from_runs(
        runs,
        agent_todos=item["agent_todos"],
    )
    if obligation:
        item["autonomous_replan_obligation"] = obligation
        item["project_asset"]["autonomous_replan_obligation"] = obligation
    return _quota(payload)


def _monitor_blocked_advancement_items(
    *,
    next_due_at: str | None,
    claimed_by: str = AGENT_ID,
) -> list[dict]:
    monitor_metadata = {
        "target_key": "future-monitor-target",
        "cadence": "10m",
    }
    if next_due_at is not None:
        monitor_metadata["next_due_at"] = next_due_at
    return [
        quota_todo_item(
            todo_id=MONITOR_ID,
            index=3,
            text="[P0] Monitor the pending external result.",
            task_class="continuous_monitor",
            claimed_by=claimed_by,
            **monitor_metadata,
        ),
        quota_todo_item(
            todo_id=MONITOR_BLOCKED_ID,
            index=4,
            text="[P0] Resume delivery after the monitor completes.",
            status="deferred",
            claimed_by=claimed_by,
            resume_when=f"todo_done:{MONITOR_ID}",
        ),
    ]


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
    assert guard["interaction_contract"]["agent_channel"]["must_attempt"] is True
    assert guard["interaction_contract"]["agent_channel"]["delivery_allowed"] is False
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False
    cli_actions = guard["interaction_contract"]["cli_channel"]["next_cli_actions"]
    assert "quota monitor-poll" in cli_actions[0]
    assert "quota should-run" in cli_actions[1]
    assert "agent_action_required=true" in guard["protocol_action_packet"]["summary"]
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


def test_agent_claimed_wait_outranks_unclaimed_cross_domain_wait() -> None:
    guard = _quota(_cross_domain_wait_status_payload())

    assert guard["decision"] == "agent_scope_wait"
    wait = guard["goal_frontier_projection"]["vision_wait_state"]
    assert wait["selected_todo_id"] == CLAIMED_WAITING_ID
    assert wait["selected_todo_claimed_by"] == AGENT_ID
    assert wait["waiting_todo_ids"] == [
        CLAIMED_WAITING_ID,
        CROSS_DOMAIN_WAITING_ID,
    ]

    status_payload = _cross_domain_wait_status_payload()
    attach_agent_lane_next_actions(status_payload, agent_id=AGENT_ID)
    item = status_payload["attention_queue"]["items"][0]
    status_wait = item["goal_frontier_projection"]["vision_wait_state"]
    assert status_wait["selected_todo_id"] == CLAIMED_WAITING_ID
    assert status_wait["waiting_todo_ids"] == wait["waiting_todo_ids"]


def test_two_identical_blocked_successor_waits_trigger_bounded_replan() -> None:
    polls = _blocked_wait_polls()
    target = polls[0]["monitor_target"]
    assert target["monitor_mode"] == (
        "blocked_successor_wait_without_material_transition"
    )
    assert target["frontier_identity"]
    assert polls[1]["monitor_target"]["target_id"] == target["target_id"]
    assert polls[1]["monitor_target"]["frontier_identity"] == target[
        "frontier_identity"
    ]

    guard = _quota_with_replan_runs([*polls, _vision_run()])

    assert guard["decision"] == "autonomous_replan_required"
    assert guard["should_run"] is True
    obligation = guard["autonomous_replan_obligation"]
    assert obligation["stall_threshold"] == 2
    assert obligation["frontier_identity"] == target["frontier_identity"]
    assert obligation["triggers"][0]["kind"] == (
        "blocked_successor_no_progress_repeat"
    )
    assert obligation["guidance_actions"] == [
        "discover_safe_successor",
        "create_successor",
        "record_wait_continuation",
    ]


def test_future_due_blocking_monitor_suppresses_predue_wait_replan() -> None:
    compacted_polls = [compact_run(poll) for poll in _blocked_wait_polls()]
    assert "next_due_at" not in compacted_polls[0]["monitor_target"]

    guard = _quota_with_replan_runs(
        [*compacted_polls, _vision_run()],
        extra_agent_items=_monitor_blocked_advancement_items(
            next_due_at="2099-01-01T00:00:00+00:00",
        ),
    )

    assert guard["decision"] == "skip"
    assert guard["effective_action"] == "monitor_quiet_skip"
    assert guard.get("autonomous_replan_obligation") is None
    assert guard["vision_wait_state"]["selected_todo_id"] == WAITING_ID


@pytest.mark.parametrize(
    "next_due_at",
    [None, "2026-07-16T00:00:00+00:00"],
    ids=["schedule-gap", "overdue"],
)
def test_unscheduled_or_overdue_monitor_preserves_wait_replan(
    next_due_at: str | None,
) -> None:
    compacted_polls = [compact_run(poll) for poll in _blocked_wait_polls()]

    guard = _quota_with_replan_runs(
        [*compacted_polls, _vision_run()],
        extra_agent_items=_monitor_blocked_advancement_items(
            next_due_at=next_due_at,
        ),
    )

    assert guard["decision"] == "autonomous_replan_required"
    trigger = guard["autonomous_replan_obligation"]["triggers"][0]
    assert trigger["kind"] == "blocked_successor_no_progress_repeat"


def test_peer_future_due_monitor_does_not_suppress_wait_replan() -> None:
    guard = _quota_with_replan_runs(
        [*[compact_run(poll) for poll in _blocked_wait_polls()], _vision_run()],
        extra_agent_items=_monitor_blocked_advancement_items(
            next_due_at="2099-01-01T00:00:00+00:00",
            claimed_by="peer-agent",
        ),
    )

    assert guard["decision"] == "autonomous_replan_required"
    trigger = guard["autonomous_replan_obligation"]["triggers"][0]
    assert trigger["kind"] == "blocked_successor_no_progress_repeat"


def test_interleaved_peer_monitor_does_not_reset_blocked_successor_replan() -> None:
    polls = _blocked_wait_polls()
    peer_poll = deepcopy(polls[0])
    peer_poll["agent_id"] = PRIMARY_AGENT
    peer_identity = {
        "agent_id": PRIMARY_AGENT,
        "target_id": "peer-monitor-target",
        "frontier_identity": "peer-frontier",
    }
    peer_poll["monitor_target"].update(peer_identity)
    peer_poll["monitor_event"]["agent_id"] = PRIMARY_AGENT
    peer_poll["monitor_event"]["monitor_target"].update(peer_identity)

    replanned = _quota_with_replan_runs(
        [polls[0], peer_poll, polls[1], _vision_run()]
    )

    assert replanned["decision"] == "autonomous_replan_required"
    obligation = replanned["autonomous_replan_obligation"]
    assert obligation["agent_id"] == AGENT_ID
    trigger = obligation["triggers"][0]
    assert trigger["kind"] == "blocked_successor_no_progress_repeat"
    assert trigger["monitor_target_id"] == polls[0]["monitor_target"]["target_id"]
    assert trigger["frontier_identity"] == polls[0]["monitor_target"][
        "frontier_identity"
    ]


def test_compacted_monitor_quiet_vision_waits_trigger_bounded_replan() -> None:
    guard = _quota(_status_payload())
    guard.update(
        {
            "decision": "skip",
            "effective_action": "monitor_quiet_skip",
            "should_run": False,
            "normal_delivery_allowed": False,
        }
    )
    polls = [
        build_quota_monitor_poll_event(
            guard,
            generated_at="2026-07-16T00:02:00+00:00",
        ),
        build_quota_monitor_poll_event(
            guard,
            generated_at="2026-07-16T00:01:00+00:00",
        ),
    ]

    assert {
        poll["monitor_target"]["monitor_mode"]
        for poll in polls
    } == {"blocked_successor_wait_without_material_transition"}
    compacted_polls = [compact_run(poll) for poll in polls]
    compact_target = compacted_polls[0]["monitor_target"]
    assert compact_target["target_id"] == polls[0]["monitor_target"]["target_id"]
    assert compact_target["frontier_identity"] == polls[0]["monitor_target"][
        "frontier_identity"
    ]
    assert "monitor_event" not in compacted_polls[0]

    replanned = _quota_with_replan_runs([*compacted_polls, _vision_run()])

    assert replanned["decision"] == "autonomous_replan_required"
    assert replanned["should_run"] is True
    trigger = replanned["autonomous_replan_obligation"]["triggers"][0]
    assert trigger["kind"] == "blocked_successor_no_progress_repeat"
    assert trigger["frontier_identity"] == compact_target["frontier_identity"]


def test_replan_ack_dedupes_only_the_same_blocked_successor_frontier() -> None:
    polls = _blocked_wait_polls()
    frontier_identity = polls[0]["monitor_target"]["frontier_identity"]
    ack = {
        "classification": "autonomous_replan_recorded",
        "generated_at": "2026-07-16T00:03:00+00:00",
        "agent_id": AGENT_ID,
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "fixture",
            "frontier_identity": frontier_identity,
            "delta_contract": {
                "schema_version": "repair_delta_contract_v0",
                "delta_present": True,
                "delta_kinds": ["watch_lane_continuation"],
            },
        },
    }

    same_frontier = _quota_with_replan_runs([*polls, ack, _vision_run()])
    assert same_frontier["decision"] == "agent_scope_wait"
    assert same_frontier.get("autonomous_replan_obligation") is None

    ack["autonomous_replan_ack"]["frontier_identity"] = "different-frontier"
    changed_frontier = _quota_with_replan_runs([*polls, ack, _vision_run()])
    assert changed_frontier["decision"] == "autonomous_replan_required"
    assert changed_frontier["autonomous_replan_obligation"][
        "frontier_identity"
    ] == frontier_identity


def test_replan_ack_does_not_cover_newer_same_frontier_stalls() -> None:
    polls = _blocked_wait_polls()
    frontier_identity = polls[0]["monitor_target"]["frontier_identity"]
    older_ack = {
        "classification": "autonomous_replan_recorded",
        "generated_at": "2026-07-16T00:00:30+00:00",
        "agent_id": AGENT_ID,
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "fixture",
            "frontier_identity": frontier_identity,
            "delta_contract": {
                "schema_version": "repair_delta_contract_v0",
                "delta_present": True,
                "delta_kinds": ["watch_lane_continuation"],
            },
        },
    }

    replanned = _quota_with_replan_runs([*polls, older_ack, _vision_run()])

    assert replanned["decision"] == "autonomous_replan_required"
    assert replanned["goal_frontier_projection"]["replan_required"] is True
    assert replanned["autonomous_replan_obligation"]["frontier_identity"] == (
        frontier_identity
    )


def test_refresh_ack_preserves_the_observed_blocked_successor_identity(
    tmp_path,
) -> None:
    polls = _blocked_wait_polls()
    frontier_identity = latest_blocked_successor_frontier_identity(polls)
    assert frontier_identity == polls[0]["monitor_target"]["frontier_identity"]

    record = build_state_refresh_record(
        goal_id=GOAL_ID,
        state_file=tmp_path / "ACTIVE_GOAL_STATE.md",
        state_text="---\nstatus: active\n---\n\n## Next Action\n\n- Replan.\n",
        classification="autonomous_replan_recorded",
        recommended_action="Continue the selected bounded replan slice.",
        recommended_action_source="explicit_arg",
        generated_at="2026-07-16T00:03:00+00:00",
        registry_goal=None,
        agent_id=AGENT_ID,
        autonomous_replan_recorded=True,
        repair_delta_contract={
            "schema_version": "repair_delta_contract_v0",
            "delta_present": True,
            "delta_kinds": ["watch_lane_continuation"],
        },
        autonomous_replan_frontier_identity=frontier_identity,
    )

    assert record["autonomous_replan_ack"]["frontier_identity"] == (
        frontier_identity
    )


def test_refresh_ack_recovers_only_the_current_agent_frontier(tmp_path) -> None:
    registry_path, runtime_root, _ = write_cli_fixture(
        tmp_path / "fixture",
        scoped_agents=True,
    )
    peer_agent_id = "codex-main-control"
    current_frontier = "current-agent-frontier"
    peer_frontier = "newer-peer-frontier"

    def monitor_poll(*, agent_id: str, frontier_identity: str, generated_at: str) -> dict:
        return {
            "goal_id": "half-speed",
            "classification": "quota_monitor_poll",
            "generated_at": generated_at,
            "agent_id": agent_id,
            "monitor_target": {
                "monitor_mode": "blocked_successor_wait_without_material_transition",
                "agent_id": agent_id,
                "frontier_identity": frontier_identity,
            },
        }

    runs = [
        monitor_poll(
            agent_id=peer_agent_id,
            frontier_identity=peer_frontier,
            generated_at="2099-01-01T00:03:00+00:00",
        ),
        monitor_poll(
            agent_id=SCOPED_AGENT_ID,
            frontier_identity=current_frontier,
            generated_at="2099-01-01T00:02:00+00:00",
        ),
    ]
    assert latest_blocked_successor_frontier_identity(runs) == peer_frontier
    assert latest_blocked_successor_frontier_identity(
        runs,
        agent_id=SCOPED_AGENT_ID,
    ) == current_frontier

    unscoped_poll = monitor_poll(
        agent_id=SCOPED_AGENT_ID,
        frontier_identity="goal-level-frontier",
        generated_at="2099-01-01T00:04:00+00:00",
    )
    unscoped_poll.pop("agent_id")
    unscoped_poll["monitor_target"].pop("agent_id")
    assert latest_blocked_successor_frontier_identity([unscoped_poll]) == (
        "goal-level-frontier"
    )
    assert (
        latest_blocked_successor_frontier_identity(
            [unscoped_poll],
            agent_id=SCOPED_AGENT_ID,
        )
        is None
    )

    conflicting_poll = monitor_poll(
        agent_id=SCOPED_AGENT_ID,
        frontier_identity="conflicting-frontier",
        generated_at="2099-01-01T00:05:00+00:00",
    )
    conflicting_poll["monitor_target"]["agent_id"] = peer_agent_id
    assert (
        latest_blocked_successor_frontier_identity(
            [conflicting_poll],
            agent_id=SCOPED_AGENT_ID,
        )
        is None
    )

    index_path = runtime_root / "goals" / "half-speed" / "runs" / "index.jsonl"
    with index_path.open("a", encoding="utf-8") as index_file:
        for run in reversed(runs):
            index_file.write(json.dumps(run, ensure_ascii=False) + "\n")

    payload = refresh_state_run(
        registry_path=registry_path,
        runtime_root_override=None,
        goal_id="half-speed",
        project=None,
        state_file=None,
        classification="autonomous_replan_recorded",
        recommended_action="Continue the current agent replan.",
        agent_id=SCOPED_AGENT_ID,
        autonomous_replan_recorded=True,
        repair_delta_kinds=["watch_lane_continuation"],
        dry_run=True,
        sync_global=False,
    )

    assert payload["autonomous_replan_ack"]["frontier_identity"] == current_frontier


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
