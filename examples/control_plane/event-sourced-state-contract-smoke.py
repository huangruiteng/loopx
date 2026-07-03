#!/usr/bin/env python3
"""Smoke-test event-sourced todo/history contract invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = REPO_ROOT / "docs/reference/protocols/event-sourced-state-contract-v0.md"
PROTOCOL_INDEX = REPO_ROOT / "docs/reference/protocols/README.md"
STATE_MODEL = REPO_ROOT / "docs/state-interaction-model.md"


PUBLIC_FORBIDDEN = (
    "/Users/",
    "/home/",
    "/private/tmp/",
    "Bearer ",
    "AKIA",
)


@dataclass
class EventStore:
    events_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: dict[str, Any]) -> None:
        event_id = event["event_id"]
        existing = self.events_by_id.get(event_id)
        normalized = dict(sorted(event.items()))
        if existing is not None:
            if dict(sorted(existing.items())) != normalized:
                raise ValueError(f"conflicting event_id: {event_id}")
            return
        if event.get("event_type") == "event_mutated":
            raise ValueError("events must not mutate prior events")
        if "mutates_prior_event_id" in event.get("refs", {}):
            raise ValueError("events must not mutate prior events")
        self.events_by_id[event_id] = normalized
        self.events.append(normalized)

    def replay_todos(self) -> dict[str, Any]:
        todos: dict[str, dict[str, Any]] = {}
        completed: list[str] = []
        for event in sorted(
            self.events,
            key=lambda item: (
                item["append_sequence"],
                item["recorded_at"],
                item["event_id"],
            ),
        ):
            event_type = event["event_type"]
            todo_id = event.get("refs", {}).get("todo_id")
            if event_type == "todo_added":
                todos[todo_id] = {
                    "todo_id": todo_id,
                    "priority": event["payload"]["priority"],
                    "role": event["payload"]["role"],
                    "title": event["payload"]["title"],
                    "planner_order": event["payload"].get("planner_order"),
                    "append_sequence": event["append_sequence"],
                    "status": "open",
                }
            elif event_type == "todo_claimed":
                todos[todo_id]["claimed_by"] = event["payload"]["claimed_by"]
            elif event_type == "todo_blocked":
                todos[todo_id]["status"] = "blocked"
                todos[todo_id]["blocker"] = event["payload"]["reason"]
            elif event_type == "todo_completed":
                todos[todo_id]["status"] = "done"
                completed.append(todo_id)

        open_todos = [
            todo for todo in todos.values() if todo.get("status") in {"open", "blocked"}
        ]
        open_todos.sort(
            key=lambda todo: (
                todo["priority"],
                todo.get("planner_order") or 9999,
                todo["append_sequence"],
            )
        )
        return {
            "schema_version": "event_sourced_state_projection_v0",
            "goal_id": "loopx-meta",
            "source_event_count": len(self.events),
            "last_event_id": self.events[-1]["event_id"],
            "last_append_sequence": self.events[-1]["append_sequence"],
            "projection_version": "event_sourced_state_contract_v0",
            "open_todos": open_todos,
            "completed_todo_ids": completed,
        }


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_contract_text() -> None:
    contract = read(CONTRACT)
    compact = " ".join(contract.split())
    for required in [
        "# event_sourced_state_contract_v0",
        "ACTIVE_GOAL_STATE.md` remains the human/agent workbench",
        "Markdown edits are not canonical state changes",
        "append_sequence` is the final same-priority tie-breaker",
        "public_safe",
        "local_private",
        "private_pointer",
        "last_append_sequence",
        "projection_version",
        "raw chat transcripts",
        "raw logs",
        "duplicate conflicting `event_id` append fails closed",
        "Tracked outputs require explicit redaction or compact pointers",
    ]:
        assert required in contract, required

    for event_type in [
        "todo_added",
        "todo_claimed",
        "todo_updated",
        "todo_blocked",
        "todo_deferred",
        "todo_completed",
        "gate_added",
        "gate_resolved",
        "run_recorded",
        "refresh_recorded",
        "quota_spent",
        "evidence_attached",
        "projection_rendered",
        "snapshot_compacted",
    ]:
        assert f"`{event_type}`" in contract, event_type

    for forbidden in PUBLIC_FORBIDDEN:
        assert forbidden not in compact, forbidden


def test_docs_are_linked() -> None:
    index = read(PROTOCOL_INDEX)
    state_model = read(STATE_MODEL)
    assert "event_sourced_state_contract_v0" in index, index
    assert "event-sourced-state-contract-v0.md" in index, index
    assert "event_sourced_state_contract_v0" in state_model, state_model
    assert "ACTIVE_GOAL_STATE.md` stays the human/agent workbench" in state_model


def event(
    event_id: str,
    event_type: str,
    append_sequence: int,
    todo_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "loopx_state_event_v0",
        "event_id": event_id,
        "goal_id": "loopx-meta",
        "event_type": event_type,
        "recorded_at": f"2026-06-27T00:00:{append_sequence:02d}Z",
        "append_sequence": append_sequence,
        "producer": "loopx.todo",
        "privacy": "public_safe",
        "projection_version": "event_sourced_state_contract_v0",
        "refs": {"todo_id": todo_id},
        "payload": payload,
    }


def test_replay_order_and_idempotency() -> None:
    store = EventStore()
    todo_a = event(
        "evt-a",
        "todo_added",
        1,
        "todo_a",
        {
            "role": "agent",
            "priority": "P0",
            "title": "Define event source contract",
            "planner_order": 1,
        },
    )
    todo_b = event(
        "evt-b",
        "todo_added",
        2,
        "todo_b",
        {
            "role": "agent",
            "priority": "P0",
            "title": "Implement event store",
            "planner_order": 2,
        },
    )
    store.append(todo_b)
    store.append(todo_a)
    store.append(todo_a)
    store.append(
        event(
            "evt-claim-a",
            "todo_claimed",
            3,
            "todo_a",
            {"claimed_by": "codex-product-capability"},
        )
    )

    projection = store.replay_todos()
    assert [todo["todo_id"] for todo in projection["open_todos"]] == [
        "todo_a",
        "todo_b",
    ], projection
    assert projection["source_event_count"] == 3, projection
    assert projection["last_event_id"] == "evt-claim-a", projection
    assert projection["last_append_sequence"] == 3, projection
    assert projection["projection_version"] == "event_sourced_state_contract_v0"

    conflicting = dict(todo_a)
    conflicting["payload"] = dict(todo_a["payload"])
    conflicting["payload"]["title"] = "Rewrite prior event"
    try:
        store.append(conflicting)
    except ValueError as exc:
        assert "conflicting event_id" in str(exc), exc
    else:
        raise AssertionError("conflicting duplicate event id was accepted")

    mutation = event("evt-mutate", "todo_updated", 4, "todo_a", {"title": "mutate"})
    mutation["refs"]["mutates_prior_event_id"] = "evt-a"
    try:
        store.append(mutation)
    except ValueError as exc:
        assert "must not mutate prior events" in str(exc), exc
    else:
        raise AssertionError("prior-event mutation was accepted")


def main() -> int:
    test_contract_text()
    test_docs_are_linked()
    test_replay_order_and_idempotency()
    print("event-sourced-state-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
