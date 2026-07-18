from __future__ import annotations

from typing import Any


EVENT_STORE_MIGRATION_BRIDGE_SCHEMA_VERSION = "event_store_migration_bridge_v0"
EVENT_STORE_MIGRATION_CANARY_SCHEMA_VERSION = "event_store_migration_canary_v0"

MARKDOWN_ACTIVE_STATE_SOURCE = "markdown_active_state"
EVENT_PROJECTION_SOURCE = "event_projection"


def _compact_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _bool(value: Any) -> bool:
    return value is True


def build_event_store_migration_bridge(
    *,
    goal_id: str,
    event_read_path_ready: bool,
    dual_read_parity_clean: bool = False,
    rollback_plan_recorded: bool = False,
    bounded_canary_passed: bool = False,
    idempotency_conflicts_clean: bool = False,
    public_boundary_clean: bool = False,
    active_state_projection_ready: bool = False,
    event_projection_head_matches_store: bool = False,
    canary_goal_limit: int = 1,
    canary_duration_minutes: int = 30,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a fail-closed migration bridge before event projection promotion."""

    normalized_goal_id = _compact_text(goal_id)
    if not normalized_goal_id:
        raise ValueError("goal_id is required")
    canary_goal_limit = max(1, int(canary_goal_limit or 1))
    canary_duration_minutes = max(1, int(canary_duration_minutes or 1))
    evidence = [_compact_text(ref) for ref in (evidence_refs or []) if _compact_text(ref)]

    checks = {
        "event_read_path_ready": _bool(event_read_path_ready),
        "active_state_projection_ready": _bool(active_state_projection_ready),
        "dual_read_parity_clean": _bool(dual_read_parity_clean),
        "event_projection_head_matches_store": _bool(event_projection_head_matches_store),
        "rollback_plan_recorded": _bool(rollback_plan_recorded),
        "bounded_canary_passed": _bool(bounded_canary_passed),
        "idempotency_conflicts_clean": _bool(idempotency_conflicts_clean),
        "public_boundary_clean": _bool(public_boundary_clean),
    }
    required_for_shadow = [
        "event_read_path_ready",
        "active_state_projection_ready",
    ]
    required_for_canary = [
        *required_for_shadow,
        "dual_read_parity_clean",
        "event_projection_head_matches_store",
        "rollback_plan_recorded",
        "idempotency_conflicts_clean",
        "public_boundary_clean",
    ]
    required_for_promotion = [
        *required_for_canary,
        "bounded_canary_passed",
    ]
    missing_for_shadow = [key for key in required_for_shadow if not checks[key]]
    missing_for_canary = [key for key in required_for_canary if not checks[key]]
    missing_for_promotion = [key for key in required_for_promotion if not checks[key]]

    if missing_for_shadow:
        stage = "wait_for_event_read_path"
        next_action = (
            "finish event read-path prerequisites before dual-read migration work"
        )
    elif missing_for_canary:
        stage = "dual_read_shadow"
        next_action = (
            "compare Markdown read model and event projection until parity, rollback, "
            "idempotency, and public-boundary checks are clean"
        )
    elif missing_for_promotion:
        stage = "bounded_canary"
        next_action = (
            "run the bounded canary on a small goal set before promotion"
        )
    else:
        stage = "promotion_candidate"
        next_action = (
            "promote event projection only through an explicit reviewed write-path change"
        )

    return {
        "schema_version": EVENT_STORE_MIGRATION_BRIDGE_SCHEMA_VERSION,
        "goal_id": normalized_goal_id,
        "source_of_truth": MARKDOWN_ACTIVE_STATE_SOURCE,
        "candidate_source": EVENT_PROJECTION_SOURCE,
        "stage": stage,
        "promotion_allowed": False,
        "promotion_candidate": not missing_for_promotion,
        "next_action": next_action,
        "checks": checks,
        "missing_for_shadow": missing_for_shadow,
        "missing_for_canary": missing_for_canary,
        "missing_for_promotion": missing_for_promotion,
        "dual_read": {
            "enabled": not missing_for_shadow,
            "read_order": [
                MARKDOWN_ACTIVE_STATE_SOURCE,
                EVENT_PROJECTION_SOURCE,
            ],
            "failure_policy": "prefer_markdown_and_record_parity_delta",
            "required_equality": [
                "todo ids",
                "todo status",
                "priority and planner order",
                "claimed_by",
                "user todo binding",
                "gate refs",
                "projection head sequence",
            ],
        },
        "rollback": {
            "required": True,
            "recorded": checks["rollback_plan_recorded"],
            "fallback_source": MARKDOWN_ACTIVE_STATE_SOURCE,
            "trigger": [
                "parity delta",
                "projection head mismatch",
                "event append conflict",
                "public boundary warning",
                "canary regression",
            ],
            "action": "disable event projection preference and keep Markdown parser as canonical read fallback",
        },
        "canary": build_event_store_migration_canary(
            goal_id=normalized_goal_id,
            ready=not missing_for_canary,
            passed=checks["bounded_canary_passed"],
            goal_limit=canary_goal_limit,
            duration_minutes=canary_duration_minutes,
            evidence_refs=evidence,
        ),
        "evidence_refs": evidence,
    }


def build_event_store_migration_canary(
    *,
    goal_id: str,
    ready: bool,
    passed: bool = False,
    goal_limit: int = 1,
    duration_minutes: int = 30,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Describe the bounded rollout canary for event-store read promotion."""

    normalized_goal_id = _compact_text(goal_id)
    if not normalized_goal_id:
        raise ValueError("goal_id is required")
    goal_limit = max(1, int(goal_limit or 1))
    duration_minutes = max(1, int(duration_minutes or 1))
    evidence = [_compact_text(ref) for ref in (evidence_refs or []) if _compact_text(ref)]

    return {
        "schema_version": EVENT_STORE_MIGRATION_CANARY_SCHEMA_VERSION,
        "goal_id": normalized_goal_id,
        "ready": bool(ready),
        "passed": bool(passed),
        "scope": {
            "max_goals": goal_limit,
            "duration_minutes": duration_minutes,
            "write_path": "disabled",
            "read_preference": MARKDOWN_ACTIVE_STATE_SOURCE,
        },
        "observe": [
            "status todo summaries",
            "quota selected todo",
            "review packet todo refs",
            "dashboard/frontstage projection",
            "event projection head sequence",
        ],
        "success_criteria": [
            "no parity delta",
            "no idempotency conflict",
            "no private-boundary warning",
            "rollback remains one-command safe",
        ],
        "failure_policy": "stop canary and keep Markdown parser canonical",
        "evidence_refs": evidence,
    }
