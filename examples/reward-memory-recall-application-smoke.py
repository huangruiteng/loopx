#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


from loopx.capabilities.context_providers.base import (  # noqa: E402
    ContextProviderItem,
    ContextProviderRetrieval,
)
from loopx.capabilities.issue_fix.reward_memory import (  # noqa: E402
    run_issue_fix_patch_planning_reward_memory,
)
from loopx.capabilities.reward_memory import (  # noqa: E402
    apply_reward_memory_recall,
    build_active_reward_memory_record,
    build_reward_memory_candidate,
    build_reward_memory_recall_request,
    execute_reward_memory_recall,
    review_reward_memory_candidate,
)
from loopx.capabilities.semantic_preference.reward_memory import (  # noqa: E402
    run_semantic_preference_reward_memory,
)


OBSERVED_AT = "2026-07-14T10:00:00+00:00"
WORKSPACE = "workspace:example"
PROJECT = "repository:example"
REVISION = "revision:abc123"
SCOPE_REF = "viking://resources/reward-memory/example"


class FakeProvider:
    provider_id = "fake_provider"

    def __init__(
        self,
        items: tuple[ContextProviderItem, ...],
        *,
        status: str = "completed",
    ) -> None:
        self.items = items
        self.status = status
        self.calls: list[dict[str, Any]] = []

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        self.calls.append(dict(kwargs))
        return ContextProviderRetrieval(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status=self.status,
            query_summary=str(kwargs["query_summary"]),
            observed_at=str(kwargs["observed_at"]),
            search_performed=self.status == "completed",
            read_performed=self.status == "completed",
            items=self.items if self.status == "completed" else (),
            reason_code=(
                None if self.status == "completed" else "provider_service_unavailable"
            ),
            requested_limit=int(kwargs["max_results"]),
        )

    def sync(self, **_kwargs: Any) -> Any:
        raise AssertionError("Stage-3 recall must not call provider sync")


def corpus(*, corpus_id: str, class_id: str, surface: str) -> dict[str, Any]:
    return {
        "corpus_id": corpus_id,
        "class_id": class_id,
        "provider_id": "fake_provider",
        "owner_ref": "provider_scope_owner",
        "source_of_truth": "reviewed_owner_feedback",
        "read_authority": "module_scoped",
        "write_authority": "provider_managed",
        "scope": {
            "workspace_ref": WORKSPACE,
            "project_ref": PROJECT,
            "surface_ids": [surface],
        },
        "freshness": {
            "mode": "revision_bound",
            "source_revision": REVISION,
        },
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
            SCOPE_REF.encode("utf-8")
        ).hexdigest()[:16],
    }


def reviewed_candidate(
    *,
    target_class: str,
    surface: str,
    content_summary: str,
    requested_action_scopes: list[str] | None = None,
) -> dict[str, Any]:
    proposal = {
        "target_class": target_class,
        "content_summary": content_summary,
        "source": {
            "source_kind": "maintainer_correction",
            "source_ref": "github:example/repository#42:comment:1",
            "actor_ref": "github:user:maintainer",
            "actor_role": "verified_repository_core_contributor",
        },
        "scope": {
            "workspace_ref": WORKSPACE,
            "project_ref": PROJECT,
            "surface_ids": [surface],
            "revision_ref": REVISION,
        },
        "reasoning": {
            "summary": "The reviewed feedback is reusable only inside this surface.",
            "confidence": "high",
        },
        "guard_context": {
            "source_freshness": "current",
            "conflict_state": "clear",
            "current_artifact_verified": True,
        },
        "requested_action_scopes": requested_action_scopes or [],
        "raw_content_captured": False,
    }
    checkpoint = None
    if target_class == "hard_policy":
        checkpoint = {
            "verified": True,
            "source_ref": "repository:authority-map",
            "actor_ref": "github:user:maintainer",
            "actor_role": "verified_repository_core_contributor",
            "project_ref": PROJECT,
            "action_scopes": requested_action_scopes or [],
        }
    candidate = build_reward_memory_candidate(
        proposal,
        authority_checkpoint=checkpoint,
    )
    return review_reward_memory_candidate(
        candidate,
        {
            "decision": "accept",
            "reviewer_ref": "github:user:maintainer",
            "review_ref": f"review:{target_class}:{surface}",
            "reasoning_summary": "The compact candidate and authority were reviewed.",
        },
    )


def item(active_record: Mapping[str, Any], ref: str) -> ContextProviderItem:
    return ContextProviderItem(
        resource_ref=ref,
        summary=str(active_record["content_summary"]),
        content=json.dumps(active_record, ensure_ascii=False),
        score=0.9,
    )


def binding(corpus_id: str) -> dict[str, Any]:
    return {
        "corpus_id": corpus_id,
        "provider_id": "fake_provider",
        "namespace": "reward_memory",
        "scope_ref": SCOPE_REF,
        "timeout_seconds": 5,
        "setup_hints": {
            "install": "Install the configured provider CLI.",
            "configure": "Configure it through the existing private channel.",
        },
    }


def checkpoint(corpus_id: str, surface: str) -> dict[str, Any]:
    return {
        "verified": True,
        "corpus_id": corpus_id,
        "workspace_ref": WORKSPACE,
        "project_ref": PROJECT,
        "surface_id": surface,
        "read_authority": "module_scoped",
        "source_ref": "repository:authority-map",
    }


def main() -> None:
    issue_surface = "issue_fix.patch_planning"
    issue_corpus = corpus(
        corpus_id="openviking_patch_policy",
        class_id="hard_policy",
        surface=issue_surface,
    )
    issue_review = reviewed_candidate(
        target_class="hard_policy",
        surface=issue_surface,
        content_summary=(
            "Require relevant evidence for memory-core changes and avoid "
            "disproportionate code for one narrow edge case."
        ),
        requested_action_scopes=["issue_fix:scope_selection"],
    )
    active_issue = build_active_reward_memory_record(
        issue_review,
        issue_corpus,
        activated_at=OBSERVED_AT,
    )
    assert active_issue["provider_write_performed"] is False
    issue_provider = FakeProvider(
        (item(active_issue, "viking://resources/reward-memory/example/policy.json"),)
    )

    def apply_plan(base: Any, items: Any) -> dict[str, Any]:
        plan = dict(base)
        plan["evidence_policy"] = "relevance_gated"
        plan["edge_case_scope"] = "bounded_or_escalate"
        return {
            "outcome": "applied",
            "output": plan,
            "memory_refs": [items[0].memory_ref],
            "reasoning_summary": (
                "Current code confirms a memory-core change, so effect evidence "
                "is required while benchmark evidence remains claim-gated."
            ),
            "current_artifact_verified": True,
        }

    issue_result = run_issue_fix_patch_planning_reward_memory(
        {"change_scope": "memory_retrieval"},
        corpus=issue_corpus,
        workspace_ref=WORKSPACE,
        repository_ref=PROJECT,
        revision_ref=REVISION,
        queries=[
            {
                "query": "What reviewed policy constrains this memory-core patch?",
                "query_summary": "reviewed memory-core patch policy",
            }
        ],
        mode="function_boundary",
        observed_at=OBSERVED_AT,
        freshness_context={
            "source_truth_current": True,
            "source_revision": REVISION,
        },
        conflict_state="clear",
        read_authority_checkpoint=checkpoint("openviking_patch_policy", issue_surface),
        provider_binding=binding("openviking_patch_policy"),
        application_id="issue-fix:example:patch-plan",
        artifact_ref="patch-plan:example",
        apply_memory=apply_plan,
        provider=issue_provider,
    )
    assert issue_result["patch_plan"]["evidence_policy"] == "relevance_gated"
    assert issue_result["recall"]["provider_call_count"] == 1
    assert issue_result["recall"]["result_readback_verified"] is True
    assert issue_result["recall"]["results"][0]["content_exposed"] is False
    assert issue_result["recall"]["results"][0]["content_summary"] is None
    assert issue_result["application"]["status"] == "applied"
    receipt = issue_result["application"]["receipt"]
    assert receipt["current_artifact_verified"] is True
    assert receipt["result_readback_verified"] is True
    assert len(receipt["memory_ref_digests"]) == 1
    assert issue_result["automatic_recall"] is False

    review_surface = "pr_review.reply"
    preference_corpus = corpus(
        corpus_id="review_reply_preferences",
        class_id="soft_preference",
        surface=review_surface,
    )
    preference_review = reviewed_candidate(
        target_class="soft_preference",
        surface=review_surface,
        content_summary="Keep review replies concise and evidence linked.",
    )
    active_preference = build_active_reward_memory_record(
        preference_review,
        preference_corpus,
        activated_at=OBSERVED_AT,
    )
    preference_provider = FakeProvider(
        (
            item(
                active_preference,
                "viking://resources/reward-memory/example/preference.json",
            ),
        )
    )
    semantic_result = run_semantic_preference_reward_memory(
        "The current reply already includes evidence.",
        corpus=preference_corpus,
        request={
            "workspace_ref": WORKSPACE,
            "project_ref": PROJECT,
            "surface_id": review_surface,
            "revision_ref": REVISION,
            "mode": "bounded_agentic_search",
            "queries": [
                {"query": "reply tone", "query_summary": "review reply tone"},
                {"query": "evidence links", "query_summary": "review evidence style"},
            ],
            "limit": 5,
            "observed_at": OBSERVED_AT,
            "freshness_context": {
                "source_truth_current": True,
                "source_revision": REVISION,
            },
            "conflict_state": "clear",
            "raw_content_captured": False,
        },
        read_authority_checkpoint=checkpoint(
            "review_reply_preferences", review_surface
        ),
        provider_binding=binding("review_reply_preferences"),
        application_id="pr-review:example:reply",
        apply_memory=lambda base, items: {
            "outcome": "ignored",
            "output": base,
            "memory_refs": [items[0].memory_ref],
            "reasoning_summary": "The current reply already satisfies the preference.",
            "current_artifact_verified": True,
        },
        provider=preference_provider,
    )
    assert semantic_result["application"]["status"] == "ignored"
    assert semantic_result["output"].startswith("The current reply")
    assert len(preference_provider.calls) == 2

    blocked_request = build_reward_memory_recall_request(
        issue_corpus,
        {
            "workspace_ref": WORKSPACE,
            "project_ref": "repository:other",
            "surface_id": issue_surface,
            "revision_ref": REVISION,
            "mode": "function_boundary",
            "queries": [{"query": "policy", "query_summary": "policy"}],
            "limit": 1,
            "observed_at": OBSERVED_AT,
            "freshness_context": {
                "source_truth_current": True,
                "source_revision": REVISION,
            },
            "conflict_state": "clear",
            "raw_content_captured": False,
        },
        read_authority_checkpoint=checkpoint("openviking_patch_policy", issue_surface),
    )
    blocked_provider = FakeProvider(())
    blocked_session = execute_reward_memory_recall(
        blocked_request,
        provider_binding=binding("openviking_patch_policy"),
        provider=blocked_provider,
    )
    assert blocked_session.public_packet["status"] == "guard_blocked"
    assert blocked_session.public_packet["provider_call_count"] == 0
    assert blocked_provider.calls == []

    unavailable_provider = FakeProvider((), status="unavailable")
    unavailable_result = run_issue_fix_patch_planning_reward_memory(
        {"change_scope": "memory_retrieval"},
        corpus=issue_corpus,
        workspace_ref=WORKSPACE,
        repository_ref=PROJECT,
        revision_ref=REVISION,
        queries=[{"query": "policy", "query_summary": "policy"}],
        mode="function_boundary",
        observed_at=OBSERVED_AT,
        freshness_context={
            "source_truth_current": True,
            "source_revision": REVISION,
        },
        conflict_state="clear",
        read_authority_checkpoint=checkpoint("openviking_patch_policy", issue_surface),
        provider_binding=binding("openviking_patch_policy"),
        application_id="issue-fix:example:unavailable",
        apply_memory=apply_plan,
        provider=unavailable_provider,
    )
    assert unavailable_result["patch_plan"] == {"change_scope": "memory_retrieval"}
    assert unavailable_result["recall"]["status"] == "provider_unavailable"
    assert unavailable_result["recall"]["provider_failure_is_user_gate"] is False
    assert unavailable_result["recall"]["setup_hints"]["configure"]
    assert unavailable_result["application"]["fail_open_preserved_base"] is True

    failed_application = apply_reward_memory_recall(
        {"change_scope": "memory_retrieval"},
        execute_reward_memory_recall(
            build_reward_memory_recall_request(
                issue_corpus,
                {
                    "workspace_ref": WORKSPACE,
                    "project_ref": PROJECT,
                    "surface_id": issue_surface,
                    "revision_ref": REVISION,
                    "mode": "function_boundary",
                    "queries": [{"query": "policy", "query_summary": "policy"}],
                    "limit": 1,
                    "observed_at": OBSERVED_AT,
                    "freshness_context": {
                        "source_truth_current": True,
                        "source_revision": REVISION,
                    },
                    "conflict_state": "clear",
                    "raw_content_captured": False,
                },
                read_authority_checkpoint=checkpoint(
                    "openviking_patch_policy", issue_surface
                ),
            ),
            provider_binding=binding("openviking_patch_policy"),
            provider=issue_provider,
        ),
        application_id="issue-fix:example:failed-application",
        apply_memory=lambda _base, _items: (_ for _ in ()).throw(RuntimeError()),
    )
    assert failed_application["status"] == "failed"
    assert failed_application["output"] == {"change_scope": "memory_retrieval"}
    assert failed_application["receipt"]["outcome"] == "failed"

    try:
        build_active_reward_memory_record(
            issue_review | {"effective_decision": "no_write"},
            issue_corpus,
            activated_at=OBSERVED_AT,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("no-write review must not become active memory")

    print("reward-memory-recall-application-smoke: ok")


if __name__ == "__main__":
    main()
