from __future__ import annotations

from typing import Any


QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_todo_summary_compaction_v0"
)
QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND = (
    "quota should-run --include-todo-summary-detail"
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


def _compact_agent_todo_summary(summary: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    omitted_lanes: dict[str, int] = {}
    for key, value in summary.items():
        if isinstance(value, list):
            limit = _RETAINED_AGENT_ITEM_LANES.get(key)
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
        "schema_version": QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
        "retained_item_lanes": sorted(_RETAINED_AGENT_ITEM_LANES),
        "omitted_lanes": omitted_lanes,
        "full_detail_cold_path": QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
    }
    return compact


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
    include_vision_audit_detail: bool = False,
) -> dict[str, Any]:
    """Bound CLI-only diagnostics after the full decision is computed."""

    compact = payload
    summary = payload.get("agent_todo_summary")
    if not include_todo_summary_detail and isinstance(summary, dict):
        compact = dict(compact)
        compact["agent_todo_summary"] = _compact_agent_todo_summary(summary)
        compact["todo_summary_projection"] = {
            "schema_version": QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
            "mode": "compact_hot_path",
            "compacted_roles": ["agent"],
            "detail_ref": QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
        }
    if not include_vision_audit_detail:
        compact = _compact_vision_audit_copies(compact)
    return compact
