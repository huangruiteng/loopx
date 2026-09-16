"""The steward team preview validates without ever becoming an effect."""

from __future__ import annotations

import pytest

from loopx.control_plane.work_items.governed_transition_proposal import (
    _SETTLEMENT_PHASE_BY_PROPOSAL_KIND,
    GovernedTransitionSettlementPhase,
    STEWARD_TEAM_PLAN_PREVIEW_KIND,
    STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION,
    validate_steward_team_plan_preview,
)


def _plan(**overrides: object) -> dict[str, object]:
    plan: dict[str, object] = {
        "schema_version": STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION,
        "kind": STEWARD_TEAM_PLAN_PREVIEW_KIND,
        "objective": "Ship the intake lane",
        "quota_envelope": {"slots_per_day": 4},
        "stop_condition": "Stop when the owner withdraws the request",
        "lanes": [
            {
                "lane_id": "lane-alpha",
                "agent_id": "agent-alpha",
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
    plan.update(overrides)
    return plan


def _validate(plan: object) -> dict:
    return validate_steward_team_plan_preview(
        plan,
        registered_agent_ids=["agent-alpha"],
        supported_action_kinds=["implement"],
    )


def test_a_staffed_lane_becomes_a_preview_that_cannot_apply() -> None:
    preview = _validate(_plan())

    assert preview["applies"] is False
    assert preview["gaps"] == []
    assert preview["lanes"][0]["staffing"] == "ready"
    assert preview["lanes"][0]["first_todo"]["priority"] == "P1"
    assert preview["quota_envelope"] == {"slots_per_day": 4}


def test_an_unregistered_agent_becomes_a_gap_instead_of_being_invented() -> None:
    plan = _plan()
    plan["lanes"][0]["agent_id"] = "agent-not-registered"  # type: ignore[index]

    preview = _validate(plan)

    lane = preview["lanes"][0]
    assert lane["staffing"] == "gap"
    assert lane["gap_reason_code"] == "agent_not_registered"
    # The work the owner asked for is kept with the gap, never silently dropped.
    assert lane["declined_first_todo"]["text"] == "Advance the intake contract"
    assert "first_todo" not in lane
    assert preview["gaps"] == [
        {"lane_id": "lane-alpha", "reason_code": "agent_not_registered"}
    ]
    assert preview["applies"] is False


def test_a_declared_gap_keeps_its_reason_and_carries_no_work() -> None:
    plan = _plan()
    lane = plan["lanes"][0]  # type: ignore[index]
    lane.pop("first_todo")
    lane["staffing_gap"] = {
        "reason_code": "capability_not_granted",
        "note": "The reviewer capability is not granted on this machine",
    }

    preview = _validate(plan)

    assert preview["gaps"] == [
        {"lane_id": "lane-alpha", "reason_code": "capability_not_granted"}
    ]
    with pytest.raises(ValueError, match="may not declare work"):
        _validate(
            _plan(
                lanes=[
                    {
                        **lane,
                        "first_todo": _plan()["lanes"][0]["first_todo"],  # type: ignore[index]
                    }
                ]
            )
        )


@pytest.mark.parametrize(
    "mutation,match",
    [
        ({"kind": "something_else"}, "kind is invalid"),
        ({"schema_version": "v0"}, "schema_version is invalid"),
        ({"lanes": []}, "requires 1..8 lanes"),
        ({"stop_condition": ""}, "stop_condition must be a non-empty string"),
        ({"quota_envelope": {}}, "requires a quota envelope"),
    ],
)
def test_a_malformed_preview_fails_closed(mutation: dict, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _validate(_plan(**mutation))


def test_the_preview_kind_is_settled_only_at_pre_settlement() -> None:
    """The kind applies through one phase of the canonical owner, and nowhere else."""

    assert _SETTLEMENT_PHASE_BY_PROPOSAL_KIND[STEWARD_TEAM_PLAN_PREVIEW_KIND] is (
        GovernedTransitionSettlementPhase.PRE_SETTLEMENT
    )


def test_the_chat_normalizer_admits_a_preview_only_with_host_facts() -> None:
    """The production caller: one malformed or unproven preview never surfaces."""

    from loopx.chat import normalize_agent_response

    envelope = {
        "message": "Here is the plan",
        "proposals": [_plan()],
        "context_handoff": None,
        "protected_action": None,
        "gate": None,
    }
    context = {
        "registered_agent_ids": ["agent-alpha"],
        "supported_action_kinds": ["implement"],
    }

    surfaced = normalize_agent_response(envelope, team_plan_context=context)
    proposals = surfaced["proposals"]
    assert [item["kind"] for item in proposals] == [
        "steward_team_plan_preview"
    ]
    assert proposals[0]["preview"]["applies"] is False
    assert proposals[0]["preview"]["lanes"][0]["staffing"] == "ready"

    # Without the host facts the preview cannot be validated, so it is not
    # surfaced at all rather than admitted half-checked.
    assert normalize_agent_response(envelope)["proposals"] == []

    # A malformed preview is dropped like any other proposal the normalizer
    # cannot accept, and the owner's answer text still arrives.
    malformed = {**envelope, "proposals": [_plan(kind="not_a_plan")]}
    dropped = normalize_agent_response(malformed, team_plan_context=context)
    assert dropped["proposals"] == []
    assert dropped["message"] == "Here is the plan"

    # The plain Todo proposals keep their existing behaviour.
    todo = {
        **envelope,
        "proposals": [
            {"kind": "todo", "text": "Do one thing", "priority": "P2", "rationale": "why"}
        ],
    }
    assert normalize_agent_response(todo)["proposals"] == [
        {"kind": "todo", "text": "Do one thing", "priority": "P2", "rationale": "why"}
    ]
