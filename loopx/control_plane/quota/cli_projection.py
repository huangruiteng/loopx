from __future__ import annotations

from typing import Any


QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_todo_summary_compaction_v0"
)
QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND = (
    "quota should-run --include-todo-summary-detail"
)
QUOTA_CLI_USER_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_user_todo_summary_compaction_v0"
)
QUOTA_CLI_USER_TODO_SUMMARY_DETAIL_COMMAND = (
    "quota should-run --include-user-todo-summary-detail"
)
QUOTA_CLI_CAPABILITY_GATE_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_capability_gate_compaction_v0"
)
QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND = (
    "quota should-run --include-capability-gate-detail"
)
QUOTA_CLI_AGENT_LANE_NEXT_ACTION_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_agent_lane_next_action_compaction_v0"
)
QUOTA_CLI_AGENT_LANE_NEXT_ACTION_DETAIL_COMMAND = (
    "quota should-run --include-agent-lane-next-action-detail"
)
QUOTA_CLI_NEXT_ACTION_PROJECTION_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_next_action_projection_compaction_v0"
)
QUOTA_CLI_NEXT_ACTION_PROJECTION_DETAIL_COMMAND = (
    "quota should-run --include-next-action-projection-detail"
)
QUOTA_CLI_VISION_AUDIT_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_vision_audit_compaction_v0"
)
QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND = (
    "quota should-run --include-vision-audit-detail"
)
QUOTA_CLI_VISION_AUDIT_ROOT_REF = "#/vision_continuation_audit"
_RETAINED_AGENT_ITEM_LANES = {
    "first_open_items": 3,
    "first_executable_items": 3,
    "monitor_due_items": 1,
    "monitor_capability_blocked_due_items": 2,
}
_RETAINED_USER_ITEM_LANES = {
    "first_open_items": 3,
    "gate_open_items": 3,
    "active_next_action_items": 3,
}
_RETAINED_CAPABILITY_GATE_CANDIDATES = 3
_CAPABILITY_GATE_CANDIDATE_ANCHOR_FIELDS = (
    "schema_version",
    "todo_id",
    "index",
    "role",
    "status",
    "priority",
    "task_class",
    "action_kind",
    "task_repository",
    "continuation_policy",
    "required_capabilities",
    "target_capabilities",
    "missing_capabilities",
    "missing_target_capabilities",
    "capability_action",
    "capability_repair_mode",
    "claimed_by",
    "required_decision_scopes",
    "unblocks_todo_id",
    "target_key",
    "next_due_at",
    "route_id",
    "route_key",
)
_CAPABILITY_GATE_CANDIDATE_TITLE_MAX_CHARS = 240
_AGENT_LANE_NEXT_ACTION_ANCHOR_FIELDS = (
    "todo_id",
    "task_class",
    "action_kind",
    "task_repository",
    "continuation_policy",
    "required_capabilities",
    "target_capabilities",
    "missing_capabilities",
    "capability_action",
    "claimed_by",
    "required_decision_scopes",
    "unblocks_todo_id",
    "successor_todo_ids",
    "agent_id",
    "source",
    "selected_by",
    "confidence",
    "preserves_goal_next_action",
    "route_id",
    "route_key",
)
_HANDOFF_LINEAGE_FIELDS = (
    "schema_version",
    "handoff_id",
    "todo_id",
    "goal_id",
    "from_agent",
    "to_agent",
    "intent",
    "evidence_refs",
    "unresolved_decisions",
    "blocked_on",
    "source",
    "successor_todo_ids",
    "unblocks_todo_id",
    "excluded_agents",
)
_NEXT_ACTION_PROJECTION_WARNING_ANCHOR_FIELDS = (
    "kind",
    "severity",
    "requires_state_writeback",
    "reason",
    "recommended_action",
)
_VISION_AUDIT_ANCHOR_FIELDS = (
    "required",
    "agent_id",
    "decision",
    "selected_todo_is_goal_completion",
    "closeout_allowed_without_evidence",
    "trigger_count",
    "trigger_kinds",
    "recommended_action",
)


def _compact_nested_item_lists(
    value: dict[str, Any],
    *,
    omitted_lanes: dict[str, int],
    path: str,
) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, child in value.items():
        if isinstance(child, list) and key.endswith("items"):
            if child:
                omitted_lanes[f"{path}.{key}"] = len(child)
            continue
        compact[key] = child
    return compact


def _todo_ids(items: object) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {
        str(item["todo_id"])
        for item in items
        if isinstance(item, dict) and item.get("todo_id")
    }


def _compact_agent_todo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    omitted_lanes: dict[str, int] = {}
    retained_monitor_due = summary.get("monitor_due_items")
    if isinstance(retained_monitor_due, list):
        retained_monitor_due = retained_monitor_due[
            : _RETAINED_AGENT_ITEM_LANES["monitor_due_items"]
        ]
    retained_blocked_due = summary.get("monitor_capability_blocked_due_items")
    if isinstance(retained_blocked_due, list):
        retained_blocked_due = retained_blocked_due[
            : _RETAINED_AGENT_ITEM_LANES["monitor_capability_blocked_due_items"]
        ]
    monitor_ids = _todo_ids(retained_monitor_due)
    monitor_ids.update(_todo_ids(retained_blocked_due))
    deduplicated_aliases: dict[str, int] = {}
    for key, value in summary.items():
        if isinstance(value, list):
            candidate_value = value
            if key == "first_open_items" and monitor_ids:
                candidate_value = [
                    item
                    for item in value
                    if not (
                        isinstance(item, dict)
                        and item.get("todo_id")
                        and str(item["todo_id"]) in monitor_ids
                    )
                ]
                duplicate_count = len(value) - len(candidate_value)
                if duplicate_count:
                    deduplicated_aliases["first_open_items.monitor_aliases"] = (
                        duplicate_count
                    )
            limit = _RETAINED_AGENT_ITEM_LANES.get(key)
            if limit is None:
                if candidate_value:
                    omitted_lanes[key] = len(candidate_value)
                continue
            compact[key] = candidate_value[:limit]
            if len(candidate_value) > limit:
                omitted_lanes[key] = len(candidate_value) - limit
            continue
        if isinstance(value, dict):
            compact[key] = _compact_nested_item_lists(
                value,
                omitted_lanes=omitted_lanes,
                path=key,
            )
            continue
        compact[key] = value

    compact["payload_compaction"] = {
        "schema_version": QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
        "retained_item_lanes": sorted(_RETAINED_AGENT_ITEM_LANES),
        "omitted_lanes": omitted_lanes,
        "deduplicated_aliases": deduplicated_aliases,
        "full_detail_cold_path": QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
    }
    return compact


def _compact_user_todo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    omitted_lanes: dict[str, int] = {}
    for key, value in summary.items():
        if isinstance(value, list):
            limit = _RETAINED_USER_ITEM_LANES.get(key)
            if limit is None:
                if value:
                    omitted_lanes[key] = len(value)
                continue
            compact[key] = value[:limit]
            if len(value) > limit:
                omitted_lanes[key] = len(value) - limit
            continue
        if isinstance(value, dict):
            compact[key] = _compact_nested_item_lists(
                value,
                omitted_lanes=omitted_lanes,
                path=key,
            )
            continue
        compact[key] = value

    compact["payload_compaction"] = {
        "schema_version": QUOTA_CLI_USER_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
        "retained_item_lanes": sorted(_RETAINED_USER_ITEM_LANES),
        "omitted_lanes": omitted_lanes,
        "full_detail_cold_path": QUOTA_CLI_USER_TODO_SUMMARY_DETAIL_COMMAND,
    }
    return compact


def _bounded_projection_title(item: dict[str, Any]) -> tuple[str | None, bool]:
    title = str(item.get("title") or item.get("text") or "").strip()
    if not title:
        return None, False
    if len(title) <= _CAPABILITY_GATE_CANDIDATE_TITLE_MAX_CHARS:
        return title, False
    return (
        title[: _CAPABILITY_GATE_CANDIDATE_TITLE_MAX_CHARS - 3].rstrip() + "...",
        True,
    )


def _capability_gate_candidate_anchor(item: dict[str, Any]) -> dict[str, Any]:
    anchor: dict[str, Any] = {}
    for field in _CAPABILITY_GATE_CANDIDATE_ANCHOR_FIELDS:
        if item.get(field) is not None:
            anchor[field] = item[field]
    title, title_truncated = _bounded_projection_title(item)
    if title:
        anchor["title"] = title
    if title_truncated:
        anchor["title_truncated"] = True
    return anchor


def _compact_capability_gate(gate: dict[str, Any]) -> dict[str, Any]:
    compact = dict(gate)
    omitted_candidates: dict[str, int] = {}
    for lane in ("runnable_candidates", "blocked_candidates"):
        candidates = gate.get(lane)
        if not isinstance(candidates, list):
            continue
        typed_candidates = [
            _capability_gate_candidate_anchor(item)
            for item in candidates
            if isinstance(item, dict)
        ]
        compact[lane] = typed_candidates[:_RETAINED_CAPABILITY_GATE_CANDIDATES]
        if len(typed_candidates) > _RETAINED_CAPABILITY_GATE_CANDIDATES:
            omitted_candidates[lane] = (
                len(typed_candidates) - _RETAINED_CAPABILITY_GATE_CANDIDATES
            )
        if lane == "blocked_candidates":
            compact["blocked_count"] = len(typed_candidates)

    compact["payload_compaction"] = {
        "schema_version": QUOTA_CLI_CAPABILITY_GATE_COMPACTION_SCHEMA_VERSION,
        "retained_candidate_limit": _RETAINED_CAPABILITY_GATE_CANDIDATES,
        "omitted_candidates": omitted_candidates,
        "full_detail_cold_path": QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND,
    }
    return compact


def _handoff_lineage_anchor(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    anchor = {
        field: value[field]
        for field in _HANDOFF_LINEAGE_FIELDS
        if value.get(field) is not None
    }
    return anchor or None


def _agent_lane_next_action_anchor(item: dict[str, Any]) -> dict[str, Any]:
    anchor: dict[str, Any] = {
        "schema_version": QUOTA_CLI_AGENT_LANE_NEXT_ACTION_COMPACTION_SCHEMA_VERSION,
        "source_schema_version": item.get("schema_version"),
    }
    for field in _AGENT_LANE_NEXT_ACTION_ANCHOR_FIELDS:
        if item.get(field) is not None:
            anchor[field] = item[field]
    handoff_lineage = _handoff_lineage_anchor(item.get("handoff_note"))
    if handoff_lineage:
        anchor["handoff_lineage"] = handoff_lineage
    anchor["instruction_ref"] = "#/selected_todo"
    anchor["detail_ref"] = QUOTA_CLI_AGENT_LANE_NEXT_ACTION_DETAIL_COMMAND
    return anchor


def _next_action_projection_warning_anchor(
    warning: dict[str, Any],
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    anchor: dict[str, Any] = {
        "schema_version": QUOTA_CLI_NEXT_ACTION_PROJECTION_COMPACTION_SCHEMA_VERSION,
        "source_schema_version": warning.get("schema_version"),
    }
    for field in _NEXT_ACTION_PROJECTION_WARNING_ANCHOR_FIELDS:
        if warning.get(field) is not None:
            anchor[field] = warning[field]
    if isinstance(payload.get("goal_route_hint"), dict):
        anchor["goal_route_hint_ref"] = "#/goal_route_hint"
    if payload.get("active_state_next_action") is not None:
        anchor["active_state_next_action_ref"] = "#/active_state_next_action"
    if payload.get("latest_run_recommended_action") is not None:
        anchor["latest_run_recommended_action_ref"] = (
            "#/latest_run_recommended_action"
        )
    if warning.get("agent_lane_next_action") is not None:
        anchor["agent_lane_next_action_ref"] = (
            "#/selected_todo/text"
            if isinstance(payload.get("selected_todo"), dict)
            else "#/agent_lane_next_action"
        )
    anchor["detail_ref"] = QUOTA_CLI_NEXT_ACTION_PROJECTION_DETAIL_COMMAND
    return anchor


def _vision_audit_anchor(
    audit: dict[str, Any],
    *,
    detail_ref: str,
) -> dict[str, Any]:
    anchor = {
        "schema_version": QUOTA_CLI_VISION_AUDIT_COMPACTION_SCHEMA_VERSION,
        "source_schema_version": audit.get("schema_version"),
    }
    for field in _VISION_AUDIT_ANCHOR_FIELDS:
        if field in audit:
            anchor[field] = audit[field]
    anchor["detail_ref"] = detail_ref
    anchor["full_detail_cold_path"] = QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND
    return anchor


def _compact_vision_audit_copies(payload: dict[str, Any]) -> dict[str, Any]:
    root_audit = payload.get("vision_continuation_audit")
    if not isinstance(root_audit, dict):
        return payload

    compact = dict(payload)
    compact["vision_continuation_audit"] = _vision_audit_anchor(
        root_audit,
        detail_ref=QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND,
    )

    frontier = payload.get("goal_frontier_projection")
    if isinstance(frontier, dict) and isinstance(
        frontier.get("vision_continuation_audit"),
        dict,
    ):
        compact_frontier = dict(frontier)
        compact_frontier["vision_continuation_audit"] = _vision_audit_anchor(
            frontier["vision_continuation_audit"],
            detail_ref=QUOTA_CLI_VISION_AUDIT_ROOT_REF,
        )
        compact["goal_frontier_projection"] = compact_frontier

    interaction = payload.get("interaction_contract")
    if isinstance(interaction, dict):
        compact_interaction = dict(interaction)
        changed = False
        for channel_name in ("agent_channel", "cli_channel"):
            channel = interaction.get(channel_name)
            if not isinstance(channel, dict) or not isinstance(
                channel.get("vision_continuation_audit"),
                dict,
            ):
                continue
            compact_channel = dict(channel)
            compact_channel["vision_continuation_audit"] = _vision_audit_anchor(
                channel["vision_continuation_audit"],
                detail_ref=QUOTA_CLI_VISION_AUDIT_ROOT_REF,
            )
            compact_interaction[channel_name] = compact_channel
            changed = True
        if changed:
            compact["interaction_contract"] = compact_interaction

    compact["vision_audit_projection"] = {
        "schema_version": QUOTA_CLI_VISION_AUDIT_COMPACTION_SCHEMA_VERSION,
        "mode": "compact_hot_path",
        "canonical_ref": QUOTA_CLI_VISION_AUDIT_ROOT_REF,
        "detail_ref": QUOTA_CLI_VISION_AUDIT_DETAIL_COMMAND,
    }
    return compact


def compact_quota_should_run_cli_payload(
    payload: dict[str, Any],
    *,
    include_todo_summary_detail: bool = False,
    include_user_todo_summary_detail: bool = False,
    include_capability_gate_detail: bool = False,
    include_agent_lane_next_action_detail: bool = False,
    include_next_action_projection_detail: bool = False,
    include_vision_audit_detail: bool = False,
) -> dict[str, Any]:
    """Bound CLI-only diagnostics after the full decision is computed."""

    compact = payload
    compacted_roles: list[str] = []
    role_detail_refs: dict[str, str] = {}
    summary = payload.get("agent_todo_summary")
    if not include_todo_summary_detail and isinstance(summary, dict):
        compact = dict(compact)
        compact["agent_todo_summary"] = _compact_agent_todo_summary(summary)
        compacted_roles.append("agent")
        role_detail_refs["agent"] = QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND

    user_summary = payload.get("user_todo_summary")
    if not include_user_todo_summary_detail and isinstance(user_summary, dict):
        compact = dict(compact)
        compact["user_todo_summary"] = _compact_user_todo_summary(user_summary)
        compacted_roles.append("user")
        role_detail_refs["user"] = QUOTA_CLI_USER_TODO_SUMMARY_DETAIL_COMMAND

    if compacted_roles:
        compact["todo_summary_projection"] = {
            "schema_version": QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
            "mode": "compact_hot_path",
            "compacted_roles": compacted_roles,
            "detail_ref": role_detail_refs[compacted_roles[0]],
            "role_detail_refs": role_detail_refs,
        }
    capability_gate = payload.get("capability_gate")
    if not include_capability_gate_detail and isinstance(capability_gate, dict):
        compact = dict(compact)
        compact["capability_gate"] = _compact_capability_gate(capability_gate)
        compact["capability_gate_projection"] = {
            "schema_version": QUOTA_CLI_CAPABILITY_GATE_COMPACTION_SCHEMA_VERSION,
            "mode": "compact_hot_path",
            "detail_ref": QUOTA_CLI_CAPABILITY_GATE_DETAIL_COMMAND,
        }
    agent_lane_next_action = payload.get("agent_lane_next_action")
    if not include_agent_lane_next_action_detail and isinstance(
        agent_lane_next_action,
        dict,
    ):
        compact = dict(compact)
        compact["agent_lane_next_action"] = _agent_lane_next_action_anchor(
            agent_lane_next_action
        )
    next_action_projection_warning = payload.get("next_action_projection_warning")
    if not include_next_action_projection_detail and isinstance(
        next_action_projection_warning,
        dict,
    ):
        compact = dict(compact)
        compact["next_action_projection_warning"] = (
            _next_action_projection_warning_anchor(
                next_action_projection_warning,
                payload=payload,
            )
        )
    if not include_vision_audit_detail:
        compact = _compact_vision_audit_copies(compact)
    return compact
