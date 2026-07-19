from __future__ import annotations

from loopx.presentation.renderers.quota_event_markdown import (
    render_quota_monitor_poll_markdown,
    render_quota_slot_preview_markdown,
)


def test_monitor_poll_renderer_preserves_rejection_context() -> None:
    markdown = render_quota_monitor_poll_markdown(
        {
            "ok": False,
            "mode": "monitor-poll",
            "goal_id": "quality-goal",
            "agent_id": "codex-quality",
            "todo_id": "todo_monitor",
            "target_key": "release-watch",
            "material_change": False,
            "reason": "monitor target is not due",
        }
    )

    assert markdown.startswith("# LoopX Quota Monitor Poll")
    assert "- ok: `False`" in markdown
    assert "- agent_id: `codex-quality`" in markdown
    assert "- todo_id: `todo_monitor`" in markdown
    assert "- target_key: `release-watch`" in markdown
    assert "- reason: monitor target is not due" in markdown


def test_monitor_poll_renderer_preserves_decision_and_writeback_context() -> None:
    markdown = render_quota_monitor_poll_markdown(
        {
            "goal_id": "quality-goal",
            "classification": "quota_monitor_poll",
            "health_check": "monitor observation recorded",
            "monitor_event": {
                "agent_id": "codex-quality",
                "source": "heartbeat",
                "monitor_target": {"target_id": "release-watch"},
                "todo_id": "todo_monitor",
                "target_key": "release-watch",
                "material_change": True,
                "reason_summary": "new release observed",
                "before": {
                    "effective_action": "monitor_quiet_skip",
                    "should_run": False,
                    "self_repair_allowed": False,
                    "state": "eligible",
                },
                "todo_writeback": {
                    "dry_run": False,
                    "consecutive_no_change": 0,
                    "last_checked_at": "2026-07-19T00:00:00Z",
                    "next_due_at": "2026-07-20T00:00:00Z",
                },
            },
        }
    )

    assert "- effective_action: `monitor_quiet_skip`" in markdown
    assert "- monitor_target: `release-watch`" in markdown
    assert "- material_change: `True`" in markdown
    assert "consecutive_no_change=0" in markdown
    assert "- reason: new release observed" in markdown


def test_slot_renderer_preserves_accounting_transition_context() -> None:
    markdown = render_quota_slot_preview_markdown(
        {
            "ok": True,
            "dry_run": False,
            "goal_id": "quality-goal",
            "classification": "quota_slot_spent",
            "agent_id": "codex-quality",
            "slots": 1,
            "appended": True,
            "registry_mutated": False,
            "would_throttle": False,
            "json_path": "/runtime/run.json",
            "index_path": "/runtime/index.jsonl",
            "before": {
                "state": "eligible",
                "should_run": True,
                "quota": {"spent_slots": 4, "allowed_slots": 10},
            },
            "after": {
                "state": "eligible",
                "should_run": True,
                "quota": {"spent_slots": 5, "allowed_slots": 10},
                "plan_summary": {"next_automatic_turn": "quality-goal"},
            },
            "rolling_window_note": "older events may expire",
        }
    )

    assert markdown.startswith("# LoopX Quota Slot Preview")
    assert "- before: state=eligible should_run=True slots=4/10" in markdown
    assert "- after: state=eligible should_run=True slots=5/10" in markdown
    assert "- after_plan_next_automatic_turn: quality-goal" in markdown
    assert "- rolling_window_note: older events may expire" in markdown
