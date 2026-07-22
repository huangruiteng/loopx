from __future__ import annotations

from loopx import status
from loopx.benchmarks.read_models.benchmark_attempt_accounting import (
    compact_benchmark_attempt_accounting,
)
from loopx.benchmarks.read_models.benchmark_experiment_report import (
    benchmark_experiment_report_readiness_note,
    benchmark_experiment_report_replay_decision,
    compact_benchmark_experiment_report,
)


def test_status_preserves_benchmark_experiment_report_imports() -> None:
    assert (
        status.compact_benchmark_experiment_report
        is compact_benchmark_experiment_report
    )
    assert (
        status.benchmark_experiment_report_readiness_note
        is benchmark_experiment_report_readiness_note
    )
    assert (
        status.benchmark_experiment_report_replay_decision
        is benchmark_experiment_report_replay_decision
    )


def test_compact_report_preserves_public_contract_and_attempt_accounting() -> None:
    compact = compact_benchmark_experiment_report(
        {
            "benchmark_report": {
                "schema_version": "benchmark_experiment_report_v0",
                "experiment_identity": {
                    "report_id": "report-1",
                    "benchmark_id": "fixture-benchmark",
                    "private_detail": "drop",
                },
                "official_score": {
                    "native_score": "1.0",
                    "wrapped_score": 1,
                    "submit_eligible": False,
                    "leaderboard_evidence": False,
                    "private_detail": "drop",
                },
                "attempt_accounting": {
                    "schema_version": "benchmark_attempt_accounting_v0",
                    "case_attempt_countable": True,
                    "attempts": {
                        "case": {"attempted": True, "countable": True},
                        "private_phase": {"attempted": True},
                    },
                    "private_detail": "drop",
                },
                "claim_boundary": {
                    "may_claim": ["one", "two", "three", "four", "five", "drop"],
                    "must_not_claim": ["official uplift"],
                    "private_detail": "drop",
                },
                "negative_results": {
                    "failed_hypotheses": [
                        {"evidence_layer": "readiness_only"},
                        {"evidence_layer": "failure_analysis"},
                    ],
                    "overhead_regressions": ["latency"],
                },
            }
        }
    )

    assert compact is not None
    assert compact["experiment_identity"] == {
        "report_id": "report-1",
        "benchmark_id": "fixture-benchmark",
    }
    assert compact["official_score"] == {
        "native_score": 1.0,
        "wrapped_score": 1,
        "submit_eligible": False,
        "leaderboard_evidence": False,
    }
    assert compact["attempt_accounting"] == {
        "schema_version": "benchmark_attempt_accounting_v0",
        "case_attempt_countable": True,
        "attempts": {"case": {"attempted": True, "countable": True}},
    }
    assert compact["claim_boundary"]["may_claim"] == [
        "one",
        "two",
        "three",
        "four",
        "five",
    ]
    assert compact["negative_results"] == {
        "failed_hypothesis_count": 2,
        "negative_evidence_layers": ["readiness_only", "failure_analysis"],
        "overhead_regression_count": 1,
    }


def test_readiness_and_replay_keep_authorization_boundary() -> None:
    readiness = benchmark_experiment_report_readiness_note(
        {
            "schema_version": "benchmark_experiment_report_v0",
            "experiment_identity": {"report_id": "report-1"},
            "official_score": {
                "submit_eligible": True,
                "leaderboard_evidence": False,
            },
            "claim_boundary": {"must_not_claim": ["official uplift"]},
        }
    )

    assert readiness is not None
    assert readiness["readiness"] == "review_required"
    assert readiness["next_run_authorization"] == "requires_operator_approval"

    replay = benchmark_experiment_report_replay_decision(readiness)
    assert replay is not None
    assert replay["replay_decision"] == "operator_review_required"
    assert replay["next_run_mode"] == "operator_review"
    assert replay["must_not_claim"] == ["official uplift"]


def test_attempt_accounting_and_report_projection_reject_unrelated_values() -> None:
    assert compact_benchmark_attempt_accounting(None) == {}
    assert compact_benchmark_experiment_report({}) is None
    assert benchmark_experiment_report_readiness_note(None) is None
    assert benchmark_experiment_report_replay_decision(None) is None
