from __future__ import annotations

from typing import Any


BENCHMARK_RUN_LEDGER_CURRENT_AGGREGATE_SCHEMA_VERSION = (
    "benchmark_run_ledger_current_aggregate_v0"
)


def _ledger_module():
    from . import benchmark_ledger

    return benchmark_ledger


def _compact_text(value: Any, *, limit: int = 160) -> str:
    return _ledger_module()._compact_text(value, limit=limit)


def _compact_list(value: Any, *, limit: int = 8) -> list[str]:
    return _ledger_module()._compact_list(value, limit=limit)


def _active_ledger_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _ledger_module()._active_ledger_runs(runs)


def _normalize_benchmark_run_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    return _ledger_module()._normalize_benchmark_run_ledger(ledger)


def _ledger_score_value(run: dict[str, Any]) -> float | None:
    value = run.get("official_score")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _official_score_countability(run: dict[str, Any]) -> dict[str, Any]:
    return _ledger_module().benchmark_run_official_score_countability(run)


def _official_score_countable(run: dict[str, Any]) -> bool:
    return _official_score_countability(run).get("countable") is True


def _current_aggregate_failure_label_list(run: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for key in ("failure_labels", "failure_attribution_labels"):
        for label in _compact_list(run.get(key), limit=16):
            if label not in seen:
                seen.add(label)
                labels.append(label)
    return labels


def _current_aggregate_failure_labels(run: dict[str, Any]) -> set[str]:
    return set(_current_aggregate_failure_label_list(run))


def _current_aggregate_effective_failure_class(run: dict[str, Any]) -> str:
    for key in (
        "failure_class",
        "score_failure_attribution",
        "attempt_failure_class",
        "attempt_failure_label",
        "first_blocker",
    ):
        value = _compact_text(run.get(key), limit=120)
        if value and value not in {"none", "None", "null"}:
            return value
    for label in _current_aggregate_failure_label_list(run):
        if label and label not in {"none", "None", "null"}:
            return label
    return ""


def _current_aggregate_bucket(run: dict[str, Any] | None) -> str:
    if not isinstance(run, dict):
        return "missing"
    score = _ledger_score_value(run)
    if score is not None:
        if not _official_score_countable(run):
            return "uncountable_official_score"
        if score >= 1.0:
            return "pass"
        if score > 0.0:
            return "partial"
        return "official_zero"
    labels = _current_aggregate_failure_labels(run)
    failure_class = _current_aggregate_effective_failure_class(run)
    failure_scope = _compact_text(run.get("failure_scope"), limit=120)
    score_status = _compact_text(run.get("score_status"), limit=120)
    if (
        "verifier_no_reward" in labels
        or "verifier_reward_missing" in labels
        or "reward_missing" in failure_class
        or "verifier_no_reward" in failure_class
    ):
        return "verifier_no_reward"
    if (
        failure_scope == "runner_or_setup"
        or failure_scope == "score_missing"
        or "infrastructure" in failure_class
        or "setup" in failure_class
        or "preflight" in failure_class
        or "compose" in failure_class
        or "docker" in failure_class
        or "runner" in failure_class
        or any(
            "infra" in label
            or "setup" in label
            or "compose" in label
            or "docker" in label
            for label in labels
        )
    ):
        return "setup_runner_infra"
    if score_status == "missing":
        return "missing"
    return "missing"


_CURRENT_AGGREGATE_BUCKET_RANK = {
    "missing": 0,
    "setup_runner_infra": 1,
    "verifier_no_reward": 2,
    "uncountable_official_score": 3,
    "official_zero": 4,
    "partial": 5,
    "pass": 6,
}


def _current_aggregate_run_sort_key(run: dict[str, Any]) -> tuple[Any, ...]:
    bucket = _current_aggregate_bucket(run)
    score = _ledger_score_value(run)
    score_rank = score if score is not None else -1.0
    return (
        _CURRENT_AGGREGATE_BUCKET_RANK.get(bucket, 0),
        score_rank,
        _compact_text(run.get("recorded_at"), limit=80),
        _compact_text(run.get("run_group_id"), limit=160),
        _compact_text(run.get("run_id"), limit=80),
    )


def _current_aggregate_run_summary(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {"bucket": "missing"}
    keys = (
        "run_id",
        "recorded_at",
        "benchmark_id",
        "case_id",
        "run_group_id",
        "arm_id",
        "route",
        "artifact_refs",
        "status",
        "score_status",
        "official_score",
        "official_passed",
        "official_score_countable",
        "official_score_countability_reason",
        "countable_score",
        "round_reward_count",
        "round_success_observed",
        "max_rounds_budget",
        "app_server_goal_round_semantics",
        "native_goal_session_policy",
        "max_rounds_budget_applies_to",
        "native_goal_initial_turn_budget",
        "native_goal_same_thread_followup_budget",
        "native_goal_independent_attempt_budget",
        "native_goal_fresh_thread_per_independent_attempt",
        "native_goal_official_reward_feedback_forwarded_to_worker",
        "native_goal_verifier_output_forwarded_to_worker",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "failure_class",
        "failure_scope",
        "failure_labels",
        "score_failure_attribution",
        "failure_attribution_labels",
        "attempt_lifecycle_phase",
        "attempt_failure_label",
        "attempt_failure_class",
        "runner_return_status",
        "runner_score_recovered_from_verifier_artifact",
        "verifier_reward_artifact_recovery_status",
        "verifier_reward_artifact_recovered",
        "official_result_json_materialized",
        "solution_quality_signals",
        "task_setup_preflight",
        "task_staging",
        "repair_class",
        "repair_priority",
    )
    summary = {key: run[key] for key in keys if key in run}
    summary["bucket"] = _current_aggregate_bucket(run)
    countability = _official_score_countability(run)
    summary["official_score_countable"] = countability["countable"]
    summary["official_score_countability_reason"] = countability["reason"]
    if countability["countable"] is True and countability.get("score") is not None:
        summary["countable_score"] = countability["score"]
    effective_failure_class = _current_aggregate_effective_failure_class(run)
    if effective_failure_class:
        summary["effective_failure_class"] = effective_failure_class
    return summary


def _current_aggregate_case_is_noncanonical_sanity_source(case: dict[str, Any]) -> bool:
    runs = _active_ledger_runs(
        [item for item in case.get("runs", []) if isinstance(item, dict)]
    )
    if not runs:
        return False
    saw_sanity_source_preflight = False
    for run in runs:
        if _ledger_score_value(run) is not None:
            return False
        if _current_aggregate_effective_failure_class(run) != (
            "skillsbench_task_source_preflight_blocked"
        ):
            return False
        preflight = run.get("task_setup_preflight")
        if not isinstance(preflight, dict):
            return False
        if preflight.get("canonical_task_present") is not False:
            return False
        if _compact_text(preflight.get("status"), limit=120) != (
            "task_missing_from_canonical_tasks"
        ):
            return False
        if _compact_text(preflight.get("alternate_source_kind"), limit=120) != (
            "experiments_sanity_tasks"
        ):
            return False
        if preflight.get("alternate_source_supported_by_runner") is not False:
            return False
        saw_sanity_source_preflight = True
    return saw_sanity_source_preflight


def build_benchmark_run_ledger_current_aggregate(
    ledger: dict[str, Any],
    *,
    benchmark_id: str = "skillsbench@1.1",
    canonical_case_ids: list[str] | None = None,
    source_ledger_count: int = 1,
    exclude_noncanonical_sanity_sources: bool = True,
) -> dict[str, Any]:
    """Build a current-case aggregate, preferring countable results over missing rows."""

    normalized = _normalize_benchmark_run_ledger(dict(ledger))
    benchmark = (
        normalized.get("benchmarks", {}).get(benchmark_id)
        if isinstance(normalized.get("benchmarks"), dict)
        else None
    )
    cases = benchmark.get("cases") if isinstance(benchmark, dict) else {}
    if not isinstance(cases, dict):
        cases = {}
    if canonical_case_ids:
        canonical_ids = [
            _compact_text(case_id, limit=160)
            for case_id in canonical_case_ids
            if _compact_text(case_id, limit=160)
        ]
        if exclude_noncanonical_sanity_sources:
            canonical_ids = [
                case_id
                for case_id in canonical_ids
                if not (
                    isinstance(cases.get(case_id), dict)
                    and _current_aggregate_case_is_noncanonical_sanity_source(
                        cases[case_id]
                    )
                )
            ]
    else:
        canonical_ids = sorted(
            case_id
            for case_id, case in cases.items()
            if not (
                isinstance(case, dict)
                and _current_aggregate_case_is_noncanonical_sanity_source(case)
            )
        )
    distribution = {
        "missing": 0,
        "setup_runner_infra": 0,
        "verifier_no_reward": 0,
        "uncountable_official_score": 0,
        "official_zero": 0,
        "partial": 0,
        "pass": 0,
    }
    cases_by_bucket = {bucket: [] for bucket in distribution}
    case_best: dict[str, dict[str, Any]] = {}
    deduped_run_ids: set[str] = set()
    countable_case_ids: list[str] = []
    countable_scores: list[float] = []
    uncountable_numeric_case_ids: list[str] = []
    for case in cases.values():
        if not isinstance(case, dict):
            continue
        for run in _active_ledger_runs(
            [item for item in case.get("runs", []) if isinstance(item, dict)]
        ):
            run_id = _compact_text(run.get("run_id"), limit=80)
            if run_id:
                deduped_run_ids.add(run_id)
    for case_id in canonical_ids:
        case = cases.get(case_id)
        runs = []
        if isinstance(case, dict):
            runs = _active_ledger_runs(
                [item for item in case.get("runs", []) if isinstance(item, dict)]
            )
        best = max(runs, key=_current_aggregate_run_sort_key) if runs else None
        summary = _current_aggregate_run_summary(best)
        bucket = summary["bucket"]
        distribution[bucket] = distribution.get(bucket, 0) + 1
        cases_by_bucket.setdefault(bucket, []).append(case_id)
        case_best[case_id] = summary
        score = _ledger_score_value(summary)
        if summary.get("official_score_countable") is True and score is not None:
            countable_case_ids.append(case_id)
            countable_scores.append(score)
        elif score is not None:
            uncountable_numeric_case_ids.append(case_id)
    countable_score_sum = sum(countable_scores)
    countable_score_mean = (
        countable_score_sum / len(countable_scores) if countable_scores else None
    )
    return {
        "schema_version": BENCHMARK_RUN_LEDGER_CURRENT_AGGREGATE_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "canonical_total": len(canonical_ids),
        "canonical_covered": sum(
            count for bucket, count in distribution.items() if bucket != "missing"
        ),
        "countable_score_summary": {
            "schema_version": "benchmark_run_ledger_countable_score_summary_v0",
            "countable_case_count": len(countable_scores),
            "countable_score_sum": round(countable_score_sum, 6),
            "countable_score_mean": round(countable_score_mean, 6)
            if countable_score_mean is not None
            else None,
            "pass_count": sum(1 for score in countable_scores if score >= 1.0),
            "partial_count": sum(
                1 for score in countable_scores if 0.0 < score < 1.0
            ),
            "official_zero_count": sum(1 for score in countable_scores if score == 0.0),
            "uncountable_numeric_case_count": len(uncountable_numeric_case_ids),
            "countable_case_ids": sorted(countable_case_ids),
            "uncountable_numeric_case_ids": sorted(uncountable_numeric_case_ids),
        },
        "distribution": distribution,
        "cases_by_bucket": {
            bucket: sorted(case_ids) for bucket, case_ids in cases_by_bucket.items()
        },
        "case_best": case_best,
        "deduped_run_count": len(deduped_run_ids),
        "source_ledger_files": source_ledger_count,
        "selection_policy": {
            "schema_version": "benchmark_run_ledger_current_selection_policy_v0",
            "rule": "prefer_countable_official_result_over_missing_or_infra_rows",
            "bucket_precedence": [
                "pass",
                "partial",
                "official_zero",
                "uncountable_official_score",
                "verifier_no_reward",
                "setup_runner_infra",
                "missing",
            ],
            "raw_logs_recorded": False,
            "raw_task_text_recorded": False,
            "source_paths_recorded": False,
        },
    }
