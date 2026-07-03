#!/usr/bin/env python3
"""Validate event-projected todos flow into quota and review-packet reads."""

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
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import active_state_todo_fields, project_asset_todo_summary  # noqa: E402


GOAL_ID = "event-sourced-downstream-read-fixture"
EVENT_TODO_ID = "todo_event_downstream_read"
EVENT_TODO = "Use event projection for downstream read surfaces"
MARKDOWN_TODO_ID = "todo_markdown_fallback"
MARKDOWN_TODO = "Fallback Markdown todo for corrupted event logs"


def write_active_state(state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "\n".join(
            [
                "# Event Read Fixture",
                "",
                "## Next Action",
                "",
                "- Keep downstream reads public-safe.",
                "",
                "## Agent Todo",
                "",
                f"- [ ] [P2] {MARKDOWN_TODO}.",
                f"  <!-- loopx:todo todo_id={MARKDOWN_TODO_ID} status=open task_class=advancement_task action_kind=markdown_fallback -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


def append_event_todos(event_log: Path) -> None:
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        make_state_event(
            event_id="evt-add-downstream-read",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": EVENT_TODO_ID},
            payload={
                "role": "agent",
                "priority": "P0",
                "title": EVENT_TODO,
                "planner_order": 1,
                "task_class": "advancement_task",
                "action_kind": "event_projection_read_path",
            },
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-06-27T02:00:01Z",
        )
    )
    store.append(
        make_state_event(
            event_id="evt-claim-downstream-read",
            goal_id=GOAL_ID,
            event_type=TODO_CLAIMED,
            refs={"todo_id": EVENT_TODO_ID},
            payload={"claimed_by": "codex-product-capability"},
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-06-27T02:00:02Z",
        )
    )


def status_payload_from_fields(project: Path, fields: dict) -> dict:
    agent_todos = fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else {}
    asset_agent_todos = project_asset_todo_summary(agent_todos, role="agent")
    item = {
        "goal_id": GOAL_ID,
        "status": "event_projection_downstream_read_fixture",
        "waiting_on": "codex",
        "severity": "action",
        "source": "project_asset",
        "recommended_action": "Advance the event-projected downstream read todo.",
        "quota": {
            "compute": 1.0,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "agent_todos": agent_todos,
        "state_event_projection": fields.get("state_event_projection"),
        "project_asset": {
            "owner": "codex",
            "next_action": "Advance the event-projected downstream read todo.",
            "stop_condition": "stop on fixture boundary",
            "agent_todos": asset_agent_todos,
            "state_event_projection": fields.get("state_event_projection"),
            "quota": {
                "compute": 1.0,
                "slot_minutes": 1,
                "allowed_slots": 1440,
                "spent_slots": 0,
                "state": "eligible",
                "reason": "eligible fixture",
            },
        },
    }
    return {
        "ok": True,
        "attention_queue": {"items": [item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "repo": str(project),
                    "registry_member": True,
                    "status": "active",
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": [
                            "codex-main-control",
                            "codex-product-capability",
                        ],
                    },
                    "latest_runs": [],
                }
            ]
        },
    }


def agent_todo_ids(fields: dict) -> list[str]:
    agent_todos = fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else {}
    return [str(item.get("todo_id") or "") for item in agent_todos.get("items") or []]


def test_event_projection_feeds_quota_and_review_packet() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-downstream-") as tmp:
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
        assert agent_todo_ids(fields) == [EVENT_TODO_ID], fields
        assert MARKDOWN_TODO_ID not in agent_todo_ids(fields), fields

        status = status_payload_from_fields(project, fields)
        guard = build_quota_should_run(
            status,
            goal_id=GOAL_ID,
            agent_id="codex-product-capability",
        )
        assert guard["should_run"] is True, guard
        assert guard["agent_todo_summary"]["first_open_items"][0]["todo_id"] == EVENT_TODO_ID, guard
        assert guard["agent_lane_next_action"]["todo_id"] == EVENT_TODO_ID, guard
        markdown = render_quota_should_run_markdown(guard)
        assert EVENT_TODO in markdown, markdown
        assert MARKDOWN_TODO not in markdown, markdown

        packet = build_review_packet(status, goal_id=GOAL_ID, action_kind="codex")
        assert packet["agent_todo_items"] == [
            f"[P0] {EVENT_TODO} claimed_by=codex-product-capability"
        ], packet
        assert EVENT_TODO in packet["project_agent_handoff"], packet
        assert MARKDOWN_TODO not in packet["project_agent_handoff"], packet


def test_corrupted_event_log_falls_back_to_markdown() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-downstream-fallback-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        write_active_state(state_path)
        state_path.with_name("events.jsonl").write_text("{not json\n", encoding="utf-8")

        goal = {
            "id": GOAL_ID,
            "repo": str(project),
            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        }
        fields = active_state_todo_fields(goal)
        assert fields["state_event_projection_warning"]["fallback"] == "markdown_active_state", fields
        assert agent_todo_ids(fields) == [MARKDOWN_TODO_ID], fields

        status = status_payload_from_fields(project, fields)
        guard = build_quota_should_run(status, goal_id=GOAL_ID, agent_id="codex-product-capability")
        assert guard["agent_todo_summary"]["first_open_items"][0]["todo_id"] == MARKDOWN_TODO_ID, guard
        packet = build_review_packet(status, goal_id=GOAL_ID, action_kind="codex")
        assert MARKDOWN_TODO in packet["project_agent_handoff"], packet


def main() -> int:
    test_event_projection_feeds_quota_and_review_packet()
    test_corrupted_event_log_falls_back_to_markdown()
    print("event-sourced-downstream-read-path-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
