from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..agents.agent_scope import (
    _agent_scope_filter_user_action_items,
    _agent_scope_filter_user_gate_items,
    _agent_scope_selectable_todo_item,
)
from ..agents.capability_gate import missing_required_capabilities
from .claim_visibility import (
    build_agent_claim_scoped_open_items,
    build_todo_claim_visibility_lanes,
)
from .contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
)
from .deferred_resume import (
    build_todo_deferred_visibility_lanes,
    build_todo_resume_blocked_visibility_lanes,
    resolve_capacity_resume_summary,
)
from .handoff_gate import build_todo_handoff_gate_lanes
from .projection import (
    todo_item_is_actionable_open,
    todo_item_is_due_monitor,
    todo_item_task_class,
    todo_projection_sort_key,
    todo_summary_monitor_schedule_gap_items,
    todo_summary_monitor_writeback_contract,
    todo_summary_monitor_writeback_supported,
)
from .route_continuation import build_todo_route_continuation_lanes
from .succession_warning import build_todo_succession_warning_lanes
from .summary_item import compact_todo_summary_item, todo_summary_source_items
from .user_gate import is_user_gate_todo_item


MONITOR_DUE_ITEM_LIMIT = 1
TODO_BACKLOG_ITEM_LIMIT = 8
TODO_DEFERRED_VISIBILITY_LIMIT = 8
TODO_VISIBILITY_LANE_LIMIT = 16
QUOTA_PAYLOAD_ITEM_TEXT_LIMIT = 180
QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT = 2
QUOTA_PAYLOAD_USER_ACTION_ITEM_LIMIT = 3
QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT = 2
QUOTA_PAYLOAD_COMPACTION_SCHEMA_VERSION = "quota_todo_summary_payload_compaction_v0"
QUOTA_PAYLOAD_ITEM_FIELDS = (
    "schema_version",
    "index",
    "text",
    "title",
    "todo_id",
    "status",
    "priority",
    "task_class",
    "action_kind",
    "decision_scope",
    "required_decision_scopes",
    "task_repository",
    "continuation_policy",
    "required_capabilities",
    "missing_capabilities",
    "claimed_by",
    "bound_agent",
    "goal_bound",
    "blocks_agent",
    "excluded_agents",
    "global_gate",
    "unblocks_todo_id",
    "resume_when",
    "resume_condition",
    "resume_ready",
    "blocking_monitor_todo_id",
    "no_followup",
    "successor_todo_ids",
    "target_key",
    "cadence",
    "next_due_at",
    "expires_at",
    "last_checked_at",
    "result_hash",
    "consecutive_no_change",
    "material_change",
    "max_no_change_before_replan",
    "route_continuation_replan_required",
    "route_continuation_reason",
    "route_id",
    "route_key",
    "completed_at",
    "updated_at",
    "gate_state",
)
QUOTA_PAYLOAD_LANE_LIMITS = {
    "monitor_due_items": MONITOR_DUE_ITEM_LIMIT,
    "monitor_capability_blocked_due_items": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "monitor_schedule_gap_items": MONITOR_DUE_ITEM_LIMIT,
    "first_open_items": 3,
    "first_executable_items": 3,
    "active_next_action_items": 3,
    "active_next_action_executable_items": 3,
    "monitor_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "backlog_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "executable_backlog_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "unclaimed_priority_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "claimed_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "claimed_advancement_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "claimed_monitor_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "current_agent_claimed_open_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "current_agent_claimed_advancement_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "current_agent_claimed_monitor_items": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
    "claimed_by_others_items": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "other_agent_scoped_items": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "other_agent_bound_user_action_items": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "user_action_items": QUOTA_PAYLOAD_USER_ACTION_ITEM_LIMIT,
    "resume_blocked_items": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "handoff_gates": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "current_agent_handoff_gates": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
    "current_agent_cleared_without_successor_handoff_gates": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
}


@dataclass(frozen=True)
class _QuotaTodoLanes:
    all_open_items: list[dict[str, Any]]
    blocking_open_items: list[dict[str, Any]]
    user_action_open_items: list[dict[str, Any]]
    other_agent_bound_user_action_items: list[dict[str, Any]]
    user_action_agent_scope_filter: dict[str, Any] | None
    other_agent_scoped_items: list[dict[str, Any]]
    agent_scope_filter: dict[str, Any] | None
    open_items: list[dict[str, Any]]
    claim_scope: dict[str, Any] | None
    executable_items: list[dict[str, Any]]
    monitor_items: list[dict[str, Any]]
    monitor_due_items: list[dict[str, Any]]
    monitor_capability_blocked_due_items: list[dict[str, Any]]
    claimed_open_items: list[dict[str, Any]]
    display_open_items: list[dict[str, Any]]
    active_next_action_items: list[dict[str, Any]]
    active_next_action_executable_items: list[dict[str, Any]]
    open_count: Any


def _strict_non_negative_int(value: Any) -> int | None:
    if type(value) is not int or value < 0:
        return None
    return value


def _terminal_closure_proof_is_valid(
    value: dict[str, Any],
    *,
    counts: dict[str, int | None],
    source_proof: dict[str, Any],
) -> bool:
    proof = value.get("terminal_closure_proof")
    items = value.get("items")
    return bool(
        value.get("schema_version") == "todo_summary_v0"
        and isinstance(items, list)
        and 0 < len(items) <= counts["total_count"]
        and all(
            isinstance(item, dict)
            and item.get("status") == "done"
            and item.get("done") is True
            and item.get("route_continuation_replan_required") is not True
            for item in items
        )
        and value.get("monitor_open_items") == []
        and value.get("deferred_items") == []
        and value.get("deferred_resume_candidates") == []
        and _strict_non_negative_int(value.get("monitor_due_count")) == 0
        and _strict_non_negative_int(value.get("monitor_schedule_gap_count")) == 0
        and _strict_non_negative_int(value.get("completed_without_successor_count", 0)) == 0
        and _strict_non_negative_int(value.get("route_continuation_replan_count", 0)) == 0
        and isinstance(proof, dict)
        and proof.get("schema_version") == "todo_terminal_closure_proof_v0"
        and proof.get("role") == source_proof.get("role")
        and proof.get("source_section") == value.get("source_section")
        and proof.get("item_count") == counts["total_count"]
        and proof.get("all_todos_done") is True
        and _strict_non_negative_int(proof.get("monitor_open_count")) == 0
        and _strict_non_negative_int(proof.get("successor_gap_count")) == 0
        and _strict_non_negative_int(proof.get("route_replan_count")) == 0
        and _strict_non_negative_int(proof.get("no_followup_count")) is not None
        and proof.get("derived") is True
    )


def _validated_todo_source_contract(
    value: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    proof = value.get("source_proof")
    counts = {
        key: _strict_non_negative_int(value.get(key))
        for key in ("total_count", "open_count", "done_count", "deferred_count")
    }
    valid_counts = (
        all(count is not None for count in counts.values())
        and bool(counts["total_count"])
        and counts["total_count"]
        == counts["open_count"] + counts["done_count"] + counts["deferred_count"]
    )
    valid_proof = bool(
        isinstance(proof, dict)
        and proof.get("schema_version") == "todo_source_proof_v0"
        and proof.get("role") in {"user", "agent"}
        and proof.get("derived") is True
        and bool(str(value.get("source_section") or "").strip())
        and type(proof.get("item_count")) is int
        and proof.get("item_count") == counts["total_count"]
    )
    valid_terminal_closure = bool(
        valid_counts
        and valid_proof
        and _terminal_closure_proof_is_valid(
            value,
            counts=counts,
            source_proof=proof,
        )
    )
    completeness = {
        "schema_version": "todo_source_completeness_v0",
        "status": "valid" if valid_terminal_closure else "invalid",
        "source": "structured_todo_projection",
        "role": proof.get("role") if isinstance(proof, dict) else None,
        "terminal_closure": "valid" if valid_terminal_closure else "invalid",
    }

    intent = value.get("closure_intent")
    terminal_proof = value.get("terminal_closure_proof")
    valid_intent = bool(
        valid_terminal_closure
        and isinstance(intent, dict)
        and intent.get("schema_version") == "todo_closure_intent_v0"
        and intent.get("kind") == "no_followup"
        and intent.get("derived") is True
        and type(intent.get("count")) is int
        and 0 < intent.get("count") <= counts["done_count"]
        and isinstance(terminal_proof, dict)
        and intent.get("count") == terminal_proof.get("no_followup_count")
    )
    return completeness, {**intent, "source": "todo_no_followup"} if valid_intent else None


def _build_quota_todo_lanes(
    value: dict[str, Any],
    *,
    all_open_items: list[dict[str, Any]],
    source_open_count: Any,
    agent_identity: dict[str, Any] | None,
    filter_user_gate_blocks_agent: bool,
    available_capabilities: Any,
) -> _QuotaTodoLanes:
    blocking_open_items = all_open_items
    user_action_open_items: list[dict[str, Any]] = []
    other_agent_bound_user_action_items: list[dict[str, Any]] = []
    user_action_agent_scope_filter: dict[str, Any] | None = None
    other_agent_scoped_items: list[dict[str, Any]] = []
    agent_scope_filter: dict[str, Any] | None = None
    if filter_user_gate_blocks_agent:
        gate_candidate_items = [
            item for item in all_open_items if is_user_gate_todo_item(item)
        ]
        user_action_candidate_items = [
            item for item in all_open_items if not is_user_gate_todo_item(item)
        ]
        (
            user_action_open_items,
            other_agent_bound_user_action_items,
            user_action_agent_scope_filter,
        ) = _agent_scope_filter_user_action_items(
            user_action_candidate_items,
            agent_identity=agent_identity,
        )
        (
            blocking_open_items,
            other_agent_scoped_items,
            agent_scope_filter,
        ) = _agent_scope_filter_user_gate_items(
            gate_candidate_items,
            agent_identity=agent_identity,
        )
    open_items, claim_scope = build_agent_claim_scoped_open_items(
        blocking_open_items,
        agent_identity=agent_identity,
        diagnostic_item_limit=3,
    )
    executable_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    monitor_items = [
        item
        for item in open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_due_candidates = (
        [
            item
            for item in monitor_items
            if todo_item_is_due_monitor(item)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if todo_summary_monitor_writeback_supported(value)
        else []
    )
    monitor_due_items: list[dict[str, Any]] = []
    monitor_capability_blocked_due_items: list[dict[str, Any]] = []
    for item in monitor_due_candidates:
        missing = missing_required_capabilities(
            item,
            available_capabilities=available_capabilities,
        )
        if missing:
            diagnostic_item = compact_todo_summary_item(
                item,
                text=str(item.get("text") or "").strip(),
            )
            diagnostic_item["missing_capabilities"] = missing
            monitor_capability_blocked_due_items.append(diagnostic_item)
            continue
        monitor_due_items.append(item)
    active_next_action_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_items"), list)
        else []
    )
    active_next_action_executable_items = (
        [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in (value.get("active_next_action_executable_items") or [])
            if isinstance(item, dict)
            if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
        ]
        if isinstance(value.get("active_next_action_executable_items"), list)
        else []
    )
    open_count = source_open_count
    if filter_user_gate_blocks_agent:
        open_count = len(open_items) + len(user_action_open_items)
    elif claim_scope is not None:
        open_count = len(open_items)
    return _QuotaTodoLanes(
        all_open_items=all_open_items,
        blocking_open_items=blocking_open_items,
        user_action_open_items=user_action_open_items,
        other_agent_bound_user_action_items=other_agent_bound_user_action_items,
        user_action_agent_scope_filter=user_action_agent_scope_filter,
        other_agent_scoped_items=other_agent_scoped_items,
        agent_scope_filter=agent_scope_filter,
        open_items=open_items,
        claim_scope=claim_scope,
        executable_items=executable_items,
        monitor_items=monitor_items,
        monitor_due_items=monitor_due_items,
        monitor_capability_blocked_due_items=monitor_capability_blocked_due_items,
        claimed_open_items=[
            item for item in blocking_open_items if item.get("claimed_by")
        ],
        display_open_items=(
            open_items + user_action_open_items
            if filter_user_gate_blocks_agent
            else open_items
        ),
        active_next_action_items=active_next_action_items,
        active_next_action_executable_items=active_next_action_executable_items,
        open_count=open_count,
    )


def summarize_user_todos_for_quota(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
    available_capabilities: Any = None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    source_completeness, closure_intent = _validated_todo_source_contract(value)
    all_open_items = sorted(
        todo_summary_source_items(value),
        key=todo_projection_sort_key,
    )
    lanes = _build_quota_todo_lanes(
        value,
        all_open_items=all_open_items,
        source_open_count=value.get("open_count", len(all_open_items)),
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        available_capabilities=available_capabilities,
    )
    monitor_schedule_gap_items = todo_summary_monitor_schedule_gap_items(
        {
            "monitor_open_items": lanes.monitor_items,
            "monitor_writeback": value.get("monitor_writeback"),
        }
    )
    gate_items = [
        item
        for item in lanes.open_items
        if is_user_gate_todo_item(item)
    ]
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section"),
        "total_count": value.get("total_count"),
        "open_count": lanes.open_count,
        "done_count": value.get("done_count"),
        "deferred_count": value.get("deferred_count"),
        "source_completeness": source_completeness,
        "first_open_items": lanes.display_open_items[:3],
        "first_executable_items": lanes.executable_items[:3],
        "gate_open_items": gate_items[:3],
        "monitor_open_items": lanes.monitor_items,
        "monitor_due_count": len(lanes.monitor_due_items),
        "monitor_due_items": lanes.monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "monitor_capability_blocked_due_count": len(
            lanes.monitor_capability_blocked_due_items
        ),
        "monitor_capability_blocked_due_items": (
            lanes.monitor_capability_blocked_due_items
        ),
        "monitor_schedule_gap_count": len(monitor_schedule_gap_items),
        "monitor_schedule_gap_items": monitor_schedule_gap_items[:MONITOR_DUE_ITEM_LIMIT],
        "active_next_action_items": lanes.active_next_action_items,
        "active_next_action_executable_items": lanes.active_next_action_executable_items,
        "backlog_items": lanes.display_open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": lanes.executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    if closure_intent:
        summary["closure_intent"] = closure_intent
    monitor_writeback = todo_summary_monitor_writeback_contract(value)
    if monitor_writeback:
        summary["monitor_writeback"] = monitor_writeback
    summary.update(
        build_todo_claim_visibility_lanes(
            lanes.blocking_open_items,
            agent_identity=agent_identity,
            backlog_item_limit=TODO_BACKLOG_ITEM_LIMIT,
            visibility_lane_limit=TODO_VISIBILITY_LANE_LIMIT,
        )
    )
    summary.update(
        build_todo_deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_resume_blocked_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_route_continuation_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_succession_warning_lanes(
            value,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    source_claimed_open_count = None if filter_user_gate_blocks_agent else value.get("claimed_open_count")
    if lanes.claimed_open_items or source_claimed_open_count:
        summary["claimed_open_count"] = source_claimed_open_count or len(lanes.claimed_open_items)
        summary["unclaimed_open_count"] = (
            max(0, int(lanes.open_count or 0) - len(lanes.claimed_open_items))
            if filter_user_gate_blocks_agent
            else value.get(
                "unclaimed_open_count",
                max(0, int(lanes.open_count or 0) - len(lanes.claimed_open_items)),
            )
        )
    if lanes.claim_scope:
        summary["claim_scope"] = lanes.claim_scope
    if filter_user_gate_blocks_agent:
        summary["all_open_count"] = value.get("open_count", len(all_open_items))
    if lanes.agent_scope_filter:
        summary["agent_scope_filter"] = lanes.agent_scope_filter
        summary["other_agent_scoped_open_count"] = len(lanes.other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    if filter_user_gate_blocks_agent and lanes.user_action_open_items:
        summary["user_action_open_count"] = len(lanes.user_action_open_items)
        summary["user_action_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.user_action_open_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    if lanes.user_action_agent_scope_filter:
        summary["user_action_agent_scope_filter"] = lanes.user_action_agent_scope_filter
        summary["other_agent_bound_user_action_open_count"] = len(
            lanes.other_agent_bound_user_action_items
        )
        summary["other_agent_bound_user_action_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.other_agent_bound_user_action_items[
                :TODO_VISIBILITY_LANE_LIMIT
            ]
        ]
    return summary


def _truncate_quota_payload_text(value: Any, *, limit: int) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _compact_quota_payload_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    compact: dict[str, Any] = {}
    for key in QUOTA_PAYLOAD_ITEM_FIELDS:
        value = item.get(key)
        if value is None:
            continue
        if key in {"text", "title"}:
            value = _truncate_quota_payload_text(
                value,
                limit=QUOTA_PAYLOAD_ITEM_TEXT_LIMIT,
            )
        compact[key] = value
    if "text" not in compact and item.get("text") is not None:
        compact["text"] = _truncate_quota_payload_text(
            item.get("text"),
            limit=QUOTA_PAYLOAD_ITEM_TEXT_LIMIT,
        )
    return compact


def _compact_quota_payload_item_list(
    items: Any,
    *,
    limit: int,
) -> list[Any]:
    if not isinstance(items, list):
        return []
    return [_compact_quota_payload_item(item) for item in items[:limit]]


def _compact_quota_payload_claim_scope(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    compact: dict[str, Any] = {}
    for key, child in value.items():
        if isinstance(child, list):
            compact[key] = _compact_quota_payload_item_list(
                child,
                limit=QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
            )
        else:
            compact[key] = child
    return compact


def _compact_quota_payload_nested_warning(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    compact: dict[str, Any] = {}
    for key, child in value.items():
        if isinstance(child, list) and key.endswith("items"):
            compact[key] = _compact_quota_payload_item_list(
                child,
                limit=QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
            )
        else:
            compact[key] = child
    return compact


def compact_quota_todo_summary_for_payload(summary: dict[str, Any]) -> dict[str, Any]:
    """Keep quota hot-path todo summaries bounded without changing decision input."""
    compact: dict[str, Any] = {}
    compacted_lanes: dict[str, dict[str, int]] = {}
    for key, value in summary.items():
        if key in {"source_completeness", "closure_intent"}:
            continue
        if isinstance(value, list):
            limit = QUOTA_PAYLOAD_LANE_LIMITS.get(key, QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT)
            compact[key] = _compact_quota_payload_item_list(value, limit=limit)
            if len(value) > limit:
                compacted_lanes[key] = {
                    "shown": limit,
                    "total": len(value),
                }
        elif key == "claim_scope":
            compact[key] = _compact_quota_payload_claim_scope(value)
        elif isinstance(value, dict):
            compact[key] = _compact_quota_payload_nested_warning(value)
        else:
            compact[key] = value
    compact["payload_compaction"] = {
        "schema_version": QUOTA_PAYLOAD_COMPACTION_SCHEMA_VERSION,
        "item_text_limit": QUOTA_PAYLOAD_ITEM_TEXT_LIMIT,
        "visibility_lane_item_limit": QUOTA_PAYLOAD_VISIBILITY_LANE_LIMIT,
        "diagnostic_lane_item_limit": QUOTA_PAYLOAD_DIAGNOSTIC_LANE_LIMIT,
        "compacted_lanes": compacted_lanes,
        "full_detail_cold_path": "status, todo list, or active state",
    }
    return compact


def summarize_project_asset_todos_for_quota(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
    available_capabilities: Any = None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("items"), list)
        or isinstance(value.get("first_open_items"), list)
    ) and (
        "total_count" in value or "open_count" in value or "done_count" in value
    ):
        return summarize_user_todos_for_quota(
            value,
            agent_identity=agent_identity,
            filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
            available_capabilities=available_capabilities,
        )

    all_open_items = sorted(
        todo_summary_source_items(value),
        key=todo_projection_sort_key,
    )
    if not all_open_items:
        next_text = str(value.get("next") or "").strip()
        next_index = value.get("next_index", 1)
        all_open_items = [{"index": next_index, "text": next_text}] if next_text else []
        next_claimed_by = str(value.get("next_claimed_by") or "").strip()
        if all_open_items and next_claimed_by:
            all_open_items[0]["claimed_by"] = next_claimed_by
    lanes = _build_quota_todo_lanes(
        value,
        all_open_items=all_open_items,
        source_open_count=value.get("open", value.get("open_count", len(all_open_items))),
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        available_capabilities=available_capabilities,
    )
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section") or "project_asset",
        "total_count": value.get("total", value.get("total_count")),
        "open_count": lanes.open_count,
        "done_count": value.get("done", value.get("done_count")),
        "first_open_items": lanes.display_open_items[:3],
        "first_executable_items": lanes.executable_items[:3],
        "monitor_open_items": lanes.monitor_items,
        "monitor_due_count": len(lanes.monitor_due_items),
        "monitor_due_items": lanes.monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "monitor_capability_blocked_due_count": len(
            lanes.monitor_capability_blocked_due_items
        ),
        "monitor_capability_blocked_due_items": (
            lanes.monitor_capability_blocked_due_items
        ),
        "active_next_action_items": lanes.active_next_action_items,
        "active_next_action_executable_items": lanes.active_next_action_executable_items,
        "backlog_items": lanes.display_open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": lanes.executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    monitor_writeback = todo_summary_monitor_writeback_contract(value)
    if monitor_writeback:
        summary["monitor_writeback"] = monitor_writeback
    summary.update(
        build_todo_claim_visibility_lanes(
            lanes.blocking_open_items,
            agent_identity=agent_identity,
            backlog_item_limit=TODO_BACKLOG_ITEM_LIMIT,
            visibility_lane_limit=TODO_VISIBILITY_LANE_LIMIT,
        )
    )
    summary.update(
        build_todo_deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_DEFERRED_VISIBILITY_LIMIT,
        )
    )
    summary.update(
        build_todo_handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    summary.update(
        build_todo_route_continuation_lanes(
            value,
            agent_identity=agent_identity,
            item_limit=TODO_BACKLOG_ITEM_LIMIT,
        )
    )
    source_claimed_open_count = None if filter_user_gate_blocks_agent else value.get("claimed_open_count")
    if lanes.claimed_open_items or source_claimed_open_count:
        summary["claimed_open_count"] = source_claimed_open_count or len(lanes.claimed_open_items)
        summary["unclaimed_open_count"] = (
            max(0, int(lanes.open_count or 0) - len(lanes.claimed_open_items))
            if filter_user_gate_blocks_agent
            else value.get(
                "unclaimed_open_count",
                max(0, int(lanes.open_count or 0) - len(lanes.claimed_open_items)),
            )
        )
    if lanes.claim_scope:
        summary["claim_scope"] = lanes.claim_scope
    if lanes.agent_scope_filter:
        summary["agent_scope_filter"] = lanes.agent_scope_filter
        summary["all_open_count"] = value.get("open", value.get("open_count", len(all_open_items)))
        summary["other_agent_scoped_open_count"] = len(lanes.other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    if filter_user_gate_blocks_agent and lanes.user_action_open_items:
        summary["user_action_open_count"] = len(lanes.user_action_open_items)
        summary["user_action_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.user_action_open_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    if lanes.user_action_agent_scope_filter:
        summary["user_action_agent_scope_filter"] = lanes.user_action_agent_scope_filter
        summary["other_agent_bound_user_action_open_count"] = len(
            lanes.other_agent_bound_user_action_items
        )
        summary["other_agent_bound_user_action_items"] = [
            compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in lanes.other_agent_bound_user_action_items[
                :TODO_VISIBILITY_LANE_LIMIT
            ]
        ]
    return summary


def is_canonical_attention_todo_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schema_version") == "todo_summary_v0":
        return True
    source_section = str(value.get("source_section") or "").strip().lower()
    if source_section.startswith("raw "):
        return False
    return source_section in {"agent todo", "user todo"}


def select_quota_todo_summary(
    canonical_value: Any,
    project_asset_value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
    available_capabilities: Any = None,
) -> dict[str, Any] | None:
    canonical_value = resolve_capacity_resume_summary(
        canonical_value,
        available_capabilities=available_capabilities,
    )
    project_asset_value = resolve_capacity_resume_summary(
        project_asset_value,
        available_capabilities=available_capabilities,
    )
    canonical_summary = summarize_user_todos_for_quota(
        canonical_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        available_capabilities=available_capabilities,
    )
    project_asset_summary = summarize_project_asset_todos_for_quota(
        project_asset_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        available_capabilities=available_capabilities,
    )
    if is_canonical_attention_todo_summary(canonical_value):
        return canonical_summary or project_asset_summary
    return project_asset_summary or canonical_summary


def select_quota_todo_source_items(
    canonical_value: Any,
    project_asset_value: Any,
) -> list[dict[str, Any]]:
    """Return the authoritative pre-hot-path todo source for semantic checks."""

    canonical_items = (
        todo_summary_source_items(canonical_value)
        if isinstance(canonical_value, dict)
        else None
    )
    project_asset_items = (
        todo_summary_source_items(project_asset_value)
        if isinstance(project_asset_value, dict)
        else None
    )
    if is_canonical_attention_todo_summary(canonical_value):
        return canonical_items if canonical_items is not None else project_asset_items or []
    return project_asset_items if project_asset_items is not None else canonical_items or []
