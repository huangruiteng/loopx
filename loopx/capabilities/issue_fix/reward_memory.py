from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from ..context_providers.base import ContextProvider
from ..reward_memory.application import RewardMemoryApplier
from ..reward_memory.candidate_review import build_issue_fix_reward_memory_candidate
from ..reward_memory.ingestion import (
    ingest_reward_memory_candidate,
    normalize_reward_memory_standing_policy,
)
from ..semantic_preference.reward_memory import run_semantic_preference_reward_memory


ISSUE_FIX_PATCH_PLANNING_SURFACE = "issue_fix.patch_planning"
ISSUE_FIX_REVIEWER_ARTIFACT_SURFACE = "reviewer_artifact.summary"
ISSUE_FIX_REWARD_MEMORY_APPLICATION_SCHEMA_VERSION = (
    "issue_fix_reward_memory_application_v0"
)
ISSUE_FIX_REVIEWER_ARTIFACT_SCHEMA_VERSION = "issue_fix_reviewer_artifact_v0"
ISSUE_FIX_REVIEWER_ARTIFACT_APPLICATION_SCHEMA_VERSION = (
    "issue_fix_reviewer_artifact_reward_memory_application_v0"
)
ISSUE_FIX_REWARD_MEMORY_EVENT_SCHEMA_VERSION = "issue_fix_reward_memory_event_v0"

_EVENT_FIELDS = {
    "schema_version",
    "issue_ref",
    "workspace_ref",
    "repository_ref",
    "surface_id",
    "revision_ref",
    "target_class",
    "content_summary",
    "source",
    "reasoning",
    "guard_context",
    "requested_action_scopes",
    "raw_content_captured",
}
_SOURCE_FIELDS = {"source_kind", "source_ref", "actor_ref", "actor_role"}
_REASONING_FIELDS = {"summary", "confidence"}
_GUARD_FIELDS = {
    "source_freshness",
    "conflict_state",
    "current_artifact_verified",
}


def _strict_object(
    value: object,
    *,
    label: str,
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(
            f"{label} contains unsupported fields: {', '.join(unexpected)}"
        )
    return value


def ingest_issue_fix_reward_memory_event(
    event: Mapping[str, Any],
    *,
    corpus: Mapping[str, Any],
    standing_policy: Mapping[str, Any],
    provider_binding: Mapping[str, Any],
    observed_at: str,
    execute: bool = False,
    provider: ContextProvider | None = None,
) -> dict[str, Any]:
    """Map one compact Issue Fix feedback event into the shared ingest seam."""

    raw = _strict_object(event, label="issue_fix_event", allowed=_EVENT_FIELDS)
    if raw.get("schema_version") != ISSUE_FIX_REWARD_MEMORY_EVENT_SCHEMA_VERSION:
        raise ValueError("event must use issue_fix_reward_memory_event_v0")
    _strict_object(
        raw.get("source"), label="issue_fix_event.source", allowed=_SOURCE_FIELDS
    )
    _strict_object(
        raw.get("reasoning"),
        label="issue_fix_event.reasoning",
        allowed=_REASONING_FIELDS,
    )
    _strict_object(
        raw.get("guard_context"),
        label="issue_fix_event.guard_context",
        allowed=_GUARD_FIELDS,
    )
    policy = normalize_reward_memory_standing_policy(standing_policy)
    source = raw["source"]
    assert isinstance(source, Mapping)
    authority_checkpoint = None
    if raw.get("target_class") == "hard_policy":
        authority_checkpoint = {
            "verified": policy["enabled"] is True,
            "source_ref": policy["authority_source_ref"],
            "actor_ref": source.get("actor_ref"),
            "actor_role": source.get("actor_role"),
            "project_ref": raw.get("repository_ref"),
            "action_scopes": raw.get("requested_action_scopes") or [],
        }
    adapter = build_issue_fix_reward_memory_candidate(
        raw,
        authority_checkpoint=authority_checkpoint,
    )
    result = ingest_reward_memory_candidate(
        adapter["shared_candidate"],
        corpus=corpus,
        standing_policy=policy,
        provider_binding=provider_binding,
        observed_at=observed_at,
        execute=execute,
        provider=provider,
    )
    summary = public_safe_compact_text(raw.get("content_summary"), limit=500)
    return result | {
        "adapter_schema_version": ISSUE_FIX_REWARD_MEMORY_EVENT_SCHEMA_VERSION,
        "issue_ref": public_safe_compact_text(raw.get("issue_ref"), limit=160),
        "event_summary_digest": hashlib.sha256(summary.encode("utf-8")).hexdigest()[
            :16
        ],
        "next_issue_fix_call": "run_issue_fix_patch_planning_reward_memory",
    }


def run_issue_fix_patch_planning_reward_memory(
    base_plan: Mapping[str, Any],
    *,
    corpus: Mapping[str, Any],
    workspace_ref: str,
    repository_ref: str,
    revision_ref: str,
    queries: list[Mapping[str, Any]],
    mode: str,
    observed_at: str,
    freshness_context: Mapping[str, Any],
    conflict_state: str,
    read_authority_checkpoint: Mapping[str, Any],
    provider_binding: Mapping[str, Any],
    application_id: str,
    artifact_ref: str | None = None,
    apply_memory: RewardMemoryApplier | None = None,
    provider: ContextProvider | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Apply opt-in reward memory at the Issue Fix patch-planning boundary."""

    guarded_apply = apply_memory
    if apply_memory is not None:

        def guarded_apply(base: Any, items: Any) -> Mapping[str, Any]:
            decision = apply_memory(base, items)
            output = decision.get("output") if isinstance(decision, Mapping) else None
            if not isinstance(output, Mapping):
                raise ValueError("Issue Fix reward-memory output must be a patch plan")
            return decision

    shared = run_semantic_preference_reward_memory(
        dict(base_plan),
        corpus=corpus,
        request={
            "workspace_ref": workspace_ref,
            "project_ref": repository_ref,
            "surface_id": ISSUE_FIX_PATCH_PLANNING_SURFACE,
            "revision_ref": revision_ref,
            "mode": mode,
            "queries": queries,
            "limit": limit,
            "observed_at": observed_at,
            "freshness_context": dict(freshness_context),
            "conflict_state": conflict_state,
            "raw_content_captured": False,
        },
        read_authority_checkpoint=read_authority_checkpoint,
        provider_binding=provider_binding,
        application_id=application_id,
        artifact_ref=artifact_ref,
        apply_memory=guarded_apply,
        provider=provider,
    )
    output = shared["output"]
    if not isinstance(output, Mapping):
        raise AssertionError("Issue Fix fail-open invariant returned a non-plan output")
    return {
        "ok": True,
        "schema_version": ISSUE_FIX_REWARD_MEMORY_APPLICATION_SCHEMA_VERSION,
        "surface_id": ISSUE_FIX_PATCH_PLANNING_SURFACE,
        "patch_plan": dict(output),
        "recall": shared["recall"],
        "application": shared["application"],
        "shared_core": shared["shared_core"],
        "adapter_role": "field_mapping_only_model_owns_patch_tradeoffs",
        "automatic_recall": False,
        "provider_failure_is_user_gate": False,
    }


def _reviewer_artifact(value: Mapping[str, Any]) -> dict[str, Any]:
    artifact = {
        "schema_version": ISSUE_FIX_REVIEWER_ARTIFACT_SCHEMA_VERSION,
        "repo": public_safe_compact_text(value.get("repo"), limit=200),
        "pr_ref": public_safe_compact_text(value.get("pr_ref"), limit=40),
        "permalink": public_safe_compact_text(value.get("permalink"), limit=300),
        "source_title": public_safe_compact_text(value.get("source_title"), limit=180),
        "summary": public_safe_compact_text(value.get("summary"), limit=220),
    }
    if not all(artifact[key] for key in ("repo", "pr_ref", "permalink")):
        raise ValueError("reviewer artifact must identify the current PR")
    return artifact


def reviewer_artifact_notification_gate(
    application: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Validate the compact receipt required before reviewer-facing delivery."""

    reasons: list[str] = []
    packet = application if isinstance(application, Mapping) else {}
    artifact_raw = packet.get("reviewer_artifact")
    artifact = artifact_raw if isinstance(artifact_raw, Mapping) else {}
    shared = packet.get("application")
    shared = shared if isinstance(shared, Mapping) else {}
    receipt = shared.get("receipt")
    receipt = receipt if isinstance(receipt, Mapping) else {}
    summary = public_safe_compact_text(artifact.get("summary"), limit=220)
    if packet.get("schema_version") != (
        ISSUE_FIX_REVIEWER_ARTIFACT_APPLICATION_SCHEMA_VERSION
    ):
        reasons.append("application_schema_invalid")
    if packet.get("surface_id") != ISSUE_FIX_REVIEWER_ARTIFACT_SURFACE:
        reasons.append("surface_mismatch")
    if artifact.get("schema_version") != ISSUE_FIX_REVIEWER_ARTIFACT_SCHEMA_VERSION:
        reasons.append("artifact_schema_invalid")
    if not summary or not any("\u4e00" <= char <= "\u9fff" for char in summary):
        reasons.append("concise_chinese_summary_missing")
    if shared.get("status") != "applied":
        reasons.append("memory_not_applied")
    if receipt.get("schema_version") != "reward_memory_application_receipt_v0":
        reasons.append("application_receipt_invalid")
    if receipt.get("current_artifact_verified") is not True:
        reasons.append("current_artifact_unverified")
    if receipt.get("result_readback_verified") is not True:
        reasons.append("memory_readback_unverified")
    digests = receipt.get("memory_ref_digests")
    if not isinstance(digests, list) or not digests:
        reasons.append("memory_attribution_missing")
    return {
        "schema_version": "issue_fix_reviewer_artifact_notification_gate_v0",
        "passed": not reasons,
        "status": "ready" if not reasons else "blocked",
        "reason_codes": reasons,
        "surface_id": ISSUE_FIX_REVIEWER_ARTIFACT_SURFACE,
        "summary": summary or None,
        "application_receipt": dict(receipt) if receipt else None,
        "grants_new_action_authority": False,
        "external_writes_performed": False,
    }


def run_issue_fix_reviewer_artifact_reward_memory(
    base_artifact: Mapping[str, Any],
    *,
    reviewer_summary: str | None,
    reasoning_summary: str | None,
    corpus: Mapping[str, Any],
    workspace_ref: str,
    repository_ref: str,
    revision_ref: str,
    observed_at: str,
    freshness_context: Mapping[str, Any],
    conflict_state: str,
    read_authority_checkpoint: Mapping[str, Any],
    provider_binding: Mapping[str, Any],
    application_id: str,
    artifact_ref: str | None = None,
    provider: ContextProvider | None = None,
    limit: int = 3,
) -> dict[str, Any]:
    """Apply exact reviewed policy to one current reviewer-facing PR summary.

    The caller/model owns the proposed summary and its reasoning. This adapter
    only preserves PR identity, attributes recalled memory, and emits the
    compact receipt consumed by the external notification gate.
    """

    base = _reviewer_artifact(base_artifact)
    proposed_summary = public_safe_compact_text(reviewer_summary, limit=220)
    proposed_reasoning = public_safe_compact_text(reasoning_summary, limit=500)

    apply_memory: RewardMemoryApplier | None = None
    if proposed_summary and proposed_reasoning:

        def apply_memory(current: Any, items: Any) -> Mapping[str, Any]:
            if not isinstance(current, Mapping):
                raise ValueError("reviewer artifact base must be an object")
            verified = _reviewer_artifact(current)
            output = {**verified, "summary": proposed_summary}
            return {
                "outcome": "applied",
                "output": output,
                "memory_refs": [item.memory_ref for item in items],
                "reasoning_summary": proposed_reasoning,
                "current_artifact_verified": all(
                    output[key] == base[key]
                    for key in ("repo", "pr_ref", "permalink", "source_title")
                ),
            }

    shared = run_semantic_preference_reward_memory(
        base,
        corpus=corpus,
        request={
            "workspace_ref": workspace_ref,
            "project_ref": repository_ref,
            "surface_id": ISSUE_FIX_REVIEWER_ARTIFACT_SURFACE,
            "revision_ref": revision_ref,
            "mode": "function_boundary",
            "queries": [
                {
                    "query": (
                        "Which reviewed policy governs this reviewer-facing PR "
                        "summary?"
                    ),
                    "query_summary": "reviewer-facing PR summary policy",
                }
            ],
            "limit": limit,
            "observed_at": observed_at,
            "freshness_context": dict(freshness_context),
            "conflict_state": conflict_state,
            "raw_content_captured": False,
        },
        read_authority_checkpoint=read_authority_checkpoint,
        provider_binding=provider_binding,
        application_id=application_id,
        artifact_ref=artifact_ref,
        apply_memory=apply_memory,
        provider=provider,
    )
    output = shared.get("output")
    if not isinstance(output, Mapping):
        raise AssertionError("reviewer artifact fail-open invariant was violated")
    result = {
        "ok": True,
        "schema_version": ISSUE_FIX_REVIEWER_ARTIFACT_APPLICATION_SCHEMA_VERSION,
        "surface_id": ISSUE_FIX_REVIEWER_ARTIFACT_SURFACE,
        "reviewer_artifact": _reviewer_artifact(output),
        "recall": shared["recall"],
        "application": shared["application"],
        "shared_core": shared["shared_core"],
        "adapter_role": "identity_guard_only_model_owns_summary_reasoning",
        "automatic_recall": False,
        "provider_failure_is_user_gate": False,
    }
    result["notification_gate"] = reviewer_artifact_notification_gate(result)
    return result
