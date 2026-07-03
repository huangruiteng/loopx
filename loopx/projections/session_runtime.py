from __future__ import annotations

from typing import Any, Callable, Optional

from ..session_runtime import SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION


SESSION_RUNTIME_READONLY_PROJECTION_KEYS = (
    "session_runtime_readonly_projection",
    "session_runtime_projection",
)

PublicSafeText = Callable[..., Optional[str]]
PublicSafeList = Callable[..., list[str]]


def compact_session_runtime_source(
    source: Any,
    *,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any]:
    if not isinstance(source, dict):
        return {}
    compact: dict[str, Any] = {}
    host_kind = public_safe_compact_text(source.get("host_kind"), limit=80)
    if host_kind:
        compact["host_kind"] = host_kind
    latest_fact_at = public_safe_compact_text(source.get("latest_fact_at"), limit=80)
    if latest_fact_at:
        compact["latest_fact_at"] = latest_fact_at
    source_refs = source.get("source_refs")
    if isinstance(source_refs, dict):
        counts = {
            str(key): len(value)
            for key, value in source_refs.items()
            if isinstance(value, list) and value
        }
        if counts:
            compact["source_ref_counts"] = counts
    return compact


def compact_session_runtime_boundary(
    boundary: Any,
    *,
    public_safe_compact_list: PublicSafeList,
) -> dict[str, Any]:
    if not isinstance(boundary, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "raw_transcript_copied",
        "raw_logs_copied",
        "credentials_copied",
        "runtime_writeback_allowed",
        "runtime_mutation_allowed",
        "raw_material_detected",
    ):
        if field in boundary:
            compact[field] = bool(boundary.get(field))
    raw_keys = public_safe_compact_list(boundary.get("raw_material_key_names"), limit=8)
    if raw_keys:
        compact["raw_material_key_names"] = raw_keys
    return compact


def compact_session_runtime_first_screen(
    first_screen: Any,
    *,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any]:
    if not isinstance(first_screen, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in (
        "waiting_on",
        "first_user_todo",
        "first_agent_todo",
        "latest_validation",
        "latest_blocker",
        "gate_state",
        "recommended_action",
    ):
        value = public_safe_compact_text(first_screen.get(field), limit=260)
        if value:
            compact[field] = value
    for field in ("user_action_required", "agent_can_continue"):
        if field in first_screen:
            compact[field] = bool(first_screen.get(field))
    return compact


def compact_session_runtime_work_lane(
    contract: Any,
    *,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {}
    compact: dict[str, Any] = {}
    lane = public_safe_compact_text(contract.get("lane"), limit=80)
    if lane:
        compact["lane"] = lane
    for field in ("must_attempt_work", "user_gate_blocks_delivery", "monitor_only"):
        if field in contract:
            compact[field] = bool(contract.get(field))
    return compact


def compact_session_runtime_attention_item(
    attention_item: Any,
    *,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any]:
    if not isinstance(attention_item, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in ("kind", "priority", "title", "waiting_on"):
        value = public_safe_compact_text(attention_item.get(field), limit=220)
        if value:
            compact[field] = value
    return compact


def compact_session_runtime_readonly_projection(
    value: Any,
    *,
    public_safe_compact_text: PublicSafeText,
    public_safe_compact_list: PublicSafeList,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if value.get("schema_version") != SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION:
        return None
    compact: dict[str, Any] = {
        "schema_version": SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION,
        "mode": "read_only",
    }
    goal_id = public_safe_compact_text(value.get("goal_id"), limit=120)
    if goal_id:
        compact["goal_id"] = goal_id
    source = compact_session_runtime_source(
        value.get("source"),
        public_safe_compact_text=public_safe_compact_text,
    )
    if source:
        compact["source"] = source
    boundary = compact_session_runtime_boundary(
        value.get("boundary"),
        public_safe_compact_list=public_safe_compact_list,
    )
    if boundary:
        compact["boundary"] = boundary
    first_screen = compact_session_runtime_first_screen(
        value.get("first_screen"),
        public_safe_compact_text=public_safe_compact_text,
    )
    if first_screen:
        compact["first_screen"] = first_screen
    work_lane = compact_session_runtime_work_lane(
        value.get("work_lane_contract"),
        public_safe_compact_text=public_safe_compact_text,
    )
    if work_lane:
        compact["work_lane_contract"] = work_lane
    attention = compact_session_runtime_attention_item(
        value.get("attention_item"),
        public_safe_compact_text=public_safe_compact_text,
    )
    if attention:
        compact["attention_item"] = attention
    return compact


def compact_session_runtime_projection_from_run(
    run: dict[str, Any] | None,
    *,
    public_safe_compact_text: PublicSafeText,
    public_safe_compact_list: PublicSafeList,
) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    for key in SESSION_RUNTIME_READONLY_PROJECTION_KEYS:
        projection = compact_session_runtime_readonly_projection(
            run.get(key),
            public_safe_compact_text=public_safe_compact_text,
            public_safe_compact_list=public_safe_compact_list,
        )
        if projection:
            return projection
    return compact_session_runtime_readonly_projection(
        run,
        public_safe_compact_text=public_safe_compact_text,
        public_safe_compact_list=public_safe_compact_list,
    )
