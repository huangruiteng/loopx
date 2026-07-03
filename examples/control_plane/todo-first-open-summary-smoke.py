#!/usr/bin/env python3
"""Smoke-test first-open todo summaries when visible todo items are truncated."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown  # noqa: E402
from loopx.projections.project_asset import build_project_asset_todo_summary  # noqa: E402
from loopx.review_packet import build_review_packet  # noqa: E402
from loopx.status import (  # noqa: E402
    MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    MAX_PROJECT_ASSET_TODO_ITEMS,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
    TODO_PROJECTION_VIEW_SCHEMA_VERSION,
    compact_todo_item,
    compact_todo_group,
    open_todo_items,
    parse_active_state_todos,
    project_asset_todo_summary,
    todo_item_is_actionable_open,
    todo_item_task_class,
    todo_lane_items,
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
FRONTSTAGE_CLAIMED_TODO = (
    "[P1] Frontstage dashboard route MVP: render goal_channel_projection_v0 in apps/dashboard."
)
FRONTSTAGE_MONITOR_TODO = (
    "[P2] Repository quality monitor: watch README and dashboard demo freshness."
)


def direct_project_asset_todo_summary(todos: dict, *, role: str | None = None) -> dict | None:
    return build_project_asset_todo_summary(
        todos,
        role=role,
        item_limit=MAX_PROJECT_ASSET_TODO_ITEMS,
        deferred_item_limit=MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
        advancement_task_class=TODO_TASK_CLASS_ADVANCEMENT,
        open_todo_items=open_todo_items,
        compact_todo_item=compact_todo_item,
        todo_lane_items=todo_lane_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        todo_item_task_class=todo_item_task_class,
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
    assert [item["index"] for item in group["items"][:3]] == [17, 14, 15], group
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
    assert [item["index"] for item in group["backlog_items"]] == [17, 14, 15, 16], group
    assert [item["index"] for item in group["executable_backlog_items"]] == [17, 14, 15, 16], group
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
    assert [item["index"] for item in group["items"][:3]] == [17, 14, 15], group
    assert all(not item["done"] for item in group["items"][:4]), group
    assert all(item["done"] for item in group["items"][4:]), group
    assert group["open_count"] == 4, group
    assert group["first_open_items"][0]["index"] == 17, group
    assert group["first_open_items"][0]["text"] == APPENDED_P0_TODO, group
    assert group["first_open_items"][0]["title"] == "Select the next material-ready benchmark case after compact review.", group
    assert [item["index"] for item in group["first_open_items"]] == [17, 14, 15], group
    assert [item["index"] for item in group["backlog_items"]] == [17, 14, 15, 16], group
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
    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    direct_summary = direct_project_asset_todo_summary(agent_todos, role="agent")
    assert direct_summary == asset_summary, (direct_summary, asset_summary)
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
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
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
        agent_id="codex-main-control",
    )
    assert decision["should_run"] is True, decision
    fallback = decision["blocked_priority_fallback"]
    assert fallback["notify_user"] is False, fallback
    assert fallback["requires_user_action"] is False, fallback
    assert fallback["blocked_items"][0]["text"] == BLOCKED_CORE_TODO, fallback
    assert fallback["selected_executable"]["text"] == FALLBACK_TODO, fallback
    assert decision["heartbeat_recommendation"]["notify"] == "DONT_NOTIFY", decision
    user_channel = decision["interaction_contract"]["user_channel"]
    assert user_channel["action_required"] is False, user_channel
    assert user_channel["notify"] == "DONT_NOTIFY", user_channel
    markdown = render_quota_should_run_markdown(decision)
    assert "blocked_priority_fallback: notify_user=False" in markdown, markdown
    assert f"blocked_priority_item[1]: {BLOCKED_CORE_TODO}" in markdown, markdown
    assert f"blocked_priority_selected: {FALLBACK_TODO}" in markdown, markdown


def assert_claimed_frontstage_lanes_visible() -> None:
    many_unclaimed = [
        {
            "index": index,
            "done": False,
            "text": f"[P1] Unclaimed priority backlog item {index}.",
            "task_class": "advancement_task",
        }
        for index in range(1, 14)
    ]
    agent_todos = compact_todo_group(
        [
            *many_unclaimed,
            {
                "index": 40,
                "done": False,
                "text": FRONTSTAGE_CLAIMED_TODO,
                "task_class": "advancement_task",
                "action_kind": "frontstage_dashboard_route_mvp",
                "claimed_by": "codex-side-bypass",
            },
            {
                "index": 41,
                "done": False,
                "text": FRONTSTAGE_MONITOR_TODO,
                "task_class": "continuous_monitor",
                "action_kind": "repository_quality_monitor",
                "claimed_by": "codex-side-bypass",
            },
        ],
        source_section="Agent Todo",
        role="agent",
    )
    assert agent_todos is not None, agent_todos
    assert all(item["index"] != 40 for item in agent_todos["first_open_items"]), agent_todos
    assert all(item["index"] != 40 for item in agent_todos["backlog_items"]), agent_todos
    assert [item["index"] for item in agent_todos["unclaimed_priority_open_items"]] == list(range(1, 9)), agent_todos
    assert [item["index"] for item in agent_todos["claimed_open_items"]] == [40, 41], agent_todos
    assert [item["index"] for item in agent_todos["claimed_advancement_open_items"]] == [40], agent_todos
    assert [item["index"] for item in agent_todos["claimed_monitor_open_items"]] == [41], agent_todos
    assert agent_todos["claimed_advancement_open_count"] == 1, agent_todos
    assert agent_todos["claimed_monitor_open_count"] == 1, agent_todos

    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    assert asset_summary["projection_view"]["view"] == "project_asset_overview", asset_summary
    assert asset_summary["projection_view"]["truth"] == "derived", asset_summary
    assert asset_summary["detail_pointer"]["full_list_included"] is False, asset_summary
    assert "unclaimed_priority_open_items" not in asset_summary, asset_summary
    assert "claimed_open_items" not in asset_summary, asset_summary
    assert "claimed_advancement_open_items" not in asset_summary, asset_summary
    assert "claimed_monitor_open_items" not in asset_summary, asset_summary

    attention_item = {
        "goal_id": GOAL_ID,
        "status": "eligible_with_claimed_frontstage_backlog",
        "waiting_on": "codex",
        "severity": "action",
        "source": "latest_run",
        "recommended_action": "Use priority candidates for scheduling but keep claimed frontstage work visible.",
        "coordination": {
            "primary_agent": "codex-main-control",
            "registered_agents": ["codex-main-control", "codex-side-bypass"],
        },
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
            "next_action": "Use priority candidates for scheduling but keep claimed frontstage work visible.",
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
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }
    decision = build_quota_should_run(status_payload, goal_id=GOAL_ID, agent_id="codex-side-bypass")
    summary = decision["agent_todo_summary"]
    assert [item["index"] for item in summary["unclaimed_priority_open_items"]] == list(range(1, 9)), summary
    assert [item["index"] for item in summary["claimed_open_items"]] == [40, 41], summary
    assert [item["index"] for item in summary["current_agent_claimed_open_items"]] == [40, 41], summary
    assert [item["index"] for item in summary["current_agent_claimed_advancement_items"]] == [40], summary
    assert [item["index"] for item in summary["current_agent_claimed_monitor_items"]] == [41], summary
    assert summary["current_agent_claimed_advancement_count"] == 1, summary
    assert summary["current_agent_claimed_monitor_count"] == 1, summary
    assert summary["claim_scope"]["current_agent_claimed_open_count"] == 2, summary
    assert decision["agent_identity"]["agent_id"] == "codex-side-bypass", decision


def assert_claimed_markdown_todos_survive_visibility_lanes() -> None:
    unclaimed_lines = "\n".join(
        f"- [ ] [P1] Unclaimed priority backlog item {index}."
        for index in range(1, 14)
    )
    state_text = (
        "## Agent Todo\n\n"
        f"{unclaimed_lines}\n"
        f" - [ ] {FRONTSTAGE_CLAIMED_TODO}\n"
        "   <!-- loopx:todo todo_id=todo_claimed_markdown status=open "
        "task_class=advancement_task action_kind=frontstage_dashboard_route_mvp "
        "claimed_by=codex-side-bypass -->\n"
        f"- [ ] {FRONTSTAGE_MONITOR_TODO}\n"
        "  <!-- loopx:todo todo_id=todo_claimed_monitor status=open "
        "task_class=continuous_monitor action_kind=repository_quality_monitor "
        "claimed_by=codex-side-bypass -->\n"
    )
    agent_todos = parse_active_state_todos(state_text)["agent_todos"]
    assert all(
        item["todo_id"] != "todo_claimed_markdown"
        for item in agent_todos["first_open_items"]
    ), agent_todos
    assert all(
        item["todo_id"] != "todo_claimed_markdown"
        for item in agent_todos["backlog_items"]
    ), agent_todos
    assert [item["todo_id"] for item in agent_todos["claimed_open_items"]] == [
        "todo_claimed_markdown",
        "todo_claimed_monitor",
    ], agent_todos
    assert [item["todo_id"] for item in agent_todos["claimed_advancement_open_items"]] == [
        "todo_claimed_markdown",
    ], agent_todos
    assert [item["todo_id"] for item in agent_todos["claimed_monitor_open_items"]] == [
        "todo_claimed_monitor",
    ], agent_todos

    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    status_payload = {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "eligible_with_claimed_markdown_backlog",
                    "waiting_on": "codex",
                    "severity": "action",
                    "source": "latest_run",
                    "recommended_action": "Keep claimed markdown todos visible outside scheduler top-N.",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
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
                        "next_action": "Keep claimed markdown todos visible outside scheduler top-N.",
                        "stop_condition": "stop on fixture boundary",
                        "agent_todos": asset_summary,
                    },
                    "agent_todos": agent_todos,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }
    decision = build_quota_should_run(
        status_payload,
        goal_id=GOAL_ID,
        agent_id="codex-side-bypass",
    )
    summary = decision["agent_todo_summary"]
    assert [item["todo_id"] for item in summary["current_agent_claimed_open_items"]] == [
        "todo_claimed_markdown",
        "todo_claimed_monitor",
    ], summary
    assert [item["todo_id"] for item in summary["current_agent_claimed_advancement_items"]] == [
        "todo_claimed_markdown",
    ], summary
    assert [item["todo_id"] for item in summary["current_agent_claimed_monitor_items"]] == [
        "todo_claimed_monitor",
    ], summary
    assert summary["current_agent_claimed_advancement_count"] == 1, summary
    assert summary["current_agent_claimed_monitor_count"] == 1, summary


def assert_claimed_advancement_lanes_preserve_claimants() -> None:
    primary_claimed_lines = "\n".join(
        (
            f"- [ ] [P1] Primary claimed advancement item {index}.\n"
            f"  <!-- loopx:todo todo_id=todo_primary_{index} status=open "
            "task_class=advancement_task action_kind=primary_backlog "
            "claimed_by=codex-main-control -->"
        )
        for index in range(1, 21)
    )
    stale_side_lines = "\n".join(
        (
            f"- [ ] [P1] Stale side claimed advancement item {index}.\n"
            f"  <!-- loopx:todo todo_id=todo_side_stale_{index} status=open "
            "task_class=advancement_task action_kind=frontstage_stale_backlog "
            "claimed_by=codex-side-bypass -->"
        )
        for index in range(1, 6)
    )
    state_text = (
        "## Agent Todo\n\n"
        f"{primary_claimed_lines}\n"
        f"{stale_side_lines}\n"
        "- [ ] [P0] Side claimed TUI continuation item.\n"
        "  <!-- loopx:todo todo_id=todo_side_tui status=open "
        "task_class=advancement_task action_kind=codex_cli_tui_continuation "
        "claimed_by=codex-side-bypass -->\n"
    )
    agent_todos = parse_active_state_todos(state_text)["agent_todos"]
    assert agent_todos["claimed_advancement_open_count"] == 26, agent_todos
    assert agent_todos["first_open_items"][0]["todo_id"] == "todo_side_tui", agent_todos
    claimed_advancement_ids = [
        item["todo_id"] for item in agent_todos["claimed_advancement_open_items"]
    ]
    assert "todo_side_tui" in claimed_advancement_ids, agent_todos
    assert "todo_side_stale_5" in claimed_advancement_ids, agent_todos
    assert "todo_primary_20" not in claimed_advancement_ids, agent_todos

    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    status_payload = {
        "ok": True,
        "attention_queue": {
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": "eligible_with_many_claimed_advancement_items",
                    "waiting_on": "codex",
                    "severity": "action",
                    "source": "latest_run",
                    "recommended_action": "Use claimed advancement lanes without losing side agents.",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
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
                        "next_action": "Use claimed advancement lanes without losing side agents.",
                        "stop_condition": "stop on fixture boundary",
                        "agent_todos": asset_summary,
                    },
                    "agent_todos": agent_todos,
                }
            ]
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": "active",
                    "coordination": {
                        "primary_agent": "codex-main-control",
                        "registered_agents": ["codex-main-control", "codex-side-bypass"],
                    },
                    "quota": {"compute": 1.0, "window_hours": 24},
                    "latest_runs": [],
                }
            ]
        },
    }
    primary_decision = build_quota_should_run(
        status_payload,
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    primary_summary = primary_decision["agent_todo_summary"]
    assert primary_summary["first_executable_items"][0]["todo_id"] == "todo_primary_1", primary_summary
    assert primary_summary["claim_scope"]["agent_role"] == "primary-agent", primary_summary
    assert primary_summary["claim_scope"]["other_agent_claimed_items"][0]["todo_id"] == "todo_side_tui", primary_summary
    assert "Primary claimed advancement item 1" in primary_decision["recommended_action"], primary_decision
    assert "state_action_projection_warning" not in primary_decision, primary_decision

    decision = build_quota_should_run(
        status_payload,
        goal_id=GOAL_ID,
        agent_id="codex-side-bypass",
    )
    summary = decision["agent_todo_summary"]
    current_agent_advancement_ids = [
        item["todo_id"] for item in summary["current_agent_claimed_advancement_items"]
    ]
    assert current_agent_advancement_ids[0] == "todo_side_tui", summary
    assert "todo_side_tui" in current_agent_advancement_ids, summary
    assert summary["first_executable_items"][0]["todo_id"] == "todo_side_tui", summary
    assert summary["claim_scope"]["selection_order"] == (
        "current_agent_claimed_then_unclaimed"
    ), summary
    assert summary["claim_scope"]["other_agent_claimed_open_count"] == 11, summary
    assert summary["claim_scope"]["other_agent_claimed_items"][0]["todo_id"] == "todo_primary_1", summary
    assert summary["claim_scope"]["blocked_claimed_items"][0]["todo_id"] == "todo_primary_1", summary
    assert summary["current_agent_claimed_advancement_count"] == 6, summary


def main() -> int:
    agent_todos = build_truncated_todo_group()
    parsed_agent_todos = parse_multiline_deep_open_todo()
    assert parsed_agent_todos["first_open_items"] == agent_todos["first_open_items"], parsed_agent_todos
    asset_summary = project_asset_todo_summary(agent_todos, role="agent")
    assert asset_summary is not None, agent_todos
    assert asset_summary["open"] == 4, asset_summary
    assert asset_summary["next"] == APPENDED_P0_TODO, asset_summary
    assert asset_summary["next_index"] == 17, asset_summary
    assert asset_summary["projection_view"] == {
        "schema_version": TODO_PROJECTION_VIEW_SCHEMA_VERSION,
        "view": "project_asset_overview",
        "truth": "derived",
        "canonical_source": "attention_queue.items[].agent_todos",
        "item_limit": 3,
        "deferred_item_limit": 8,
    }, asset_summary
    assert asset_summary["detail_pointer"] == {
        "schema_version": TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
        "cold_path": "loopx status --format json",
        "active_state_source": "registry goal state_file",
        "full_list_included": False,
    }, asset_summary
    assert [item["index"] for item in asset_summary["items"]] == [17, 14, 15], asset_summary
    assert [item["index"] for item in asset_summary["first_executable_items"]] == [17, 14, 15], asset_summary
    assert "backlog_items" not in asset_summary, asset_summary
    assert "executable_backlog_items" not in asset_summary, asset_summary
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
    assert [item["index"] for item in agent_summary["backlog_items"]] == [17, 14, 15, 16], decision
    assert [item["index"] for item in agent_summary["executable_backlog_items"]] == [17, 14, 15, 16], decision
    markdown = render_quota_should_run_markdown(decision)
    assert f"agent_todo_next[17]: {APPENDED_P0_TODO}" in markdown, markdown
    assert f"agent_todo_next[14]: {OPEN_TODO}" in markdown, markdown
    assert f"agent_todo_next[15]: {SECOND_OPEN_TODO}" in markdown, markdown
    assert f"agent_todo_backlog[16]: {THIRD_OPEN_TODO}" in markdown, markdown
    packet = build_review_packet(status_payload, goal_id=GOAL_ID, action_kind="codex")
    assert packet["agent_todo_items"] == [
        APPENDED_P0_TODO,
        OPEN_TODO,
        SECOND_OPEN_TODO,
    ], packet
    assert f"Agent 待办：{APPENDED_P0_TODO}" in packet["project_agent_handoff"], packet
    assert f"Agent 待办候选 2：{OPEN_TODO}" in packet["project_agent_handoff"], packet
    assert_blocked_priority_fallback_visible()
    assert_claimed_frontstage_lanes_visible()
    assert_claimed_markdown_todos_survive_visibility_lanes()
    assert_claimed_advancement_lanes_preserve_claimants()
    print("todo-first-open-summary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
