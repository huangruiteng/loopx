from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from loopx.capabilities.context_providers.base import (
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
    canonical_context_matches,
)
from loopx.capabilities.issue_fix.reward_memory import (
    ingest_issue_fix_reward_memory_event,
)
from loopx.capabilities.reward_memory.runtime_hooks import (
    run_reward_memory_automatic_ingest_hook,
)


OBSERVED_AT = "2026-07-16T00:30:00+00:00"
WORKSPACE = "workspace:example"
PROJECT = "repository:example"
REVISION = "revision:abc123"
SURFACE = "issue_fix.patch_planning"
SCOPE_REF = "viking://resources/reward-memory/example"


class FakeProvider:
    provider_id = "fake_provider"

    def __init__(
        self,
        *,
        alter_readback: bool = False,
        materialize_descendant: bool = False,
    ) -> None:
        self.alter_readback = alter_readback
        self.materialize_descendant = materialize_descendant
        self.resources: dict[str, str] = {}
        self.sync_calls = 0
        self.retrieve_calls = 0

    def sync(self, **kwargs: Any) -> ContextProviderSync:
        self.sync_calls += 1
        source, target = kwargs["resources"][0]
        content = Path(source).read_text(encoding="utf-8")
        write_count = 0
        if target in self.resources:
            assert canonical_context_matches(self.resources[target], content)
        else:
            self.resources[target] = content
            write_count = 1
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="completed",
            observed_at=str(kwargs["observed_at"]),
            requested_count=1,
            completed_count=1,
            write_count=write_count,
            result_refs=(target,),
        )

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        self.retrieve_calls += 1
        items: list[ContextProviderItem] = []
        for target, stored in self.resources.items():
            content = stored
            if self.alter_readback:
                envelope = json.loads(stored)
                envelope["review"]["reasoning_summary"] = (
                    "Unexpected provider mutation."
                )
                content = json.dumps(
                    envelope,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            items.append(
                ContextProviderItem(
                    resource_ref=(
                        f"{target}/materialized.md"
                        if self.materialize_descendant
                        else target
                    ),
                    summary="Compact reviewed reward memory.",
                    content=content,
                    score=0.95,
                )
            )
        return ContextProviderRetrieval(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="completed",
            query_summary=str(kwargs["query_summary"]),
            observed_at=str(kwargs["observed_at"]),
            search_performed=True,
            read_performed=True,
            items=tuple(items),
            requested_limit=int(kwargs["max_results"]),
        )


def corpus() -> dict[str, Any]:
    return {
        "corpus_id": "openviking_patch_policy",
        "class_id": "hard_policy",
        "provider_id": "fake_provider",
        "owner_ref": "openviking_reward_memory_owner",
        "source_of_truth": "reviewed_maintainer_feedback",
        "read_authority": "module_scoped",
        "write_authority": "provider_managed",
        "scope": {
            "workspace_ref": WORKSPACE,
            "project_ref": PROJECT,
            "surface_ids": [SURFACE],
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
            "writeback_triggers": ["reviewed_maintainer_feedback"],
            "closure_policy": "write_exact_readback_then_recall",
            "retirement_authority": "openviking_reward_memory_owner",
        },
        "privacy": {"visibility": "private", "raw_content_in_registry": False},
        "provider_scope_ref_digest": hashlib.sha256(
            SCOPE_REF.encode("utf-8")
        ).hexdigest()[:16],
    }


def policy(*, project_ref: str = PROJECT) -> dict[str, Any]:
    return {
        "schema_version": "reward_memory_standing_policy_v0",
        "policy_id": "policy:openviking:issue-fix-maintainer-feedback",
        "enabled": True,
        "auto_activate": True,
        "owner_ref": "openviking_reward_memory_owner",
        "reviewer_ref": "agent:codex-openviking-meta",
        "authority_source_ref": "policy:openviking:issue-fix",
        "scope": {
            "workspace_ref": WORKSPACE,
            "project_ref": project_ref,
            "surface_ids": [SURFACE],
        },
        "allowed_target_classes": ["hard_policy"],
        "allowed_source_kinds": ["maintainer_correction"],
        "allowed_actor_roles": ["verified_repository_core_contributor"],
        "allowed_action_scopes": ["issue_fix:scope_selection"],
        "raw_content_captured": False,
    }


def event() -> dict[str, Any]:
    return {
        "schema_version": "issue_fix_reward_memory_event_v0",
        "issue_ref": "github:example/repository#42",
        "workspace_ref": WORKSPACE,
        "repository_ref": PROJECT,
        "surface_id": SURFACE,
        "revision_ref": REVISION,
        "target_class": "hard_policy",
        "content_summary": (
            "Keep memory-core changes focused and validate material effects before PR."
        ),
        "source": {
            "source_kind": "maintainer_correction",
            "source_ref": "github:example/repository#42:comment:1",
            "actor_ref": "github:user:maintainer",
            "actor_role": "verified_repository_core_contributor",
        },
        "reasoning": {
            "summary": "The verified correction is reusable at patch planning.",
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


def binding() -> dict[str, Any]:
    return {
        "corpus_id": "openviking_patch_policy",
        "provider_id": "fake_provider",
        "namespace": "reward_memory",
        "scope_ref": SCOPE_REF,
        "timeout_seconds": 5,
    }


def ingest(provider: FakeProvider, *, execute: bool = True) -> dict[str, Any]:
    return ingest_issue_fix_reward_memory_event(
        event(),
        corpus=corpus(),
        standing_policy=policy(),
        provider_binding=binding(),
        observed_at=OBSERVED_AT,
        execute=execute,
        provider=provider,
    )


def runtime_config(*, automatic_ingest: bool) -> dict[str, Any]:
    return {
        "automation": {
            "automatic_recall": False,
            "automatic_ingest": automatic_ingest,
            "fail_open": True,
        },
        "corpora": {
            corpus()["corpus_id"]: {
                "corpus": corpus(),
                "standing_policy": policy(),
                "provider_binding": binding(),
            }
        },
        "surfaces": {
            SURFACE: {
                "surface_id": SURFACE,
                "adapter": "issue_fix_maintainer_feedback",
                "corpus_ids": [corpus()["corpus_id"]],
                "ingest_corpus_id": corpus()["corpus_id"],
                "recall_profile": {
                    "profile_id": "issue_fix_patch_planning_v1",
                    "mode": "function_boundary",
                    "max_queries": 1,
                    "limit": 5,
                },
            }
        },
    }


def automatic_ingest(
    provider: FakeProvider,
    *,
    automatic: bool = True,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return run_reward_memory_automatic_ingest_hook(
        runtime_config(automatic_ingest=automatic),
        surface_id=SURFACE,
        adapter="issue_fix_maintainer_feedback",
        event=payload or event(),
        observed_at=OBSERVED_AT,
        ingest_event=ingest_issue_fix_reward_memory_event,
        execute=True,
        provider=provider,
    )


def test_atomic_ingest_writes_reads_back_and_deduplicates() -> None:
    provider = FakeProvider()

    first = ingest(provider)
    second = ingest(provider)

    assert first["status"] == "activated"
    assert first["exact_readback_verified"] is True
    assert first["memory_available_for_recall"] is True
    assert first["external_writes_performed"] is True
    assert first["write"]["write_count"] == 1
    assert second["status"] == "activated"
    assert second["candidate_ref"] == first["candidate_ref"]
    assert second["deduplicated"] is True
    assert second["external_writes_performed"] is False
    assert second["write"]["write_count"] == 0
    assert provider.sync_calls == 2
    assert provider.retrieve_calls == 2


def test_atomic_ingest_accepts_exact_descendant_materialization() -> None:
    receipt = ingest(FakeProvider(materialize_descendant=True))

    assert receipt["status"] == "activated"
    assert receipt["exact_readback_verified"] is True
    assert receipt["memory_available_for_recall"] is True


def test_dry_run_needs_no_provider_call() -> None:
    provider = FakeProvider()

    receipt = ingest(provider, execute=False)

    assert receipt["status"] == "planned"
    assert receipt["write"]["status"] == "planned"
    assert receipt["memory_available_for_recall"] is False
    assert provider.sync_calls == 0
    assert provider.retrieve_calls == 0


def test_policy_scope_mismatch_fails_open_before_provider() -> None:
    provider = FakeProvider()

    receipt = ingest_issue_fix_reward_memory_event(
        event(),
        corpus=corpus(),
        standing_policy=policy(project_ref="repository:different"),
        provider_binding=binding(),
        observed_at=OBSERVED_AT,
        execute=True,
        provider=provider,
    )

    assert receipt["status"] == "guard_blocked"
    assert "candidate_project_policy_mismatch" in receipt["guard"]["reason_codes"]
    assert receipt["provider_failure_is_user_gate"] is False
    assert provider.sync_calls == 0


def test_mutated_provider_content_does_not_become_recallable() -> None:
    receipt = ingest(FakeProvider(alter_readback=True))

    assert receipt["status"] == "readback_unverified"
    assert receipt["exact_readback_verified"] is False
    assert receipt["memory_available_for_recall"] is False
    assert receipt["external_writes_performed"] is True


def test_raw_or_unmodelled_comment_fields_are_rejected() -> None:
    raw_event = event() | {"comment_body": "raw maintainer comment"}

    with pytest.raises(ValueError, match="unsupported fields: comment_body"):
        ingest_issue_fix_reward_memory_event(
            raw_event,
            corpus=corpus(),
            standing_policy=policy(),
            provider_binding=binding(),
            observed_at=OBSERVED_AT,
        )


def test_automatic_ingest_is_opt_in_and_reuses_atomic_deduplication() -> None:
    disabled_provider = FakeProvider()
    disabled = automatic_ingest(disabled_provider, automatic=False)
    provider = FakeProvider()

    first = automatic_ingest(provider)
    second = automatic_ingest(provider)

    assert disabled["status"] == "disabled"
    assert disabled_provider.sync_calls == 0
    assert first["status"] == "activated"
    assert first["telemetry"]["exact_readback_verified"] is True
    assert second["status"] == "activated"
    assert second["telemetry"]["deduplicated"] is True
    assert provider.sync_calls == 2
    assert provider.retrieve_calls == 2


def test_automatic_ingest_scope_mismatch_stops_before_provider() -> None:
    provider = FakeProvider()
    mismatched = event() | {"repository_ref": "repository:different"}

    result = automatic_ingest(provider, payload=mismatched)

    assert result["status"] == "guard_blocked"
    assert (
        "candidate_project_policy_mismatch"
        in result["receipt"]["guard"]["reason_codes"]
    )
    assert result["telemetry"]["provider_sync_count"] == 0
    assert provider.sync_calls == 0
