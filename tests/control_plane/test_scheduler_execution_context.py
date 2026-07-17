from __future__ import annotations

from itertools import product

import pytest

from loopx.control_plane.scheduler.execution_context import (
    ExecutionMode,
    HostSurface,
    SchedulerRuntimeProfile,
    SchedulerOwner,
    resolve_scheduler_execution_context,
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint


VALID_COMBINATIONS = {
    ("codex_app", "host_automation", "hosted_automation"),
    ("local_scheduler", "host_automation", "hosted_automation"),
    *{
        (surface, owner, mode)
        for surface in ("codex_cli", "generic_cli", "claude_code")
        for owner, mode in (
            ("agent_cli_loop", "interactive"),
            ("agent_cli_loop", "isolated_headless"),
            ("outer_controller", "isolated_headless"),
            ("none", "interactive"),
        )
    },
}


def _active_payload() -> dict:
    return {
        "goal_id": "scheduler-context-fixture",
        "agent_identity": {"agent_id": "codex-fixture"},
        "should_run": True,
        "effective_action": "normal_run",
        "recommended_action": "Advance the public fixture.",
        "heartbeat_recommendation": {
            "recommended_mode": "normal_run",
            "spend_policy": "spend only after validated writeback",
        },
        "execution_obligation": {
            "must_attempt_work": True,
            "spend_policy": "spend only after validated writeback",
        },
        "automation_liveness": {
            "automation_action": "execute_bounded_work",
            "spend_policy": "spend only after validated writeback",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "normal_run",
            "user_channel": {"action_required": False, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
            },
            "cli_channel": {"next_cli_actions": [], "spend_allowed_now": False},
        },
    }


@pytest.mark.parametrize(
    ("host_surface", "scheduler_owner", "execution_mode"),
    list(product(HostSurface, SchedulerOwner, ExecutionMode)),
)
def test_scheduler_execution_context_decision_table(
    host_surface: HostSurface,
    scheduler_owner: SchedulerOwner,
    execution_mode: ExecutionMode,
) -> None:
    values = (
        host_surface.value,
        scheduler_owner.value,
        execution_mode.value,
    )
    context = {
        "host_surface": values[0],
        "scheduler_owner": values[1],
        "execution_mode": values[2],
    }

    resolution = resolve_scheduler_execution_context(context)
    hint = build_scheduler_hint(
        _active_payload(),
        scheduler_execution_context=context,
    )

    assert resolution.ok is (values in VALID_COMBINATIONS)
    if values not in VALID_COMBINATIONS:
        assert hint["execution_phase"]["disposition"] == "contract_error"
        assert hint["execution_phase"]["completed"] is False
        assert hint["codex_app"]["applicability"] == "blocked_invalid_context"
        return

    app_expected = values == (
        "codex_app",
        "host_automation",
        "hosted_automation",
    )
    assert hint["codex_app"]["applicability"] == (
        "applicable" if app_expected else "not_applicable"
    )
    assert ("stateful_backoff" in hint["codex_app"]) is app_expected
    if app_expected:
        assert "execution_context" not in hint
        assert "execution_phase" not in hint
    else:
        assert hint["execution_phase"]["apply_needed"] is False
        assert hint["execution_phase"]["completed"] is True


def test_partial_scheduler_context_fails_closed_without_app_action() -> None:
    hint = build_scheduler_hint(
        _active_payload(),
        scheduler_execution_context={"host_surface": "generic_cli"},
    )

    assert hint["action"] == "repair_scheduler_execution_context"
    assert hint["codex_app"]["applicability"] == "blocked_invalid_context"
    assert "stateful_backoff" not in hint["codex_app"]
    assert hint["execution_phase"]["apply_needed"] is False


def test_missing_scheduler_context_fails_closed() -> None:
    hint = build_scheduler_hint(_active_payload())

    assert hint["action"] == "repair_scheduler_execution_context"
    assert hint["execution_context"]["valid"] is False
    assert hint["codex_app"]["applicability"] == "blocked_invalid_context"
    assert hint["execution_phase"]["disposition"] == "contract_error"


def test_codex_app_runtime_profile_preserves_host_backoff() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT
    )
    hint = build_scheduler_hint(
        _active_payload(),
        include_detail=True,
        scheduler_execution_context=context,
    )

    assert "execution_context" not in hint
    assert "execution_phase" not in hint
    assert hint["cold_path_detail"]["execution_context"]["source"] == (
        "runtime_profile:codex_app_heartbeat"
    )
    assert (
        hint["cold_path_detail"]["execution_context"]["codex_app_applicability"]
        == "applicable"
    )
    assert hint["codex_app"]["stateful_backoff"]["apply_needed"] is True
    assert hint["cold_path_detail"]["execution_phase"]["apply_needed"] is True
