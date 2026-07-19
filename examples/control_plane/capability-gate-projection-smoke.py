#!/usr/bin/env python3
"""Smoke-test capability-gate projection and decision contracts used by quota."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.agents.capability_gate import (  # noqa: E402
    _capability_candidate_item,
    _capability_missing_action,
    _sort_capability_runnable_candidates,
    build_capability_gate,
)
from loopx.control_plane.agents.agent_lane_recommendation import (  # noqa: E402
    build_agent_lane_next_action,
)


AGENT_ID = "codex-product-capability"
PRIMARY_AGENT = "codex-main-control"


def todo(
    todo_id: str,
    index: int,
    priority: str,
    *,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
    unblocks_todo_id: str | None = None,
    action_kind: str | None = None,
    continuation_policy: str | None = None,
    required_capabilities: list[str] | None = None,
    target_capabilities: list[str] | None = None,
) -> dict:
    item = {
        "schema_version": "todo_item_v0",
        "todo_id": todo_id,
        "role": "agent",
        "source_section": "Agent Todo",
        "status": "open",
        "done": False,
        "index": index,
        "priority": priority,
        "text": f"[{priority}] fixture {todo_id}",
        "task_class": "advancement_task",
    }
    if claimed_by:
        item["claimed_by"] = claimed_by
    if blocks_agent:
        item["blocks_agent"] = blocks_agent
    if unblocks_todo_id:
        item["unblocks_todo_id"] = unblocks_todo_id
    if action_kind:
        item["action_kind"] = action_kind
    if continuation_policy:
        item["continuation_policy"] = continuation_policy
    if required_capabilities:
        item["required_capabilities"] = required_capabilities
    if target_capabilities:
        item["target_capabilities"] = target_capabilities
    return item


def assert_missing_action_contract() -> None:
    assert _capability_missing_action([]) == "run"
    assert _capability_missing_action(["benchmark_runner"]) == "repair_bridge"
    assert _capability_missing_action(["network"]) == "repair_bridge"
    assert _capability_missing_action(["credentials"]) == "ask_owner"
    assert _capability_missing_action(["custom_capability"]) == "skip"


def assert_candidate_compaction_contract() -> None:
    item = todo(
        "todo_bridge",
        3,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["shell", "benchmark_runner"],
        target_capabilities=["status_quota_read_model_refactor"],
    )
    candidate = _capability_candidate_item(
        item,
        missing=["benchmark_runner"],
        missing_target_capabilities=["benchmark_runner"],
    )
    assert candidate["todo_id"] == "todo_bridge", candidate
    assert candidate["required_capabilities"] == ["shell", "benchmark_runner"], (
        candidate
    )
    assert candidate["target_capabilities"] == ["status_quota_read_model_refactor"], (
        candidate
    )
    assert candidate["missing_capabilities"] == ["benchmark_runner"], candidate
    assert candidate["missing_target_capabilities"] == ["benchmark_runner"], candidate
    assert candidate["capability_action"] == "repair_bridge", candidate
    assert candidate["capability_repair_mode"] is True, candidate


def assert_current_agent_candidate_order_contract() -> None:
    runnable = [
        todo("todo_unclaimed_p0", 1, "P0"),
        todo("todo_current_p2", 2, "P2", claimed_by=AGENT_ID),
        todo(
            "todo_current_unblock_p2",
            3,
            "P2",
            claimed_by=AGENT_ID,
            unblocks_todo_id="todo_value_explorer_delivery",
        ),
        todo("todo_other_p0", 4, "P0", claimed_by=PRIMARY_AGENT),
        todo(
            "todo_primary_review",
            5,
            "P2",
            claimed_by=AGENT_ID,
            action_kind="merge_gate",
            continuation_policy="independent_handoff",
        ),
    ]
    ordered, policy = _sort_capability_runnable_candidates(
        runnable,
        agent_identity={
            "agent_id": AGENT_ID,
            "agent_model": "peer_v1",
        },
    )
    assert policy == "claim_then_priority_then_active_next_then_repair"
    assert [item["todo_id"] for item in ordered] == [
        "todo_current_p2",
        "todo_current_unblock_p2",
        "todo_primary_review",
        "todo_unclaimed_p0",
        "todo_other_p0",
    ], ordered


def assert_stale_active_next_does_not_override_ready_p0() -> None:
    ready_p0 = todo("todo_ready_p0", 2, "P0", claimed_by=AGENT_ID)
    ready_p0.update(
        {
            "resume_when": "todo_done:todo_dependency",
            "resume_ready": True,
            "resume_condition": {
                "schema_version": "todo_resume_condition_v0",
                "resume_when": "todo_done:todo_dependency",
                "kind": "todo_done",
                "target_todo_id": "todo_dependency",
                "target_status": "done",
                "satisfied": True,
            },
        }
    )
    stale_p1 = todo("todo_stale_p1", 3, "P1", claimed_by=AGENT_ID)
    other_peer_p0 = todo("todo_other_peer_p0", 1, "P0", claimed_by=PRIMARY_AGENT)
    selected = build_agent_lane_next_action(
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
        agent_todo_summary={
            "active_next_action_executable_items": [stale_p1],
        },
        capability_gate={
            "runnable_candidates": [stale_p1, other_peer_p0, ready_p0],
        },
        active_next_action="Continue todo_stale_p1 after the resumed P0.",
    )
    assert selected is not None
    assert selected["todo_id"] == "todo_ready_p0", selected
    assert selected["selected_by"] == "current_agent_claimed_todo", selected
    assert selected["source"] == "capability_gate.runnable_candidates", selected


def assert_gate_prefers_active_next_and_exposes_blocked_fallback() -> None:
    blocked = todo(
        "todo_needs_network",
        1,
        "P0",
        claimed_by=AGENT_ID,
        required_capabilities=["network"],
    )
    runnable = todo(
        "todo_local_refactor",
        2,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["shell"],
    )
    gate = build_capability_gate(
        {
            "active_next_action_executable_items": [blocked, blocked],
            "executable_backlog_items": [runnable],
        },
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["schema_version"] == "capability_gate_v0", gate
    assert gate["source"] == "agent_todo_summary.active_next_action_executable_items", (
        gate
    )
    assert gate["action"] == "run", gate
    assert gate["decision_owner"] == "agent", gate
    assert gate["runnable_candidates"][0]["todo_id"] == "todo_local_refactor", gate
    assert [item["todo_id"] for item in gate["blocked_candidates"]] == [
        "todo_needs_network"
    ], gate
    assert gate["blocked_missing"] == ["network"], gate
    assert gate["repair_missing"] == ["network"], gate
    assert gate["resolution_bindings"] == [
        {
            "owner": "agent",
            "action": "repair_bridge",
            "capability": "network",
            "priority": "P0",
            "primary_blocked_todo_id": "todo_needs_network",
            "blocked_todo_ids": ["todo_needs_network"],
        }
    ], gate
    assert gate["available"] == ["shell", "filesystem_read", "filesystem_write"], gate


def assert_runnable_fallback_preserves_owner_resolution() -> None:
    blocked = todo(
        "todo_needs_credentials",
        1,
        "P0",
        claimed_by=AGENT_ID,
        required_capabilities=["credentials"],
    )
    runnable = todo(
        "todo_local_docs",
        2,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["shell"],
    )
    gate = build_capability_gate(
        {"executable_backlog_items": [blocked, runnable]},
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["action"] == "run", gate
    assert gate["owner_missing"] == ["credentials"], gate
    assert gate["owner_action"] == (
        "provide or authorize the missing owner-held capability: credentials "
        "for todo_needs_credentials"
    ), gate
    assert gate["resolution_bindings"] == [
        {
            "owner": "user",
            "action": "provide_or_authorize",
            "capability": "credentials",
            "priority": "P0",
            "primary_blocked_todo_id": "todo_needs_credentials",
            "blocked_todo_ids": ["todo_needs_credentials"],
        }
    ], gate
    assert gate["runnable_candidates"][0]["todo_id"] == "todo_local_docs", gate


def assert_target_capability_creates_repair_hint_not_hard_block() -> None:
    item = todo(
        "todo_bridge_repair",
        3,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["shell", "benchmark_runner"],
        target_capabilities=["benchmark_runner"],
    )
    gate = build_capability_gate(
        {"executable_backlog_items": [item]},
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["action"] == "run", gate
    assert gate["repair_candidate_count"] == 1, gate
    assert gate["repair_missing"] == ["benchmark_runner"], gate
    candidate = gate["runnable_candidates"][0]
    assert candidate["todo_id"] == "todo_bridge_repair", gate
    assert candidate["capability_repair_mode"] is True, gate
    assert candidate["capability_action"] == "repair_bridge", gate


def assert_all_blocked_runtime_capability_routes_to_agent_repair() -> None:
    item = todo(
        "todo_live_fetch",
        4,
        "P0",
        required_capabilities=["network"],
    )
    gate = build_capability_gate(
        {"first_executable_items": [item]},
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["source"] == "agent_todo_summary.first_executable_items", gate
    assert gate["action"] == "repair_bridge", gate
    assert gate["decision_owner"] == "agent", gate
    assert gate["owner_missing"] == [], gate
    assert gate["repair_missing"] == ["network"], gate
    assert gate["resolution_steps"] == [
        {
            "owner": "agent",
            "action": "repair_bridge",
            "capabilities": ["network"],
        }
    ], gate
    assert gate["blocks_delivery"] is True, gate
    assert gate["missing"] == ["network"], gate
    assert gate["owner_action"] is None, gate


def assert_all_blocked_owner_capability_stops_delivery() -> None:
    item = todo(
        "todo_credentials",
        5,
        "P0",
        required_capabilities=["credentials"],
    )
    gate = build_capability_gate(
        {"first_executable_items": [item]},
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["action"] == "ask_owner", gate
    assert gate["decision_owner"] == "user", gate
    assert gate["owner_missing"] == ["credentials"], gate
    assert gate["repair_missing"] == [], gate
    assert gate["owner_action"] == (
        "provide or authorize the missing owner-held capability: credentials "
        "for todo_credentials"
    ), gate


def assert_requirement_free_advancement_does_not_create_gate() -> None:
    item = todo("todo_plain_local", 5, "P2")
    gate = build_capability_gate(
        {"executable_backlog_items": [item]},
        available_capabilities=[],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is None


def assert_due_monitor_source_composes_with_advancement() -> None:
    advancement = todo(
        "todo_local_delivery",
        6,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["shell"],
    )
    monitor = todo(
        "todo_network_monitor",
        7,
        "P1",
        claimed_by=AGENT_ID,
        required_capabilities=["network"],
    )
    monitor["task_class"] = "continuous_monitor"
    gate = build_capability_gate(
        {
            "executable_backlog_items": [advancement],
            "monitor_due_items": [monitor],
        },
        available_capabilities=["shell"],
        agent_identity={"agent_id": AGENT_ID, "agent_model": "peer_v1"},
    )
    assert gate is not None
    assert gate["action"] == "run", gate
    assert gate["source"] == (
        "agent_todo_summary.executable_backlog_items+"
        "agent_todo_summary.monitor_due_items"
    ), gate
    assert [item["todo_id"] for item in gate["runnable_candidates"]] == [
        "todo_local_delivery"
    ], gate
    assert [item["todo_id"] for item in gate["blocked_candidates"]] == [
        "todo_network_monitor"
    ], gate


def main() -> int:
    assert_missing_action_contract()
    assert_candidate_compaction_contract()
    assert_current_agent_candidate_order_contract()
    assert_stale_active_next_does_not_override_ready_p0()
    assert_gate_prefers_active_next_and_exposes_blocked_fallback()
    assert_runnable_fallback_preserves_owner_resolution()
    assert_target_capability_creates_repair_hint_not_hard_block()
    assert_all_blocked_runtime_capability_routes_to_agent_repair()
    assert_all_blocked_owner_capability_stops_delivery()
    assert_requirement_free_advancement_does_not_create_gate()
    assert_due_monitor_source_composes_with_advancement()
    print("capability-gate-projection-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
