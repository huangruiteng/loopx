#!/usr/bin/env python3
"""Smoke-test compact protocol action packets for quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.scheduler.execution_context import (
    SchedulerRuntimeProfile,
    scheduler_execution_context_for_runtime_profile,
)
from loopx.quota import (
    build_quota_should_run as _build_quota_should_run,
    render_quota_should_run_markdown,
)


GOAL_ID = "protocol-packet-fixture"
ADVANCEMENT_TODO = (
    "[P1] LLM-assisted protocol simplification research spike: compare a "
    "deterministic action packet with an optional Codex/LLM router before "
    "adding direct API wiring."
)
MONITOR_TODO = (
    "[P2] Meta canary/readiness observation lane: keep status health observable."
)
FULL_AIRLINE_ACTION = (
    "Collect or aggregate additional same-protocol full-airline experience-route "
    "repeats, then rebuild dynamic-beta labels and rerun the standard "
    "source-heldout vector-aware scorer gate."
)
USER_TODO = "[P1] Decide whether to approve a no-submit setup check."
CODEX_APP_SCHEDULER_CONTEXT = scheduler_execution_context_for_runtime_profile(
    SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT
)


def build_quota_should_run(*args, **kwargs):
    kwargs.setdefault("scheduler_execution_context", CODEX_APP_SCHEDULER_CONTEXT)
    return _build_quota_should_run(*args, **kwargs)


def status_payload(
    *,
    agent_todos: list[dict],
    user_todos: list[dict] | None = None,
    status: str = "protocol_packet_fixture",
    next_action: str = "Advance the P1 protocol simplification spike.",
) -> dict:
    agent_summary = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(agent_todos),
        "open_count": len(agent_todos),
        "done_count": 0,
        "first_open_items": agent_todos[:3],
    }
    item = {
        "goal_id": GOAL_ID,
        "status": status,
        "waiting_on": "codex",
        "severity": "info",
        "source": "project_asset",
        "recommended_action": next_action,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "allowed_slots": 10,
            "spent_slots": 0,
            "state": "eligible",
            "reason": "eligible fixture",
        },
        "project_asset": {
            "next_action": next_action,
            "stop_condition": "stop on private material",
            "agent_todos": agent_summary,
        },
    }
    if user_todos:
        user_summary = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "total_count": len(user_todos),
            "open_count": len(user_todos),
            "done_count": 0,
            "first_open_items": user_todos,
            "items": user_todos,
        }
        item["user_todos"] = user_summary
        item["project_asset"]["user_todos"] = user_summary
    payload = {
        "ok": True,
        "attention_queue": {
            "items": [item],
        },
        "run_history": {
            "goals": [
                {
                    "id": GOAL_ID,
                    "registry_member": True,
                    "status": status,
                    "adapter_kind": "harness_self_improvement",
                    "adapter_status": "connected-read-only",
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
    advancement_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "advancement_task"
        or "research spike" in str(item.get("text") or "")
    ]
    monitor_items = [
        item
        for item in agent_todos
        if item.get("task_class") == "continuous_monitor"
        or "observation lane" in str(item.get("text") or "")
    ]
    if advancement_items:
        payload["attention_queue"]["autonomous_backlog_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(advancement_items),
            "task_class": "advancement_task",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "advancement_task",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in advancement_items
            ],
        }
    if monitor_items:
        payload["attention_queue"]["autonomous_monitor_candidates"] = {
            "source": "attention_queue.agent_todos",
            "open_count": len(monitor_items),
            "task_class": "continuous_monitor",
            "items": [
                {
                    "goal_id": GOAL_ID,
                    "status": status,
                    "waiting_on": "codex",
                    "quota_state": "eligible",
                    "priority": item.get("priority"),
                    "todo_index": item.get("index"),
                    "task_class": "continuous_monitor",
                    "text": item.get("text"),
                    "source": "agent_todos",
                }
                for item in monitor_items
            ],
        }
    return payload


def todo(index: int, text: str, *, priority: str, task_class: str | None = None) -> dict:
    item = {
        "index": index,
        "text": text,
        "role": "agent",
        "status": "open",
        "priority": priority,
    }
    if task_class:
        item["task_class"] = task_class
    return item


def user_todo(
    index: int,
    text: str,
    *,
    task_class: str | None = None,
    action_kind: str | None = None,
    claimed_by: str | None = None,
    blocks_agent: str | None = None,
) -> dict:
    item = {
        "index": index,
        "text": text,
        "role": "user",
        "status": "open",
        "priority": "P1",
    }
    if task_class:
        item["task_class"] = task_class
    if action_kind:
        item["action_kind"] = action_kind
    if claimed_by:
        item["claimed_by"] = claimed_by
    if blocks_agent:
        item["blocks_agent"] = blocks_agent
    return item


def assert_advancement_packet_prefers_backlog_candidate() -> None:
    guard = build_quota_should_run(
        status_payload(
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
                todo(2, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert packet["schema_version"] == "protocol_action_packet_v0", packet
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "LLM-assisted protocol simplification" in packet["summary"], packet
    assert "compare a deterministic" not in packet["summary"], packet
    assert "llm=no_api" in packet["summary"], packet
    summary = guard["agent_todo_summary"]
    assert summary["first_executable_items"][0]["text"] == ADVANCEMENT_TODO, summary
    assert summary["monitor_open_items"][0]["text"] == MONITOR_TODO, summary
    markdown = render_quota_should_run_markdown(guard)
    assert "protocol_action_packet: schema=protocol_action_packet_v0 actor=agent" in markdown, markdown


def assert_advancement_packet_keeps_user_todo_pending() -> None:
    guard = build_quota_should_run(
        status_payload(
            agent_todos=[
                todo(1, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
            ],
            user_todos=[user_todo(1, USER_TODO)],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    contract = guard["interaction_contract"]
    assert "actor=agent_with_user_gate" in packet["summary"], packet
    assert "user_action_required=true" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "user_action_pending=true" in packet["summary"], packet
    assert f"user_action={USER_TODO}" in packet["summary"], packet
    assert "agent_action=[P1] LLM-assisted protocol simplification research spike" in packet["summary"], packet
    assert f"agent_action={USER_TODO}" not in packet["summary"], packet
    assert contract["mode"] == "bounded_delivery_with_user_notice", contract
    assert contract["user_channel"]["action_required"] is True, contract
    assert contract["user_channel"]["notify"] == "NOTIFY", contract
    assert contract["agent_channel"]["must_attempt"] is True, contract


def assert_explicit_user_gate_still_allows_independent_agent_action() -> None:
    gate_todo = (
        "[P0] Approve one no-upload Terminal-Bench rerun before crossing the "
        "resource boundary."
    )
    guard = build_quota_should_run(
        status_payload(
            agent_todos=[
                todo(1, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
            ],
            user_todos=[
                user_todo(
                    1,
                    gate_todo,
                    task_class="user_gate",
                    action_kind="approve_resource_boundary",
                )
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    contract = guard["interaction_contract"]
    user_summary = guard["user_todo_summary"]
    assert guard["requires_user_action"] is True, guard
    assert guard["notify_user_on_gate"] is True, guard
    assert guard["open_todo_notification_policy"] == "repeat_until_resolved", guard
    assert user_summary["gate_open_items"][0]["text"] == gate_todo, user_summary
    assert "actor=agent_with_user_gate" in packet["summary"], packet
    assert "user_action_required=true" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "user_action=[P0] Approve one no-upload Terminal-Bench rerun" in packet["summary"], packet
    assert "agent_action=[P1] LLM-assisted protocol simplification" in packet["summary"], packet
    assert contract["mode"] == "bounded_delivery_with_user_notice", contract
    assert contract["user_channel"]["action_required"] is True, contract
    assert contract["user_channel"]["notify"] == "NOTIFY", contract
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["primary_action"] == (
        "[P1] LLM-assisted protocol simplification research spike"
    ), contract


def assert_monitor_only_packet_keeps_user_todo_pending() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_fixture",
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
            ],
            user_todos=[user_todo(1, USER_TODO)],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    contract = guard["interaction_contract"]
    assert "actor=agent_with_user_gate" in packet["summary"], packet
    assert "user_action_required=true" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "user_action_pending=true" in packet["summary"], packet
    assert "agent_action=repair the selected continuous_monitor todo" in packet["summary"], packet
    assert f"user_action={USER_TODO}" in packet["summary"], packet
    assert USER_TODO in packet["summary"], packet
    assert guard.get("notify_user_on_open_todo") is None, guard
    assert contract["mode"] == "bounded_delivery_with_user_notice", contract
    assert contract["user_channel"]["action_required"] is True, contract
    assert contract["user_channel"]["notify"] == "NOTIFY", contract
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is False, contract


def assert_agent_scoped_user_gate_stays_diagnostic_only() -> None:
    payload = status_payload(
        status="operator_gate_fixture",
        agent_todos=[
            todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
        ],
        user_todos=[
            user_todo(
                82,
                "[P0-decision] Review/merge PR #807 or explicitly authorize admin-bypass merge.",
                task_class="user_gate",
                action_kind="review_pr",
                claimed_by="codex-main-control",
                blocks_agent="codex-main-control",
            )
        ],
    )
    payload["attention_queue"]["items"][0]["quota"]["state"] = "operator_gate"
    payload["run_history"]["goals"][0]["coordination"] = {
        "agent_model": "peer_v1",
        "registered_agents": [
            "codex-main-control",
            "codex-product-capability",
        ],
    }
    guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id="codex-product-capability",
    )
    user_summary = guard["user_todo_summary"]
    assert user_summary["open_count"] == 0, user_summary
    assert user_summary["other_agent_scoped_open_count"] == 1, user_summary
    assert "gate_prompt" not in guard, guard
    assert guard["state"] == "eligible", guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["should_run"] is True, guard
    lane = guard["work_lane_contract"]
    assert lane["obligation"] == "repair_monitor_schedule_metadata", lane
    assert lane["monitor_policy"] == "repair_schedule_metadata_before_quiet_wait", lane
    contract = guard["interaction_contract"]
    assert contract["mode"] == "bounded_delivery", contract
    assert contract["user_channel"]["action_required"] is False, contract
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert contract["agent_channel"]["quiet_noop_allowed"] is False, contract


def assert_explicit_non_gating_user_todo_stays_quiet() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_fixture",
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
            ],
            user_todos=[
                user_todo(
                    1,
                    "[P2] Watch the benchmark dashboard for a material transition.",
                    task_class="continuous_monitor",
                    action_kind="monitor",
                )
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    contract = guard["interaction_contract"]
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "user_action_pending=true" not in packet["summary"], packet
    assert "agent_action=repair the selected continuous_monitor todo" in packet["summary"], packet
    assert contract["mode"] == "bounded_delivery", contract
    assert contract["user_channel"]["action_required"] is False, contract
    assert contract["agent_channel"]["must_attempt"] is True, contract


def assert_monitor_only_packet_requires_schedule_metadata_repair() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_fixture",
            agent_todos=[
                todo(1, MONITOR_TODO, priority="P2", task_class="continuous_monitor"),
            ],
        ),
        goal_id=GOAL_ID,
    )
    packet = guard["protocol_action_packet"]
    assert "actor=agent" in packet["summary"], packet
    assert "user_action_required=false" in packet["summary"], packet
    assert "agent_action_required=true" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "lane=advancement_task" in packet["summary"], packet
    assert "agent_action=repair the selected continuous_monitor todo" in packet["summary"], packet
    lane = guard["work_lane_contract"]
    assert lane["obligation"] == "repair_monitor_schedule_metadata", lane
    assert lane["monitor_policy"] == "repair_schedule_metadata_before_quiet_wait", lane


def assert_executable_recommended_action_overrides_monitor_todo() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="monitor_wording_fixture",
            next_action=FULL_AIRLINE_ACTION,
            agent_todos=[
                todo(
                    1,
                    (
                        "[P0] Current route support-blocked monitor: keep the "
                        "full-airline experience-route repeat state visible."
                    ),
                    priority="P0",
                    task_class="continuous_monitor",
                ),
            ],
        ),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "materialize_advancement_todo_or_blocker", lane
    assert lane["reason_codes"] == ["monitor_todo_only", "next_action_requires_advancement"], lane
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    packet = guard["protocol_action_packet"]
    assert "agent_action_required=true" in packet["summary"], packet
    assert "Collect or aggregate additional same-protocol" in packet["summary"], packet
    contract = guard["interaction_contract"]
    assert contract["agent_channel"]["must_attempt"] is True, contract
    assert (
        "Collect or aggregate additional same-protocol"
        in contract["agent_channel"]["primary_action"]
    ), contract


def assert_goal_scoped_primary_action_ignores_foreign_backlog() -> None:
    payload = status_payload(
        agent_todos=[
            todo(1, ADVANCEMENT_TODO, priority="P1", task_class="advancement_task"),
        ],
    )
    payload["attention_queue"]["autonomous_backlog_candidates"]["items"].insert(
        0,
        {
            "goal_id": "foreign-goal",
            "status": "foreign_status",
            "waiting_on": "codex",
            "quota_state": "eligible",
            "priority": "P0",
            "todo_index": 1,
            "task_class": "advancement_task",
            "text": "[P0] Foreign Terminal-Bench backlog candidate should not leak.",
            "source": "agent_todos",
        },
    )
    payload["attention_queue"]["autonomous_backlog_candidates"]["open_count"] = 2
    guard = build_quota_should_run(payload, goal_id=GOAL_ID)
    packet = guard["protocol_action_packet"]
    contract = guard["interaction_contract"]
    assert "Foreign Terminal-Bench" not in packet["summary"], packet
    assert "Foreign Terminal-Bench" not in contract["agent_channel"]["primary_action"], contract
    assert "LLM-assisted protocol simplification" in packet["summary"], packet
    assert len(guard["autonomous_backlog_candidates"]["items"]) == 1, guard
    assert (
        guard["autonomous_backlog_candidates"]["items"][0]["goal_id"] == GOAL_ID
    ), guard


def main() -> None:
    assert_advancement_packet_prefers_backlog_candidate()
    assert_advancement_packet_keeps_user_todo_pending()
    assert_explicit_user_gate_still_allows_independent_agent_action()
    assert_monitor_only_packet_keeps_user_todo_pending()
    assert_agent_scoped_user_gate_stays_diagnostic_only()
    assert_explicit_non_gating_user_todo_stays_quiet()
    assert_monitor_only_packet_requires_schedule_metadata_repair()
    assert_executable_recommended_action_overrides_monitor_todo()
    assert_goal_scoped_primary_action_ignores_foreign_backlog()
    print("ok: protocol action packet smoke")


if __name__ == "__main__":
    main()
