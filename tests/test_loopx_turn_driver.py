from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from loopx.cli import main as cli_main
from loopx.control_plane.quota.turn_envelope import build_turn_envelope
from loopx.control_plane.turn_driver import (
    LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
    LoopXTurnRoute,
    TurnLeaseController,
    build_loopx_turn_host_request,
    build_loopx_turn_plan,
    codex_cli_session_binding,
    load_turn_events,
    loopx_turn_execution_committed,
    run_loopx_turn_once,
    selected_turn_todo_write_scopes,
)
from loopx.control_plane.turn_driver.codex_cli import _store_codex_cli_session
from loopx.control_plane.quota.live_decision import bind_scheduler_followup_cli_routes
from loopx.control_plane.work_items.task_lease import (
    acquire_task_lease,
    read_lease,
    release_task_lease,
    task_lease_fencing_token,
    task_lease_path,
)
from loopx.todos import complete_goal_todo


def _envelope(
    *,
    should_run: bool = True,
    effective_action: str = "normal_run",
    action_required: bool = False,
    quiet_noop_allowed: bool = False,
) -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "loopx_turn_envelope_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "should_run": should_run,
        "effective_action": effective_action,
        "action": {
            "must_attempt": should_run,
            "delivery_allowed": should_run,
            "quiet_noop_allowed": quiet_noop_allowed,
            "selected_todo": {
                "todo_id": "todo_fixture0001",
                "text": "Advance one public fixture",
            },
        },
        "user": {
            "action_required": action_required,
            "open_count": 1 if action_required else 0,
            "notify": "NOTIFY" if action_required else "DONT_NOTIFY",
        },
        "writeback": {"spend_after_validation": should_run},
        "scheduler": {"action": "run_now" if should_run else "wait"},
        "action_signature": {
            "matches": True,
            "source_hash": "sha256:fixture",
            "envelope_hash": "sha256:fixture",
        },
        "compaction": {"within_budget": True},
    }


def test_turn_plan_projects_ready_route_without_side_effects() -> None:
    envelope = _envelope()

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is True
    assert payload["schema_version"] == "loopx_turn_plan_v0"
    assert payload["mode"] == "plan"
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["route"]["would_invoke_host"] is True
    assert payload["route"]["host_invocation_allowed"] is False
    assert payload["session"] == {
        "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
        "action": "start_new",
    }
    assert payload["transaction"]["status"] == "planned"
    assert payload["transaction"]["phases"] == [
        "host_execute",
        "typed_result",
        "validation",
        "durable_writeback",
        "quota_spend",
        "scheduler_apply",
        "scheduler_ack",
    ]
    assert payload["transaction"]["receipt_seed"]["status"] == "not_executed"
    assert payload["transaction"]["receipt_seed"]["next_phase"] == "host_execute"
    settlement_plan = payload["transaction"]["settlement_plan"]
    assert settlement_plan["identity"]["goal_id"] == "fixture-goal"
    assert settlement_plan["identity"]["agent_id"] == "codex-fixture"
    assert settlement_plan["identity"]["todo_id"] == "todo_fixture0001"
    assert [step["kind"] for step in settlement_plan["ordered_steps"]] == [
        "validation",
        "durable_writeback",
        "quota_spend",
    ]
    for step in settlement_plan["ordered_steps"]:
        assert step["owner"]
        assert step["precondition"]
        assert step["idempotency_key_ref"] == "$.identity.effect_id"
        assert step["expected_receipt"]
    assert settlement_plan["host_handoff"]["inside_agent_settlement"] is False
    assert payload["turn_envelope"] == envelope
    assert payload["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "scheduler_acknowledged": False,
        "quota_spent": False,
    }
    assert payload["boundary"]["read_only"] is True


def _adaptive_envelope() -> dict[str, object]:
    envelope = _envelope()
    envelope["task_orchestration_contract"] = {
        "schema_version": "task_orchestration_contract_v2",
        "mode": "adaptive",
        "coordinator_agent_id": "codex-fixture",
        "primary_todo_id": "todo_fixture0001",
        "primary_todo": {
            "todo_id": "todo_fixture0001",
            "required_write_scopes": [],
        },
        "child_brief_defaults": {
            "schema_version": "subagent_control_plane_handoff_v0",
            "parent_goal_id": "fixture-goal",
            "context_policy": {
                "selection_owner": "task_coordinator",
                "default": "fresh",
                "allowed": ["fresh", "resume"],
            },
        },
        "eligible_child_lanes": [
            {
                "todo_id": "todo_child001",
                "task_domain": "validation",
                "execution_kind": "ephemeral_child",
                "child_brief": {
                    "todo_id": "todo_child001",
                    "objective": "Validate one independent fixture.",
                    "task_domain": "validation",
                },
            }
        ],
        "writeback_owner": "task_coordinator",
    }
    return envelope


def _signed_adaptive_envelope(
    *,
    stale_selected_todo_id: str,
    recommended_action: str = "Advance one public fixture",
) -> dict[str, object]:
    decision = {
        "ok": True,
        "goal_id": "fixture-goal",
        "agent_identity": {"agent_id": "codex-fixture"},
        "decision": "run",
        "should_run": True,
        "effective_action": "normal_run",
        "state": "eligible",
        "recommended_action": recommended_action,
        "selected_todo": {
            "todo_id": stale_selected_todo_id,
            "text": "A stale pre-orchestration selection",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "normal_run",
            "user_channel": {
                "action_required": False,
                "notify": "DONT_NOTIFY",
            },
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
            },
            "cli_channel": {
                "spend_after_validation": True,
            },
        },
        "task_orchestration_contract": {
            **_adaptive_envelope()["task_orchestration_contract"],
            "primary_todo_id": "todo_primary",
            "primary_todo": {
                "todo_id": "todo_primary",
                "required_write_scopes": ["src/**"],
            },
        },
    }
    return build_turn_envelope(decision)


def test_turn_plan_maps_admitted_child_to_codex_native_operation() -> None:
    payload = build_loopx_turn_plan(
        _adaptive_envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    orchestration = payload["turn_envelope"]["task_orchestration_contract"]
    lane_brief = orchestration["eligible_child_lanes"][0]["child_brief"]
    brief = {
        **orchestration["child_brief_defaults"],
        **lane_brief,
        "evidence_boundary": {
            "task_domain": "validation",
            "task_repository": None,
            "required_write_scopes": [],
        },
    }
    assert payload["child_operations"] == [
        {
            "schema_version": "loopx_child_host_operation_v0",
            "todo_id": "todo_child001",
            "host": "codex-cli",
            "selection_owner": "task_coordinator",
            "recommended_context": "fresh",
            "available_contexts": [
                {
                    "context": "fresh",
                    "native_operation": "spawn_agent",
                    "requires_session": False,
                },
                {
                    "context": "resume",
                    "native_operation": "resume_agent",
                    "requires_session": True,
                },
            ],
            "brief": brief,
            "result_channel": "public_safe_typed_evidence",
            "writeback_owner": "task_coordinator",
        }
    ]


def test_turn_plan_uses_adaptive_primary_todo_for_bundle_lineage() -> None:
    first_envelope = _signed_adaptive_envelope(
        stale_selected_todo_id="todo_stale_selection",
    )
    second_envelope = _signed_adaptive_envelope(
        stale_selected_todo_id="todo_another_stale_selection",
    )
    assert first_envelope["action_signature"]["matches"] is True
    assert (
        first_envelope["action_signature"]["source_hash"]
        == first_envelope["action_signature"]["envelope_hash"]
    )
    assert second_envelope["action_signature"]["matches"] is True
    assert (
        second_envelope["action_signature"]["source_hash"]
        == second_envelope["action_signature"]["envelope_hash"]
    )
    assert (
        first_envelope["action_signature"]["source_hash"]
        == second_envelope["action_signature"]["source_hash"]
    )

    payload = build_loopx_turn_plan(
        first_envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is True
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["route"]["selected_todo"] == {
        "todo_id": "todo_primary",
        "source": "task_orchestration_contract.primary_todo",
        "required_write_scopes": ["src/**"],
    }
    same_primary_plan = build_loopx_turn_plan(
        second_envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )
    changed_action_plan = build_loopx_turn_plan(
        _signed_adaptive_envelope(
            stale_selected_todo_id="todo_stale_selection",
            recommended_action="Advance a different public fixture",
        ),
        host="codex-cli",
        execution_mode="interactive-visible",
    )
    assert (
        payload["transaction"]["turn_key"]
        == same_primary_plan["transaction"]["turn_key"]
    )
    assert (
        payload["transaction"]["turn_key"]
        != changed_action_plan["transaction"]["turn_key"]
    )


def test_adaptive_primary_todo_without_scope_projection_fails_closed() -> None:
    with pytest.raises(
        ValueError,
        match="adaptive primary todo must project required_write_scopes",
    ):
        selected_turn_todo_write_scopes(
            {
                "todo_id": "todo_primary",
                "source": "task_orchestration_contract.primary_todo_id",
            }
        )


def test_turn_plan_exposes_only_qualified_claude_child_contexts() -> None:
    envelope = _adaptive_envelope()
    payload = build_loopx_turn_plan(
        envelope,
        host="claude-code",
        execution_mode="interactive-visible",
    )
    orchestration = envelope["task_orchestration_contract"]
    lane_brief = orchestration["eligible_child_lanes"][0]["child_brief"]
    brief = {
        **orchestration["child_brief_defaults"],
        **lane_brief,
        "evidence_boundary": {
            "task_domain": "validation",
            "task_repository": None,
            "required_write_scopes": [],
        },
    }

    assert payload["child_operations"][0] == {
        "schema_version": "loopx_child_host_operation_v0",
        "todo_id": "todo_child001",
        "host": "claude-code",
        "selection_owner": "task_coordinator",
        "recommended_context": "fresh",
        "available_contexts": [
            {
                "context": "fresh",
                "native_operation": "Task",
                "requires_session": False,
            }
        ],
        "brief": brief,
        "result_channel": "public_safe_typed_evidence",
        "writeback_owner": "task_coordinator",
    }


def test_codex_session_binding_uses_adaptive_primary_todo(
    tmp_path: Path,
) -> None:
    envelope = _adaptive_envelope()
    envelope["action"]["selected_todo"] = {
        "todo_id": "todo_stale_selection",
        "text": "A stale pre-orchestration selection",
    }
    envelope["task_orchestration_contract"]["primary_todo_id"] = "todo_primary"
    envelope["task_orchestration_contract"]["primary_todo"] = {
        "todo_id": "todo_primary",
        "required_write_scopes": ["src/**"],
    }
    lineage = {
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "todo_id": "todo_primary",
    }
    _store_codex_cli_session(
        tmp_path,
        lineage=lineage,
        session_id="session-primary",
    )

    assert codex_cli_session_binding(tmp_path, envelope) == {
        "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
        **lineage,
    }


def test_generic_host_does_not_project_unqualified_child_operations() -> None:
    payload = build_loopx_turn_plan(
        _adaptive_envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
    )

    assert payload["ok"] is True
    assert "child_operations" not in payload


def test_turn_host_request_carries_typed_child_operations() -> None:
    plan = build_loopx_turn_plan(
        _adaptive_envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    request = build_loopx_turn_host_request(plan)

    assert request["child_operations"] == plan["child_operations"]
    assert request["child_operations"][0]["available_contexts"][0] == {
        "context": "fresh",
        "native_operation": "spawn_agent",
        "requires_session": False,
    }
    assert request["result_contract"]["stdout"] == "one public-safe JSON object"


def test_turn_help_omits_legacy_agent_loop_entrypoint() -> None:
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(["--help"])

    assert exit_code == 0
    assert "agent-loop" not in output.getvalue()
    assert "turn" in output.getvalue()


def test_turn_plan_resumes_only_a_matching_session_binding() -> None:
    payload = build_loopx_turn_plan(
        _envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
        session_binding={
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "goal_id": "fixture-goal",
            "agent_id": "codex-fixture",
            "todo_id": "todo_fixture0001",
        },
    )

    assert payload["ok"] is True
    assert payload["session"]["action"] == "resume"
    assert payload["boundary"]["opaque_session_handle_omitted"] is True


def test_turn_plan_rejects_session_binding_identity_drift() -> None:
    payload = build_loopx_turn_plan(
        _envelope(),
        host="codex-cli",
        execution_mode="interactive-visible",
        session_binding={
            "schema_version": LOOPX_TURN_SESSION_BINDING_SCHEMA_VERSION,
            "goal_id": "another-goal",
            "agent_id": "codex-fixture",
            "todo_id": "todo_fixture0001",
        },
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value
    assert payload["route"]["would_invoke_host"] is False
    assert payload["session"]["action"] == "reject"
    assert payload["session"]["binding_status"] == "identity_mismatch"
    assert payload["transaction"]["status"] == "not_applicable"
    assert payload["effects"]["host_invoked"] is False


def test_turn_plan_transaction_key_is_stable_and_todo_scoped() -> None:
    first = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    repeated = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    changed_envelope = _envelope()
    changed_envelope["action"]["selected_todo"]["todo_id"] = "todo_fixture0002"
    changed = build_loopx_turn_plan(
        changed_envelope,
        host="generic-cli",
        execution_mode="isolated-headless",
    )

    assert first["transaction"]["turn_key"] == repeated["transaction"]["turn_key"]
    assert first["transaction"]["turn_key"] != changed["transaction"]["turn_key"]
    assert (
        first["transaction"]["settlement_plan"]["identity"]["effect_id"]
        == repeated["transaction"]["settlement_plan"]["identity"]["effect_id"]
    )
    assert (
        first["transaction"]["settlement_plan"]["identity"]["effect_id"]
        != changed["transaction"]["settlement_plan"]["identity"]["effect_id"]
    )


def test_turn_plan_instance_id_distinguishes_new_turns_from_retries() -> None:
    first = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
        turn_instance_id="batch-42:turn-1",
    )
    retry = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
        turn_instance_id="batch-42:turn-1",
    )
    second = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
        turn_instance_id="batch-42:turn-2",
    )

    assert first["transaction"]["turn_instance_id"] == "batch-42:turn-1"
    assert first["transaction"]["turn_key"] == retry["transaction"]["turn_key"]
    assert first["transaction"]["turn_key"] != second["transaction"]["turn_key"]


@pytest.mark.parametrize(
    "instance_id",
    ["", "contains space", "private/path", "x" * 129],
)
def test_turn_plan_rejects_unsafe_instance_id(instance_id: str) -> None:
    with pytest.raises(ValueError, match="turn_instance_id"):
        build_loopx_turn_plan(
            _envelope(),
            host="generic-cli",
            execution_mode="isolated-headless",
            turn_instance_id=instance_id,
        )


@pytest.mark.parametrize(
    ("effective_action", "expected"),
    [
        ("capability_repair", LoopXTurnRoute.REPAIR_REQUIRED),
        ("autonomous_replan", LoopXTurnRoute.REPLAN_REQUIRED),
        ("successor_replan_required", LoopXTurnRoute.REPLAN_REQUIRED),
    ],
)
def test_turn_plan_projects_typed_recovery_routes(
    effective_action: str,
    expected: LoopXTurnRoute,
) -> None:
    payload = build_loopx_turn_plan(
        _envelope(effective_action=effective_action),
        host="generic-cli",
        execution_mode="isolated-headless",
    )

    assert payload["route"]["kind"] == expected.value
    assert payload["host"]["explicit_isolation"] is True
    assert payload["host"]["scheduler_owner"] == "outer_controller"
    assert payload["scheduler_execution_context"] == {
        "schema_version": "scheduler_execution_context_v0",
        "host_surface": "generic_cli",
        "scheduler_owner": "outer_controller",
        "execution_mode": "isolated_headless",
        "source": "loopx_turn",
        "valid": True,
        "codex_app_applicability": "not_applicable",
    }


def test_turn_plan_rejects_contradictory_scheduler_owner() -> None:
    payload = build_loopx_turn_plan(
        _envelope(),
        host="generic-cli",
        execution_mode="isolated-headless",
        scheduler_owner="host_automation",
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value
    assert payload["route"]["would_invoke_host"] is False
    assert "cannot be owned by host_automation" in payload["error"]


def test_turn_plan_preserves_safe_bypass_when_user_action_is_visible() -> None:
    payload = build_loopx_turn_plan(
        _envelope(action_required=True),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value


@pytest.mark.parametrize(
    ("action_required", "quiet_noop_allowed", "expected"),
    [
        (True, False, LoopXTurnRoute.USER_ACTION_REQUIRED),
        (False, True, LoopXTurnRoute.WAIT),
        (False, False, LoopXTurnRoute.BLOCKED),
    ],
)
def test_turn_plan_projects_non_run_routes(
    action_required: bool,
    quiet_noop_allowed: bool,
    expected: LoopXTurnRoute,
) -> None:
    payload = build_loopx_turn_plan(
        _envelope(
            should_run=False,
            action_required=action_required,
            quiet_noop_allowed=quiet_noop_allowed,
        ),
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["route"]["kind"] == expected.value
    assert payload["route"]["would_invoke_host"] is False
    assert payload["session"]["action"] == "none"
    assert payload["transaction"]["status"] == "not_applicable"
    assert payload["transaction"]["phases"] == []


def test_turn_plan_fails_closed_on_action_signature_drift() -> None:
    envelope = _envelope()
    envelope["action_signature"] = {"matches": False}

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value
    assert payload["route"]["would_invoke_host"] is False


def test_turn_plan_fails_closed_on_oversized_turn_envelope() -> None:
    envelope = _envelope()
    envelope["compaction"] = {"within_budget": False}

    payload = build_loopx_turn_plan(
        envelope,
        host="codex-cli",
        execution_mode="interactive-visible",
    )

    assert payload["ok"] is False
    assert payload["route"]["kind"] == LoopXTurnRoute.CONTRACT_ERROR.value


def test_scheduler_followup_binding_preserves_turn_lineage(
    tmp_path: Path,
) -> None:
    payload = {
        "scheduler_hint": {
            "codex_app": {"ack_hint": {"cli_args": ["quota", "scheduler-ack-current"]}}
        }
    }

    bind_scheduler_followup_cli_routes(
        payload,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        source="loopx_turn_plan",
    )

    ack_hint = payload["scheduler_hint"]["codex_app"]["ack_hint"]
    assert ack_hint["cli_args"][:2] == ["--registry", str(tmp_path / "registry.json")]
    assert ack_hint["route_binding"]["source"] == "loopx_turn_plan"


def _write_live_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    runtime.mkdir(parents=True)
    state = project / ".codex" / "goals" / "loopx-turn-fixture" / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# LoopX Turn Fixture",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Advance one public fixture.",
                "  <!-- loopx:todo todo_id=todo_fixture0001 status=open task_class=advancement_task action_kind=fixture claimed_by=codex-fixture required_write_scopes=docs%2F%2A%2A priority=P0 -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": "loopx-turn-fixture",
                        "domain": "loopx-turn-public-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": str(state.relative_to(project)),
                        "adapter": {
                            "kind": "fixture_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {"compute": 1.0, "window_hours": 24},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": ["codex-fixture"],
                            "agent_profiles": {
                                "codex-fixture": {
                                    "schema_version": "agent_profile_v1",
                                    "profile_role": "fixture",
                                    "scope": "public qualification",
                                }
                            },
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return project, runtime, registry


def test_quota_cli_projects_outer_controller_without_codex_app_action(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--host-surface",
                "generic_cli",
                "--scheduler-owner",
                "outer_controller",
                "--execution-mode",
                "isolated_headless",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    hint = payload["scheduler_hint"]
    assert exit_code == 0, payload
    assert hint["execution_context"]["codex_app_applicability"] == "not_applicable"
    assert hint["codex_app"]["applicability"] == "not_applicable"
    assert "stateful_backoff" not in hint["codex_app"]
    assert hint["execution_phase"]["scheduler_owner"] == "outer_controller"
    assert hint["execution_phase"]["completed"] is True
    assert hint["execution_phase"]["apply_needed"] is False
    assert hint["execution_phase"]["ack_needed"] is False


def test_quota_cli_without_scheduler_context_fails_closed(tmp_path: Path) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    hint = payload["scheduler_hint"]
    assert exit_code == 0, payload
    assert hint["action"] == "repair_scheduler_execution_context"
    assert hint["execution_context"]["valid"] is False
    assert hint["codex_app"]["applicability"] == "blocked_invalid_context"


@pytest.mark.parametrize(
    "profile_args",
    (
        ["--runtime-profile", "codex_app_heartbeat"],
        ["--codex-app"],
    ),
)
def test_quota_cli_codex_app_profile_is_explicit_and_applicable(
    tmp_path: Path,
    profile_args: list[str],
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                *profile_args,
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    hint = payload["scheduler_hint"]
    assert exit_code == 0, payload
    assert "execution_context" not in hint
    assert "execution_phase" not in hint
    assert hint["codex_app"]["applicability"] == "applicable"
    assert "stateful_backoff" in hint["codex_app"]


def test_quota_cli_short_context_flags_preserve_all_typed_fields(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "quota",
                "should-run",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "-H",
                "generic_cli",
                "-O",
                "agent_cli_loop",
                "-M",
                "interactive",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    context = payload["scheduler_hint"]["execution_context"]
    assert exit_code == 0, payload
    assert context["host_surface"] == "generic_cli"
    assert context["scheduler_owner"] == "agent_cli_loop"
    assert context["execution_mode"] == "interactive"
    assert context["codex_app_applicability"] == "not_applicable"


def test_heartbeat_cli_codex_app_alias_reaches_generated_quota_guard(
    tmp_path: Path,
) -> None:
    _, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "heartbeat-prompt",
                "--thin",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--codex-app",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["runtime_profile"] == "codex_app_heartbeat"
    assert "--codex-app" in payload["quota_guard_command"]
    assert "--codex-app" in payload["task_body"]


def test_turn_cli_consumes_live_state_without_writes(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "plan",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--scan-root",
                str(project),
                "--include-transaction-detail",
            ]
        )

    payload = json.loads(output.getvalue())
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert exit_code == 0
    assert payload["route"]["kind"] == LoopXTurnRoute.READY_FOR_HOST.value
    assert payload["session"]["action"] == "start_new"
    assert "settlement_plan" not in payload["transaction"]
    assert payload["turn_envelope"]["action_signature"]["matches"] is True
    assert payload["effects"]["state_written"] is False
    assert before == after


def test_turn_cli_omits_transaction_detail_by_default(tmp_path: Path) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "plan",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert "session" not in payload
    assert "transaction" not in payload
    assert "opaque_session_handle_omitted" not in payload["boundary"]


def test_turn_cli_requires_complete_resume_identity(tmp_path: Path) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "plan",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--resume-goal-id",
                "loopx-turn-fixture",
                "--scan-root",
                str(project),
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1
    assert payload["ok"] is False
    assert "requires --resume-goal-id" in payload["error"]


def test_turn_run_once_cli_commits_validated_result_and_one_quota_slot(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    host_script = """
import json
import pathlib
import sys
request = json.load(sys.stdin)
pathlib.Path("fixture-artifact.txt").write_text("validated", encoding="utf-8")
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "fixture_progress",
    "recommended_action": "Continue the public fixture",
    "next_action": "Run the next public fixture check",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "One public fixture advanced."
}, sys.stdout)
"""
    validation_script = """
import json
import pathlib
import sys
json.load(sys.stdin)
artifact = pathlib.Path("fixture-artifact.txt")
raise SystemExit(0 if artifact.read_text(encoding="utf-8") == "validated" else 7)
"""
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-adapter-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["status"] == "committed"
    assert payload["receipt"]["status"] == "committed"
    assert payload["receipt"]["next_phase"] is None
    assert payload["validation"]["status"] == "passed"
    assert payload["validation"]["validator_kind"] == "command"
    assert payload["resume_turn_key"].startswith("sha256:")
    assert payload["scheduler"] == {
        "schema_version": "scheduler_execution_phase_v0",
        "host_surface": "generic_cli",
        "scheduler_owner": "outer_controller",
        "disposition": "outer_controller_owned",
        "completed": True,
        "apply_needed": False,
        "ack_needed": False,
        "acknowledged": False,
        "completion_reason": "selected scheduler owner requires no Codex App apply or ACK",
    }
    assert payload["effects"] == {
        "host_invoked": True,
        "state_written": True,
        "quota_spent": True,
        "scheduler_acknowledged": False,
    }
    assert payload["lease_release"] == {"released": True}
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    assert "Run the next public fixture check" in state_path.read_text(encoding="utf-8")
    index_path = runtime / "goals" / "loopx-turn-fixture" / "runs" / "index.jsonl"
    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert [row["classification"] for row in rows] == [
        "fixture_progress",
        "quota_slot_spent",
    ]
    turn_key = payload["resume_turn_key"]
    assert [row["turn_effect_key"] for row in rows] == [
        f"{turn_key}:durable_writeback",
        f"{turn_key}:quota_spend",
    ]
    lease = read_lease(
        task_lease_path(
            runtime_root=runtime,
            goal_id="loopx-turn-fixture",
            todo_id="todo_fixture0001",
        )
    )
    assert lease is not None
    assert lease["status"] == "released"
    assert lease["owner"] == "codex-fixture"
    assert lease["idempotency_key"] == f"turn:{turn_key}"
    assert lease["write_scopes"] == ["docs/**"]

    resumed_output = io.StringIO()
    with contextlib.redirect_stdout(resumed_output):
        resumed_exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--resume-turn-key",
                payload["resume_turn_key"],
                "--execute",
            ]
        )

    resumed = json.loads(resumed_output.getvalue())
    assert resumed_exit_code == 0, resumed
    assert resumed["status"] == "committed"
    assert resumed["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    replayed_rows = [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [row["classification"] for row in replayed_rows] == [
        "fixture_progress",
        "quota_slot_spent",
    ]


def test_turn_run_once_cli_completes_selected_todo_after_validation(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    host_script = """
import json
import pathlib
import sys
request = json.load(sys.stdin)
pathlib.Path("completion-artifact.txt").write_text("completed", encoding="utf-8")
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "validated_completion",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "fixture_completion",
    "recommended_action": "Refresh the active goal after completion.",
    "next_action": "Select the next Todo from a fresh decision.",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The active goal may have further work.",
    "summary": "One public fixture completed."
}, sys.stdout)
"""
    validation_script = """
import json
import pathlib
import sys
json.load(sys.stdin)
artifact = pathlib.Path("completion-artifact.txt")
raise SystemExit(0 if artifact.read_text(encoding="utf-8") == "completed" else 7)
"""
    output = io.StringIO()
    argv = [
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "turn",
        "run-once",
        "--goal-id",
        "loopx-turn-fixture",
        "--agent-id",
        "codex-fixture",
        "--project",
        str(host_project),
        "--host-adapter-command-json",
        json.dumps([sys.executable, "-c", host_script]),
        "--validation-command-json",
        json.dumps([sys.executable, "-c", validation_script]),
        "--scan-root",
        str(project),
        "--no-global-sync",
        "--execute",
    ]
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(argv)

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["status"] == "committed"
    assert payload["effects"]["state_written"] is True
    assert payload["effects"]["quota_spent"] is True
    events = load_turn_events(
        runtime,
        "loopx-turn-fixture",
        payload["resume_turn_key"],
    )
    states = [
        event["payload"]["state"]
        for event in events
        if isinstance(event.get("payload"), dict)
        and isinstance(event["payload"].get("state"), dict)
    ]
    assert states
    journal = states[-1]
    assert journal["writeback"]["completion"] == {
        "todo_id": "todo_fixture0001",
        "continuation": "active_goal",
    }
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    state = state_path.read_text(encoding="utf-8")
    assert "todo_id=todo_fixture0001 status=done" in state
    assert "LoopX%20Turn%20validated%20completion" in state
    assert f"completion_turn_key={payload['resume_turn_key']}" in state

    recovered_completion = complete_goal_todo(
        registry_path=registry,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        role="agent",
        agent_id="codex-fixture",
        completion_turn_key=payload["resume_turn_key"],
    )
    assert recovered_completion["idempotent_replay"] is True
    assert recovered_completion["changed"] is False

    replayed_output = io.StringIO()
    with contextlib.redirect_stdout(replayed_output):
        replayed_exit_code = cli_main(
            [
                *argv[:-1],
                "--resume-turn-key",
                payload["resume_turn_key"],
                "--execute",
            ]
        )
    replayed = json.loads(replayed_output.getvalue())
    assert replayed_exit_code == 0, replayed
    assert replayed["replayed"] is True
    assert not any(replayed["effects"].values())


def test_turn_run_once_cli_fails_closed_before_host_on_lease_conflict(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key="turn:competing-worker",
        write_scopes=["docs/**"],
    )
    host_script = """
import json
import pathlib
import sys
request = json.load(sys.stdin)
pathlib.Path("host-invoked.txt").write_text("invoked", encoding="utf-8")
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "wait",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "fixture_wait",
    "recommended_action": "Wait",
    "next_action": "Wait",
    "delivery_batch_scale": "single_surface",
    "delivery_outcome": "outcome_noop",
    "vision_unchanged_reason": "The fixture is unchanged.",
    "summary": "No work was attempted."
}, sys.stdout)
"""
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-adapter-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1, payload
    assert payload["status"] == "failed_closed"
    assert payload["reason_code"] == "todo_lease_conflict"
    assert payload["effects"]["host_invoked"] is False
    assert not (host_project / "host-invoked.txt").exists()
    lease = read_lease(
        task_lease_path(
            runtime_root=runtime,
            goal_id="loopx-turn-fixture",
            todo_id="todo_fixture0001",
        )
    )
    assert lease is not None
    assert lease["status"] == "active"
    assert lease["idempotency_key"] == "turn:competing-worker"


def test_remote_turn_cli_journal_and_effects_share_one_lease_fence(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    envelope = _envelope()
    envelope["goal_id"] = "loopx-turn-fixture"
    plan = build_loopx_turn_plan(
        envelope,
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    turn_key = str(transaction["turn_key"])
    idempotency_key = f"turn:{turn_key}"
    acquired = acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=idempotency_key,
        write_scopes=["docs/**"],
    )
    lease = acquired["lease"]
    assert isinstance(lease, dict)
    fencing_token = task_lease_fencing_token(lease)
    event_request = {
        "event_type": "turn_owned",
        "phase_key": f"{turn_key}:ownership:1",
        "fencing": {
            "todo_id": "todo_fixture0001",
            "owner": "codex-fixture",
            "idempotency_key": idempotency_key,
            "token": fencing_token,
        },
        "payload": {"phase": "ownership"},
    }

    append_output = io.StringIO()
    with contextlib.redirect_stdout(append_output):
        append_exit = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "journal-append",
                "--goal-id",
                "loopx-turn-fixture",
                "--turn-key",
                turn_key,
                "--event-json",
                json.dumps(event_request),
            ]
        )
    appended = json.loads(append_output.getvalue())
    assert append_exit == 0, appended
    assert appended["event"]["phase_key"] == event_request["phase_key"]

    read_output = io.StringIO()
    with contextlib.redirect_stdout(read_output):
        read_exit = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "journal-read",
                "--goal-id",
                "loopx-turn-fixture",
                "--turn-key",
                turn_key,
            ]
        )
    readback = json.loads(read_output.getvalue())
    assert read_exit == 0, readback
    assert readback["event_count"] == 1

    fence_args = [
        "--turn-fence-todo-id",
        "todo_fixture0001",
        "--turn-fence-idempotency-key",
        idempotency_key,
        "--turn-fencing-token",
        fencing_token,
    ]
    writeback_key = f"{turn_key}:durable_writeback"
    refresh_argv = [
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "refresh-state",
        "--goal-id",
        "loopx-turn-fixture",
        "--classification",
        "fixture_remote_turn_progress",
        "--recommended-action",
        "Continue the fixture.",
        "--next-action",
        "Run the next bounded fixture Turn.",
        "--delivery-batch-scale",
        "single_surface",
        "--delivery-outcome",
        "outcome_progress",
        "--agent-id",
        "codex-fixture",
        "--progress-scope",
        "goal",
        "--vision-unchanged-reason",
        "The fixture objective remains open.",
        "--no-global-sync",
        "--turn-effect-key",
        writeback_key,
        *fence_args,
    ]
    refresh_payloads: list[dict[str, object]] = []
    for _ in range(2):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli_main(refresh_argv)
        payload = json.loads(output.getvalue())
        assert exit_code == 0, payload
        refresh_payloads.append(payload)
    assert refresh_payloads[0]["appended"] is True
    assert refresh_payloads[1]["appended"] is False
    assert refresh_payloads[1]["idempotent_replay"] is True

    spend_key = f"{turn_key}:quota_spend"
    spend_argv = [
        "--registry",
        str(registry),
        "--runtime-root",
        str(runtime),
        "--format",
        "json",
        "quota",
        "spend-slot",
        "--goal-id",
        "loopx-turn-fixture",
        "--agent-id",
        "codex-fixture",
        "--source",
        "adapter",
        "--execute",
        "--scan-root",
        str(project),
        "--turn-effect-key",
        spend_key,
        *fence_args,
    ]
    spend_payloads: list[dict[str, object]] = []
    for _ in range(2):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exit_code = cli_main(spend_argv)
        payload = json.loads(output.getvalue())
        assert exit_code == 0, payload
        spend_payloads.append(payload)
    assert spend_payloads[0]["appended"] is True
    assert spend_payloads[1]["appended"] is False
    assert spend_payloads[1]["idempotent_replay"] is True

    release_task_lease(
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=idempotency_key,
        expected_version=int(lease["version"]),
    )
    acquire_task_lease(
        registry_path=registry,
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key="turn:replacement-worker",
        write_scopes=["docs/**"],
    )
    stale_output = io.StringIO()
    stale_argv = [
        *refresh_argv,
        "--classification",
        "fixture_stale_write_must_not_append",
        "--turn-effect-key",
        f"{turn_key}:stale_writeback",
    ]
    with contextlib.redirect_stdout(stale_output):
        stale_exit = cli_main(stale_argv)
    stale = json.loads(stale_output.getvalue())
    assert stale_exit == 1, stale
    assert stale["appended"] is False
    assert "stale" in str(stale["error"]).lower()


def test_turn_run_once_cli_rejects_execute_without_selected_todo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from loopx.cli_commands.turn import build_turn_envelope as real_build_turn_envelope

    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()

    def envelope_without_selected_todo(
        *args: object,
        **kwargs: object,
    ) -> dict[str, object]:
        envelope = real_build_turn_envelope(*args, **kwargs)
        action = envelope.get("action")
        assert isinstance(action, dict)
        action.pop("selected_todo", None)
        return envelope

    monkeypatch.setattr(
        "loopx.cli_commands.turn.build_turn_envelope",
        envelope_without_selected_todo,
    )
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-adapter-command-json",
                json.dumps([sys.executable, "-c", "raise SystemExit(9)"]),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1, payload
    assert payload["effects"]["host_invoked"] is False
    assert "requires one selected todo" in payload["error"]
    assert not (runtime / "goals" / "loopx-turn-fixture" / "task-leases").exists()


def test_turn_run_once_commits_independently_validated_progress(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    envelope = _envelope()
    envelope["goal_id"] = "loopx-turn-fixture"
    plan = build_loopx_turn_plan(
        envelope,
        host="generic-cli",
        execution_mode="isolated-headless",
    )
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    turn_key = str(transaction["turn_key"])
    lease_controller = TurnLeaseController(
        registry_path=registry,
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=f"turn:{turn_key}",
        write_scopes=["docs/**"],
    )

    def host_runner(request: dict[str, object]) -> dict[str, object]:
        return {
            "schema_version": "loopx_turn_result_v0",
            "turn_key": request["turn_key"],
            "result_kind": "validated_progress",
            "completed_phases": ["host_execute", "typed_result"],
            "classification": "fixture_intermediate_progress",
            "recommended_action": "Continue the fixture",
            "next_action": "Run the next bounded fixture Turn",
            "delivery_batch_scale": "single_surface",
            "delivery_outcome": "outcome_progress",
            "vision_unchanged_reason": "The fixture objective remains open.",
            "summary": "One intermediate fixture step passed validation.",
        }

    execution = run_loopx_turn_once(
        plan,
        host_runner=host_runner,
        project=project,
        runtime_root=runtime,
        goal_id="loopx-turn-fixture",
        timeout_seconds=10,
        execute=True,
        task_validator=lambda _plan, _result: {
            "status": "progress",
            "validator_kind": "fixture",
            "summary": "intermediate fixture progress is independently valid",
            "exit_code": 10,
        },
        writeback=lambda _effect, _result: {"ok": True, "appended": True},
        spend=lambda _effect: {"ok": True, "appended": True, "slots": 1},
        scheduler=lambda _effect, _spend: {
            "disposition": "outer_controller_owned",
            "completed": True,
            "acknowledged": False,
            "apply_needed": False,
        },
        lease_controller=lease_controller,
    )

    assert execution["status"] == "committed"
    assert execution["validation"]["status"] == "progress"
    assert execution["validation"]["exit_code"] == 10
    assert execution["quota_slot_spend_count"] == 1
    assert loopx_turn_execution_committed(execution) is True


def test_turn_run_once_cli_rejects_unproven_host_claim_before_writeback(
    tmp_path: Path,
) -> None:
    project, runtime, registry = _write_live_fixture(tmp_path)
    host_project = tmp_path / "isolated-host-workspace"
    host_project.mkdir()
    host_script = """
import json
import sys
request = json.load(sys.stdin)
json.dump({
    "schema_version": "loopx_turn_result_v0",
    "turn_key": request["turn_key"],
    "result_kind": "validated_progress",
    "completed_phases": ["host_execute", "typed_result"],
    "classification": "unproven_fixture_progress",
    "recommended_action": "Continue the public fixture",
    "next_action": "Run the next public fixture check",
    "delivery_batch_scale": "implementation",
    "delivery_outcome": "outcome_progress",
    "vision_unchanged_reason": "The fixture objective remains unchanged.",
    "summary": "The host claims a missing artifact."
}, sys.stdout)
"""
    validation_script = """
import json
import pathlib
import sys
json.load(sys.stdin)
raise SystemExit(0 if pathlib.Path("claimed-artifact.txt").is_file() else 9)
"""
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    before_state = state_path.read_text(encoding="utf-8")
    output = io.StringIO()

    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--project",
                str(host_project),
                "--host-command-json",
                json.dumps([sys.executable, "-c", host_script]),
                "--validation-command-json",
                json.dumps([sys.executable, "-c", validation_script]),
                "--validation-failure-kind",
                "replan_required",
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 1, payload
    assert payload["status"] == "failed"
    assert payload["result_kind"] == "validation_failed"
    assert payload["validation"]["status"] == "failed"
    assert payload["validation"]["recovery_kind"] == "replan_required"
    assert payload["validation"]["exit_code"] == 9
    assert payload["effects"]["host_invoked"] is True
    assert payload["effects"]["state_written"] is False
    assert payload["effects"]["quota_spent"] is False
    assert state_path.read_text(encoding="utf-8") == before_state
    assert not (runtime / "goals" / "loopx-turn-fixture" / "runs").exists()
    lease = read_lease(
        task_lease_path(
            runtime_root=runtime,
            goal_id="loopx-turn-fixture",
            todo_id="todo_fixture0001",
        )
    )
    assert lease is not None
    assert lease["status"] == "active"
    assert lease["owner"] == "codex-fixture"
    assert lease["idempotency_key"] == f"turn:{payload['resume_turn_key']}"


@pytest.mark.parametrize(
    "result_kind", ["validated_progress", "repair_required", "replan_required"]
)
def test_turn_run_once_cli_uses_built_in_codex_host_and_typed_writeback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    result_kind: str,
) -> None:
    from loopx.cli_commands.turn import (
        build_turn_envelope as real_build_turn_envelope,
        refresh_state_run as real_refresh_state_run,
        spend_quota_slot as real_spend_quota_slot,
        update_goal_todo as real_update_goal_todo,
    )

    project, runtime, registry = _write_live_fixture(tmp_path)
    state_path = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    )
    state_path.write_text(
        state_path.read_text(encoding="utf-8").replace(
            "priority=P0 -->",
            "task_repository=git:example.invalid/loopx/turn-fixture priority=P0 -->",
        ),
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "init", "--initial-branch", "main", str(project)],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "remote",
            "add",
            "origin",
            "https://example.invalid/loopx/turn-fixture.git",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    refresh_workspace_paths: list[Path | None] = []
    spend_workspace_paths: list[Path | None] = []
    updated_todo_ids: list[str] = []

    def adaptive_turn_envelope(*args: object, **kwargs: object) -> dict[str, object]:
        envelope = real_build_turn_envelope(*args, **kwargs)
        primary_todo = dict(envelope["action"]["selected_todo"])
        envelope["action"]["selected_todo"] = {
            "todo_id": "todo_stale_selection",
            "text": "A stale pre-orchestration selection",
        }
        envelope["task_orchestration_contract"] = {
            "schema_version": "task_orchestration_contract_v2",
            "mode": "adaptive",
            "primary_todo_id": "todo_fixture0001",
            "primary_todo": {
                **primary_todo,
                "source": "task_orchestration_contract.primary_todo",
            },
            "eligible_child_lanes": [],
        }
        return envelope

    def recording_refresh_state_run(*args: object, **kwargs: object) -> dict[str, object]:
        refresh_workspace_paths.append(kwargs.get("delivery_workspace_path"))
        return real_refresh_state_run(*args, **kwargs)

    def recording_spend_quota_slot(*args: object, **kwargs: object) -> dict[str, object]:
        spend_workspace_paths.append(kwargs.get("workspace_path"))
        return real_spend_quota_slot(*args, **kwargs)

    def recording_update_goal_todo(*args: object, **kwargs: object) -> dict[str, object]:
        updated_todo_ids.append(str(kwargs.get("todo_id") or ""))
        return real_update_goal_todo(*args, **kwargs)

    def fake_codex_host(request: dict[str, object], **_kwargs: object) -> dict[str, object]:
        return {
            "schema_version": "loopx_turn_result_v0",
            "turn_key": request["turn_key"],
            "result_kind": result_kind,
            "completed_phases": ["host_execute", "typed_result"],
            "classification": f"fixture_{result_kind}",
            "recommended_action": "Apply the typed follow-up",
            "next_action": "Run one revised public fixture check",
            "delivery_batch_scale": "implementation",
            "delivery_outcome": "outcome_progress",
            "vision_unchanged_reason": "The fixture objective remains unchanged.",
            "summary": "One public fixture advanced.",
        }

    monkeypatch.setattr("loopx.cli_commands.turn.run_codex_cli_host", fake_codex_host)
    monkeypatch.setattr(
        "loopx.cli_commands.turn.build_turn_envelope",
        adaptive_turn_envelope,
    )
    monkeypatch.setattr(
        "loopx.cli_commands.turn.refresh_state_run",
        recording_refresh_state_run,
    )
    monkeypatch.setattr(
        "loopx.cli_commands.turn.spend_quota_slot",
        recording_spend_quota_slot,
    )
    monkeypatch.setattr(
        "loopx.cli_commands.turn.update_goal_todo",
        recording_update_goal_todo,
    )
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        exit_code = cli_main(
            [
                "--registry",
                str(registry),
                "--runtime-root",
                str(runtime),
                "--format",
                "json",
                "turn",
                "run-once",
                "--goal-id",
                "loopx-turn-fixture",
                "--agent-id",
                "codex-fixture",
                "--host",
                "codex-cli",
                "--project",
                str(project),
                "--validation-command-json",
                json.dumps(
                    [
                        sys.executable,
                        "-c",
                        "import json, sys; json.load(sys.stdin)",
                    ]
                ),
                "--scan-root",
                str(project),
                "--no-global-sync",
                "--execute",
            ]
        )

    payload = json.loads(output.getvalue())
    assert exit_code == 0, payload
    assert payload["host"] == {"executable": "built-in", "kind": "codex-cli"}
    assert payload["effects"]["state_written"] is True
    assert payload["effects"]["quota_spent"] is True
    assert refresh_workspace_paths == [project]
    assert spend_workspace_paths == [project]
    assert updated_todo_ids == (
        [] if result_kind == "validated_progress" else ["todo_fixture0001"]
    )
    lease = read_lease(
        task_lease_path(
            runtime_root=runtime,
            goal_id="loopx-turn-fixture",
            todo_id="todo_fixture0001",
        )
    )
    assert lease is not None
    assert lease["write_scopes"] == ["docs/**"]
    state = (
        project
        / ".codex"
        / "goals"
        / "loopx-turn-fixture"
        / "ACTIVE_GOAL_STATE.md"
    ).read_text(encoding="utf-8")
    assert "Run one revised public fixture check" in state
    if result_kind != "validated_progress":
        assert f"LoopX%20Turn%20{result_kind}" in state
