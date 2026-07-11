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
    TODO_UPDATED,
    make_state_event,
)
from loopx.control_plane.todos.claim_visibility import (  # noqa: E402
    build_agent_claim_scoped_open_items,
)
from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import active_state_todo_fields, project_asset_todo_summary  # noqa: E402


GOAL_ID = "event-sourced-downstream-read-fixture"
EVENT_TODO_ID = "todo_event_downstream_read"
EVENT_TODO = "Use event projection for downstream read surfaces"
EVENT_MONITOR_ID = "todo_event_monitor_readonly"
EVENT_MONITOR = "Poll event-projected monitor metadata without writeback"
MARKDOWN_TODO_ID = "todo_markdown_fallback"
MARKDOWN_TODO = "Fallback Markdown todo for corrupted event logs"
LEGACY_REVIEW_ID = "todo_event_legacy_review"
LEGACY_FALLBACK_ID = "todo_event_legacy_fallback"
AUTHOR_AGENT = "codex-main-control"
REVIEWER_AGENT = "codex-product-capability"


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


def append_event_todo_and_due_monitor(event_log: Path) -> None:
    append_event_todos(event_log)
    store = AppendOnlyStateEventStore(event_log)
    store.append(
        make_state_event(
            event_id="evt-add-readonly-monitor",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": EVENT_MONITOR_ID},
            payload={
                "role": "agent",
                "priority": "P0",
                "title": EVENT_MONITOR,
                "planner_order": 2,
                "task_class": "continuous_monitor",
                "action_kind": "poll",
                "target_key": "event-projected-watch",
                "cadence": "15m",
                "next_due_at": "2026-01-01T00:00:00+00:00",
            },
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-06-27T02:00:03Z",
        )
    )


def append_legacy_review_events(event_log: Path, *, policy: str) -> None:
    store = AppendOnlyStateEventStore(event_log)
    added_payload = {
        "role": "agent",
        "priority": "P0",
        "title": f"Legacy {policy} event must remain blocked",
        "planner_order": 1,
        "task_class": "advancement_task",
        "action_kind": "review",
    }
    if policy == "review_handoff":
        added_payload["continuation_policy"] = policy
    else:
        added_payload["continuation_policy"] = "independent_handoff"
    store.append(
        make_state_event(
            event_id=f"evt-add-legacy-{policy}",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": LEGACY_REVIEW_ID},
            payload=added_payload,
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-07-11T00:00:01Z",
        )
    )
    if policy == "primary_review":
        store.append(
            make_state_event(
                event_id=f"evt-update-legacy-{policy}",
                goal_id=GOAL_ID,
                event_type=TODO_UPDATED,
                refs={"todo_id": LEGACY_REVIEW_ID},
                payload={"continuation_policy": policy},
                producer="event-sourced-downstream-read-path-smoke",
                recorded_at="2026-07-11T00:00:02Z",
            )
        )
    store.append(
        make_state_event(
            event_id=f"evt-update-incidental-{policy}",
            goal_id=GOAL_ID,
            event_type=TODO_UPDATED,
            refs={"todo_id": LEGACY_REVIEW_ID},
            payload={"title": f"Legacy {policy} survives incidental update"},
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-07-11T00:00:03Z",
        )
    )
    store.append(
        make_state_event(
            event_id=f"evt-add-fallback-{policy}",
            goal_id=GOAL_ID,
            event_type=TODO_ADDED,
            refs={"todo_id": LEGACY_FALLBACK_ID},
            payload={
                "role": "agent",
                "priority": "P1",
                "title": "Repair the legacy event projection",
                "planner_order": 2,
                "task_class": "advancement_task",
                "action_kind": "repair",
            },
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-07-11T00:00:04Z",
        )
    )
    store.append(
        make_state_event(
            event_id=f"evt-claim-fallback-{policy}",
            goal_id=GOAL_ID,
            event_type=TODO_CLAIMED,
            refs={"todo_id": LEGACY_FALLBACK_ID},
            payload={"claimed_by": AUTHOR_AGENT},
            producer="event-sourced-downstream-read-path-smoke",
            recorded_at="2026-07-11T00:00:05Z",
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
                        "agent_model": "peer_v1",
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


def agent_todo_by_id(fields: dict, todo_id: str) -> dict:
    agent_todos = fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else {}
    for item in agent_todos.get("items") or []:
        if isinstance(item, dict) and item.get("todo_id") == todo_id:
            return item
    raise AssertionError(f"missing todo {todo_id}: {fields}")


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


def test_event_projected_due_monitor_is_read_only_for_writeback() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-event-readonly-monitor-") as tmp:
        project = Path(tmp)
        state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
        write_active_state(state_path)
        append_event_todo_and_due_monitor(state_path.with_name("events.jsonl"))

        goal = {
            "id": GOAL_ID,
            "repo": str(project),
            "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
        }
        fields = active_state_todo_fields(goal)
        assert agent_todo_ids(fields) == [EVENT_TODO_ID, EVENT_MONITOR_ID], fields
        monitor = agent_todo_by_id(fields, EVENT_MONITOR_ID)
        assert monitor["target_key"] == "event-projected-watch", monitor
        assert monitor["cadence"] == "15m", monitor
        assert monitor["next_due_at"] == "2026-01-01T00:00:00+00:00", monitor
        monitor_writeback = fields["agent_todos"]["monitor_writeback"]
        assert monitor_writeback == {
            "schema_version": "monitor_writeback_contract_v0",
            "supported": False,
            "source": "event_projection_read_model",
        }, fields

        status = status_payload_from_fields(project, fields)
        guard = build_quota_should_run(
            status,
            goal_id=GOAL_ID,
            agent_id="codex-product-capability",
        )
        assert guard["decision"] == "run", guard
        assert guard["agent_lane_next_action"]["todo_id"] == EVENT_TODO_ID, guard
        lane = guard["work_lane_contract"]
        assert lane["lane"] == "advancement_task", lane
        assert "open_agent_todo" in lane["reason_codes"], lane
        assert "external_monitor_context" in lane["reason_codes"], lane
        assert "due_monitor_context" not in lane["reason_codes"], lane
        assert lane.get("obligation") != "attempt_due_monitor", lane
        summary = guard["agent_todo_summary"]
        assert summary["monitor_due_count"] == 0, summary
        assert summary["monitor_open_items"][0]["todo_id"] == EVENT_MONITOR_ID, summary
        assert summary["monitor_writeback"] == {
            "supported": False,
            "source": "event_projection_read_model",
        }, summary


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


def test_legacy_event_review_handoffs_fail_closed_until_explicit_repair() -> None:
    for policy in ("review_handoff", "primary_review"):
        with tempfile.TemporaryDirectory(prefix=f"loopx-event-legacy-{policy}-") as tmp:
            project = Path(tmp)
            state_path = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
            write_active_state(state_path)
            event_log = state_path.with_name("events.jsonl")
            append_legacy_review_events(event_log, policy=policy)
            goal = {
                "id": GOAL_ID,
                "repo": str(project),
                "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
            }

            fields = active_state_todo_fields(goal)
            legacy = agent_todo_by_id(fields, LEGACY_REVIEW_ID)
            assert legacy["removed_continuation_policy"] == policy, fields
            assert legacy.get("continuation_policy") is None, fields
            items = fields["agent_todos"]["items"]
            author_selectable, author_scope = build_agent_claim_scoped_open_items(
                items,
                agent_identity={"agent_id": AUTHOR_AGENT, "agent_model": "peer_v1"},
                diagnostic_item_limit=3,
            )
            assert [item["todo_id"] for item in author_selectable] == [LEGACY_FALLBACK_ID]
            assert author_scope["removed_continuation_blocked_count"] == 1, author_scope
            reviewer_selectable, reviewer_scope = build_agent_claim_scoped_open_items(
                items,
                agent_identity={"agent_id": REVIEWER_AGENT, "agent_model": "peer_v1"},
                diagnostic_item_limit=3,
            )
            assert reviewer_selectable == [], reviewer_selectable
            assert reviewer_scope["removed_continuation_blocked_count"] == 1, reviewer_scope

            status = status_payload_from_fields(project, fields)
            author_guard = build_quota_should_run(status, goal_id=GOAL_ID, agent_id=AUTHOR_AGENT)
            assert author_guard["agent_lane_next_action"]["todo_id"] == LEGACY_FALLBACK_ID, author_guard
            assert LEGACY_REVIEW_ID not in author_guard["recommended_action"], author_guard

            AppendOnlyStateEventStore(event_log).append(
                make_state_event(
                    event_id=f"evt-repair-legacy-{policy}",
                    goal_id=GOAL_ID,
                    event_type=TODO_UPDATED,
                    refs={"todo_id": LEGACY_REVIEW_ID},
                    payload={
                        "continuation_policy": "independent_handoff",
                        "excluded_agents": [AUTHOR_AGENT],
                    },
                    producer="event-sourced-downstream-read-path-smoke",
                    recorded_at="2026-07-11T00:00:06Z",
                )
            )
            repaired_fields = active_state_todo_fields(goal)
            repaired = agent_todo_by_id(repaired_fields, LEGACY_REVIEW_ID)
            assert repaired.get("removed_continuation_policy") is None, repaired
            assert repaired["continuation_policy"] == "independent_handoff", repaired
            assert repaired["excluded_agents"] == [AUTHOR_AGENT], repaired
            reviewer_guard = build_quota_should_run(
                status_payload_from_fields(project, repaired_fields),
                goal_id=GOAL_ID,
                agent_id=REVIEWER_AGENT,
            )
            assert reviewer_guard["agent_lane_next_action"]["todo_id"] == LEGACY_REVIEW_ID, reviewer_guard


def main() -> int:
    test_event_projection_feeds_quota_and_review_packet()
    test_event_projected_due_monitor_is_read_only_for_writeback()
    test_corrupted_event_log_falls_back_to_markdown()
    test_legacy_event_review_handoffs_fail_closed_until_explicit_repair()
    print("event-sourced-downstream-read-path-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
