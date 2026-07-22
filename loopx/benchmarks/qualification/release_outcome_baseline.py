from __future__ import annotations

import re
from collections import Counter
from statistics import fmean
from typing import Any, Iterable, Mapping

from ..read_models.benchmark_result import compact_benchmark_result
from ...control_plane.runtime.public_safety import public_safe_compact_text


RELEASE_OUTCOME_PAIR_MANIFEST_SCHEMA_VERSION = "release_outcome_pair_manifest_v0"
RELEASE_OUTCOME_BASELINE_SCHEMA_VERSION = "release_outcome_baseline_v0"
RELEASE_OUTCOME_COMPARISON_KIND = "stable_release_vs_candidate"

_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_MANIFEST_FIELDS = {
    "schema_version",
    "comparison_kind",
    "baseline_ref",
    "candidate_ref",
    "policy",
    "pairs",
}
_POLICY_FIELDS = {
    "min_distinct_cases",
    "min_repetitions_per_case",
    "max_wall_time_ratio",
    "max_cost_ratio",
}
_PAIR_FIELDS = {
    "case_id",
    "repeat_index",
    "same_task_semantics",
    "same_runner_protocol",
    "same_verifier_contract",
    "same_budget",
    "baseline_result",
    "candidate_result",
}
_PUBLIC_TRACE_LABELS = {
    "public",
    "public-safe",
    "compact_public",
    "public_safe_compact",
}
_COMPLETED_TERMINAL_STATES = {"completed", "resolved", "success", "succeeded"}
_REQUIRED_PARITY_FIELDS = (
    "same_task_semantics",
    "same_runner_protocol",
    "same_verifier_contract",
    "same_budget",
)


def _token(value: Any, *, field: str) -> str:
    text = public_safe_compact_text(value, limit=160)
    if text is None or not _TOKEN_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a compact public-safe token")
    return text


def _bounded_int(
    value: Any,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def _positive_ratio(value: Any, *, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    normalized = float(value)
    if normalized < 1.0 or normalized > 10.0:
        raise ValueError(f"{field} must be between 1.0 and 10.0")
    return normalized


def _normalized_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("manifest.policy must be an object")
    unknown = set(value) - _POLICY_FIELDS
    if unknown:
        raise ValueError("manifest.policy contains unknown fields")
    return {
        "min_distinct_cases": _bounded_int(
            value.get("min_distinct_cases"),
            field="policy.min_distinct_cases",
            minimum=2,
            maximum=12,
        ),
        "min_repetitions_per_case": _bounded_int(
            value.get("min_repetitions_per_case"),
            field="policy.min_repetitions_per_case",
            minimum=2,
            maximum=8,
        ),
        "max_wall_time_ratio": _positive_ratio(
            value.get("max_wall_time_ratio"), field="policy.max_wall_time_ratio"
        ),
        "max_cost_ratio": _positive_ratio(
            value.get("max_cost_ratio"), field="policy.max_cost_ratio"
        ),
    }


def _exact_compact_result(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a compact benchmark_result_v0 object")
    source = dict(value)
    compact = compact_benchmark_result(source)
    if compact is None or compact != source:
        raise ValueError(
            f"{field} must already be an exact compact benchmark_result_v0 object"
        )
    trace_publicness = compact.get("trace_publicness")
    if trace_publicness not in _PUBLIC_TRACE_LABELS:
        raise ValueError(f"{field}.trace_publicness must declare compact public evidence")
    official_score = compact.get("official_task_score")
    if not isinstance(official_score, Mapping) or not isinstance(
        official_score.get("passed"), bool
    ):
        raise ValueError(f"{field}.official_task_score.passed must be explicit")
    counts = compact.get("counts")
    if not isinstance(counts, Mapping):
        raise ValueError(f"{field}.counts must be present")
    for count_field in ("wall_time_ms", "cost_usd"):
        count = counts.get(count_field)
        if (
            not isinstance(count, (int, float))
            or isinstance(count, bool)
            or count < 0
        ):
            raise ValueError(f"{field}.counts.{count_field} must be non-negative")
    for count_field in ("erroneous_write_count", "human_intervention_count"):
        count = counts.get(count_field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(
                f"{field}.counts.{count_field} must be a non-negative integer"
            )
    if not isinstance(compact.get("stop_policy_correct"), bool):
        raise ValueError(f"{field}.stop_policy_correct must be explicit")
    if not compact.get("task_id") or not compact.get("terminal_state"):
        raise ValueError(f"{field} must include task_id and terminal_state")
    return compact


def _normalize_pair(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("manifest.pairs[] must be an object")
    unknown = set(value) - _PAIR_FIELDS
    if unknown:
        raise ValueError("manifest.pairs[] contains unknown fields")
    for field in _REQUIRED_PARITY_FIELDS:
        if value.get(field) is not True:
            raise ValueError(f"manifest.pairs[].{field} must be true")
    baseline = _exact_compact_result(
        value.get("baseline_result"), field="manifest.pairs[].baseline_result"
    )
    candidate = _exact_compact_result(
        value.get("candidate_result"), field="manifest.pairs[].candidate_result"
    )
    if baseline["task_id"] != candidate["task_id"]:
        raise ValueError("paired results must have the same task_id")
    return {
        "case_id": _token(value.get("case_id"), field="manifest.pairs[].case_id"),
        "repeat_index": _bounded_int(
            value.get("repeat_index"),
            field="manifest.pairs[].repeat_index",
            minimum=1,
            maximum=32,
        ),
        "baseline_result": baseline,
        "candidate_result": candidate,
    }


def _normalize_manifest(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("manifest must be an object")
    unknown = set(value) - _MANIFEST_FIELDS
    if unknown:
        raise ValueError("manifest contains unknown fields")
    if value.get("schema_version") != RELEASE_OUTCOME_PAIR_MANIFEST_SCHEMA_VERSION:
        raise ValueError("manifest must use release_outcome_pair_manifest_v0")
    if value.get("comparison_kind") != RELEASE_OUTCOME_COMPARISON_KIND:
        raise ValueError(
            "manifest.comparison_kind must be stable_release_vs_candidate"
        )
    raw_pairs = value.get("pairs")
    if not isinstance(raw_pairs, list) or not raw_pairs:
        raise ValueError("manifest.pairs must be a non-empty list")
    if len(raw_pairs) > 96:
        raise ValueError("manifest.pairs must contain at most 96 paired attempts")
    pairs = [_normalize_pair(pair) for pair in raw_pairs]
    identities = [(pair["case_id"], pair["repeat_index"]) for pair in pairs]
    if len(set(identities)) != len(identities):
        raise ValueError("manifest contains a duplicate case_id/repeat_index pair")
    case_tasks: dict[str, str] = {}
    for pair in pairs:
        case_id = pair["case_id"]
        task_id = pair["baseline_result"]["task_id"]
        if case_id in case_tasks and case_tasks[case_id] != task_id:
            raise ValueError("each case_id must keep the same task_id across repetitions")
        case_tasks[case_id] = task_id
    baseline_ref = _token(value.get("baseline_ref"), field="manifest.baseline_ref")
    candidate_ref = _token(
        value.get("candidate_ref"), field="manifest.candidate_ref"
    )
    if baseline_ref == candidate_ref:
        raise ValueError("manifest baseline_ref and candidate_ref must differ")
    return {
        "schema_version": RELEASE_OUTCOME_PAIR_MANIFEST_SCHEMA_VERSION,
        "comparison_kind": RELEASE_OUTCOME_COMPARISON_KIND,
        "baseline_ref": baseline_ref,
        "candidate_ref": candidate_ref,
        "policy": _normalized_policy(value.get("policy")),
        "pairs": pairs,
    }


def _mean(values: Iterable[float]) -> float:
    return round(fmean(values), 6)


def _arm_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    attempt_count = len(results)
    completed_count = sum(
        result["terminal_state"] in _COMPLETED_TERMINAL_STATES for result in results
    )
    verifier_pass_count = sum(
        result["official_task_score"]["passed"] is True for result in results
    )
    stop_correct_count = sum(result["stop_policy_correct"] is True for result in results)
    erroneous_write_count = sum(
        float(result["counts"]["erroneous_write_count"]) for result in results
    )
    human_intervention_count = sum(
        float(result["counts"]["human_intervention_count"]) for result in results
    )
    return {
        "attempt_count": attempt_count,
        "completed_count": completed_count,
        "completion_rate": round(completed_count / attempt_count, 6),
        "verifier_pass_count": verifier_pass_count,
        "verifier_pass_rate": round(verifier_pass_count / attempt_count, 6),
        "erroneous_write_count": erroneous_write_count,
        "human_intervention_count": human_intervention_count,
        "stop_policy_correct_count": stop_correct_count,
        "stop_policy_correct_rate": round(stop_correct_count / attempt_count, 6),
        "mean_wall_time_ms": _mean(
            float(result["counts"]["wall_time_ms"]) for result in results
        ),
        "mean_cost_usd": _mean(
            float(result["counts"]["cost_usd"]) for result in results
        ),
    }


def _ratio(candidate: float, baseline: float) -> float | None:
    if baseline == 0:
        return 1.0 if candidate == 0 else None
    return round(candidate / baseline, 6)


def build_release_outcome_baseline(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Reduce paired compact outcomes into a review-only release receipt."""

    normalized = _normalize_manifest(manifest)
    pairs = normalized["pairs"]
    policy = normalized["policy"]
    case_repetitions = Counter(pair["case_id"] for pair in pairs)
    baseline_results = [pair["baseline_result"] for pair in pairs]
    candidate_results = [pair["candidate_result"] for pair in pairs]
    baseline_metrics = _arm_metrics(baseline_results)
    candidate_metrics = _arm_metrics(candidate_results)

    deltas = {
        field: round(candidate_metrics[field] - baseline_metrics[field], 6)
        for field in (
            "completion_rate",
            "verifier_pass_rate",
            "erroneous_write_count",
            "human_intervention_count",
            "stop_policy_correct_rate",
        )
    }
    wall_time_ratio = _ratio(
        candidate_metrics["mean_wall_time_ms"], baseline_metrics["mean_wall_time_ms"]
    )
    cost_ratio = _ratio(
        candidate_metrics["mean_cost_usd"], baseline_metrics["mean_cost_usd"]
    )
    deltas["wall_time_ratio"] = wall_time_ratio
    deltas["cost_ratio"] = cost_ratio

    evidence_gaps: list[str] = []
    if len(case_repetitions) < policy["min_distinct_cases"]:
        evidence_gaps.append("insufficient_distinct_cases")
    if any(
        repeat_count < policy["min_repetitions_per_case"]
        for repeat_count in case_repetitions.values()
    ):
        evidence_gaps.append("insufficient_repetitions_per_case")

    regressions: list[str] = []
    for field in ("completion_rate", "verifier_pass_rate", "stop_policy_correct_rate"):
        if deltas[field] < 0:
            regressions.append(field)
    for field in ("erroneous_write_count", "human_intervention_count"):
        if deltas[field] > 0:
            regressions.append(field)
    if wall_time_ratio is None or wall_time_ratio > policy["max_wall_time_ratio"]:
        regressions.append("wall_time_ratio")
    if cost_ratio is None or cost_ratio > policy["max_cost_ratio"]:
        regressions.append("cost_ratio")

    decision = "owner_review_required"
    if evidence_gaps:
        decision = "insufficient_evidence"
    elif regressions:
        decision = "hold_regression"

    return {
        "schema_version": RELEASE_OUTCOME_BASELINE_SCHEMA_VERSION,
        "comparison_kind": normalized["comparison_kind"],
        "baseline_ref": normalized["baseline_ref"],
        "candidate_ref": normalized["candidate_ref"],
        "decision": decision,
        "eligible_for_owner_review": decision == "owner_review_required",
        "automatic_release_promotion_allowed": False,
        "coverage": {
            "distinct_case_count": len(case_repetitions),
            "paired_attempt_count": len(pairs),
            "case_repetitions": dict(sorted(case_repetitions.items())),
            "policy": policy,
            "evidence_gaps": evidence_gaps,
        },
        "baseline": baseline_metrics,
        "candidate": candidate_metrics,
        "deltas": deltas,
        "regressions": regressions,
        "read_boundary": {
            "compact_benchmark_results_only": True,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "raw_verifier_output_read": False,
            "local_paths_recorded": False,
            "model_api_invoked": False,
            "benchmark_execution_invoked": False,
            "release_mutation_invoked": False,
        },
    }
