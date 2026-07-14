#!/usr/bin/env python3
from __future__ import annotations

import sys
import json
import subprocess
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


from loopx.capabilities.reward_memory import (  # noqa: E402
    RewardMemoryRecallItem,
    RewardMemoryRecallSession,
    apply_reward_memory_recall,
    build_reward_memory_candidate,
    build_reward_memory_dogfood_batch,
    build_reward_memory_dogfood_receipt,
    build_reward_memory_operator_control,
    review_reward_memory_candidate,
    run_reward_memory_evaluation,
)


def corpus() -> dict[str, object]:
    return {
        "corpus_id": "dogfood_preferences",
        "class_id": "soft_preference",
        "provider_id": "configured_memory_provider",
        "owner_ref": "owner:dogfood",
        "source_of_truth": "reviewed_feedback",
        "read_authority": "module_scoped",
        "write_authority": "provider_managed",
        "scope": {
            "workspace_ref": "workspace:dogfood",
            "project_ref": "project:dogfood",
            "surface_ids": ["module.owned_surface"],
        },
        "freshness": {"mode": "source_truth_bound"},
        "lifecycle": {"state": "active", "supersedes": []},
        "retrieval": {
            "index_required": True,
            "readback_required": True,
            "application_receipt_required": True,
        },
        "maintenance": {
            "writeback_triggers": ["explicit_feedback"],
            "closure_policy": "owner_write_then_exact_readback",
            "retirement_authority": "operator:retirement",
        },
        "privacy": {"visibility": "private", "raw_content_in_registry": False},
    }


def active_review() -> dict[str, object]:
    candidate = build_reward_memory_candidate(
        {
            "target_class": "soft_preference",
            "content_summary": (
                "Prefer a focused change unless current evidence justifies a broader one."
            ),
            "source": {
                "source_kind": "reviewed_feedback",
                "source_ref": "fixture:dogfood:reviewed",
                "actor_ref": "operator:fixture",
                "actor_role": "verified_project_owner_or_operator",
            },
            "scope": {
                "workspace_ref": "workspace:dogfood",
                "project_ref": "project:dogfood",
                "surface_ids": ["module.owned_surface"],
            },
            "reasoning": {
                "summary": "The preference is reusable inside one owned module.",
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
    return review_reward_memory_candidate(
        candidate,
        {
            "decision": "accept",
            "reviewer_ref": "operator:fixture",
            "review_ref": "review:dogfood:accept",
            "reasoning_summary": "The scoped compact preference is accepted.",
        },
    )


def session(*, surface_id: str, status: str) -> RewardMemoryRecallSession:
    items: tuple[RewardMemoryRecallItem, ...] = ()
    if status == "completed":
        items = (
            RewardMemoryRecallItem(
                memory_ref=f"memory:{surface_id}",
                candidate_ref=f"candidate:{surface_id}",
                target_class="soft_preference",
                content_summary="Transient fixture summary.",
            ),
        )
    return RewardMemoryRecallSession(
        public_packet={
            "corpus_id": "dogfood_preferences",
            "surface_id": surface_id,
            "mode": "function_boundary",
            "status": status,
            "result_readback_verified": status == "completed",
        },
        items=items,
    )


def application_receipts() -> list[dict[str, object]]:
    hit_session = session(surface_id="issue_fix.patch_planning", status="completed")
    hit = apply_reward_memory_recall(
        {"candidate": "broad_change"},
        hit_session,
        application_id="application:issue-fix",
        artifact_ref="artifact:issue-fix",
        apply_memory=lambda base, items: {
            "outcome": "applied",
            "output": {"candidate": "focused_change"},
            "memory_refs": [items[0].memory_ref],
            "reasoning_summary": "Current code supports the narrower candidate.",
            "current_artifact_verified": True,
        },
    )["receipt"]

    miss = apply_reward_memory_recall(
        {"layout": "semantic_lanes"},
        session(surface_id="explore_graph.layout", status="empty"),
        application_id="application:explore",
        artifact_ref="artifact:explore",
    )["receipt"]

    refute_session = session(
        surface_id="runtime_projection.routing", status="completed"
    )
    refute = apply_reward_memory_recall(
        {"route": "external_runtime"},
        refute_session,
        application_id="application:runtime-route",
        artifact_ref="artifact:runtime-route",
        apply_memory=lambda base, items: {
            "outcome": "refuted",
            "output": base,
            "memory_refs": [items[0].memory_ref],
            "reasoning_summary": "Current registry evidence refutes the old route.",
            "current_artifact_verified": True,
        },
    )["receipt"]
    return [hit, miss, refute]


def observation(
    receipt: dict[str, object],
    *,
    family: str,
    domain_id: str,
    latency_ms: int,
    interventions: int,
) -> dict[str, object]:
    return {
        "raw_content_captured": False,
        "domain_family": family,
        "domain_id": domain_id,
        "application_receipt": receipt,
        "module_outcome": {
            "artifact_ref": receipt["artifact_ref"],
            "outcome_verified": True,
            "summary": f"Verified bounded outcome for {domain_id}.",
        },
        "cost": {
            "latency_ms": latency_ms,
            "model_tokens": 0,
            "provider_call_count": int(bool(receipt["result_readback_verified"])),
        },
        "intervention": {
            "count": interventions,
            "summary": (
                "One operator correction was required." if interventions else None
            ),
        },
        "bot_feedback": {
            "captured": family == "issue_fix",
            "summary": (
                "The bot can consume the compact verified receipt."
                if family == "issue_fix"
                else None
            ),
        },
    }


def main() -> None:
    receipts = application_receipts()
    observations = [
        observation(
            receipts[0],
            family="issue_fix",
            domain_id="issue_fix.patch_planning",
            latency_ms=8,
            interventions=0,
        ),
        observation(
            receipts[1],
            family="loopx",
            domain_id="loopx.explore_graph",
            latency_ms=2,
            interventions=0,
        ),
        observation(
            receipts[2],
            family="loopx",
            domain_id="loopx.runtime_projection",
            latency_ms=5,
            interventions=1,
        ),
    ]
    dogfood = [build_reward_memory_dogfood_receipt(item) for item in observations]

    reviewed = active_review()
    edited = build_reward_memory_operator_control(
        reviewed,
        corpus(),
        action="edit",
        operator_checkpoint={
            "verified": True,
            "operator_ref": "operator:fixture",
            "authority_ref": "owner:dogfood",
            "source_ref": "authority:fixture:edit",
            "corpus_id": "dogfood_preferences",
            "project_ref": "project:dogfood",
            "action": "edit",
        },
        control_ref="control:dogfood:edit",
        reasoning_summary="The owner narrowed the preference.",
        edited_content_summary="Prefer a focused change after current-artifact verification.",
    )
    assert edited["decision"]["status"] == "review_ready", edited
    retired = build_reward_memory_operator_control(
        reviewed,
        corpus(),
        action="retire",
        operator_checkpoint={
            "verified": True,
            "operator_ref": "operator:fixture",
            "authority_ref": "operator:retirement",
            "source_ref": "authority:fixture:retire",
            "corpus_id": "dogfood_preferences",
            "project_ref": "project:dogfood",
            "action": "retire",
        },
        control_ref="control:dogfood:retire",
        reasoning_summary="Current evidence supersedes the preference.",
    )
    assert retired["decision"]["status"] == "retired", retired
    try:
        build_reward_memory_operator_control(
            reviewed,
            corpus(),
            action="edit",
            operator_checkpoint={
                "verified": True,
                "operator_ref": "operator:fixture",
                "authority_ref": "owner:dogfood",
                "source_ref": "authority:fixture:wrong-project",
                "corpus_id": "dogfood_preferences",
                "project_ref": "project:other",
                "action": "edit",
            },
            control_ref="control:dogfood:wrong-project",
            reasoning_summary="This checkpoint belongs to another project.",
            edited_content_summary="This edit must not be accepted.",
        )
    except ValueError as exc:
        assert "project does not match" in str(exc), exc
    else:
        raise AssertionError("cross-project operator authority was accepted")

    packet = build_reward_memory_dogfood_batch(
        dogfood,
        [edited["receipt"], retired["receipt"]],
        evaluation=run_reward_memory_evaluation(),
    )
    assert packet["status"] == "ready_for_bounded_issue_fix_pilot", packet
    assert packet["metrics"]["hit_count"] == 1, packet
    assert packet["metrics"]["miss_count"] == 1, packet
    assert packet["metrics"]["refute_count"] == 1, packet
    assert packet["metrics"]["loopx_domain_count"] == 2, packet
    assert packet["metrics"]["intervention_count"] == 1, packet
    assert packet["boundaries"]["production_rollout_allowed"] is False, packet
    assert packet["boundaries"]["operator_write_performed"] is False, packet

    held = build_reward_memory_dogfood_batch(
        dogfood[:1],
        [edited["receipt"]],
        evaluation=run_reward_memory_evaluation(),
    )
    assert held["status"] == "hold", held
    assert "two_loopx_domains_required" in held["reason_codes"], held
    assert "operator_control_missing:retire" in held["reason_codes"], held

    with tempfile.TemporaryDirectory() as directory:
        dogfood_input = Path(directory) / "dogfood.json"
        dogfood_input.write_text(
            json.dumps(
                {
                    "observations": observations,
                    "operator_controls": [
                        edited["receipt"],
                        retired["receipt"],
                    ],
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "reward-memory",
                "dogfood-evaluate",
                "--input",
                str(dogfood_input),
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        cli_packet = json.loads(completed.stdout)
        assert cli_packet["status"] == "ready_for_bounded_issue_fix_pilot"

        control_input = Path(directory) / "control.json"
        control_input.write_text(
            json.dumps(
                {
                    "reviewed_record": reviewed,
                    "corpus": corpus(),
                    "operator_checkpoint": {
                        "verified": True,
                        "operator_ref": "operator:fixture",
                        "authority_ref": "owner:dogfood",
                        "source_ref": "authority:fixture:edit",
                        "corpus_id": "dogfood_preferences",
                        "project_ref": "project:dogfood",
                        "action": "edit",
                    },
                }
            ),
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "reward-memory",
                "operator-control",
                "--input",
                str(control_input),
                "--action",
                "edit",
                "--control-ref",
                "control:cli:edit",
                "--reasoning-summary",
                "The owner narrowed the preference.",
                "--edited-content-summary",
                "Prefer a focused current-artifact-verified change.",
                "--format",
                "json",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        control_packet = json.loads(completed.stdout)
        assert control_packet["status"] == "control_ready"
    print("reward-memory-dogfood-smoke: ok")


if __name__ == "__main__":
    main()
