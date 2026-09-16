"""A confirmed team plan creates its lanes' first Todos and nothing else."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.work_items.governed_transition_proposal import (
    GovernedTransitionSettlementPhase,
    settle_governed_transition_proposals,
    validate_governed_transition_receipts,
)

GOAL_ID = "team-plan-apply-fixture"
AGENT_ID = "agent-alpha"


def _fixture(
    tmp_path: Path, *, agents: tuple[str, ...] = (AGENT_ID,)
) -> tuple[Path, Path]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active-read-only\n"
        "owner_mode: goal\n"
        'objective: "Stand up one digital team."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Team Plan Apply Fixture\n\n"
        "## Next Action\n\n"
        "- Confirm the team plan.\n\n"
        "## Agent Todo\n\n",
        encoding="utf-8",
    )
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "team-plan-apply-fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "read_only_project_map_v0",
                            "status": "connected-read-only",
                        },
                        "coordination": {
                            "registered_agents": list(agents),
                            "agent_model": "peer_v1",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return project, registry_path


def _proposal(*, agent_id: str = AGENT_ID, extra_lane: dict | None = None) -> dict:
    lanes = [
        {
            "lane_id": "lane-alpha",
            "agent_id": agent_id,
            "acceptance": "The lane's first Todo is delivered with evidence",
            "first_todo": {
                "text": "Advance the intake contract",
                "priority": "P1",
                "task_class": "advancement_task",
                "action_kind": "implement",
            },
        }
    ]
    if extra_lane is not None:
        lanes.append(extra_lane)
    return {
        "schema_version": "steward_team_plan_preview_v0",
        "kind": "steward_team_plan_preview",
        "proposal_id": "proposal-team-plan",
        "objective": "Stand up the intake lane",
        "quota_envelope": {"slots_per_day": 4},
        "stop_condition": "Stop when the owner withdraws the request",
        "lanes": lanes,
    }


def _settle(registry_path: Path, proposal: dict) -> list[dict]:
    return settle_governed_transition_proposals(
        registry_path=registry_path,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        effect_id="effect-team-plan",
        proposals=[proposal],
        existing_receipts=[],
        checkpoint=lambda _receipts: None,
        phase=GovernedTransitionSettlementPhase.PRE_SETTLEMENT,
    )


def _todos(project: Path) -> str:
    return (project / f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md").read_text(
        encoding="utf-8"
    )


def test_a_confirmed_plan_creates_each_ready_lane_first_todo(tmp_path: Path) -> None:
    project, registry_path = _fixture(tmp_path)

    receipts = _settle(registry_path, _proposal())

    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["kind"] == "steward_team_plan_preview"
    assert receipt["status"] == "committed"
    assert receipt["action"] == "created"
    assert receipt["todo_id"].startswith("todo_")
    state = _todos(project)
    assert "Advance the intake contract" in state
    assert f"claimed_by={AGENT_ID}" in state
    # One lane, one Todo: no monitor rows, no extra work.
    assert state.count("loopx:todo ") == 1


def test_a_gap_lane_creates_nothing_and_a_replay_adds_no_second_row(
    tmp_path: Path,
) -> None:
    project, registry_path = _fixture(tmp_path)
    gap_lane = {
        "lane_id": "lane-beta",
        "agent_id": "agent-not-registered",
        "acceptance": "Never reached",
        "first_todo": {
            "text": "Work that cannot be staffed",
            "priority": "P1",
            "task_class": "advancement_task",
            "action_kind": "implement",
        },
    }

    first = _settle(registry_path, _proposal(extra_lane=gap_lane))

    assert first[0]["action"] == "created"
    state = _todos(project)
    assert "Work that cannot be staffed" not in state
    assert state.count("loopx:todo ") == 1

    # The canonical Todo owner decides reuse, so a replayed settlement does not
    # duplicate the lane it already created.
    replay = _settle(registry_path, _proposal(extra_lane=gap_lane))
    assert replay[0]["action"] == "reused"
    # The receipt still names the same lane Todo, and the gap lane stays absent.
    assert replay[0]["todo_id"] == first[0]["todo_id"]
    assert replay[0]["proposal_digest"] == first[0]["proposal_digest"]
    assert _todos(project).count("loopx:todo ") == 1


def test_an_unknown_goal_is_refused_before_any_todo(tmp_path: Path) -> None:
    project, registry_path = _fixture(tmp_path)

    with pytest.raises(ValueError, match="unknown Goal"):
        settle_governed_transition_proposals(
            registry_path=registry_path,
            goal_id="goal-that-does-not-exist",
            agent_id=AGENT_ID,
            effect_id="effect-team-plan",
            proposals=[_proposal()],
            existing_receipts=[],
            checkpoint=lambda _receipts: None,
            phase=GovernedTransitionSettlementPhase.PRE_SETTLEMENT,
        )

    assert "loopx:todo " not in _todos(project)


def _second_lane() -> dict:
    return {
        "lane_id": "lane-beta",
        "agent_id": "agent-beta",
        "acceptance": "The second lane's first Todo is delivered with evidence",
        "first_todo": {
            "text": "Read back the second lane's bounded first turn",
            "priority": "P2",
            "task_class": "advancement_task",
            "action_kind": "implement",
        },
    }


def test_the_receipt_names_every_lane_todo_it_created(tmp_path: Path) -> None:
    """One readback has to say what exists now, not only where it started."""

    project, registry_path = _fixture(tmp_path, agents=(AGENT_ID, "agent-beta"))

    receipts = _settle(registry_path, _proposal(extra_lane=_second_lane()))

    receipt = receipts[0]
    lane_todo_ids = receipt["lane_todo_ids"]
    assert len(lane_todo_ids) == 2 and len(set(lane_todo_ids)) == 2
    # The first lane Todo is still the receipt's own identity, so a reader that
    # only knows the older field keeps working.
    assert receipt["todo_id"] == lane_todo_ids[0]
    assert _todos(project).count("loopx:todo ") == 2
    # Both the plan readback and the older receipt shape validate, which is what
    # a settlement journal does with its stored receipts.
    assert len(validate_governed_transition_receipts(receipts)) == 1

    # A replayed settlement reports the same lanes instead of an empty readback.
    replay = _settle(registry_path, _proposal(extra_lane=_second_lane()))
    assert replay[0]["action"] == "reused"
    assert replay[0]["lane_todo_ids"] == lane_todo_ids
    assert _todos(project).count("loopx:todo ") == 2


def _receipt(**overrides) -> dict:
    receipt = {
        "schema_version": "loopx_governed_transition_proposal_receipt_v0",
        "proposal_id": "proposal-receipt-fixture",
        "proposal_digest": "sha256:" + "a" * 64,
        "kind": "continuous_monitor_upsert",
        "monitor_key": "monitor-key-1",
        "action": "updated",
        "todo_id": "todo_1",
        "status": "committed",
        "target_key": None,
    }
    receipt.update(overrides)
    return receipt


def test_the_lane_readback_is_optional_bounded_and_additive() -> None:
    """An older receipt stays valid; the new field is the only addition."""

    assert len(validate_governed_transition_receipts([_receipt()])) == 1
    assert len(
        validate_governed_transition_receipts(
            [_receipt(lane_todo_ids=["todo_1", "todo_2"])]
        )
    ) == 1

    for invalid_readback in (
        [],
        ["todo_1", "todo_1"],
        ["todo_1", "not-a-todo-id"],
        ["todo_1", "todo_" + "a" * 41],
        ["todo_1"] * 9,
        "todo_1",
    ):
        with pytest.raises(ValueError, match="lane_todo_ids is invalid"):
            validate_governed_transition_receipts(
                [_receipt(lane_todo_ids=invalid_readback)]
            )
    # The field set stays closed: the readback is the only thing that may be
    # added, and a monitor receipt still has to name its own key.
    with pytest.raises(ValueError, match="receipt fields are invalid"):
        validate_governed_transition_receipts([_receipt(unexpected_field=1)])
    with pytest.raises(ValueError, match="monitor_key is invalid"):
        validate_governed_transition_receipts([_receipt(monitor_key=None)])


def test_a_team_plan_receipt_must_not_invent_a_monitor_key() -> None:
    """A plan is not a monitor, so its receipt carries no monitor identity."""

    team_plan = _receipt(kind="steward_team_plan_preview", monitor_key=None)

    assert len(validate_governed_transition_receipts([team_plan])) == 1
    with pytest.raises(ValueError, match="monitor_key is invalid"):
        validate_governed_transition_receipts(
            [{**team_plan, "monitor_key": "monitor-key-1"}]
        )
