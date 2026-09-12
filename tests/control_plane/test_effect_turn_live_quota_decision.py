from __future__ import annotations

import json
from pathlib import Path

from loopx.control_plane.effect_program import (
    interpret_quota_should_run_packet,
)
from loopx.control_plane.capability_hooks import (
    TURN_START_HOOK_RESULT_SCHEMA_VERSION,
    TurnStartHookRegistration,
    dispatch_turn_start_hooks,
)
from loopx.control_plane.quota.live_decision import (
    bind_action_selection_cli_routes,
    build_live_quota_should_run_decision,
)
from loopx.control_plane.testing.quota_fixtures import quota_status_payload
from loopx.rollout_event_log import build_rollout_event

GOAL_ID = "effect-interpreter-fixture"


def _turn_start_dispatch(
    *,
    required: bool = True,
    observation_count: int = 1,
    commands: tuple[str, ...] = ("loopx inbox drain --goal-id fixture",),
) -> dict[str, object]:
    hooks: list[TurnStartHookRegistration] = []
    for index, command in enumerate(commands):
        hook_id = f"operator_inbox.turn_start_sync_{index}"

        def produce(
            *, hook_id: str = hook_id, required: bool = required
        ) -> dict[str, object]:
            return {
                "schema_version": TURN_START_HOOK_RESULT_SCHEMA_VERSION,
                "hook_id": hook_id,
                "capability_id": "operator-inbox",
                "phase": "turn_start",
                "status": "observed" if required else "empty",
                "observation_count": observation_count if required else 0,
                "agent_read_required": required,
                "external_reads_performed": True,
                "external_writes_performed": False,
                "local_private_state_mutated": required,
                "private_content_returned": False,
                "provider_payload_returned": False,
                "error_code": None,
            }

        hooks.append(
            TurnStartHookRegistration(
                hook_id=hook_id,
                capability_id="operator-inbox",
                requested_read_scope=("provider_history",),
                requested_write_scope=("owner_private_inbox",),
                producer=produce,
                required_read={
                    "kind": "operator_inbox",
                    "command": command,
                    "reason": "turn-start hook synchronized new operator inbox evidence",
                    "ordering": "before_work",
                },
            )
        )
    return dispatch_turn_start_hooks(hooks)


def _ordinary_status_payload() -> dict[str, object]:
    todo_text = "[P1] Keep advancing the selected task."
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        agent_todo_items=[
            {
                "todo_id": "todo_ordinary_work",
                "index": 1,
                "text": todo_text,
                "role": "agent",
                "status": "open",
                "priority": "P1",
                "task_class": "advancement_task",
            }
        ],
        recommended_action=todo_text,
        next_action=todo_text,
    )


def _material_review_urgency(
    *, reply_due: bool = False, pending_count: int = 1, **_kwargs: object
) -> dict[str, object]:
    return {
        "schema_version": "operator_inbox_urgency_v0",
        "enabled": True,
        "pending_count": pending_count,
        "attention_required_count": int(reply_due),
        "reply_due": reply_due,
        "material_review_count": 1,
        "material_attachment_count": 0,
        "material_review_due": True,
        "material_review_drain_limit": 20,
        "local_private_content_returned": False,
    }


def _inbox_goal(tmp_path: Path) -> dict[str, object]:
    return {
        "id": GOAL_ID,
        "registry_member": True,
        "status": "active",
        "adapter_kind": "harness_self_improvement",
        "adapter_status": "connected-read-only",
        "repo": str(tmp_path),
        "quota": {"compute": 1.0, "window_hours": 24},
        "control_plane": {
            "lark_event_inbox": {
                "enabled": True,
                "config_path": ".loopx/config/lark/inbox.json",
            }
        },
    }


def _status_with_inbox(tmp_path: Path) -> dict[str, object]:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps({"goals": [_inbox_goal(tmp_path)]}),
        encoding="utf-8",
    )
    return _ordinary_status_payload() | {"registry": str(registry_path)}


def test_live_quota_decision_maps_to_effect_turn(tmp_path: Path) -> None:
    todo_text = "[P1] Advance the bounded slice."
    payload = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        agent_todo_items=[
            {
                "index": 1,
                "text": todo_text,
                "role": "agent",
                "status": "open",
                "priority": "P1",
                "task_class": "advancement_task",
            }
        ],
        recommended_action=todo_text,
        next_action=todo_text,
    )
    packet = build_live_quota_should_run_decision(
        payload,
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        scheduler_execution_context={
            "host_surface": "generic_cli",
            "scheduler_owner": "agent_cli_loop",
            "execution_mode": "interactive",
        },
    )
    turn = interpret_quota_should_run_packet(
        packet,
        goal_id=GOAL_ID,
        agent_id="codex-fixture",
        capabilities=["shell"],
    )

    assert turn.observation.decision == "run"
    assert turn.observation.effective_action == "normal_run"
    assert turn.interpretation.route == "advancement_task"
    assert turn.interpretation.obligation == "advance_one_bounded_segment"
    assert turn.interpretation.interaction_mode == "bounded_delivery"
    assert turn.next_effect.cli_actions
    assert turn.next_effect.cli_actions[0].startswith("loopx --runtime-root ")


def test_managed_turn_projects_prior_unsettled_heartbeat_recovery(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "runtime"
    agent_id = "codex-fixture"
    todo_id = "todo_ordinary_work"
    prior_turn_id = "managed-prior-turn"
    event = build_rollout_event(
        goal_id=GOAL_ID,
        event_kind="quota_should_run",
        agent_id=agent_id,
        todo_id=todo_id,
        run_id=prior_turn_id,
        status="normal_run",
        summary="managed heartbeat guard requires closeout",
        details={
            "todo_id": todo_id,
            "settlement_effect_id": (
                f"{GOAL_ID}:{agent_id}:{todo_id}:{prior_turn_id}"
            ),
            "closeout_required": True,
        },
    )
    log_path = runtime_root / "goals" / GOAL_ID / "rollout-event-log.jsonl"
    log_path.parent.mkdir(parents=True)
    log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    todo_text = "[P1] Keep advancing the selected task."
    status = quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        agent_todo_items=[
            {
                "todo_id": todo_id,
                "index": 1,
                "text": todo_text,
                "role": "agent",
                "status": "open",
                "priority": "P1",
                "task_class": "advancement_task",
            }
        ],
        recommended_action=todo_text,
        next_action=todo_text,
        coordination={
            "registered_agents": [agent_id],
            "agent_model": "peer_v1",
        },
        claim_scope_agent_id=agent_id,
    )
    packet = build_live_quota_should_run_decision(
        status,
        goal_id=GOAL_ID,
        agent_id=agent_id,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=runtime_root,
        route_source="loopx_turn_plan",
        turn_instance_id="managed-current-turn",
        scheduler_execution_context={
            "host_surface": "generic_cli",
            "scheduler_owner": "agent_cli_loop",
            "execution_mode": "interactive",
        },
    )

    assert packet["runtime_root"] == str(runtime_root)
    assert packet["effective_action"] == "unsettled_host_turn_recovery"
    assert packet["unsettled_host_turn_recovery"]["prior_turn_instance_id"] == (
        prior_turn_id
    )
    contract = packet["interaction_contract"]
    assert contract["mode"] == "unsettled_host_turn_recovery"
    assert contract["agent_channel"]["delivery_allowed"] is False
    assert contract["cli_channel"]["spend_after_validation"] is False


def test_action_selection_route_binding_fails_closed_on_malformed_prefix(
    tmp_path: Path,
) -> None:
    payload = {
        "interaction_contract": {
            "cli_channel": {
                "selection_required": True,
                "selection_command": {"route_prefix": "loopx --runtime-root /tmp"},
            }
        }
    }

    bind_action_selection_cli_routes(
        payload,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
    )

    assert payload["interaction_contract"]["cli_channel"]["selection_command"][
        "route_prefix"
    ] == "loopx --runtime-root /tmp"


def test_turn_start_read_is_required_before_ordinary_work(tmp_path: Path) -> None:
    status = _ordinary_status_payload()
    baseline = build_live_quota_should_run_decision(
        status,
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
    )
    packet = build_live_quota_should_run_decision(
        status,
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        turn_start_hook_dispatch=_turn_start_dispatch(
            commands=(
                f"loopx --registry {tmp_path / 'registry.json'} "
                f"lark-inbox drain --goal-id {GOAL_ID}",
            )
        ),
    )

    required_reads = packet["interaction_contract"]["agent_channel"]["required_reads"]
    assert (
        required_reads
        == packet["interaction_contract"]["cli_channel"]["required_reads"]
    )
    assert required_reads == [
        {
            "kind": "operator_inbox",
            "command": (
                f"loopx --registry {tmp_path / 'registry.json'} "
                f"lark-inbox drain --goal-id {GOAL_ID}"
            ),
            "reason": "turn-start hook synchronized new operator inbox evidence",
            "source": "turn_start_capability_hook",
            "ordering": "before_work",
        }
    ]
    assert packet["interaction_contract"]["user_channel"]["notify"] == "NOTIFY"
    assert packet["interaction_contract"]["user_channel"]["action_required"] is False
    assert packet.get("selected_todo") == baseline.get("selected_todo")
    assert (
        packet["agent_todo_summary"]["first_executable_items"]
        == baseline["agent_todo_summary"]["first_executable_items"]
    )
    assert packet["recommended_action"] == baseline["recommended_action"]
    assert packet["effective_action"] == baseline["effective_action"] == "normal_run"


def test_fresh_turn_start_read_notifies_without_preempting_selected_work(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.quota.goal_boundary.operator_inbox_binding",
        lambda **_kwargs: {
            "status": "verified",
            "attention_required": False,
        },
    )
    status = _status_with_inbox(tmp_path)
    baseline = build_live_quota_should_run_decision(
        status,
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
    )
    packet = build_live_quota_should_run_decision(
        status,
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        operator_inbox_urgency_projector=_material_review_urgency,
        turn_start_hook_dispatch=_turn_start_dispatch(),
    )

    assert packet["effective_action"] == baseline["effective_action"] == "normal_run"
    assert packet.get("selected_todo") == baseline.get("selected_todo")
    assert packet["recommended_action"] == baseline["recommended_action"]
    assert packet["interaction_contract"]["user_channel"]["notify"] == "NOTIFY"
    assert packet["interaction_contract"]["user_channel"]["action_required"] is False
    assert packet["interaction_contract"]["agent_channel"]["required_reads"]


def test_unsettled_inbox_material_preempts_on_following_turn(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.quota.goal_boundary.operator_inbox_binding",
        lambda **_kwargs: {
            "status": "verified",
            "attention_required": False,
        },
    )
    packet = build_live_quota_should_run_decision(
        _status_with_inbox(tmp_path),
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        operator_inbox_urgency_projector=_material_review_urgency,
        turn_start_hook_dispatch=_turn_start_dispatch(required=False),
    )

    assert packet["effective_action"] == "operator_inbox_material_review_due"
    assert packet["work_lane_contract"]["priority_preemption"] is True
    assert "required_reads" not in packet["interaction_contract"]["agent_channel"]


def test_fresh_direct_reply_still_preempts_selected_work(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.quota.goal_boundary.operator_inbox_binding",
        lambda **_kwargs: {
            "status": "verified",
            "attention_required": False,
        },
    )
    packet = build_live_quota_should_run_decision(
        _status_with_inbox(tmp_path),
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        operator_inbox_urgency_projector=(
            lambda **kwargs: _material_review_urgency(reply_due=True, **kwargs)
        ),
        turn_start_hook_dispatch=_turn_start_dispatch(),
    )

    assert packet["effective_action"] == "lark_inbox_reply_due"
    assert packet["work_lane_contract"]["priority_preemption"] is True
    assert packet["interaction_contract"]["agent_channel"]["required_reads"]


def test_fresh_read_does_not_hide_older_unsettled_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.quota.goal_boundary.operator_inbox_binding",
        lambda **_kwargs: {
            "status": "verified",
            "attention_required": False,
        },
    )
    packet = build_live_quota_should_run_decision(
        _status_with_inbox(tmp_path),
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        operator_inbox_urgency_projector=(
            lambda **kwargs: _material_review_urgency(
                pending_count=2,
                **kwargs,
            )
        ),
        turn_start_hook_dispatch=_turn_start_dispatch(observation_count=1),
    )

    assert packet["effective_action"] == "operator_inbox_material_review_due"
    assert packet["work_lane_contract"]["priority_preemption"] is True
    assert packet["interaction_contract"]["agent_channel"]["required_reads"]


def test_non_inbox_hook_observations_do_not_mask_unsettled_inbox_material(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "loopx.control_plane.quota.goal_boundary.operator_inbox_binding",
        lambda **_kwargs: {
            "status": "verified",
            "attention_required": False,
        },
    )
    dispatch = _turn_start_dispatch(observation_count=1)
    dispatch["results"].append(
        {
            "hook_id": "repository.turn_start_sync",
            "capability_id": "repository",
            "agent_read_required": True,
            "observation_count": 10,
        }
    )
    dispatch["required_reads"].append(
        {
            "kind": "repository",
            "command": "git status --short",
            "reason": "read repository state",
            "ordering": "before_work",
            "source": "turn_start_capability_hook",
            "hook_id": "repository.turn_start_sync",
            "capability_id": "repository",
        }
    )

    packet = build_live_quota_should_run_decision(
        _status_with_inbox(tmp_path),
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        operator_inbox_urgency_projector=(
            lambda **kwargs: _material_review_urgency(
                pending_count=2,
                **kwargs,
            )
        ),
        turn_start_hook_dispatch=dispatch,
    )

    assert packet["effective_action"] == "operator_inbox_material_review_due"
    assert packet["work_lane_contract"]["priority_preemption"] is True


def test_turn_start_read_is_not_projected_for_empty_or_failed_dispatch(
    tmp_path: Path,
) -> None:
    status = _ordinary_status_payload()
    dispatches = [
        _turn_start_dispatch(required=False),
        {
            "registered_count": 1,
            "invoked_count": 0,
            "results": [],
            "failures": [
                {
                    "hook_id": "lark.turn_start_inbox_sync",
                    "capability_id": "lark-event-inbox",
                    "error_code": "producer_failed",
                }
            ],
        },
    ]

    for dispatch in dispatches:
        packet = build_live_quota_should_run_decision(
            status,
            goal_id=GOAL_ID,
            agent_id=None,
            available_capabilities=["shell"],
            include_scheduler_detail=False,
            codex_app_current_rrule=None,
            registry_path=tmp_path / "registry.json",
            runtime_root=tmp_path / "runtime",
            turn_start_hook_dispatch=dispatch,
        )

        assert "required_reads" not in packet["interaction_contract"]["agent_channel"]
        assert "required_reads" not in packet["interaction_contract"]["cli_channel"]


def test_duplicate_required_inbox_routes_project_one_public_safe_read(
    tmp_path: Path,
) -> None:
    command = "loopx lark-inbox drain --goal-id fixture"
    dispatch = _turn_start_dispatch(commands=(command, command))
    packet = build_live_quota_should_run_decision(
        _ordinary_status_payload(),
        goal_id=GOAL_ID,
        agent_id=None,
        available_capabilities=["shell"],
        include_scheduler_detail=False,
        codex_app_current_rrule=None,
        registry_path=tmp_path / "registry.json",
        runtime_root=tmp_path / "runtime",
        turn_start_hook_dispatch=dispatch,
    )

    assert len(packet["required_reads"]) == 1
    assert packet["required_reads"][0]["command"] == command
