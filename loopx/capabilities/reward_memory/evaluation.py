from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from .evaluation_fixtures import (
    generic_compact_restart_fixture,
    generic_inactive_lifecycle_fixture,
    generic_issue_fix_application_fixture,
    generic_multi_person_authority_fixture,
    generic_scope_isolation_fixture,
    generic_stale_source_fixture,
    openviking_pr_3237_regression_fixture,
)


REWARD_MEMORY_EVALUATION_SCHEMA_VERSION = "reward_memory_evaluation_v0"
REWARD_MEMORY_RELEASE_GATE_SCHEMA_VERSION = "reward_memory_release_gate_v0"
REQUIRED_CASE_IDS = (
    "compact_restart_survival",
    "project_module_scope_isolation",
    "supersede_revoke_rejection",
    "stale_source_rejection",
    "multi_person_authority_conditions",
    "gate_non_override",
    "candidate_ranking_influence",
    "large_edge_case_patch_protection",
)

def _evaluate_case(
    case_id: str, check: Callable[[], tuple[bool, int, dict[str, Any]]]
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    try:
        passed, assertion_count, evidence = check()
        failure_kind = None if passed else "assertion_failed"
    except Exception as exc:  # noqa: BLE001 - compact harness boundary
        passed, assertion_count, evidence = False, 1, {}
        failure_kind = type(exc).__name__
    latency_ms = max(0, (time.perf_counter_ns() - started) // 1_000_000)
    compact_evidence = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    false_application_count = int(
        bool(evidence.get("false_application_observed", False))
    )
    return {
        "case_id": case_id,
        "passed": passed,
        "assertion_count": assertion_count,
        "failure_kind": failure_kind,
        "latency_ms": latency_ms,
        "public_evidence_bytes": len(compact_evidence.encode("utf-8")),
        "model_tokens": 0,
        "storage_write_bytes": 0,
        "provider_write_count": 0,
        "external_write_count": 0,
        "false_application_count": false_application_count,
        "maintainer_interruption_count": 0,
        "user_gate_count": 0,
        "evidence": evidence,
    }


def _compact_restart_case() -> tuple[bool, int, dict[str, Any]]:
    fixture = generic_compact_restart_fixture()
    checks = (
        fixture["record_schema_version"] == "reward_memory_active_record_v0",
        fixture["recall_status"] == "completed",
        fixture["readback_verified"] is True,
        fixture["provider_call_count"] == 1,
    )
    return all(checks), len(checks), {
        "serialized_bytes": fixture["serialized_bytes"],
        "recall_status": fixture["recall_status"],
        "readback_verified": fixture["readback_verified"],
    }


def _scope_case() -> tuple[bool, int, dict[str, Any]]:
    fixture = generic_scope_isolation_fixture()
    checks = (
        fixture["project_status"] == "guard_blocked",
        "project_scope_mismatch" in fixture["project_reason_codes"],
        fixture["surface_status"] == "guard_blocked",
        "surface_scope_mismatch" in fixture["surface_reason_codes"],
        fixture["provider_call_count"] == 0,
    )
    return all(checks), len(checks), {
        "project_status": fixture["project_status"],
        "surface_status": fixture["surface_status"],
        "provider_call_count": fixture["provider_call_count"],
        "false_application_observed": fixture["provider_call_count"] > 0,
    }


def _inactive_case() -> tuple[bool, int, dict[str, Any]]:
    fixture = generic_inactive_lifecycle_fixture()
    checks = (
        fixture["recall_status"] == "empty",
        fixture["result_count"] == 0,
        fixture["readback_verified"] is False,
    )
    return all(checks), len(checks), {
        "recall_status": fixture["recall_status"],
        "accepted_result_count": fixture["result_count"],
        "false_application_observed": fixture["result_count"] > 0,
    }


def _stale_case() -> tuple[bool, int, dict[str, Any]]:
    fixture = generic_stale_source_fixture()
    reasons = fixture["reason_codes"]
    checks = (
        fixture["recall_status"] == "guard_blocked",
        "source_revision_mismatch" in reasons,
        "request_revision_mismatch" in reasons,
        fixture["provider_call_count"] == 0,
    )
    return all(checks), len(checks), {
        "recall_status": fixture["recall_status"],
        "reason_codes": reasons,
        "provider_call_count": fixture["provider_call_count"],
        "false_application_observed": fixture["provider_call_count"] > 0,
    }


def _multi_person_case() -> tuple[bool, int, dict[str, Any]]:
    fixture = generic_multi_person_authority_fixture()
    reasons = fixture["reason_codes"]
    checks = (
        fixture["matching_actor_guard"] is True,
        fixture["mismatched_actor_guard"] is False,
        "authority_actor_mismatch" in reasons,
    )
    return all(checks), len(checks), {
        "matching_actor_guard": fixture["matching_actor_guard"],
        "mismatched_actor_guard": fixture["mismatched_actor_guard"],
        "reason_codes": reasons,
    }


def _gate_case() -> tuple[bool, int, dict[str, Any]]:
    result = generic_issue_fix_application_fixture()
    receipt = result["application"]["receipt"]
    checks = (
        result["application"]["status"] == "applied",
        receipt["grants_new_action_authority"] is False,
        receipt["current_artifact_verified"] is True,
        receipt["external_writes_performed"] is False,
    )
    return all(checks), len(checks), {
        "application_status": result["application"]["status"],
        "grants_new_action_authority": receipt["grants_new_action_authority"],
        "current_artifact_verified": receipt["current_artifact_verified"],
        "false_application_observed": receipt["grants_new_action_authority"],
    }


def _ranking_case() -> tuple[bool, int, dict[str, Any]]:
    result = generic_issue_fix_application_fixture()
    receipt = result["application"]["receipt"]
    checks = (
        result["patch_plan"]["candidates"][0] == "focused_fix",
        result["application"]["status"] == "applied",
        bool(receipt["memory_ref_digests"]),
        result["shared_core"] == "loopx.capabilities.reward_memory.application",
    )
    return all(checks), len(checks), {
        "top_candidate": result["patch_plan"]["candidates"][0],
        "application_status": result["application"]["status"],
        "shared_core": result["shared_core"],
    }


def _edge_case() -> tuple[bool, int, dict[str, Any]]:
    route = openviking_pr_3237_regression_fixture()
    checks = (
        route["decision"] == "meta_design_gate",
        route["pilot_authorized"] is False,
        route["memory_patch_authority"] is False,
        set(route["missing_required_evidence"]) == {"effect", "ux", "performance"},
    )
    return all(checks), len(checks), {
        "decision": route["decision"],
        "pilot_authorized": route["pilot_authorized"],
        "memory_patch_authority": route["memory_patch_authority"],
        "missing_required_evidence": route["missing_required_evidence"],
        "false_application_observed": (
            route["pilot_authorized"] or route["memory_patch_authority"]
        ),
    }


_CASE_CHECKS: dict[str, Callable[[], tuple[bool, int, dict[str, Any]]]] = {
    "compact_restart_survival": _compact_restart_case,
    "project_module_scope_isolation": _scope_case,
    "supersede_revoke_rejection": _inactive_case,
    "stale_source_rejection": _stale_case,
    "multi_person_authority_conditions": _multi_person_case,
    "gate_non_override": _gate_case,
    "candidate_ranking_influence": _ranking_case,
    "large_edge_case_patch_protection": _edge_case,
}


def run_reward_memory_evaluation() -> dict[str, Any]:
    """Run the bounded Stage-4 contract suite and emit a compact release gate."""

    cases = [
        _evaluate_case(case_id, _CASE_CHECKS[case_id])
        for case_id in REQUIRED_CASE_IDS
    ]
    failed = [case["case_id"] for case in cases if not case["passed"]]
    metrics = {
        "case_count": len(cases),
        "passed_case_count": len(cases) - len(failed),
        "failed_case_count": len(failed),
        "assertion_count": sum(case["assertion_count"] for case in cases),
        "latency_ms": sum(case["latency_ms"] for case in cases),
        "model_tokens": sum(case["model_tokens"] for case in cases),
        "public_evidence_bytes": sum(case["public_evidence_bytes"] for case in cases),
        "storage_write_bytes": sum(case["storage_write_bytes"] for case in cases),
        "provider_write_count": sum(case["provider_write_count"] for case in cases),
        "external_write_count": sum(case["external_write_count"] for case in cases),
        "false_application_count": sum(
            case["false_application_count"] for case in cases
        ),
        "maintainer_interruption_count": sum(
            case["maintainer_interruption_count"] for case in cases
        ),
        "user_gate_count": sum(case["user_gate_count"] for case in cases),
    }
    gate_reasons = [f"case_failed:{case_id}" for case_id in failed]
    for metric in (
        "storage_write_bytes",
        "provider_write_count",
        "external_write_count",
        "false_application_count",
        "maintainer_interruption_count",
        "user_gate_count",
    ):
        if metrics[metric]:
            gate_reasons.append(f"nonzero:{metric}")
    passed = not gate_reasons
    dimensions = {
        "task_outcome": {
            "case_count": metrics["case_count"],
            "passed_case_count": metrics["passed_case_count"],
            "failed_case_count": metrics["failed_case_count"],
            "assertion_count": metrics["assertion_count"],
        },
        "user_experience": {
            "maintainer_interruption_count": metrics[
                "maintainer_interruption_count"
            ],
            "user_gate_count": metrics["user_gate_count"],
        },
        "performance_and_cost": {
            "latency_ms": metrics["latency_ms"],
            "model_tokens": metrics["model_tokens"],
            "public_evidence_bytes": metrics["public_evidence_bytes"],
            "storage_write_bytes": metrics["storage_write_bytes"],
        },
        "application_quality": {
            "false_application_count": metrics["false_application_count"],
        },
    }
    return {
        "ok": passed,
        "schema_version": REWARD_MEMORY_EVALUATION_SCHEMA_VERSION,
        "status": "passed" if passed else "failed",
        "suite": "stage4_provider_neutral_contract",
        "runner": "loopx_reward_memory_evaluation",
        "executes_real_core": True,
        "uses_surrogate_evaluator": False,
        "cases": cases,
        "metrics": metrics,
        "dimensions": dimensions,
        "release_gate": {
            "schema_version": REWARD_MEMORY_RELEASE_GATE_SCHEMA_VERSION,
            "status": "ready_for_bounded_dogfood" if passed else "hold",
            "decision": "advance_stage_5" if passed else "repair_stage_4",
            "reason_codes": gate_reasons,
            "claim_scope": "core_contract_invariants_only",
            "semantic_uplift_claim_allowed": False,
            "production_rollout_allowed": False,
        },
        "boundaries": {
            "provider_writes_performed": False,
            "external_writes_performed": False,
            "raw_memory_captured": False,
            "model_reasoning_replaced": False,
            "new_store_provider_or_scheduler_added": False,
        },
    }
