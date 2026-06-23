from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any


CONTENT_OPS_SURFACE_SCHEMA_VERSION = "content_ops_surface_v0"
CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION = "content_ops_surface_projection_v0"

SOURCE_ITEM_SCHEMA_VERSION = "source_item_v0"
ANGLE_CANDIDATE_SCHEMA_VERSION = "angle_candidate_v0"
DRAFT_ITEM_SCHEMA_VERSION = "draft_item_v0"
FEEDBACK_SIGNAL_SCHEMA_VERSION = "feedback_signal_v0"
PUBLISH_GATE_SCHEMA_VERSION = "publish_gate_v0"
MATERIAL_MEMORY_SCHEMA_VERSION = "material_memory_v0"
CONNECTOR_TRIAL_SCHEMA_VERSION = "connector_trial_v0"
CONTENT_OPS_VALIDATION_SCHEMA_VERSION = "content_ops_surface_validation_v0"

RAW_MATERIAL_KEY_HINTS = (
    "body",
    "chat",
    "credential",
    "dm",
    "local_path",
    "log",
    "message",
    "raw",
    "secret",
    "token",
    "transcript",
)

ALLOWED_SOURCE_STATUSES = {
    "public",
    "private_needs_review",
    "synthetic_public_safe",
    "unpublished",
    "forbidden_for_public_surface",
}
ALLOWED_FRESHNESS = {"fresh", "stale", "unknown"}
ALLOWED_USE_POLICIES = {
    "summarize_and_transform",
    "metadata_only",
    "do_not_quote",
    "forbidden",
}
ALLOWED_ANGLE_DECISIONS = {"draft", "reject", "hold", "needs_review"}
ALLOWED_DRAFT_STATES = {"outline", "draft", "rewrite", "blocked", "ready_for_review"}
ALLOWED_FEEDBACK_EFFECTS = {
    "preference_hint",
    "source_boundary_correction",
    "rewrite_todo",
    "publish_decision",
}
ALLOWED_PUBLISH_GATE_STATUSES = {
    "blocked_until_user_approval",
    "approved",
    "denied",
    "needs_revision",
}
ALLOWED_CONNECTOR_TRIAL_STATES = {
    "candidate",
    "ready_for_metadata_trial",
    "needs_owner_gate",
    "blocked",
}
ALLOWED_CONNECTOR_ACCESS_MODES = {
    "public_metadata_only",
    "private_metadata_only",
    "synthetic_fixture_only",
}


def _as_mappings(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if not values:
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _text(value: Any, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _ids(items: Sequence[Mapping[str, Any]], key: str) -> set[str]:
    return {
        str(item.get(key))
        for item in items
        if item.get(key) is not None and str(item.get(key)).strip()
    }


def _counter(values: Sequence[Any]) -> dict[str, int]:
    return dict(sorted(Counter(str(value) for value in values if value).items()))


def _raw_material_key_names(*groups: Sequence[Mapping[str, Any]]) -> list[str]:
    names: set[str] = set()
    for group in groups:
        for item in group:
            for key in item:
                lowered = str(key).lower()
                if any(hint in lowered for hint in RAW_MATERIAL_KEY_HINTS):
                    names.add(str(key))
    return sorted(names)


def build_content_ops_surface_fixture(
    *, generated_at: str | None = "2026-06-23T00:00:00Z"
) -> dict[str, Any]:
    """Build a synthetic public-safe content-ops state surface fixture.

    This fixture demonstrates the shape of a creator/self-media loop without
    copying raw platform posts, chat messages, draft bodies, credentials, or
    local paths into LoopX state.
    """

    source_items = [
        {
            "schema_version": SOURCE_ITEM_SCHEMA_VERSION,
            "source_item_id": "source_demo_public_feed_001",
            "source_kind": "synthetic_demo_feed",
            "source_status": "synthetic_public_safe",
            "freshness": "fresh",
            "terms_note": "synthetic demo only; no platform scraping claim",
            "allowed_use": "summarize_and_transform",
            "attribution": "LoopX synthetic creator-ops demo",
            "summary": (
                "A public-safe trend summary suggests creator operators need "
                "source-aware drafting queues."
            ),
        },
        {
            "schema_version": SOURCE_ITEM_SCHEMA_VERSION,
            "source_item_id": "source_demo_private_note_001",
            "source_kind": "synthetic_private_note",
            "source_status": "private_needs_review",
            "freshness": "fresh",
            "terms_note": "metadata-only placeholder for private material",
            "allowed_use": "metadata_only",
            "attribution": "operator-owned private source placeholder",
            "summary": "Private source is represented only as a compact review-needed signal.",
        },
    ]
    angle_candidates = [
        {
            "schema_version": ANGLE_CANDIDATE_SCHEMA_VERSION,
            "angle_id": "angle_source_aware_loop",
            "source_item_ids": ["source_demo_public_feed_001"],
            "audience": "maintainers evaluating creator-ops automation",
            "topic": "source-aware drafting loop",
            "novelty": "connects connector observations to explicit publish gates",
            "preference_fit": "high",
            "evidence_quality": "synthetic_demo",
            "decision": "draft",
        },
        {
            "schema_version": ANGLE_CANDIDATE_SCHEMA_VERSION,
            "angle_id": "angle_private_material_quote",
            "source_item_ids": ["source_demo_private_note_001"],
            "audience": "same",
            "topic": "private source quote",
            "novelty": "blocked by source boundary",
            "preference_fit": "unknown",
            "evidence_quality": "needs_owner_review",
            "decision": "reject",
            "rejection_reason": "private material cannot be quoted or promoted without review",
        },
    ]
    draft_items = [
        {
            "schema_version": DRAFT_ITEM_SCHEMA_VERSION,
            "draft_id": "draft_source_aware_loop_outline",
            "angle_id": "angle_source_aware_loop",
            "state": "outline",
            "source_map": [
                {
                    "source_item_id": "source_demo_public_feed_001",
                    "use": "summarized premise",
                }
            ],
            "preference_hints": [
                "explain value as quality and feedback, not raw publish count",
                "keep publish decision human-gated",
            ],
            "publish_gate_id": "publish_gate_source_aware_loop",
            "validation_surface": (
                "source map present; no raw private material; publish gate visible"
            ),
        }
    ]
    feedback_signals = [
        {
            "schema_version": FEEDBACK_SIGNAL_SCHEMA_VERSION,
            "feedback_id": "feedback_demo_style_001",
            "target_id": "draft_source_aware_loop_outline",
            "signal": "useful_but_less_salesy",
            "effect": "preference_hint",
            "writes_todo": False,
            "summary": "Favor operator-quality framing over content volume claims.",
        },
        {
            "schema_version": FEEDBACK_SIGNAL_SCHEMA_VERSION,
            "feedback_id": "feedback_private_source_boundary_001",
            "target_id": "source_demo_private_note_001",
            "signal": "do_not_use_source_body",
            "effect": "source_boundary_correction",
            "writes_todo": False,
            "summary": "Private source stays metadata-only until an explicit review approves use.",
        },
    ]
    publish_gates = [
        {
            "schema_version": PUBLISH_GATE_SCHEMA_VERSION,
            "gate_id": "publish_gate_source_aware_loop",
            "draft_id": "draft_source_aware_loop_outline",
            "status": "blocked_until_user_approval",
            "approval_required": True,
            "autopublish_allowed": False,
            "required_review": [
                "source attribution",
                "tone/style",
                "platform policy",
                "final publish destination",
            ],
        }
    ]
    material_memory = [
        {
            "schema_version": MATERIAL_MEMORY_SCHEMA_VERSION,
            "memory_id": "memory_source_aware_loop",
            "source_item_id": "source_demo_public_feed_001",
            "attribution": "LoopX synthetic creator-ops demo",
            "reuse_boundary": "demo_only",
            "rejected_angles": ["angle_private_material_quote"],
            "preference_hints": ["quality and feedback beat raw article count"],
        }
    ]
    connector_trials = [
        {
            "schema_version": CONNECTOR_TRIAL_SCHEMA_VERSION,
            "trial_id": "trial_x_ego_lite_browser",
            "surface": "x_public_feed",
            "tool_hint": "ego-lite browser",
            "access_mode": "public_metadata_only",
            "source_status": "public",
            "freshness": "unknown",
            "allowed_use": "metadata_only",
            "trial_state": "ready_for_metadata_trial",
            "proposed_source_item_id": "source_x_public_signal_001",
            "terms_note": "public/terms-aware signal intake; no login, posting, or raw timeline capture in LoopX state",
            "promotion_target": "source_item_v0",
            "requires_user_gate": False,
            "external_write_allowed": False,
        },
        {
            "schema_version": CONNECTOR_TRIAL_SCHEMA_VERSION,
            "trial_id": "trial_wechat_chatlog_alpha",
            "surface": "wechat_private_archive",
            "tool_hint": "chatlog-alpha/chatview",
            "access_mode": "private_metadata_only",
            "source_status": "private_needs_review",
            "freshness": "unknown",
            "allowed_use": "metadata_only",
            "trial_state": "needs_owner_gate",
            "proposed_source_item_id": "source_wechat_metadata_signal_001",
            "terms_note": "private material intake stays metadata-only until owner review approves any use",
            "promotion_target": "source_item_v0",
            "requires_user_gate": True,
            "external_write_allowed": False,
        },
    ]
    return {
        "schema_version": CONTENT_OPS_SURFACE_SCHEMA_VERSION,
        "surface_id": "creator_ops_public_safe_demo",
        "generated_at": generated_at,
        "mode": "compact_state_surface",
        "source_items": source_items,
        "angle_candidates": angle_candidates,
        "draft_items": draft_items,
        "feedback_signals": feedback_signals,
        "publish_gates": publish_gates,
        "material_memory": material_memory,
        "connector_trials": connector_trials,
        "operator_states": [
            "waiting_for_source_review",
            "ready_to_draft",
            "waiting_for_feedback",
            "ready_for_publish_decision",
            "safe_side_work_available",
        ],
        "boundary": {
            "public_safe": True,
            "raw_private_material_recorded": False,
            "raw_platform_data_recorded": False,
            "credentials_recorded": False,
            "autopublish_allowed": False,
            "publish_requires_user_gate": True,
            "connector_bodies_are_source_of_truth": False,
        },
    }


def validate_content_ops_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    source_items = _as_mappings(surface.get("source_items"))  # type: ignore[arg-type]
    angle_candidates = _as_mappings(surface.get("angle_candidates"))  # type: ignore[arg-type]
    draft_items = _as_mappings(surface.get("draft_items"))  # type: ignore[arg-type]
    feedback_signals = _as_mappings(surface.get("feedback_signals"))  # type: ignore[arg-type]
    publish_gates = _as_mappings(surface.get("publish_gates"))  # type: ignore[arg-type]
    material_memory = _as_mappings(surface.get("material_memory"))  # type: ignore[arg-type]
    connector_trials = _as_mappings(surface.get("connector_trials"))  # type: ignore[arg-type]

    errors: list[str] = []
    source_ids = _ids(source_items, "source_item_id")
    angle_ids = _ids(angle_candidates, "angle_id")
    draft_ids = _ids(draft_items, "draft_id")
    gate_ids = _ids(publish_gates, "gate_id")

    if surface.get("schema_version") != CONTENT_OPS_SURFACE_SCHEMA_VERSION:
        errors.append("surface schema_version must be content_ops_surface_v0")
    if not source_items:
        errors.append("at least one source_item_v0 record is required")
    if not angle_candidates:
        errors.append("at least one angle_candidate_v0 record is required")
    if not draft_items:
        errors.append("at least one draft_item_v0 record is required")
    if not feedback_signals:
        errors.append("at least one feedback_signal_v0 record is required")
    if not publish_gates:
        errors.append("at least one publish_gate_v0 record is required")
    if not material_memory:
        errors.append("at least one material_memory_v0 record is required")
    if not connector_trials:
        errors.append("at least one connector_trial_v0 record is required")

    for item in source_items:
        if item.get("schema_version") != SOURCE_ITEM_SCHEMA_VERSION:
            errors.append(f"source item {item.get('source_item_id')} has wrong schema")
        if item.get("source_status") not in ALLOWED_SOURCE_STATUSES:
            errors.append(
                f"source item {item.get('source_item_id')} has invalid source_status"
            )
        if item.get("freshness") not in ALLOWED_FRESHNESS:
            errors.append(f"source item {item.get('source_item_id')} has invalid freshness")
        if item.get("allowed_use") not in ALLOWED_USE_POLICIES:
            errors.append(f"source item {item.get('source_item_id')} has invalid allowed_use")

    for item in angle_candidates:
        if item.get("schema_version") != ANGLE_CANDIDATE_SCHEMA_VERSION:
            errors.append(f"angle {item.get('angle_id')} has wrong schema")
        if item.get("decision") not in ALLOWED_ANGLE_DECISIONS:
            errors.append(f"angle {item.get('angle_id')} has invalid decision")
        for source_id in item.get("source_item_ids") or []:
            if str(source_id) not in source_ids:
                errors.append(
                    f"angle {item.get('angle_id')} references unknown source {source_id}"
                )

    for item in draft_items:
        if item.get("schema_version") != DRAFT_ITEM_SCHEMA_VERSION:
            errors.append(f"draft {item.get('draft_id')} has wrong schema")
        if item.get("state") not in ALLOWED_DRAFT_STATES:
            errors.append(f"draft {item.get('draft_id')} has invalid state")
        if str(item.get("angle_id")) not in angle_ids:
            errors.append(f"draft {item.get('draft_id')} references unknown angle")
        if str(item.get("publish_gate_id")) not in gate_ids:
            errors.append(f"draft {item.get('draft_id')} references unknown publish gate")
        source_map = item.get("source_map")
        if not isinstance(source_map, Sequence) or isinstance(source_map, (str, bytes)):
            errors.append(f"draft {item.get('draft_id')} must carry a source_map")
        else:
            for source_ref in source_map:
                if not isinstance(source_ref, Mapping):
                    errors.append(f"draft {item.get('draft_id')} has invalid source_map item")
                    continue
                source_id = str(source_ref.get("source_item_id") or "")
                if source_id not in source_ids:
                    errors.append(
                        f"draft {item.get('draft_id')} source_map references unknown source"
                    )

    for item in feedback_signals:
        if item.get("schema_version") != FEEDBACK_SIGNAL_SCHEMA_VERSION:
            errors.append(f"feedback {item.get('feedback_id')} has wrong schema")
        if item.get("effect") not in ALLOWED_FEEDBACK_EFFECTS:
            errors.append(f"feedback {item.get('feedback_id')} has invalid effect")
        target_id = str(item.get("target_id") or "")
        if (
            target_id not in draft_ids
            and target_id not in source_ids
            and target_id not in angle_ids
        ):
            errors.append(f"feedback {item.get('feedback_id')} references unknown target")

    for item in publish_gates:
        if item.get("schema_version") != PUBLISH_GATE_SCHEMA_VERSION:
            errors.append(f"publish gate {item.get('gate_id')} has wrong schema")
        if item.get("status") not in ALLOWED_PUBLISH_GATE_STATUSES:
            errors.append(f"publish gate {item.get('gate_id')} has invalid status")
        if item.get("autopublish_allowed") is not False:
            errors.append(
                f"publish gate {item.get('gate_id')} must set autopublish_allowed=false"
            )
        if item.get("approval_required") is not True:
            errors.append(f"publish gate {item.get('gate_id')} must require approval")

    for item in material_memory:
        if item.get("schema_version") != MATERIAL_MEMORY_SCHEMA_VERSION:
            errors.append(f"memory {item.get('memory_id')} has wrong schema")
        source_id = str(item.get("source_item_id") or "")
        if source_id not in source_ids:
            errors.append(f"memory {item.get('memory_id')} references unknown source")

    for item in connector_trials:
        if item.get("schema_version") != CONNECTOR_TRIAL_SCHEMA_VERSION:
            errors.append(f"connector trial {item.get('trial_id')} has wrong schema")
        if item.get("source_status") not in ALLOWED_SOURCE_STATUSES:
            errors.append(
                f"connector trial {item.get('trial_id')} has invalid source_status"
            )
        if item.get("freshness") not in ALLOWED_FRESHNESS:
            errors.append(
                f"connector trial {item.get('trial_id')} has invalid freshness"
            )
        if item.get("allowed_use") not in ALLOWED_USE_POLICIES:
            errors.append(
                f"connector trial {item.get('trial_id')} has invalid allowed_use"
            )
        if item.get("trial_state") not in ALLOWED_CONNECTOR_TRIAL_STATES:
            errors.append(
                f"connector trial {item.get('trial_id')} has invalid trial_state"
            )
        if item.get("access_mode") not in ALLOWED_CONNECTOR_ACCESS_MODES:
            errors.append(
                f"connector trial {item.get('trial_id')} has invalid access_mode"
            )
        if item.get("external_write_allowed") is not False:
            errors.append(
                f"connector trial {item.get('trial_id')} must keep external_write_allowed=false"
            )
        if item.get("access_mode") == "private_metadata_only" and item.get(
            "requires_user_gate"
        ) is not True:
            errors.append(
                f"connector trial {item.get('trial_id')} must gate private metadata use"
            )

    boundary = surface.get("boundary") if isinstance(surface.get("boundary"), Mapping) else {}
    if boundary.get("public_safe") is not True:
        errors.append("boundary.public_safe must be true")
    for key in (
        "raw_private_material_recorded",
        "raw_platform_data_recorded",
        "credentials_recorded",
        "autopublish_allowed",
        "connector_bodies_are_source_of_truth",
    ):
        if boundary.get(key) is not False:
            errors.append(f"boundary.{key} must be false")
    if boundary.get("publish_requires_user_gate") is not True:
        errors.append("boundary.publish_requires_user_gate must be true")

    raw_key_names = _raw_material_key_names(
        source_items,
        angle_candidates,
        draft_items,
        feedback_signals,
        publish_gates,
        material_memory,
        connector_trials,
    )
    if raw_key_names:
        errors.append(
            "raw/private-looking key names must not appear in content-ops records"
        )

    return {
        "schema_version": CONTENT_OPS_VALIDATION_SCHEMA_VERSION,
        "ok": not errors,
        "errors": errors,
        "record_counts": {
            "source_items": len(source_items),
            "angle_candidates": len(angle_candidates),
            "draft_items": len(draft_items),
            "feedback_signals": len(feedback_signals),
            "publish_gates": len(publish_gates),
            "material_memory": len(material_memory),
            "connector_trials": len(connector_trials),
        },
        "raw_material_key_names": raw_key_names,
    }


def project_content_ops_surface(surface: Mapping[str, Any]) -> dict[str, Any]:
    """Project a content-ops surface into first-screen status fields."""

    source_items = _as_mappings(surface.get("source_items"))  # type: ignore[arg-type]
    angle_candidates = _as_mappings(surface.get("angle_candidates"))  # type: ignore[arg-type]
    draft_items = _as_mappings(surface.get("draft_items"))  # type: ignore[arg-type]
    feedback_signals = _as_mappings(surface.get("feedback_signals"))  # type: ignore[arg-type]
    publish_gates = _as_mappings(surface.get("publish_gates"))  # type: ignore[arg-type]
    material_memory = _as_mappings(surface.get("material_memory"))  # type: ignore[arg-type]
    connector_trials = _as_mappings(surface.get("connector_trials"))  # type: ignore[arg-type]
    validation = validate_content_ops_surface(surface)

    source_review_required = [
        item
        for item in source_items
        if item.get("source_status") in {"private_needs_review", "unpublished"}
        or item.get("allowed_use") == "metadata_only"
    ]
    ready_angles = [
        item for item in angle_candidates if item.get("decision") == "draft"
    ]
    drafts_waiting_feedback = [
        item
        for item in draft_items
        if item.get("state") in {"outline", "draft", "ready_for_review"}
    ]
    publish_decision_gates = [
        item
        for item in publish_gates
        if item.get("status") == "blocked_until_user_approval"
    ]
    feedback_effects = _counter(item.get("effect") for item in feedback_signals)
    operator_states = [
        str(item)
        for item in surface.get("operator_states", []) or []
        if isinstance(item, str) and item.strip()
    ]
    user_action_required = bool(publish_decision_gates)
    safe_side_work_available = "safe_side_work_available" in operator_states
    ready_to_draft = bool(ready_angles)

    if user_action_required:
        waiting_on = "user"
        next_safe_action = "review source map and publish gate before external posting"
    elif ready_to_draft:
        waiting_on = "agent"
        next_safe_action = "draft or rewrite from approved source-mapped angle"
    elif source_review_required:
        waiting_on = "operator"
        next_safe_action = "review source status before drafting"
    else:
        waiting_on = "agent"
        next_safe_action = "collect more compact source signals"

    todo_candidates = []
    if ready_angles:
        todo_candidates.append(
            {
                "role": "agent",
                "action_kind": "content_ops_draft_from_angle",
                "title": "Draft or rewrite the selected source-mapped angle",
                "angle_ids": [str(item.get("angle_id")) for item in ready_angles],
                "validation_surface": "source_map plus publish_gate must remain present",
                "stop_condition": "stop before external posting",
            }
        )
    if source_review_required:
        todo_candidates.append(
            {
                "role": "user",
                "action_kind": "content_ops_source_review",
                "title": "Review private or metadata-only source before use",
                "source_item_ids": [
                    str(item.get("source_item_id")) for item in source_review_required
                ],
                "validation_surface": "source_status and allowed_use updated",
            }
        )
    if publish_decision_gates:
        todo_candidates.append(
            {
                "role": "user",
                "action_kind": "content_ops_publish_gate",
                "title": "Approve, deny, or request revision before publication",
                "publish_gate_ids": [
                    str(item.get("gate_id")) for item in publish_decision_gates
                ],
                "validation_surface": "publish gate decision recorded",
            }
        )
    runnable_connector_trials = [
        item
        for item in connector_trials
        if item.get("trial_state") == "ready_for_metadata_trial"
        and item.get("external_write_allowed") is False
    ]
    gated_connector_trials = [
        item for item in connector_trials if item.get("requires_user_gate") is True
    ]
    if runnable_connector_trials:
        todo_candidates.append(
            {
                "role": "agent",
                "action_kind": "content_ops_connector_metadata_trial",
                "title": "Run a connector metadata-only observation trial",
                "trial_ids": [
                    str(item.get("trial_id")) for item in runnable_connector_trials
                ],
                "validation_surface": (
                    "compact source_item_v0 produced; no raw platform or private material"
                ),
                "stop_condition": "stop before login-gated reads, posting, or private source use",
            }
        )
    if gated_connector_trials:
        todo_candidates.append(
            {
                "role": "user",
                "action_kind": "content_ops_connector_owner_gate",
                "title": "Approve or reject private connector metadata intake",
                "trial_ids": [str(item.get("trial_id")) for item in gated_connector_trials],
                "validation_surface": "connector trial gate decision recorded",
            }
        )

    return {
        "schema_version": CONTENT_OPS_SURFACE_PROJECTION_SCHEMA_VERSION,
        "surface_schema_version": surface.get("schema_version"),
        "surface_id": _text(surface.get("surface_id"), limit=120),
        "mode": "read_only",
        "first_screen": {
            "waiting_on": waiting_on,
            "user_action_required": user_action_required,
            "agent_can_continue": bool(ready_to_draft or safe_side_work_available),
            "safe_side_work_available": safe_side_work_available,
            "source_review_required_count": len(source_review_required),
            "ready_to_draft_count": len(ready_angles),
            "waiting_for_feedback_count": len(drafts_waiting_feedback),
            "publish_decision_count": len(publish_decision_gates),
            "next_safe_action": next_safe_action,
        },
        "record_counts": validation["record_counts"],
        "source_statuses": _counter(item.get("source_status") for item in source_items),
        "draft_states": _counter(item.get("state") for item in draft_items),
        "feedback_effects": feedback_effects,
        "publish_gate_statuses": _counter(item.get("status") for item in publish_gates),
        "connector_trials": {
            "count": len(connector_trials),
            "states": _counter(item.get("trial_state") for item in connector_trials),
            "access_modes": _counter(item.get("access_mode") for item in connector_trials),
            "surfaces": _counter(item.get("surface") for item in connector_trials),
            "ready_for_metadata_trial_count": len(runnable_connector_trials),
            "owner_gate_required_count": len(gated_connector_trials),
        },
        "material_memory": {
            "count": len(material_memory),
            "reuse_boundaries": _counter(
                item.get("reuse_boundary") for item in material_memory
            ),
        },
        "todo_candidates": todo_candidates,
        "validation": validation,
        "truth_contract": {
            "projection_is_writable": False,
            "write_authority": "none",
            "source_surface_is_source_of_truth": True,
            "publish_gate_required": True,
            "autopublish_allowed": False,
            "raw_private_material_copied": False,
            "recompute_rule": (
                "recompute from compact content_ops_surface_v0 records; "
                "do not edit this projection as source state"
            ),
        },
    }
