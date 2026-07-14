from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..context_providers.base import ContextProvider
from ..reward_memory.application import RewardMemoryApplier
from ..semantic_preference.reward_memory import run_semantic_preference_reward_memory


ISSUE_FIX_PATCH_PLANNING_SURFACE = "issue_fix.patch_planning"
ISSUE_FIX_REWARD_MEMORY_APPLICATION_SCHEMA_VERSION = (
    "issue_fix_reward_memory_application_v0"
)


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
