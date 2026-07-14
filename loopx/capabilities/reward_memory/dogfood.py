from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from ...control_plane.runtime.public_safety import public_safe_compact_text
from .application import REWARD_MEMORY_APPLICATION_RECEIPT_SCHEMA_VERSION
from .candidate_review import (
    REWARD_MEMORY_REVIEW_SCHEMA_VERSION,
    review_reward_memory_candidate,
)
from .evaluation import REWARD_MEMORY_EVALUATION_SCHEMA_VERSION
from .registry import normalize_reward_memory_corpus


REWARD_MEMORY_DOGFOOD_RECEIPT_SCHEMA_VERSION = "reward_memory_dogfood_receipt_v0"
REWARD_MEMORY_DOGFOOD_BATCH_SCHEMA_VERSION = "reward_memory_dogfood_batch_v0"
REWARD_MEMORY_OPERATOR_CONTROL_SCHEMA_VERSION = "reward_memory_operator_control_v0"

DOGFOOD_OUTCOMES = {"hit", "miss", "refute"}
DOMAIN_FAMILIES = {"issue_fix", "loopx"}
OPERATOR_ACTIONS = {"edit", "retire"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,199}$")
MAX_RECEIPTS = 24
MAX_OPERATOR_CONTROLS = 8


def _token(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not TOKEN_RE.fullmatch(result):
        raise ValueError(f"{label} must be a compact public-safe token")
    return result


def _compact(value: object, label: str, *, limit: int = 500) -> str:
    result = public_safe_compact_text(value, limit=limit)
    if not result:
        raise ValueError(f"{label} must be compact and public-safe")
    return result


def _boolean(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _counter(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


def _digest(payload: Mapping[str, Any], *, prefix: str) -> str:
    value = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:20]
    return f"{prefix}:{value}"


def _dogfood_outcome(application_outcome: object) -> str:
    outcome = str(application_outcome or "").strip()
    if outcome == "applied":
        return "hit"
    if outcome == "refuted":
        return "refute"
    if outcome in {
        "ignored",
        "failed",
        "not_available",
        "available_not_applied",
    }:
        return "miss"
    raise ValueError("application receipt outcome is invalid")


def build_reward_memory_dogfood_receipt(
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one real module outcome to an existing compact application receipt."""

    if _boolean(observation, "raw_content_captured"):
        raise ValueError("dogfood observations must not contain raw content")
    family = str(observation.get("domain_family") or "").strip()
    if family not in DOMAIN_FAMILIES:
        raise ValueError("domain_family must be issue_fix or loopx")
    domain_id = _token(observation.get("domain_id"), "domain_id")
    if family == "issue_fix" and not domain_id.startswith("issue_fix."):
        raise ValueError("issue_fix domain_id must use the issue_fix namespace")
    if family == "loopx" and not domain_id.startswith("loopx."):
        raise ValueError("loopx domain_id must use the loopx namespace")

    application = observation.get("application_receipt")
    if not isinstance(application, Mapping):
        raise ValueError("application_receipt must be an object")
    if (
        application.get("schema_version")
        != REWARD_MEMORY_APPLICATION_RECEIPT_SCHEMA_VERSION
    ):
        raise ValueError("application_receipt must use the Stage-3 receipt schema")
    application_id = _token(application.get("application_id"), "application_id")
    artifact_ref = _token(application.get("artifact_ref"), "artifact_ref")
    surface_id = _token(application.get("surface_id"), "surface_id")
    outcome = _dogfood_outcome(application.get("outcome"))
    readback_verified = _boolean(application, "result_readback_verified")
    current_verified = _boolean(application, "current_artifact_verified")
    if _boolean(application, "grants_new_action_authority"):
        raise ValueError("application receipt cannot grant action authority")
    if _boolean(application, "raw_content_captured"):
        raise ValueError("application receipt cannot contain raw content")
    if _boolean(application, "external_writes_performed"):
        raise ValueError("application receipt cannot perform external writes")
    if outcome in {"hit", "refute"} and not readback_verified:
        raise ValueError("hit or refute requires exact provider result readback")
    if outcome in {"hit", "refute"} and not current_verified:
        raise ValueError("hit or refute requires current-artifact verification")
    memory_ref_digests = application.get("memory_ref_digests")
    if not isinstance(memory_ref_digests, Sequence) or isinstance(
        memory_ref_digests, (str, bytes)
    ):
        raise ValueError("memory_ref_digests must be a list")
    digests = sorted(
        {_token(value, "memory_ref_digest") for value in memory_ref_digests}
    )
    if len(digests) != len(memory_ref_digests):
        raise ValueError("memory_ref_digests must not contain duplicates")
    if outcome in {"hit", "refute"} and not digests:
        raise ValueError("hit or refute requires attributed memory references")

    module_outcome = observation.get("module_outcome")
    if not isinstance(module_outcome, Mapping):
        raise ValueError("module_outcome must be an object")
    if (
        _token(module_outcome.get("artifact_ref"), "module_outcome.artifact_ref")
        != artifact_ref
    ):
        raise ValueError("module outcome and application artifact_ref must match")
    outcome_verified = _boolean(module_outcome, "outcome_verified")
    if not outcome_verified:
        raise ValueError("dogfood requires a verified real module outcome")
    outcome_summary = _compact(
        module_outcome.get("summary"), "module_outcome.summary", limit=360
    )

    cost = observation.get("cost")
    if not isinstance(cost, Mapping):
        raise ValueError("cost must be an object")
    compact_cost = {
        key: _counter(cost, key)
        for key in ("latency_ms", "model_tokens", "provider_call_count")
    }
    intervention = observation.get("intervention")
    if not isinstance(intervention, Mapping):
        raise ValueError("intervention must be an object")
    intervention_count = _counter(intervention, "count")
    intervention_summary = None
    if intervention_count:
        intervention_summary = _compact(
            intervention.get("summary"), "intervention.summary", limit=240
        )

    bot_feedback = observation.get("bot_feedback") or {
        "captured": False,
        "summary": None,
    }
    if not isinstance(bot_feedback, Mapping):
        raise ValueError("bot_feedback must be an object")
    feedback_captured = _boolean(bot_feedback, "captured")
    feedback_summary = None
    if feedback_captured:
        feedback_summary = _compact(
            bot_feedback.get("summary"), "bot_feedback.summary", limit=240
        )

    identity = {
        "domain_family": family,
        "domain_id": domain_id,
        "application_id": application_id,
        "artifact_ref": artifact_ref,
        "surface_id": surface_id,
        "outcome": outcome,
    }
    return {
        "ok": True,
        "schema_version": REWARD_MEMORY_DOGFOOD_RECEIPT_SCHEMA_VERSION,
        "receipt_id": _digest(identity, prefix="dogfood"),
        "domain_family": family,
        "domain_id": domain_id,
        "application_id": application_id,
        "artifact_ref": artifact_ref,
        "surface_id": surface_id,
        "outcome": outcome,
        "module_outcome": {
            "verified": True,
            "summary": outcome_summary,
        },
        "memory_ref_digests": digests,
        "verification": {
            "result_readback_verified": readback_verified,
            "current_artifact_verified": current_verified,
        },
        "cost": compact_cost,
        "intervention": {
            "count": intervention_count,
            "summary": intervention_summary,
        },
        "bot_feedback": {
            "captured": feedback_captured,
            "summary": feedback_summary,
        },
        "grants_new_action_authority": False,
        "raw_content_captured": False,
        "external_writes_performed": False,
    }


def _scope_matches(record: Mapping[str, Any], corpus: Mapping[str, Any]) -> bool:
    scope = record.get("scope")
    expected = corpus["scope"]
    if not isinstance(scope, Mapping):
        return False
    base_matches = (
        scope.get("workspace_ref") == expected["workspace_ref"]
        and scope.get("project_ref") == expected["project_ref"]
        and set(scope.get("surface_ids") or []).issubset(set(expected["surface_ids"]))
    )
    if not base_matches:
        return False
    if corpus["freshness"]["mode"] == "revision_bound":
        return scope.get("revision_ref") == corpus["freshness"]["source_revision"]
    return True


def build_reward_memory_operator_control(
    reviewed_record: Mapping[str, Any],
    corpus: Mapping[str, Any],
    *,
    action: str,
    operator_checkpoint: Mapping[str, Any],
    control_ref: str,
    reasoning_summary: str,
    edited_content_summary: str | None = None,
) -> dict[str, Any]:
    """Prepare an authorized edit or retirement without performing a provider write."""

    normalized = normalize_reward_memory_corpus(corpus)
    if action not in OPERATOR_ACTIONS:
        raise ValueError("operator action must be edit or retire")
    if normalized["lifecycle"]["state"] != "active":
        raise ValueError("operator control corpus must be active")
    if normalized["write_authority"] == "read_only":
        raise ValueError("operator control corpus is read-only")
    if reviewed_record.get("schema_version") != REWARD_MEMORY_REVIEW_SCHEMA_VERSION:
        raise ValueError("operator control requires an active reviewed record")
    if (
        reviewed_record.get("status") != "active"
        or reviewed_record.get("guard_passed") is not True
    ):
        raise ValueError("operator control requires a guard-passed active record")
    record = reviewed_record.get("record")
    if not isinstance(record, Mapping):
        raise ValueError("reviewed record is incomplete")
    lifecycle = record.get("lifecycle")
    if not isinstance(lifecycle, Mapping) or lifecycle.get("state") != "active":
        raise ValueError("operator control target must be active")
    if record.get("target_class") != normalized["class_id"]:
        raise ValueError("operator control corpus class does not match")
    if not _scope_matches(record, normalized):
        raise ValueError("operator control corpus scope does not match")
    if not isinstance(operator_checkpoint, Mapping):
        raise ValueError("operator_checkpoint must be an object")
    if not _boolean(operator_checkpoint, "verified"):
        raise ValueError("operator authority checkpoint must be verified")
    operator_ref = _token(
        operator_checkpoint.get("operator_ref"), "operator_checkpoint.operator_ref"
    )
    authority_ref = _token(
        operator_checkpoint.get("authority_ref"), "operator_checkpoint.authority_ref"
    )
    source_ref = _token(
        operator_checkpoint.get("source_ref"), "operator_checkpoint.source_ref"
    )
    checkpoint_corpus_id = _token(
        operator_checkpoint.get("corpus_id"), "operator_checkpoint.corpus_id"
    )
    checkpoint_project_ref = _token(
        operator_checkpoint.get("project_ref"), "operator_checkpoint.project_ref"
    )
    checkpoint_action = str(operator_checkpoint.get("action") or "").strip()
    if checkpoint_corpus_id != normalized["corpus_id"]:
        raise ValueError("operator authority corpus does not match")
    if checkpoint_project_ref != normalized["scope"]["project_ref"]:
        raise ValueError("operator authority project does not match")
    if checkpoint_action != action:
        raise ValueError("operator authority action does not match")
    expected_authority = (
        normalized["owner_ref"]
        if action == "edit"
        else normalized["maintenance"]["retirement_authority"]
    )
    if authority_ref != expected_authority:
        raise ValueError("operator authority does not match the corpus declaration")

    target = deepcopy(dict(reviewed_record))
    if action == "edit":
        target_record = target["record"]
        old_ref = _token(target_record.get("candidate_ref"), "candidate_ref")
        target_record["lifecycle"] = {
            "state": "candidate",
            "supersedes_refs": [old_ref],
        }
    review = {
        "decision": action,
        "reviewer_ref": operator_ref,
        "review_ref": _token(control_ref, "control_ref"),
        "reasoning_summary": _compact(
            reasoning_summary, "reasoning_summary", limit=360
        ),
    }
    if action == "edit":
        review["edited_content_summary"] = _compact(
            edited_content_summary, "edited_content_summary", limit=500
        )
    decision = review_reward_memory_candidate(target, review)
    old_candidate_ref = _token(record.get("candidate_ref"), "candidate_ref")
    new_candidate_ref = _token(
        decision["record"].get("candidate_ref"), "decision.candidate_ref"
    )
    receipt = {
        "schema_version": REWARD_MEMORY_OPERATOR_CONTROL_SCHEMA_VERSION,
        "control_ref": review["review_ref"],
        "action": action,
        "effective_action": decision["effective_decision"],
        "operator_ref": operator_ref,
        "authority_ref": authority_ref,
        "authority_source_ref": source_ref,
        "authority_verified": True,
        "corpus_id": normalized["corpus_id"],
        "prior_candidate_ref_digest": hashlib.sha256(
            old_candidate_ref.encode("utf-8")
        ).hexdigest()[:16],
        "result_candidate_ref_digest": hashlib.sha256(
            new_candidate_ref.encode("utf-8")
        ).hexdigest()[:16],
        "result_state": decision["record"]["lifecycle"]["state"],
        "reasoning_summary": review["reasoning_summary"],
        "provider_write_performed": False,
        "readback_verified": False,
        "next_step": (
            "review_replacement_then_owner_write_and_exact_readback"
            if action == "edit"
            else "owner_write_retirement_then_exact_readback"
        ),
        "grants_new_action_authority": False,
        "raw_content_captured": False,
        "external_writes_performed": False,
    }
    return {
        "ok": True,
        "schema_version": REWARD_MEMORY_OPERATOR_CONTROL_SCHEMA_VERSION,
        "status": "control_ready",
        "decision": decision,
        "receipt": receipt,
    }


def _validate_control_receipt(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("operator control receipt must be an object")
    if raw.get("schema_version") != REWARD_MEMORY_OPERATOR_CONTROL_SCHEMA_VERSION:
        raise ValueError("operator control receipt schema is invalid")
    action = str(raw.get("action") or "").strip()
    if action not in OPERATOR_ACTIONS:
        raise ValueError("operator control receipt action is invalid")
    if _boolean(raw, "authority_verified") is not True:
        raise ValueError("operator control authority must be verified")
    if _boolean(raw, "provider_write_performed"):
        raise ValueError("Stage-5 control receipt must precede provider write")
    if str(raw.get("effective_action") or "").strip() != action:
        raise ValueError("operator control effective action is invalid")
    expected_state = "candidate" if action == "edit" else "retired"
    if str(raw.get("result_state") or "").strip() != expected_state:
        raise ValueError("operator control result state is invalid")
    for key in (
        "control_ref",
        "operator_ref",
        "authority_ref",
        "authority_source_ref",
        "corpus_id",
        "prior_candidate_ref_digest",
        "result_candidate_ref_digest",
    ):
        _token(raw.get(key), key)
    if _boolean(raw, "grants_new_action_authority"):
        raise ValueError("operator control cannot grant action authority")
    if _boolean(raw, "raw_content_captured"):
        raise ValueError("operator control cannot contain raw content")
    if _boolean(raw, "external_writes_performed"):
        raise ValueError("operator control cannot perform external writes")
    return dict(raw)


def _validate_dogfood_receipt(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("dogfood receipt must be an object")
    if raw.get("schema_version") != REWARD_MEMORY_DOGFOOD_RECEIPT_SCHEMA_VERSION:
        raise ValueError("dogfood receipt schema is invalid")
    family = str(raw.get("domain_family") or "").strip()
    domain_id = _token(raw.get("domain_id"), "domain_id")
    if family not in DOMAIN_FAMILIES or not domain_id.startswith(f"{family}."):
        raise ValueError("dogfood receipt domain is invalid")
    outcome = str(raw.get("outcome") or "").strip()
    if outcome not in DOGFOOD_OUTCOMES:
        raise ValueError("dogfood receipt outcome is invalid")
    for key in ("receipt_id", "application_id", "artifact_ref", "surface_id"):
        _token(raw.get(key), key)
    verification = raw.get("verification")
    if not isinstance(verification, Mapping):
        raise ValueError("dogfood receipt verification is invalid")
    readback = _boolean(verification, "result_readback_verified")
    current = _boolean(verification, "current_artifact_verified")
    if outcome in {"hit", "refute"} and not (readback and current):
        raise ValueError("hit or refute receipt is not exactly verified")
    module_outcome = raw.get("module_outcome")
    if not isinstance(module_outcome, Mapping) or not _boolean(
        module_outcome, "verified"
    ):
        raise ValueError("dogfood module outcome is not verified")
    _compact(module_outcome.get("summary"), "module_outcome.summary", limit=360)
    cost = raw.get("cost")
    if not isinstance(cost, Mapping):
        raise ValueError("dogfood receipt cost is invalid")
    for key in ("latency_ms", "model_tokens", "provider_call_count"):
        _counter(cost, key)
    intervention = raw.get("intervention")
    if not isinstance(intervention, Mapping):
        raise ValueError("dogfood receipt intervention is invalid")
    _counter(intervention, "count")
    feedback = raw.get("bot_feedback")
    if not isinstance(feedback, Mapping):
        raise ValueError("dogfood receipt bot_feedback is invalid")
    _boolean(feedback, "captured")
    if _boolean(raw, "grants_new_action_authority"):
        raise ValueError("dogfood receipt cannot grant action authority")
    if _boolean(raw, "raw_content_captured"):
        raise ValueError("dogfood receipt cannot contain raw content")
    if _boolean(raw, "external_writes_performed"):
        raise ValueError("dogfood receipt cannot perform external writes")
    return dict(raw)


def build_reward_memory_dogfood_batch(
    receipts: Sequence[Mapping[str, Any]],
    operator_controls: Sequence[Mapping[str, Any]],
    *,
    evaluation: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate bounded Stage-5 evidence without claiming production uplift."""

    if not isinstance(evaluation, Mapping):
        raise ValueError("evaluation must be a Stage-4 evaluation packet")
    if len(receipts) > MAX_RECEIPTS:
        raise ValueError(f"dogfood batch accepts at most {MAX_RECEIPTS} receipts")
    if len(operator_controls) > MAX_OPERATOR_CONTROLS:
        raise ValueError(
            f"dogfood batch accepts at most {MAX_OPERATOR_CONTROLS} controls"
        )
    normalized_receipts = [_validate_dogfood_receipt(item) for item in receipts]
    controls = [_validate_control_receipt(item) for item in operator_controls]
    receipt_ids = [item["receipt_id"] for item in normalized_receipts]
    if len(receipt_ids) != len(set(receipt_ids)):
        raise ValueError("dogfood batch must not double-count a receipt")
    control_refs = [item["control_ref"] for item in controls]
    if len(control_refs) != len(set(control_refs)):
        raise ValueError("dogfood batch must not double-count an operator control")

    gate_ready = (
        evaluation.get("schema_version") == REWARD_MEMORY_EVALUATION_SCHEMA_VERSION
        and evaluation.get("status") == "passed"
        and isinstance(evaluation.get("release_gate"), Mapping)
        and evaluation["release_gate"].get("status") == "ready_for_bounded_dogfood"
    )
    issue_fix_count = sum(
        item["domain_family"] == "issue_fix" for item in normalized_receipts
    )
    loopx_domains = sorted(
        {
            item["domain_id"]
            for item in normalized_receipts
            if item["domain_family"] == "loopx"
        }
    )
    outcomes = {item["outcome"] for item in normalized_receipts}
    actions = {item["action"] for item in controls}
    reason_codes: list[str] = []
    if not gate_ready:
        reason_codes.append("stage4_release_gate_not_ready")
    if issue_fix_count < 1:
        reason_codes.append("issue_fix_outcome_missing")
    if len(loopx_domains) < 2:
        reason_codes.append("two_loopx_domains_required")
    for outcome in sorted(DOGFOOD_OUTCOMES - outcomes):
        reason_codes.append(f"outcome_missing:{outcome}")
    for action in sorted(OPERATOR_ACTIONS - actions):
        reason_codes.append(f"operator_control_missing:{action}")

    totals = {
        "receipt_count": len(normalized_receipts),
        "issue_fix_receipt_count": issue_fix_count,
        "loopx_domain_count": len(loopx_domains),
        "hit_count": sum(item["outcome"] == "hit" for item in normalized_receipts),
        "miss_count": sum(item["outcome"] == "miss" for item in normalized_receipts),
        "refute_count": sum(
            item["outcome"] == "refute" for item in normalized_receipts
        ),
        "latency_ms": sum(item["cost"]["latency_ms"] for item in normalized_receipts),
        "model_tokens": sum(
            item["cost"]["model_tokens"] for item in normalized_receipts
        ),
        "provider_call_count": sum(
            item["cost"]["provider_call_count"] for item in normalized_receipts
        ),
        "intervention_count": sum(
            item["intervention"]["count"] for item in normalized_receipts
        ),
        "bot_feedback_count": sum(
            item["bot_feedback"]["captured"] for item in normalized_receipts
        ),
    }
    ready = not reason_codes
    compact_receipts = [
        {
            key: item[key]
            for key in (
                "receipt_id",
                "domain_family",
                "domain_id",
                "artifact_ref",
                "surface_id",
                "outcome",
                "verification",
                "cost",
                "intervention",
                "bot_feedback",
            )
        }
        for item in normalized_receipts
    ]
    return {
        "ok": ready,
        "schema_version": REWARD_MEMORY_DOGFOOD_BATCH_SCHEMA_VERSION,
        "status": "ready_for_bounded_issue_fix_pilot" if ready else "hold",
        "reason_codes": reason_codes,
        "stage4_gate_verified": gate_ready,
        "loopx_domains": loopx_domains,
        "outcomes": sorted(outcomes),
        "operator_controls": sorted(actions),
        "metrics": totals,
        "receipts": compact_receipts,
        "boundaries": {
            "semantic_uplift_claim_allowed": False,
            "production_rollout_allowed": False,
            "automatic_recall_enabled": False,
            "new_store_provider_or_scheduler_added": False,
            "operator_write_performed": False,
            "raw_content_captured": False,
        },
    }
