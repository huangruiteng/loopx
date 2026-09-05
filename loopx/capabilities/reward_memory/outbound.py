"""Scoped advisory recall for a caller-owned outbound intent.

The caller owns authorization, destination validation and delivery. Recalled
text is returned to the agent, never interpreted as a send/deny policy.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .experiment import (
    resolve_reward_memory_experiment,
    resolve_reward_memory_surface_config,
)
from .runtime_hooks import run_reward_memory_automatic_recall_hook

SURFACE = "outbound_message.before_send"


def outbound_guidance_hook(
    *,
    registry_path: Path,
    goal_id: str | None,
    agent_id: str | None,
    purpose: str = "unspecified",
    reviewed_digest: str | None = None,
):
    """Build an opt-in hook; absence preserves the existing sender exactly."""
    if purpose not in {"unspecified", "help", "progress", "urgent"}:
        raise ValueError("invalid outbound message purpose")
    if not goal_id or not agent_id:
        return None
    _, config = resolve_reward_memory_experiment(
        registry_path=registry_path, goal_id=goal_id, agent_id=agent_id
    )
    if config is None or not config["automation"]["automatic_recall"]:
        return None
    if SURFACE not in config["surfaces"]:
        return None
    route = resolve_reward_memory_surface_config(config, SURFACE)
    identity = None
    checkpoints = {}
    for item in route["recall_corpora"]:
        corpus = item["corpus"]
        scope = corpus["scope"]
        current = {
            key: scope.get(key)
            for key in (
                "workspace_ref",
                "project_ref",
                "user_ref",
                "peer_ref",
                "session_ref",
            )
        }
        if current["peer_ref"] != f"agent:{agent_id}":
            raise ValueError(
                "outbound recall requires the exact configured agent scope"
            )
        if identity is not None and identity != current:
            raise ValueError("outbound recall corpora must share an identity scope")
        identity = current
        checkpoints[corpus["corpus_id"]] = {
            **{k: v for k, v in current.items() if v is not None},
            "verified": True,
            "corpus_id": corpus["corpus_id"],
            "surface_id": SURFACE,
            "read_authority": corpus["read_authority"],
            "source_ref": f"registry:{goal_id}:reward-memory",
        }

    def recall(intent_digest: str) -> dict[str, Any]:
        def apply(base, items):
            guidance = [
                {"candidate_ref": i.candidate_ref, "content_summary": i.content_summary}
                for i in items
                if i.target_class == "soft_preference"
            ]
            return {
                "outcome": "applied" if guidance else "ignored",
                "output": {"guidance": guidance},
                "memory_refs": [
                    i.memory_ref for i in items if i.target_class == "soft_preference"
                ],
                "reasoning_summary": "Guidance returned to the agent before delivery; no send authority granted.",
                "current_artifact_verified": True,
            }

        result = run_reward_memory_automatic_recall_hook(
            config,
            surface_id=SURFACE,
            base_output={"guidance": []},
            **identity,
            revision_ref=intent_digest,
            artifact_ref=intent_digest,
            queries=[
                {
                    "query": f"Reviewed guidance before an outbound {purpose} message: alternatives, evidence, recipient and escalation",
                    "query_summary": "outbound communication guidance",
                }
            ],
            observed_at=datetime.now(timezone.utc).isoformat(),
            freshness_context={
                "source_truth_current": True,
                "source_revision": intent_digest,
                "age_seconds": 0,
            },
            conflict_state="clear",
            read_authority_checkpoints=checkpoints,
            application_id="outbound-guidance",
            apply_memory=apply,
        )
        guidance = result.get("output", {}).get("guidance", [])
        digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    {
                        "intent": intent_digest,
                        "identity": identity,
                        "purpose": purpose,
                        "guidance": guidance,
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        )
        # This acknowledgement is by the executing agent, never a user gate.
        # Urgent notices and unavailable providers preserve the existing path.
        review_required = (
            bool(guidance) and purpose != "urgent" and reviewed_digest != digest
        )
        return {
            "schema_version": "outbound_guidance_review_v0",
            "status": result["status"],
            "guidance": guidance,
            "review_digest": digest,
            "agent_review_required": review_required,
            "continue_delivery": not review_required,
            "urgent_notice": purpose == "urgent",
            "provider_failure_is_user_gate": False,
            "grants_new_action_authority": False,
            "application": result.get("application"),
            "telemetry": result.get("telemetry"),
        }

    return recall
