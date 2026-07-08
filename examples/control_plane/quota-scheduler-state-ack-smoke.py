#!/usr/bin/env python3
"""Smoke-test CLI-owned scheduler RRULE ack state."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.testing.canary_harness import run_json_cli  # noqa: E402
from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_module  # noqa: E402
from loopx.control_plane.scheduler.scheduler_hint import (  # noqa: E402
    build_codex_app_scheduler_ack_event,
    build_scheduler_ack_plan,
    build_scheduler_hint,
)
from loopx.control_plane.scheduler.state import (  # noqa: E402
    SCHEDULER_STATE_SCHEMA_VERSION,
    load_scheduler_state,
    write_scheduler_state,
)
from loopx.quota import AgentScopeFrontierAction  # noqa: E402
from loopx.status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK  # noqa: E402


AGENT_SCOPE_ACTIONS = [action.value for action in AgentScopeFrontierAction]
FROZEN_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


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
            "mode": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "user_channel": {"action_required": False},
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
            "mode": "monitor_quiet_skip",
            "user_channel": {"action_required": False},
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
            "mode": "bounded_delivery",
            "user_channel": {"action_required": False},
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
) -> dict:
    original_now_utc = scheduler_hint_module.now_utc
    try:
        scheduler_hint_module.now_utc = lambda: now
        return build_scheduler_hint(
            deepcopy(payload),
            agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
            codex_app_scheduler_state=scheduler_state,
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


def assert_monitor_wait_progression_reaches_120() -> None:
    base = monitor_payload()
    first = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    assert first["action"] == "backoff_until_material_transition", first
    assert first["codex_app"]["example_progression_minutes"] == [15, 30, 60, 120], first
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

    fourth = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(third),
    )
    assert fourth["codex_app"]["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=120", fourth

    quiet = build_scheduler_hint(
        deepcopy(base),
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
        codex_app_scheduler_state=state_from(fourth),
    )
    assert quiet["codex_app"]["stateful_backoff"]["apply_needed"] is False, quiet
    assert quiet["codex_app"]["host_action"] == "none", quiet
    assert "recommended_rrule" not in quiet["codex_app"], quiet


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
    }, ack_hint
    assert ack_cli_args == [
        "quota",
        "scheduler-ack-current",
        "--goal-id",
        ack_args["goal_id"],
        "--agent-id",
        ack_args["agent_id"],
        "--surface",
        ack_args["surface"],
        "--state-key",
        ack_args["state_key"],
        "--applied-rrule",
        ack_args["applied_rrule"],
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


def assert_monitor_wait_stale_ack_hint_is_accepted() -> None:
    base = monitor_window_payload(minutes_until_due=119)
    first = build_hint_at(base, now=FROZEN_NOW)
    second = build_hint_at(base, now=FROZEN_NOW, scheduler_state=state_from(first))
    third = build_hint_at(base, now=FROZEN_NOW, scheduler_state=state_from(second))
    previous_state = state_from(third)

    stale_hint_source = build_hint_at(
        base,
        now=FROZEN_NOW,
        scheduler_state=previous_state,
    )
    stale_app = stale_hint_source["codex_app"]
    stale_ack_args = stale_app["ack_hint"]["args"]
    assert stale_hint_source["cadence_class"] == "monitor_wait", stale_hint_source
    assert stale_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=119", stale_hint_source

    current_hint = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=1),
        scheduler_state=previous_state,
    )
    current_app = current_hint["codex_app"]
    assert current_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=118", current_hint
    assert (
        current_app["stateful_backoff"]["reset_token"]
        == stale_ack_args["reset_token"]
    ), current_hint
    assert (
        current_app["stateful_backoff"]["identity_signature"]
        == stale_ack_args["identity_signature"]
    ), current_hint

    plan = build_scheduler_ack_plan(
        {"scheduler_hint": current_hint},
        agent_id=stale_ack_args["agent_id"],
        state_key=stale_ack_args["state_key"],
        applied_rrule=stale_ack_args["applied_rrule"],
        reset_token=stale_ack_args["reset_token"],
        identity_signature=stale_ack_args["identity_signature"],
    )
    assert plan == {
        "ok": True,
        "already_applied": False,
        "applied_rrule": "FREQ=MINUTELY;INTERVAL=119",
        "expected_rrule": "FREQ=MINUTELY;INTERVAL=118",
        "stale_hint_accepted": True,
        "stale_hint_tolerance_minutes": 2,
    }, plan

    event = build_codex_app_scheduler_ack_event(
        {"goal_id": "scheduler-state-ack-smoke", "scheduler_hint": current_hint},
        agent_id=stale_ack_args["agent_id"],
        applied_rrule=stale_ack_args["applied_rrule"],
        reset_token=stale_ack_args["reset_token"],
        identity_signature=stale_ack_args["identity_signature"],
    )
    ack_event = event["scheduler_ack_event"]
    assert ack_event["applied_rrule"] == "FREQ=MINUTELY;INTERVAL=119", event
    assert ack_event["expected_rrule"] == "FREQ=MINUTELY;INTERVAL=118", event
    assert ack_event["stale_hint_accepted"] is True, event
    assert (
        ack_event["scheduler_state"]["last_applied_rrule"]
        == "FREQ=MINUTELY;INTERVAL=119"
    ), event
    quiet_after_stale_ack = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=1),
        scheduler_state=ack_event["scheduler_state"],
    )
    quiet_app = quiet_after_stale_ack["codex_app"]
    assert quiet_app["stateful_backoff"]["apply_needed"] is False, quiet_after_stale_ack
    assert quiet_app["host_action"] == "none", quiet_after_stale_ack
    assert "recommended_rrule" not in quiet_app, quiet_after_stale_ack

    outside_state_tolerance = build_hint_at(
        base,
        now=FROZEN_NOW + timedelta(minutes=3),
        scheduler_state=ack_event["scheduler_state"],
    )
    outside_app = outside_state_tolerance["codex_app"]
    assert outside_app["recommended_rrule"] == "FREQ=MINUTELY;INTERVAL=116", (
        outside_state_tolerance
    )
    assert outside_app["stateful_backoff"]["apply_needed"] is True, (
        outside_state_tolerance
    )

    outside_tolerance = build_scheduler_ack_plan(
        {"scheduler_hint": current_hint},
        agent_id=stale_ack_args["agent_id"],
        state_key=stale_ack_args["state_key"],
        applied_rrule="FREQ=MINUTELY;INTERVAL=121",
        reset_token=stale_ack_args["reset_token"],
        identity_signature=stale_ack_args["identity_signature"],
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


def run_cli(root: Path, *args: str, registry_path: Path, runtime: Path, project: Path) -> dict:
    return run_json_cli(
        *args,
        "--scan-path",
        str(project),
        registry_path=registry_path,
        runtime_root=runtime,
        cwd=REPO_ROOT,
        include_returncode=False,
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
        assert first_ack_cli_args[:2] == ["quota", "scheduler-ack-current"], first
        assert "--reset-token" not in first_ack_cli_args, first
        assert "--identity-signature" not in first_ack_cli_args, first

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
        assert ack["after"] is None, ack
        assert ack["post_ack_contract"]["do_not_apply_successor_rrule_from_ack_response"] is True, ack

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
        assert second_app["recommended_rrule"] != first_rrule, second
        assert second_app["stateful_backoff"]["apply_needed"] is True, second

        current = second
        while current["scheduler_hint"]["codex_app"]["stateful_backoff"]["apply_needed"]:
            current_app = current["scheduler_hint"]["codex_app"]
            current_rrule = current_app["recommended_rrule"]
            current_ack_args = current_app["ack_hint"]["args"]
            current_ack_cli_args = current_app["ack_hint"]["cli_args"]
            assert current_ack_args["applied_rrule"] == current_rrule, current
            assert current_ack_args["reset_token"], current
            assert current_ack_args["identity_signature"], current
            assert "--reset-token" not in current_ack_cli_args, current
            assert "--identity-signature" not in current_ack_cli_args, current
            ack = run_cli(
                root,
                *current_ack_cli_args,
                registry_path=registry_path,
                runtime=runtime,
                project=project,
            )
            assert ack["ok"] is True, ack
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
    assert_monitor_wait_progression_reaches_120()
    assert_active_work_keeps_initial_cadence()
    assert_scheduler_ack_plan_validation()
    assert_monitor_wait_stale_ack_hint_is_accepted()
    assert_scheduler_state_scope_validation()
    assert_cli_scheduler_ack_progression()
    assert_cli_ignores_corrupt_scheduler_state()
    assert_cli_scheduler_ack_uses_should_run_lookback()
    print("quota-scheduler-state-ack-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
