#!/usr/bin/env python3
"""Smoke-test CLI-owned scheduler RRULE ack state."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.canary_harness import (  # noqa: E402
    run_json_cli,
    run_json_cli_result,
)
from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_module  # noqa: E402
from loopx.control_plane.scheduler.ack import (  # noqa: E402
    build_codex_app_scheduler_ack_event,
    build_scheduler_ack_plan,
)
from loopx.control_plane.scheduler.execution_context import (  # noqa: E402
    SchedulerRuntimeProfile,
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.scheduler.scheduler_hint import (  # noqa: E402
    build_scheduler_hint as _build_scheduler_hint,
)
from loopx.control_plane.scheduler.state import (  # noqa: E402
    SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
    SCHEDULER_STATE_SCHEMA_VERSION,
    load_scheduler_state,
    write_scheduler_state,
)
from loopx.control_plane.testing.quota_fixtures import (  # noqa: E402
    quota_status_payload,
    quota_todo_item,
)
from loopx.quota import AgentScopeFrontierAction, build_quota_should_run  # noqa: E402
from loopx.status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK  # noqa: E402


AGENT_SCOPE_ACTIONS = [action.value for action in AgentScopeFrontierAction]
FROZEN_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
APP_SCHEDULER_CONTEXT = scheduler_execution_context_for_runtime_profile(
    SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT
)


def build_scheduler_hint(payload: dict, **kwargs: object) -> dict:
    return _build_scheduler_hint(
        payload,
        scheduler_execution_context=APP_SCHEDULER_CONTEXT,
        **kwargs,
    )


def _load_quota_plan_fixture_module():
    module_path = REPO_ROOT / "examples" / "control_plane" / "quota_plan_fixtures.py"
    spec = importlib.util.spec_from_file_location("quota_plan_smoke_fixture", module_path)
    assert spec and spec.loader, module_path
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(*, recommended_action: str = "Wait for reassignment.") -> dict:
    return {
        "goal_id": "scheduler-state-ack-smoke",
        "agent_identity": {"agent_id": "codex-side-agent"},
        "should_run": False,
        "effective_action": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
        "recommended_action": recommended_action,
        "heartbeat_recommendation": {
            "recommended_mode": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "notify": "DONT_NOTIFY",
            "spend_policy": "no spend while waiting for reassignment",
        },
        "execution_obligation": {
            "must_attempt_work": False,
            "spend_policy": "do not spend",
        },
        "automation_liveness": {
            "automation_action": "",
            "spend_policy": "automation liveness spend policy",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "user_channel": {"action_required": False},
            "agent_channel": {
                "must_attempt": False,
                "delivery_allowed": False,
                "quiet_noop_allowed": True,
            },
        },
    }


def monitor_payload(*, recommended_action: str = "Wait for material monitor evidence.") -> dict:
    return {
        "goal_id": "scheduler-state-ack-smoke",
        "agent_identity": {"agent_id": "codex-side-agent"},
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "recommended_action": recommended_action,
        "heartbeat_recommendation": {
            "recommended_mode": "monitor_quiet_until_material_transition",
            "notify": "DONT_NOTIFY",
            "spend_policy": "no spend while the monitor target is unchanged",
        },
        "execution_obligation": {
            "must_attempt_work": False,
            "spend_policy": "do not spend",
        },
        "automation_liveness": {
            "automation_action": "keep_active_quiet",
            "spend_policy": "no quota spend for unchanged monitor-only polls",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "monitor_quiet_skip",
            "user_channel": {"action_required": False},
            "agent_channel": {
                "must_attempt": False,
                "delivery_allowed": False,
                "quiet_noop_allowed": True,
            },
        },
    }


def monitor_window_payload(*, minutes_until_due: int = 119) -> dict:
    due_at = FROZEN_NOW + timedelta(minutes=minutes_until_due)
    expires_at = FROZEN_NOW + timedelta(minutes=minutes_until_due + 60)
    payload = monitor_payload()
    payload["agent_todo_summary"] = {
        "current_agent_claimed_monitor_items": [
            {
                "todo_id": "todo_monitor_window_stale_ack",
                "priority": "P1",
                "task_class": "continuous_monitor",
                "target_key": "monitor-window-stale-ack",
                "cadence": "3m",
                "next_due_at": due_at.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
        ],
        "monitor_open_items": [],
    }
    return payload


def active_payload() -> dict:
    return {
        "goal_id": "scheduler-state-ack-smoke",
        "agent_identity": {"agent_id": "codex-side-agent"},
        "should_run": True,
        "effective_action": "normal_run",
        "recommended_action": "Run the active work cadence smoke.",
        "heartbeat_recommendation": {
            "recommended_mode": "run_first_read_only_map",
            "notify": "DONT_NOTIFY",
            "spend_policy": "spend once after validated writeback",
        },
        "execution_obligation": {
            "must_attempt_work": True,
            "spend_policy": "spend after validation",
        },
        "automation_liveness": {
            "automation_action": "execute_bounded_work",
            "spend_policy": "spend after validation",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "bounded_delivery",
            "user_channel": {"action_required": False},
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
            },
        },
    }


def state_from(hint: dict) -> dict:
    stateful = hint["codex_app"]["stateful_backoff"]
    return {
        "schema_version": SCHEDULER_STATE_SCHEMA_VERSION,
        "goal_id": "scheduler-state-ack-smoke",
        "agent_id": "codex-side-agent",
        "surface": "codex_app",
        "state_key": stateful["state_key"],
        "reset_token": stateful["reset_token"],
        "identity_signature": stateful["identity_signature"],
        "progression_index": stateful["progression_index"],
        "progression_minutes": hint["codex_app"]["example_progression_minutes"],
        "last_applied_rrule": hint["codex_app"]["recommended_rrule"],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def state_from_hint_with_applied_rrule(hint: dict, *, index: int, rrule: str) -> dict:
    state = state_from(hint)
    state["progression_index"] = index
    state["last_applied_rrule"] = rrule
    return state


def build_hint_at(
    payload: dict,
    *,
    now: datetime,
    scheduler_state: dict | None = None,
    codex_app_current_rrule: str | None = None,
) -> dict:
    original_now_utc = scheduler_hint_module.now_utc
    try:
        scheduler_hint_module.now_utc = lambda: now
        return build_scheduler_hint(
            deepcopy(payload),
            agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
            codex_app_scheduler_state=scheduler_state,
            codex_app_current_rrule=codex_app_current_rrule,
        )
    finally:
        scheduler_hint_module.now_utc = original_now_utc


def assert_policy_state_progression() -> None:
    base = payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    first_backoff = first["codex_app"]["stateful_backoff"]
    assert first["action"] == "backoff_until_reassigned", first
    assert first["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=10", first
    assert first_backoff["apply_needed"] is True, first
    assert first_backoff["state_status"] == "missing", first

    second = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(first),
    )
    assert second["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=20", second
    assert second["codex_app"]["stateful_backoff"]["progression_index"] == 1, second
    assert second["codex_app"]["stateful_backoff"]["state_status"] == "same_identity", second

    third = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(second),
    )
    assert third["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", third

    fourth = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(third),
    )
    assert fourth["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60", fourth

    quiet = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(fourth),
    )
    assert quiet["codex_app"]["stateful_backoff"]["apply_needed"] is False, quiet
    assert quiet["codex_app"]["host_action"] == "none", quiet
    assert quiet["codex_app"]["rrule_source"] is None, quiet
    assert "recommended_rrule" not in quiet["codex_app"], quiet

    reset = build_scheduler_hint(
        payload(recommended_action="A new reassignment candidate appeared."),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(fourth),
    )
    assert reset["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=10", reset
    assert reset["codex_app"]["stateful_backoff"]["state_status"] == "reset_required", reset


def assert_monitor_wait_progression_caps_at_60() -> None:
    base = monitor_payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    assert first["action"] == "backoff_until_material_transition", first
    assert first["codex_app"]["example_progression_minutes"] == [15, 30, 60], first
    assert first["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=15", first

    second = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(first),
    )
    assert second["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", second

    third = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(second),
    )
    assert third["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=60", third

    steady = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(third),
    )
    assert steady["codex_app"]["stateful_backoff"]["apply_needed"] is False, steady
    assert steady["codex_app"]["stateful_backoff"]["current_rrule"] == "FREQ=MINUTELY;INTERVAL=60", steady
    assert steady["codex_app"]["host_action"] == "none", steady
    assert "recommended_rrule" not in steady["codex_app"], steady


def assert_monitor_wait_ignores_goal_recommended_action_identity_noise() -> None:
    first_payload = monitor_window_payload(minutes_until_due=119)
    first_payload["recommended_action"] = (
        "Monitor another agent's post-merge run until material evidence appears."
    )
    first = build_hint_at(first_payload, now=FROZEN_NOW)
    first_backoff = first["codex_app"]["stateful_backoff"]
    assert first["cadence_class"] == "monitor_wait", first
    assert first["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=15", first
    assert "recommended_action" not in first["unchanged_identity_keys"], first

    second_payload = monitor_window_payload(minutes_until_due=119)
    second_payload["recommended_action"] = (
        "Goal-level controller text changed, but the monitor target is unchanged."
    )
    second = build_hint_at(
        second_payload,
        now=FROZEN_NOW,
        scheduler_state=state_from(first),
    )
    second_backoff = second["codex_app"]["stateful_backoff"]
    assert second_backoff["state_status"] == "same_identity", second
    assert second["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", second
    assert second_backoff["identity_signature"] == first_backoff["identity_signature"], second
    assert second_backoff["reset_token"] == first_backoff["reset_token"], second
    assert "recommended_action" not in second["unchanged_identity_keys"], second


def assert_active_work_keeps_initial_cadence() -> None:
    base = active_payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    assert first["action"] == "run_now", first
    assert first["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=3", first
    assert "same_identity_action" not in first["codex_app"]["stateful_backoff"], first
    first_detailed = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        include_detail=True,
    )
    assert (
        first_detailed["cold_path_detail"]["stateful_backoff_detail"]["same_identity_action"]
        == "keep_initial_interval_while_active_work"
    ), first_detailed

    stale_backoff_state = state_from_hint_with_applied_rrule(
        first,
        index=1,
        rrule="FREQ=MINUTELY;INTERVAL=6",
    )
    repaired = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=stale_backoff_state,
    )
    assert repaired["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=3", repaired
    assert repaired["codex_app"]["stateful_backoff"]["progression_index"] == 0, repaired
    assert repaired["codex_app"]["stateful_backoff"]["state_status"] == "same_identity", repaired
    assert repaired["codex_app"]["stateful_backoff"]["apply_needed"] is True, repaired

    steady = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(repaired),
    )
    assert steady["codex_app"]["stateful_backoff"]["current_rrule"] == "FREQ=MINUTELY;INTERVAL=3", steady
    assert steady["codex_app"]["stateful_backoff"]["progression_index"] == 0, steady
    assert steady["codex_app"]["stateful_backoff"]["apply_needed"] is False, steady
    assert "recommended_rrule" not in steady["codex_app"], steady


def assert_scheduler_ack_plan_validation() -> None:
    base = active_payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    codex_app = first["codex_app"]
    backoff = codex_app["stateful_backoff"]
    ack_hint = codex_app["ack_hint"]
    ack_args = ack_hint["args"]
    ack_cli_args = ack_hint["cli_args"]
    assert ack_hint["schema_version"] == "codex_app_scheduler_ack_hint_v0", ack_hint
    assert ack_hint["after"] == "automation_update_rrule_success", ack_hint
    assert ack_hint["command"] == "quota scheduler-ack-current", ack_hint
    assert ack_hint["execute"] is True, ack_hint
    assert ack_hint["no_spend"] is True, ack_hint
    assert ack_hint["uses_current_hint"] is True, ack_hint
    assert ack_args == {
        "goal_id": "scheduler-state-ack-smoke",
        "agent_id": "codex-side-agent",
        "surface": "codex_app",
        "state_key": backoff["state_key"],
        "applied_rrule": codex_app["recommended_rrule"],
        "reset_token": backoff["reset_token"],
        "identity_signature": backoff["identity_signature"],
        "host_match_observed": True,
    }, ack_hint
    assert ack_cli_args == [
        "quota",
        "scheduler-ack-current",
        "--goal-id",
        ack_args["goal_id"],
        "--agent-id",
        ack_args["agent_id"],
        "-A",
        "--applied-rrule",
        ack_args["applied_rrule"],
        "--host-match-observed",
        "--reset-token",
        ack_args["reset_token"],
        "--identity-signature",
        ack_args["identity_signature"],
        "--execute",
    ], ack_hint
    with_capabilities = active_payload()
    with_capabilities["capability_gate"] = {
        "available": ["shell", "network", "benchmark_runner"],
    }
    capability_hint = build_scheduler_hint(
        with_capabilities,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    capability_ack_hint = capability_hint["codex_app"]["ack_hint"]
    capability_ack_args = capability_ack_hint["args"]
    capability_cli_args = capability_ack_hint["cli_args"]
    assert capability_ack_args["available_capabilities"] == [
        "network",
        "benchmark_runner",
    ], capability_ack_hint
    assert capability_cli_args.count("--available-capability") == 2, capability_ack_hint
    for capability in capability_ack_args["available_capabilities"]:
        capability_index = capability_cli_args.index(capability)
        assert capability_cli_args[capability_index - 1] == "--available-capability", (
            capability,
            capability_ack_hint,
        )
    plan = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id=ack_args["agent_id"],
        state_key=ack_args["state_key"],
        applied_rrule=ack_args["applied_rrule"],
        reset_token=ack_args["reset_token"],
        identity_signature=ack_args["identity_signature"],
    )
    assert plan == {
        "ok": True,
        "already_applied": False,
        "applied_rrule": codex_app["recommended_rrule"],
        "expected_rrule": codex_app["recommended_rrule"],
    }, plan

    missing_agent = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id=None,
        state_key=backoff["state_key"],
        applied_rrule=codex_app["recommended_rrule"],
    )
    assert missing_agent["ok"] is False, missing_agent
    assert "--agent-id" in missing_agent["reason"], missing_agent

    wrong_state_key = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id="codex-side-agent",
        state_key="wrong.state.key",
        applied_rrule=codex_app["recommended_rrule"],
    )
    assert wrong_state_key["ok"] is False, wrong_state_key
    assert "--state-key" in wrong_state_key["reason"], wrong_state_key

    wrong_reset_token = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id="codex-side-agent",
        state_key=backoff["state_key"],
        applied_rrule=codex_app["recommended_rrule"],
        reset_token="wrong-reset-token",
    )
    assert wrong_reset_token["ok"] is False, wrong_reset_token
    assert "--reset-token" in wrong_reset_token["reason"], wrong_reset_token

    wrong_identity = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id="codex-side-agent",
        state_key=backoff["state_key"],
        applied_rrule=codex_app["recommended_rrule"],
        identity_signature="wrong-identity",
    )
    assert wrong_identity["ok"] is False, wrong_identity
    assert "--identity-signature" in wrong_identity["reason"], wrong_identity

    missing_rrule = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id="codex-side-agent",
        state_key=backoff["state_key"],
    )
    assert missing_rrule["ok"] is False, missing_rrule
    assert "--applied-rrule" in missing_rrule["reason"], missing_rrule

    wrong_rrule = build_scheduler_ack_plan(
        {"scheduler_hint": first},
        agent_id="codex-side-agent",
        state_key=backoff["state_key"],
        applied_rrule="FREQ=MINUTELY;INTERVAL=99",
    )
    assert wrong_rrule["ok"] is False, wrong_rrule
    assert "does not match expected" in wrong_rrule["reason"], wrong_rrule

    steady = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(first),
    )
    steady_backoff = steady["codex_app"]["stateful_backoff"]
    already_applied = build_scheduler_ack_plan(
        {"scheduler_hint": steady},
        agent_id="codex-side-agent",
        state_key=steady_backoff["state_key"],
    )
    assert already_applied == {
        "ok": True,
        "already_applied": True,
        "applied_rrule": "",
    }, already_applied


def assert_normal_run_ack_preserves_runtime_capabilities() -> None:
    status = quota_status_payload(
        goal_id="scheduler-state-ack-runtime-capabilities",
        status="active",
        recommended_action="Run the bounded delivery.",
        next_action="Run the bounded delivery.",
        active_state_next_action="Run the bounded delivery.",
        agent_todo_items=[
            quota_todo_item(
                todo_id="todo_runtime_capabilities",
                title="Run the bounded delivery.",
                claimed_by="codex-side-agent",
            )
        ],
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": ["codex-side-agent"],
        },
        latest_runs=[],
    )
    decision = build_quota_should_run(
        status,
        goal_id="scheduler-state-ack-runtime-capabilities",
        agent_id="codex-side-agent",
        available_capabilities=["shell", "network", "lark_read"],
        scheduler_execution_context=APP_SCHEDULER_CONTEXT,
    )
    assert decision["effective_action"] == "normal_run", decision
    assert "capability_gate" not in decision, decision
    ack_hint = decision["scheduler_hint"]["codex_app"]["ack_hint"]
    assert ack_hint["args"]["available_capabilities"] == [
        "network",
        "lark_read",
    ], ack_hint
    cli_args = ack_hint["cli_args"]
    assert cli_args.count("--available-capability") == 2, ack_hint
    for capability in ("network", "lark_read"):
        capability_index = cli_args.index(capability)
        assert cli_args[capability_index - 1] == "--available-capability", ack_hint


def assert_monitor_wait_fixed_due_bucket_does_not_churn() -> None:
    base = monitor_window_payload(minutes_until_due=59)
    first = build_hint_at(base, now=FROZEN_NOW)
    second = build_hint_at(base, now=FROZEN_NOW, scheduler_state=state_from(first))
    applied_state = state_from(second)
    steady = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=1),
        scheduler_state=applied_state,
        codex_app_current_rrule="FREQ=MINUTELY;INTERVAL=30",
    )
    steady_app = steady["codex_app"]
    assert first["codex_app"]["example_progression_minutes"] == [15, 30], first
    assert second["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", second
    assert steady_app["example_progression_minutes"] == [15, 30], steady
    assert steady_app["stateful_backoff"]["current_rrule"] == (
        "FREQ=MINUTELY;INTERVAL=30"
    ), steady
    assert steady_app["stateful_backoff"]["apply_needed"] is False, steady
    assert steady_app["stateful_backoff"]["ack_needed"] is False, steady
    assert steady_app["host_action"] == "none", steady
    assert "recommended_rrule" not in steady_app, steady


def assert_monitor_wait_stale_ack_hint_is_accepted() -> None:
    base = monitor_window_payload(minutes_until_due=59)
    first = build_hint_at(base, now=FROZEN_NOW)
    current_hint = build_hint_at(
        base,
        now=FROZEN_NOW,
        scheduler_state=state_from(first),
    )
    current_app = current_hint["codex_app"]
    ack_args = current_app["ack_hint"]["args"]
    assert current_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", current_hint

    plan = build_scheduler_ack_plan(
        {"scheduler_hint": current_hint},
        agent_id=ack_args["agent_id"],
        state_key=ack_args["state_key"],
        applied_rrule="FREQ=MINUTELY;INTERVAL=31",
        reset_token=ack_args["reset_token"],
        identity_signature=ack_args["identity_signature"],
    )
    assert plan == {
        "ok": True,
        "already_applied": False,
        "applied_rrule": "FREQ=MINUTELY;INTERVAL=31",
        "expected_rrule": "FREQ=MINUTELY;INTERVAL=30",
        "stale_hint_accepted": True,
        "stale_hint_tolerance_minutes": 2,
    }, plan

    event = build_codex_app_scheduler_ack_event(
        {"goal_id": "scheduler-state-ack-smoke", "scheduler_hint": current_hint},
        agent_id=ack_args["agent_id"],
        applied_rrule="FREQ=MINUTELY;INTERVAL=31",
        reset_token=ack_args["reset_token"],
        identity_signature=ack_args["identity_signature"],
    )
    ack_event = event["scheduler_ack_event"]
    assert ack_event["applied_rrule"] == "FREQ=MINUTELY;INTERVAL=31", event
    assert ack_event["expected_rrule"] == "FREQ=MINUTELY;INTERVAL=30", event
    assert ack_event["stale_hint_accepted"] is True, event
    quiet_after_stale_ack = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=1),
        scheduler_state=ack_event["scheduler_state"],
    )
    quiet_app = quiet_after_stale_ack["codex_app"]
    assert quiet_app["stateful_backoff"]["apply_needed"] is False, quiet_after_stale_ack
    assert quiet_app["host_action"] == "none", quiet_after_stale_ack

    observed_stale_host = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=1),
        scheduler_state=ack_event["scheduler_state"],
        codex_app_current_rrule="FREQ=MINUTELY;INTERVAL=31",
    )
    observed_app = observed_stale_host["codex_app"]
    assert observed_app["stateful_backoff"]["apply_needed"] is True, observed_stale_host
    assert observed_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=30", observed_stale_host

    outside_tolerance = build_scheduler_ack_plan(
        {"scheduler_hint": current_hint},
        agent_id=ack_args["agent_id"],
        state_key=ack_args["state_key"],
        applied_rrule="FREQ=MINUTELY;INTERVAL=33",
        reset_token=ack_args["reset_token"],
        identity_signature=ack_args["identity_signature"],
    )
    assert outside_tolerance["ok"] is False, outside_tolerance
    assert "does not match expected" in outside_tolerance["reason"], outside_tolerance


def assert_scheduler_state_scope_validation() -> None:
    base = active_payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    valid_state = state_from(first)
    with tempfile.TemporaryDirectory(prefix="loopx-scheduler-state-scope-") as tmp:
        runtime = Path(tmp)
        state_path = write_scheduler_state(
            runtime,
            valid_state,
            goal_id="scheduler-state-ack-smoke",
            agent_id="codex-side-agent",
        )
        loaded = load_scheduler_state(
            runtime,
            goal_id="scheduler-state-ack-smoke",
            agent_id="codex-side-agent",
        )
        assert loaded == valid_state, loaded

        corrupt_state = dict(valid_state)
        corrupt_state["agent_id"] = "codex-other-agent"
        state_path.write_text(json.dumps(corrupt_state, sort_keys=True) + "\n", encoding="utf-8")
        assert (
            load_scheduler_state(
                runtime,
                goal_id="scheduler-state-ack-smoke",
                agent_id="codex-side-agent",
            )
            is None
        )

        try:
            write_scheduler_state(
                runtime,
                corrupt_state,
                goal_id="scheduler-state-ack-smoke",
                agent_id="codex-side-agent",
            )
        except ValueError as exc:
            assert "target scope or schema" in str(exc), exc
        else:
            raise AssertionError("write_scheduler_state accepted cross-agent scheduler state")


def bind_codex_app_quota_args(args: tuple[str, ...]) -> tuple[str, ...]:
    app_commands = {
        "should-run",
        "scheduler-ack",
        "scheduler-ack-current",
        "scheduler-fail-current",
    }
    if (
        len(args) >= 2
        and args[0] == "quota"
        and args[1] in app_commands
        and not {"-A", "--codex-app"}.intersection(args)
    ):
        return (*args, "--codex-app")
    return args


def run_cli(root: Path, *args: str, registry_path: Path, runtime: Path, project: Path) -> dict:
    return run_json_cli(
        *bind_codex_app_quota_args(args),
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime_root=runtime,
        cwd=REPO_ROOT,
        include_returncode=False,
    )


def run_cli_result(
    root: Path, *args: str, registry_path: Path, runtime: Path, project: Path
) -> tuple[int, dict]:
    return run_json_cli_result(
        *bind_codex_app_quota_args(args),
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime_root=runtime,
        cwd=REPO_ROOT,
    )


def assert_cli_scheduler_ack_progression() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-scheduler-ack-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        first = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        first_rrule = first["scheduler_hint"]["codex_app"]["recommended_rrule"]
        first_app = first["scheduler_hint"]["codex_app"]
        first_ack_args = first_app["ack_hint"]["args"]
        first_ack_cli_args = first_app["ack_hint"]["cli_args"]
        assert first_app["stateful_backoff"]["apply_needed"] is True, first
        assert first_ack_args["goal_id"] == "needs-operator", first
        assert first_ack_args["agent_id"] == agent_id, first
        assert first_ack_args["applied_rrule"] == first_rrule, first
        assert first_ack_args["reset_token"], first
        assert first_ack_args["identity_signature"], first
        assert first_ack_cli_args[:4] == [
            "--registry",
            str(registry_path.resolve()),
            "--runtime-root",
            str(runtime.resolve()),
        ], first
        assert first_ack_cli_args[4:6] == ["quota", "scheduler-ack-current"], first
        assert first_ack_args["host_match_observed"] is True, first
        assert "--host-match-observed" in first_ack_cli_args, first
        assert first_ack_args["reset_token"] in first_ack_cli_args, first
        assert first_ack_args["identity_signature"] in first_ack_cli_args, first

        current_hint_preview = run_cli(
            root,
            "quota",
            "scheduler-ack",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--applied-rrule",
            first_rrule,
            "--reset-token",
            "stale-reset-token",
            "--identity-signature",
            "stale-identity-signature",
            "--use-current-hint",
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert current_hint_preview["ok"] is True, current_hint_preview
        assert current_hint_preview["used_current_hint"] is True, current_hint_preview
        assert current_hint_preview["scheduler_state_mutated"] is False, current_hint_preview

        failure_returncode, current_hint_failure = run_cli_result(
            root,
            "quota",
            "scheduler-ack",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--state-key",
            "wrong.state.key",
            "--use-current-hint",
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert failure_returncode != 0, current_hint_failure
        assert current_hint_failure["ok"] is False, current_hint_failure
        assert current_hint_failure["used_current_hint"] is True, current_hint_failure
        assert (
            current_hint_failure["current_hint_source"]
            == "quota.should-run.scheduler_hint"
        ), current_hint_failure
        assert "--state-key" in current_hint_failure["reason"], current_hint_failure

        ack = run_cli(
            root,
            *first_ack_cli_args,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert ack["ok"] is True, ack
        assert ack["appended"] is False, ack
        assert ack["scheduler_state_mutated"] is True, ack
        assert ack["scheduler_ack_event"]["scheduler_state"]["last_applied_rrule"] == first_rrule, ack
        assert Path(ack["scheduler_state_path"]).exists(), ack
        assert ack["before"] == ack["scheduler_ack_event"]["before"], ack
        assert ack["before"]["spent_slots"] == 0, ack
        assert "scheduler_hint" not in ack["before"], ack
        assert ack["after"] is None, ack
        assert ack["post_ack_contract"]["do_not_apply_successor_rrule_from_ack_response"] is True, ack
        scheduler_state_path = Path(ack["scheduler_state_path"])

        second = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        second_app = second["scheduler_hint"]["codex_app"]
        assert second_app["stateful_backoff"]["state_status"] == "same_identity", second
        assert second_app["stateful_backoff"]["current_rrule"] == first_rrule, second
        assert second_app["stateful_backoff"]["apply_needed"] is False, second
        assert second_app["host_action"] == "none", second
        assert "recommended_rrule" not in second_app, second

        def age_applied_interval() -> None:
            persisted = json.loads(scheduler_state_path.read_text(encoding="utf-8"))
            persisted["updated_at"] = "2000-01-01T00:00:00+00:00"
            scheduler_state_path.write_text(
                json.dumps(persisted, sort_keys=True) + "\n",
                encoding="utf-8",
            )

        age_applied_interval()
        current = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert current["scheduler_hint"]["codex_app"]["recommended_rrule"] != first_rrule, current

        while current["scheduler_hint"]["codex_app"]["stateful_backoff"]["apply_needed"]:
            current_app = current["scheduler_hint"]["codex_app"]
            current_rrule = current_app["recommended_rrule"]
            current_ack_args = current_app["ack_hint"]["args"]
            current_ack_cli_args = current_app["ack_hint"]["cli_args"]
            assert current_ack_args["applied_rrule"] == current_rrule, current
            assert current_ack_args["reset_token"], current
            assert current_ack_args["identity_signature"], current
            assert current_ack_args["host_match_observed"] is True, current
            assert "--host-match-observed" in current_ack_cli_args, current
            assert current_ack_args["reset_token"] in current_ack_cli_args, current
            assert current_ack_args["identity_signature"] in current_ack_cli_args, current
            ack = run_cli(
                root,
                *current_ack_cli_args,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert ack["ok"] is True, ack
            settled = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            settled_app = settled["scheduler_hint"]["codex_app"]
            assert settled_app["stateful_backoff"]["current_rrule"] == current_rrule, settled
            assert settled_app["stateful_backoff"]["apply_needed"] is False, settled
            assert "recommended_rrule" not in settled_app, settled
            age_applied_interval()
            current = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )

        final_app = current["scheduler_hint"]["codex_app"]
        assert final_app["stateful_backoff"]["apply_needed"] is False, current
        assert final_app["host_action"] == "none", current
        assert "recommended_rrule" not in final_app, current


def assert_cli_scheduler_failure_circuit_breaker() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-scheduler-failure-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        codex_home = root / "codex-home"
        automation_path = codex_home / "automations" / "fixture" / "automation.toml"
        automation_path.parent.mkdir(parents=True)

        def write_host_rrule(rrule: str) -> None:
            automation_path.write_text(
                "\n".join(
                    [
                        "version = 1",
                        'id = "fixture"',
                        'kind = "heartbeat"',
                        'name = "Scheduler failure fixture"',
                        'prompt = "Advance `needs-operator` from active state. Agent: `codex-side-bypass`."',
                        'status = "ACTIVE"',
                        f'rrule = "{rrule}"',
                        'target_thread_id = "fixture-thread"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

        write_host_rrule("FREQ=MINUTELY;INTERVAL=3")
        previous_codex_home = os.environ.get("CODEX_HOME")
        previous_thread_id = os.environ.get("CODEX_THREAD_ID")
        os.environ["CODEX_HOME"] = str(codex_home)
        os.environ["CODEX_THREAD_ID"] = "fixture-thread"
        try:
            first = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            first_app = first["scheduler_hint"]["codex_app"]
            target_rrule = first_app["recommended_rrule"]
            failure_hint = first_app["failure_hint"]
            assert first_app["stateful_backoff"]["apply_needed"] is True, first
            assert first_app["no_spend_for_cadence_change"] is True, first
            assert failure_hint["route_binding"]["registry_bound"] is True, first

            failure = run_cli(
                root,
                *failure_hint["cli_args"],
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            persisted_failure = failure["scheduler_failure_event"]["scheduler_state"][
                "host_update_failure"
            ]
            assert failure["scheduler_state_mutated"] is True, failure
            assert persisted_failure["target_rrule"] == target_rrule, failure
            assert persisted_failure["observed_host_rrule"] == (
                "FREQ=MINUTELY;INTERVAL=3"
            ), failure

            suppressed = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            suppressed_app = suppressed["scheduler_hint"]["codex_app"]
            assert suppressed_app["stateful_backoff"]["apply_needed"] is False, suppressed
            assert suppressed_app["stateful_backoff"]["ack_needed"] is False, suppressed
            assert suppressed_app["no_spend_for_cadence_change"] is True, suppressed
            assert suppressed_app["stateful_backoff"]["state_status"] == (
                "host_update_failure_suppressed"
            ), suppressed
            assert suppressed_app["host_action_contract"] == (
                "skip_automation_update_for_recorded_host_failure"
            ), suppressed
            assert "recommended_rrule" not in suppressed_app, suppressed
            assert "failure_hint" not in suppressed_app, suppressed
            assert "ack_hint" not in suppressed_app, suppressed
            cooldown = suppressed["user_gate_notification_cooldown"]
            assert cooldown["notification_suppressed"] is True, suppressed
            assert cooldown["notification_due"] is False, suppressed
            assert cooldown["cooldown_minutes"] == 30, suppressed
            assert cooldown["reminder_window_minutes"] == 3, suppressed
            assert suppressed["action_required"] is False, suppressed
            assert suppressed["requires_user_action"] is False, suppressed
            assert suppressed["pending_user_action"] is True, suppressed
            assert suppressed["state"] == "operator_gate", suppressed
            assert suppressed["interaction_contract"]["mode"] == (
                "user_gate_cooldown_wait"
            ), suppressed
            assert suppressed["interaction_contract"]["user_channel"] == {
                "action_required": False,
                "notify": "DONT_NOTIFY",
                "reason": cooldown["reason"],
            }, suppressed
            assert suppressed["interaction_contract"]["agent_channel"][
                "quiet_noop_allowed"
            ] is True, suppressed

            reminder_state = load_scheduler_state(
                runtime,
                goal_id="needs-operator",
                agent_id=agent_id,
            )
            assert reminder_state is not None, suppressed
            reminder_state["host_update_failure"]["failed_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=31)
            ).isoformat()
            write_scheduler_state(
                runtime,
                reminder_state,
                goal_id="needs-operator",
                agent_id=agent_id,
            )
            reminder_due = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert reminder_due["user_gate_notification_cooldown"][
                "notification_due"
            ] is True, reminder_due
            assert reminder_due["action_required"] is True, reminder_due
            assert reminder_due["interaction_contract"]["mode"] == "user_gate", (
                reminder_due
            )
            assert reminder_due["interaction_contract"]["user_channel"][
                "notify"
            ] == "NOTIFY", reminder_due

            reminder_state["host_update_failure"]["failed_at"] = (
                datetime.now(timezone.utc) - timedelta(minutes=34)
            ).isoformat()
            write_scheduler_state(
                runtime,
                reminder_state,
                goal_id="needs-operator",
                agent_id=agent_id,
            )
            after_window = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert after_window["user_gate_notification_cooldown"][
                "notification_suppressed"
            ] is True, after_window
            assert after_window["interaction_contract"]["user_channel"][
                "notify"
            ] == "DONT_NOTIFY", after_window

            repeated_rc, repeated = run_cli_result(
                root,
                *failure_hint["cli_args"],
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert repeated_rc != 0, repeated
            assert repeated.get("scheduler_state_mutated") is not True, repeated

            write_host_rrule(target_rrule)
            host_matched = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            matched_app = host_matched["scheduler_hint"]["codex_app"]
            assert matched_app["stateful_backoff"]["apply_needed"] is False, host_matched
            assert matched_app["stateful_backoff"]["ack_needed"] is True, host_matched
            assert matched_app["ack_hint"]["after"] == "matching_host_rrule_observed", host_matched
            cleared = run_cli(
                root,
                *matched_app["ack_hint"]["cli_args"],
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert "host_update_failure" not in cleared["scheduler_ack_event"]["scheduler_state"], cleared
        finally:
            if previous_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = previous_codex_home
            if previous_thread_id is None:
                os.environ.pop("CODEX_THREAD_ID", None)
            else:
                os.environ["CODEX_THREAD_ID"] = previous_thread_id


def assert_cli_host_rrule_repairs_false_ack() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-host-rrule-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        first = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        ledger_only = first
        for _ in range(4):
            current_app = ledger_only["scheduler_hint"]["codex_app"]
            if current_app["stateful_backoff"]["apply_needed"] is False:
                break
            ack = run_cli(
                root,
                *current_app["ack_hint"]["cli_args"],
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert ack["scheduler_state_mutated"] is True, ack
            scheduler_state_path = Path(ack["scheduler_state_path"])
            persisted = json.loads(scheduler_state_path.read_text(encoding="utf-8"))
            persisted["updated_at"] = "2000-01-01T00:00:00+00:00"
            scheduler_state_path.write_text(
                json.dumps(persisted, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            ledger_only = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
        assert ledger_only["scheduler_hint"]["codex_app"]["stateful_backoff"]["apply_needed"] is False, ledger_only
        expected_rrule = ledger_only["scheduler_hint"]["codex_app"]["stateful_backoff"]["current_rrule"]

        codex_home = root / "codex-home"
        automation_path = codex_home / "automations" / "fixture" / "automation.toml"
        automation_path.parent.mkdir(parents=True)
        automation_path.write_text(
            "\n".join(
                [
                    "version = 1",
                    'id = "fixture"',
                    'kind = "heartbeat"',
                    'name = "Scheduler host observation fixture"',
                    'prompt = "Advance `needs-operator` from active state. Agent: `codex-side-bypass`"',
                    'status = "ACTIVE"',
                    'rrule = "FREQ=MINUTELY;INTERVAL=30"',
                    'target_thread_id = "fixture-thread"',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        previous_codex_home = os.environ.get("CODEX_HOME")
        previous_thread_id = os.environ.get("CODEX_THREAD_ID")
        os.environ["CODEX_HOME"] = str(codex_home)
        os.environ["CODEX_THREAD_ID"] = "fixture-thread"
        try:
            drift = run_cli(
                root,
                "quota",
                "should-run",
                "--goal-id",
                "needs-operator",
                "--agent-id",
                agent_id,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
        finally:
            if previous_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = previous_codex_home
            if previous_thread_id is None:
                os.environ.pop("CODEX_THREAD_ID", None)
            else:
                os.environ["CODEX_THREAD_ID"] = previous_thread_id
        drift_app = drift["scheduler_hint"]["codex_app"]
        assert drift_app["recommended_rrule"] == expected_rrule, drift
        assert drift_app["stateful_backoff"]["apply_needed"] is True, drift
        assert drift_app["stateful_backoff"]["host_observation"] == {
            "source": "quota_should_run_host_observation",
            "current_rrule": "FREQ=MINUTELY;INTERVAL=30",
            "status": "drift_detected",
        }, drift

        matched = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--codex-app-current-rrule",
            expected_rrule,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        matched_app = matched["scheduler_hint"]["codex_app"]
        assert matched_app["stateful_backoff"]["apply_needed"] is False, matched
        assert matched_app["stateful_backoff"]["host_observation"]["status"] == "matches_recommended", matched


def assert_cli_host_match_ack_after_ambiguous_update() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-host-match-ack-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        first = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        first_app = first["scheduler_hint"]["codex_app"]
        first_rrule = first_app["recommended_rrule"]
        assert first_app["stateful_backoff"]["apply_needed"] is True, first

        observed = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--codex-app-current-rrule",
            first_rrule,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        observed_app = observed["scheduler_hint"]["codex_app"]
        assert observed_app["stateful_backoff"]["apply_needed"] is False, observed
        assert observed_app["stateful_backoff"]["ack_needed"] is True, observed
        assert observed_app["ack_hint"]["after"] == "matching_host_rrule_observed", observed
        observed_ack_args = observed_app["ack_hint"]["args"]
        observed_ack_cli_args = observed_app["ack_hint"]["cli_args"]
        assert observed_ack_args["host_match_observed"] is True, observed
        assert "--host-match-observed" in observed_ack_cli_args, observed
        assert observed_ack_args["reset_token"] in observed_ack_cli_args, observed
        assert observed_ack_args["identity_signature"] in observed_ack_cli_args, observed
        assert observed_app["ack_hint"]["route_binding"]["registry_bound"] is True, observed

        ack = run_cli(
            root,
            *observed_app["ack_hint"]["cli_args"],
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        assert ack["ok"] is True, ack
        assert ack["scheduler_state_mutated"] is True, ack
        assert ack["host_match_ack"] is True, ack

        scheduler_state_path = Path(ack["scheduler_state_path"])
        persisted = json.loads(scheduler_state_path.read_text(encoding="utf-8"))
        historical_failure = {
            "schema_version": SCHEDULER_HOST_UPDATE_FAILURE_SCHEMA_VERSION,
            "target_rrule": "FREQ=MINUTELY;INTERVAL=3",
            "observed_host_rrule": first_rrule,
            "failure_kind": "timeout",
            "failure_count": 1,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        persisted["host_update_failures"] = [historical_failure]
        persisted["host_update_failure"] = historical_failure
        scheduler_state_path.write_text(
            json.dumps(persisted, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        settled = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--codex-app-current-rrule",
            first_rrule,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        settled_app = settled["scheduler_hint"]["codex_app"]
        assert settled_app["stateful_backoff"]["apply_needed"] is False, settled
        assert "recommended_rrule" not in settled_app, settled
        assert settled_app["stateful_backoff"]["host_observation"]["status"] == "matches_recommended", settled
        assert settled_app["stateful_backoff"]["host_update_failures"] == [
            historical_failure
        ], settled

        persisted = json.loads(scheduler_state_path.read_text(encoding="utf-8"))
        persisted["updated_at"] = "2000-01-01T00:00:00+00:00"
        scheduler_state_path.write_text(
            json.dumps(persisted, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        advanced = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--codex-app-current-rrule",
            first_rrule,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        advanced_app = advanced["scheduler_hint"]["codex_app"]
        assert advanced_app["stateful_backoff"]["apply_needed"] is True, advanced
        assert advanced_app["recommended_rrule"] != first_rrule, advanced
        assert advanced_app["host_action"] == "update_current_heartbeat_rrule", advanced
        assert advanced_app["stateful_backoff"]["host_update_failures"] == [
            historical_failure
        ], advanced


def assert_cli_ignores_corrupt_scheduler_state() -> None:
    fixture = _load_quota_plan_fixture_module()
    with tempfile.TemporaryDirectory(prefix="loopx-quota-scheduler-corrupt-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        agent_id = fixture.SCOPED_AGENT_ID
        first = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        first_rrule = first["scheduler_hint"]["codex_app"]["recommended_rrule"]
        ack = run_cli(
            root,
            "quota",
            "scheduler-ack",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            "--applied-rrule",
            first_rrule,
            "--execute",
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        state_path = Path(ack["scheduler_state_path"])
        persisted_state = json.loads(state_path.read_text(encoding="utf-8"))
        persisted_state["agent_id"] = "codex-other-agent"
        state_path.write_text(json.dumps(persisted_state, sort_keys=True) + "\n", encoding="utf-8")

        repaired = run_cli(
            root,
            "quota",
            "should-run",
            "--goal-id",
            "needs-operator",
            "--agent-id",
            agent_id,
            registry_path=registry_path,
            runtime=runtime,
            project=project,
        )
        app = repaired["scheduler_hint"]["codex_app"]
        assert app["recommended_rrule"] == first_rrule, repaired
        assert app["stateful_backoff"]["state_status"] == "missing", repaired
        assert app["stateful_backoff"]["apply_needed"] is True, repaired


def assert_cli_scheduler_ack_uses_should_run_lookback() -> None:
    from argparse import Namespace
    from loopx.cli_commands import quota as quota_command

    seen: dict[str, object] = {}

    def fake_collect_status(**kwargs):
        seen["limit"] = kwargs.get("limit")
        return {"ok": True, "runtime_root": str(REPO_ROOT)}

    def fake_record_quota_scheduler_ack(status_payload, **kwargs):
        seen["status_payload"] = status_payload
        seen["ack_kwargs"] = kwargs
        return {"ok": True, "mode": "scheduler-ack", "dry_run": True}

    def fake_print_payload(payload, output_format, renderer):
        seen["payload"] = payload
        seen["output_format"] = output_format
        seen["renderer"] = renderer

    args = Namespace(
        quota_command="scheduler-ack",
        goal_id="scheduler-state-ack-smoke",
        agent_id="codex-side-agent",
        available_capabilities=["shell", "network", "benchmark_runner"],
        include_scheduler_detail=False,
        runtime_profile=None,
        codex_app=True,
        host_surface=None,
        scheduler_owner=None,
        execution_mode=None,
        codex_app_current_rrule=None,
        slots=1,
        source="heartbeat",
        void_generated_at=None,
        reason_summary=None,
        todo_id=None,
        target_key=None,
        result_hash=None,
        material_change=False,
        cadence=None,
        next_due_at=None,
        next_agent_todo=None,
        next_user_todo=None,
        next_claimed_by=None,
        surface="codex_app",
        state_key="scheduler_hint.codex_app.stateful_backoff",
        applied_rrule="FREQ=MINUTELY;INTERVAL=10",
        reset_token="fixture-reset-token",
        identity_signature="fixture-identity-signature",
        host_match_observed=False,
        use_current_hint=False,
        dry_run=False,
        execute=False,
        scan_root=str(REPO_ROOT),
        scan_path=[],
        limit=5,
        format="json",
    )
    original_collect_status = quota_command.collect_status
    original_record_ack = quota_command.record_quota_scheduler_ack
    try:
        quota_command.collect_status = fake_collect_status
        quota_command.record_quota_scheduler_ack = fake_record_quota_scheduler_ack
        rc = quota_command.handle_quota_command(
            args,
            registry_path=REPO_ROOT / ".loopx" / "registry.json",
            runtime_root_arg=None,
            print_payload=fake_print_payload,
            append_cli_rollout_event=lambda **_: {},
        )
    finally:
        quota_command.collect_status = original_collect_status
        quota_command.record_quota_scheduler_ack = original_record_ack

    assert rc == 0, rc
    assert seen["limit"] == AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, seen
    assert seen["payload"] == {"ok": True, "mode": "scheduler-ack", "dry_run": True}, seen
    ack_kwargs = seen["ack_kwargs"]
    assert ack_kwargs["available_capabilities"] == [
        "shell",
        "network",
        "benchmark_runner",
    ], seen
    assert ack_kwargs["reset_token"] == "fixture-reset-token", seen
    assert ack_kwargs["identity_signature"] == "fixture-identity-signature", seen


def main() -> int:
    assert_policy_state_progression()
    assert_monitor_wait_progression_caps_at_60()
    assert_monitor_wait_ignores_goal_recommended_action_identity_noise()
    assert_active_work_keeps_initial_cadence()
    assert_scheduler_ack_plan_validation()
    assert_normal_run_ack_preserves_runtime_capabilities()
    assert_monitor_wait_fixed_due_bucket_does_not_churn()
    assert_monitor_wait_stale_ack_hint_is_accepted()
    assert_scheduler_state_scope_validation()
    assert_cli_scheduler_ack_progression()
    assert_cli_scheduler_failure_circuit_breaker()
    assert_cli_host_rrule_repairs_false_ack()
    assert_cli_host_match_ack_after_ambiguous_update()
    assert_cli_ignores_corrupt_scheduler_state()
    assert_cli_scheduler_ack_uses_should_run_lookback()
    print("quota-scheduler-state-ack-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
