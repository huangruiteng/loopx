from __future__ import annotations

import json

from loopx.control_plane.quota.turn_envelope import (
    TURN_ENVELOPE_BUDGET_BYTES,
    build_turn_envelope,
)


def _full_decision() -> dict[str, object]:
    return {
        "ok": True,
        "goal_id": "fixture-goal",
        "decision": "run",
        "should_run": True,
        "effective_action": "normal_run",
        "state": "eligible",
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
        "agent_todo_summary": {"large_diagnostic_lane": ["x" * 2_000]},
        "goal_frontier_projection": {"large_diagnostic_lane": ["y" * 2_000]},
        "plan_summary": {"large_diagnostic_lane": ["z" * 2_000]},
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
    assert envelope["writeback"]["spend_after_validation"] is True
    assert envelope["scheduler"]["codex_app"]["stateful_backoff"]["apply_needed"] is True
    assert envelope["scheduler"]["codex_app"]["ack_cli_args"][0] == "quota"

    assert "agent_todo_summary" not in envelope
    assert "goal_frontier_projection" not in envelope
    assert "plan_summary" not in envelope
    assert envelope["compaction"]["source_json_bytes"] == len(
        json.dumps(source, ensure_ascii=False, separators=(",", ":"))
    )
    assert envelope["compaction"]["envelope_json_bytes"] < TURN_ENVELOPE_BUDGET_BYTES
    assert envelope["compaction"]["within_budget"] is True
    assert envelope["compaction"]["byte_reduction_ratio"] > 0.5


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
