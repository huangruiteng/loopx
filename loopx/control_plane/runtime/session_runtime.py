from __future__ import annotations

from typing import AbstractSet, Any, Callable, Optional

from ...session_runtime import SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION


SESSION_RUNTIME_READONLY_PROJECTION_KEYS = (
    "session_runtime_readonly_projection",
    "session_runtime_projection",
)

PublicSafeText = Callable[..., Optional[str]]
PublicSafeList = Callable[..., list[str]]
AttentionItemBuilder = Callable[..., dict[str, Any]]
GoalLifecycleFields = Callable[[dict[str, Any], Optional[dict[str, Any]]], dict[str, Any]]


def legacy_runtime_goal_attention(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    readiness_fields: dict[str, Any],
    *,
    attention_item: AttentionItemBuilder,
    goal_lifecycle_fields: GoalLifecycleFields,
    blocking_classifications: AbstractSet[str],
    user_or_controller_classifications: AbstractSet[str],
    codex_ready_classifications: AbstractSet[str],
) -> dict[str, Any] | None:
    if not goal.get("legacy_runtime_goal") or not current_run:
        return None

    goal_id = str(goal.get("id") or "unknown-goal")
    json_exists = bool(current_run.get("json_exists"))
    markdown_exists = bool(current_run.get("markdown_exists"))
    classification = str(current_run.get("classification") or "unknown")
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)

    actionable_classification = (
        classification in blocking_classifications
        or classification in user_or_controller_classifications
        or classification in codex_ready_classifications
    )
    if not actionable_classification and json_exists and markdown_exists:
        return None

    if not json_exists or not markdown_exists:
        severity = "high"
        action = (
            "repair this unregistered runtime goal or preview cleanup with "
            f"`loopx archive-runtime --goal-id {goal_id}` before trusting multi-project status"
        )
    elif classification in blocking_classifications:
        severity = "high"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `loopx archive-runtime --goal-id {goal_id}` "
            "so multi-project status stays authoritative"
        )
    else:
        severity = "action"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `loopx archive-runtime --goal-id {goal_id}` "
            "so multi-project status stays authoritative"
        )

    return attention_item(
        goal_id=goal_id,
        status="unregistered_runtime_goal",
        waiting_on="controller",
        severity=severity,
        recommended_action=action,
        source="run_history",
        **readiness_fields,
        **lifecycle_fields,
    )


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


def session_runtime_status_waiting_on(
    value: Any,
    *,
    monitor_signal_waiting_on: str,
    monitor_only: bool = False,
) -> str:
    waiting_on = str(value or "").strip().lower()
    if waiting_on in {"agent", "codex"}:
        return "codex"
    if waiting_on in {"controller", "human", "operator", "owner", "user", "user_or_controller"}:
        return "user_or_controller"
    if waiting_on in {"runtime", "external_evidence"}:
        return "external_evidence"
    if waiting_on in {"none", "monitor", monitor_signal_waiting_on} or monitor_only:
        return monitor_signal_waiting_on
    return "codex"


def session_runtime_status_label(
    projection: dict[str, Any],
    *,
    public_safe_compact_text: PublicSafeText,
) -> str:
    work_lane = projection.get("work_lane_contract") if isinstance(projection.get("work_lane_contract"), dict) else {}
    lane = public_safe_compact_text(work_lane.get("lane"), limit=80) or "projection"
    return f"session_runtime_{lane}"


def attach_session_runtime_projection(item: dict[str, Any], projection: dict[str, Any]) -> None:
    item["session_runtime_projection"] = projection
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["session_runtime_projection"] = projection


def session_runtime_projection_attention(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    projection: dict[str, Any],
    *,
    public_safe_compact_text: PublicSafeText,
    attention_item: AttentionItemBuilder,
    goal_lifecycle_fields: GoalLifecycleFields,
    monitor_signal_waiting_on: str,
) -> dict[str, Any]:
    first_screen = projection.get("first_screen") if isinstance(projection.get("first_screen"), dict) else {}
    work_lane = projection.get("work_lane_contract") if isinstance(projection.get("work_lane_contract"), dict) else {}
    boundary = projection.get("boundary") if isinstance(projection.get("boundary"), dict) else {}
    monitor_only = bool(work_lane.get("monitor_only"))
    waiting_on = session_runtime_status_waiting_on(
        first_screen.get("waiting_on"),
        monitor_signal_waiting_on=monitor_signal_waiting_on,
        monitor_only=monitor_only,
    )
    recommended_action = public_safe_compact_text(
        first_screen.get("recommended_action") or (current_run or {}).get("recommended_action"),
        limit=320,
    ) or "inspect the session-runtime projection and choose the next safe action"
    severity = "watch" if waiting_on in {"external_evidence", monitor_signal_waiting_on} else "action"
    if boundary.get("raw_material_detected"):
        severity = "high"
    item = attention_item(
        goal_id=str(goal.get("id") or projection.get("goal_id") or "unknown-goal"),
        status=session_runtime_status_label(
            projection,
            public_safe_compact_text=public_safe_compact_text,
        ),
        waiting_on=waiting_on,
        severity=severity,
        recommended_action=recommended_action,
        source="session_runtime_projection",
        **goal_lifecycle_fields(goal, current_run),
    )
    attach_session_runtime_projection(item, projection)
    return item
