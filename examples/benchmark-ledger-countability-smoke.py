#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_ledger import (  # noqa: E402
    BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
    benchmark_run_official_score_countability,
    build_benchmark_run_ledger_current_aggregate,
    upsert_benchmark_run_ledger_entry,
)


def _setup_preflight_run() -> dict[str, object]:
    return {
        "schema_version": "benchmark_run_v0",
        "benchmark_id": "skillsbench@1.1",
        "case_id": "setup-preflight-case",
        "case_ids": ["setup-preflight-case"],
        "run_id": "setup-preflight-case-run",
        "run_group_id": "skillsbench-codex-cli-goal-xhigh-setup-preflight-case",
        "official_score_status": "missing",
        "official_score": None,
        "official_task_score": {
            "kind": "skillsbench_verifier_reward_missing",
            "value": None,
            "passed": False,
        },
        "official_score_attempt_countable": True,
        "attempt_accounting": {
            "lifecycle_phase": "not_started",
            "failure_class": "none",
            "failure_label": "not_run_adapter_skeleton",
            "launcher_attempt_countable": False,
            "case_attempt_countable": False,
            "solver_attempt_countable": False,
            "verifier_attempt_countable": False,
            "official_score_attempt_countable": False,
        },
        "failure_class": "skillsbench_runner_error",
        "failure_scope": "runner_or_setup",
        "score_status": "missing",
    }


def test_missing_verifier_reward_bool_does_not_override_uncountable_attempt() -> None:
    run = _setup_preflight_run()

    countability = benchmark_run_official_score_countability(run)
    assert countability == {
        "countable": False,
        "reason": "official_score_attempt_not_countable",
        "score": 0.0,
    }, countability

    persisted_run = dict(run)
    persisted_run.pop("official_task_score")
    persisted_run.pop("attempt_accounting")
    persisted_run["official_score"] = 0.0
    persisted_run["official_score_status"] = None
    persisted_run["score_status"] = "failed"
    persisted_run["attempt_lifecycle_phase"] = "not_started"

    persisted_countability = benchmark_run_official_score_countability(persisted_run)
    assert persisted_countability == {
        "countable": False,
        "reason": "official_score_attempt_not_countable",
        "score": 0.0,
    }, persisted_countability

    ledger = upsert_benchmark_run_ledger_entry(
        {
            "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
            "benchmarks": {},
        },
        persisted_run,
    )
    aggregate = build_benchmark_run_ledger_current_aggregate(
        ledger,
        benchmark_id="skillsbench@1.1",
        canonical_case_ids=["setup-preflight-case"],
    )
    summary = aggregate["countable_score_summary"]
    assert summary["countable_case_count"] == 0, aggregate
    assert summary["uncountable_numeric_case_ids"] == ["setup-preflight-case"], aggregate
    assert aggregate["case_best"]["setup-preflight-case"]["bucket"] == (
        "uncountable_official_score"
    ), aggregate


def test_uncountable_bool_official_result_does_not_synthesize_zero() -> None:
    run = _setup_preflight_run()
    run["failure_class"] = "official_verifier_solution_failure"
    run["failure_scope"] = "case_or_solution"
    run["official_score_attempt_countable"] = False
    run["official_task_score"] = {"kind": "skillsbench_reward", "passed": False}
    run["score_status"] = "missing"

    assert benchmark_run_official_score_countability(run) == {
        "countable": False,
        "reason": "score_missing",
        "score": None,
    }


def test_verifier_infrastructure_failure_zero_is_uncountable() -> None:
    run = _setup_preflight_run()
    run.pop("official_task_score")
    run.pop("attempt_accounting")
    run["case_id"] = "verifier-timeout-case"
    run["case_ids"] = ["verifier-timeout-case"]
    run["run_id"] = "verifier-timeout-case-run"
    run["run_group_id"] = "skillsbench-codex-cli-goal-xhigh-verifier-timeout-case"
    run["official_score"] = 0.0
    run["official_score_status"] = None
    run["official_score_attempt_countable"] = None
    run["score_status"] = "failed"
    run["failure_class"] = "verifier_infrastructure_failure"
    run["failure_scope"] = "verifier_or_infra"
    run["score_failure_attribution"] = "verifier_infrastructure_failure"

    countability = benchmark_run_official_score_countability(run)
    assert countability == {
        "countable": False,
        "reason": "official_score_attempt_not_countable",
        "score": 0.0,
    }, countability

    ledger = upsert_benchmark_run_ledger_entry(
        {
            "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
            "benchmarks": {},
        },
        run,
    )
    aggregate = build_benchmark_run_ledger_current_aggregate(
        ledger,
        benchmark_id="skillsbench@1.1",
        canonical_case_ids=["verifier-timeout-case"],
    )
    summary = aggregate["countable_score_summary"]
    assert summary["countable_case_count"] == 0, aggregate
    assert summary["uncountable_numeric_case_ids"] == ["verifier-timeout-case"], aggregate
    assert aggregate["case_best"]["verifier-timeout-case"]["bucket"] == (
        "uncountable_official_score"
    ), aggregate


def test_verifier_dependency_failure_zero_is_uncountable() -> None:
    run = _setup_preflight_run()
    run.pop("official_task_score")
    run.pop("attempt_accounting")
    run["case_id"] = "verifier-dependency-case"
    run["case_ids"] = ["verifier-dependency-case"]
    run["run_id"] = "verifier-dependency-case-run"
    run["run_group_id"] = "skillsbench-codex-cli-goal-xhigh-verifier-dependency-case"
    run["official_score"] = 0.0
    run["official_score_status"] = None
    run["official_score_attempt_countable"] = None
    run["score_status"] = "failed"
    run["failure_class"] = "verifier_dependency_install_failure"
    run["failure_scope"] = "verifier_or_infra"
    run["score_failure_attribution"] = "verifier_dependency_install_failure"

    countability = benchmark_run_official_score_countability(run)
    assert countability == {
        "countable": False,
        "reason": "official_score_attempt_not_countable",
        "score": 0.0,
    }, countability


def test_explicit_scored_attempt_precedes_coarse_verifier_attribution() -> None:
    run = _setup_preflight_run()
    run["case_id"] = "scored-verifier-attribution-case"
    run["case_ids"] = ["scored-verifier-attribution-case"]
    run["run_id"] = "scored-verifier-attribution-case-run"
    run["official_score"] = 0.0
    run["official_score_status"] = "completed"
    run["official_task_score"] = {
        "kind": "skillsbench_verifier_reward_recovered_from_controller_trace",
        "value": 0.0,
        "passed": False,
    }
    run["score_status"] = "failed"
    run["failure_class"] = "verifier_dependency_install_failure"
    run["failure_scope"] = "verifier_or_infra"
    run["score_failure_attribution"] = "verifier_dependency_install_failure"
    run["attempt_lifecycle_phase"] = "verifier_scored"
    run["official_score_attempt_countable"] = True
    accounting = run["attempt_accounting"]
    assert isinstance(accounting, dict)
    accounting["lifecycle_phase"] = "verifier_scored"
    accounting["official_score_attempt_countable"] = True

    assert benchmark_run_official_score_countability(run) == {
        "countable": True,
        "reason": "countable_official_score",
        "score": 0.0,
    }

    ledger = upsert_benchmark_run_ledger_entry(
        {
            "schema_version": BENCHMARK_RUN_LEDGER_SCHEMA_VERSION,
            "benchmarks": {},
        },
        run,
    )
    aggregate = build_benchmark_run_ledger_current_aggregate(
        ledger,
        benchmark_id="skillsbench@1.1",
        canonical_case_ids=["scored-verifier-attribution-case"],
    )
    summary = aggregate["countable_score_summary"]
    assert summary["countable_case_count"] == 1, aggregate
    assert aggregate["case_best"]["scored-verifier-attribution-case"]["bucket"] == (
        "official_zero"
    ), aggregate

    run["failure_attribution_labels"] = [
        "skillsbench_product_mode_uncountable_treatment"
    ]
    assert benchmark_run_official_score_countability(run) == {
        "countable": False,
        "reason": "uncountable_attribution",
        "score": 0.0,
    }
    run.pop("failure_attribution_labels")

    run["official_score_attempt_countable"] = False
    accounting["official_score_attempt_countable"] = False
    assert benchmark_run_official_score_countability(run) == {
        "countable": False,
        "reason": "official_score_attempt_not_countable",
        "score": 0.0,
    }


def main() -> None:
    test_missing_verifier_reward_bool_does_not_override_uncountable_attempt()
    test_uncountable_bool_official_result_does_not_synthesize_zero()
    test_verifier_infrastructure_failure_zero_is_uncountable()
    test_verifier_dependency_failure_zero_is_uncountable()
    test_explicit_scored_attempt_precedes_coarse_verifier_attribution()
    print("benchmark-ledger-countability-smoke: ok")


if __name__ == "__main__":
    main()
