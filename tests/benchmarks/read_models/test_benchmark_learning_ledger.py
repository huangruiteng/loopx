from __future__ import annotations

from loopx import status
from loopx.benchmarks.read_models.benchmark_learning_ledger import (
    compact_benchmark_learning_ledger,
)


def test_status_preserves_benchmark_learning_ledger_import() -> None:
    assert status.compact_benchmark_learning_ledger is compact_benchmark_learning_ledger


def test_compact_learning_ledger_preserves_public_routing_contract() -> None:
    compact = compact_benchmark_learning_ledger(
        {
            "benchmark_learning_ledger": {
                "schema_version": "benchmark_learning_ledger_v0",
                "task_id": "task-1",
                "comparison_id": "pair-1",
                "learning_status": "actionable",
                "claim_strength": "fixture_only",
                "official_task_score_delta": "not_available",
                "control_plane_score_delta": 1.5,
                "repair_candidates": [
                    "one",
                    "two",
                    "three",
                    "four",
                    "five",
                    "drop",
                ],
                "claim_blockers": ["official uplift"],
                "lifecycle_gate": {
                    "budget_count_allowed": True,
                    "blocked_reason": "none",
                    "private_detail": "drop",
                },
                "learning_quota_gate": {
                    "actionable_learning_present": True,
                    "spend_allowed": True,
                    "actionable_reasons": ["public fixture"],
                    "private_detail": "drop",
                },
                "overhead": {
                    "cost_delta_usd": "0.25",
                    "wall_time_delta_seconds_or_ms": 120,
                    "label": "bounded",
                },
                "routing": {
                    "repeat_allowed": False,
                    "new_candidate_allowed": True,
                    "next_allowed_action": "select next candidate",
                    "private_detail": "drop",
                },
                "read_boundary": {
                    "compact_only": True,
                    "raw_artifacts_read": False,
                    "task_text_read": False,
                    "local_paths_recorded": False,
                    "private_detail": True,
                },
                "private_detail": "drop",
            }
        }
    )

    assert compact is not None
    assert compact["schema_version"] == "benchmark_learning_ledger_v0"
    assert compact["official_task_score_delta"] == "not_available"
    assert compact["control_plane_score_delta"] == 1.5
    assert compact["repair_candidates"] == [
        "one",
        "two",
        "three",
        "four",
        "five",
    ]
    assert compact["lifecycle_gate"] == {
        "budget_count_allowed": True,
        "blocked_reason": "none",
    }
    assert compact["learning_quota_gate"] == {
        "actionable_learning_present": True,
        "spend_allowed": True,
        "actionable_reasons": ["public fixture"],
    }
    assert compact["overhead"] == {
        "cost_delta_usd": "0.25",
        "wall_time_delta_seconds_or_ms": 120,
        "label": "bounded",
    }
    assert compact["routing"] == {
        "repeat_allowed": False,
        "new_candidate_allowed": True,
        "next_allowed_action": "select next candidate",
    }
    assert compact["read_boundary"] == {
        "compact_only": True,
        "raw_artifacts_read": False,
        "task_text_read": False,
        "local_paths_recorded": False,
    }
    assert "private_detail" not in compact


def test_learning_ledger_accepts_direct_rows_and_rejects_unrelated_payloads() -> None:
    direct = compact_benchmark_learning_ledger(
        {
            "schema_version": "benchmark_learning_ledger_v0",
            "task_id": "task-2",
        }
    )
    assert direct == {
        "schema_version": "benchmark_learning_ledger_v0",
        "task_id": "task-2",
    }
    assert compact_benchmark_learning_ledger({}) is None
    assert (
        compact_benchmark_learning_ledger(
            {"schema_version": "benchmark_result_v0", "task_id": "task-3"}
        )
        is None
    )
