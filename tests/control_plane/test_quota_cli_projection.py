from __future__ import annotations

import json

from loopx.control_plane.quota.cli_projection import (
    QUOTA_CLI_AGENT_LANE_NEXT_ACTION_DETAIL_COMMAND,
    QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND,
    QUOTA_CLI_NEXT_ACTION_PROJECTION_DETAIL_COMMAND,
    QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
    QUOTA_CLI_USER_TODO_SUMMARY_DETAIL_COMMAND,
    QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND,
    QUOTA_CLI_VISION_AUDIT_ROOT_REF,
    compact_quota_should_run_cli_payload,
)


def _items(count: int, *, prefix: str) -> list[dict[str, object]]:
    return [
        {
            "schema_version": "todo_item_v0",
            "todo_id": f"{prefix}-{index}",
            "text": f"{prefix} item {index}",
            "task_class": "advancement_task",
        }
        for index in range(count)
    ]


def test_compact_quota_should_run_cli_payload_keeps_decision_lanes_and_counts() -> None:
    backlog = _items(40, prefix="backlog")
    first_executable = _items(4, prefix="execute")
    monitor_due = _items(2, prefix="monitor")
    first_open = [monitor_due[0], monitor_due[1], *_items(4, prefix="open")]
    payload = {
        "interaction_contract": {"mode": "bounded_delivery"},
        "selected_todo": {"todo_id": "execute-0"},
        "scheduler_hint": {"action": "run_now"},
        "agent_todo_summary": {
            "schema_version": "todo_summary_v0",
            "total_count": 50,
            "open_count": 40,
            "done_count": 10,
            "first_open_items": first_open,
            "first_executable_items": first_executable,
            "monitor_due_items": monitor_due,
            "backlog_items": backlog,
            "claimed_open_items": backlog,
            "claim_scope": {
                "schema_version": "agent_claim_scope_v0",
                "current_agent_claimed_open_count": 4,
                "other_agent_claimed_items": backlog,
            },
            "todo_succession_warning": {
                "count": 3,
                "items": backlog,
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(payload)

    assert compact["interaction_contract"] == payload["interaction_contract"]
    assert compact["selected_todo"] == payload["selected_todo"]
    assert compact["scheduler_hint"] == payload["scheduler_hint"]
    summary = compact["agent_todo_summary"]
    assert summary["total_count"] == 50
    assert summary["open_count"] == 40
    assert len(summary["first_open_items"]) == 3
    assert [item["todo_id"] for item in summary["first_open_items"]] == [
        "monitor-1",
        "open-0",
        "open-1",
    ]
    assert len(summary["first_executable_items"]) == 3
    assert len(summary["monitor_due_items"]) == 1
    assert "backlog_items" not in summary
    assert "claimed_open_items" not in summary
    assert "other_agent_claimed_items" not in summary["claim_scope"]
    assert "items" not in summary["todo_succession_warning"]
    assert summary["payload_compaction"]["omitted_lanes"] == {
        "backlog_items": 40,
        "claim_scope.other_agent_claimed_items": 40,
        "claimed_open_items": 40,
        "first_executable_items": 1,
        "first_open_items": 2,
        "monitor_due_items": 1,
        "todo_succession_warning.items": 40,
    }
    assert summary["payload_compaction"]["deduplicated_aliases"] == {
        "first_open_items.monitor_aliases": 1,
    }
    assert summary["payload_compaction"]["full_detail_cold_path"] == (
        QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND
    )
    assert len(payload["agent_todo_summary"]["backlog_items"]) == 40

    larger_backlog = _items(400, prefix="backlog")
    larger_payload = {
        **payload,
        "agent_todo_summary": {
            **payload["agent_todo_summary"],
            "backlog_items": larger_backlog,
            "claimed_open_items": larger_backlog,
            "claim_scope": {
                **payload["agent_todo_summary"]["claim_scope"],
                "other_agent_claimed_items": larger_backlog,
            },
            "todo_succession_warning": {
                "count": 300,
                "items": larger_backlog,
            },
        },
    }
    larger_compact = compact_quota_should_run_cli_payload(larger_payload)
    compact_chars = len(json.dumps(compact, sort_keys=True))
    larger_compact_chars = len(json.dumps(larger_compact, sort_keys=True))
    assert compact_chars < 10_000
    assert larger_compact_chars - compact_chars < 200


def test_compact_quota_should_run_cli_payload_keeps_active_user_work_and_gate_scope() -> None:
    active_user_actions = [
        {
            **item,
            "task_class": "user_action",
            "bound_agent": "quality-agent",
        }
        for item in _items(4, prefix="user-action")
    ]
    active_gates = [
        {
            **item,
            "task_class": "user_gate",
            "blocks_agent": "quality-agent",
            "decision_scope": "release:action:quota-output",
        }
        for item in _items(2, prefix="user-gate")
    ]
    other_agent_actions = [
        {
            **item,
            "task_class": "user_action",
            "bound_agent": "other-agent",
        }
        for item in _items(20, prefix="other-user-action")
    ]
    payload = {
        "interaction_contract": {
            "user_channel": {
                "action_required": True,
                "items": active_user_actions[:1],
            }
        },
        "selected_todo": {"todo_id": "quality-0"},
        "scheduler_hint": {"action": "wait"},
        "user_todo_summary": {
            "schema_version": "todo_summary_v0",
            "total_count": 30,
            "open_count": 6,
            "all_open_count": 26,
            "first_open_items": active_user_actions,
            "gate_open_items": active_gates,
            "active_next_action_items": active_user_actions[:2],
            "deferred_items": other_agent_actions,
            "other_agent_bound_user_action_items": other_agent_actions,
            "claim_scope": {
                "schema_version": "agent_claim_scope_v0",
                "blocked_claimed_open_count": 2,
                "blocked_claimed_items": other_agent_actions,
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_vision_audit_detail=True,
    )

    summary = compact["user_todo_summary"]
    assert summary["total_count"] == 30
    assert summary["open_count"] == 6
    assert len(summary["first_open_items"]) == 3
    assert summary["gate_open_items"] == active_gates
    assert summary["active_next_action_items"] == active_user_actions[:2]
    assert summary["gate_open_items"][0]["blocks_agent"] == "quality-agent"
    assert summary["gate_open_items"][0]["decision_scope"] == (
        "release:action:quota-output"
    )
    assert "deferred_items" not in summary
    assert "other_agent_bound_user_action_items" not in summary
    assert "blocked_claimed_items" not in summary["claim_scope"]
    assert summary["payload_compaction"]["omitted_lanes"] == {
        "claim_scope.blocked_claimed_items": 20,
        "deferred_items": 20,
        "first_open_items": 1,
        "other_agent_bound_user_action_items": 20,
    }
    assert summary["payload_compaction"]["full_detail_cold_path"] == (
        QUOTA_CLI_USER_TODO_SUMMARY_DETAIL_COMMAND
    )
    assert compact["interaction_contract"] == payload["interaction_contract"]
    assert compact["selected_todo"] == payload["selected_todo"]

    full = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_vision_audit_detail=True,
    )
    assert full == payload


def test_compact_quota_should_run_cli_payload_bounds_capability_gate_candidates() -> None:
    runnable = [
        {
            **item,
            "priority": "P1",
            "action_kind": "run_quality_slice",
            "task_repository": "git:github.com/example/loopx",
            "required_capabilities": ["shell", "filesystem_write"],
            "missing_capabilities": [],
            "capability_action": "run",
            "claimed_by": "quality-agent",
            "handoff_note": {
                "summary": "duplicated handoff detail " * 40,
            },
        }
        for item in _items(5, prefix="runnable")
    ]
    runnable[0]["text"] = "candidate " * 80
    runnable[0]["title"] = runnable[0]["text"]
    blocked = [
        {
            **item,
            "priority": "P0",
            "required_capabilities": ["credentials"],
            "missing_capabilities": ["credentials"],
            "capability_action": "ask_owner",
        }
        for item in _items(4, prefix="blocked")
    ]
    payload = {
        "interaction_contract": {"mode": "bounded_delivery"},
        "selected_todo": {"todo_id": "runnable-0"},
        "scheduler_hint": {"action": "run_now"},
        "capability_gate": {
            "schema_version": "capability_gate_v0",
            "action": "run",
            "decision_owner": "agent",
            "selection_policy": "agent_steering_audit_over_runnable_candidates",
            "candidate_order_policy": "claim_then_priority",
            "required": ["shell", "filesystem_write"],
            "available": ["shell", "filesystem_write"],
            "missing": [],
            "runnable_count": 5,
            "runnable_candidates": runnable,
            "blocked_candidates": blocked,
            "blocked_missing": ["credentials"],
            "owner_missing": ["credentials"],
            "owner_action": "provide or authorize credentials for blocked-0",
            "resolution_bindings": [
                {
                    "owner": "user",
                    "capability": "credentials",
                    "primary_blocked_todo_id": "blocked-0",
                }
            ],
        },
    }

    compact = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_vision_audit_detail=True,
    )

    gate = compact["capability_gate"]
    assert gate["action"] == "run"
    assert gate["decision_owner"] == "agent"
    assert gate["owner_missing"] == ["credentials"]
    assert gate["owner_action"] == "provide or authorize credentials for blocked-0"
    assert gate["resolution_bindings"] == payload["capability_gate"][
        "resolution_bindings"
    ]
    assert gate["runnable_count"] == 5
    assert gate["blocked_count"] == 4
    assert [item["todo_id"] for item in gate["runnable_candidates"]] == [
        "runnable-0",
        "runnable-1",
        "runnable-2",
    ]
    assert [item["todo_id"] for item in gate["blocked_candidates"]] == [
        "blocked-0",
        "blocked-1",
        "blocked-2",
    ]
    assert gate["runnable_candidates"][0]["title_truncated"] is True
    assert len(gate["runnable_candidates"][0]["title"]) == 240
    assert "text" not in gate["runnable_candidates"][0]
    assert "handoff_note" not in gate["runnable_candidates"][0]
    assert gate["blocked_candidates"][0]["missing_capabilities"] == [
        "credentials"
    ]
    assert gate["payload_compaction"]["omitted_candidates"] == {
        "blocked_candidates": 1,
        "runnable_candidates": 2,
    }
    assert gate["payload_compaction"]["full_detail_cold_path"] == (
        QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND
    )
    assert compact["capability_gate_projection"]["detail_ref"] == (
        QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND
    )
    for key in ("interaction_contract", "scheduler_hint", "selected_todo"):
        assert compact[key] == payload[key]

    full = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_capability_gate_detail=True,
        include_vision_audit_detail=True,
    )
    assert full == payload


def test_compact_quota_should_run_cli_payload_keeps_agent_lane_handoff_lineage() -> None:
    payload = {
        "interaction_contract": {"mode": "bounded_delivery"},
        "selected_todo": {"todo_id": "quality-0"},
        "scheduler_hint": {"action": "run_now"},
        "agent_lane_next_action": {
            "schema_version": "agent_lane_next_action_v0",
            "todo_id": "quality-0",
            "index": 12,
            "text": "continue the bounded quality slice " * 30,
            "title": "continue the bounded quality slice " * 30,
            "role": "agent",
            "status": "open",
            "priority": "P1",
            "archive_state": "active",
            "source_section": "Agent Todo",
            "task_class": "advancement_task",
            "action_kind": "qualify_output",
            "task_repository": "git:github.com/example/loopx",
            "continuation_policy": "independent_handoff",
            "required_capabilities": ["shell", "filesystem_write"],
            "claimed_by": "quality-agent",
            "updated_at": "2026-07-24T00:00:00Z",
            "agent_id": "quality-agent",
            "source": "capability_gate.runnable_candidates",
            "selected_by": "current_agent_claimed_todo",
            "confidence": "selected",
            "preserves_goal_next_action": True,
            "handoff_note": {
                "schema_version": "handoff_note_v0",
                "handoff_id": "handoff_quality_0",
                "todo_id": "quality-0",
                "from_agent": "planner-agent",
                "to_agent": "quality-agent",
                "intent": "qualify_output",
                "summary": "duplicated handoff summary " * 30,
                "evidence_refs": ["todo:quality-0:evidence"],
                "blocked_on": "todo:design-0",
                "suggested_next_action": "duplicated next action " * 30,
                "unblocks_todo_id": "design-0",
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_capability_gate_detail=True,
        include_vision_audit_detail=True,
    )

    lane = compact["agent_lane_next_action"]
    assert lane["schema_version"] == (
        "quota_cli_agent_lane_next_action_compaction_v0"
    )
    assert lane["source_schema_version"] == "agent_lane_next_action_v0"
    assert lane["todo_id"] == "quality-0"
    assert lane["agent_id"] == "quality-agent"
    assert lane["source"] == "capability_gate.runnable_candidates"
    assert "text" not in lane
    assert "title" not in lane
    assert "index" not in lane
    assert "status" not in lane
    assert "updated_at" not in lane
    assert "archive_state" not in lane
    assert lane["handoff_lineage"] == {
        "schema_version": "handoff_note_v0",
        "handoff_id": "handoff_quality_0",
        "todo_id": "quality-0",
        "from_agent": "planner-agent",
        "to_agent": "quality-agent",
        "intent": "qualify_output",
        "evidence_refs": ["todo:quality-0:evidence"],
        "blocked_on": "todo:design-0",
        "unblocks_todo_id": "design-0",
    }
    assert lane["detail_ref"] == (
        QUOTA_CLI_AGENT_LANE_NEXT_ACTION_DETAIL_COMMAND
    )
    assert lane["instruction_ref"] == "#/selected_todo"
    for key in ("interaction_contract", "scheduler_hint", "selected_todo"):
        assert compact[key] == payload[key]

    full = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_capability_gate_detail=True,
        include_agent_lane_next_action_detail=True,
        include_vision_audit_detail=True,
    )
    assert full == payload


def test_compact_quota_should_run_cli_payload_references_next_action_sources() -> None:
    payload = {
        "active_state_next_action": "durable goal route",
        "latest_run_recommended_action": "agent-lane run recommendation",
        "selected_todo": {
            "todo_id": "quality-0",
            "text": "continue the bounded quality slice",
        },
        "goal_route_hint": {
            "schema_version": "goal_route_hint_v0",
            "route_decision": "run_current_agent_lane",
            "preserves_goal_next_action": True,
        },
        "next_action_projection_warning": {
            "schema_version": "next_action_projection_warning_v0",
            "kind": "next_action_projection_mismatch",
            "severity": "info",
            "requires_state_writeback": False,
            "active_state_next_action": "durable goal route",
            "latest_run_recommended_action": "agent-lane run recommendation",
            "reason": "the selected lane preserves the durable route",
            "recommended_action": "run the selected agent lane",
            "agent_lane_next_action": "continue the bounded quality slice",
        },
        "interaction_contract": {"mode": "bounded_delivery"},
        "scheduler_hint": {"action": "run_now"},
    }

    compact = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_capability_gate_detail=True,
        include_agent_lane_next_action_detail=True,
        include_vision_audit_detail=True,
    )

    warning = compact["next_action_projection_warning"]
    assert warning["schema_version"] == (
        "quota_cli_next_action_projection_compaction_v0"
    )
    assert warning["source_schema_version"] == (
        "next_action_projection_warning_v0"
    )
    assert warning["kind"] == "next_action_projection_mismatch"
    assert warning["severity"] == "info"
    assert warning["requires_state_writeback"] is False
    assert warning["goal_route_hint_ref"] == "#/goal_route_hint"
    assert warning["active_state_next_action_ref"] == (
        "#/active_state_next_action"
    )
    assert warning["latest_run_recommended_action_ref"] == (
        "#/latest_run_recommended_action"
    )
    assert warning["agent_lane_next_action_ref"] == "#/selected_todo/text"
    assert warning["detail_ref"] == (
        QUOTA_CLI_NEXT_ACTION_PROJECTION_DETAIL_COMMAND
    )
    assert "active_state_next_action" not in warning
    assert "latest_run_recommended_action" not in warning
    assert "agent_lane_next_action" not in warning
    for key in (
        "goal_route_hint",
        "interaction_contract",
        "scheduler_hint",
        "selected_todo",
    ):
        assert compact[key] == payload[key]

    full = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_capability_gate_detail=True,
        include_agent_lane_next_action_detail=True,
        include_next_action_projection_detail=True,
        include_vision_audit_detail=True,
    )
    assert full == payload


def test_compact_quota_should_run_cli_payload_deduplicates_vision_audit() -> None:
    audit = {
        "schema_version": "vision_continuation_audit_v0",
        "required": True,
        "agent_id": "quality-agent",
        "decision": "acceptance_gap_open",
        "selected_todo_is_goal_completion": False,
        "closeout_allowed_without_evidence": False,
        "trigger_count": 1,
        "trigger_kinds": ["vision_acceptance_gap"],
        "acceptance_gaps": _items(30, prefix="gap"),
        "required_before_closeout": [f"requirement-{index}" for index in range(30)],
        "recommended_action": "continue one bounded quality slice",
        "vision_gap_judge": {
            "done": False,
            "decision": "continue",
            "agent_judge_instruction": "inspect authoritative evidence",
        },
    }
    payload = {
        "selected_todo": {"todo_id": "quality-0"},
        "scheduler_hint": {"action": "run_now"},
        "vision_continuation_audit": audit,
        "goal_frontier_projection": {
            "vision_continuation_audit": audit,
        },
        "interaction_contract": {
            "mode": "bounded_delivery",
            "agent_channel": {
                "must_attempt": True,
                "vision_continuation_audit": audit,
            },
            "cli_channel": {
                "next_cli_actions": ["continue"],
                "vision_continuation_audit": audit,
            },
        },
    }

    compact = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
    )

    root = compact["vision_continuation_audit"]
    assert root["required"] is True
    assert root["decision"] == "acceptance_gap_open"
    assert root["recommended_action"] == "continue one bounded quality slice"
    assert root["detail_ref"] == QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND
    assert "acceptance_gaps" not in root
    assert "vision_gap_judge" not in root
    for nested in (
        compact["goal_frontier_projection"]["vision_continuation_audit"],
        compact["interaction_contract"]["agent_channel"][
            "vision_continuation_audit"
        ],
        compact["interaction_contract"]["cli_channel"][
            "vision_continuation_audit"
        ],
    ):
        assert nested["required"] is True
        assert nested["decision"] == "acceptance_gap_open"
        assert nested["recommended_action"] == "continue one bounded quality slice"
        assert nested["detail_ref"] == QUOTA_CLI_VISION_AUDIT_ROOT_REF
        assert "acceptance_gaps" not in nested
    assert payload["vision_continuation_audit"]["acceptance_gaps"]

    full = compact_quota_should_run_cli_payload(
        payload,
        include_todo_summary_detail=True,
        include_user_todo_summary_detail=True,
        include_vision_audit_detail=True,
    )
    assert full == payload
    compact_chars = len(json.dumps(compact, sort_keys=True))
    full_chars = len(json.dumps(full, sort_keys=True))
    assert compact_chars < full_chars * 0.45
