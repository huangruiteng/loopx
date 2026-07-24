from __future__ import annotations

import json

from loopx.control_plane.quota.cli_projection import (
    QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
    compact_quota_should_run_cli_payload,
)
from loopx.presentation.renderers.quota_markdown import (
    render_quota_should_run_markdown,
)


def _items(count: int, *, prefix: str) -> list[dict[str, object]]:
    return [
        {
            "schema_version": "todo_item_v0",
            "todo_id": f"{prefix}-{index}",
            "text": f"{prefix} item {index}",
            "task_class": "advancement_task",
        }
        for index in range(count)
    ]


def test_compact_quota_should_run_cli_payload_keeps_decision_lanes_and_counts() -> None:
    backlog = _items(40, prefix="backlog")
    first_open = _items(5, prefix="open")
    first_executable = _items(4, prefix="execute")
    unclaimed = _items(5, prefix="unclaimed")
    monitor_due = _items(2, prefix="monitor")
    monitor_schedule_gap = _items(2, prefix="monitor-gap")
    payload = {
        "interaction_contract": {"mode": "bounded_delivery"},
        "selected_todo": {"todo_id": "execute-0"},
        "scheduler_hint": {"action": "run_now"},
        "agent_todo_summary": {
            "schema_version": "todo_summary_v0",
            "total_count": 50,
            "open_count": 40,
            "done_count": 10,
            "first_open_items": first_open,
            "first_executable_items": first_executable,
            "unclaimed_priority_open_items": unclaimed,
            "monitor_due_items": monitor_due,
            "monitor_schedule_gap_count": 2,
            "monitor_schedule_gap_items": monitor_schedule_gap,
            "backlog_items": backlog,
            "claimed_open_items": backlog,
            "claim_scope": {
                "schema_version": "agent_claim_scope_v0",
                "current_agent_claimed_open_count": 4,
                "other_agent_claimed_items": backlog,
            },
            "todo_succession_warning": {
                "count": 3,
                "items": backlog,
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(payload)

    assert compact["interaction_contract"] == payload["interaction_contract"]
    assert compact["selected_todo"] == payload["selected_todo"]
    assert compact["scheduler_hint"] == payload["scheduler_hint"]
    summary = compact["agent_todo_summary"]
    assert summary["total_count"] == 50
    assert summary["open_count"] == 40
    assert len(summary["first_open_items"]) == 3
    assert len(summary["first_executable_items"]) == 3
    assert [item["todo_id"] for item in summary["unclaimed_priority_open_items"]] == [
        "unclaimed-0",
        "unclaimed-1",
        "unclaimed-2",
    ]
    assert len(summary["monitor_due_items"]) == 1
    assert [item["todo_id"] for item in summary["monitor_schedule_gap_items"]] == [
        "monitor-gap-0",
    ]
    assert "backlog_items" not in summary
    assert "claimed_open_items" not in summary
    assert "other_agent_claimed_items" not in summary["claim_scope"]
    assert "items" not in summary["todo_succession_warning"]
    assert summary["todo_succession_warning"]["todo_ids"] == [
        "backlog-0",
        "backlog-1",
        "backlog-2",
    ]
    assert summary["payload_compaction"]["omitted_lanes"] == {
        "backlog_items": 40,
        "claim_scope.other_agent_claimed_items": 40,
        "claimed_open_items": 40,
        "first_executable_items": 1,
        "first_open_items": 2,
        "monitor_due_items": 1,
        "monitor_schedule_gap_items": 1,
        "todo_succession_warning.items": 40,
        "unclaimed_priority_open_items": 2,
    }
    assert summary["payload_compaction"]["full_detail_cold_path"] == (
        QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND
    )
    assert len(payload["agent_todo_summary"]["backlog_items"]) == 40

    larger_backlog = _items(400, prefix="backlog")
    larger_payload = {
        **payload,
        "agent_todo_summary": {
            **payload["agent_todo_summary"],
            "backlog_items": larger_backlog,
            "claimed_open_items": larger_backlog,
            "claim_scope": {
                **payload["agent_todo_summary"]["claim_scope"],
                "other_agent_claimed_items": larger_backlog,
            },
            "todo_succession_warning": {
                "count": 300,
                "items": larger_backlog,
            },
        },
    }
    larger_compact = compact_quota_should_run_cli_payload(larger_payload)
    compact_chars = len(json.dumps(compact, sort_keys=True))
    larger_compact_chars = len(json.dumps(larger_compact, sort_keys=True))
    assert compact_chars < 10_000
    assert larger_compact_chars - compact_chars < 200


def test_compact_quota_should_run_cli_payload_keeps_succession_warning_identity_in_markdown() -> None:
    payload = {
        "ok": True,
        "goal_id": "succession-warning-fixture",
        "agent_todo_summary": {
            "total_count": 5,
            "open_count": 1,
            "completed_without_successor_count": 4,
            "first_open_items": _items(1, prefix="open"),
            "todo_succession_warning": {
                "reason_code": "completed_advancement_without_successor",
                "count": 4,
                "items": _items(4, prefix="repair"),
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(payload)
    warning = compact["agent_todo_summary"]["todo_succession_warning"]

    assert warning["todo_ids"] == ["repair-0", "repair-1", "repair-2"]
    assert "items" not in warning
    markdown = render_quota_should_run_markdown(compact)
    assert (
        "- agent_todo_succession_warning: "
        "reason=completed_advancement_without_successor "
        "count=4 todo_ids=repair-0,repair-1,repair-2"
    ) in markdown
    assert "todo_ids=n/a" not in markdown


def test_compact_quota_should_run_cli_payload_keeps_unclaimed_and_monitor_repair_identity_in_markdown() -> None:
    payload = {
        "ok": True,
        "goal_id": "routing-identity-fixture",
        "agent_todo_summary": {
            "total_count": 8,
            "open_count": 8,
            "claimed_open_count": 3,
            "unclaimed_open_count": 5,
            "monitor_schedule_gap_count": 2,
            "first_open_items": _items(3, prefix="claimed"),
            "unclaimed_priority_open_items": _items(5, prefix="unclaimed"),
            "monitor_schedule_gap_items": _items(2, prefix="monitor-gap"),
        },
    }

    compact = compact_quota_should_run_cli_payload(payload)
    summary = compact["agent_todo_summary"]

    assert [item["todo_id"] for item in summary["unclaimed_priority_open_items"]] == [
        "unclaimed-0",
        "unclaimed-1",
        "unclaimed-2",
    ]
    assert [item["todo_id"] for item in summary["monitor_schedule_gap_items"]] == [
        "monitor-gap-0",
    ]
    markdown = render_quota_should_run_markdown(compact)
    assert (
        "- agent_todo_unclaimed_candidates: "
        "todo_ids=unclaimed-0,unclaimed-1,unclaimed-2"
    ) in markdown
    assert (
        "- agent_todo_monitor_schedule_gap: todo_ids=monitor-gap-0"
    ) in markdown
