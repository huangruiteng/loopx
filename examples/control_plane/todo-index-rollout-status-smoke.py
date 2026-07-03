#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loopx.status import build_todo_index


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

        index = build_todo_index(
            queue={"items": []},
            history={"goals": [{"id": "loopx-meta"}]},
            runtime_root=runtime_root,
        )

    items = index["items"]
    assert len(items) == 1, items
    item = items[0]
    assert item["todo_id"] == "todo_done_status", item
    assert item["latest_event_kind"] == "todo_complete", item
    assert item["latest_event_status"] == "done", item
    assert item["status"] == "done", item
    assert item["done"] is True, item
    print("todo-index-rollout-status smoke ok")


if __name__ == "__main__":
    main()
