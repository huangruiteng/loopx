#!/usr/bin/env python3
"""Smoke-test shared todo summary item compaction and source aggregation."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.summary_item import (  # noqa: E402
    compact_todo_summary_item,
    todo_summary_source_items,
)


GATE_ID = "todo_gate_done"
SUCCESSOR_ID = "todo_successor"
SUCCESSOR_TEXT = "[P1] Resume after the handoff gate is cleared."
DUPLICATE_TEXT = "[P2] Keep only one no-id duplicate."


def successor_item(**overrides: object) -> dict:
    item = {
        "index": 2,
        "todo_id": SUCCESSOR_ID,
        "text": SUCCESSOR_TEXT,
        "status": "open",
        "task_class": "advancement_task",
        "resume_when": f"todo_done:{GATE_ID}",
        "unblocks_todo_id": GATE_ID,
        "required_write_scopes": [" loopx/** ", "loopx/**"],
        "decision_scope": "direction:action:claim",
        "claimed_by": "codex-product-capability",
    }
    item.update(overrides)
    return item


def assert_compact_item_normalizes_shared_contract() -> None:
    compact = compact_todo_summary_item(successor_item())
    assert compact["todo_id"] == SUCCESSOR_ID, compact
    assert compact["required_write_scopes"] == ["loopx/**"], compact
    assert compact["decision_scope"]["scope_key"] == "claim", compact
    assert compact["task_class"] == "advancement_task", compact


def assert_source_items_dedupe_and_mark_handoff_successor_ready() -> None:
    value = {
        "first_open_items": [
            successor_item(),
            {
                "index": 4,
                "text": DUPLICATE_TEXT,
                "status": "open",
                "task_class": "advancement_task",
            },
            {
                "index": 5,
                "text": "   ",
                "status": "open",
            },
        ],
        "backlog_items": [
            successor_item(text="[P1] Later duplicate must not replace first source."),
            {
                "index": 4,
                "text": DUPLICATE_TEXT,
                "status": "open",
                "task_class": "advancement_task",
            },
        ],
        "items": [
            {
                "index": 1,
                "todo_id": GATE_ID,
                "text": "[P0] Cleared handoff gate.",
                "status": "done",
                "done": True,
                "task_class": "blocker",
                "continuation_policy": "independent_handoff",
                "excluded_agents": ["codex-product-capability"],
                "unblocks_todo_id": SUCCESSOR_ID,
            },
            successor_item(index=3),
        ],
    }

    items = todo_summary_source_items(value)
    assert [item.get("todo_id") for item in items] == [SUCCESSOR_ID, None], items
    successor = items[0]
    assert successor["text"] == SUCCESSOR_TEXT, successor
    assert successor["resume_ready"] is True, successor
    assert successor["resume_condition"] == {
        "schema_version": "todo_resume_condition_v0",
        "resume_when": f"todo_done:{GATE_ID}",
        "satisfied": True,
        "source": "handoff_gate_cleared_with_successor",
    }, successor
    assert items[1]["text"] == DUPLICATE_TEXT, items


def main() -> int:
    assert_compact_item_normalizes_shared_contract()
    assert_source_items_dedupe_and_mark_handoff_successor_ready()
    print("todo-summary-item-source-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
