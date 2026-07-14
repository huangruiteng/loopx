from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..context_providers.base import ContextProvider
from ..reward_memory.application import (
    RewardMemoryApplier,
    apply_reward_memory_recall,
    build_reward_memory_recall_request,
    execute_reward_memory_recall,
)


SEMANTIC_PREFERENCE_REWARD_MEMORY_SCHEMA_VERSION = (
    "semantic_preference_reward_memory_application_v0"
)


def run_semantic_preference_reward_memory(
    base_output: Any,
    *,
    corpus: Mapping[str, Any],
    request: Mapping[str, Any],
    read_authority_checkpoint: Mapping[str, Any],
    provider_binding: Mapping[str, Any],
    application_id: str,
    artifact_ref: str | None = None,
    apply_memory: RewardMemoryApplier | None = None,
    provider: ContextProvider | None = None,
) -> dict[str, Any]:
    """Reuse the shared Stage-3 seam from a non-Issue-Fix capability."""

    recall_request = build_reward_memory_recall_request(
        corpus,
        request,
        read_authority_checkpoint=read_authority_checkpoint,
    )
    session = execute_reward_memory_recall(
        recall_request,
        provider_binding=provider_binding,
        provider=provider,
    )
    application = apply_reward_memory_recall(
        base_output,
        session,
        application_id=application_id,
        artifact_ref=artifact_ref,
        apply_memory=apply_memory,
    )
    return {
        "ok": True,
        "schema_version": SEMANTIC_PREFERENCE_REWARD_MEMORY_SCHEMA_VERSION,
        "surface_id": recall_request["request"]["surface_id"],
        "output": application["output"],
        "recall": session.public_packet,
        "application": {
            key: value for key, value in application.items() if key != "output"
        },
        "shared_core": "loopx.capabilities.reward_memory.application",
        "automatic_recall": False,
    }
