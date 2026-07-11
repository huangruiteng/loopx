from __future__ import annotations

import json

from loopx.control_plane.quota.turn_envelope import (
    TURN_ENVELOPE_BUDGET_BYTES,
    build_turn_envelope,
    quota_action_signature_document,
    turn_envelope_action_signature_document,
)


def _full_decision() -> dict[str, object]:
    return {
        "ok": True,
        "goal_id": "fixture-goal",
        "decision": "run",
        "should_run": True,
        "effective_action": "normal_run",
        "state": "eligible",
        "normal_delivery_allowed": True,
        "recovery_delivery_allowed": False,
        "self_repair_allowed": False,
        "capability_repair_allowed": False,
        "workspace_repair_allowed": False,
        "safe_bypass_allowed": False,
        "reason": "eligible fixture",
        "action_required": False,
        "open_count": 0,
        "recommended_action": "implement one bounded public-safe slice",
        "agent_identity": {"agent_id": "codex-fixture"},
        "selected_todo": {
            "todo_id": "todo_fixture0001",
            "priority": "P0",
            "status": "open",
            "task_class": "advancement_task",
            "action_kind": "fixture_action",
            "claimed_by": "codex-fixture",
            "text": "Implement one bounded public-safe slice",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": "bounded_delivery",
            "user_channel": {"action_required": False, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
                "primary_action": "todo_fixture0001: implement the fixture",
            },
            "cli_channel": {
                "next_cli_actions": [
                    "loopx refresh-state --goal-id fixture-goal --classification validated",
                    "loopx quota spend-slot --goal-id fixture-goal --execute",
                ],
                "spend_allowed_now": False,
                "spend_after_validation": True,
                "spend_policy": "spend once after validated writeback",
            },
            "required_reads": [
                {"kind": "repository", "command": "git status --short", "reason": "inspect state"}
            ],
        },
        "goal_boundary": {
            "adapter": {"kind": "fixture", "status": "connected-read-only"},
            "write_scope": ["loopx/**", "tests/**"],
            "requires_parent_approval": ["publish"],
            "guards": ["stop on private material"],
            "stop_condition": "stop before unauthorized production action",
            "rule": "stay_in_scope_or_stop",
        },
        "scheduler_hint": {
            "action": "run_now",
            "cadence_class": "active_work",
            "spend_policy": "spend after validated writeback",
            "codex_app": {
                "apply": "update_automation_cadence_if_possible",
                "host_action": "update_current_heartbeat_rrule",
                "recommended_rrule": "FREQ=MINUTELY;INTERVAL=3",
                "no_spend_for_cadence_change": True,
                "stateful_backoff": {
                    "state_key": "scheduler_hint.codex_app.stateful_backoff",
                    "current_rrule": "FREQ=MINUTELY;INTERVAL=60",
                    "apply_needed": True,
                    "state_status": "reset_required",
                },
                "ack_hint": {
                    "cli_args": [
                        "quota",
                        "scheduler-ack-current",
                        "--goal-id",
                        "fixture-goal",
                        "--execute",
                    ]
                },
            },
        },
        "work_lane_contract": {
            "schema_version": "work_lane_contract_v1",
            "lane": "advancement_task",
            "next_lane": "advancement_task",
            "obligation": "advance_primary_outcome_or_write_blocker",
            "must_attempt_work": True,
            "monitor_policy": "material_transition_only",
            "action": "advance one product-path slice",
            "outcome_followthrough": {
                "required": True,
                "obligation": "advance_primary_outcome_or_write_blocker",
                "accepted_resolution_kinds": ["product_path_execution", "blocker_writeback"],
                "spend_policy": "spend after validated evidence",
            },
        },
        "execution_obligation": {
            "schema_version": "execution_obligation_v0",
            "kind": "work_lane_contract",
            "contract": "work_lane_contract",
            "contract_obligation": "advance_primary_outcome_or_write_blocker",
            "must_attempt_work": True,
            "notify_is_execution_gate": False,
            "reason": "runnable fixture todo",
        },
        "goal_route_hint": {
            "schema_version": "goal_route_hint_v0",
            "kind": "agent_lane_synthesis",
            "route_decision": "run_current_agent_lane",
            "reason": "selected current-agent claimed todo",
            "preserves_goal_next_action": True,
            "goal_next_action_mutation": "none",
        },
        "automation_liveness": {
            "schema_version": "automation_liveness_v0",
            "keep_active": True,
            "pause_allowed": False,
            "automation_action": "execute_bounded_work",
            "reason": "runnable work remains",
            "spend_policy": "spend after validated writeback",
        },
        "handoff_readiness": {
            "ready": True,
            "codex_ready": True,
            "handoff_status": "post_handoff_run_seen",
            "post_handoff_run_seen": True,
            "post_handoff_recent_runs": ["diagnostic-only"],
        },
        "protocol_action_packet": {
            "schema_version": "protocol_action_packet_v0",
            "summary": "actor=agent agent_action_required=true",
        },
        "agent_todo_summary": {"large_diagnostic_lane": ["x" * 4_000]},
        "goal_frontier_projection": {"large_diagnostic_lane": ["y" * 4_000]},
        "plan_summary": {"large_diagnostic_lane": ["z" * 4_000]},
    }


def test_turn_envelope_preserves_action_boundary_and_writeback() -> None:
    source = _full_decision()
    envelope = build_turn_envelope(source)

    assert envelope["schema_version"] == "loopx_turn_envelope_v0"
    assert envelope["view"] == "turn_envelope"
    assert envelope["goal_id"] == "fixture-goal"
    assert envelope["agent_id"] == "codex-fixture"
    assert envelope["action"]["selected_todo"]["todo_id"] == "todo_fixture0001"
    assert envelope["action"]["must_attempt"] is True
    assert envelope["user"] == {
        "action_required": False,
        "open_count": 0,
        "notify": "DONT_NOTIFY",
    }
    assert envelope["required_reads"][0]["command"] == "git status --short"
    assert envelope["boundary"]["write_scope"] == ["loopx/**", "tests/**"]
    assert envelope["execution_policy"]["normal_delivery_allowed"] is True
    assert envelope["execution_policy"]["safe_bypass_allowed"] is False
    assert envelope["writeback"]["spend_after_validation"] is True
    assert envelope["scheduler"]["codex_app"]["stateful_backoff"]["apply_needed"] is True
    assert envelope["scheduler"]["codex_app"]["ack_cli_args"][0] == "quota"
    assert (
        envelope["contract_capsule"]["work_lane_contract"]["lane"]
        == "advancement_task"
    )
    assert (
        envelope["contract_capsule"]["execution_obligation"]["contract_obligation"]
        == "advance_primary_outcome_or_write_blocker"
    )
    assert (
        envelope["contract_capsule"]["automation_liveness"]["pause_allowed"]
        is False
    )
    assert envelope["contract_capsule"]["protocol_action_packet"] == {
        "schema_version": "protocol_action_packet_v0",
        "present": True,
        "summary": "actor=agent agent_action_required=true",
        "summary_hash": envelope["contract_capsule"]["protocol_action_packet"]["summary_hash"],
        "derivation_status": "unproven_retain_summary",
        "candidate_derivation_inputs": [
            "action",
            "user",
            "work_lane_contract",
            "automation_liveness",
            "scheduler",
        ],
    }
    assert envelope["action_signature"]["matches"] is True
    assert envelope["action_signature"]["source_hash"] == envelope["action_signature"]["envelope_hash"]
    assert quota_action_signature_document(source) == turn_envelope_action_signature_document(envelope)

    assert "agent_todo_summary" not in envelope
    assert "goal_frontier_projection" not in envelope
    assert "plan_summary" not in envelope
    assert envelope["compaction"]["source_json_bytes"] == len(
        json.dumps(source, ensure_ascii=False, separators=(",", ":"))
    )
    assert envelope["compaction"]["envelope_json_bytes"] < TURN_ENVELOPE_BUDGET_BYTES
    assert envelope["compaction"]["within_budget"] is True
    assert envelope["compaction"]["byte_reduction_ratio"] > 0.5
    assert envelope["compaction"]["envelope_json_bytes"] == len(
        json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    )


def test_turn_envelope_keeps_concrete_user_gate() -> None:
    source = _full_decision()
    source["action_required"] = True
    source["open_count"] = 1
    source["interaction_contract"]["user_channel"] = {
        "action_required": True,
        "notify": "NOTIFY",
        "actions": ["Approve public release"],
        "reason": "release approval required",
    }

    envelope = build_turn_envelope(source)

    assert envelope["user"]["action_required"] is True
    assert envelope["user"]["actions"] == ["Approve public release"]
    assert envelope["user"]["reason"] == "release approval required"
    assert envelope["action_required"] is True
    assert envelope["open_count"] == 1
    assert envelope["action_signature"]["matches"] is True


def test_action_signature_detects_semantic_drift() -> None:
    source = _full_decision()
    envelope = build_turn_envelope(source)
    envelope["writeback"]["spend_after_validation"] = False

    assert quota_action_signature_document(source) != turn_envelope_action_signature_document(envelope)

    envelope = build_turn_envelope(source)
    envelope["execution_policy"]["safe_bypass_allowed"] = True

    assert quota_action_signature_document(source) != turn_envelope_action_signature_document(envelope)


def test_contract_capsule_stays_bounded_with_replan_and_vision_contracts() -> None:
    source = _full_decision()
    source["execution_profile"] = {
        "cadence": "bounded_progress_segment",
        "minimum_scale": "multi_surface_or_implementation",
        "spend_rule": "spend_only_after_artifact_validation_writeback",
        "must_include": ["coherent_artifact", "targeted_validation", "state_writeback"],
    }
    source["autonomous_replan_scope"] = {
        "schema_version": "autonomous_replan_scope_v0",
        "required": True,
        "applies": True,
        "scope": "explicit_agent_owner",
        "owner_agent_ids": ["codex-fixture"],
        "selected_peer_agent": "codex-fixture",
    }
    source["agent_scope_frontier"] = {
        "schema_version": "agent_scope_frontier_v0",
        "action": "successor_replan_required",
        "effective_action": "successor_replan_required",
        "blocks_delivery": True,
        "quiet_noop_allowed": False,
        "requires_replan": True,
        "recommended_action": "write a concrete successor before quiet wait " * 20,
        "spend_policy": "spend only after successor writeback " * 20,
    }
    source["vision_continuation_audit"] = {
        "schema_version": "vision_continuation_audit_v0",
        "required": True,
        "decision": "acceptance_gap_open",
        "selected_todo_is_goal_completion": False,
        "closeout_allowed_without_evidence": False,
        "required_before_closeout": [
            f"requirement-{index}-" + "evidence " * 30 for index in range(4)
        ],
        "recommended_action": "audit active vision acceptance " * 30,
    }
    source["automation_liveness"]["pause_policy"] = (
        "pause only after bounded repair is stuck " * 20
    )

    envelope = build_turn_envelope(source)

    assert envelope["action_signature"]["matches"] is True
    assert envelope["contract_capsule"]["autonomous_replan_scope"]["applies"] is True
    assert envelope["contract_capsule"]["agent_scope_frontier"]["requires_replan"] is True
    assert envelope["contract_capsule"]["vision_continuation_audit"]["required"] is True
    assert envelope["compaction"]["within_budget"] is True
    assert envelope["compaction"]["envelope_json_bytes"] < TURN_ENVELOPE_BUDGET_BYTES
