"""Lane scoping for the completion-validation fence.

The fence stops an agent from claiming accountable evidence while its own
controller-validated Todo is still open. It used to skip its scope filter when
the settlement bound a replan obligation instead of a Todo, so any open
unclaimed validation-gated Todo fenced every lane.

The public-safe text contract that shipped with this fix now lives in
tests/control_plane/test_public_safe_text_owner_parity.py, because it is a
cross-owner contract rather than a completion-validation rule.
"""

from __future__ import annotations

from loopx.control_plane.todos.completion_validation_accountability import (
    require_accountable_completion_validation,
)
from loopx.control_plane.todos.completion_validation_projection import (
    pending_completion_validation_todo,
)
from loopx.control_plane.turn_driver.delivery_continuity import (
    DELIVERY_BOUNDARY_IN_FLIGHT,
)

LANE_AGENT = "kiro-cli"
OTHER_AGENT = "codex-main-control"


def _summary(*items: dict[str, object]) -> dict[str, object]:
    return {"items": list(items)}


def _gated(
    todo_id: str,
    *,
    claimed_by: str | None,
    status: str = "open",
) -> dict[str, object]:
    return {
        "todo_id": todo_id,
        "status": status,
        "claimed_by": claimed_by,
        "completion_validation_required": True,
    }


def test_lane_fence_ignores_unclaimed_validation_todo() -> None:
    """An unclaimed gated Todo owns no lane, so it must not fence another lane.

    The fence exists to stop an agent from claiming accountable evidence while
    its own controller-validated Todo is still open. A Todo nobody claimed has
    no owning lane, so it cannot be "its own" for any agent.
    """

    summary = _summary(_gated("todo_unclaimed", claimed_by=None))

    assert (
        pending_completion_validation_todo(
            summary,
            todo_id=None,
            agent_id=LANE_AGENT,
        )
        is None
    )


def test_lane_fence_ignores_other_lane_validation_todo() -> None:
    summary = _summary(_gated("todo_other_lane", claimed_by=OTHER_AGENT))

    assert (
        pending_completion_validation_todo(
            summary,
            todo_id=None,
            agent_id=LANE_AGENT,
        )
        is None
    )


def test_lane_fence_still_blocks_own_claimed_validation_todo() -> None:
    summary = _summary(_gated("todo_own_lane", claimed_by=LANE_AGENT))

    pending = pending_completion_validation_todo(
        summary,
        todo_id=None,
        agent_id=LANE_AGENT,
    )

    assert pending is not None
    assert pending["todo_id"] == "todo_own_lane"


def test_exact_todo_fence_blocks_regardless_of_claim() -> None:
    """Naming a Todo in the settlement binds it, so an unclaimed one still fences."""

    summary = _summary(_gated("todo_named", claimed_by=None))

    pending = pending_completion_validation_todo(
        summary,
        todo_id="todo_named",
        agent_id=LANE_AGENT,
    )

    assert pending is not None
    assert pending["todo_id"] == "todo_named"


def test_exact_todo_fence_releases_when_done() -> None:
    summary = _summary(_gated("todo_named", claimed_by=LANE_AGENT, status="done"))

    assert (
        pending_completion_validation_todo(
            summary,
            todo_id="todo_named",
            agent_id=LANE_AGENT,
        )
        is None
    )


def _state_with_unclaimed_gated_todo() -> str:
    return "\n".join(
        [
            "## Agent Todo",
            "",
            "- [ ] Fix the reported control-plane defect.",
            "  <!-- loopx:todo todo_id=todo_unclaimed status=open"
            " task_class=advancement_task validation_command=pytest -->",
            "",
        ]
    )


def test_accountable_refresh_is_not_fenced_by_unclaimed_gated_todo() -> None:
    require_accountable_completion_validation(
        _state_with_unclaimed_gated_todo(),
        todo_id=None,
        agent_id=LANE_AGENT,
    )


def test_in_flight_progress_is_not_fenced_by_open_validation_todo() -> None:
    """Intermediate evidence may settle without claiming Todo completion."""

    require_accountable_completion_validation(
        "",
        todo_id="todo_named",
        agent_id=LANE_AGENT,
        todo_fields={
            "agent_todos": _summary(
                _gated("todo_named", claimed_by=LANE_AGENT),
            )
        },
        delivery_boundary=DELIVERY_BOUNDARY_IN_FLIGHT,
        delivery_outcome="outcome_progress",
    )


def test_primary_outcome_still_requires_terminal_completion_validation() -> None:
    try:
        require_accountable_completion_validation(
            "",
            todo_id="todo_named",
            agent_id=LANE_AGENT,
            todo_fields={
                "agent_todos": _summary(
                    _gated("todo_named", claimed_by=LANE_AGENT),
                )
            },
            delivery_boundary=DELIVERY_BOUNDARY_IN_FLIGHT,
            delivery_outcome="primary_goal_outcome",
        )
    except ValueError as exc:
        assert "completion validation" in str(exc)
    else:
        raise AssertionError("primary outcome must not bypass terminal validation")
