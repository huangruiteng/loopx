"""Regression coverage for the blocked-priority fallback notice (#4381).

A higher-priority Agent Todo that is blocked while an executable fallback
continues must stay visible to the owner. Informing the owner and requiring
owner action are different decisions: an agent-owned blocker says that no
owner action is required, and a scheduled future monitor window is a deferral
rather than a blocker, so it earns no notice at all.
"""

from __future__ import annotations

from typing import Any

from loopx.control_plane.quota.should_run_prepare import _blocked_priority_fallback

BLOCKED_TODO_ID = "todo_aaaaaaaaaaaa"
FALLBACK_TODO_ID = "todo_bbbbbbbbbbbb"


def _advancement_item(
    todo_id: str,
    text: str,
    *,
    status: str,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "todo_id": todo_id,
        "text": text,
        "status": status,
        "task_class": "advancement_task",
        **extra,
    }


def _fallback() -> dict[str, Any]:
    return _advancement_item(
        FALLBACK_TODO_ID,
        "[P1] Prepare independent documentation",
        status="open",
    )


def test_blocked_primary_todo_informs_the_owner_without_asking_for_action() -> None:
    blocked = _advancement_item(
        BLOCKED_TODO_ID,
        "[P0] Validate the primary deliverable",
        status="blocked",
        reason="Required input has not arrived",
    )

    fallback = _blocked_priority_fallback(
        {
            "first_open_items": [blocked, _fallback()],
            "first_executable_items": [_fallback()],
        }
    )

    assert fallback is not None
    assert fallback["kind"] == "blocked_priority_fallback"
    assert fallback["notify_user"] is True
    assert fallback["requires_user_action"] is False
    assert [item["todo_id"] for item in fallback["blocked_items"]] == [BLOCKED_TODO_ID]
    assert fallback["selected_executable"]["todo_id"] == FALLBACK_TODO_ID


def test_unsatisfied_resume_condition_counts_as_a_blocker() -> None:
    waiting = _advancement_item(
        BLOCKED_TODO_ID,
        "[P0] Validate the primary deliverable",
        status="open",
        resume_when=f"todo_done:{BLOCKED_TODO_ID}",
        resume_ready=False,
    )

    fallback = _blocked_priority_fallback(
        {
            "first_open_items": [waiting, _fallback()],
            "first_executable_items": [_fallback()],
        }
    )

    assert fallback is not None
    assert fallback["notify_user"] is True
    assert fallback["requires_user_action"] is False


def test_scheduled_future_monitor_stays_a_silent_deferral() -> None:
    future_monitor = {
        "todo_id": BLOCKED_TODO_ID,
        "text": "[P1-monitor] Observe the stable public fixture",
        "status": "open",
        "task_class": "continuous_monitor",
        "next_due_at": "2999-01-01T00:00:00Z",
    }

    fallback = _blocked_priority_fallback(
        {
            "first_open_items": [future_monitor, _fallback()],
            "first_executable_items": [_fallback()],
        }
    )

    assert fallback is not None
    assert fallback["notify_user"] is False
    assert fallback["requires_user_action"] is False
    assert "future monitor window" in fallback["reason"]


def test_open_advancement_todo_before_the_fallback_is_not_a_blocker() -> None:
    open_item = _advancement_item(
        BLOCKED_TODO_ID,
        "[P0] Validate the primary deliverable",
        status="open",
    )

    fallback = _blocked_priority_fallback(
        {
            "first_open_items": [open_item, _fallback()],
            "first_executable_items": [_fallback()],
        }
    )

    assert fallback is None
