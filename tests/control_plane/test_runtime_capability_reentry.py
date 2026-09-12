from __future__ import annotations

import json

from loopx.control_plane.quota.cli_projection import (
    compact_quota_should_run_cli_payload,
)
from loopx.control_plane.scheduler.execution_context import (
    scheduler_execution_context_for_runtime_profile,
)
from loopx.control_plane.work_items.interaction_contract import (
    build_interaction_contract,
)


GOAL_ID = "runtime-capability-reentry-fixture"
AGENT_ID = "managed-agent"
MANAGED_AGENT_CONTEXT = scheduler_execution_context_for_runtime_profile(
    "ark_managed_agent_goal"
)


def _blocked_payload(*, missing: list[str]) -> dict:
    return {
        "goal_id": GOAL_ID,
        "agent_identity": {
            "agent_id": AGENT_ID,
            "agent_model": "peer_v1",
        },
        "should_run": True,
        "effective_action": "capability_bridge_repair",
        "execution_obligation": {
            "must_attempt_work": True,
            "delivery_allowed": False,
        },
        "heartbeat_recommendation": {
            "recommended_mode": "repair_capability_bridge",
        },
        "capability_gate": {
            "action": "repair_bridge",
            "repair_missing": missing,
            "owner_missing": [],
            "resolution_bindings": [
                {
                    "owner": "agent",
                    "action": "repair_bridge",
                    "capability": capability,
                    "priority": "P0",
                    "primary_blocked_todo_id": "todo_blocked",
                    "blocked_todo_ids": ["todo_blocked"],
                }
                for capability in missing
            ],
            "blocked_candidates": [
                {
                    "todo_id": "todo_blocked",
                    "action_kind": "inspect_target",
                    "target_key": "fixture/target.json",
                    "text": "[P0] Inspect fixture/target.json.",
                    "required_capabilities": missing,
                }
            ],
            "runnable_candidates": [],
        },
    }


def test_runtime_capability_gap_returns_verified_reentry_packet() -> None:
    contract = build_interaction_contract(
        _blocked_payload(missing=["network"]),
        available_capabilities=["shell"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )

    reentry = contract["cli_channel"]["runtime_capability_reentry"]
    assert contract["agent_channel"]["primary_action"] == (
        "execute interaction_contract.agent_channel.next_task_action.operation "
        "once with its real task-facing tool and exact target_ref when projected; "
        "preflight_allowed is false, and the instruction is context rather than "
        "CLI text; on success "
        "execute cli_channel."
        "next_cli_actions[0] in the same turn and continue only when quota allows"
    )
    assert contract["agent_channel"]["next_task_action"] == {
        "kind": "capability_verification",
        "capability": "network",
        "todo_id": "todo_blocked",
        "action_kind": "inspect_target",
        "operation": "inspect_target",
        "instruction": "[P0] Inspect fixture/target.json.",
        "target_ref": "fixture/target.json",
        "preflight_allowed": False,
        "advancement_checkpoint": False,
        "settles_turn": False,
        "continuation_cli_action_index": 0,
    }
    assert reentry["schema_version"] == "runtime_capability_reentry_v0"
    assert reentry["state"] == "verification_required"
    assert reentry["verification_contract"] == {
        "scope": "real_task_facing_callsite_for_blocked_todo",
        "ordinary_delivery_allowed": False,
        "advancement_checkpoint": False,
        "settles_turn": False,
        "on_success": "rerun_quota_in_same_turn_then_continue_if_allowed",
        "on_failure": "record_exact_blocker_without_capability_flag",
    }
    assert reentry["inheritance_contract"] == {
        "source_invocation": "verified quota should-run reentry",
        "propagates_to": [
            "interaction_contract.cli_channel.next_cli_actions",
            "quota spend-slot",
            "quota monitor-poll",
        ],
        "session_scoped": False,
        "observation_scope": "host_registry_goal_agent",
        "remembers": ["benchmark_runner", "network", "external_evidence_poll", "worker_bridge", "cli_bridge"],
        "durable_grant_written": False,
    }
    candidate = reentry["candidates"][0]
    assert candidate["capability"] == "network"
    assert candidate["verification_required"] == (
        "successful_real_callsite_observation"
    )
    assert candidate["verification_target"] == {
        "todo_id": "todo_blocked",
        "action_kind": "inspect_target",
        "instruction": "[P0] Inspect fixture/target.json.",
        "target_ref": "fixture/target.json",
    }
    assert candidate["command"] == (
        "loopx --format json quota should-run --goal-id "
        f"{GOAL_ID} --agent-id {AGENT_ID} --available-capability shell "
        "--available-capability network --runtime-profile ark_managed_agent_goal"
    )
    assert contract["cli_channel"]["next_cli_actions"] == [candidate["command"]]
    assert contract["cli_channel"]["spend_after_validation"] is False
    assert contract["cli_channel"]["spend_policy"] == (
        "no spend or advancement checkpoint for capability verification; rerun "
        "quota in the same turn"
    )
    assert all(
        "todo add" not in action
        and "refresh-state" not in action
        and "spend-slot" not in action
        for action in contract["cli_channel"]["next_cli_actions"]
    )


def test_runtime_capability_reentry_preserves_visible_goal_turn() -> None:
    turn_instance_id = "guided-start:fixture-turn"
    contract = build_interaction_contract(
        _blocked_payload(missing=["network"]),
        available_capabilities=["shell"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
        turn_instance_id=turn_instance_id,
    )

    candidate = contract["cli_channel"]["runtime_capability_reentry"][
        "candidates"
    ][0]
    assert candidate["command"] == (
        "loopx --format json quota should-run --goal-id "
        f"{GOAL_ID} --agent-id {AGENT_ID} "
        f"--turn-instance-id {turn_instance_id} "
        "--available-capability shell --available-capability network "
        "--runtime-profile ark_managed_agent_goal"
    )
    assert contract["cli_channel"]["next_cli_actions"] == [candidate["command"]]


def test_runtime_capability_reentry_keeps_runtime_root() -> None:
    runtime_root = "/tmp/loopx-runtime-capability-reentry"
    contract = build_interaction_contract(
        _blocked_payload(missing=["network"]),
        available_capabilities=["shell"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
        turn_instance_id="guided-start:fixture-turn",
        runtime_root=runtime_root,
    )

    candidate = contract["cli_channel"]["runtime_capability_reentry"][
        "candidates"
    ][0]
    assert candidate["command"].startswith(f"loopx --runtime-root {runtime_root} ")
    assert contract["cli_channel"]["next_cli_actions"] == [candidate["command"]]


def test_runtime_capability_reentry_does_not_switch_from_selected_todo() -> None:
    payload = {
        **_blocked_payload(missing=["network"]),
        "effective_action": "bounded_delivery",
        "selected_todo": {
            "todo_id": "todo_selected",
            "task_class": "advancement_task",
        },
        "execution_obligation": {
            "must_attempt_work": True,
            "delivery_allowed": True,
        },
    }

    contract = build_interaction_contract(
        payload,
        available_capabilities=["shell"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )

    assert "runtime_capability_reentry" not in contract["cli_channel"]
    assert contract["agent_channel"].get("next_task_action") is None


def test_verified_reentry_inherits_capability_into_followup_actions() -> None:
    contract = build_interaction_contract(
        {
            **_blocked_payload(missing=[]),
            "effective_action": "bounded_delivery",
            "execution_obligation": {
                "must_attempt_work": True,
                "delivery_allowed": True,
            },
            "capability_gate": {
                "action": "run",
                "repair_missing": [],
                "owner_missing": [],
                "resolution_bindings": [],
                "runnable_candidates": [
                    {
                        "todo_id": "todo_network",
                        "target_capabilities": ["network"],
                    }
                ],
            },
        },
        available_capabilities=["network"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )

    assert "runtime_capability_reentry" not in contract["cli_channel"]
    actions = contract["cli_channel"]["next_cli_actions"]
    assert actions
    assert all(
        "--available-capability network" in action
        for action in actions
        if action.startswith("loopx refresh-state")
        or action.startswith("loopx quota spend-slot")
    )


def test_owner_capability_never_becomes_runtime_reentry_candidate() -> None:
    contract = build_interaction_contract(
        _blocked_payload(missing=["credentials"]),
        available_capabilities=[],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )

    assert "runtime_capability_reentry" not in contract["cli_channel"]


def test_quota_cli_promotes_reentry_before_large_diagnostics() -> None:
    contract = build_interaction_contract(
        _blocked_payload(missing=["network"]),
        available_capabilities=["shell"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )
    packet = contract["cli_channel"]["runtime_capability_reentry"]
    payload = {
        "ok": True,
        "status_health_ok": True,
        "mode": "should-run",
        "goal_id": GOAL_ID,
        "decision": "run",
        "should_run": True,
        "large_diagnostic": "x" * 20_000,
        "interaction_contract": contract,
    }

    projected = compact_quota_should_run_cli_payload(payload)
    rendered = json.dumps(projected, indent=2)

    assert projected["runtime_capability_reentry"] == packet
    assert rendered.index('"runtime_capability_reentry"') < 512
    assert rendered.index('"interaction_contract"') < 2_048
    assert rendered.index('"interaction_contract"') < rendered.index(
        '"large_diagnostic"'
    )
    assert rendered.index('"schema_version": "runtime_capability_reentry_v0"') < 1_024
    assert rendered.index('"large_diagnostic"') > rendered.index(
        '"runtime_capability_reentry"'
    )


def test_quota_cli_omits_reentry_projection_when_not_requested() -> None:
    contract = build_interaction_contract(
        {
            **_blocked_payload(missing=[]),
            "effective_action": "bounded_delivery",
        },
        available_capabilities=["network"],
        scheduler_execution_context=MANAGED_AGENT_CONTEXT,
    )

    projected = compact_quota_should_run_cli_payload(
        {
            "ok": True,
            "mode": "should-run",
            "goal_id": GOAL_ID,
            "interaction_contract": contract,
        }
    )

    assert "runtime_capability_reentry" not in projected
