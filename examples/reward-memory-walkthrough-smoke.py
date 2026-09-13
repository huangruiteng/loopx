#!/usr/bin/env python3
"""Contributor-safe walkthrough: corpus health → candidate → ATR → apply → feedback.

Synthetic quota/todo packets only. Guidance stays advisory. Without explicit
Reward Memory activation, Agent Turn Recall fails closed. No external sinks and
no retained provider payloads.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.agent_turn_recall import (  # noqa: E402
    build_agent_turn_recall_preview,
    build_agent_turn_situation,
    run_agent_turn_recall,
)
from loopx.capabilities.context_providers.base import (  # noqa: E402
    ContextProviderItem,
    ContextProviderRetrieval,
    ContextProviderSync,
)
from loopx.capabilities.reward_memory import (  # noqa: E402
    apply_reward_memory_recall,
    build_active_reward_memory_record,
    build_reward_memory_candidate,
    build_reward_memory_corpus_health_packet,
    build_reward_memory_recall_request,
    execute_reward_memory_recall,
    review_reward_memory_candidate,
    reward_memory_health_case,
)
from loopx.capabilities.reward_memory.experiment import (  # noqa: E402
    load_reward_memory_experiment_config,
    resolve_reward_memory_surface_config,
)
from loopx.capabilities.reward_memory.scoped_feedback import (  # noqa: E402
    ingest_scoped_feedback_reward_memory_event,
)


OBSERVED_AT = "2026-08-26T07:00:00+00:00"
WORKSPACE = "workspace:rm-walkthrough"
PROJECT = "repository:loopx"
USER = "user:example"
PEER = "agent:pilot"
SESSION = "session:walkthrough-turn"
SURFACE = "agent_workflow.turn_admission"
SCOPE_REF = "viking://user/example/memories/agent-turn"
GOAL_ID = "goal:rm-walkthrough"

_PRIVATE_RE = (
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._-]+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
)


class FakeProvider:
    provider_id = "fake_provider"

    def __init__(self, content: str | None = None) -> None:
        self.content = content
        self.calls = 0

    def retrieve(self, **kwargs: Any) -> ContextProviderRetrieval:
        self.calls += 1
        content = self.content
        if content is None:
            items: tuple[ContextProviderItem, ...] = ()
        else:
            items = (
                ContextProviderItem(
                    resource_ref=f"{SCOPE_REF}/guidance.json",
                    summary="Scoped turn guidance.",
                    content=content,
                    score=0.97,
                ),
            )
        return ContextProviderRetrieval(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="completed",
            query_summary=str(kwargs["query_summary"]),
            observed_at=str(kwargs["observed_at"]),
            search_performed=True,
            read_performed=bool(items),
            items=items,
            requested_limit=int(kwargs["max_results"]),
        )

    def sync(self, **kwargs: Any) -> ContextProviderSync:
        assert kwargs["execute"] is False
        self.calls += 1
        return ContextProviderSync(
            provider=self.provider_id,
            namespace=str(kwargs["namespace"]),
            status="preflight_ready",
            observed_at=str(kwargs["observed_at"]),
            requested_count=1,
            completed_count=0,
            reason_code="execute_required_for_verified_write",
            retry_disposition="execute_required",
            provider_preflight_performed=True,
            target_access_preflight_verified=True,
            writability_verified=False,
        )


def assert_public_safe(payload: object) -> None:
    text = json.dumps(payload, sort_keys=True) if not isinstance(payload, str) else payload
    for pattern in _PRIVATE_RE:
        assert pattern.search(text) is None, pattern.pattern
    assert '"provider_payload":' not in text
    assert "raw chat" not in text.lower()


def quota_decision() -> dict[str, Any]:
    return {
        "ok": True,
        "status_health_ok": True,
        "decision": "run",
        "lifecycle_phase": "reviewing",
        "recommended_action": "Review and refine the selected work.",
        "selected_todo": {
            "todo_id": "todo:walkthrough-001",
            "text": "Advance one synthetic review todo.",
            "action_kind": "review_refine_merge",
            "target_key": "pr:walkthrough",
            "claimed_by": "pilot",
        },
    }


def corpus() -> dict[str, Any]:
    return {
        "corpus_id": "agent_turn_prefs",
        "class_id": "soft_preference",
        "provider_id": "fake_provider",
        "owner_ref": "owner:example",
        "source_of_truth": "reviewed_owner_feedback",
        "read_authority": "module_scoped",
        "write_authority": "provider_managed",
        "scope": {
            "workspace_ref": WORKSPACE,
            "project_ref": PROJECT,
            "user_ref": USER,
            "peer_ref": PEER,
            "session_ref": SESSION,
            "surface_ids": [SURFACE],
        },
        "freshness": {"mode": "source_truth_bound"},
        "lifecycle": {"state": "active", "supersedes": []},
        "retrieval": {
            "index_required": True,
            "readback_required": True,
            "application_receipt_required": True,
        },
        "maintenance": {
            "writeback_triggers": ["reviewed_candidate"],
            "closure_policy": "provider_write_then_revision_verified_read",
            "retirement_authority": "owner:example",
        },
        "privacy": {"visibility": "private", "raw_content_in_registry": False},
        "provider_scope_ref_digest": hashlib.sha256(
            SCOPE_REF.encode("utf-8")
        ).hexdigest()[:16],
    }


def checkpoint() -> dict[str, Any]:
    return {
        "verified": True,
        "corpus_id": "agent_turn_prefs",
        "workspace_ref": WORKSPACE,
        "project_ref": PROJECT,
        "user_ref": USER,
        "peer_ref": PEER,
        "session_ref": SESSION,
        "surface_id": SURFACE,
        "read_authority": "module_scoped",
        "source_ref": "repository:authority-map",
    }


def binding() -> dict[str, Any]:
    return {
        "corpus_id": "agent_turn_prefs",
        "provider_id": "fake_provider",
        "namespace": "reward_memory",
        "scope_ref": SCOPE_REF,
        "timeout_seconds": 5,
    }


def standing_policy() -> dict[str, Any]:
    return {
        "schema_version": "reward_memory_standing_policy_v0",
        "policy_id": "policy:walkthrough:agent-turn",
        "enabled": True,
        "auto_activate": True,
        "owner_ref": "owner:example",
        "reviewer_ref": "github:user:maintainer",
        "authority_source_ref": "policy:walkthrough:agent-turn",
        "scope": dict(corpus()["scope"]),
        "allowed_target_classes": ["soft_preference"],
        "allowed_source_kinds": ["explicit_feedback", "explicit_user_instruction"],
        "allowed_actor_roles": ["verified_project_owner_or_operator"],
        "allowed_action_scopes": [],
        "raw_content_captured": False,
    }


def candidate_scope() -> dict[str, Any]:
    scope = dict(corpus()["scope"])
    scope["revision_ref"] = "revision:abc123"
    return scope


def build_candidate() -> dict[str, Any]:
    return build_reward_memory_candidate(
        {
            "target_class": "soft_preference",
            "content_summary": "Prefer small reversible turn refinements.",
            "source": {
                "source_kind": "explicit_feedback",
                "source_ref": "fb:walkthrough-1",
                "actor_ref": USER,
                "actor_role": "verified_project_owner_or_operator",
            },
            "scope": candidate_scope(),
            "reasoning": {
                "summary": "Owner preference for bounded turn changes.",
                "confidence": "high",
            },
            "guard_context": {
                "source_freshness": "current",
                "conflict_state": "clear",
                "current_artifact_verified": True,
            },
            "requested_action_scopes": [],
            "raw_content_captured": False,
        }
    )


def feedback_event(*, peer_ref: str = PEER, project_ref: str = PROJECT) -> dict[str, Any]:
    return {
        "schema_version": "scoped_feedback_reward_memory_event_v0",
        "feedback_ref": "feedback:walkthrough:turn-preference",
        "workspace_ref": WORKSPACE,
        "project_ref": project_ref,
        "user_ref": USER,
        "peer_ref": peer_ref,
        "session_ref": SESSION,
        "surface_id": SURFACE,
        "revision_ref": "revision:abc123",
        "target_class": "soft_preference",
        "content_summary": "Prefer small reversible turn refinements.",
        "source": {
            "source_kind": "explicit_user_instruction",
            "source_ref": "user:instruction:walkthrough",
            "actor_ref": USER,
            "actor_role": "verified_project_owner_or_operator",
        },
        "reasoning": {
            "summary": "Scoped feedback for one agent session.",
            "confidence": "high",
        },
        "guard_context": {
            "source_freshness": "current",
            "conflict_state": "clear",
            "current_artifact_verified": True,
        },
        "requested_action_scopes": [],
        "raw_content_captured": False,
    }


def recall_payload(**overrides: Any) -> dict[str, Any]:
    """Function-boundary recall payload; scope fields are overridable for fail-closed cases."""
    payload: dict[str, Any] = {
        "workspace_ref": WORKSPACE,
        "project_ref": PROJECT,
        "user_ref": USER,
        "peer_ref": PEER,
        "session_ref": SESSION,
        "surface_id": SURFACE,
        "revision_ref": "revision:abc123",
        "mode": "function_boundary",
        "queries": [
            {"query": "turn guidance", "query_summary": "turn admission"},
        ],
        "limit": 3,
        "observed_at": OBSERVED_AT,
        "freshness_context": {
            "source_truth_current": True,
            "source_revision": "revision:abc123",
        },
        "conflict_state": "clear",
        "raw_content_captured": False,
    }
    payload.update(overrides)
    return payload


def experiment_raw(*, automatic_recall: bool) -> dict[str, Any]:
    selected = corpus()
    return {
        "schema_version": "reward_memory_experiment_config_v1",
        "project_provider_binding": {
            "provider_id": "fake_provider",
            "namespace": "reward_memory",
            "timeout_seconds": 5,
            "corpus_scopes": [
                {"corpus_id": selected["corpus_id"], "scope_ref": SCOPE_REF}
            ],
        },
        "corpora": [{"corpus": selected, "standing_policy": standing_policy()}],
        "surfaces": [
            {
                "surface_id": SURFACE,
                "adapter": "scoped_feedback",
                "corpus_ids": [selected["corpus_id"]],
                "ingest_corpus_id": selected["corpus_id"],
                "recall_profile": {
                    "profile_id": "agent_turn_v1",
                    "mode": "bounded_agentic_search",
                    "max_queries": 1,
                    "limit": 4,
                },
            }
        ],
        "automation": {
            "automatic_recall": automatic_recall,
            "automatic_ingest": False,
            "fail_open": True,
        },
    }


def load_config(*, automatic_recall: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="loopx-rm-walkthrough-") as root:
        project = Path(root)
        path = project / "experiment.json"
        path.write_text(
            json.dumps(experiment_raw(automatic_recall=automatic_recall)),
            encoding="utf-8",
        )
        return load_reward_memory_experiment_config(
            project=project,
            config_path="experiment.json",
        )


def situation() -> dict[str, Any]:
    return build_agent_turn_situation(
        quota_decision(),
        goal_id=GOAL_ID,
        agent_id="pilot",
        turn_instance_id=OBSERVED_AT,
        workspace_ref=WORKSPACE,
        project_ref=PROJECT,
        user_ref=USER,
        session_ref=SESSION,
    )


def main() -> int:
    # 1) Corpus health: empty fails closed for apply; retrieval-verified may apply.
    empty_corpus, empty_obs = reward_memory_health_case("empty")
    empty_health = build_reward_memory_corpus_health_packet(empty_corpus, empty_obs)
    assert empty_health["health_state"] == "empty"
    assert empty_health["may_apply_memory"] is False
    assert empty_health["memory_patch_authority"] is False

    ready_corpus, ready_obs = reward_memory_health_case("retrieval-verified")
    ready_health = build_reward_memory_corpus_health_packet(ready_corpus, ready_obs)
    assert ready_health["health_state"] == "retrieval_verified"
    assert ready_health["may_apply_memory"] is True
    assert_public_safe(empty_health)
    assert_public_safe(ready_health)

    # 2) Candidate review stays advisory and does not write providers.
    candidate = build_candidate()
    assert candidate["status"] == "review_ready"
    assert candidate["raw_content_captured"] is False
    assert candidate["provider_write_performed"] is False
    accepted = review_reward_memory_candidate(
        candidate,
        {
            "decision": "accept",
            "reviewer_ref": "github:user:maintainer",
            "review_ref": "review:walkthrough-accept",
            "reasoning_summary": "Scoped preference is review-ready.",
        },
    )
    assert accepted["effective_decision"] == "accept"
    assert accepted["status"] == "active"
    assert accepted["grants_new_action_authority"] is False
    assert accepted["provider_write_performed"] is False
    active = build_active_reward_memory_record(
        accepted, corpus(), activated_at=OBSERVED_AT
    )
    assert active["schema_version"] == "reward_memory_active_record_v0"
    assert active["provider_write_performed"] is False
    assert_public_safe(active)

    # 3) Agent Turn Recall: preview, fail closed without activation, then apply.
    turn = situation()
    assert turn["user_prompt_included"] is False
    assert turn["session_ref"] == SESSION
    preview = build_agent_turn_recall_preview(turn)
    assert preview["status"] == "preview"
    assert preview["provider_call_count"] == 0
    assert preview["context"]["guidance"] == []
    assert preview["grants_new_action_authority"] is False
    assert preview["suppress_external_sinks"] is True

    disabled_config = load_config(automatic_recall=False)
    disabled_provider = FakeProvider(json.dumps(active, ensure_ascii=False))
    disabled = run_agent_turn_recall(
        disabled_config,
        turn,
        observed_at=OBSERVED_AT,
        read_authority_checkpoints={
            "agent_turn_prefs": checkpoint(),
        },
        provider=disabled_provider,
    )
    assert disabled["status"] == "disabled"
    assert disabled["provider_call_count"] == 0
    assert disabled_provider.calls == 0
    assert disabled["grants_new_action_authority"] is False
    assert disabled["suppress_external_sinks"] is True
    assert disabled["raw_provider_payload_captured"] is False

    enabled_config = load_config(automatic_recall=True)
    route = resolve_reward_memory_surface_config(enabled_config, SURFACE)
    enabled_provider = FakeProvider(json.dumps(active, ensure_ascii=False))
    recalled = run_agent_turn_recall(
        enabled_config,
        turn,
        observed_at=OBSERVED_AT,
        read_authority_checkpoints={
            route["corpus"]["corpus_id"]: checkpoint(),
        },
        provider=enabled_provider,
    )
    assert recalled["status"] == "applied"
    assert recalled["provider_call_count"] == 1
    assert len(recalled["context"]["guidance"]) == 1
    assert recalled["grants_new_action_authority"] is False
    assert recalled["quota_spend_performed"] is False
    assert recalled["suppress_external_sinks"] is True
    assert recalled["raw_provider_payload_captured"] is False
    assert_public_safe(recalled)

    # 4) Explicit Reward Memory recall/application remains advisory; wrong
    #    project/session scope fails closed before any provider call.
    request = build_reward_memory_recall_request(
        corpus(),
        recall_payload(),
        read_authority_checkpoint=checkpoint(),
    )
    assert request["status"] == "ready"
    apply_provider = FakeProvider(json.dumps(active, ensure_ascii=False))
    session = execute_reward_memory_recall(
        request,
        provider_binding=binding(),
        provider=apply_provider,
    )
    assert session.public_packet["status"] == "completed"
    applied = apply_reward_memory_recall(
        {"guidance": []},
        session,
        application_id="recall:walkthrough",
        apply_memory=lambda base, items: {
            "outcome": "applied",
            "output": dict(base)
            | {
                "guidance": [
                    {
                        "candidate_ref": item.candidate_ref,
                        "target_class": item.target_class,
                        "content_summary": item.content_summary,
                    }
                    for item in items
                ]
            },
            "memory_refs": [item.memory_ref for item in items],
            "reasoning_summary": "Advisory guidance injected for the exact turn.",
            "current_artifact_verified": True,
        },
    )
    assert applied["status"] == "applied"
    assert applied["receipt"]["grants_new_action_authority"] is False
    assert_public_safe(applied)

    # Mirrors tests/capabilities/test_reward_memory_agent_scoped_recall.py:
    # wrong and missing agent/task scope must both fail closed at the guard.
    scope_negatives = [
        ("project_ref", {"project_ref": "repository:other"}, "project_scope_mismatch"),
        ("session_ref", {"session_ref": "task:other"}, "session_ref_scope_mismatch"),
        ("missing session_ref", {"session_ref": None}, "session_ref_scope_mismatch"),
    ]
    scope_blocked: dict[str, str] = {}
    for label, overrides, reason_code in scope_negatives:
        blocked = build_reward_memory_recall_request(
            corpus(),
            recall_payload(**overrides),
            read_authority_checkpoint=checkpoint(),
        )
        assert blocked["status"] == "guard_blocked", label
        assert reason_code in blocked["guard"]["reason_codes"], label
        scope_blocked[label] = blocked["status"]

    # 5) Scoped feedback: plan without provider write; wrong peer fails closed.
    provider = FakeProvider()
    planned = ingest_scoped_feedback_reward_memory_event(
        feedback_event(),
        corpus=corpus(),
        standing_policy=standing_policy(),
        provider_binding=binding(),
        observed_at=OBSERVED_AT,
        execute=False,
        provider=provider,
    )
    assert planned["status"] == "preflight_ready"
    assert planned["external_writes_performed"] is False
    assert planned["raw_provider_payload_captured"] is False
    assert planned["grants_new_action_authority"] is False
    assert planned["next_reward_memory_call"] == "explicit_function_boundary_recall"
    assert provider.calls == 1

    blocked_peer = ingest_scoped_feedback_reward_memory_event(
        feedback_event(peer_ref="agent:other"),
        corpus=corpus(),
        standing_policy=standing_policy(),
        provider_binding=binding(),
        observed_at=OBSERVED_AT,
        execute=False,
    )
    assert blocked_peer["status"] == "guard_blocked"
    assert "candidate_peer_ref_corpus_mismatch" in blocked_peer["guard"]["reason_codes"]

    walkthrough = {
        "empty_health": empty_health["health_state"],
        "ready_health": ready_health["health_state"],
        "candidate_status": accepted["status"],
        "atr_disabled_status": disabled["status"],
        "atr_applied_status": recalled["status"],
        "application_status": applied["status"],
        "feedback_status": planned["status"],
        "scope": {
            "agent": PEER,
            "project": PROJECT,
            "session": SESSION,
        },
    }
    assert_public_safe(walkthrough)

    print(
        json.dumps(
            {
                "ok": True,
                "walkthrough": "corpus_health→candidate→atr→apply→scoped_feedback",
                "may_apply_when_empty": empty_health["may_apply_memory"],
                "may_apply_when_verified": ready_health["may_apply_memory"],
                "atr_without_activation": disabled["status"],
                "atr_with_activation": recalled["status"],
                "guidance_advisory": recalled["grants_new_action_authority"] is False,
                "external_sinks_suppressed": recalled["suppress_external_sinks"],
                "scoped_feedback": planned["status"],
                "wrong_peer_blocked": blocked_peer["status"],
                "scope_negatives_blocked": scope_blocked,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
