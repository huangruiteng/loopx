from __future__ import annotations

from itertools import product

import pytest

from loopx.control_plane.scheduler.execution_context import (
    ExecutionMode,
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    HostSurface,
    SchedulerOwner,
    SchedulerRuntimeProfile,
    render_scheduler_execution_args,
    resolve_scheduler_execution_context,
    scheduler_execution_context_for_runtime_profile,
    scheduler_runtime_profile_for_execution_context,
)
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.work_items.interaction_contract import (
    interaction_next_cli_actions,
)


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

FIRST_CLASS_RUNTIME_PROFILES = (
    (
        SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT,
        ("codex_app", "host_automation", "hosted_automation"),
        " --codex-app",
    ),
    (
        SchedulerRuntimeProfile.CODEX_CLI_VISIBLE,
        ("codex_cli", "agent_cli_loop", "interactive"),
        " --runtime-profile codex_cli",
    ),
    (
        SchedulerRuntimeProfile.CLAUDE_CODE_VISIBLE,
        ("claude_code", "agent_cli_loop", "interactive"),
        " --runtime-profile claude_code",
    ),
    (
        SchedulerRuntimeProfile.GENERIC_CLI_AGENT_LOOP,
        ("generic_cli", "agent_cli_loop", "interactive"),
        " --runtime-profile generic_cli",
    ),
    (
        SchedulerRuntimeProfile.GENERIC_CLI_OUTER_CONTROLLER,
        ("generic_cli", "outer_controller", "isolated_headless"),
        " --runtime-profile outer_controller",
    ),
)


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


@pytest.mark.parametrize(
    ("profile", "expected_context", "expected_args"),
    FIRST_CLASS_RUNTIME_PROFILES,
)
def test_first_class_runtime_profiles_round_trip_to_compact_args(
    profile: SchedulerRuntimeProfile,
    expected_context: tuple[str, str, str],
    expected_args: str,
) -> None:
    resolution = scheduler_execution_context_for_runtime_profile(profile)

    assert resolution.ok is True
    assert resolution.context is not None
    assert (
        resolution.context.host_surface.value,
        resolution.context.scheduler_owner.value,
        resolution.context.execution_mode.value,
    ) == expected_context
    assert resolution.context.source == f"runtime_profile:{profile.value}"
    assert scheduler_runtime_profile_for_execution_context(resolution) is profile
    assert render_scheduler_execution_args(runtime_profile=profile.value) == expected_args
    assert (
        render_scheduler_execution_args(scheduler_execution_context=resolution)
        == expected_args
    )


def test_advanced_scheduler_context_keeps_explicit_context_args() -> None:
    context = {
        "host_surface": "codex_cli",
        "scheduler_owner": "agent_cli_loop",
        "execution_mode": "isolated_headless",
    }

    assert scheduler_runtime_profile_for_execution_context(context) is None
    assert render_scheduler_execution_args(
        scheduler_execution_context=context
    ) == " -H codex_cli -O agent_cli_loop -M isolated_headless"


@pytest.mark.parametrize(
    "profile",
    [profile for profile, _, _ in FIRST_CLASS_RUNTIME_PROFILES],
)
def test_stale_unbound_guard_converges_after_profile_regeneration(
    profile: SchedulerRuntimeProfile,
) -> None:
    stale_hint = build_scheduler_hint(_active_payload())
    regenerated_hint = build_scheduler_hint(
        _active_payload(),
        scheduler_execution_context=scheduler_execution_context_for_runtime_profile(
            profile
        ),
    )

    assert stale_hint["action"] == "repair_scheduler_execution_context"
    assert regenerated_hint.get("action") != "repair_scheduler_execution_context"
    assert regenerated_hint["codex_app"]["applicability"] in {
        "applicable",
        "not_applicable",
    }


def test_generic_outer_controller_rerun_actions_are_typed() -> None:
    actions = interaction_next_cli_actions(
        {
            "goal_id": "generic-controller-fixture",
            "agent_identity": {"agent_id": "codex-fixture"},
        },
        mode="monitor_quiet_skip",
        scheduler_execution_context=(
            GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT
        ),
    )
    scheduler_args = render_scheduler_execution_args(
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )

    assert len(actions) == 2
    assert scheduler_args == " --runtime-profile outer_controller"
    assert all(scheduler_args in action for action in actions)
    assert all(" -H " not in action for action in actions)


def test_codex_app_monitor_quiet_retry_uses_turn_receipt() -> None:
    actions = interaction_next_cli_actions(
        {
            "goal_id": "codex-heartbeat-fixture",
            "agent_identity": {"agent_id": "codex-fixture"},
        },
        mode="monitor_quiet_skip",
        scheduler_execution_context=scheduler_execution_context_for_runtime_profile(
            SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT
        ),
    )

    assert actions == [
        "on missing/write_failed heartbeat_receipt only: loopx --format json "
        "quota should-run --goal-id codex-heartbeat-fixture --agent-id "
        'codex-fixture --codex-app --turn-instance-id "${LOOPX_TURN:?}"'
    ]


def test_unbound_rerun_actions_do_not_emit_executable_bare_guards() -> None:
    actions = interaction_next_cli_actions(
        {"goal_id": "unbound-controller-fixture"},
        mode="monitor_quiet_skip",
    )

    assert actions == [
        "use the current host packet's typed monitor command",
        "rerun the typed quota_guard from the current host packet",
    ]
    assert all("quota should-run" not in action for action in actions)
