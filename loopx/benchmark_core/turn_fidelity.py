"""Compact fidelity gates for SkillsBench Goal versus LoopX Turn pairs."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from .loop_protocol import LOOPX_TURN_AGENT_CLI_ROUTE


LOOPX_TURN_BENCHMARK_FIDELITY_SCHEMA_VERSION = (
    "skillsbench_loopx_turn_benchmark_fidelity_v0"
)
LOOPX_TURN_MATCHED_PAIR_SCHEMA_VERSION = (
    "skillsbench_loopx_turn_goal_matched_pair_v0"
)
CODEX_CLI_GOAL_BASELINE_ROUTE = "codex-cli-goal-baseline"
COUNTABLE_ATTEMPT_FIELDS = (
    "launcher_attempt_countable",
    "case_attempt_countable",
    "solver_attempt_countable",
    "verifier_attempt_countable",
    "official_score_attempt_countable",
)


def _safe_label(value: object, *, limit: int = 120) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9@._:/+= -]+", "_", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _positive_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _finite_score(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _public_fingerprint(run: Mapping[str, Any]) -> str:
    fingerprint = _as_mapping(run.get("loopx_runner_source_fingerprint"))
    for value in (
        fingerprint.get("fingerprint"),
        fingerprint.get("source_fingerprint"),
        run.get("runner_source_fingerprint"),
    ):
        label = _safe_label(value, limit=160)
        if label:
            return label
    return ""


def _reasoning_effort(run: Mapping[str, Any]) -> str:
    config = _as_mapping(run.get("loopx_runner_config"))
    return _safe_label(
        run.get("reasoning_effort") or config.get("reasoning_effort"),
        limit=40,
    )


def _round_budget(run: Mapping[str, Any]) -> int:
    contract = _as_mapping(run.get("benchmark_loop_contract"))
    for value in (run.get("max_rounds_budget"), contract.get("max_rounds_budget")):
        parsed = _positive_int(value)
        if parsed:
            return parsed
    return 0


def _attempts_countable(run: Mapping[str, Any]) -> tuple[bool, list[str]]:
    missing = [field for field in COUNTABLE_ATTEMPT_FIELDS if run.get(field) is not True]
    if not _finite_score(run.get("official_score")):
        missing.append("official_score")
    return not missing, missing


def _safe_boundary(run: Mapping[str, Any]) -> dict[str, bool]:
    boundary = _as_mapping(run.get("public_boundary"))
    interaction = _as_mapping(run.get("interaction_counters"))
    return {
        "raw_task_text_absent": boundary.get("raw_task_text_recorded") is False
        and interaction.get("raw_task_text_recorded") is not True,
        "raw_verifier_output_absent": boundary.get("raw_verifier_output_recorded")
        is False
        and interaction.get("raw_verifier_output_recorded") is not True,
        "raw_agent_trajectory_absent": boundary.get("raw_agent_trajectory_recorded")
        is False
        and interaction.get("raw_agent_trajectory_recorded") is not True,
        "raw_host_output_absent": boundary.get("raw_host_output_recorded") is False,
        "credentials_absent": boundary.get("credentials_recorded") is False,
        "local_paths_absent": boundary.get("local_paths_recorded") is False,
    }


def _turn_executions(
    run: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], bool]:
    executions = run.get("loopx_turn_executions")
    if isinstance(executions, list):
        valid = bool(executions) and all(
            isinstance(item, Mapping) for item in executions
        )
        return [item for item in executions if isinstance(item, Mapping)], valid
    execution = run.get("loopx_turn_execution")
    if isinstance(execution, Mapping):
        return [execution], True
    return [], False


def build_loopx_turn_benchmark_fidelity_check(
    benchmark_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Require real Turn transaction evidence before treating a run as Turn."""

    route = _safe_label(benchmark_run.get("route"), limit=120)
    executions, execution_items_valid = _turn_executions(benchmark_run)

    def all_turns(predicate: Callable[[Mapping[str, Any]], bool]) -> bool:
        return bool(executions) and all(predicate(execution) for execution in executions)

    scored_validation = _as_mapping(
        benchmark_run.get("scored_workspace_validation")
    )
    safety_checks = _safe_boundary(benchmark_run)
    evidence_checks = {
        "canonical_turn_route": route == LOOPX_TURN_AGENT_CLI_ROUTE,
        "one_or_more_turns": bool(executions),
        "turn_execution_items_valid": execution_items_valid,
        "turn_execution_schema": all_turns(
            lambda execution: execution.get("schema_version")
            == "loopx_turn_execution_v0"
        ),
        "run_once_committed": all_turns(
            lambda execution: execution.get("mode") == "run_once"
            and execution.get("status") == "committed"
        ),
        "validated_material_result": all_turns(
            lambda execution: execution.get("result_kind")
            in {"validated_progress", "validated_completion"}
        ),
        "independent_turn_validation_passed": all_turns(
            lambda execution: _as_mapping(execution.get("validation")).get("status")
            == "passed"
        ),
        "turn_receipt_committed": all_turns(
            lambda execution: _as_mapping(execution.get("receipt")).get("status")
            == "committed"
        ),
        "agent_cli_host_observed": all_turns(
            lambda execution: _as_mapping(execution.get("host")).get("kind")
            in {"codex-cli", "generic-cli"}
        ),
        "isolated_headless_execution": all_turns(
            lambda execution: execution.get("execution_mode")
            == "isolated-headless"
        ),
        "host_invoked": all_turns(
            lambda execution: _as_mapping(execution.get("effects")).get(
                "host_invoked"
            )
            is True
        ),
        "durable_state_written": all_turns(
            lambda execution: _as_mapping(execution.get("effects")).get(
                "state_written"
            )
            is True
        ),
        "exactly_one_quota_spend_per_turn": all_turns(
            lambda execution: _as_mapping(execution.get("effects")).get(
                "quota_spent"
            )
            is True
            and _positive_int(execution.get("quota_slot_spend_count")) == 1
        ),
        "scored_workspace_validation_passed": (
            scored_validation.get("status") == "passed"
            and scored_validation.get("independent") is True
            and scored_validation.get("oracle_feedback_used") is False
        ),
        "scored_workspace_bridge_observed": (
            _positive_int(scored_validation.get("meaningful_operation_count")) > 0
        ),
        "official_feedback_blinded": (
            benchmark_run.get("official_feedback_blinded") is True
            and benchmark_run.get("reward_feedback_forwarded") is False
        ),
    }
    missing_evidence = [key for key, value in evidence_checks.items() if not value]
    safety_failures = [key for key, value in safety_checks.items() if not value]
    fidelity_allowed = not missing_evidence and not safety_failures
    return {
        "schema_version": LOOPX_TURN_BENCHMARK_FIDELITY_SCHEMA_VERSION,
        "benchmark_id": _safe_label(benchmark_run.get("benchmark_id"), limit=80),
        "case_id": _safe_label(benchmark_run.get("case_id"), limit=120),
        "route": route,
        "turn_count": len(executions),
        "turn_treatment_fidelity_allowed": fidelity_allowed,
        "claim_level": (
            "real_loopx_turn_treatment"
            if fidelity_allowed
            else "not_countable_as_loopx_turn_treatment"
        ),
        "evidence_checks": evidence_checks,
        "safety_checks": safety_checks,
        "missing_evidence": missing_evidence,
        "safety_failures": safety_failures,
        "read_boundary": {
            "compact_benchmark_run_only": True,
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "raw_trajectory_read": False,
            "verifier_output_read": False,
            "credentials_read": False,
        },
    }


def build_loopx_turn_goal_matched_pair_check(
    *,
    baseline_run: Mapping[str, Any],
    treatment_run: Mapping[str, Any],
) -> dict[str, Any]:
    """Gate effect analysis on a matched, official, countable Goal/Turn pair."""

    blockers: list[str] = []
    baseline_route = _safe_label(baseline_run.get("route"), limit=120)
    if baseline_route != CODEX_CLI_GOAL_BASELINE_ROUTE:
        blockers.append("baseline_not_codex_cli_goal")

    baseline_countable, baseline_missing = _attempts_countable(baseline_run)
    treatment_countable, treatment_missing = _attempts_countable(treatment_run)
    if not baseline_countable:
        blockers.append("baseline_not_official_countable")
    if not treatment_countable:
        blockers.append("treatment_not_official_countable")

    fidelity = build_loopx_turn_benchmark_fidelity_check(treatment_run)
    if fidelity.get("turn_treatment_fidelity_allowed") is not True:
        blockers.append("treatment_not_real_loopx_turn")

    parity_fields = {
        "benchmark_id": (
            _safe_label(baseline_run.get("benchmark_id"), limit=80),
            _safe_label(treatment_run.get("benchmark_id"), limit=80),
        ),
        "case_id": (
            _safe_label(baseline_run.get("case_id"), limit=120),
            _safe_label(treatment_run.get("case_id"), limit=120),
        ),
        "agent_model": (
            _safe_label(baseline_run.get("agent_model"), limit=80),
            _safe_label(treatment_run.get("agent_model"), limit=80),
        ),
        "reasoning_effort": (
            _reasoning_effort(baseline_run),
            _reasoning_effort(treatment_run),
        ),
        "max_rounds_budget": (
            _round_budget(baseline_run),
            _round_budget(treatment_run),
        ),
        "runner_source_fingerprint": (
            _public_fingerprint(baseline_run),
            _public_fingerprint(treatment_run),
        ),
    }
    parity_checks: dict[str, bool] = {}
    for field, values in parity_fields.items():
        left, right = values
        matched = bool(left) and left == right
        parity_checks[field] = matched
        if not matched:
            blockers.append(f"{field}_mismatch_or_missing")

    if baseline_run.get("official_feedback_blinded") is not True:
        blockers.append("baseline_official_feedback_not_blinded")
    if baseline_run.get("reward_feedback_forwarded") is not False:
        blockers.append("baseline_reward_feedback_forwarding_not_disabled")

    comparison_allowed = not blockers
    baseline_score = baseline_run.get("official_score")
    treatment_score = treatment_run.get("official_score")
    return {
        "schema_version": LOOPX_TURN_MATCHED_PAIR_SCHEMA_VERSION,
        "matched_pair_countable": comparison_allowed,
        "effect_analysis_allowed": comparison_allowed,
        "advantage_claim_allowed": False,
        "claim_policy": (
            "analyze_compact_outcome_and_lifecycle_without_advantage_claim"
            if comparison_allowed
            else "repair_runner_setup_or_fidelity_before_comparison"
        ),
        "blockers": blockers,
        "attempt_accounting": {
            "baseline_countable": baseline_countable,
            "baseline_missing": baseline_missing,
            "treatment_countable": treatment_countable,
            "treatment_missing": treatment_missing,
        },
        "parity_checks": parity_checks,
        "treatment_fidelity": fidelity,
        "official_scores": {
            "baseline": baseline_score if _finite_score(baseline_score) else None,
            "treatment": treatment_score if _finite_score(treatment_score) else None,
            "delta": (
                float(treatment_score) - float(baseline_score)
                if comparison_allowed
                else None
            ),
        },
    }
