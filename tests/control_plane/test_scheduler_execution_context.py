from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import product

import pytest

from loopx.control_plane.scheduler.execution_context import (
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    ExecutionMode,
    HostSurface,
    SchedulerOwner,
    SchedulerRuntimeProfile,
    build_goal_runtime_continuation,
    render_scheduler_execution_args,
    resolve_scheduler_execution_context,
    scheduler_execution_context_for_runtime_profile,
    scheduler_runtime_profile_for_execution_context,
)
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
)
from loopx.control_plane.todos.quota_summary import (
    compact_quota_todo_summary_for_payload,
)
from loopx.control_plane.work_items.interaction_contract import (
    interaction_next_cli_actions,
)
from loopx.quota import build_quota_should_run

VALID_COMBINATIONS = {
    ("ark_managed_agent", "goal_runtime", "interactive"),
    ("codex_app", "host_automation", "hosted_automation"),
    ("codex_app_ssh", "agent_cli_loop", "interactive"),
    ("local_scheduler", "host_automation", "hosted_automation"),
    *{
        (surface, owner, mode)
        for surface in ("codex_cli", "generic_cli", "claude_code", "kunluncode")
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
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL,
        ("ark_managed_agent", "goal_runtime", "interactive"),
        " --runtime-profile ark_managed_agent_goal",
    ),
    (
        SchedulerRuntimeProfile.CODEX_APP_HEARTBEAT,
        ("codex_app", "host_automation", "hosted_automation"),
        " --codex-app",
    ),
    (
        SchedulerRuntimeProfile.CODEX_APP_SSH_VISIBLE,
        ("codex_app_ssh", "agent_cli_loop", "interactive"),
        " --runtime-profile codex_app_ssh_goal",
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
        SchedulerRuntimeProfile.KUNLUNCODE_VISIBLE,
        ("kunluncode", "agent_cli_loop", "interactive"),
        " --runtime-profile kunluncode",
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


def _monitor_wait_payload() -> dict:
    payload = _active_payload()
    payload.update(
        {
            "should_run": False,
            "effective_action": "monitor_quiet_skip",
            "heartbeat_recommendation": {
                "recommended_mode": "monitor_quiet_until_material_transition",
                "spend_policy": "no spend for quiet monitor waits",
            },
            "execution_obligation": {
                "must_attempt_work": False,
                "spend_policy": "no spend for quiet monitor waits",
            },
            "interaction_contract": {
                "schema_version": "loopx_interaction_contract_v0",
                "mode": "monitor_quiet_skip",
                "user_channel": {
                    "action_required": False,
                    "notify": "DONT_NOTIFY",
                },
                "agent_channel": {
                    "must_attempt": False,
                    "delivery_allowed": False,
                    "quiet_noop_allowed": True,
                },
                "cli_channel": {
                    "next_cli_actions": [],
                    "spend_allowed_now": False,
                },
            },
        }
    )
    return payload


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


def test_goal_runtime_projects_typed_immediate_continuation() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )

    hint = build_scheduler_hint(
        _active_payload(),
        scheduler_execution_context=context,
    )

    assert hint["goal_runtime_continuation"] == {
        "schema_version": "goal_runtime_continuation_v0",
        "disposition": "continue_now",
    }


def test_goal_runtime_projects_typed_defer_with_recheck_delay() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )

    hint = build_scheduler_hint(
        _monitor_wait_payload(),
        scheduler_execution_context=context,
    )

    continuation = hint["goal_runtime_continuation"]
    assert continuation["disposition"] == "defer"
    assert continuation["recheck_after_seconds"] == 15 * 60
    assert continuation["wake_policy"] == "state_change_or_deadline"
    assert hint["reset_policy"]["reset_token"]
    assert hint["execution_phase"]["disposition"] == "goal_runtime_owned"


def test_goal_runtime_continuation_rejects_unknown_scheduler_action() -> None:
    with pytest.raises(ValueError, match="unsupported Goal runtime scheduler action"):
        build_goal_runtime_continuation({"action": "future_unmapped_action"})


def test_goal_runtime_defer_requires_bounded_recheck_interval() -> None:
    with pytest.raises(ValueError, match="positive recheck interval"):
        build_goal_runtime_continuation(
            {
                "action": "backoff_until_state_change",
                "codex_app": {"recommended_interval_minutes": None},
            }
        )


@pytest.mark.parametrize(
    ("field", "changed_value"),
    (
        ("todo_id", "todo_frontier002"),
        ("action_kind", "issue_fix_reviewer_request"),
        ("target_key", "issue-fix:owner/repo:issue_43"),
        ("claimed_by", "codex-review"),
        ("capability_binding_ref", "issue-fix:feasibility-e5f6a7b8"),
    ),
)
@pytest.mark.parametrize("waiting", (False, True), ids=("continue_now", "defer"))
def test_goal_runtime_identity_rotates_on_selected_todo_contract_change(
    field: str,
    changed_value: str,
    waiting: bool,
) -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    first_payload = _monitor_wait_payload() if waiting else _active_payload()
    first_payload["selected_todo"] = {
        "todo_id": "todo_frontier001",
        "action_kind": "issue_fix_branch_validation",
        "target_key": "issue-fix:owner/repo:issue_42",
        "claimed_by": "codex-fixture",
        "capability_binding_ref": "issue-fix:feasibility-a1b2c3d4",
    }
    second_payload = deepcopy(first_payload)
    second_payload["selected_todo"][field] = changed_value

    first = build_scheduler_hint(
        first_payload,
        scheduler_execution_context=context,
    )
    second = build_scheduler_hint(
        second_payload,
        scheduler_execution_context=context,
    )

    expected_disposition = "defer" if waiting else "continue_now"
    assert first["goal_runtime_continuation"]["disposition"] == expected_disposition
    assert second["goal_runtime_continuation"]["disposition"] == expected_disposition
    assert first["reset_policy"]["reset_token"] != second["reset_policy"][
        "reset_token"
    ]
    assert first["reset_policy"]["identity_signature"] != second[
        "reset_policy"
    ]["identity_signature"]


def test_goal_runtime_identity_ignores_non_contract_selected_todo_detail() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    first_payload = _active_payload()
    first_payload["selected_todo"] = {
        "todo_id": "todo_frontier001",
        "action_kind": "issue_fix_branch_validation",
        "target_key": "issue-fix:owner/repo:issue_42",
        "claimed_by": "codex-fixture",
        "capability_binding_ref": "issue-fix:feasibility-a1b2c3d4",
        "note": "first diagnostic note",
    }
    second_payload = deepcopy(first_payload)
    second_payload["selected_todo"]["note"] = "unrelated diagnostic refresh"

    first = build_scheduler_hint(
        first_payload,
        scheduler_execution_context=context,
    )
    second = build_scheduler_hint(
        second_payload,
        scheduler_execution_context=context,
    )

    assert first["reset_policy"]["reset_token"] == second["reset_policy"][
        "reset_token"
    ]
    assert first["goal_runtime_continuation"] == second[
        "goal_runtime_continuation"
    ]


def test_goal_runtime_mixed_frontier_continues_runnable_advancement() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    status = quota_status_payload(
        goal_id="mixed-frontier-fixture",
        status="active",
        recommended_action="Fix the next issue while the PR monitor is quiet.",
        agent_todo_items=[
            quota_todo_item(
                todo_id="todo_next_issue",
                title="Fix the next independent issue.",
                task_class="advancement_task",
                priority="P0",
            ),
            quota_todo_item(
                todo_id="todo_pr_monitor",
                title="Monitor the earlier PR for CI and review changes.",
                task_class="continuous_monitor",
                priority="P1",
                target_key="github-pr-state-open",
                cadence="30m",
                next_due_at="2099-01-01T00:00:00+00:00",
            ),
        ],
    )

    quota = build_quota_should_run(
        status,
        goal_id="mixed-frontier-fixture",
        scheduler_execution_context=context,
    )

    assert quota["work_lane_contract"]["lane"] == "advancement_task"
    assert quota["goal_frontier_projection"]["monitor_only_lanes"]["present"] is False
    assert quota["scheduler_hint"]["goal_runtime_continuation"]["disposition"] == (
        "continue_now"
    )


def test_goal_runtime_defer_uses_earliest_frontier_transition() -> None:
    """The typed Defer recheck must follow the soonest due monitor on the
    whole frontier, not a later monitor or the generic backoff interval."""

    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    payload = _monitor_wait_payload()
    payload["agent_todo_summary"] = {
        "monitor_open_items": [
            {
                "todo_id": "todo_soon",
                "target_key": "pr-ci-soon",
                "cadence": "60m",
                "next_due_at": (now + timedelta(minutes=20)).isoformat(),
            },
            {
                "todo_id": "todo_later",
                "target_key": "pr-review-later",
                "cadence": "60m",
                "next_due_at": (now + timedelta(minutes=120)).isoformat(),
            },
        ]
    }

    original_now = scheduler_hint_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    try:
        hint = build_scheduler_hint(
            payload,
            include_detail=True,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_now

    continuation = hint["goal_runtime_continuation"]
    assert continuation["disposition"] == "defer"
    # The Goal deadline is derived from the frontier, independent of the
    # coarser host-automation cadence buckets.
    assert continuation["recheck_after_seconds"] == 20 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"
    assert continuation["wake_policy"] == "state_change_or_deadline"
    assert hint["cold_path_detail"]["frontier_recheck"][
        "frontier_recheck_source"
    ] == "continuous_monitor"
    assert "frontier_recheck" not in hint


def test_goal_runtime_defer_uses_user_gate_deadline_before_monitors() -> None:
    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    payload = _monitor_wait_payload()
    payload["agent_todo_summary"] = {
        "monitor_open_items": [
            {
                "todo_id": "todo_ci",
                "target_key": "pr-ci",
                "cadence": "60m",
                "next_due_at": (now + timedelta(minutes=45)).isoformat(),
            }
        ],
        "gate_open_items": [
            {
                "todo_id": "todo_gate",
                "task_class": "user_gate",
                "next_due_at": (now + timedelta(minutes=10)).isoformat(),
            }
        ],
    }

    original_now = scheduler_hint_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    try:
        hint = build_scheduler_hint(
            payload,
            include_detail=True,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_now

    continuation = hint["goal_runtime_continuation"]
    assert continuation["recheck_after_seconds"] == 10 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"
    assert hint["cold_path_detail"]["frontier_recheck"][
        "frontier_recheck_source"
    ] == "user_gate"


def test_quota_human_gate_uses_future_user_gate_deadline_before_monitor() -> None:
    from loopx.control_plane.scheduler import monitor_todo as monitor_todo_mod
    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod
    from loopx.control_plane.todos import quota_summary as quota_summary_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    agent_id = "human-gate-frontier-agent"
    status = quota_status_payload(
        goal_id="human-gate-frontier-fixture",
        status="active",
        recommended_action="Wait for owner approval.",
        agent_todos={
            "schema_version": "todo_summary_v0",
            "source_section": "Agent Todo",
            "total_count": 1,
            "open_count": 1,
            "done_count": 0,
            "deferred_count": 0,
            "monitor_open_items": [
                {
                    "todo_id": "todo_ci",
                    "index": 0,
                    "status": "open",
                    "task_class": "continuous_monitor",
                    "text": "[P1] CI monitor",
                    "target_key": "pr-ci",
                    "cadence": "60m",
                    "next_due_at": (now + timedelta(minutes=45)).isoformat(),
                }
            ],
        },
        user_todos={
            "schema_version": "todo_summary_v0",
            "source_section": "User Todo",
            "total_count": 1,
            "open_count": 1,
            "done_count": 0,
            "deferred_count": 0,
            "resume_blocked_items": [
                {
                    "todo_id": "todo_owner_gate",
                    "index": 0,
                    "status": "open",
                    "task_class": "user_gate",
                    "text": "[P0] Owner approval",
                    "resume_when": "external:approval",
                    "resume_ready": False,
                    "next_due_at": (now + timedelta(minutes=7)).isoformat(),
                }
            ],
        },
        coordination={"registered_agents": [agent_id]},
        claim_scope_agent_id=agent_id,
    )

    original_scheduler_now = scheduler_hint_mod.now_utc
    original_monitor_now = monitor_todo_mod.now_utc
    original_quota_now = quota_summary_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    monitor_todo_mod.now_utc = lambda: now
    quota_summary_mod.now_utc = lambda: now
    try:
        quota = build_quota_should_run(
            status,
            goal_id="human-gate-frontier-fixture",
            agent_id=agent_id,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_scheduler_now
        monitor_todo_mod.now_utc = original_monitor_now
        quota_summary_mod.now_utc = original_quota_now

    continuation = quota["scheduler_hint"]["goal_runtime_continuation"]
    assert continuation["disposition"] == "defer"
    assert quota["scheduler_hint"]["reason_code"] == "interaction_blocking_user_gate"
    assert continuation["recheck_after_seconds"] == 7 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"


def test_quota_payload_compaction_preserves_earliest_frontier_deadline() -> None:
    from loopx.control_plane.scheduler import monitor_todo as monitor_todo_mod
    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod
    from loopx.control_plane.todos import quota_summary as quota_summary_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    agent_id = "frontier-deadline-agent"
    watch_lane_ack = {
        "classification": "autonomous_replan_recorded",
        "generated_at": now.isoformat(),
        "agent_id": agent_id,
        "autonomous_replan_ack": {
            "schema_version": "autonomous_replan_ack_v0",
            "recorded": True,
            "source": "fixture",
            "delta_contract": {
                "schema_version": "repair_delta_contract_v0",
                "delta_present": True,
                "delta_kinds": ["watch_lane_continuation"],
            },
        },
    }
    status = quota_status_payload(
        goal_id="frontier-deadline-compaction-fixture",
        status="active",
        recommended_action="Wait for the next monitor transition.",
        agent_todos={
            "schema_version": "todo_summary_v0",
            "source_section": "Agent Todo",
            "total_count": 3,
            "open_count": 3,
            "done_count": 0,
            "deferred_count": 0,
            "monitor_open_items": [
                {
                    "todo_id": "todo_unscheduled_monitor_a",
                    "index": 0,
                    "status": "open",
                    "task_class": "continuous_monitor",
                    "text": "[P1] Unscheduled monitor A",
                    "target_key": "unscheduled-monitor-a",
                    "cadence": "60m",
                },
                {
                    "todo_id": "todo_unscheduled_monitor_b",
                    "index": 1,
                    "status": "open",
                    "task_class": "continuous_monitor",
                    "text": "[P1] Unscheduled monitor B",
                    "target_key": "unscheduled-monitor-b",
                    "cadence": "60m",
                },
                {
                    "todo_id": "todo_earliest_monitor",
                    "index": 2,
                    "status": "open",
                    "task_class": "continuous_monitor",
                    "text": "[P1] Earliest monitor",
                    "target_key": "earliest-monitor",
                    "cadence": "60m",
                    "next_due_at": (now + timedelta(minutes=10)).isoformat(),
                },
            ],
        },
        latest_runs=[watch_lane_ack],
        claim_scope_agent_id=agent_id,
        coordination={"registered_agents": [agent_id]},
    )

    original_scheduler_now = scheduler_hint_mod.now_utc
    original_monitor_now = monitor_todo_mod.now_utc
    original_quota_now = quota_summary_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    monitor_todo_mod.now_utc = lambda: now
    quota_summary_mod.now_utc = lambda: now
    try:
        quota = build_quota_should_run(
            status,
            goal_id="frontier-deadline-compaction-fixture",
            agent_id=agent_id,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_scheduler_now
        monitor_todo_mod.now_utc = original_monitor_now
        quota_summary_mod.now_utc = original_quota_now

    compacted_summary = quota["agent_todo_summary"]
    compacted_monitors = compacted_summary["monitor_open_items"]
    assert [item["todo_id"] for item in compacted_monitors] == [
        "todo_unscheduled_monitor_a",
        "todo_unscheduled_monitor_b",
    ]
    assert compacted_summary["frontier_deadline"]["identity"] == (
        "todo_earliest_monitor"
    )
    continuation = quota["scheduler_hint"]["goal_runtime_continuation"]
    assert continuation["disposition"] == "defer"
    assert continuation["recheck_after_seconds"] == 10 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"


def test_frontier_deadline_projection_does_not_reorder_selection_lane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from loopx.control_plane.todos import quota_summary as quota_summary_mod

    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(quota_summary_mod, "now_utc", lambda: now)
    summary = {
        "first_executable_items": [
            {"todo_id": "selected_first", "index": 0},
            {
                "todo_id": "deadline_second",
                "index": 1,
                "next_due_at": (now + timedelta(minutes=5)).isoformat(),
            },
        ],
        "monitor_open_items": [
            {
                "todo_id": "deadline_second",
                "index": 1,
                "next_due_at": (now + timedelta(minutes=5)).isoformat(),
            }
        ],
    }

    compacted = compact_quota_todo_summary_for_payload(summary)

    assert [item["todo_id"] for item in compacted["first_executable_items"]] == [
        "selected_first",
        "deadline_second",
    ]
    assert compacted["frontier_deadline"]["identity"] == "deadline_second"


def test_goal_runtime_quiet_wait_uses_non_monitor_frontier_deadline() -> None:
    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    payload = _monitor_wait_payload()
    payload["interaction_contract"]["mode"] = "quiet_skip"
    payload["agent_todo_summary"] = {
        "monitor_open_items": [
            {
                "todo_id": "todo_monitor",
                "target_key": "pr-review",
                "cadence": "60m",
            }
        ],
        "deferred_resume_candidates": [
            {
                "todo_id": "todo_resume",
                "task_class": "advancement_task",
                "resume_ready": True,
                "next_due_at": (now + timedelta(minutes=7)).isoformat(),
            }
        ],
    }

    original_now = scheduler_hint_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    try:
        hint = build_scheduler_hint(
            payload,
            include_detail=True,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_now

    continuation = hint["goal_runtime_continuation"]
    assert hint["action"] == "backoff_until_state_change"
    assert continuation["recheck_after_seconds"] == 7 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"
    assert hint["cold_path_detail"]["frontier_recheck"][
        "frontier_recheck_source"
    ] == "advancement_task"


def test_goal_runtime_defer_uses_exact_due_inside_host_floor() -> None:
    from loopx.control_plane.scheduler import scheduler_hint as scheduler_hint_mod

    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    now = datetime(2026, 8, 2, 6, 0, 0, tzinfo=UTC)
    payload = _monitor_wait_payload()
    payload["agent_todo_summary"] = {
        "monitor_open_items": [
            {
                "todo_id": "todo_due_soon",
                "target_key": "pr-ci-due-soon",
                "cadence": "60m",
                "next_due_at": (now + timedelta(minutes=5)).isoformat(),
            }
        ]
    }

    original_now = scheduler_hint_mod.now_utc
    scheduler_hint_mod.now_utc = lambda: now
    try:
        hint = build_scheduler_hint(
            payload,
            scheduler_execution_context=context,
        )
    finally:
        scheduler_hint_mod.now_utc = original_now

    continuation = hint["goal_runtime_continuation"]
    assert continuation["recheck_after_seconds"] == 5 * 60
    assert continuation["recheck_source"] == "frontier_earliest_material_transition"


def test_goal_runtime_defer_falls_back_to_codex_interval_without_frontier() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )

    hint = build_scheduler_hint(
        _monitor_wait_payload(),
        scheduler_execution_context=context,
    )

    continuation = hint["goal_runtime_continuation"]
    assert continuation["disposition"] == "defer"
    assert "recheck_source" not in continuation
    assert continuation["recheck_after_seconds"] == 15 * 60
    assert continuation["wake_policy"] == "state_change_or_deadline"
    assert "frontier_recheck" not in hint


def test_non_goal_runtime_does_not_receive_goal_continuation() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.CODEX_CLI_VISIBLE
    )

    hint = build_scheduler_hint(
        _monitor_wait_payload(),
        scheduler_execution_context=context,
    )

    assert "goal_runtime_continuation" not in hint


def test_goal_runtime_terminal_stop_projects_complete() -> None:
    context = scheduler_execution_context_for_runtime_profile(
        SchedulerRuntimeProfile.ARK_MANAGED_AGENT_GOAL
    )
    payload = _monitor_wait_payload()
    payload["effective_action"] = "terminal_no_followup"
    payload["interaction_contract"]["mode"] = "terminal_no_followup"

    hint = build_scheduler_hint(
        payload,
        scheduler_execution_context=context,
    )

    assert hint["action"] == "stop_until_explicit_resume"
    assert hint["goal_runtime_continuation"]["disposition"] == "complete"
    assert "recheck_after_seconds" not in hint["goal_runtime_continuation"]


@pytest.mark.parametrize(
    ("profile", "runtime_key"),
    (
        (SchedulerRuntimeProfile.CODEX_APP_SSH_VISIBLE, "codex_app_ssh_goal"),
        (SchedulerRuntimeProfile.CODEX_CLI_VISIBLE, "codex_cli_tui"),
    ),
)
def test_native_codex_goal_monitor_wait_uses_blocked_status_after_limit(
    profile: SchedulerRuntimeProfile,
    runtime_key: str,
) -> None:
    context = scheduler_execution_context_for_runtime_profile(profile)
    hint = build_scheduler_hint(
        _monitor_wait_payload(),
        include_detail=True,
        scheduler_execution_context=context,
    )

    unchanged = hint["unchanged_poll"]
    assert unchanged["limits"][runtime_key] == 3
    assert unchanged["after_limits"][runtime_key] == (
        "update_goal_blocked_keep_loopx_active"
    )
    host_detail = hint["cold_path_detail"][runtime_key]
    assert host_detail["loopx_goal_state"] == "remains_active"
    assert host_detail["resume_trigger"] == "explicit_codex_goal_resume"
    assert host_detail["no_spend_for_block"] is True


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
        (
            "on missing/write_failed heartbeat_receipt only: loopx --format json "
            "quota should-run --goal-id codex-heartbeat-fixture --agent-id "
            'codex-fixture --codex-app --turn-instance-id "${LOOPX_TURN:?}"'
        )
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
