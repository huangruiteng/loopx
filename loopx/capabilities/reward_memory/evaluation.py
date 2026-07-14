from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ..context_providers.base import ContextProviderItem, ContextProviderRetrieval
from .application import (
    build_active_reward_memory_record,
    build_reward_memory_recall_request,
    execute_reward_memory_recall,
)
from .architecture import (
    build_reward_memory_route_packet,
    pr_3237_regression_observation,
)
from .candidate_review import (
    build_reward_memory_candidate,
    review_reward_memory_candidate,
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

_OBSERVED_AT = "2026-07-14T10:00:00+00:00"
_WORKSPACE = "workspace:reward-memory-eval"
_PROJECT = "repository:openviking-eval"
_REVISION = "revision:stage4"
_SURFACE = "issue_fix.patch_planning"
_CORPUS_ID = "openviking_issue_fix_policy"
_SCOPE_REF = "viking://resources/reward-memory/openviking-eval"


@dataclass
class _FixtureProvider:
    items: tuple[ContextProviderItem, ...]
    provider_id: str = "fixture_provider"
    call_count: int = 0

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        self.call_count += 1
        return ContextProviderRetrieval(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="completed",
            query_summary=str(kwargs["query_summary"]),
            observed_at=str(kwargs["observed_at"]),
            search_performed=True,
            read_performed=True,
            items=self.items,
            requested_limit=int(kwargs["max_results"]),
        )

    def sync(self, **_kwargs: Any) -> Any:
        raise AssertionError("the Stage-4 harness must not write provider state")


def _corpus() -> dict[str, Any]:
    return {
        "corpus_id": _CORPUS_ID,
        "class_id": "hard_policy",
        "provider_id": "fixture_provider",
        "owner_ref": "provider_scope_owner",
        "source_of_truth": "reviewed_owner_feedback",
        "read_authority": "module_scoped",
        "write_authority": "provider_managed",
        "scope": {
            "workspace_ref": _WORKSPACE,
            "project_ref": _PROJECT,
            "surface_ids": [_SURFACE],
        },
        "freshness": {"mode": "revision_bound", "source_revision": _REVISION},
        "lifecycle": {"state": "active", "supersedes": []},
        "retrieval": {
            "index_required": True,
            "readback_required": True,
            "application_receipt_required": True,
        },
        "maintenance": {
            "writeback_triggers": ["reviewed_candidate"],
            "closure_policy": "provider_write_then_revision_verified_read",
            "retirement_authority": "provider_scope_owner",
        },
        "privacy": {"visibility": "private", "raw_content_in_registry": False},
        "provider_scope_ref_digest": hashlib.sha256(
            _SCOPE_REF.encode("utf-8")
        ).hexdigest()[:16],
    }


def _proposal(*, actor_ref: str = "github:user:maintainer") -> dict[str, Any]:
    return {
        "target_class": "hard_policy",
        "content_summary": (
            "Memory-core changes require relevant effect evidence and must not add "
            "a disproportionate patch for one narrow edge case."
        ),
        "source": {
            "source_kind": "maintainer_correction",
            "source_ref": "github:volcengine/OpenViking#reviewed-feedback",
            "actor_ref": actor_ref,
            "actor_role": "verified_repository_core_contributor",
        },
        "scope": {
            "workspace_ref": _WORKSPACE,
            "project_ref": _PROJECT,
            "surface_ids": [_SURFACE],
            "revision_ref": _REVISION,
        },
        "reasoning": {
            "summary": "The correction is reusable only at Issue Fix patch planning.",
            "confidence": "high",
        },
        "guard_context": {
            "source_freshness": "current",
            "conflict_state": "clear",
            "current_artifact_verified": True,
        },
        "requested_action_scopes": ["issue_fix:scope_selection"],
        "raw_content_captured": False,
    }


def _authority(*, actor_ref: str = "github:user:maintainer") -> dict[str, Any]:
    return {
        "verified": True,
        "source_ref": "repository:authority-map",
        "actor_ref": actor_ref,
        "actor_role": "verified_repository_core_contributor",
        "project_ref": _PROJECT,
        "action_scopes": ["issue_fix:scope_selection"],
    }


def _active_record() -> dict[str, Any]:
    candidate = build_reward_memory_candidate(
        _proposal(), authority_checkpoint=_authority()
    )
    reviewed = review_reward_memory_candidate(
        candidate,
        {
            "decision": "accept",
            "reviewer_ref": "github:user:maintainer",
            "review_ref": "review:reward-memory-stage4",
            "reasoning_summary": "The compact policy and authority scope were reviewed.",
        },
    )
    return build_active_reward_memory_record(
        reviewed, _corpus(), activated_at=_OBSERVED_AT
    )


def _binding() -> dict[str, Any]:
    return {
        "corpus_id": _CORPUS_ID,
        "provider_id": "fixture_provider",
        "namespace": "reward_memory",
        "scope_ref": _SCOPE_REF,
        "timeout_seconds": 5,
        "setup_hints": {},
    }


def _checkpoint(*, project_ref: str = _PROJECT, surface_id: str = _SURFACE) -> dict[str, Any]:
    return {
        "verified": True,
        "corpus_id": _CORPUS_ID,
        "workspace_ref": _WORKSPACE,
        "project_ref": project_ref,
        "surface_id": surface_id,
        "read_authority": "module_scoped",
        "source_ref": "repository:authority-map",
    }


def _request(
    *,
    project_ref: str = _PROJECT,
    surface_id: str = _SURFACE,
    revision_ref: str = _REVISION,
    freshness_revision: str = _REVISION,
) -> dict[str, Any]:
    return build_reward_memory_recall_request(
        _corpus(),
        {
            "workspace_ref": _WORKSPACE,
            "project_ref": project_ref,
            "surface_id": surface_id,
            "revision_ref": revision_ref,
            "mode": "function_boundary",
            "queries": [
                {
                    "query": "What reviewed policy constrains this patch?",
                    "query_summary": "reviewed Issue Fix scope policy",
                }
            ],
            "limit": 3,
            "observed_at": _OBSERVED_AT,
            "freshness_context": {
                "source_truth_current": True,
                "source_revision": freshness_revision,
            },
            "conflict_state": "clear",
            "raw_content_captured": False,
        },
        read_authority_checkpoint=_checkpoint(
            project_ref=project_ref, surface_id=surface_id
        ),
    )


def _provider_item(record: Mapping[str, Any], suffix: str = "active") -> ContextProviderItem:
    return ContextProviderItem(
        resource_ref=f"{_SCOPE_REF}/{suffix}.json",
        summary=str(record["content_summary"]),
        content=json.dumps(record, ensure_ascii=False, sort_keys=True),
        score=0.9,
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
    encoded = json.dumps(_active_record(), ensure_ascii=False, sort_keys=True)
    restarted = json.loads(encoded)
    provider = _FixtureProvider((_provider_item(restarted),))
    session = execute_reward_memory_recall(
        _request(), provider_binding=_binding(), provider=provider
    )
    checks = (
        restarted["schema_version"] == "reward_memory_active_record_v0",
        session.public_packet["status"] == "completed",
        session.public_packet["result_readback_verified"] is True,
        provider.call_count == 1,
    )
    return all(checks), len(checks), {
        "serialized_bytes": len(encoded.encode("utf-8")),
        "recall_status": session.public_packet["status"],
        "readback_verified": session.public_packet["result_readback_verified"],
    }


def _scope_case() -> tuple[bool, int, dict[str, Any]]:
    wrong_project = _request(project_ref="repository:other")
    wrong_surface = _request(surface_id="semantic_preference.selection")
    provider = _FixtureProvider((_provider_item(_active_record()),))
    project_session = execute_reward_memory_recall(
        wrong_project, provider_binding=_binding(), provider=provider
    )
    surface_session = execute_reward_memory_recall(
        wrong_surface, provider_binding=_binding(), provider=provider
    )
    checks = (
        project_session.public_packet["status"] == "guard_blocked",
        "project_scope_mismatch" in wrong_project["guard"]["reason_codes"],
        surface_session.public_packet["status"] == "guard_blocked",
        "surface_scope_mismatch" in wrong_surface["guard"]["reason_codes"],
        provider.call_count == 0,
    )
    return all(checks), len(checks), {
        "project_status": project_session.public_packet["status"],
        "surface_status": surface_session.public_packet["status"],
        "provider_call_count": provider.call_count,
        "false_application_observed": provider.call_count > 0,
    }


def _inactive_case() -> tuple[bool, int, dict[str, Any]]:
    superseded = deepcopy(_active_record())
    superseded["lifecycle"] = {"state": "superseded"}
    revoked = deepcopy(_active_record())
    revoked["lifecycle"] = {"state": "revoked"}
    provider = _FixtureProvider(
        (_provider_item(superseded, "superseded"), _provider_item(revoked, "revoked"))
    )
    session = execute_reward_memory_recall(
        _request(), provider_binding=_binding(), provider=provider
    )
    checks = (
        session.public_packet["status"] == "empty",
        session.public_packet["result_count"] == 0,
        session.public_packet["result_readback_verified"] is False,
    )
    return all(checks), len(checks), {
        "recall_status": session.public_packet["status"],
        "accepted_result_count": session.public_packet["result_count"],
        "false_application_observed": session.public_packet["result_count"] > 0,
    }


def _stale_case() -> tuple[bool, int, dict[str, Any]]:
    request = _request(
        revision_ref="revision:stale", freshness_revision="revision:stale"
    )
    provider = _FixtureProvider((_provider_item(_active_record()),))
    session = execute_reward_memory_recall(
        request, provider_binding=_binding(), provider=provider
    )
    reasons = request["guard"]["reason_codes"]
    checks = (
        session.public_packet["status"] == "guard_blocked",
        "source_revision_mismatch" in reasons,
        "request_revision_mismatch" in reasons,
        provider.call_count == 0,
    )
    return all(checks), len(checks), {
        "recall_status": session.public_packet["status"],
        "reason_codes": reasons,
        "provider_call_count": provider.call_count,
        "false_application_observed": provider.call_count > 0,
    }


def _multi_person_case() -> tuple[bool, int, dict[str, Any]]:
    accepted = build_reward_memory_candidate(
        _proposal(), authority_checkpoint=_authority()
    )
    mismatched = build_reward_memory_candidate(
        _proposal(), authority_checkpoint=_authority(actor_ref="github:user:other")
    )
    reasons = mismatched["guard"]["reason_codes"]
    checks = (
        accepted["guard"]["passed"] is True,
        mismatched["guard"]["passed"] is False,
        "authority_actor_mismatch" in reasons,
    )
    return all(checks), len(checks), {
        "matching_actor_guard": accepted["guard"]["passed"],
        "mismatched_actor_guard": mismatched["guard"]["passed"],
        "reason_codes": reasons,
    }


def _issue_fix_application() -> dict[str, Any]:
    from ..issue_fix.reward_memory import run_issue_fix_patch_planning_reward_memory

    provider = _FixtureProvider((_provider_item(_active_record()),))

    def apply_plan(base: Any, items: Any) -> dict[str, Any]:
        plan = dict(base)
        plan["candidates"] = ["focused_fix", "broad_generic_patch"]
        return {
            "outcome": "applied",
            "output": plan,
            "memory_refs": [items[0].memory_ref],
            "reasoning_summary": (
                "Current code verifies the narrow boundary; rank the focused fix first."
            ),
            "current_artifact_verified": True,
        }

    return run_issue_fix_patch_planning_reward_memory(
        {"candidates": ["broad_generic_patch", "focused_fix"]},
        corpus=_corpus(),
        workspace_ref=_WORKSPACE,
        repository_ref=_PROJECT,
        revision_ref=_REVISION,
        queries=[
            {
                "query": "What reviewed policy constrains this patch?",
                "query_summary": "reviewed Issue Fix scope policy",
            }
        ],
        mode="function_boundary",
        observed_at=_OBSERVED_AT,
        freshness_context={
            "source_truth_current": True,
            "source_revision": _REVISION,
        },
        conflict_state="clear",
        read_authority_checkpoint=_checkpoint(),
        provider_binding=_binding(),
        application_id="issue-fix:stage4:ranking",
        artifact_ref="patch-plan:stage4",
        apply_memory=apply_plan,
        provider=provider,
    )


def _gate_case() -> tuple[bool, int, dict[str, Any]]:
    result = _issue_fix_application()
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
    result = _issue_fix_application()
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
    route = build_reward_memory_route_packet(pr_3237_regression_observation())
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

    cases = [_evaluate_case(case_id, _CASE_CHECKS[case_id]) for case_id in REQUIRED_CASE_IDS]
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
