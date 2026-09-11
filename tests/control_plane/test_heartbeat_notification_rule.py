"""Regression tests for the heartbeat notify/execution-obligation wording.

The short notification rule used to read "DONT_NOTIFY=quiet", which agents can
misread as "do nothing". The rule must qualify DONT_NOTIFY as an output-level
signal only and keep `execution_obligation.must_attempt_work` as the authority
for whether work must run. Compact wording must preserve the repair action,
not just diagnose a missing user action, without turning repair into a prompt.
"""

from __future__ import annotations

from loopx.control_plane.heartbeat.rules import (
    HEARTBEAT_NOTIFICATION_RULE_SHORT,
)
from loopx.control_plane.heartbeat.task_body import (
    render_brief_heartbeat_task_body,
    render_thin_heartbeat_task_body,
)
from loopx.control_plane.scheduler.execution_context import (
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
    quota_todo_summary,
)
from loopx.quota import build_quota_should_run


GOAL_ID = "heartbeat-notify-obligation-fixture"
AGENT_ID = "codex-notify-agent"


def test_short_rule_qualifies_dont_notify_as_output_only() -> None:
    rule = HEARTBEAT_NOTIFICATION_RULE_SHORT
    assert "DONT_NOTIFY" in rule
    assert "OUTPUT only" in rule
    # The old ambiguous mapping must be gone.
    assert "DONT_NOTIFY=quiet." not in rule
    assert "heartbeat_recommendation.agent_must_attempt" in rule
    assert "execution_obligation.must_attempt_work" in rule


def test_shared_rule_keeps_projection_repair_and_quiet_boundary() -> None:
    rule = HEARTBEAT_NOTIFICATION_RULE_SHORT
    assert "NOTIFY缺动作→具体user todo未投影" in rule
    assert "需修复LoopX状态投影" in rule
    assert "静默时内部修复" in rule


def test_rendered_task_bodies_keep_execution_obligation_authority() -> None:
    kwargs = dict(
        goal_id="fixture-goal",
        active_state="active",
        cli_preflight="",
        pr_review_pre_quota_command="",
        quota_guard_command="loopx quota should-run",
        quota_spend_command="",
        refresh_state_command="",
        progress_refresh_state_command="",
        material_queue_rule="",
        permission_rule="",
        cli_bin="loopx",
        agent_scope_instruction="",
        expanded_prompt_command="",
        compact_prompt_command="",
        brief_prompt_command="",
        thin_prompt_command="",
    )
    for renderer in (render_thin_heartbeat_task_body, render_brief_heartbeat_task_body):
        body = renderer(**kwargs)
        assert "heartbeat_recommendation.agent_must_attempt" in body
        assert "execution_obligation.must_attempt_work" in body
        assert "OUTPUT only" in body
        assert "需修复LoopX状态投影" in body
        assert "静默时内部修复" in body
        # A bare "DONT_NOTIFY=quiet" no-op mapping must never appear in the prompt.
        assert "DONT_NOTIFY=quiet." not in body


def test_heartbeat_recommendation_mirrors_execution_obligation_in_replan() -> None:
    obligation = {
        "schema_version": "autonomous_replan_obligation_v0",
        "required": True,
        "stall_threshold": 2,
        "trigger_count": 1,
        "triggers": [
            {
                "kind": "periodic_review_due",
                "source": "run_history",
                "agent_id": AGENT_ID,
            }
        ],
        "stop_condition": (
            "stop after one bounded replan slice writes back a concrete frontier delta"
        ),
    }
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Advance the current lane.",
        agent_todos=quota_todo_summary(
            [
                quota_todo_item(
                    todo_id="todo_advance",
                    index=1,
                    title="Advance the current lane.",
                    task_class="advancement_task",
                    claimed_by=AGENT_ID,
                )
            ]
        ),
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID],
        },
        project_asset_extra={"autonomous_replan_obligation": obligation},
    )
    guard = build_quota_should_run(
        payload,
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )
    assert guard["decision"] == "autonomous_replan_required"
    heartbeat = guard["heartbeat_recommendation"]
    obligation = guard["execution_obligation"]
    assert heartbeat.get("notify") == "NOTIFY"
    user_channel = (
        (guard.get("interaction_contract") or {}).get("user_channel") or {}
    )
    assert user_channel.get("notify") == "NOTIFY"
    assert heartbeat.get("agent_must_attempt") is True
    assert heartbeat["agent_must_attempt"] is bool(
        obligation.get("must_attempt_work")
    )
