from __future__ import annotations

from loopx.benchmark_ledger import build_benchmark_run_ledger_entry


def _skillsbench_bool_only_run(*, status: str, attempt_countable: bool) -> dict:
    return {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "case_id": "fixture-case",
        "job_name": "skillsbench_fixture_loopx_turn_agent_cli",
        "mode": "skillsbench_loopx_turn_agent_cli_treatment",
        "official_score_status": status,
        "official_task_score": {
            "kind": "skillsbench_verifier_reward",
            "passed": False,
        },
        "score_failure_attribution": (
            "verifier_infrastructure_failure"
            if status == "missing"
            else "official_score_zero_case_failure"
        ),
        "attempt_accounting": {
            "schema_version": "benchmark_attempt_accounting_v0",
            "lifecycle_phase": "verifier_scored",
            "failure_label": (
                "verifier_infrastructure_failure"
                if status == "missing"
                else "official_score_zero_case_failure"
            ),
            "failure_class": "verifier_failed" if status == "missing" else "solver_failed",
            "official_score_attempt_countable": attempt_countable,
        },
    }


def test_missing_uncountable_score_does_not_fall_back_to_zero() -> None:
    entry = build_benchmark_run_ledger_entry(
        _skillsbench_bool_only_run(status="missing", attempt_countable=False)
    )

    assert entry["score_status"] == "missing"
    assert "official_score" not in entry
    assert entry["official_score_bool_fallback_used"] is False
    assert entry["official_score_attempt_countable"] is False
    assert entry["official_score_countable"] is False
    assert entry["official_score_countability_reason"] == "score_missing"
    assert "countable_score" not in entry


def test_completed_countable_bool_only_score_can_still_fall_back_to_zero() -> None:
    entry = build_benchmark_run_ledger_entry(
        _skillsbench_bool_only_run(status="completed", attempt_countable=True)
    )

    assert entry["score_status"] == "failed"
    assert entry["official_score"] == 0.0
    assert entry["official_score_bool_fallback_used"] is True
    assert entry["official_score_attempt_countable"] is True
    assert entry["official_score_countable"] is True
    assert entry["countable_score"] == 0.0
