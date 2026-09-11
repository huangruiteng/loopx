#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import subprocess
import tempfile
from copy import deepcopy
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
from loopx.capabilities.reward_memory.dogfood import (  # noqa: E402
    REWARD_MEMORY_DOGFOOD_BATCH_SCHEMA_VERSION,
    REWARD_MEMORY_DOGFOOD_RECEIPT_SCHEMA_VERSION,
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


def session(
    *,
    surface_id: str,
    status: str,
    memory_refs: tuple[str, ...] = (),
) -> RewardMemoryRecallSession:
    items: tuple[RewardMemoryRecallItem, ...] = ()
    if status == "completed":
        selected_refs = memory_refs or (f"memory:{surface_id}",)
        items = tuple(
            RewardMemoryRecallItem(
                memory_ref=memory_ref,
                candidate_ref=f"candidate:{surface_id}:{index}",
                target_class="soft_preference",
                content_summary="Transient fixture summary.",
            )
            for index, memory_ref in enumerate(selected_refs)
        )
    return RewardMemoryRecallSession(
        public_packet={
            "corpus_id": "dogfood_preferences",
            "surface_id": surface_id,
            "mode": "function_boundary",
            "query_kind": "business_recall",
            "query_evidence": [
                {
                    "query_digest": "0123456789abcdef",
                    "query_summary": "Scoped dogfood recall fixture.",
                    "exact_query_exposed": False,
                }
            ],
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
            "outcome_ref": f"outcome:{domain_id}",
            "outcome_status": "completed",
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


def utility_attribution(
    receipt: dict[str, object],
    *,
    outcome_ref: str,
    memory_ref_digests: list[str] | None = None,
    utility_label: str = "unknown",
    attribution_level: str = "none",
    evidence_basis: str = "insufficient",
    evidence_refs: list[str] | None = None,
) -> dict[str, object]:
    scope = {
        "agent_id": "agent:dogfood",
        "project_id": "project:dogfood",
        "corpus_id": receipt["corpus_id"],
        "surface_id": receipt["surface_id"],
    }
    return {
        "context": {
            "scope": scope,
            "retrieval_snapshot_ref": "snapshot:dogfood:stage3",
            "policy_snapshot_ref": "policy:dogfood:v0",
        },
        "proposal": {
            "scope": scope,
            "application_id": receipt["application_id"],
            "artifact_ref": receipt["artifact_ref"],
            "outcome_ref": outcome_ref,
            "outcome_status": "completed",
            "retrieval_snapshot_ref": "snapshot:dogfood:stage3",
            "policy_snapshot_ref": "policy:dogfood:v0",
            "memory_ref_digests": memory_ref_digests or receipt["memory_ref_digests"],
            "utility_label": utility_label,
            "attribution_level": attribution_level,
            "evidence_basis": evidence_basis,
            "confidence": 0.95 if evidence_refs else 0.0,
            "reason_codes": [
                "attribution_evidence_missing"
                if not evidence_refs
                else "bounded_fixture_evidence"
            ],
            "evidence_refs": evidence_refs or [],
            "evaluator_ref": "evaluator:dogfood:fixture",
            "evaluation_version": "evaluation:dogfood:v0",
        },
        "created_at": "2026-08-16T00:00:00Z",
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
    observations[0]["utility_attribution"] = utility_attribution(
        receipts[0],
        outcome_ref=observations[0]["module_outcome"]["outcome_ref"],
    )

    malformed_baseline = build_reward_memory_dogfood_receipt(observations[1])
    malformed_observation = deepcopy(observations[1])
    malformed_observation["utility_attribution"] = utility_attribution(
        receipts[1],
        outcome_ref=observations[1]["module_outcome"]["outcome_ref"],
    )
    malformed_observation["utility_attribution"]["proposal"] = {
        "utility_label": "helpful"
    }
    observations[1] = malformed_observation
    dogfood = [build_reward_memory_dogfood_receipt(item) for item in observations]
    assert dogfood[0]["schema_version"] == REWARD_MEMORY_DOGFOOD_RECEIPT_SCHEMA_VERSION
    assert dogfood[0]["application_outcome"] == "applied", dogfood[0]
    assert dogfood[0]["application_disposition"] == "applied", dogfood[0]
    assert dogfood[0]["utility_evaluation"] == {"status": "accepted"}, dogfood[0]
    assert dogfood[0]["utility_observation"]["utility_label"] == "unknown", dogfood[0]
    assert dogfood[0]["utility_observation"]["evidence_basis"] == "insufficient"

    assert dogfood[1]["utility_evaluation"] == {
        "status": "rejected",
        "reason_code": "utility_attribution_rejected",
    }, dogfood[1]
    assert dogfood[1]["utility_observation"] is None, dogfood[1]
    for key in (
        "application_id",
        "artifact_ref",
        "corpus_id",
        "surface_id",
        "application_outcome",
        "application_disposition",
        "module_outcome",
        "memory_ref_digests",
        "verification",
    ):
        assert dogfood[1][key] == malformed_baseline[key], key
    assert dogfood[1]["receipt_id"] == malformed_baseline["receipt_id"], dogfood[1]
    assert "helpful" not in json.dumps(dogfood[1]), dogfood[1]
    assert dogfood[2]["utility_evaluation"]["status"] == "not_requested"

    for nested_key in (
        "verification",
        "module_outcome",
        "utility_evaluation",
        "utility_observation",
        "cost",
        "intervention",
        "bot_feedback",
    ):
        tampered = deepcopy(dogfood[0])
        tampered[nested_key]["raw_log"] = "private fixture output"
        try:
            build_reward_memory_dogfood_batch(
                [tampered],
                [],
                evaluation=run_reward_memory_evaluation(),
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"unknown nested field was accepted: {nested_key}")

    multi_memory_result = apply_reward_memory_recall(
        {"candidate": "multi_memory"},
        session(
            surface_id="issue_fix.multi_memory",
            status="completed",
            memory_refs=("memory:multi-a", "memory:multi-b"),
        ),
        application_id="application:multi-memory",
        artifact_ref="artifact:multi-memory",
        apply_memory=lambda base, items: {
            "outcome": "applied",
            "output": {"candidate": "multi_memory"},
            "memory_refs": [item.memory_ref for item in items],
            "reasoning_summary": "The result uses both recalled memories; evidence isolates one contribution.",
            "current_artifact_verified": True,
        },
    )["receipt"]
    multi_observation = observation(
        multi_memory_result,
        family="issue_fix",
        domain_id="issue_fix.multi_memory",
        latency_ms=3,
        interventions=0,
    )
    multi_observation["utility_attribution"] = utility_attribution(
        multi_memory_result,
        outcome_ref=multi_observation["module_outcome"]["outcome_ref"],
        memory_ref_digests=[multi_memory_result["memory_ref_digests"][0]],
        utility_label="helpful",
        attribution_level="item",
        evidence_basis="deterministic_effect",
        evidence_refs=["test-result:multi-memory"],
    )
    multi_dogfood = build_reward_memory_dogfood_receipt(multi_observation)
    assert multi_dogfood["utility_evaluation"] == {"status": "accepted"}, multi_dogfood
    assert multi_dogfood["utility_observation"]["attribution_level"] == "item", (
        multi_dogfood
    )
    assert build_reward_memory_dogfood_batch(
        [multi_dogfood],
        [],
        evaluation=run_reward_memory_evaluation(),
    )["receipts"][0]["utility"]["evaluation"] == {"status": "accepted"}

    revised_utility_input = deepcopy(observations[0])
    revised_utility_input["utility_attribution"]["proposal"]["evaluation_version"] = (
        "evaluation:dogfood:v1"
    )
    revised_utility = build_reward_memory_dogfood_receipt(revised_utility_input)
    assert revised_utility["receipt_id"] == dogfood[0]["receipt_id"]
    assert (
        revised_utility["utility_observation"]["observation_id"]
        != dogfood[0]["utility_observation"]["observation_id"]
    )
    try:
        build_reward_memory_dogfood_batch(
            [dogfood[0], revised_utility],
            [],
            evaluation=run_reward_memory_evaluation(),
        )
    except ValueError as exc:
        assert "double-count a receipt" in str(exc), exc
    else:
        raise AssertionError("one settlement was counted twice")

    relabeled_settlement_input = deepcopy(observations[0])
    relabeled_settlement_input["domain_family"] = "loopx"
    relabeled_settlement_input["domain_id"] = "loopx.relabelled_settlement"
    relabeled_settlement = build_reward_memory_dogfood_receipt(
        relabeled_settlement_input
    )
    assert relabeled_settlement["receipt_id"] == dogfood[0]["receipt_id"]
    try:
        build_reward_memory_dogfood_batch(
            [dogfood[0], relabeled_settlement],
            [],
            evaluation=run_reward_memory_evaluation(),
        )
    except ValueError as exc:
        assert "double-count a receipt" in str(exc), exc
    else:
        raise AssertionError("domain relabeling double-counted one settlement")

    revised_outcome_input = deepcopy(observations[0])
    revised_outcome_input["module_outcome"]["outcome_status"] = "reconciled"
    del revised_outcome_input["utility_attribution"]
    revised_outcome = build_reward_memory_dogfood_receipt(revised_outcome_input)
    assert revised_outcome["receipt_id"] != dogfood[0]["receipt_id"]
    try:
        build_reward_memory_dogfood_batch(
            [dogfood[0], revised_outcome],
            [],
            evaluation=run_reward_memory_evaluation(),
        )
    except ValueError as exc:
        assert "double-count an application settlement" in str(exc), exc
    else:
        raise AssertionError("one application settlement was counted twice")

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
    assert packet["schema_version"] == REWARD_MEMORY_DOGFOOD_BATCH_SCHEMA_VERSION
    assert packet["status"] == "ready_for_bounded_issue_fix_pilot", packet
    assert packet["metrics"]["applied_count"] == 1, packet
    assert packet["metrics"]["not_applied_count"] == 1, packet
    assert packet["metrics"]["refuted_count"] == 1, packet
    assert packet["metrics"]["utility_observation_count"] == 1, packet
    assert packet["metrics"]["utility_unknown_count"] == 1, packet
    assert packet["metrics"]["utility_rejected_count"] == 1, packet
    assert packet["metrics"]["utility_not_requested_count"] == 1, packet
    assert packet["metrics"]["loopx_domain_count"] == 2, packet
    assert packet["metrics"]["intervention_count"] == 1, packet
    assert packet["receipts"][0]["application"]["disposition"] == "applied"
    assert packet["receipts"][0]["module_outcome"]["outcome_status"] == "completed"
    assert packet["receipts"][0]["utility"]["observation"]["utility_label"] == "unknown"
    assert packet["boundaries"]["production_rollout_allowed"] is False, packet
    assert packet["boundaries"]["operator_write_performed"] is False, packet

    held = build_reward_memory_dogfood_batch(
        dogfood[:1],
        [edited["receipt"]],
        evaluation=run_reward_memory_evaluation(),
    )
    assert held["status"] == "hold", held
    assert "two_loopx_domains_required" in held["reason_codes"], held
    assert "application_disposition_missing:not_applied" in held["reason_codes"], held
    assert "application_disposition_missing:refuted" in held["reason_codes"], held
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
            env={**os.environ, "LOOPX_PYTHON": sys.executable},
        )
        cli_packet = json.loads(completed.stdout)
        assert cli_packet["status"] == "ready_for_bounded_issue_fix_pilot"
        assert (
            cli_packet["schema_version"] == REWARD_MEMORY_DOGFOOD_BATCH_SCHEMA_VERSION
        )
        assert cli_packet["metrics"]["utility_unknown_count"] == 1

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
            env={**os.environ, "LOOPX_PYTHON": sys.executable},
        )
        control_packet = json.loads(completed.stdout)
        assert control_packet["status"] == "control_ready"
    print("reward-memory-dogfood-smoke: ok")


if __name__ == "__main__":
    main()
