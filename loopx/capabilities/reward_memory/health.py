from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .registry import (
    SURFACE_RE,
    TOKEN_RE,
    build_reward_memory_corpus_registry_packet,
    normalize_reward_memory_corpus,
)


REWARD_MEMORY_CORPUS_HEALTH_SCHEMA_VERSION = "reward_memory_corpus_health_v0"


def _token(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not TOKEN_RE.fullmatch(result):
        raise ValueError(f"{label} must be a compact public-safe token")
    return result


def _optional_token(value: object, label: str) -> str | None:
    if value in (None, ""):
        return None
    return _token(value, label)


def _boolean(mapping: Mapping[str, Any], key: str) -> bool:
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def build_reward_memory_corpus_health_packet(
    corpus: Mapping[str, Any],
    observation: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify one corpus without collapsing inventory, retrieval, and use states."""

    item = normalize_reward_memory_corpus(corpus)
    requested_project = _token(
        observation.get("requested_project_ref"), "requested_project_ref"
    )
    requested_surface = str(observation.get("requested_surface") or "").strip()
    if not SURFACE_RE.fullmatch(requested_surface):
        raise ValueError("requested_surface must be a module-qualified token")
    current_revision = _optional_token(
        observation.get("current_source_revision"), "current_source_revision"
    )
    provider_available = _boolean(observation, "provider_available")
    corpus_present = _boolean(observation, "corpus_present")
    index_present = _boolean(observation, "index_present")
    retrieval_succeeded = _boolean(observation, "retrieval_query_succeeded")
    readback_verified = _boolean(observation, "result_readback_verified")
    application_receipt = _boolean(observation, "memory_applied_with_receipt")
    freshness_window_satisfied = _boolean(observation, "freshness_window_satisfied")
    record_count = observation.get("record_count")
    if (
        isinstance(record_count, bool)
        or not isinstance(record_count, int)
        or record_count < 0
    ):
        raise ValueError("record_count must be a non-negative integer")
    if not corpus_present and record_count:
        raise ValueError("record_count must be zero when corpus_present is false")
    if retrieval_succeeded and (not provider_available or not corpus_present):
        raise ValueError("retrieval success requires an available present corpus")
    if readback_verified and not retrieval_succeeded:
        raise ValueError("readback verification requires retrieval success")
    if application_receipt and not readback_verified:
        raise ValueError("application receipt requires verified readback")

    scope = item["scope"]
    freshness = item["freshness"]
    lifecycle = item["lifecycle"]
    revision_matches = (
        freshness["source_revision"] is None
        or current_revision == freshness["source_revision"]
    )
    reasons: list[str] = []
    if requested_project != scope["project_ref"]:
        state = "wrong_project"
        reasons.append("requested_project_outside_corpus_scope")
    elif requested_surface not in scope["surface_ids"]:
        state = "wrong_surface"
        reasons.append("requested_surface_outside_corpus_scope")
    elif not provider_available:
        state = "unavailable"
        reasons.append("provider_unavailable")
    elif not corpus_present:
        state = "unavailable"
        reasons.append("corpus_missing")
    elif record_count == 0:
        state = "empty"
        reasons.append("corpus_present_without_records")
    elif lifecycle["state"] != "active":
        state = "stale"
        reasons.append(f"lifecycle_{lifecycle['state']}")
    elif not revision_matches:
        state = "stale"
        reasons.append("source_revision_mismatch_or_unverified")
    elif not freshness_window_satisfied:
        state = "stale"
        reasons.append("freshness_window_unsatisfied")
    elif item["retrieval"]["index_required"] and not index_present:
        state = "index_unavailable"
        reasons.append("required_index_missing")
    elif not retrieval_succeeded:
        state = "retrieval_failed"
        reasons.append("retrieval_query_failed_or_not_run")
    elif item["retrieval"]["readback_required"] and not readback_verified:
        state = "readback_unverified"
        reasons.append("retrieval_result_not_read_back")
    elif application_receipt:
        state = "applied_verified"
        reasons.append("verified_result_has_application_receipt")
    else:
        state = "retrieval_verified"
        reasons.append("verified_result_not_yet_applied")

    may_apply = state in {"retrieval_verified", "applied_verified"}
    return {
        "ok": True,
        "schema_version": REWARD_MEMORY_CORPUS_HEALTH_SCHEMA_VERSION,
        "corpus_id": item["corpus_id"],
        "class_id": item["class_id"],
        "health_state": state,
        "reason_codes": reasons,
        "scope_check": {
            "project_matches": requested_project == scope["project_ref"],
            "surface_matches": requested_surface in scope["surface_ids"],
        },
        "freshness_check": {
            "lifecycle_state": lifecycle["state"],
            "source_revision_matches": revision_matches,
            "freshness_window_satisfied": freshness_window_satisfied,
        },
        "pipeline": {
            "provider_available": provider_available,
            "corpus_present": corpus_present,
            "record_count": record_count,
            "index_required": item["retrieval"]["index_required"],
            "index_present": index_present,
            "retrieval_query_succeeded": retrieval_succeeded,
            "result_readback_verified": readback_verified,
            "memory_applied_with_receipt": application_receipt,
        },
        "may_apply_memory": may_apply,
        "memory_patch_authority": False,
        "external_write_authorized": False,
        "raw_memory_captured": False,
    }


def reward_memory_health_case(case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return one public fixture for CLI and contract regression coverage."""

    valid_cases = {
        "unavailable",
        "empty",
        "stale",
        "wrong-project",
        "wrong-surface",
        "index-unavailable",
        "retrieval-failed",
        "readback-unverified",
        "retrieval-verified",
        "applied-verified",
    }
    if case not in valid_cases:
        raise ValueError("unknown reward-memory health case")
    registry = build_reward_memory_corpus_registry_packet()
    corpus = next(
        item
        for item in registry["corpora"]
        if item["corpus_id"] == "distilled_experiences"
    )
    observation: dict[str, Any] = {
        "requested_project_ref": "project:exact",
        "requested_surface": "issue_fix.routing",
        "current_source_revision": "revision:observed",
        "provider_available": True,
        "corpus_present": True,
        "record_count": 1,
        "index_present": True,
        "retrieval_query_succeeded": True,
        "result_readback_verified": True,
        "memory_applied_with_receipt": False,
        "freshness_window_satisfied": True,
    }
    if case == "unavailable":
        observation |= {
            "provider_available": False,
            "corpus_present": False,
            "record_count": 0,
            "index_present": False,
            "retrieval_query_succeeded": False,
            "result_readback_verified": False,
        }
    elif case == "empty":
        observation["record_count"] = 0
    elif case == "stale":
        observation["current_source_revision"] = "revision:newer"
    elif case == "wrong-project":
        observation["requested_project_ref"] = "project:other"
    elif case == "wrong-surface":
        observation["requested_surface"] = "content_ops.draft"
    elif case == "index-unavailable":
        observation["index_present"] = False
        observation["retrieval_query_succeeded"] = False
        observation["result_readback_verified"] = False
    elif case == "retrieval-failed":
        observation["retrieval_query_succeeded"] = False
        observation["result_readback_verified"] = False
    elif case == "readback-unverified":
        observation["result_readback_verified"] = False
    elif case == "applied-verified":
        observation["memory_applied_with_receipt"] = True
    return corpus, observation
