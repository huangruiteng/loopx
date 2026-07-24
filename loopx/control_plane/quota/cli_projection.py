from __future__ import annotations

from typing import Any


QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION = (
    "quota_cli_todo_summary_compaction_v0"
)
QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND = (
    "quota should-run --include-todo-summary-detail"
)
_RETAINED_AGENT_ITEM_LANES = {
    "first_open_items": 3,
    "first_executable_items": 3,
    "monitor_due_items": 1,
    "monitor_capability_blocked_due_items": 2,
}
_RETAINED_SUCCESSION_WARNING_TODO_IDS = 3


def _compact_nested_item_lists(
    value: dict[str, Any],
    *,
    omitted_lanes: dict[str, int],
    path: str,
) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, child in value.items():
        if isinstance(child, list) and key.endswith("items"):
            if path == "todo_succession_warning":
                todo_ids = [
                    str(item.get("todo_id"))
                    for item in child
                    if isinstance(item, dict) and item.get("todo_id")
                ][:_RETAINED_SUCCESSION_WARNING_TODO_IDS]
                if todo_ids:
                    compact["todo_ids"] = todo_ids
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


def compact_quota_should_run_cli_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Bound CLI-only todo diagnostics after the full decision is computed."""

    summary = payload.get("agent_todo_summary")
    if not isinstance(summary, dict):
        return payload
    compact = dict(payload)
    compact["agent_todo_summary"] = _compact_agent_todo_summary(summary)
    compact["todo_summary_projection"] = {
        "schema_version": QUOTA_CLI_TODO_SUMMARY_COMPACTION_SCHEMA_VERSION,
        "mode": "compact_hot_path",
        "compacted_roles": ["agent"],
        "detail_ref": QUOTA_CLI_TODO_SUMMARY_DETAIL_COMMAND,
    }
    return compact
