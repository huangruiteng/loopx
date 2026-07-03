#!/usr/bin/env python3
"""Validate event replay, compact workbench projection, and canonical edit guards."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.event_sourced_state import (  # noqa: E402
    AppendOnlyStateEventStore,
    REFRESH_RECORDED,
    RUN_RECORDED,
    StateEventError,
    TODO_ADDED,
    TODO_CLAIMED,
    TODO_COMPLETED,
    TODO_UPDATED,
    build_state_projection,
    make_state_event,
    render_active_state_sections,
)
from loopx.status import active_state_todo_fields, parse_active_state_todos  # noqa: E402


GOAL_ID = "event-sourced-replay-compaction-fixture"


def fixture_event(event_id: str, event_type: str, *, refs: dict | None = None, payload: dict | None = None) -> dict:
    return make_state_event(
        event_id=event_id,
        goal_id=GOAL_ID,
        event_type=event_type,
        refs=refs or {},
        payload=payload or {},
        recorded_at=f"2026-06-27T01:00:{len(event_id):02d}Z",
        producer="event-sourced-replay-compaction-smoke",
    )


def append_fixture_events(event_log: Path) -> AppendOnlyStateEventStore:
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        fixture_event(
            "evt-add-plan",
            TODO_ADDED,
            refs={"todo_id": "todo_event_plan"},
            payload={
                "role": "agent",
                "priority": "P0",
                "title": "Plan event replay migration",
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "plan",
            },
        )
    )
    store.append(
        fixture_event(
            "evt-add-render",
            TODO_ADDED,
            refs={"todo_id": "todo_event_render"},
            payload={
                "role": "agent",
                "priority": "P0",
                "title": "Render compact workbench from events",
                "planner_order": 2,
                "task_class": "advancement_task",
                "action_kind": "validate",
            },
        )
    )
    store.append(
        fixture_event(
            "evt-add-gate",
            TODO_ADDED,
            refs={"todo_id": "todo_event_gate"},
            payload={
                "role": "user",
                "priority": "P1",
                "title": "Approve promoting event projection reads",
                "planner_order": 1,
                "task_class": "user_gate",
            },
        )
    )
    store.append(
        fixture_event(
            "evt-claim-render",
            TODO_CLAIMED,
            refs={"todo_id": "todo_event_render"},
            payload={"claimed_by": "codex-product-capability"},
        )
    )
    store.append(
        fixture_event(
            "evt-update-render",
            TODO_UPDATED,
            refs={"todo_id": "todo_event_render"},
            payload={"title": "Render compact Markdown workbench from events"},
        )
    )
    store.append(
        fixture_event(
            "evt-complete-plan",
            TODO_COMPLETED,
            refs={"todo_id": "todo_event_plan"},
            payload={"evidence": "replay smoke"},
        )
    )
    store.append(
        fixture_event(
            "evt-refresh",
            REFRESH_RECORDED,
            payload={"summary": "event projection rendered into Markdown workbench"},
        )
    )
    store.append(
        fixture_event(
            "evt-run",
            RUN_RECORDED,
            payload={"summary": "compact workbench stayed readable after replay"},
        )
    )
    return store


def todo_ids(fields: dict, role: str) -> list[str]:
    return [str(item.get("todo_id") or "") for item in (fields.get(f"{role}_todos") or {}).get("items") or []]


def todo_statuses(fields: dict, role: str) -> dict[str, str]:
    return {
        str(item.get("todo_id") or ""): str(item.get("status") or "")
        for item in (fields.get(f"{role}_todos") or {}).get("items") or []
    }


def test_replay_regenerates_equivalent_projection() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-replay-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        event_log = state_path.with_name("events.jsonl")
        store = append_fixture_events(event_log)

        projection = build_state_projection(store.load(), generated_at="2026-06-27T01:01:00Z")
        replayed = build_state_projection(reversed(store.load()), generated_at="2026-06-27T01:01:00Z")
        assert projection["source_checksum"].startswith("sha256:"), projection
        assert projection["source_checksum"] == replayed["source_checksum"], replayed
        assert projection["last_append_sequence"] == 8, projection
        assert todo_ids(projection, "agent") == ["todo_event_plan", "todo_event_render"], projection
        assert projection["agent_todos"]["items"][0]["status"] == "done", projection
        assert projection["agent_todos"]["items"][1]["claimed_by"] == "codex-product-capability", projection
        assert todo_ids(projection, "user") == ["todo_event_gate"], projection

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(render_active_state_sections(projection), encoding="utf-8")
        parsed_workbench = parse_active_state_todos(state_path.read_text(encoding="utf-8"))
        assert set(todo_ids(parsed_workbench, "agent")) == set(todo_ids(projection, "agent")), parsed_workbench
        assert set(todo_ids(parsed_workbench, "user")) == set(todo_ids(projection, "user")), parsed_workbench
        assert todo_statuses(parsed_workbench, "agent") == todo_statuses(projection, "agent"), parsed_workbench


def test_compact_markdown_cannot_override_canonical_events() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-compact-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        event_log = state_path.with_name("events.jsonl")
        store = append_fixture_events(event_log)
        projection = build_state_projection(store.load(), generated_at="2026-06-27T01:02:00Z")

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            "\n".join(
                [
                    "# Compact Workbench",
                    "",
                    "## Next Action",
                    "",
                    "- Continue from the compact event projection.",
                    "",
                    "## Agent Todo",
                    "",
                    "- [x] [P0] Locally edited workbench item that must not become truth",
                    "  <!-- loopx:todo todo_id=todo_event_render status=done task_class=advancement_task action_kind=manual_edit -->",
                    "",
                    "## Progress Ledger",
                    "",
                    "- compact projection; full lineage stays in events.jsonl",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        markdown_only = parse_active_state_todos(state_path.read_text(encoding="utf-8"))
        assert markdown_only["agent_todos"]["items"][0]["status"] == "done", markdown_only

        goal = {
            "id": GOAL_ID,
            "repo": str(project),
            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        }
        fields = active_state_todo_fields(goal)
        assert fields["state_event_projection"]["source"] == "event_log", fields
        assert fields["state_event_projection"]["source_checksum"] == projection["source_checksum"], fields
        assert set(todo_ids(fields, "agent")) == {"todo_event_plan", "todo_event_render"}, fields
        assert todo_statuses(fields, "agent") == {
            "todo_event_plan": "done",
            "todo_event_render": "open",
        }, fields
        assert todo_ids(fields, "user") == ["todo_event_gate"], fields
        render_item = next(item for item in fields["agent_todos"]["items"] if item["todo_id"] == "todo_event_render")
        assert render_item["todo_id"] == "todo_event_render", fields
        assert render_item["status"] == "open", fields
        assert render_item["claimed_by"] == "codex-product-capability", fields

        try:
            mutation = fixture_event(
                "evt-mutate-prior",
                TODO_UPDATED,
                refs={"todo_id": "todo_event_render", "mutates_prior_event_id": "evt-add-render"},
                payload={"title": "Rewrite prior canonical event"},
            )
            store.append(mutation)
        except StateEventError as exc:
            assert "must not mutate prior events" in str(exc), exc
        else:
            raise AssertionError("mutable canonical event edit was accepted")


def main() -> int:
    test_replay_regenerates_equivalent_projection()
    test_compact_markdown_cannot_override_canonical_events()
    print("event-sourced-replay-compaction-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
