from __future__ import annotations

from loopx import status
from loopx.benchmarks.read_models.benchmark_result import compact_benchmark_result


def test_status_preserves_benchmark_result_import() -> None:
    assert status.compact_benchmark_result is compact_benchmark_result


def test_compact_benchmark_result_preserves_public_score_contract() -> None:
    compact = compact_benchmark_result(
        {
            "benchmark_result": {
                "schema_version": "benchmark_result_v0",
                "task_id": "task-1",
                "scenario_id": "scenario-1",
                "worker_mode": "passive",
                "harness_identity": "loopx",
                "worker_surface": "codex_cli",
                "terminal_state": "completed",
                "trace_publicness": "compact_public",
                "official_task_score": {
                    "kind": "verifier_reward",
                    "aggregation": "final",
                    "passed": True,
                    "value": 1.0,
                    "private_detail": "drop",
                },
                "control_plane_score": {
                    "schema_version": "control_plane_score_core_v0",
                    "kind": "coordination",
                    "value": 0.75,
                    "components": {
                        "restartability": 1.0,
                        "writeback_quality": 0.5,
                        "unknown_component": 1.0,
                    },
                    "private_detail": "drop",
                },
                "step_count": "3",
                "wall_time_ms": 120,
                "cost_usd": 0.25,
                "erroneous_write_count": 0,
                "human_intervention_count": 1,
                "validation_pass_count": 2,
                "open_todo_preserved": True,
                "state_reconstructable": False,
                "stop_policy_correct": True,
                "failure_attribution_labels": [
                    "one",
                    "two",
                    "three",
                    "four",
                    "five",
                    "drop",
                ],
                "private_detail": "drop",
            }
        }
    )

    assert compact is not None
    assert compact["official_task_score"] == {
        "kind": "verifier_reward",
        "aggregation": "final",
        "passed": True,
        "value": 1.0,
    }
    assert compact["control_plane_score"] == {
        "schema_version": "control_plane_score_core_v0",
        "kind": "coordination",
        "value": 0.75,
        "components": {
            "restartability": 1.0,
            "writeback_quality": 0.5,
        },
        "component_order": ["restartability", "writeback_quality"],
    }
    assert compact["counts"] == {
        "step_count": 3,
        "wall_time_ms": 120,
        "cost_usd": 0.25,
        "erroneous_write_count": 0,
        "human_intervention_count": 1,
        "validation_pass_count": 2,
    }
    assert compact["open_todo_preserved"] is True
    assert compact["state_reconstructable"] is False
    assert compact["stop_policy_correct"] is True
    assert compact["failure_attribution_labels"] == [
        "one",
        "two",
        "three",
        "four",
        "five",
    ]
    assert "private_detail" not in compact
    assert compact_benchmark_result(compact) == compact


def test_result_accepts_direct_rows_and_rejects_unrelated_payloads() -> None:
    direct = compact_benchmark_result(
        {
            "schema_version": "benchmark_result_v0",
            "task_id": "task-2",
        }
    )
    assert direct == {
        "schema_version": "benchmark_result_v0",
        "task_id": "task-2",
    }
    assert compact_benchmark_result({}) is None
    assert (
        compact_benchmark_result(
            {"schema_version": "benchmark_run_v0", "task_id": "task-3"}
        )
        is None
    )
