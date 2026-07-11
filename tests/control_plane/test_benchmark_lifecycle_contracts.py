from __future__ import annotations

from loopx.control_plane.runtime.benchmark_lifecycle_contracts import (
    compact_app_server_goal_round_semantics,
    compact_native_goal_worker_contract,
    compact_product_mode_lifecycle_contract,
)


def test_compact_product_mode_lifecycle_normalizes_late_closeout_evidence() -> None:
    compact = compact_product_mode_lifecycle_contract(
        {
            "schema_version": "skillsbench_product_mode_lifecycle_contract_v0",
            "required": True,
            "satisfied": False,
            "countable_treatment": False,
            "closeout_satisfied": False,
            "agent_operation_trace_required": True,
            "agent_operation_trace_satisfied": True,
            "state_read_count": 1,
            "state_write_count": 1,
            "agent_bridge_todo_closeout_count": 1,
            "agent_bridge_refresh_state_count": 1,
            "agent_bridge_quota_spend_slot_count": 1,
            "missing_reason": "missing_case_local_loopx_closeout",
            "private_detail": "drop",
        }
    )

    assert compact["satisfied"] is True
    assert compact["countable_treatment"] is True
    assert compact["closeout_satisfied"] is True
    assert "missing_reason" not in compact
    assert "private_detail" not in compact


def test_compact_native_goal_worker_contract_keeps_bounded_public_fields() -> None:
    compact = compact_native_goal_worker_contract(
        {
            "schema_version": "native_goal_worker_contract_v0",
            "required": True,
            "countable_baseline": False,
            "trace_count": 3,
            "failure_trace_count": -1,
            "reasoning_effort": "xhigh",
            "first_blocker": f"/{'Users'}/example/private.log",
            "incomplete_turn_statuses": [
                "waiting",
                "running",
                "blocked",
                "failed",
                "stopped",
                "ignored",
            ],
            "private_detail": "drop",
        }
    )

    assert compact["required"] is True
    assert compact["countable_baseline"] is False
    assert compact["trace_count"] == 3
    assert compact["failure_trace_count"] == -1
    assert compact["reasoning_effort"] == "xhigh"
    assert compact["incomplete_turn_statuses"] == [
        "waiting",
        "running",
        "blocked",
        "failed",
        "stopped",
    ]
    assert "first_blocker" not in compact
    assert "private_detail" not in compact


def test_compact_app_server_round_semantics_rejects_invalid_budgets() -> None:
    compact = compact_app_server_goal_round_semantics(
        {
            "schema_version": "app_server_goal_round_semantics_v0",
            "route": "native_goal_worker",
            "session_policy": "single_thread_with_blinded_followups",
            "benchflow_max_rounds_budget": 3,
            "initial_goal_turn_budget": 0,
            "same_thread_followup_budget": -1,
            "independent_attempt_budget": True,
            "fresh_goal_thread_per_independent_attempt": True,
        }
    )

    assert compact["benchflow_max_rounds_budget"] == 3
    assert compact["initial_goal_turn_budget"] == 0
    assert "same_thread_followup_budget" not in compact
    assert "independent_attempt_budget" not in compact
    assert compact["fresh_goal_thread_per_independent_attempt"] is True


def test_benchmark_lifecycle_compactors_reject_non_mapping_input() -> None:
    for compact in (
        compact_product_mode_lifecycle_contract,
        compact_native_goal_worker_contract,
        compact_app_server_goal_round_semantics,
    ):
        assert compact(None) == {}
        assert compact([]) == {}
