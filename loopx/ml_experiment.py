from __future__ import annotations

import math
import re
from typing import Any, Iterable


DOMAIN_PACK_CONTRACT_SCHEMA_VERSION = "domain_pack_contract_v0"
ML_EXPERIMENT_ADVISORY_PACKET_SCHEMA_VERSION = "ml_experiment_advisory_packet_v0"
ML_EXPERIMENT_RESULT_SCHEMA_VERSION = "ml_experiment_result_v0"
DATASET_WINDOW_CONTRACT_SCHEMA_VERSION = "dataset_window_contract_v0"
HYPOTHESIS_LEDGER_SCHEMA_VERSION = "hypothesis_ledger_v0"
EXPERIMENT_REPLAN_SCHEMA_VERSION = "experiment_replan_v0"

GUARDRAIL_STATUSES = ("clean", "warning", "failed", "unknown")
HYPOTHESIS_STATUSES = ("active", "supported", "weakened", "retired", "unknown")

_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
_ABSOLUTE_PATH_RE = re.compile(
    r"(^|[\s:=])(?:"
    + "/" + "Users/"
    + "|/private/|/tmp/|~[/\\s]|[A-Za-z]:\\\\)"
)
_URL_OR_REMOTE_PATH_RE = re.compile(r"(?i)\b(?:https?|file|s3|gs|tos|hdfs)://")
_PRIVATE_MARKER_TERMS = [
    "author" + "ization:",
    r"bearer\s+[A-Za-z0-9._-]+",
    r"api[_-]?" + "key",
    "pass" + "word",
    "sec" + "ret",
    r"begin (?:rsa |open)?private " + "key",
    "lark" + "office",
    r"fei" + r"shu\.cn",
    "byte" + "dance",
]
_PRIVATE_MARKER_RE = re.compile(r"(?i)(" + "|".join(_PRIVATE_MARKER_TERMS) + ")")


def _compact_public_text(value: str, *, field: str, max_len: int = 160) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        raise ValueError(f"{field} must be non-empty")
    if len(text) > max_len:
        raise ValueError(f"{field} is too long for a compact public-safe field")
    if ".." in text:
        raise ValueError(f"{field} must not contain parent-directory markers")
    if _ABSOLUTE_PATH_RE.search(text) or text.startswith(("/", "~")):
        raise ValueError(f"{field} must use a public alias, not a local/private path")
    if _URL_OR_REMOTE_PATH_RE.search(text):
        raise ValueError(f"{field} must use a public alias, not a raw URL or remote path")
    if _PRIVATE_MARKER_RE.search(text):
        raise ValueError(f"{field} contains a private or credential-like marker")
    return text


def _compact_public_token(value: str, *, field: str) -> str:
    token = _compact_public_text(value, field=field, max_len=80)
    if not _TOKEN_RE.match(token):
        raise ValueError(
            f"{field} must be a compact public token using letters, digits, dot, colon, dash, or underscore"
        )
    return token


def _compact_public_text_list(values: Iterable[str] | None, *, field: str) -> list[str]:
    return [_compact_public_text(value, field=f"{field}[]") for value in values or []]


def _finite_float(value: float | int | str, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def build_ml_experiment_domain_pack_contract(*, enabled: bool = False) -> dict[str, Any]:
    """Return the default-off ML experiment domain-pack boundary."""

    return {
        "schema_version": DOMAIN_PACK_CONTRACT_SCHEMA_VERSION,
        "pack": "ml_experiment",
        "enabled": bool(enabled),
        "autonomy": "suggest_only" if not enabled else "advisory",
        "allowed_actions": [
            "ingest_metrics",
            "classify_results",
            "write_hypothesis_ledger",
            "propose_replan",
        ],
        "disabled_actions": [
            "launch_training_job",
            "stop_training_job",
            "restart_training_job",
            "sync_to_production",
            "select_primary_metric_without_authority",
        ],
        "capability_requirements": [
            "compact_public_metric_artifact",
            "dataset_window_contract",
            "hypothesis_ledger",
        ],
        "authority_boundary": {
            "primary_metric_authority": "explicit_board_or_owner_decision_only",
            "launch_authority": "disabled_until_explicit_registry_delivery_mode",
            "production_authority": "disabled_until_explicit_registry_delivery_mode",
        },
    }


def build_dataset_window_contract(
    *,
    train_window: str,
    eval_window: str,
    granularity: str = "daily",
    intersection_policy: str = "matched_window_only",
    missing_window_policy: str = "mark_inconclusive",
) -> dict[str, Any]:
    return {
        "schema_version": DATASET_WINDOW_CONTRACT_SCHEMA_VERSION,
        "train_window": _compact_public_text(train_window, field="train_window"),
        "eval_window": _compact_public_text(eval_window, field="eval_window"),
        "granularity": _compact_public_token(granularity, field="granularity"),
        "intersection_policy": _compact_public_token(intersection_policy, field="intersection_policy"),
        "missing_window_policy": _compact_public_token(missing_window_policy, field="missing_window_policy"),
        "conclusion_eligibility": "eligible_if_windows_match_and_guardrails_clear",
    }


def build_hypothesis_ledger_entry(
    *,
    hypothesis_id: str,
    mechanism_family: str,
    route: str,
    status: str = "active",
    positive_evidence: Iterable[str] | None = None,
    negative_evidence: Iterable[str] | None = None,
) -> dict[str, Any]:
    compact_status = _compact_public_token(status, field="hypothesis_status")
    if compact_status not in HYPOTHESIS_STATUSES:
        raise ValueError(f"hypothesis_status must be one of {', '.join(HYPOTHESIS_STATUSES)}")
    return {
        "schema_version": HYPOTHESIS_LEDGER_SCHEMA_VERSION,
        "hypothesis_id": _compact_public_token(hypothesis_id, field="hypothesis_id"),
        "mechanism_family": _compact_public_text(mechanism_family, field="mechanism_family"),
        "route": _compact_public_token(route, field="route"),
        "status": compact_status,
        "positive_evidence": _compact_public_text_list(positive_evidence, field="positive_evidence"),
        "negative_evidence": _compact_public_text_list(negative_evidence, field="negative_evidence"),
        "raw_metrics_recorded": False,
        "private_artifacts_recorded": False,
    }


def classify_primary_metric_delta(
    *,
    baseline_value: float,
    candidate_value: float,
    higher_is_better: bool,
) -> dict[str, Any]:
    baseline = _finite_float(baseline_value, field="baseline_value")
    candidate = _finite_float(candidate_value, field="candidate_value")
    delta = candidate - baseline
    signed_improvement = delta if higher_is_better else -delta
    if abs(delta) < 1e-12:
        status = "flat"
    elif signed_improvement > 0:
        status = "improved"
    else:
        status = "regressed"
    relative_delta = None if abs(baseline) < 1e-12 else delta / abs(baseline)
    return {
        "baseline_value": baseline,
        "candidate_value": candidate,
        "delta": delta,
        "relative_delta": relative_delta,
        "higher_is_better": bool(higher_is_better),
        "primary_metric_status": status,
    }


def build_ml_experiment_result(
    *,
    experiment_id: str,
    primary_metric: str,
    baseline_value: float,
    candidate_value: float,
    higher_is_better: bool = True,
    guardrail_status: str = "unknown",
    dataset_window: dict[str, Any],
    hypothesis: dict[str, Any],
) -> dict[str, Any]:
    compact_guardrail_status = _compact_public_token(guardrail_status, field="guardrail_status")
    if compact_guardrail_status not in GUARDRAIL_STATUSES:
        raise ValueError(f"guardrail_status must be one of {', '.join(GUARDRAIL_STATUSES)}")
    metric = classify_primary_metric_delta(
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        higher_is_better=higher_is_better,
    )
    if compact_guardrail_status == "failed":
        decision_status = "blocked_by_guardrail"
    elif metric["primary_metric_status"] == "improved" and compact_guardrail_status == "clean":
        decision_status = "candidate_not_winner_yet"
    elif metric["primary_metric_status"] == "regressed":
        decision_status = "needs_replan"
    else:
        decision_status = "inconclusive"
    return {
        "schema_version": ML_EXPERIMENT_RESULT_SCHEMA_VERSION,
        "experiment_id": _compact_public_token(experiment_id, field="experiment_id"),
        "primary_metric": _compact_public_text(primary_metric, field="primary_metric"),
        **metric,
        "guardrail_status": compact_guardrail_status,
        "decision_status": decision_status,
        "dataset_window": dataset_window,
        "hypothesis": hypothesis,
        "raw_metrics_recorded": False,
        "private_artifacts_recorded": False,
    }


def build_experiment_replan_preview(
    *,
    result: dict[str, Any],
    next_candidates: Iterable[str] | None = None,
    allocation: str = "one_followup",
) -> dict[str, Any]:
    candidate_labels = _compact_public_text_list(next_candidates, field="next_candidate")
    if not candidate_labels:
        candidate_labels = ["near_neighbor_ablation", "guardrail_holdout_check"]
    decision_status = str(result.get("decision_status") or "inconclusive")
    if decision_status == "candidate_not_winner_yet":
        recommendation = "validate_on_holdout_before_promotion"
    elif decision_status == "blocked_by_guardrail":
        recommendation = "repair_guardrail_before_more_exploration"
    else:
        recommendation = "run_one_followup_or_retire_hypothesis"
    return {
        "schema_version": EXPERIMENT_REPLAN_SCHEMA_VERSION,
        "recommendation": recommendation,
        "allocation": _compact_public_token(allocation, field="allocation"),
        "next_candidates": candidate_labels,
        "launch_actions_enabled": False,
        "production_actions_enabled": False,
        "requires_explicit_authorization": True,
    }


def build_ml_experiment_advisory_packet(
    *,
    experiment_id: str,
    primary_metric: str,
    baseline_value: float,
    candidate_value: float,
    higher_is_better: bool = True,
    guardrail_status: str = "unknown",
    train_window: str,
    eval_window: str,
    granularity: str = "daily",
    hypothesis_id: str,
    mechanism_family: str,
    route: str,
    hypothesis_status: str = "active",
    positive_evidence: Iterable[str] | None = None,
    negative_evidence: Iterable[str] | None = None,
    next_candidates: Iterable[str] | None = None,
) -> dict[str, Any]:
    dataset_window = build_dataset_window_contract(
        train_window=train_window,
        eval_window=eval_window,
        granularity=granularity,
    )
    hypothesis = build_hypothesis_ledger_entry(
        hypothesis_id=hypothesis_id,
        mechanism_family=mechanism_family,
        route=route,
        status=hypothesis_status,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
    )
    result = build_ml_experiment_result(
        experiment_id=experiment_id,
        primary_metric=primary_metric,
        baseline_value=baseline_value,
        candidate_value=candidate_value,
        higher_is_better=higher_is_better,
        guardrail_status=guardrail_status,
        dataset_window=dataset_window,
        hypothesis=hypothesis,
    )
    replan = build_experiment_replan_preview(
        result=result,
        next_candidates=next_candidates,
    )
    return {
        "ok": True,
        "schema_version": ML_EXPERIMENT_ADVISORY_PACKET_SCHEMA_VERSION,
        "pack": build_ml_experiment_domain_pack_contract(enabled=False),
        "mode": "default_off_advisory_preview",
        "result": result,
        "replan_preview": replan,
        "raw_metrics_recorded": False,
        "private_artifacts_recorded": False,
        "launch_actions_enabled": False,
        "production_actions_enabled": False,
        "recommended_next_action": "owner_or_registry_can_enable_advisory_mode_for_this_goal",
    }


def render_ml_experiment_advisory_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return f"ML experiment advisory preview failed: {payload.get('error')}\n"
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    replan = payload.get("replan_preview") if isinstance(payload.get("replan_preview"), dict) else {}
    pack = payload.get("pack") if isinstance(payload.get("pack"), dict) else {}
    lines = [
        "# ML Experiment Advisory Preview",
        "",
        f"- experiment: `{result.get('experiment_id')}`",
        f"- primary metric: `{result.get('primary_metric')}`",
        f"- status: `{result.get('primary_metric_status')}`",
        f"- delta: `{result.get('delta')}`",
        f"- guardrail: `{result.get('guardrail_status')}`",
        f"- decision: `{result.get('decision_status')}`",
        f"- pack enabled: `{pack.get('enabled')}`",
        f"- launch actions enabled: `{payload.get('launch_actions_enabled')}`",
        f"- production actions enabled: `{payload.get('production_actions_enabled')}`",
        "",
        "## Replan Preview",
        "",
        f"- recommendation: `{replan.get('recommendation')}`",
        f"- allocation: `{replan.get('allocation')}`",
        "- next candidates: "
        + ", ".join(f"`{candidate}`" for candidate in replan.get("next_candidates", []) or []),
    ]
    return "\n".join(lines) + "\n"
