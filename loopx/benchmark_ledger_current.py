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


def _run_group_text(run: dict[str, Any]) -> str:
    parts: list[str] = []
    for field in ("run_group_id", "run_id", "job_name"):
        text = _compact_text(run.get(field), limit=240)
        if text:
            parts.append(text)
    return " ".join(parts)


def _run_group_matches_any(run: dict[str, Any], needles: list[str] | None) -> bool:
    if not needles:
        return False
    haystack = _run_group_text(run).lower()
    if not haystack:
        return False
    return any(needle.lower() in haystack for needle in needles if needle)


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


def _current_aggregate_official_bool_fallback_used(run: dict[str, Any]) -> bool:
    fallback_fn = getattr(_ledger_module(), "official_score_bool_fallback_used", None)
    return run.get("official_score_bool_fallback_used") is True or (
        callable(fallback_fn) and fallback_fn(run) is True
    )


def _current_aggregate_attempt_flag(
    run: dict[str, Any], field_name: str
) -> bool | None:
    value = run.get(field_name)
    if isinstance(value, bool):
        return value
    accounting = (
        run.get("attempt_accounting")
        if isinstance(run.get("attempt_accounting"), dict)
        else {}
    )
    value = accounting.get(field_name)
    if isinstance(value, bool):
        return value
    return None


def _current_aggregate_core_attempt_marked_uncountable(run: dict[str, Any]) -> bool:
    return any(
        _current_aggregate_attempt_flag(run, field_name) is False
        for field_name in (
            "case_attempt_countable",
            "solver_attempt_countable",
            "verifier_attempt_countable",
        )
    )


def _current_aggregate_has_setup_runner_infra_signal(
    *,
    labels: set[str],
    failure_class: str,
    failure_scope: str,
) -> bool:
    return (
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
            or "runner" in label
            for label in labels
        )
    )


def _current_aggregate_bool_fallback_setup_runner_infra(
    run: dict[str, Any],
    *,
    labels: set[str],
    failure_class: str,
    failure_scope: str,
) -> bool:
    return (
        _current_aggregate_official_bool_fallback_used(run)
        and _current_aggregate_core_attempt_marked_uncountable(run)
        and _current_aggregate_has_setup_runner_infra_signal(
            labels=labels,
            failure_class=failure_class,
            failure_scope=failure_scope,
        )
    )


def _current_aggregate_bucket(run: dict[str, Any] | None) -> str:
    if not isinstance(run, dict):
        return "missing"
    labels = _current_aggregate_failure_labels(run)
    failure_class = _current_aggregate_effective_failure_class(run)
    failure_scope = _compact_text(run.get("failure_scope"), limit=120)
    if _current_aggregate_bool_fallback_setup_runner_infra(
        run,
        labels=labels,
        failure_class=failure_class,
        failure_scope=failure_scope,
    ):
        return "setup_runner_infra"
    score = _ledger_score_value(run)
    if score is not None:
        if not _official_score_countable(run):
            return "uncountable_official_score"
        if score >= 1.0:
            return "pass"
        if score > 0.0:
            return "partial"
        return "official_zero"
    score_status = _compact_text(run.get("score_status"), limit=120)
    if (
        "verifier_no_reward" in labels
        or "verifier_reward_missing" in labels
        or "reward_missing" in failure_class
        or "verifier_no_reward" in failure_class
    ):
        return "verifier_no_reward"
    if _current_aggregate_has_setup_runner_infra_signal(
        labels=labels,
        failure_class=failure_class,
        failure_scope=failure_scope,
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

_CURRENT_AGGREGATE_COUNTABLE_BUCKETS = {"official_zero", "partial", "pass"}


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


def _current_aggregate_countable_run(run: dict[str, Any]) -> bool:
    if _current_aggregate_bucket(run) not in _CURRENT_AGGREGATE_COUNTABLE_BUCKETS:
        return False
    countability = _official_score_countability(run)
    return (
        countability.get("countable") is True
        and countability.get("score") is not None
    )


def _best_current_aggregate_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    return max(runs, key=_current_aggregate_run_sort_key) if runs else None


def _current_aggregate_target_lane_enabled(
    target_run_group_contains: list[str] | None,
    target_current_run_group_contains: list[str] | None,
    target_backfill_run_group_contains: list[str] | None,
) -> bool:
    return bool(
        target_run_group_contains
        or target_current_run_group_contains
        or target_backfill_run_group_contains
    )


def _current_aggregate_classify_target_lane_runs(
    runs: list[dict[str, Any]],
    *,
    target_run_group_contains: list[str] | None,
    target_current_run_group_contains: list[str] | None,
    target_backfill_run_group_contains: list[str] | None,
) -> dict[str, list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    backfill: list[dict[str, Any]] = []
    target_any: list[dict[str, Any]] = []
    for run in runs:
        matches_target = _run_group_matches_any(run, target_run_group_contains)
        matches_current = _run_group_matches_any(
            run, target_current_run_group_contains
        )
        matches_backfill = _run_group_matches_any(
            run, target_backfill_run_group_contains
        )
        if not (matches_target or matches_current or matches_backfill):
            continue
        target_any.append(run)
        if matches_current:
            current.append(run)
            continue
        if matches_backfill:
            backfill.append(run)
            continue
        # Generic policy: target-lane runs that are not explicitly marked as
        # backfill are current evidence.
        current.append(run)
    return {"current": current, "backfill": backfill, "target_any": target_any}


def _current_aggregate_select_target_lane_run(
    runs: list[dict[str, Any]],
    *,
    target_run_group_contains: list[str] | None,
    target_current_run_group_contains: list[str] | None,
    target_backfill_run_group_contains: list[str] | None,
) -> tuple[dict[str, Any] | None, str]:
    classified = _current_aggregate_classify_target_lane_runs(
        runs,
        target_run_group_contains=target_run_group_contains,
        target_current_run_group_contains=target_current_run_group_contains,
        target_backfill_run_group_contains=target_backfill_run_group_contains,
    )
    current_runs = classified["current"]
    backfill_runs = classified["backfill"]
    current_countable = [
        run for run in current_runs if _current_aggregate_countable_run(run)
    ]
    if current_countable:
        return _best_current_aggregate_run(current_countable), "current_countable"
    backfill_countable = [
        run for run in backfill_runs if _current_aggregate_countable_run(run)
    ]
    if backfill_countable:
        return _best_current_aggregate_run(backfill_countable), "backfill_countable"
    best_current = _best_current_aggregate_run(current_runs)
    if best_current is not None:
        return best_current, "current_noncountable"
    best_backfill = _best_current_aggregate_run(backfill_runs)
    if best_backfill is not None:
        return best_backfill, "backfill_noncountable"
    return None, "missing"


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
    summary.pop("countable_score", None)
    if (
        summary["bucket"] in _CURRENT_AGGREGATE_COUNTABLE_BUCKETS
        and countability["countable"] is True
        and countability.get("score") is not None
    ):
        summary["countable_score"] = countability["score"]
    effective_failure_class = _current_aggregate_effective_failure_class(run)
    if effective_failure_class:
        summary["effective_failure_class"] = effective_failure_class
    return summary


def _current_aggregate_case_is_noncanonical_source(case: dict[str, Any]) -> bool:
    runs = _active_ledger_runs(
        [item for item in case.get("runs", []) if isinstance(item, dict)]
    )
    if not runs:
        return False
    saw_noncanonical_source_preflight = False
    for run in runs:
        if _ledger_score_value(run) is not None:
            return False
        failure_class = _current_aggregate_effective_failure_class(run)
        if failure_class not in {
            "skillsbench_task_source_preflight_blocked",
            "skillsbench_task_source_excluded",
        }:
            return False
        preflight = run.get("task_setup_preflight")
        if not isinstance(preflight, dict):
            return False
        if preflight.get("canonical_task_present") is not False:
            return False
        status = _compact_text(preflight.get("status"), limit=120)
        source_kind = _compact_text(preflight.get("alternate_source_kind"), limit=120)
        if status == "task_missing_from_canonical_tasks":
            source_is_noncanonical = source_kind == "experiments_sanity_tasks"
        elif status == "task_excluded_from_formal_tasks":
            source_is_noncanonical = (
                source_kind == "tasks_extra"
                and preflight.get("registry_excluded") is True
            )
        else:
            source_is_noncanonical = False
        if not source_is_noncanonical:
            return False
        if preflight.get("alternate_source_supported_by_runner") is not False:
            return False
        saw_noncanonical_source_preflight = True
    return saw_noncanonical_source_preflight


def _current_aggregate_case_is_noncanonical_sanity_source(case: dict[str, Any]) -> bool:
    """Compatibility wrapper for the historical aggregate option name."""

    return _current_aggregate_case_is_noncanonical_source(case)


def build_benchmark_run_ledger_current_aggregate(
    ledger: dict[str, Any],
    *,
    benchmark_id: str = "skillsbench@1.1",
    canonical_case_ids: list[str] | None = None,
    active_case_ids: list[str] | None = None,
    source_ledger_count: int = 1,
    exclude_noncanonical_sanity_sources: bool = True,
    target_lane_id: str | None = None,
    target_run_group_contains: list[str] | None = None,
    target_current_run_group_contains: list[str] | None = None,
    target_backfill_run_group_contains: list[str] | None = None,
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
                    and _current_aggregate_case_is_noncanonical_source(
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
                and _current_aggregate_case_is_noncanonical_source(case)
            )
        )
    active_ids = sorted(
        {
            normalized_case_id
            for case_id in (active_case_ids or [])
            for normalized_case_id in [_compact_text(case_id, limit=160)]
            if normalized_case_id
        }
    )
    active_id_set = set(active_ids)
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
    target_lane_enabled = _current_aggregate_target_lane_enabled(
        target_run_group_contains,
        target_current_run_group_contains,
        target_backfill_run_group_contains,
    )
    target_lane_source_counts = {
        "current_countable": 0,
        "backfill_countable": 0,
        "current_noncountable": 0,
        "backfill_noncountable": 0,
        "missing": 0,
    }
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
        target_lane_source = ""
        if target_lane_enabled:
            best, target_lane_source = _current_aggregate_select_target_lane_run(
                runs,
                target_run_group_contains=target_run_group_contains,
                target_current_run_group_contains=target_current_run_group_contains,
                target_backfill_run_group_contains=target_backfill_run_group_contains,
            )
            target_lane_source_counts[target_lane_source] = (
                target_lane_source_counts.get(target_lane_source, 0) + 1
            )
        else:
            best = _best_current_aggregate_run(runs)
        summary = _current_aggregate_run_summary(best)
        if target_lane_enabled:
            summary["target_lane_source"] = target_lane_source
        bucket = summary["bucket"]
        distribution[bucket] = distribution.get(bucket, 0) + 1
        cases_by_bucket.setdefault(bucket, []).append(case_id)
        case_best[case_id] = summary
        score = _ledger_score_value(summary)
        if (
            bucket in _CURRENT_AGGREGATE_COUNTABLE_BUCKETS
            and summary.get("official_score_countable") is True
            and score is not None
        ):
            countable_case_ids.append(case_id)
            countable_scores.append(score)
        elif score is not None:
            uncountable_numeric_case_ids.append(case_id)
    countable_score_sum = sum(countable_scores)
    countable_score_mean = (
        countable_score_sum / len(countable_scores) if countable_scores else None
    )
    accepted_case_ids = sorted(countable_case_ids)
    missing_case_ids = sorted(cases_by_bucket.get("missing", []))
    blocked_uncountable_case_ids = sorted(
        {
            case_id
            for bucket in (
                "setup_runner_infra",
                "uncountable_official_score",
                "verifier_no_reward",
            )
            for case_id in cases_by_bucket.get(bucket, [])
        }
    )
    runnable_missing_case_ids = [
        case_id for case_id in missing_case_ids if case_id not in active_id_set
    ]
    standard_case_sets = {
        "schema_version": "benchmark_run_ledger_standard_case_sets_v0",
        "policy": "accepted_numeric_official_scores_blocked_uncountable_infra_missing_elsewhere",
        "accepted_case_ids": accepted_case_ids,
        "missing_case_ids": missing_case_ids,
        "blocked_uncountable_case_ids": blocked_uncountable_case_ids,
        "active_case_ids": active_ids,
        "runnable_missing_case_ids": runnable_missing_case_ids,
        "raw_logs_recorded": False,
        "raw_task_text_recorded": False,
        "source_paths_recorded": False,
    }
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
            "countable_case_ids": accepted_case_ids,
            "uncountable_numeric_case_ids": sorted(uncountable_numeric_case_ids),
        },
        "distribution": distribution,
        "cases_by_bucket": {
            bucket: sorted(case_ids) for bucket, case_ids in cases_by_bucket.items()
        },
        "standard_case_sets": standard_case_sets,
        "accepted_case_ids": accepted_case_ids,
        "missing_case_ids": missing_case_ids,
        "blocked_uncountable_case_ids": blocked_uncountable_case_ids,
        "active_case_ids": active_ids,
        "runnable_missing_case_ids": runnable_missing_case_ids,
        "case_best": case_best,
        "deduped_run_count": len(deduped_run_ids),
        "source_ledger_files": source_ledger_count,
        "selection_policy": {
            "schema_version": "benchmark_run_ledger_current_selection_policy_v0",
            "rule": (
                "target_lane_current_countable_wins_backfill_fills_missing"
                if target_lane_enabled
                else "prefer_countable_official_result_over_missing_or_infra_rows"
            ),
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
            "target_lane": {
                "enabled": target_lane_enabled,
                "lane_id": _compact_text(target_lane_id, limit=120),
                "target_run_group_contains": [
                    _compact_text(value, limit=120)
                    for value in (target_run_group_contains or [])
                    if _compact_text(value, limit=120)
                ],
                "current_run_group_contains": [
                    _compact_text(value, limit=120)
                    for value in (target_current_run_group_contains or [])
                    if _compact_text(value, limit=120)
                ],
                "backfill_run_group_contains": [
                    _compact_text(value, limit=120)
                    for value in (target_backfill_run_group_contains or [])
                    if _compact_text(value, limit=120)
                ],
                "case_source_counts": target_lane_source_counts,
                "current_evidence_rule": (
                    "target-lane runs that do not match backfill patterns are current "
                    "evidence unless explicit current patterns are provided"
                ),
                "duplicate_case_rule": (
                    "current countable official score wins; backfill countable "
                    "official score fills only when current countable evidence is absent"
                ),
            },
        },
    }
