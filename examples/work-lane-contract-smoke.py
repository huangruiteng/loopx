#!/usr/bin/env python3
"""Smoke-test monitor-vs-advancement lane projection in quota should-run."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from goal_harness.quota import build_quota_should_run, render_quota_should_run_markdown
from goal_harness.status import (
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
    return {
        "ok": True,
        "attention_queue": {
            "items": [item]
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


def assert_monitor_only_with_user_todo_stays_quiet_without_transition() -> None:
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
    assert interaction["mode"] == "user_todo_blocker_push", interaction
    assert interaction["user_channel"]["action_required"] is True, interaction
    assert interaction["agent_channel"]["must_attempt"] is False, interaction
    assert interaction["agent_channel"]["quiet_noop_allowed"] is False, interaction
    packet = guard["protocol_action_packet"]
    assert "actor=user" in packet["summary"], packet
    assert "user_action_required=true" in packet["summary"], packet
    assert "agent_action_required=false" in packet["summary"], packet
    assert "quiet_noop_allowed=false" in packet["summary"], packet
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
                "local-material-ready ALE task for a concrete Goal Harness validation hypothesis."
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
                    "text": "[P1] Add the typed task class routing smoke fixture.",
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
    first_items = guard["agent_todo_summary"]["first_open_items"]
    assert [item["task_class"] for item in first_items] == ["continuous_monitor", "advancement_task"], guard


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
        "home for Goal Harness CLI plus real Codex CLI interaction regressions. "
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
                "Goal Harness CLI plus Codex CLI interaction regression."
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


def main() -> int:
    assert_dependency_monitor_requires_advancement()
    assert_primary_status_stays_advancement_lane()
    assert_monitor_only_todo_waits_quietly()
    assert_monitor_only_with_user_todo_stays_quiet_without_transition()
    assert_blocked_agent_todo_with_user_gate_notifies_without_execution()
    assert_monitor_only_with_planning_next_action_materializes_advancement()
    assert_monitor_only_with_adapter_next_action_materializes_advancement()
    assert_executable_repeat_with_blocker_context_routes_to_advancement()
    assert_monitor_todo_with_executable_next_action_materializes_advancement()
    assert_structured_todo_lane_registration_beats_text_fallback()
    assert_structured_monitor_registration_beats_action_text()
    assert_mixed_monitor_and_advancement_routes_to_advancement()
    assert_benchmark_readiness_scan_routes_to_advancement()
    assert_benchmark_source_preflight_routes_to_advancement()
    assert_behavior_regression_suite_routes_to_advancement()
    print("work-lane-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
