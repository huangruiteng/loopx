"""The steward's shipped guidance owns the one-sentence team plan contract."""

from __future__ import annotations

from loopx.chat_manager import manager_skill_text


def test_manager_guidance_orders_one_team_preview_before_any_effect() -> None:
    """A team request is answered with one preview, never with silent creates."""

    text = manager_skill_text()

    ordered = [
        "the lanes and the Agent each one runs on",
        "the first bounded Todo per lane",
        "quota or cadence envelope",
        "acceptance signal",
        "stop condition",
    ]
    positions = [text.index(marker) for marker in ordered]
    assert positions == sorted(positions), ordered

    # The preview gates every effect, and the effects keep their canonical owners.
    assert "proposal, never an effect" in text
    assert "until the owner confirms that exact preview" in text
    # A plan is admitted only for the Goal it names, and the confirmation is the
    # product surface's typed action rather than something the steward performs.
    assert "Name the exact Goal the plan\nstaffs" in text
    assert "dropped instead of shown" in text
    assert "typed team-plan action from the product\nsurface" in text
    # A lane may not be claimed to exist before its apply receipt returns.
    assert "before the\napply receipt returns" in text
    assert "the plan went stale" in text
    assert "Agent\nregistration, Todo creation, quota or goal policy" in text
    assert "charge quota for the preview itself" in text
    # An unstaffable lane is named as a gap rather than invented.
    assert "as a gap, with the missing registration or grant" in text
    # Guidance is read as prose, so its phrases are compared as prose: a line
    # wrap is a layout choice, not a change in what the steward is told.
    prose = " ".join(text.split())
    assert "instead of inventing a lane, an Agent, a capability, or an action kind" in prose


def test_the_owner_visible_failure_names_the_executor_that_refused() -> None:
    """A host gate is the executor's refusal, not a defect in the manager."""

    from loopx.extensions.lark.manager_context import manager_failure_reply

    class _Refused(RuntimeError):
        error_code = "host_gate"

    code, text = manager_failure_reply(_Refused("upstream refused"))

    assert code == "host_gate"
    assert "上游执行器" in text
    assert "管家处理失败" not in text
    # An unmapped code still falls back to the bounded generic label.
    class _Unknown(RuntimeError):
        error_code = "some_future_code"

    assert manager_failure_reply(_Unknown("x"))[0] == "processing_failed"


def test_manager_guidance_ships_the_machine_readable_preview_contract() -> None:
    """The preview the owner confirms is the one admission can validate.

    Prose alone cannot reach the product surface: admission only surfaces a
    team preview that arrives as this typed item, so guidance that never states
    the item leaves a live steward answering correctly and still offering the
    owner nothing to confirm. The guidance and the validator therefore share
    their identifiers, and drift fails here instead of in a live answer.
    """

    from loopx.control_plane.work_items.governed_transition_proposal import (
        STEWARD_TEAM_PLAN_GAP_REASONS,
        STEWARD_TEAM_PLAN_LANE_LIMIT,
        STEWARD_TEAM_PLAN_PREVIEW_KIND,
        STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION,
    )

    text = manager_skill_text()

    assert STEWARD_TEAM_PLAN_PREVIEW_KIND in text
    assert STEWARD_TEAM_PLAN_PREVIEW_SCHEMA_VERSION in text
    assert "proposals" in text
    assert f"{STEWARD_TEAM_PLAN_LANE_LIMIT} lanes" in text
    for field in (
        '"goal_id"',
        '"objective"',
        '"lanes"',
        '"lane_id"',
        '"agent_id"',
        '"acceptance"',
        '"first_todo"',
        '"action_kind"',
        '"task_class"',
        '"quota_envelope"',
        '"stop_condition"',
    ):
        assert field in text, field
    assert "staffing_gap" in text
    assert "declares\nno `first_todo`" in text
    assert "advancement_task" in text
    for reason in STEWARD_TEAM_PLAN_GAP_REASONS:
        assert reason in text, reason
    # The preview never claims an effect of its own.
    assert "is dropped\nrather than shown" in text


def test_manager_guidance_names_the_action_kinds_the_host_ships() -> None:
    """A lane's kind is chosen from the shipped set, not invented from the ask.

    Live evidence: a steward answered a one-sentence team request and named the
    kind it thought the work deserved, which no host ships, so its lane could
    not be staffed. The guidance and the contract therefore share one list, and
    a kind added to the contract without guidance (or named in guidance without
    the contract) fails here instead of in a live answer.
    """

    from loopx.control_plane.todos.contract import (
        TODO_ACTION_KIND_ADVANCEMENT_VALUES,
    )
    from loopx.control_plane.work_items.governed_transition_proposal import (
        STEWARD_TEAM_PLAN_GAP_REASONS,
        STEWARD_TEAM_PLAN_HOST_GAP_REASONS,
        STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND,
    )

    text = manager_skill_text()

    assert "must be one this host ships" in text
    for action_kind in TODO_ACTION_KIND_ADVANCEMENT_VALUES:
        assert f"`{action_kind}`" in text, action_kind
    # The host's own verdict about a lane is not part of what a plan may declare
    # about itself, so guidance that offered it as a declared reason would be
    # guidance to describe a lane as something the host decided.
    assert STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND not in (
        STEWARD_TEAM_PLAN_GAP_REASONS
    )
    assert STEWARD_TEAM_PLAN_UNSUPPORTED_ACTION_KIND in STEWARD_TEAM_PLAN_HOST_GAP_REASONS
