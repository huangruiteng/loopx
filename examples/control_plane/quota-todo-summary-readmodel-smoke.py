#!/usr/bin/env python3
"""Smoke-test the quota-facing todo summary read model."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.quota_summary import (  # noqa: E402
    is_user_gate_todo_item,
    select_quota_todo_summary,
    summarize_project_asset_todos_for_quota,
    summarize_user_todos_for_quota,
)


AGENT_IDENTITY = {"agent_id": "codex-product-capability"}


def canonical_todo_summary() -> dict:
    return {
        "schema_version": "todo_summary_v0",
        "source_section": "agent todo",
        "total_count": 6,
        "open_count": 5,
        "done_count": 1,
        "monitor_writeback": {"supported": True, "source": "active_state"},
        "items": [
            {
                "index": 1,
                "todo_id": "todo_gate_current",
                "text": "Owner approval before product capability write",
                "task_class": "user_gate",
                "action_kind": "approval",
                "blocks_agent": "codex-product-capability",
            },
            {
                "index": 2,
                "todo_id": "todo_gate_other",
                "text": "Owner approval before main-control write",
                "task_class": "user_gate",
                "action_kind": "approval",
                "blocks_agent": "codex-main-control",
            },
            {
                "index": 3,
                "todo_id": "todo_monitor_due",
                "text": "Monitor scheduler transition",
                "task_class": "continuous_monitor",
                "claimed_by": "codex-product-capability",
                "next_due_at": "2000-01-01T00:00:00+00:00",
                "target_key": "scheduler_transition",
            },
            {
                "index": 4,
                "todo_id": "todo_monitor_gap",
                "text": "Monitor missing schedule metadata",
                "task_class": "continuous_monitor",
                "claimed_by": "codex-product-capability",
                "target_key": "schedule_gap",
            },
            {
                "index": 5,
                "todo_id": "todo_refactor_next",
                "text": "[P1] Continue quota/todo state-machine refactor",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
        ],
        "active_next_action_items": [
            {
                "index": 5,
                "todo_id": "todo_refactor_next",
                "text": "[P1] Continue quota/todo state-machine refactor",
                "task_class": "advancement_task",
                "claimed_by": "codex-product-capability",
            },
            {
                "index": 6,
                "todo_id": "todo_other_agent_next",
                "text": "[P1] Other agent active-next item",
                "task_class": "advancement_task",
                "claimed_by": "codex-main-control",
            },
        ],
        "todo_succession_warning": {
            "schema_version": "todo_succession_warning_v0",
            "reason_code": "completed_advancement_without_successor",
            "count": 1,
            "items": [
                {
                    "index": 7,
                    "todo_id": "todo_done_without_successor",
                    "text": "[P1] Finished state-machine canary without successor",
                    "status": "done",
                    "done": True,
                    "task_class": "advancement_task",
                    "action_kind": "state_machine_canary_refactor",
                    "claimed_by": "codex-product-capability",
                }
            ],
        },
    }


def assert_agent_scoped_user_gate_and_monitor_state() -> None:
    summary = summarize_user_todos_for_quota(
        canonical_todo_summary(),
        agent_identity=AGENT_IDENTITY,
        filter_user_gate_blocks_agent=True,
    )
    assert summary is not None
    assert summary["open_count"] == 1, summary
    assert summary["all_open_count"] == 5, summary
    assert summary["user_action_open_count"] == 4, summary
    assert summary["other_agent_scoped_open_count"] == 1, summary
    assert summary["gate_open_items"][0]["todo_id"] == "todo_gate_current", summary
    assert {
        item.get("todo_id")
        for item in summary["other_agent_scoped_items"]
    } == {"todo_gate_other"}, summary
    assert {
        item.get("todo_id")
        for item in summary["user_action_items"]
    } == {
        "todo_monitor_due",
        "todo_monitor_gap",
        "todo_refactor_next",
        "todo_other_agent_next",
    }, summary

    assert summary["monitor_due_count"] == 0, summary
    assert summary["monitor_due_items"] == [], summary
    assert summary["monitor_schedule_gap_count"] == 0, summary
    assert summary["monitor_schedule_gap_items"] == [], summary
    assert summary["active_next_action_items"][0]["todo_id"] == "todo_refactor_next", summary
    assert all(
        item.get("todo_id") != "todo_other_agent_next"
        for item in summary["active_next_action_items"]
    ), summary
    assert summary["todo_succession_warning"]["count"] == 1, summary


def assert_project_asset_fallback_and_canonical_precedence() -> None:
    raw_canonical = {
        "source_section": "raw legacy queue",
        "items": [
            {
                "index": 1,
                "text": "raw fallback should not outrank project asset",
            }
        ],
    }
    project_asset = {
        "next": "[P1] Project asset selected todo",
        "next_index": 9,
        "next_claimed_by": "codex-product-capability",
    }
    selected = select_quota_todo_summary(
        raw_canonical,
        project_asset,
        agent_identity=AGENT_IDENTITY,
    )
    assert selected is not None
    assert selected["source_section"] == "project_asset", selected
    assert selected["first_open_items"][0]["index"] == 9, selected
    assert "Project asset selected todo" in selected["first_open_items"][0]["text"], selected

    canonical = canonical_todo_summary()
    selected = select_quota_todo_summary(
        canonical,
        {"next": "[P1] Project asset should lose"},
        agent_identity=AGENT_IDENTITY,
    )
    assert selected is not None
    assert selected["source_section"] == "agent todo", selected
    assert any(
        item.get("todo_id") == "todo_gate_current"
        for item in selected["gate_open_items"]
    ), selected
    assert selected["first_executable_items"][0]["todo_id"] == "todo_refactor_next", selected


def assert_project_asset_summary_reuses_canonical_shape() -> None:
    canonical_shape = canonical_todo_summary()
    summary = summarize_project_asset_todos_for_quota(
        canonical_shape,
        agent_identity=AGENT_IDENTITY,
        filter_user_gate_blocks_agent=True,
    )
    assert summary is not None
    assert summary["source_section"] == "agent todo", summary
    assert summary["monitor_due_count"] == 0, summary
    assert summary["other_agent_scoped_open_count"] == 1, summary


def assert_user_gate_hint_detection_is_preserved() -> None:
    assert is_user_gate_todo_item(
        {
            "text": "Credential decision",
            "action_kind": "credential_rotation",
        }
    )
    assert not is_user_gate_todo_item(
        {
            "text": "Credential decision",
            "task_class": "advancement_task",
            "action_kind": "credential_rotation",
        }
    )
    assert is_user_gate_todo_item(
        {
            "text": "Public claim decision",
            "action_kind": "public_claim_review",
        }
    )


def main() -> None:
    assert_agent_scoped_user_gate_and_monitor_state()
    assert_project_asset_fallback_and_canonical_precedence()
    assert_project_asset_summary_reuses_canonical_shape()
    assert_user_gate_hint_detection_is_preserved()
    print("quota todo summary read model smoke passed")


if __name__ == "__main__":
    main()
