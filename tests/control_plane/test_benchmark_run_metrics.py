from __future__ import annotations

from loopx.control_plane.runtime.benchmark_run_metrics import (
    compact_benchmark_overhead_attribution_counters,
    compact_benchmark_round_reward_trace,
)


def test_round_reward_trace_compacts_and_orders_unique_rounds() -> None:
    compact = compact_benchmark_round_reward_trace(
        {
            "schema_version": "benchmark_round_reward_trace_v0",
            "success_observed": True,
            "max_rounds_budget": 3,
            "final_round_reward": 1,
            "records": [
                {
                    "agent_round": 2,
                    "reward_present": True,
                    "reward": 0.5,
                    "tool_calls": 4,
                    "private_detail": "drop",
                },
                {"agent_round": 1, "passed": False, "reward": 0},
                {"agent_round": 2, "reward": 1.0},
                {"agent_round": 0, "reward": 1.0},
                {"agent_round": True, "reward": 1.0},
            ],
            "private_detail": "drop",
        }
    )

    assert compact["success_observed"] is True
    assert compact["max_rounds_budget"] == 3
    assert compact["final_round_reward"] == 1.0
    assert compact["records"] == [
        {"agent_round": 1, "passed": False, "reward": 0.0},
        {
            "agent_round": 2,
            "reward_present": True,
            "reward": 0.5,
            "tool_calls": 4,
        },
    ]
    assert "private_detail" not in compact


def test_round_reward_trace_rejects_negative_rounds_and_private_text() -> None:
    compact = compact_benchmark_round_reward_trace(
        {
            "first_success_round": -1,
            "declared_done_round": True,
            "loop_score_policy": f"/{'Users'}/example/private.json",
            "best_round_reward": False,
        }
    )

    assert compact == {}


def test_overhead_counters_keep_public_metrics_and_numeric_call_maps() -> None:
    compact = compact_benchmark_overhead_attribution_counters(
        {
            "schema_version": "benchmark_overhead_attribution_counters_v0",
            "trace_publicness": "public-safe",
            "raw_logs_read": False,
            "wall_time_seconds": 12.5,
            "trial_count": 2,
            "loopx_cli_calls": {
                "quota should-run": 3,
                "todo claim": "2",
                "invalid": "unknown",
                "bool": True,
            },
            "codex_runtime_goal_tool_calls": {"turn/start": 4},
            "private_detail": "drop",
        }
    )

    assert compact["trace_publicness"] == "public-safe"
    assert compact["raw_logs_read"] is False
    assert compact["wall_time_seconds"] == 12.5
    assert compact["trial_count"] == 2
    assert compact["loopx_cli_calls"] == {
        "quota should-run": 3,
        "todo claim": 2,
    }
    assert compact["codex_runtime_goal_tool_calls"] == {"turn/start": 4}
    assert "private_detail" not in compact


def test_benchmark_run_metrics_reject_non_mapping_input() -> None:
    assert compact_benchmark_round_reward_trace(None) == {}
    assert compact_benchmark_round_reward_trace([]) == {}
    assert compact_benchmark_overhead_attribution_counters(None) == {}
    assert compact_benchmark_overhead_attribution_counters([]) == {}
