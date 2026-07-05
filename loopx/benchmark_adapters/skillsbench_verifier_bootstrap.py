"""Public-safe SkillsBench verifier bootstrap attribution helpers."""

from __future__ import annotations

from typing import Any


GENERIC_MISSING_ATTRIBUTIONS = {
    "",
    "none",
    "official_score_missing",
    "skillsbench_result_json_missing_after_runner_exit",
    "skillsbench_runner_error",
    "skillsbench_runner_failed_before_agent_install",
    "skillsbench_runner_interrupted_before_official_result",
    "skillsbench_runner_setup_error",
    "skillsbench_verifier_reward_missing",
}

SETUP_PREFLIGHT_REPLACEABLE_ATTRIBUTIONS = GENERIC_MISSING_ATTRIBUTIONS | {
    "skillsbench_product_mode_lifecycle_missing",
    "skillsbench_remote_bridge_agent_operation_trace_missing",
}

GENERIC_MISSING_LABELS = {
    "official_score_missing",
    "skillsbench_result_json_missing_after_runner_exit",
    "skillsbench_runner_error",
    "skillsbench_runner_failed_before_agent_install",
    "skillsbench_runner_interrupted_before_official_result",
    "skillsbench_runner_setup_error",
    "skillsbench_verifier_reward_missing",
}

SETUP_PREFLIGHT_REPLACEABLE_LABELS = GENERIC_MISSING_LABELS | {
    "skillsbench_product_mode_lifecycle_missing",
    "skillsbench_product_mode_uncountable_treatment",
    "skillsbench_remote_bridge_agent_operation_trace_missing",
}


def _public_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def apply_skillsbench_verifier_bootstrap_missing_score_attribution(
    compact: dict[str, Any],
    *,
    task_staging: dict[str, Any] | None = None,
    setup_preflight: dict[str, Any] | None = None,
) -> bool:
    """Classify missing official score when public preflight saw bootstrap risk."""

    if compact.get("official_score_status") != "missing":
        return False
    if compact.get("official_score") is not None:
        return False

    task_staging = task_staging if isinstance(task_staging, dict) else {}
    setup_preflight = setup_preflight if isinstance(setup_preflight, dict) else {}
    task_score = (
        compact.get("official_task_score")
        if isinstance(compact.get("official_task_score"), dict)
        else {}
    )
    score_kind = str(task_score.get("kind") or "")
    if score_kind and "missing" not in score_kind:
        return False

    uv_bootstrap_risk = (
        task_staging.get("verifier_uv_bootstrap_risk_detected") is True
        or setup_preflight.get("verifier_uv_bootstrap_risk_detected") is True
    )
    package_install_risk = (
        task_staging.get("verifier_package_install_risk_detected") is True
        or setup_preflight.get("verifier_package_install_risk_detected") is True
    )
    verifier_bootstrap_risk = (
        task_staging.get("verifier_bootstrap_risk_detected") is True
        or setup_preflight.get("verifier_bootstrap_risk_detected") is True
    )
    bootstrap_light_blocking_fields = setup_preflight.get(
        "bootstrap_light_blocking_fields"
    )
    if not isinstance(bootstrap_light_blocking_fields, list):
        bootstrap_light_blocking_fields = []
    explicit_bootstrap_blocked = (
        task_staging.get("verifier_bootstrap_risk_preflight_blocked") is True
        or setup_preflight.get("first_blocker") == "verifier_bootstrap_risk"
    )
    pre_agent_setup_blocked = (
        explicit_bootstrap_blocked
        or task_staging.get("staged") is False
        or setup_preflight.get("bootstrap_light_candidate_eligible") is False
        or "verifier_package_install_risk_detected" in bootstrap_light_blocking_fields
        or "verifier_bootstrap_risk_detected" in bootstrap_light_blocking_fields
    )
    verifier_bootstrap_blocked = explicit_bootstrap_blocked or (
        verifier_bootstrap_risk
        and pre_agent_setup_blocked
        and setup_preflight.get("status") == "verifier_bootstrap_risk_detected"
    )
    if not (
        uv_bootstrap_risk
        or verifier_bootstrap_blocked
        or (package_install_risk and verifier_bootstrap_risk)
    ):
        return False

    current_attribution = str(compact.get("score_failure_attribution") or "")
    replaceable_attributions = (
        SETUP_PREFLIGHT_REPLACEABLE_ATTRIBUTIONS
        if pre_agent_setup_blocked
        else GENERIC_MISSING_ATTRIBUTIONS
    )
    if current_attribution not in replaceable_attributions:
        return False

    existing_labels = [
        label
        for label in compact.get("failure_attribution_labels", [])
        if isinstance(label, str) and label
    ]
    replaceable_labels = (
        SETUP_PREFLIGHT_REPLACEABLE_LABELS
        if pre_agent_setup_blocked
        else GENERIC_MISSING_LABELS
    )
    if any(label not in replaceable_labels for label in existing_labels):
        return False

    attribution = "verifier_dependency_install_failure"
    compact["score_failure_attribution"] = attribution
    compact["first_blocker"] = attribution
    compact["repeat_blocked_by"] = attribution
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False
    compact["verifier_failure_attribution_count"] = max(
        1,
        _public_int(compact.get("verifier_failure_attribution_count")),
    )
    compact["verifier_dependency_failure_count"] = max(
        1,
        _public_int(compact.get("verifier_dependency_failure_count")),
    )

    labels = [
        label for label in existing_labels if label not in SETUP_PREFLIGHT_REPLACEABLE_LABELS
    ]
    for label in (
        attribution,
        "skillsbench_verifier_bootstrap_missing_official_score",
    ):
        if label not in labels:
            labels.append(label)
    if uv_bootstrap_risk:
        label = "verifier_uv_install_or_download_failure"
        if label not in labels:
            labels.append(label)
    if package_install_risk:
        label = "skillsbench_verifier_package_install_risk"
        if label not in labels:
            labels.append(label)
    if verifier_bootstrap_blocked:
        label = "skillsbench_verifier_bootstrap_preflight_blocked"
        if label not in labels:
            labels.append(label)
    compact["failure_attribution_labels"] = labels

    if isinstance(task_score, dict):
        task_score = dict(task_score)
        task_score["kind"] = "skillsbench_verifier_bootstrap_reward_missing"
        task_score["value"] = None
        task_score["passed"] = False
        compact["official_task_score"] = task_score

    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = attribution
        runner_failure["verifier_bootstrap_missing_score_attributed"] = True

    attempt_accounting = compact.get("attempt_accounting")
    if pre_agent_setup_blocked and isinstance(attempt_accounting, dict):
        attempt_accounting["failure_label"] = attribution
        attempt_accounting["failure_class"] = "job_materialization_failed"

    diagnostic: dict[str, Any] = {
        "schema_version": "skillsbench_verifier_bootstrap_missing_score_diagnostic_v0",
        "status": "missing_official_score_with_verifier_bootstrap_risk",
        "score_failure_attribution": attribution,
        "verifier_uv_bootstrap_risk_detected": uv_bootstrap_risk,
        "verifier_package_install_risk_detected": package_install_risk,
        "verifier_bootstrap_risk_preflight_blocked": verifier_bootstrap_blocked,
        "pre_agent_setup_blocked": pre_agent_setup_blocked,
        "verifier_uv_bootstrap_mirror_patch_required": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_required"
        )
        is True,
        "verifier_uv_bootstrap_mirror_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_mirror_patch_applied"
        )
        is True,
        "verifier_uv_bootstrap_pip_fallback_patch_applied": task_staging.get(
            "verifier_uv_bootstrap_pip_fallback_patch_applied"
        )
        is True,
        "raw_verifier_output_read": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "next_diagnostic_action": "prewarm_or_fail_fast_verifier_bootstrap_before_rerun",
    }
    for field in (
        "verifier_uv_bootstrap_version",
        "verifier_uv_bootstrap_mirror_host",
    ):
        value = task_staging.get(field) or setup_preflight.get(field)
        if isinstance(value, str) and value:
            diagnostic[field] = value[:180]
    compact["verifier_bootstrap_diagnostic"] = diagnostic

    validation = (
        compact.get("validation")
        if isinstance(compact.get("validation"), dict)
        else {}
    )
    validation["raw_verifier_output_read"] = False
    validation["verifier_bootstrap_missing_score_classified"] = True
    compact["validation"] = validation
    return True
