#!/usr/bin/env python3
"""Smoke-test the minimal append-only LoopX state event API."""

from __future__ import annotations

import tempfile
from pathlib import Path

import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    StateEventConflictError,
    StateEventError,
    TODO_ADDED,
    TODO_BLOCKED,
    TODO_CLAIMED,
    TODO_COMPLETED,
    TODO_UPDATED,
    REFRESH_RECORDED,
    build_state_projection,
    make_state_event,
    render_active_state_sections,
)
from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "event-sourced-state-api-fixture"


def todo_event(event_id: str, event_type: str, todo_id: str, payload: dict) -> dict:
    return make_state_event(
        event_id=event_id,
        goal_id=GOAL_ID,
        event_type=event_type,
        refs={"todo_id": todo_id},
        payload=payload,
        recorded_at=f"2026-06-27T00:00:{len(event_id):02d}Z",
        producer="event-sourced-state-api-smoke",
    )


def test_store_projection_and_markdown() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-store-") as tmp:
        store = AppendOnlyStateEventStore(Path(tmp) / "events.jsonl")
        todo_a = todo_event(
            "evt-todo-a",
            TODO_ADDED,
            "todo_event_a",
            {
                "role": "agent",
                "priority": "P0",
                "title": "Implement append-only event store",
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "implement",
            },
        )
        todo_b = todo_event(
            "evt-todo-b",
            TODO_ADDED,
            "todo_event_b",
            {
                "role": "agent",
                "priority": "P0",
                "title": "Render Markdown-compatible active-state sections",
                "planner_order": 2,
                "task_class": "advancement_task",
                "action_kind": "validate",
            },
        )
        user_gate = todo_event(
            "evt-user-gate",
            TODO_ADDED,
            "todo_user_gate",
            {
                "role": "user",
                "priority": "P1",
                "title": "Approve promoting event projection to status reads",
                "planner_order": 1,
                "task_class": "user_gate",
            },
        )
        store.append(todo_b)
        appended_a = store.append(todo_a)
        assert appended_a["append_sequence"] == 2, appended_a
        assert store.append(todo_a)["append_sequence"] == 2
        store.append(user_gate)
        store.append(
            todo_event(
                "evt-claim-a",
                TODO_CLAIMED,
                "todo_event_a",
                {"claimed_by": "codex-product-capability"},
            )
        )
        store.append(
            todo_event(
                "evt-update-b",
                TODO_UPDATED,
                "todo_event_b",
                {"title": "Render Markdown-compatible sections from projection"},
            )
        )
        store.append(
            todo_event(
                "evt-block-b",
                TODO_BLOCKED,
                "todo_event_b",
                {"reason": "blocked pending projection review"},
            )
        )
        store.append(
            todo_event(
                "evt-complete-a",
                TODO_COMPLETED,
                "todo_event_a",
                {"evidence": "event store smoke"},
            )
        )
        store.append(
            make_state_event(
                event_id="evt-refresh",
                goal_id=GOAL_ID,
                event_type=REFRESH_RECORDED,
                payload={"summary": "projection rendered from append-only events"},
                recorded_at="2026-06-27T00:01:00Z",
            )
        )

        projection = build_state_projection(store.load(), generated_at="2026-06-27T00:02:00Z")
        assert projection["schema_version"] == "event_sourced_state_projection_v0", projection
        assert projection["source_event_count"] == 8, projection
        assert projection["last_append_sequence"] == 8, projection
        assert [item["todo_id"] for item in projection["agent_todos"]["items"]] == [
            "todo_event_a",
            "todo_event_b",
        ], projection
        assert projection["agent_todos"]["items"][0]["status"] == "done", projection
        assert projection["agent_todos"]["items"][1]["status"] == "blocked", projection
        assert projection["user_todos"]["first_open_items"][0]["todo_id"] == "todo_user_gate", projection

        markdown = render_active_state_sections(projection)
        assert "## User Todo / Owner Review Reading Queue" in markdown, markdown
        assert "## Agent Todo" in markdown, markdown
        assert "todo_id=todo_event_a" in markdown, markdown
        assert "todo_id=todo_user_gate" in markdown, markdown
        assert "claimed_by=codex-product-capability" in markdown, markdown
        assert "## Progress Ledger" in markdown, markdown

        parsed = parse_active_state_todos(markdown)
        assert parsed["agent_todos"]["total_count"] == 2, parsed
        assert parsed["agent_todos"]["done_count"] == 1, parsed
        assert parsed["user_todos"]["open_count"] == 1, parsed


def test_conflicts_and_mutations_fail_closed() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-store-conflict-") as tmp:
        store = AppendOnlyStateEventStore(Path(tmp) / "events.jsonl")
        event = todo_event(
            "evt-conflict",
            TODO_ADDED,
            "todo_conflict",
            {"role": "agent", "priority": "P1", "title": "Stable event"},
        )
        store.append(event)
        conflict = dict(event)
        conflict["payload"] = dict(event["payload"])
        conflict["payload"]["title"] = "Different event body"
        try:
            store.append(conflict)
        except StateEventConflictError:
            pass
        else:
            raise AssertionError("conflicting duplicate event_id was accepted")

        mutation = todo_event(
            "evt-mutation",
            TODO_UPDATED,
            "todo_conflict",
            {"title": "Attempt mutation"},
        )
        mutation["refs"]["mutates_prior_event_id"] = "evt-conflict"
        try:
            store.append(mutation)
        except StateEventError as exc:
            assert "must not mutate prior events" in str(exc), exc
        else:
            raise AssertionError("prior event mutation was accepted")


def main() -> int:
    test_store_projection_and_markdown()
    test_conflicts_and_mutations_fail_closed()
    print("event-sourced-state-api-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
