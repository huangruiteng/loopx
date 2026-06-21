#!/usr/bin/env python3
"""Smoke-test monitor-vs-advancement lane projection in quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.quota import build_quota_should_run, render_quota_should_run_markdown
from loopx.status import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_task_class,
)


GOAL_ID = "work-lane-fixture"


def status_payload(
    *,
    status: str,
    has_agent_todo: bool = True,
    agent_todo_items: list[dict] | None = None,
    user_todo_items: list[dict] | None = None,
    next_action: str = "Observe dependency state and then advance backlog if unchanged.",
    post_handoff_latest_run: dict | None = None,
    coordination: dict | None = None,
) -> dict:
    if agent_todo_items is None:
        agent_todo_items = [
            {
                "index": 1,
                "text": "[P1] Advance the self-repair planning slice with a validation-backed patch.",
                "role": "agent",
                "status": "open",
                "priority": "P1",
            }
        ]
    open_items = agent_todo_items if has_agent_todo else []
    agent_todos = {
        "schema_version": "todo_summary_v0",
        "source_section": "Agent Todo",
        "total_count": len(open_items),
        "open_count": len(open_items),
        "done_count": 0,
        "first_open_items": open_items,
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
            "agent_todos": agent_todos,
        },
    }
    if post_handoff_latest_run:
        item["handoff_readiness"] = {
            "post_handoff_run_seen": True,
            "handoff_status": "post_handoff_run_seen",
            "post_handoff_latest_run": post_handoff_latest_run,
        }
    if coordination:
        item["coordination"] = coordination
    if user_todo_items:
        item["user_todos"] = {
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo / Owner Review Reading Queue",
            "total_count": len(user_todo_items),
            "open_count": len(user_todo_items),
            "done_count": 0,
            "first_open_items": user_todo_items,
            "items": user_todo_items,
        }
    goal_history_item = {
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
    if coordination:
        goal_history_item["coordination"] = coordination
    return {
        "ok": True,
        "attention_queue": {
            "items": [item]
        },
        "run_history": {
            "goals": [goal_history_item]
        },
    }


def assert_dependency_monitor_requires_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(status="side_bypass_dependency_observation"),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    lane = guard["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["monitor_kind"] == "dependency_observation", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_unless_material_monitor_transition", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["dependency_observation", "open_agent_todo"], lane
    recommendation = guard["heartbeat_recommendation"]
    assert recommendation["recommended_mode"] == "follow_work_lane_contract", recommendation
    assert "dependency_observation_cap" not in recommendation, recommendation
    assert "work_lane_contract" not in recommendation, recommendation
    assert guard["execution_obligation"]["kind"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["contract"] == "work_lane_contract", guard
    assert guard["execution_obligation"]["contract_obligation"] == lane["obligation"], guard
    assert "minimum" not in guard["execution_obligation"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=continuous_monitor next=advancement_task" in markdown, markdown
    assert "obligation=advance_unless_material_monitor_transition" in markdown, markdown
    assert "work_lane_reason_codes: dependency_observation,open_agent_todo" in markdown, markdown


def assert_primary_status_stays_advancement_lane() -> None:
    guard = build_quota_should_run(
        status_payload(status="self_repair_planning_slice"),
        goal_id=GOAL_ID,
    )
    assert guard["should_run"] is True, guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", guard
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane


def assert_structured_surface_only_run_requires_outcome_followthrough() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="runner_contract_delivered",
            next_action="Execute the compact runner batch or write the exact blocker.",
            post_handoff_latest_run={
                "classification": "runner_contract_v0_delivered",
                "delivery_batch_scale": "implementation",
                "delivery_outcome": "surface_only",
            },
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["should_run"] is True, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_primary_outcome_or_write_blocker", lane
    assert lane["reason_codes"] == [
        "open_agent_todo",
        "outcome_followthrough_required",
    ], lane
    assert lane["outcome_followthrough"]["latest_delivery_outcome"] == "surface_only", lane
    assert "contract-only" in lane["action"], lane


def assert_contract_word_alone_does_not_trigger_outcome_followthrough() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="runner_contract_delivered",
            post_handoff_latest_run={
                "classification": "runner_contract_v0_delivered",
                "delivery_batch_scale": "implementation",
                "delivery_outcome": "outcome_progress",
            },
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert "outcome_followthrough" not in lane, lane


def assert_monitor_only_todo_waits_quietly() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="typed_task_lane_planning_writeback",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "skip", guard
    assert guard["should_run"] is False, guard
    assert guard["normal_delivery_allowed"] is False, guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["monitor_kind"] == "todo_monitor", lane
    assert lane["next_lane"] == "continuous_monitor", lane
    assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
    assert lane["must_attempt_work"] is False, lane
    assert lane["reason_codes"] == ["monitor_todo_only"], lane
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "monitor_quiet_until_material_transition", guard
    assert guard["execution_obligation"]["kind"] == "monitor_quiet_skip", guard
    assert guard["execution_obligation"]["must_attempt_work"] is False, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert [item["task_class"] for item in first_items] == ["continuous_monitor", "continuous_monitor"], guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=continuous_monitor next=continuous_monitor" in markdown, markdown
    assert "obligation=quiet_until_material_monitor_transition" in markdown, markdown


def assert_monitor_only_with_user_todo_surfaces_user_action_without_transition() -> None:
    user_todo = (
        "[P1] Decide whether to approve a no-submit Terminal-Bench setup check "
        "or provide public official-runner output."
    )
    guard = build_quota_should_run(
        status_payload(
            status="typed_task_lane_planning_writeback",
            user_todo_items=[
                {
                    "index": 1,
                    "text": user_todo,
                    "role": "user",
                    "status": "open",
                    "priority": "P1",
                }
            ],
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "skip", guard
    assert guard["should_run"] is False, guard
    assert guard["normal_delivery_allowed"] is False, guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["must_attempt_work"] is False, lane
    recommendation = guard["heartbeat_recommendation"]
    assert recommendation["recommended_mode"] == "monitor_quiet_until_material_transition", recommendation
    assert recommendation["notify"] == "DONT_NOTIFY", recommendation
    assert "repeat_notification_required" not in recommendation, recommendation
    assert "notify_user_on_open_todo" not in guard, guard
    assert "open_todo_notification_policy" not in guard, guard
    assert guard["requires_user_action"] is False, guard
    assert guard["execution_obligation"]["must_attempt_work"] is False, guard
    interaction = guard["interaction_contract"]
    assert interaction["mode"] == "user_action_required", interaction
    assert interaction["user_channel"]["action_required"] is True, interaction
    assert interaction["user_channel"]["notify"] == "NOTIFY", interaction
    assert interaction["agent_channel"]["must_attempt"] is False, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
    packet = guard["protocol_action_packet"]
    assert "actor=user" in packet["summary"], packet
    assert "user_action_required=true" in packet["summary"], packet
    assert "agent_action_required=false" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
    assert "user_action=[P1] Decide whether to approve a no-submit Terminal-Bench" in packet["summary"], packet
    markdown = render_quota_should_run_markdown(guard)
    assert "monitor_quiet_until_material_transition" in markdown, markdown
    assert "heartbeat_repeat_notification_required" not in markdown, markdown
    assert "notify_user_on_open_todo" not in markdown, markdown
    assert "open_todo_notification_policy" not in markdown, markdown
    assert user_todo in markdown, markdown


def assert_blocked_agent_todo_with_user_gate_notifies_without_execution() -> None:
    user_todo = (
        "[P1] Provide GCP_PROJECT plus GCP_SA_KEY before the formal ALE run."
    )
    blocked_agent_todo = (
        "[P1] Prove ALE task-data substrate readiness before any formal local "
        "no-upload run. The remaining formal ALE path is official gs://ale-data-public "
        "staging with credential-file presence only. Do not launch any selected "
        "formal task until official GCS substrate proof is present."
    )
    truncated_blocked_agent_todo = (
        "[P1] Prove ALE task-data substrate readiness before any formal local "
        "no-upload run. The baked sandbox input route is absent, and the current "
        "selected pool has 0 baked-input candidates. The remaining formal ALE path is t..."
    )
    guard = build_quota_should_run(
        status_payload(
            status="ale_substrate_gates_documented_gcs_gate_needed",
            next_action=(
                "Formal ALE remains gated on official gs://ale-data-public substrate proof."
            ),
            user_todo_items=[
                {
                    "index": 1,
                    "text": user_todo,
                    "role": "user",
                    "status": "open",
                    "priority": "P1",
                }
            ],
            agent_todo_items=[
                {
                    "index": 1,
                    "text": blocked_agent_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "skip", guard
    assert guard["should_run"] is False, guard
    assert guard["normal_delivery_allowed"] is False, guard
    assert guard["effective_action"] == "monitor_quiet_skip", guard
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["next_lane"] == "continuous_monitor", lane
    assert lane["must_attempt_work"] is False, lane
    assert lane["reason_codes"] == ["monitor_todo_only"], lane
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "continuous_monitor", guard
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "monitor_quiet_until_material_transition", guard
    assert guard["execution_obligation"]["must_attempt_work"] is False, guard
    assert guard["requires_user_action"] is False, guard

    truncated_guard = build_quota_should_run(
        status_payload(
            status="ale_substrate_gates_documented_gcs_gate_needed",
            next_action="Formal ALE remains gated on official substrate proof.",
            user_todo_items=[
                {
                    "index": 1,
                    "text": user_todo,
                    "role": "user",
                    "status": "open",
                    "priority": "P1",
                }
            ],
            agent_todo_items=[
                {
                    "index": 1,
                    "text": truncated_blocked_agent_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    truncated_lane = truncated_guard["work_lane_contract"]
    assert truncated_lane["lane"] == "continuous_monitor", truncated_lane
    assert truncated_guard["agent_todo_summary"]["first_open_items"][0]["task_class"] == "continuous_monitor", truncated_guard
    assert truncated_guard["decision"] == "skip", truncated_guard
    assert truncated_guard["should_run"] is False, truncated_guard
    assert truncated_guard["effective_action"] == "monitor_quiet_skip", truncated_guard
    assert truncated_guard["execution_obligation"]["must_attempt_work"] is False, truncated_guard


def assert_monitor_only_with_planning_next_action_materializes_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="benchmark_experiment_report_template",
            next_action=(
                "Post-reporting lane should route to the planning/self-repair capability lane "
                "as the next eligible advancement turn."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["schema_version"] == "work_lane_contract_v1", lane
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "materialize_advancement_todo_or_blocker", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["monitor_todo_only", "next_action_requires_advancement"], lane
    assert "planning/self-repair" in lane["action"], lane
    assert guard["execution_obligation"]["contract_obligation"] == lane["obligation"], guard
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "work_lane_contract: lane=advancement_task next=advancement_task" in markdown, markdown
    assert "obligation=materialize_advancement_todo_or_blocker" in markdown, markdown
    assert "work_lane_reason_codes: monitor_todo_only,next_action_requires_advancement" in markdown, markdown


def assert_monitor_only_with_adapter_next_action_materializes_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="ale_host_codex_e2e_validated",
            next_action=(
                "Continue after ALE host Codex e2e: package the ignored host-Codex "
                "adapter contract into a public-safe generic artifact, or select one "
                "local-material-ready ALE task for a concrete LoopX validation hypothesis."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": "[P2] Meta canary/readiness observation lane: keep release readiness observable.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "materialize_advancement_todo_or_blocker", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["monitor_todo_only", "next_action_requires_advancement"], lane
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", guard
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    assert guard["execution_obligation"]["contract_obligation"] == lane["obligation"], guard


def assert_executable_repeat_with_blocker_context_routes_to_advancement() -> None:
    repeat_todo = (
        "Run a fresh full treatment repeat under the validated retrieval-smoke "
        "path; the previous seed is support-blocked and does not unblock the "
        "scorer by itself, but if the repeat completes with real retrieval and "
        "evaluation rows plus a non-empty retrieval trace, rebuild scoring "
        "inputs and scorer validation; if it fails, write the concrete blocker."
    )
    assert normalize_todo_task_class(None, text=repeat_todo) == TODO_TASK_CLASS_ADVANCEMENT
    guard = build_quota_should_run(
        status_payload(
            status="side_bypass_retrieval_smoke_passed",
            next_action=(
                "Run a fresh full treatment repeat, then rebuild scoring inputs "
                "only if the repeat completes with real retrieval and evaluation rows."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": repeat_todo,
                    "role": "agent",
                    "status": "open",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard


def assert_monitor_todo_with_executable_next_action_materializes_advancement() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="side_bypass_retrieval_smoke_passed",
            next_action=(
                "Run a fresh full treatment repeat, then rebuild scoring inputs "
                "only if the repeat completes with real retrieval and evaluation rows."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": (
                        "Blocked on owner evidence for the scorer-valid next "
                        "treatment source; the previous seed is support-blocked "
                        "and does not unblock this todo."
                    ),
                    "role": "agent",
                    "status": "open",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "materialize_advancement_todo_or_blocker", lane
    assert lane["reason_codes"] == ["monitor_todo_only", "next_action_requires_advancement"], lane
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "continuous_monitor", guard


def assert_structured_todo_lane_registration_beats_text_fallback() -> None:
    blocked_like_todo = (
        "[P0] Blocked on owner evidence for the selected runner source; when "
        "the source is selected, run the benchmark case and write back either "
        "validated results or the concrete blocker."
    )
    assert normalize_todo_task_class(None, text=blocked_like_todo) == TODO_TASK_CLASS_MONITOR
    assert (
        normalize_todo_task_class(
            TODO_TASK_CLASS_ADVANCEMENT,
            text=blocked_like_todo,
            action_kind="run_eval",
        )
        == TODO_TASK_CLASS_ADVANCEMENT
    )
    guard = build_quota_should_run(
        status_payload(
            status="structured_lane_registration_ready",
            next_action="Run the registered benchmark case and write back a result or blocker.",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": blocked_like_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "action_kind": "run_eval",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard
    assert first_items[0]["action_kind"] == "run_eval", guard


def assert_structured_monitor_registration_beats_action_text() -> None:
    guard = build_quota_should_run(
        status_payload(
            status="structured_monitor_registration_waiting",
            next_action="Observe the external evidence channel until a material transition is recorded.",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "Run the remote evaluator only after owner evidence arrives.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                    "task_class": "continuous_monitor",
                    "action_kind": "monitor",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["should_run"] is False, guard
    assert lane["lane"] == "continuous_monitor", lane
    assert lane["obligation"] == "quiet_until_material_monitor_transition", lane
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == TODO_TASK_CLASS_MONITOR, guard
    assert first_items[0]["action_kind"] == "monitor", guard


def assert_mixed_monitor_and_advancement_routes_to_advancement() -> None:
    executable_todo = "[P1] Add the typed task class routing smoke fixture."
    guard = build_quota_should_run(
        status_payload(
            status="typed_task_lane_planning_writeback",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": "[P2] Side-bypass dependency monitor: observe public-safe replay state transitions only.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                },
                {
                    "index": 2,
                    "text": executable_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["next_lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["must_attempt_work"] is True, lane
    assert guard["recommended_action"] == executable_todo, guard
    assert guard["interaction_contract"]["agent_channel"]["primary_action"] == executable_todo, guard
    assert f"agent_action={executable_todo}" in guard["protocol_action_packet"]["summary"], guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert [item["task_class"] for item in first_items] == ["advancement_task", "continuous_monitor"], guard


def assert_lower_priority_executable_before_higher_priority_is_reordered() -> None:
    p2_todo = "[P2] Fold server scheduling into the longer-term roadmap."
    p1_todo = "[P1] Fix first-screen dashboard acceptance before roadmap cleanup."
    guard = build_quota_should_run(
        status_payload(
            status="todo_priority_projection_fixture",
            agent_todo_items=[
                {
                    "index": 1,
                    "text": p2_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                    "task_class": "advancement_task",
                },
                {
                    "index": 2,
                    "text": p1_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                    "task_class": "advancement_task",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    assert guard["decision"] == "run", guard
    assert guard["recommended_action"] == p1_todo, guard
    assert guard["interaction_contract"]["agent_channel"]["primary_action"] == p1_todo, guard
    executable_items = guard["agent_todo_summary"]["first_executable_items"]
    assert [item["priority"] for item in executable_items[:2]] == ["P1", "P2"], guard


def assert_external_monitor_context_recommends_executable_backlog() -> None:
    poll_action = (
        "Agent: continue compact-polling Terminal-Bench train-fasttext until a "
        "terminal compact result/trial reward appears."
    )
    executable_todo = (
        "[P1] Behavior regression suite lane: maintain `regression/` as the "
        "home for LoopX CLI plus real Codex CLI interaction regressions."
    )
    guard = build_quota_should_run(
        status_payload(
            status="benchmark_ledger_running_placeholder_guard",
            next_action=poll_action,
            agent_todo_items=[
                {
                    "index": 67,
                    "text": (
                        "[P0] [P0 monitor] Observe no-upload Terminal-Bench "
                        "train-fasttext using compact process/result markers only."
                    ),
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "continuous_monitor",
                    "action_kind": "monitor",
                },
                {
                    "index": 2,
                    "text": executable_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                    "task_class": "advancement_task",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo", "external_monitor_context"], lane
    assert guard["recommended_action"] == executable_todo, guard
    assert poll_action != guard["recommended_action"], guard
    assert guard["interaction_contract"]["agent_channel"]["primary_action"] == (
        "[P1] Behavior regression suite lane"
    ), guard
    packet = guard["protocol_action_packet"]["summary"]
    assert "lane=advancement_task" in packet, packet
    assert "agent_action=[P1] Behavior regression suite lane" in packet, packet


def assert_benchmark_readiness_scan_routes_to_advancement() -> None:
    readiness_scan_todo = (
        "[P1] Follow-up benchmark readiness scans while SWE-Marathon is blocked "
        "on local capacity and if the remote GPU route is blocked: AgentIssue-Bench "
        "first, then PerfBench, then SWE-Bench Pro public. Optimize for low "
        "frontier-agent success plus local/Docker reproducibility, objective scoring, "
        "Codex CLI wrapper feasibility, and compact `benchmark_run_v0` / "
        "`benchmark_result_v0` evidence. Do not spend a fresh benchmark execution "
        "quota slot until a setup-readiness scan proves a plausible learning run."
    )
    guard = build_quota_should_run(
        status_payload(
            status="remote_gpu_route_b_runner_plumbing_ready",
            next_action=(
                "Resume benchmark-candidate readiness scanning, starting with "
                "AgentIssue-Bench unless the owner pivots back to an existing route."
            ),
            user_todo_items=[
                {
                    "index": 1,
                    "text": "[P1] Optional local runtime cleanup only if returning to SWE-Marathon.",
                    "role": "user",
                    "status": "open",
                    "priority": "P1",
                }
            ],
            agent_todo_items=[
                {
                    "index": 1,
                    "text": readiness_scan_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert guard["heartbeat_recommendation"]["recommended_mode"] == "steering_audit_then_one_step", guard
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard


def assert_benchmark_source_preflight_routes_to_advancement() -> None:
    source_preflight_todo = (
        "[P2] Run a sparse no-task TheAgentCompany source preflight unless the "
        "owner first approves a gated route. Exclude `workspaces/tasks`, task "
        "instructions, evaluators, checkpoints, scenarios, setup-script execution, "
        "Docker image pulls/runs, credential-bearing LLM config, trajectories, "
        "screenshots, uploads, leaderboard, submit, hidden refs, and shared-host "
        "workload inspection. The preflight should answer only whether a "
        "Codex-compatible runner wrapper can be designed from public harness code "
        "and docs without consuming task material."
    )
    assert normalize_todo_task_class(None, text=source_preflight_todo) == TODO_TASK_CLASS_ADVANCEMENT
    guard = build_quota_should_run(
        status_payload(
            status="theagentcompany_setup_readiness_ready_env_gate",
            next_action=(
                "TheAgentCompany is setup-readiness ready but environment and "
                "credential gated; next bounded step is a sparse no-task source "
                "preflight unless the owner approves Docker service setup."
            ),
            user_todo_items=[
                {
                    "index": 1,
                    "text": "[P1] Approve TheAgentCompany Docker service setup before a real run.",
                    "role": "user",
                    "status": "open",
                    "priority": "P1",
                }
            ],
            agent_todo_items=[
                {
                    "index": 1,
                    "text": source_preflight_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P2",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard


def assert_behavior_regression_suite_routes_to_advancement() -> None:
    regression_todo = (
        "[P1] Behavior regression suite lane: maintain `regression/` as the "
        "home for LoopX CLI plus real Codex CLI interaction regressions. "
        "Add focused cases when a control-plane behavior previously failed or "
        "could strand automation, especially external-evidence waits, "
        "P0-blocked/P1-P2 fallback, no-progress self-repair, compact blocker "
        "writeback, and Codex credential boundary expectations on shared or "
        "remote machines."
    )
    assert normalize_todo_task_class(None, text=regression_todo) == TODO_TASK_CLASS_ADVANCEMENT
    guard = build_quota_should_run(
        status_payload(
            status="regression_suite_lane_only",
            next_action=(
                "Continue the behavior regression suite lane by adding one focused "
                "LoopX CLI plus Codex CLI interaction regression."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": regression_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["must_attempt_work"] is True, lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert guard["execution_obligation"]["must_attempt_work"] is True, guard
    assert guard["interaction_contract"]["agent_channel"]["quiet_noop_allowed"] is False, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard


def assert_launched_external_observation_does_not_preempt_advancement_backlog() -> None:
    observe_todo = (
        "[P0] Observe launched private no-upload paired pilot for terminal-bench@2.0 / "
        "git-multibranch (run_basename=terminal-bench-git-multibranch-paired-fixture; "
        "baseline pid=111; treatment pid=222): poll compact Harbor materialization "
        "only, inspect case execution status via compact result/blocker markers, and "
        "when both arms close run verifier-attribution review before any repeat or claim."
    )
    backlog_todo = (
        "[P1] Re-rank follow-on benchmark lanes after the first Terminal-Bench paired "
        "pilot or a documented Terminal-Bench blocker."
    )
    guard = build_quota_should_run(
        status_payload(
            status="terminal_bench_git_multibranch_paired_launch_observation_v0",
            next_action=(
                "Observe launched private no-upload terminal-bench@2.0/git-multibranch "
                "paired pilot run_basename=terminal-bench-git-multibranch-paired-fixture "
                "via compact Harbor materialization/process state only; when both arms "
                "close, ingest compact result/blocker and run verifier-attribution review "
                "before any repeat or claim."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": observe_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "continuous_monitor",
                    "action_kind": "terminal_bench_case_observation",
                },
                {
                    "index": 2,
                    "text": backlog_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                    "task_class": "advancement_task",
                    "action_kind": "planning_refresh",
                },
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    assert guard["actionable_by_codex"] is True, guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["reason_codes"] == [
        "open_agent_todo",
        "external_monitor_context",
    ], lane
    assert "external_evidence_observation" not in guard, guard
    interaction = guard["interaction_contract"]
    assert interaction["mode"] == "bounded_delivery", interaction
    assert interaction["agent_channel"]["must_attempt"] is True, interaction
    assert "Re-rank follow-on benchmark lanes" in interaction["agent_channel"]["primary_action"], interaction


def assert_launch_then_poll_todo_without_handle_routes_to_advancement() -> None:
    launch_repeat_todo = (
        "[P0] Launch a private no-upload paired repeat for terminal-bench@2.0 / "
        "large-scale-text-editing with agent_setup_timeout_multiplier=4 on both "
        "codex-goal-mode baseline and loopx treatment; poll only compact "
        "materialization/result summaries, then ingest and compare before any claim."
    )
    guard = build_quota_should_run(
        status_payload(
            status="terminal_bench_large_scale_repeat_handle_absent_v0",
            next_action=(
                "No observable public launch summary or compact writeback channel "
                "exists yet for the planned paired repeat; launch the private "
                "no-upload repeat before further polling."
            ),
            agent_todo_items=[
                {
                    "index": 1,
                    "text": launch_repeat_todo,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "action_kind": "run_eval",
                }
            ],
        ),
        goal_id=GOAL_ID,
    )
    lane = guard["work_lane_contract"]
    assert guard["decision"] == "run", guard
    assert guard["should_run"] is True, guard
    assert guard["effective_action"] == "normal_run", guard
    assert lane["lane"] == "advancement_task", lane
    assert lane["obligation"] == "advance_one_bounded_segment", lane
    assert lane["reason_codes"] == ["open_agent_todo"], lane
    assert "external_evidence_observation" not in guard, guard
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert first_items[0]["task_class"] == "advancement_task", guard
    assert first_items[0]["action_kind"] == "run_eval", guard


def assert_side_agent_next_action_projects_without_stealing_goal_next_action() -> None:
    primary_action = "[P0] Run the primary benchmark monitor owned by main control."
    side_action = (
        "[P0] Codex CLI TUI continuation: prove the same-open-TUI steering "
        "slice without adding temporary runtime packet fields."
    )
    guard = build_quota_should_run(
        status_payload(
            status="primary_goal_route_active",
            next_action=primary_action,
            coordination={
                "primary_agent": "codex-main-control",
                "registered_agents": ["codex-main-control", "codex-side-bypass"],
            },
            agent_todo_items=[
                {
                    "index": 1,
                    "text": primary_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-main-control",
                    "todo_id": "todo_primary",
                },
                {
                    "index": 2,
                    "text": side_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "action_kind": "codex_cli_tui_continuation",
                    "claimed_by": "codex-side-bypass",
                    "todo_id": "todo_side_tui",
                    "required_capabilities": ["shell", "filesystem_write"],
                },
                {
                    "index": 3,
                    "text": "[P1] Render the public showcase animation prototype.",
                    "role": "agent",
                    "status": "open",
                    "priority": "P1",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-side-bypass",
                    "todo_id": "todo_side_showcase",
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id="codex-side-bypass",
    )
    assert guard["recommended_action"] == side_action, guard
    assert guard["agent_identity"]["agent_id"] == "codex-side-bypass", guard
    next_action = guard["agent_lane_next_action"]
    assert next_action["schema_version"] == "agent_lane_next_action_v0", next_action
    assert next_action["agent_id"] == "codex-side-bypass", next_action
    assert next_action["primary_agent"] == "codex-main-control", next_action
    assert next_action["todo_id"] == "todo_side_tui", next_action
    assert next_action["selected_by"] == "current_agent_claimed_todo", next_action
    assert next_action["confidence"] == "selected", next_action
    assert next_action["source"] == "capability_gate.runnable_candidates", next_action
    assert next_action["preserves_goal_next_action"] is True, next_action
    assert guard["capability_gate"]["runnable_candidates"][0]["todo_id"] == "todo_side_tui", guard
    markdown = render_quota_should_run_markdown(guard)
    assert "agent_lane_next_action: todo_id=todo_side_tui" in markdown, markdown
    assert side_action in markdown, markdown
    assert primary_action not in guard["agent_lane_next_action"]["text"], guard


def assert_agent_lane_next_action_prefers_capability_repair_candidate() -> None:
    ordinary_action = (
        "[P0] Run the already-launched full-suite polling lane and record compact results."
    )
    repair_action = (
        "[P0] Repair benchmark treatment product-path parity by building the "
        "benchmark_runner bridge itself before claiming uplift."
    )
    guard = build_quota_should_run(
        status_payload(
            status="target_capabilities_gate_merged",
            next_action=ordinary_action,
            coordination={
                "primary_agent": "codex-main-control",
                "registered_agents": ["codex-main-control"],
            },
            agent_todo_items=[
                {
                    "index": 1,
                    "text": ordinary_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-main-control",
                    "todo_id": "todo_full_suite",
                },
                {
                    "index": 2,
                    "text": repair_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-main-control",
                    "todo_id": "todo_bridge_repair",
                    "required_capabilities": ["shell"],
                    "target_capabilities": ["benchmark_runner"],
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    capability_gate = guard["capability_gate"]
    repair_candidates = [
        item
        for item in capability_gate["runnable_candidates"]
        if item.get("capability_repair_mode") is True
    ]
    assert [item["todo_id"] for item in repair_candidates] == ["todo_bridge_repair"], guard
    assert guard["recommended_action"] == repair_action, guard
    next_action = guard["agent_lane_next_action"]
    assert next_action["todo_id"] == "todo_bridge_repair", guard
    assert next_action["source"] == "capability_gate.runnable_candidates", next_action
    assert next_action["selected_by"] == "current_agent_claimed_todo", next_action
    assert next_action["capability_repair_mode"] is True, next_action
    assert next_action["missing_target_capabilities"] == ["benchmark_runner"], next_action
    markdown = render_quota_should_run_markdown(guard)
    assert "agent_lane_next_action: todo_id=todo_bridge_repair" in markdown, markdown


def assert_agent_lane_next_action_prefers_explicit_next_action_todo_id() -> None:
    ordinary_action = (
        "[P0] Run SWE-Marathon full-suite polling and record compact results."
    )
    parity_action = (
        "[P0] Repair benchmark treatment product-path parity before claiming uplift."
    )
    guard = build_quota_should_run(
        status_payload(
            status="next_action_todo_id_projection",
            next_action=(
                "[P0] Continue todo_parity_slice: repair treatment parity before "
                "another full-suite polling slice."
            ),
            coordination={
                "primary_agent": "codex-main-control",
                "registered_agents": ["codex-main-control"],
            },
            agent_todo_items=[
                {
                    "index": 1,
                    "text": ordinary_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-main-control",
                    "todo_id": "todo_full_suite",
                    "required_capabilities": ["shell"],
                },
                {
                    "index": 2,
                    "text": parity_action,
                    "role": "agent",
                    "status": "open",
                    "priority": "P0",
                    "task_class": "advancement_task",
                    "claimed_by": "codex-main-control",
                    "todo_id": "todo_parity_slice",
                    "required_capabilities": ["shell"],
                },
            ],
        ),
        goal_id=GOAL_ID,
        agent_id="codex-main-control",
    )
    next_action = guard["agent_lane_next_action"]
    assert next_action["todo_id"] == "todo_parity_slice", guard
    assert next_action["selected_by"] == "active_next_action_todo", guard
    assert next_action["confidence"] == "selected", guard
    assert guard["recommended_action"] == parity_action, guard
    markdown = render_quota_should_run_markdown(guard)
    assert "agent_lane_next_action: todo_id=todo_parity_slice" in markdown, markdown


def main() -> int:
    assert_dependency_monitor_requires_advancement()
    assert_primary_status_stays_advancement_lane()
    assert_structured_surface_only_run_requires_outcome_followthrough()
    assert_contract_word_alone_does_not_trigger_outcome_followthrough()
    assert_monitor_only_todo_waits_quietly()
    assert_monitor_only_with_user_todo_surfaces_user_action_without_transition()
    assert_blocked_agent_todo_with_user_gate_notifies_without_execution()
    assert_monitor_only_with_planning_next_action_materializes_advancement()
    assert_monitor_only_with_adapter_next_action_materializes_advancement()
    assert_executable_repeat_with_blocker_context_routes_to_advancement()
    assert_monitor_todo_with_executable_next_action_materializes_advancement()
    assert_structured_todo_lane_registration_beats_text_fallback()
    assert_structured_monitor_registration_beats_action_text()
    assert_mixed_monitor_and_advancement_routes_to_advancement()
    assert_lower_priority_executable_before_higher_priority_is_reordered()
    assert_external_monitor_context_recommends_executable_backlog()
    assert_benchmark_readiness_scan_routes_to_advancement()
    assert_benchmark_source_preflight_routes_to_advancement()
    assert_behavior_regression_suite_routes_to_advancement()
    assert_launched_external_observation_does_not_preempt_advancement_backlog()
    assert_launch_then_poll_todo_without_handle_routes_to_advancement()
    assert_side_agent_next_action_projects_without_stealing_goal_next_action()
    assert_agent_lane_next_action_prefers_capability_repair_candidate()
    assert_agent_lane_next_action_prefers_explicit_next_action_todo_id()
    print("work-lane-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
