"""Agent-lane projection fixtures for the status markdown smoke."""

from __future__ import annotations

from loopx.cli_commands.status import attach_agent_lane_next_actions, _review_handoff_agent
from loopx.review_packet import build_review_packet
from loopx.status import project_asset_todo_summary, render_status_markdown


def assert_status_agent_lane_next_action_projection() -> None:
    goal_id = "agent-lane-status-fixture"
    primary_action = "[P0] Continue the primary controller benchmark route."
    stale_run_action = "[P0] Monitor the primary controller route before changing Next Action."
    side_action = (
        "[P0] Codex CLI TUI continuation: prove the visible steering turn "
        "without losing user takeover."
    )
    side_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_side_tui",
        "index": 2,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "action_kind": "codex_cli_tui_continuation",
        "claimed_by": "codex-side-bypass",
        "required_capabilities": ["shell", "filesystem_write"],
        "text": side_action,
    }
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_route",
        "index": 1,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "claimed_by": "codex-main-control",
        "text": primary_action,
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 2,
        "done_count": 0,
        "total_count": 2,
        "first_open_items": [
            primary_todo,
            side_todo,
        ],
        "items": [primary_todo, side_todo],
        "first_executable_items": [side_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
        "agent_profiles": {
            "codex-side-bypass": {
                "schema_version": "agent_profile_v0",
                "agent_id": "codex-side-bypass",
                "role": "side-agent",
                "scope_summary": "productization showcase docs lane",
                "worktree_policy": {
                    "mode": "independent_worktree_required",
                    "requires_independent_worktree": True,
                },
                "review_policy": {
                    "handoff_agent": "codex-main-control",
                    "can_self_merge": "small_validated_docs_or_metadata_only",
                },
            }
        },
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_action,
                    "active_state_next_action": primary_action,
                    "latest_run_recommended_action": stale_run_action,
                    "next_action_projection_warning": {
                        "schema_version": "next_action_projection_warning_v0",
                        "kind": "next_action_projection_mismatch",
                        "severity": "warning",
                        "requires_state_writeback": True,
                        "active_state_next_action": primary_action,
                        "latest_run_recommended_action": stale_run_action,
                    },
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_action,
                        "active_state_next_action": primary_action,
                        "latest_run_recommended_action": stale_run_action,
                        "next_action_projection_warning": {
                            "schema_version": "next_action_projection_warning_v0",
                            "kind": "next_action_projection_mismatch",
                            "severity": "warning",
                            "requires_state_writeback": True,
                            "active_state_next_action": primary_action,
                            "latest_run_recommended_action": stale_run_action,
                        },
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    next_action = item["agent_lane_next_action"]
    assert next_action["schema_version"] == "agent_lane_next_action_v0", next_action
    assert next_action["todo_id"] == "todo_side_tui", next_action
    assert next_action["agent_id"] == "codex-side-bypass", next_action
    assert next_action["preserves_goal_next_action"] is True, next_action
    warning = item["next_action_projection_warning"]
    assert warning["severity"] == "info", warning
    assert warning["requires_state_writeback"] is False, warning
    assert warning["agent_lane_next_action"] == side_action, warning
    assert item["project_asset"]["next_action_projection_warning"] == warning, item
    goal_frontier = item["goal_frontier_projection"]
    assert goal_frontier["deferred_successors"]["ready_count"] == 0, goal_frontier
    assert goal_frontier["acceptance_gaps"] == [], goal_frontier
    assert item["recommended_action"] == primary_action, item
    assert item["project_asset"]["next_action"] == primary_action, item
    member = item["agent_member"]
    assert member["schema_version"] == "agent_member_v0", member
    assert member["agent_id"] == "codex-side-bypass", member
    assert member["role"] == "side-agent", member
    assert member["scope_summary"] == "productization showcase docs lane", member
    assert member["worktree_policy"] == "independent_worktree_required", member
    assert member["requires_independent_worktree"] is True, member
    assert member["current_claims"] == ["todo_side_tui"], member
    assert member["lease_projection"]["source"] == "todo.claimed_by", member
    assert member["lease_projection"]["hard_lease_available"] is False, member
    assert member["handoff_agent"] == "codex-main-control", member
    assert member["role_is_advisory"] is True, member
    assert item["project_asset"]["agent_member"] == member, item
    projection = payload["agent_member_projection"]
    assert projection["schema_version"] == "agent_member_projection_v0", projection
    assert projection["attached_count"] == 1, projection
    assert projection["projection_is_authoritative"] is False, projection
    markdown = render_status_markdown(payload)
    assert "agent_member: agent=codex-side-bypass role=side-agent" in markdown, markdown
    assert "worktree_policy=independent_worktree_required" in markdown, markdown
    assert "claims=todo_side_tui" in markdown, markdown
    assert "current_agent_todo: agent=codex-side-bypass todo_id=todo_side_tui" in markdown, markdown
    assert "source=agent_lane_next_action" in markdown, markdown
    assert "next_action_projection_warning: requires_state_writeback=False severity=info" in markdown, markdown
    assert "goal_frontier_projection: replan_required=False" in markdown, markdown
    assert "deferred_ready=0 acceptance_gaps=0" in markdown, markdown
    assert side_action in markdown, markdown
    assert f"next_agent_todo: {primary_action} claimed_by=codex-main-control scope=goal_all_agents" in markdown, markdown
    assert f"asset_agent_todo: {primary_action} claimed_by=codex-main-control scope=goal_all_agents" in markdown, markdown
    packet = build_review_packet(payload, goal_id=goal_id, action_kind="codex")
    assert packet["agent_member"]["agent_id"] == "codex-side-bypass", packet
    assert "Agent 成员：agent=codex-side-bypass role=side-agent" in packet["project_agent_handoff"], packet
    assert "authority=advisory_projection" in packet["project_agent_handoff"], packet


def assert_status_agent_member_selected_lane_claim_survives_truncated_claim_list() -> None:
    goal_id = "agent-lane-truncated-claims-fixture"
    selected_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_selected_lane",
        "index": 116,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "action_kind": "rapid_self_merge_kernel_iteration",
        "claimed_by": "codex-side-bypass",
        "text": "[P0] Continue the selected side-agent lane.",
    }
    visible_stale_claims = [
        {
            "schema_version": "todo_item_v0",
            "todo_id": f"todo_visible_stale_claim_{offset}",
            "index": 56 + offset,
            "role": "agent",
            "status": "blocked",
            "priority": "P0",
            "task_class": "advancement_task",
            "action_kind": "old_side_lane",
            "claimed_by": "codex-side-bypass",
            "text": "[P0] Old side-agent claim kept in the visible status window.",
        }
        for offset in range(10)
    ]
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_visible",
        "index": 22,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "blocker",
        "claimed_by": "codex-main-control",
        "text": "[P0] Primary visible item.",
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 105,
        "done_count": 0,
        "total_count": 105,
        "items": [primary_todo, *visible_stale_claims, selected_todo],
        "first_open_items": [primary_todo, *visible_stale_claims[:2]],
        "first_executable_items": [selected_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_todo["text"],
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_todo["text"],
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    assert item["agent_lane_next_action"]["todo_id"] == "todo_selected_lane", item
    member = item["agent_member"]
    assert member["current_claims"][0] == "todo_selected_lane", member
    assert "todo_visible_stale_claim_0" in member["current_claims"], member
    markdown = render_status_markdown(payload)
    assert "claims=todo_selected_lane,todo_visible_stale_claim_0" in markdown, markdown


def assert_status_agent_member_handoff_uses_quota_identity() -> None:
    assert (
        _review_handoff_agent(
            coordination={},
            profile={},
            identity={"handoff_agent": "codex-product-capability"},
            role="side-agent",
        )
        == "codex-product-capability"
    )
    assert (
        _review_handoff_agent(
            coordination={"side_agent_handoff_agent": "codex-main-control"},
            profile={},
            identity={"handoff_agent": "codex-product-capability"},
            role="side-agent",
        )
        == "codex-product-capability"
    )


def assert_status_agent_lane_frontier_hint_projection() -> None:
    goal_id = "agent-lane-frontier-status-fixture"
    primary_action = "[P0] Continue the primary controller benchmark route."
    primary_todo = {
        "schema_version": "todo_item_v0",
        "todo_id": "todo_primary_route",
        "index": 1,
        "role": "agent",
        "status": "open",
        "priority": "P0",
        "task_class": "advancement_task",
        "claimed_by": "codex-main-control",
        "text": primary_action,
    }
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "open_count": 1,
        "done_count": 0,
        "total_count": 1,
        "first_open_items": [primary_todo],
        "items": [primary_todo],
    }
    coordination = {
        "primary_agent": "codex-main-control",
        "registered_agents": ["codex-main-control", "codex-side-bypass"],
    }
    payload = {
        "ok": True,
        "registry": "./fixtures/registry.json",
        "runtime_root": "./fixtures/runtime",
        "goal_count": 1,
        "run_count": 1,
        "contract": {"ok": True, "summary": {"errors": 0, "warnings": 0, "checks": 0}},
        "global_registry": {"available": False, "summary": {}},
        "attention_queue": {
            "available": True,
            "item_count": 1,
            "items": [
                {
                    "goal_id": goal_id,
                    "status": "primary_route_active",
                    "waiting_on": "codex",
                    "severity": "action",
                    "recommended_action": primary_action,
                    "source": "registry",
                    "coordination": coordination,
                    "quota": {
                        "state": "eligible",
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                    "agent_todos": agent_todos,
                    "project_asset": {
                        "owner": "codex-main-control",
                        "gate": "none",
                        "stop_condition": "stop on unsafe workspace or user gate",
                        "next_action": primary_action,
                        "agent_todos": project_asset_todo_summary(agent_todos, role="agent"),
                    },
                }
            ],
        },
        "run_history": {
            "goals": [
                {
                    "id": goal_id,
                    "registry_member": True,
                    "status": "primary_route_active",
                    "coordination": coordination,
                    "quota": {
                        "compute": 1.0,
                        "window_hours": 24,
                        "slot_minutes": 1,
                        "allowed_slots": 10,
                    },
                }
            ]
        },
    }
    attach_agent_lane_next_actions(payload, agent_id="codex-side-bypass")
    item = payload["attention_queue"]["items"][0]
    assert "agent_lane_next_action" not in item, item
    frontier = item["agent_scope_frontier"]
    assert frontier["action"] == "agent_scope_wait", frontier
    goal_frontier = item["goal_frontier_projection"]
    assert goal_frontier["remaining_advancement_frontier"] == {
        "current_agent_claimed_advancement_count": 0,
        "unclaimed_advancement_count": 0,
        "other_agent_claimed_advancement_count": 1,
    }, goal_frontier
    assert goal_frontier["deferred_successors"]["ready_count"] == 0, goal_frontier
    assert goal_frontier["acceptance_gaps"] == [], goal_frontier
    hint = item["agent_lane_frontier_hint"]
    assert hint["schema_version"] == "agent_lane_frontier_hint_v0", hint
    assert hint["decision"] == "quiet_noop_blocker", hint
    assert hint["source"] == "agent_scope_frontier", hint
    assert hint["target_todo_id"] == "todo_primary_route", hint
    projection = payload["agent_lane_next_action_projection"]
    assert projection["attached_count"] == 0, projection
    assert projection["frontier_attached_count"] == 1, projection
    assert projection["frontier_hint_attached_count"] == 1, projection
    markdown = render_status_markdown(payload)
    assert "agent_lane_frontier_hint: agent=codex-side-bypass" in markdown, markdown
    assert "decision=quiet_noop_blocker" in markdown, markdown
    assert "target_todo_id=todo_primary_route" in markdown, markdown
    assert "goal_frontier_projection: replan_required=False" in markdown, markdown
    assert "other_agent_advancement=1 deferred_ready=0 acceptance_gaps=0" in markdown, markdown
