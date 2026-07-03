#!/usr/bin/env python3
"""Validate that status todo reads prefer event projection with Markdown fallback."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    TODO_ADDED,
    TODO_CLAIMED,
    make_state_event,
)
from loopx.status import active_state_todo_fields  # noqa: E402


GOAL_ID = "event-sourced-status-read-fixture"


def write_active_state(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "\n".join(
            [
                "# Fixture State",
                "",
                "## Next Action",
                "",
                "- Keep the current status read path stable.",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P2] Stale Markdown todo that should lose to events.",
                "  <!-- loopx:todo todo_id=todo_markdown_stale status=open task_class=advancement_task action_kind=stale -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


def append_event_todos(event_log: Path) -> None:
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        make_state_event(
            event_id="evt-add-agent-status-read",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": "todo_event_status_read"},
            payload={
                "role": "agent",
                "priority": "P0",
                "title": "Prefer event projection for status todo reads",
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "event_projection_read_path",
            },
            producer="event-sourced-status-read-path-smoke",
            recorded_at="2026-06-27T00:00:01Z",
        )
    )
    store.append(
        make_state_event(
            event_id="evt-claim-agent-status-read",
            goal_id=GOAL_ID,
            event_type=TODO_CLAIMED,
            refs={"todo_id": "todo_event_status_read"},
            payload={"claimed_by": "codex-product-capability"},
            producer="event-sourced-status-read-path-smoke",
            recorded_at="2026-06-27T00:00:02Z",
        )
    )


def event_todo_ids(fields: dict) -> list[str]:
    agent_todos = fields.get("agent_todos") or {}
    return [str(item.get("todo_id") or "") for item in agent_todos.get("items") or []]


def test_event_projection_preferred() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-status-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        write_active_state(state_path)
        append_event_todos(state_path.with_name("events.jsonl"))

        goal = {
            "id": GOAL_ID,
            "repo": str(project),
            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        }
        fields = active_state_todo_fields(goal)
        assert fields["state_event_projection"]["source"] == "event_log", fields
        assert fields["state_event_projection"]["last_append_sequence"] == 2, fields
        assert event_todo_ids(fields) == ["todo_event_status_read"], fields
        assert "todo_markdown_stale" not in event_todo_ids(fields), fields
        assert fields["agent_todos"]["items"][0]["claimed_by"] == "codex-product-capability", fields


def test_markdown_fallback_without_valid_event_log() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-status-fallback-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        write_active_state(state_path)
        goal = {
            "id": GOAL_ID,
            "repo": str(project),
            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        }

        fields = active_state_todo_fields(goal)
        assert event_todo_ids(fields) == ["todo_markdown_stale"], fields
        assert "state_event_projection" not in fields, fields

        state_path.with_name("events.jsonl").write_text("{not json\n", encoding="utf-8")
        corrupted_fields = active_state_todo_fields(goal)
        assert event_todo_ids(corrupted_fields) == ["todo_markdown_stale"], corrupted_fields
        assert corrupted_fields["state_event_projection_warning"]["fallback"] == "markdown_active_state", (
            corrupted_fields
        )


def main() -> int:
    test_event_projection_preferred()
    test_markdown_fallback_without_valid_event_log()
    print("event-sourced-status-read-path-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
