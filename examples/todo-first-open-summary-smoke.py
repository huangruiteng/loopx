#!/usr/bin/env python3
"""Smoke-test first-open todo summaries when visible todo items are truncated."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from goal_harness.review_packet import build_review_packet  # noqa: E402
from goal_harness.status import (  # noqa: E402
    compact_todo_group,
    parse_active_state_todos,
    project_asset_todo_summary,
)


GOAL_ID = "todo-first-open-summary-goal"
OPEN_TODO = (
    "[P1] Keep heartbeat prompt and agent-to-CLI interaction lean as an ongoing "
    "interface-budget task."
)
SECOND_OPEN_TODO = "[P1] Add stale latest-run detection before workers trust run projections."
THIRD_OPEN_TODO = "[P1] Reconcile outcome-floor safe-bypass incident gaps into smokes."
APPENDED_P0_TODO = (
    "[P0] Select the next material-ready benchmark case after compact review."
)
BLOCKED_CORE_TODO = (
    "[P0] Repair the primary benchmark mode before selecting another case."
)
FALLBACK_TODO = (
    "[P1] Continue one safe benchmark attribution cleanup while the primary mode is blocked."
)


def build_truncated_todo_group() -> dict:
    items = [
        {"index": index, "done": True, "text": f"Completed item {index}"}
        for index in range(1, 14)
    ]
    items.append({"index": 14, "done": False, "text": OPEN_TODO})
    items.append({"index": 15, "done": False, "text": SECOND_OPEN_TODO})
    items.append({"index": 16, "done": False, "text": THIRD_OPEN_TODO})
    items.append({"index": 17, "done": False, "text": APPENDED_P0_TODO})
    group = compact_todo_group(items, source_section="Agent Todo", role="agent")
    assert group is not None, group
    assert group["schema_version"] == "todo_summary_v0", group
    assert len(group["items"]) == 12, group
    assert [item["index"] for item in group["items"][:3]] == [14, 15, 16], group
    assert all(not item["done"] for item in group["items"][:4]), group
    assert all(item["done"] for item in group["items"][4:]), group
    assert group["open_count"] == 4, group
    assert group["first_open_items"][0]["index"] == 17, group
    assert group["first_open_items"][0]["text"] == APPENDED_P0_TODO, group
    assert group["first_open_items"][0]["status"] == "open", group
    assert group["first_open_items"][0]["priority"] == "P0", group
    assert group["first_open_items"][0]["role"] == "agent", group
    assert group["first_open_items"][0]["archive_state"] == "active", group
    assert group["first_open_items"][0]["source_section"] == "Agent Todo", group
    assert str(group["first_open_items"][0]["todo_id"]).startswith("todo_"), group
    assert [item["index"] for item in group["first_open_items"]] == [17, 14, 15], group
    return group


def parse_multiline_deep_open_todo() -> dict:
    done_lines = "\n".join(
        f"- [x] Completed item {index}"
        for index in range(1, 14)
    )
    state_text = (
        "## Agent Todo\n\n"
        f"{done_lines}\n"
        "- [ ] [P1] Keep heartbeat prompt and agent-to-CLI interaction lean as an\n"
        "  ongoing interface-budget task.\n"
        f"- [ ] {SECOND_OPEN_TODO}\n"
        f"- [ ] {THIRD_OPEN_TODO}\n"
        f"- [ ] {APPENDED_P0_TODO}\n"
    )
    group = parse_active_state_todos(state_text)["agent_todos"]
    assert len(group["items"]) == 12, group
    assert [item["index"] for item in group["items"][:3]] == [14, 15, 16], group
    assert all(not item["done"] for item in group["items"][:4]), group
    assert all(item["done"] for item in group["items"][4:]), group
    assert group["open_count"] == 4, group
    assert group["first_open_items"][0]["index"] == 17, group
    assert group["first_open_items"][0]["text"] == APPENDED_P0_TODO, group
    assert group["first_open_items"][0]["title"] == "Select the next material-ready benchmark case after compact review.", group
    assert [item["index"] for item in group["first_open_items"]] == [17, 14, 15], group
    return group


def build_blocked_priority_fallback_status_payload() -> dict:
    agent_todos = compact_todo_group(
        [
            {
                "index": 1,
                "done": False,
                "text": BLOCKED_CORE_TODO,
                "status": "blocked",
                "task_class": "advancement_task",
                "action_kind": "repair_primary_mode",
            },
            {
                "index": 2,
                "done": False,
                "text": FALLBACK_TODO,
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "safe_fallback_cleanup",
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None, agent_todos
    assert agent_todos["first_open_items"][0]["status"] == "blocked", agent_todos
    assert agent_todos["first_executable_items"][0]["text"] == FALLBACK_TODO, agent_todos
    asset_summary = project_asset_todo_summary(agent_todos)
    assert asset_summary is not None, agent_todos
    attention_item = {
        "goal_id": GOAL_ID,
        "status": "eligible_with_blocked_priority_fallback",
        "waiting_on": "codex",
        "severity": "action",
        "source": "latest_run",
        "recommended_action": "Use the first executable fallback only after surfacing the blocked core todo.",
        "quota": {
            "compute": 1.0,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "owner": "codex",
            "next_action": "Use the first executable fallback only after surfacing the blocked core todo.",
            "stop_condition": "stop on fixture boundary",
            "agent_todos": asset_summary,
            "quota": {
                "compute": 1.0,
                "slot_minutes": 1,
                "allowed_slots": 1440,
                "spent_slots": 0,
                "state": "eligible",
                "reason": "eligible fixture",
            },
        },
        "agent_todos": agent_todos,
    }
    return {
        "ok": True,
        "attention_queue": {"items": [attention_item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }


def assert_blocked_priority_fallback_visible() -> None:
    decision = build_quota_should_run(
        build_blocked_priority_fallback_status_payload(),
        goal_id=GOAL_ID,
    )
    assert decision["should_run"] is True, decision
    fallback = decision["blocked_priority_fallback"]
    assert fallback["notify_user"] is True, fallback
    assert fallback["requires_user_action"] is False, fallback
    assert fallback["blocked_items"][0]["text"] == BLOCKED_CORE_TODO, fallback
    assert fallback["selected_executable"]["text"] == FALLBACK_TODO, fallback
    assert decision["heartbeat_recommendation"]["notify"] == "NOTIFY", decision
    user_channel = decision["interaction_contract"]["user_channel"]
    assert user_channel["action_required"] is False, user_channel
    assert user_channel["notify"] == "NOTIFY", user_channel
    markdown = render_quota_should_run_markdown(decision)
    assert "blocked_priority_fallback: notify_user=True" in markdown, markdown
    assert f"blocked_priority_item[1]: {BLOCKED_CORE_TODO}" in markdown, markdown
    assert f"blocked_priority_selected: {FALLBACK_TODO}" in markdown, markdown


def main() -> int:
    agent_todos = build_truncated_todo_group()
    parsed_agent_todos = parse_multiline_deep_open_todo()
    assert parsed_agent_todos["first_open_items"] == agent_todos["first_open_items"], parsed_agent_todos
    asset_summary = project_asset_todo_summary(agent_todos)
    assert asset_summary is not None, agent_todos
    assert asset_summary["open"] == 4, asset_summary
    assert asset_summary["next"] == APPENDED_P0_TODO, asset_summary
    assert asset_summary["next_index"] == 17, asset_summary
    assert [item["index"] for item in asset_summary["items"]] == [17, 14, 15, 16], asset_summary
    assert asset_summary["items"][0]["priority"] == "P0", asset_summary
    assert asset_summary["items"][0]["status"] == "open", asset_summary
    assert asset_summary["items"][0]["todo_id"] == agent_todos["first_open_items"][0]["todo_id"], asset_summary

    attention_item = {
        "goal_id": GOAL_ID,
        "status": "eligible_with_deep_agent_todo",
        "waiting_on": "codex",
        "severity": "action",
        "source": "latest_run",
        "recommended_action": "Use the first open agent todo as the next bounded step.",
        "quota": {
            "compute": 1.0,
            "slot_minutes": 1,
            "allowed_slots": 1440,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "owner": "codex",
            "next_action": "Use the first open agent todo as the next bounded step.",
            "stop_condition": "stop on fixture boundary",
            "agent_todos": asset_summary,
            "quota": {
                "compute": 1.0,
                "slot_minutes": 1,
                "allowed_slots": 1440,
                "spent_slots": 0,
                "state": "eligible",
                "reason": "eligible fixture",
            },
        },
        "agent_todos": agent_todos,
    }
    status_payload = {
        "ok": True,
        "attention_queue": {"items": [attention_item]},
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }
    decision = build_quota_should_run(status_payload, goal_id=GOAL_ID)
    assert decision["should_run"] is True, decision
    agent_summary = decision["agent_todo_summary"]
    assert agent_summary["open_count"] == 4, decision
    assert agent_summary["first_open_items"][0]["index"] == 17, decision
    assert agent_summary["first_open_items"][0]["text"] == APPENDED_P0_TODO, decision
    assert agent_summary["first_open_items"][0]["priority"] == "P0", decision
    assert agent_summary["first_open_items"][0]["status"] == "open", decision
    assert agent_summary["first_open_items"][0]["todo_id"] == agent_todos["first_open_items"][0]["todo_id"], decision
    assert [item["index"] for item in agent_summary["first_open_items"]] == [17, 14, 15], decision
    markdown = render_quota_should_run_markdown(decision)
    assert f"agent_todo_next[17]: {APPENDED_P0_TODO}" in markdown, markdown
    assert f"agent_todo_next[14]: {OPEN_TODO}" in markdown, markdown
    assert f"agent_todo_next[15]: {SECOND_OPEN_TODO}" in markdown, markdown
    packet = build_review_packet(status_payload, goal_id=GOAL_ID, action_kind="codex")
    assert packet["agent_todo_items"] == [
        APPENDED_P0_TODO,
        OPEN_TODO,
        SECOND_OPEN_TODO,
    ], packet
    assert f"Agent 待办：{APPENDED_P0_TODO}" in packet["project_agent_handoff"], packet
    assert f"Agent 待办候选 2：{OPEN_TODO}" in packet["project_agent_handoff"], packet
    assert_blocked_priority_fallback_visible()
    print("todo-first-open-summary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
