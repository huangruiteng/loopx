from __future__ import annotations

from loopx.benchmarks.read_models.benchmark_comparison import (
    benchmark_comparison_decision_note,
    compact_benchmark_comparison,
)


def test_compact_benchmark_comparison_preserves_public_contract() -> None:
    compact = compact_benchmark_comparison(
        {
            "benchmark_comparison": {
                "schema_version": "benchmark_comparison_v0",
                "comparison_id": "pair-1",
                "task_id": "task-1",
                "mode_pair": ["a", "b", "c", "d", "e", "drop"],
                "official_task_score_delta": 0,
                "control_plane_score_delta": 2.5,
                "requires_explicit_authorization_for_real_execution": True,
                "failure_attribution_labels": ["public-label"],
                "claim_boundary": {
                    "leaderboard_claim_allowed": False,
                    "raw_trace_excluded": True,
                    "private_detail": True,
                },
                "baseline_failure_gate": {
                    "baseline_mode": "control",
                    "baseline_failed": True,
                    "control_plane_addressable": True,
                    "treatment_eligible": True,
                    "evidence_refs": ["artifact:public"],
                    "private_detail": "drop",
                },
                "decision": {
                    "score_uplift": False,
                    "validation_enhancement_point": True,
                    "why": "better attribution",
                    "private_detail": "drop",
                },
                "result_refs": [
                    {
                        "scenario_id": f"scenario-{index}",
                        "result_id": f"result-{index}",
                        "private_detail": "drop",
                    }
                    for index in range(7)
                ],
                "private_detail": "drop",
            }
        }
    )

    assert compact is not None
    assert compact["schema_version"] == "benchmark_comparison_v0"
    assert compact["comparison_id"] == "pair-1"
    assert compact["mode_pair"] == ["a", "b", "c", "d", "e"]
    assert compact["official_task_score_delta"] == 0
    assert compact["control_plane_score_delta"] == 2.5
    assert compact["claim_boundary"] == {
        "leaderboard_claim_allowed": False,
        "raw_trace_excluded": True,
    }
    assert compact["baseline_failure_gate"] == {
        "schema_version": "benchmark_baseline_failure_gate_v0",
        "baseline_mode": "control",
        "baseline_failed": True,
        "control_plane_addressable": True,
        "treatment_eligible": True,
        "evidence_refs": ["artifact:public"],
    }
    assert compact["decision"] == {
        "score_uplift": False,
        "validation_enhancement_point": True,
        "why": "better attribution",
    }
    assert len(compact["result_refs"]) == 5
    assert all("private_detail" not in ref for ref in compact["result_refs"])
    assert "private_detail" not in compact


def test_decision_note_routes_readiness_only_comparison() -> None:
    note = benchmark_comparison_decision_note(
        {
            "schema_version": "benchmark_comparison_v0",
            "task_id": "task-1",
            "comparison_id": "pair-1",
            "official_task_score_delta": "not_applicable_readiness_only",
            "ready_to_run_real_benchmark": False,
        }
    )

    assert note is not None
    assert note["schema_version"] == "benchmark_comparison_decision_note_v0"
    assert note["decision"] == "continue"
    assert note["evidence_layer"] == "readiness_only"
    assert note["official_task_score_delta"] == "not_applicable_readiness_only"
    assert "benchmark pass/fail or score uplift" in note["must_not_claim"]


def test_decision_note_routes_treatment_eligible_baseline_failure() -> None:
    note = benchmark_comparison_decision_note(
        {
            "schema_version": "benchmark_comparison_v0",
            "comparison_id": "pair-2",
            "baseline_failure_gate": {
                "schema_version": "benchmark_baseline_failure_gate_v0",
                "baseline_mode": "control",
                "baseline_failed": True,
                "control_plane_addressable": True,
                "treatment_eligible": True,
                "minimum_next_evidence": "run one bounded treatment",
            },
        }
    )

    assert note is not None
    assert note["decision"] == "continue"
    assert note["evidence_layer"] == "baseline_failure_gate"
    assert note["minimum_next_evidence"] == "run one bounded treatment"
    assert note["baseline_failure_gate"] == {
        "schema_version": "benchmark_baseline_failure_gate_v0",
        "baseline_mode": "control",
        "baseline_failed": True,
        "control_plane_addressable": True,
        "treatment_eligible": True,
    }


def test_comparison_projection_rejects_unrelated_payloads() -> None:
    assert compact_benchmark_comparison({}) is None
    assert benchmark_comparison_decision_note(None) is None
    assert (
        benchmark_comparison_decision_note({"schema_version": "benchmark_result_v0"})
        is None
    )
