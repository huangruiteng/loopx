#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx import status as status_module
from loopx.control_plane.todos.todo_index import build_todo_index as build_todo_index_read_model


def write_event(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def main() -> None:
    with tempfile.TemporaryDirectory() as raw_tmp:
        runtime_root = Path(raw_tmp)
        event_log = runtime_root / "goals" / "loopx-meta" / "rollout-event-log.jsonl"
        write_event(
            event_log,
            {
                "schema_version": "loopx_rollout_event_v0",
                "event_kind": "todo_add",
                "goal_id": "loopx-meta",
                "todo_id": "todo_done_status",
                "status": "open",
                "recorded_at": "2026-06-22T16:00:00Z",
                "details": {"role": "agent"},
            },
        )
        write_event(
            event_log,
            {
                "schema_version": "loopx_rollout_event_v0",
                "event_kind": "todo_complete",
                "goal_id": "loopx-meta",
                "todo_id": "todo_done_status",
                "recorded_at": "2026-06-22T16:05:00Z",
                "details": {"role": "agent"},
            },
        )

        history = {"goals": [{"id": "loopx-meta"}]}
        event_only_index = status_module.build_todo_index(
            queue={"items": []},
            history=history,
            runtime_root=runtime_root,
        )
        queue = {
            "items": [
                {
                    "goal_id": "loopx-meta",
                    "agent_todos": {
                        "items": [
                            {
                                "todo_id": "todo_done_status",
                                "status": "open",
                                "title": "Confirm rollout status merge",
                                "text": "Confirm rollout status merge",
                            }
                        ]
                    },
                }
            ]
        }
        index = status_module.build_todo_index(
            queue=queue,
            history=history,
            runtime_root=runtime_root,
        )
        read_model_index = build_todo_index_read_model(
            queue=queue,
            history=history,
            runtime_root=runtime_root,
            public_safe_compact_text=status_module.public_safe_compact_text,
        )

    event_only_items = event_only_index["items"]
    assert len(event_only_items) == 1, event_only_items
    assert event_only_items[0]["source"] == "rollout_event_log", event_only_items[0]

    assert read_model_index == index, (read_model_index, index)
    assert index["current_projected_count"] == 1, index
    assert index["rollout_event_count"] == 2, index
    items = index["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["todo_id"] == "todo_done_status", item
    assert item["source"] == "attention_queue", item
    assert item["event_count"] == 2, item
    assert item["event_kinds"] == ["todo_add", "todo_complete"], item
    assert item["latest_event_kind"] == "todo_complete", item
    assert item["latest_event_status"] == "done", item
    assert item["status"] == "done", item
    assert item["done"] is True, item
    print("todo-index-rollout-status smoke ok")


if __name__ == "__main__":
    main()
