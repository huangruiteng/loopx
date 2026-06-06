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


def build_truncated_todo_group() -> dict:
    items = [
        {"index": index, "done": True, "text": f"Completed item {index}"}
        for index in range(1, 14)
    ]
    items.append({"index": 14, "done": False, "text": OPEN_TODO})
    items.append({"index": 15, "done": False, "text": SECOND_OPEN_TODO})
    items.append({"index": 16, "done": False, "text": THIRD_OPEN_TODO})
    group = compact_todo_group(items, source_section="Agent Todo")
    assert group is not None, group
    assert len(group["items"]) == 12, group
    assert all(item["done"] for item in group["items"]), group
    assert group["open_count"] == 3, group
    assert group["first_open_items"][0]["index"] == 14, group
    assert group["first_open_items"][0]["text"] == OPEN_TODO, group
    assert [item["index"] for item in group["first_open_items"]] == [14, 15, 16], group
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
    )
    group = parse_active_state_todos(state_text)["agent_todos"]
    assert len(group["items"]) == 12, group
    assert group["open_count"] == 3, group
    assert group["first_open_items"][0]["index"] == 14, group
    assert group["first_open_items"][0]["text"] == OPEN_TODO, group
    assert [item["index"] for item in group["first_open_items"]] == [14, 15, 16], group
    return group


def main() -> int:
    agent_todos = build_truncated_todo_group()
    parsed_agent_todos = parse_multiline_deep_open_todo()
    assert parsed_agent_todos["first_open_items"] == agent_todos["first_open_items"], parsed_agent_todos
    asset_summary = project_asset_todo_summary(agent_todos)
    assert asset_summary is not None, agent_todos
    assert asset_summary["open"] == 3, asset_summary
    assert asset_summary["next"] == OPEN_TODO, asset_summary
    assert asset_summary["next_index"] == 14, asset_summary
    assert [item["index"] for item in asset_summary["items"]] == [14, 15, 16], asset_summary

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
    assert agent_summary["open_count"] == 3, decision
    assert agent_summary["first_open_items"][0]["index"] == 14, decision
    assert agent_summary["first_open_items"][0]["text"] == OPEN_TODO, decision
    assert [item["index"] for item in agent_summary["first_open_items"]] == [14, 15, 16], decision
    markdown = render_quota_should_run_markdown(decision)
    assert f"agent_todo_next[14]: {OPEN_TODO}" in markdown, markdown
    assert f"agent_todo_next[15]: {SECOND_OPEN_TODO}" in markdown, markdown
    packet = build_review_packet(status_payload, goal_id=GOAL_ID, action_kind="codex")
    assert packet["agent_todo_items"] == [OPEN_TODO, SECOND_OPEN_TODO, THIRD_OPEN_TODO], packet
    assert f"Agent 待办：{OPEN_TODO}" in packet["project_agent_handoff"], packet
    assert f"Agent 待办候选 2：{SECOND_OPEN_TODO}" in packet["project_agent_handoff"], packet
    print("todo-first-open-summary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
