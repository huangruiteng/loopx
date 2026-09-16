"""A confirmed team plan applies through the Chat action service."""

from __future__ import annotations

import json
import itertools
from pathlib import Path

import pytest

from loopx.chat_action_store import ChatActionStore
from loopx.chat_actions import ChatActionService

GOAL_ID = "team-plan-action-fixture"
AGENT_ID = "agent-alpha"
_PREVIEWS = itertools.count(1)


def _fixture(tmp_path: Path, *, agents: tuple[str, ...] = (AGENT_ID,)):
    project = tmp_path / "project"
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
        "# Team Plan Action Fixture\n\n"
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
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": GOAL_ID,
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
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
    service = ChatActionService(
        store=ChatActionStore(tmp_path / "runtime" / "chat" / "actions"),
        registry_path=registry_path,
    )
    return project, registry_path, service


def _plan(*, agent_id: str = AGENT_ID, goal_id: str = GOAL_ID) -> dict:
    return {
        "schema_version": "steward_team_plan_preview_v0",
        "kind": "steward_team_plan_preview",
        "goal_id": goal_id,
        "objective": "Stand up the intake lane",
        "quota_envelope": {"slots_per_day": 4},
        "stop_condition": "Stop when the owner withdraws the request",
        "lanes": [
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
        ],
    }


def _preview(service: ChatActionService, plan: dict | None = None) -> dict:
    return service.preview(
        {
            "action_kind": "team.plan",
            "summary": "Confirm the team plan",
            "normalized_parameters": {"goal_id": GOAL_ID, "plan": plan or _plan()},
            "context": {},
            "idempotency_key": f"team-plan-preview-{next(_PREVIEWS)}",
        }
    )


def _todos(project: Path) -> str:
    return (project / f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md").read_text(
        encoding="utf-8"
    )


def test_a_confirmed_plan_creates_each_ready_lane_first_todo(tmp_path: Path) -> None:
    project, _registry_path, service = _fixture(tmp_path)

    preview = _preview(service)
    assert preview["action_kind"] == "team.plan"
    assert preview["permission_classification"] == "durable_write"

    applied = service.apply(preview["proposal_id"])
    proposal = applied["proposal"]
    assert proposal["status"] == "applied"
    receipt = proposal["receipt"]
    assert receipt["outcome"] == "team_plan_applied"
    lane_todo_ids = receipt["resource_ids"]["lane_todo_ids"]
    assert len(lane_todo_ids) == 1 and lane_todo_ids[0].startswith("todo_")
    assert receipt["resource_ids"]["todo_id"] == lane_todo_ids[0]
    # The readback names the canonical revision these lanes were created
    # against, so the owner sees what the new work is meant to advance.
    assert receipt["intent_basis"].startswith("sha256:")
    state = _todos(project)
    assert "Advance the intake contract" in state
    assert f"claimed_by={AGENT_ID}" in state
    assert state.count("loopx:todo ") == 1


def test_a_lane_with_an_unregistered_agent_becomes_a_gap_and_creates_nothing(
    tmp_path: Path,
) -> None:
    project, _registry_path, service = _fixture(tmp_path)

    preview = _preview(service, _plan(agent_id="agent-not-registered"))
    applied = service.apply(preview["proposal_id"])
    # The preview is admitted with its gap, and confirming it creates nothing:
    # the owner sees what was asked for and what is missing.
    assert applied["proposal"]["receipt"]["resource_ids"]["lane_todo_ids"] == []
    assert "loopx:todo " not in _todos(project)


def test_a_plan_for_another_goal_is_refused_at_preview(tmp_path: Path) -> None:
    _project, _registry_path, service = _fixture(tmp_path)

    with pytest.raises(ValueError, match="must match the plan's own Goal"):
        _preview(service, _plan(goal_id="some-other-goal"))


def test_a_changed_registry_makes_the_confirmed_plan_stale(tmp_path: Path) -> None:
    project, registry_path, service = _fixture(tmp_path, agents=(AGENT_ID,))

    preview = _preview(service)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["registered_agents"] = [AGENT_ID, "agent-beta"]
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    applied = service.apply(preview["proposal_id"])
    # The Agents a plan was validated against are the state that can invalidate
    # it, so a registration change asks the owner to confirm the current plan.
    assert applied["proposal"]["status"] == "stale"
    assert "loopx:todo " not in _todos(project)


def _validated(preview_plan: dict) -> dict:
    from loopx.control_plane.todos.contract import (
        TODO_ACTION_KIND_ADVANCEMENT_VALUES,
    )
    from loopx.control_plane.work_items.governed_transition_proposal import (
        validate_steward_team_plan_preview,
    )

    return validate_steward_team_plan_preview(
        preview_plan,
        registered_agent_ids=[AGENT_ID],
        supported_action_kinds=sorted(TODO_ACTION_KIND_ADVANCEMENT_VALUES),
    )


def test_an_admitted_preview_becomes_the_card_the_surfaces_list(
    tmp_path: Path,
) -> None:
    """Admission shows the plan; the owner still confirms it from one card.

    An admitted preview is not yet a confirmation surface: the product lists
    typed actions, so the manager channel projects the preview it validated into
    exactly one `team.plan` proposal. The projection creates no work, is scoped
    to the Goal the plan names, and is idempotent per plan, so a replayed Turn
    reuses the card instead of stacking a second one.
    """

    project, _registry_path, service = _fixture(tmp_path)
    plan = _plan()
    plan["lanes"].append(
        {
            "lane_id": "lane-beta",
            "agent_id": AGENT_ID,
            "acceptance": "Never reached",
            "first_todo": {
                "text": "Repair the public smoke",
                "priority": "P1",
                "task_class": "advancement_task",
                "action_kind": "public_smoke_quality_repair",
            },
        }
    )

    proposal = service.project_team_plan_preview(_validated(plan))

    assert proposal["action_kind"] == "team.plan"
    assert proposal["context"] == {"kind": "manager", "goal_id": GOAL_ID}
    assert proposal["status"] == "preview_ready"
    stored_plan = proposal["normalized_parameters"]["plan"]
    assert stored_plan["applies"] is False
    assert [lane["staffing"] for lane in stored_plan["lanes"]] == ["ready", "gap"]
    assert stored_plan["lanes"][1]["gap_reason_code"] == "action_kind_not_supported"
    # The projection itself created nothing.
    assert "loopx:todo " not in _todos(project)

    replay = service.project_team_plan_preview(_validated(plan))
    assert replay["proposal_id"] == proposal["proposal_id"]
    assert len(service.store.list(context_kind="manager")) == 1

    applied = service.apply(proposal["proposal_id"])
    receipt = applied["proposal"]["receipt"]
    assert receipt["outcome"] == "team_plan_applied"
    # Confirming the card creates the lane that can run and not the one whose
    # kind this host does not ship.
    assert len(receipt["resource_ids"]["lane_todo_ids"]) == 1
    state = _todos(project)
    assert "Advance the intake contract" in state
    assert "Repair the public smoke" not in state
