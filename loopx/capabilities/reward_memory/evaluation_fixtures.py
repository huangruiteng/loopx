from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
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


_OBSERVED_AT = "2026-07-14T10:00:00+00:00"
_WORKSPACE = "workspace:reward-memory-eval"
_PROJECT = "repository:fixture-project"
_REVISION = "revision:stage4"
_SURFACE = "issue_fix.patch_planning"
_CORPUS_ID = "reward_memory_policy_scopes"
_SCOPE_REF = "memory://resources/reward-memory/fixture-project"


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
        raise AssertionError("the Stage-4 fixture must not write provider state")


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
            "source_ref": "github:example/reward-memory#reviewed-feedback",
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
            "reasoning_summary": (
                "The compact policy and authority scope were reviewed."
            ),
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


def _checkpoint(
    *, project_ref: str = _PROJECT, surface_id: str = _SURFACE
) -> dict[str, Any]:
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


def _provider_item(
    record: Mapping[str, Any], suffix: str = "active"
) -> ContextProviderItem:
    return ContextProviderItem(
        resource_ref=f"{_SCOPE_REF}/{suffix}.json",
        summary=str(record["content_summary"]),
        content=json.dumps(record, ensure_ascii=False, sort_keys=True),
        score=0.9,
    )


def generic_compact_restart_fixture() -> dict[str, Any]:
    encoded = json.dumps(_active_record(), ensure_ascii=False, sort_keys=True)
    restarted = json.loads(encoded)
    provider = _FixtureProvider((_provider_item(restarted),))
    session = execute_reward_memory_recall(
        _request(), provider_binding=_binding(), provider=provider
    )
    return {
        "fixture_identity": {
            "project_ref": _PROJECT,
            "corpus_id": _CORPUS_ID,
            "scope_ref": _SCOPE_REF,
        },
        "serialized_bytes": len(encoded.encode("utf-8")),
        "record_schema_version": restarted["schema_version"],
        "recall_status": session.public_packet["status"],
        "readback_verified": session.public_packet["result_readback_verified"],
        "provider_call_count": provider.call_count,
    }


def generic_scope_isolation_fixture() -> dict[str, Any]:
    wrong_project = _request(project_ref="repository:other")
    wrong_surface = _request(surface_id="semantic_preference.selection")
    provider = _FixtureProvider((_provider_item(_active_record()),))
    project_session = execute_reward_memory_recall(
        wrong_project, provider_binding=_binding(), provider=provider
    )
    surface_session = execute_reward_memory_recall(
        wrong_surface, provider_binding=_binding(), provider=provider
    )
    return {
        "project_status": project_session.public_packet["status"],
        "project_reason_codes": wrong_project["guard"]["reason_codes"],
        "surface_status": surface_session.public_packet["status"],
        "surface_reason_codes": wrong_surface["guard"]["reason_codes"],
        "provider_call_count": provider.call_count,
    }


def generic_inactive_lifecycle_fixture() -> dict[str, Any]:
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
    return {
        "recall_status": session.public_packet["status"],
        "result_count": session.public_packet["result_count"],
        "readback_verified": session.public_packet["result_readback_verified"],
    }


def generic_stale_source_fixture() -> dict[str, Any]:
    request = _request(
        revision_ref="revision:stale", freshness_revision="revision:stale"
    )
    provider = _FixtureProvider((_provider_item(_active_record()),))
    session = execute_reward_memory_recall(
        request, provider_binding=_binding(), provider=provider
    )
    return {
        "recall_status": session.public_packet["status"],
        "reason_codes": request["guard"]["reason_codes"],
        "provider_call_count": provider.call_count,
    }


def generic_multi_person_authority_fixture() -> dict[str, Any]:
    accepted = build_reward_memory_candidate(
        _proposal(), authority_checkpoint=_authority()
    )
    mismatched = build_reward_memory_candidate(
        _proposal(), authority_checkpoint=_authority(actor_ref="github:user:other")
    )
    return {
        "matching_actor_guard": accepted["guard"]["passed"],
        "mismatched_actor_guard": mismatched["guard"]["passed"],
        "reason_codes": mismatched["guard"]["reason_codes"],
    }


def generic_issue_fix_application_fixture() -> dict[str, Any]:
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


def openviking_pr_3237_regression_fixture() -> dict[str, Any]:
    return build_reward_memory_route_packet(pr_3237_regression_observation())
