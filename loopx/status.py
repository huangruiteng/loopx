from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
from typing import Any

from .benchmark_adapters.skillsbench_signals import (
    build_skillsbench_solution_quality_signals,
)
from .control_plane import compact_control_plane_policy, control_plane_policy_summary
from .contract import check_contract
from .delivery_batch_scale import (
    SMALL_DELIVERY_BATCH_SCALES as STRUCTURED_SMALL_DELIVERY_BATCH_SCALES,
    UNKNOWN_DELIVERY_BATCH_SCALE,
    DeliveryBatchScale,
    normalize_delivery_batch_scale,
)
from .delivery_outcome import (
    DELIVERY_OUTCOME_NOT_CONFIGURED,
    DELIVERY_OUTCOME_UNKNOWN,
    DeliveryOutcome,
    PROGRESS_DELIVERY_OUTCOMES,
    delivery_turn_kind_for_run,
    normalize_delivery_outcome,
)
from .doctor import (
    PROMOTION_READINESS_CLASSIFICATIONS,
    PROMOTION_READINESS_FRESHNESS_HOURS,
    add_promotion_readiness_freshness,
    latest_promotion_readiness_event,
)
from .execution_profile import (
    compact_execution_profile,
    execution_profile_outcome_floor,
    execution_profile_summary,
)
from .event_sourced_state import (
    AppendOnlyStateEventStore,
    StateEventError,
    build_state_projection,
    render_active_state_sections,
)
from .frontstage import build_goal_channel_projection
from .handoff_budget import handoff_budget_contract
from .history import collect_history, load_registry
from .history import STATUS_NEUTRAL_CLASSIFICATIONS as HISTORY_STATUS_NEUTRAL_CLASSIFICATIONS
from .interface_budget import interface_budget_cadence_for_runs
from .long_task_cadence import build_long_task_cadence_hint, long_task_cadence_hint_summary
from .materials import extract_review_materials
from .operator_gate import DEFAULT_OPERATOR_GATE, default_operator_question, normalize_operator_question
from .orchestration import compact_orchestration_policy, orchestration_policy_summary
from .paths import global_registry_path, resolve_runtime_root
from .projections.task_graph import (
    TASK_GRAPH_MAX_USER_GATE_NODES,
    TASK_GRAPH_PROJECTION_SCHEMA_VERSION,
    TASK_GRAPH_SOURCE_OF_TRUTH,
    build_task_graph_projection as _build_task_graph_projection_read_model,
)
from .projections.project_asset import (
    LOCAL_PATH_SURFACE_PATTERN,
    PROJECT_ASSET_TODO_PROJECTION_GAP_SCHEMA_VERSION,
    SECRET_LIKE_SURFACE_PATTERN,
    TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
    TODO_PROJECTION_VIEW_SCHEMA_VERSION,
    build_project_asset,
    completed_todo_archive_warning,
    project_asset_handoff_check_projection,
    project_asset_latest_validation,
    project_asset_quota_summary,
    project_asset_summary_is_public_safe,
    project_asset_todo_projection_metadata,
    project_asset_todo_projection_gap,
)
from .promotion_gate import build_promotion_gate
from .quota import quota_status, quota_with_handoff_outcome_floor
from .registry import registry_goals
from .renderers.status_markdown import (
    append_attention_queue_item_header_markdown as _append_attention_queue_item_header_markdown,
    append_attention_queue_summary_markdown as _append_attention_queue_summary_markdown,
    append_decision_freshness_summary_markdown as _append_decision_freshness_summary_markdown,
    append_event_ledger_summary_markdown as _append_event_ledger_summary_markdown,
    append_human_reward_markdown as _append_human_reward_markdown,
    append_operator_gate_resume_contract_markdown as _append_operator_gate_resume_contract_markdown,
    append_promotion_gate_markdown as _append_promotion_gate_markdown,
    append_promotion_readiness_summary_markdown as _append_promotion_readiness_summary_markdown,
    append_usage_summary_markdown as _append_usage_summary_markdown,
    authority_registry_markdown_summary as _authority_registry_markdown_summary,
    goals_by_id as _goals_by_id,
    markdown_scalar as _markdown_scalar,
)
from .rollout_event_log import load_rollout_events, rollout_event_log_path
from .session_runtime import SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION
from .state_projection import (
    active_state_next_action_entries,
    actions_are_projection_aligned,
    next_action_projection_warning,
    state_projection_gap_warning,
)
from .todo_contract import (
    TODO_RESUME_KIND_PR_MERGED,
    TODO_RESUME_KIND_TODO_DONE,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    TODO_TASK_PATTERN,
    build_todo_id,
    normalize_todo_action_kind,
    normalize_required_capabilities,
    normalize_target_capabilities,
    normalize_required_write_scopes,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_global_gate,
    normalize_todo_id,
    normalize_todo_no_followup,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_todo_status,
    normalize_todo_task_class,
    parse_todo_metadata_line,
    todo_done_for_status,
    todo_status_from_marker,
)
from .todo_handoff_gate import build_todo_handoff_gate_states
from .todo_projection import (
    todo_claimed_visibility_items as projection_todo_claimed_visibility_items,
    todo_item_expires_at as projection_todo_item_expires_at,
    todo_item_is_actionable_open as projection_todo_item_is_actionable_open,
    todo_item_is_deferred as projection_todo_item_is_deferred,
    todo_item_is_due_monitor as projection_todo_item_is_due_monitor,
    todo_item_is_expired_monitor as projection_todo_item_is_expired_monitor,
    todo_item_missing_monitor_schedule as projection_todo_item_missing_monitor_schedule,
    todo_item_next_due_at as projection_todo_item_next_due_at,
    todo_item_task_class as projection_todo_item_task_class,
    todo_priority_parts as projection_todo_priority_parts,
    todo_priority_rank as projection_todo_priority_rank,
    todo_projection_sort_key as projection_todo_projection_sort_key,
)


CODEX_READY_CLASSIFICATIONS = {
    "controller_opted_in_waiting_for_run",
    "design_next_experiment",
    "inspect_eval_result",
    "inspect_result",
    "needs_more_read_only_evidence",
    "needs_validation",
    "public_harness_healthy",
    "read_only_project_map",
    "run_validation",
    "state_refreshed",
    "operator_gate_approved",
    "monitor_todo_repeat_dedupe_deployed",
}
STATUS_NEUTRAL_CLASSIFICATIONS = HISTORY_STATUS_NEUTRAL_CLASSIFICATIONS
STATE_EVENT_LOG_BASENAME = "events.jsonl"
STATUS_CONTROL_PLANE_CONTEXT_LIMIT = 20
AGENT_LANE_PROGRESS_SCOPE = "agent_lane"
HANDOFF_READY_CLASSIFICATIONS = {
    "operator_gate_approved",
    "controller_opted_in_waiting_for_run",
}
DREAMING_ADVISORY_CLASSIFICATIONS = {
    "dreaming_exploration_proposal",
    "dreaming_memory_consolidation",
    "dreaming_refactor_warning",
    "dreaming_archive_suggestion",
}
USER_OR_CONTROLLER_CLASSIFICATIONS = {
    "needs_human_reward",
    "needs_controller_opt_in",
    "needs_user_relay",
    "ready_for_controller_opt_in",
    "ready_for_user_relay",
    "operator_gate_deferred",
    "operator_gate_rejected",
} | DREAMING_ADVISORY_CLASSIFICATIONS
REGISTRY_WAITING_ON_OVERRIDES = {
    "user_or_controller",
    "controller",
    "codex",
    "external_evidence",
}
LEGACY_EXTERNAL_EVIDENCE_CLASSIFICATION_PREFIXES = (
    "await_",
    "external_evidence_observation_",
)
MONITOR_SIGNAL_WAITING_ON = "monitor_signal"
MONITOR_DISPLAY_SCHEMA_VERSION = "monitor_quiet_display_v0"
MONITOR_DISPLAY_STOP_CONDITION = (
    "stop until a material monitor transition, regression, or concrete blocker appears"
)
MONITOR_DISPLAY_FALLBACK_ACTION = (
    "No immediate agent work; keep the monitor quiet until a material monitor "
    "transition, regression, or concrete blocker appears."
)
BLOCKING_CLASSIFICATIONS = {
    "blocked_by_safety",
}
BENCHMARK_VALIDATION_NEUTRAL_FALSE_FIELDS = {
    "case_success_claimed",
    "case_solution_not_required_for_probe",
    "official_case_success",
    "official_verifier_validation_present",
    "native_goal_worker_route",
    "native_goal_worker_connected",
    "native_goal_worker_trace_dir_present",
    "native_goal_worker_public_trace_read",
    "native_goal_worker_trace_observed",
    "remote_command_file_bridge_consumed_by_solver",
    "remote_command_file_bridge_solver_public_trace_read",
    "loopx_controller_trace_present",
    "leaderboard_claim_allowed",
    "official_score_claim_allowed",
    "probe_contract_result_present",
    "assisted_collaboration_claim_allowed",
}
EVENT_LEDGER_CLASSES = (
    "accounting",
    "decision",
    "evidence",
    "state",
    "work",
)
EVENT_LEDGER_PROXY_NOTE = "append-only run-history projection; compact event-class counts only"
BENCHMARK_RUN_SCHEMA_VERSION = "benchmark_run_v0"
BENCHMARK_RESULT_SCHEMA_VERSION = "benchmark_result_v0"
BENCHMARK_COMPARISON_SCHEMA_VERSION = "benchmark_comparison_v0"
BENCHMARK_COMPARISON_DECISION_SCHEMA_VERSION = "benchmark_comparison_decision_note_v0"
BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION = "benchmark_baseline_failure_gate_v0"
BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION = "benchmark_learning_ledger_v0"
WORKER_BRIDGE_INGEST_HEALTH_SCHEMA_VERSION = "worker_bridge_ingest_health_note_v0"
BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION = "benchmark_experiment_report_v0"
BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION = "benchmark_experiment_report_readiness_note_v0"
BENCHMARK_EXPERIMENT_REPORT_REPLAY_DECISION_SCHEMA_VERSION = "benchmark_experiment_report_replay_decision_v0"
ACTIVE_USER_ASSISTED_PILOT_SCHEMA_VERSION = "active_user_assisted_pilot_v0"
OPERATOR_SIMULATOR_RUN_SCHEMA_VERSION = "operator_simulator_run_v0"
CONTROL_PLANE_SCORE_SCHEMA_VERSION = "control_plane_score_core_v0"
CONTROL_PLANE_SCORE_COMPONENTS = (
    "restartability",
    "stale_state_avoidance",
    "evidence_discipline",
    "boundary_safety",
    "writeback_quality",
    "gate_compliance",
    "failure_attribution",
    "overhead",
)
MAX_BENCHMARK_RUN_TRIALS = 3
MAX_BENCHMARK_RUN_LIST_ITEMS = 5
STATUS_CONTRACT_SCHEMA_VERSION = 2
MINIMUM_DASHBOARD_STATUS_CONTRACT_SCHEMA_VERSION = 2
STATUS_CONTRACT_RELOAD_HINT = "scripts/macos-dashboard-launchagent.sh restart"
STATUS_CONTRACT_SIGNAL_LIMIT = 3
MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION = "monitor_writeback_contract_v0"
TODO_INDEX_SCHEMA_VERSION = "todo_index_v0"
TODO_INDEX_ITEM_SCHEMA_VERSION = "todo_index_item_v0"
DECISION_FRESHNESS_WINDOW_DAYS = 7
DECISION_FRESHNESS_ITEM_LIMIT = 12
DECISION_FRESHNESS_PROXY_NOTE = (
    "checkpointed decision freshness projection; rebase old decisions at the decision point before reuse"
)
PROMOTION_READINESS_PROXY_NOTE = (
    "canary promotion-readiness projection from append-only run history; exact evidence stays in run artifacts"
)
DECISION_FRESHNESS_CLASSIFICATION_PREFIXES = (
    "human_reward",
    "reward_overlay",
)
EVENT_LEDGER_DECISION_CLASSIFICATIONS = USER_OR_CONTROLLER_CLASSIFICATIONS | {
    "operator_gate_approved",
}
EVENT_LEDGER_STATE_CLASSIFICATIONS = {
    "state_refreshed",
    "public_harness_healthy",
}
EVENT_LEDGER_EVIDENCE_CLASSIFICATIONS = {
    "inspect_eval_result",
    "inspect_result",
    "needs_more_read_only_evidence",
    "read_only_project_map",
}
EVENT_LEDGER_EVIDENCE_HINTS = (
    "artifact",
    "blocker",
    "ci",
    "data",
    "deploy",
    "done",
    "eval",
    "evidence",
    "failure",
    "fail",
    "metric",
    "monitor",
    "validation",
)
DELIVERY_BATCH_SCALE_TEST_ONLY_CLASSIFICATION_HINTS = (
    "_test",
    "_smoke",
    "readiness_test",
    "integrity_test",
)
DELIVERY_BATCH_SCALE_MULTI_SURFACE_CLASSIFICATION_HINTS = (
    "batch",
    "cross_benchmark",
    "downstream_pack",
    "matrix",
    "owner_handoff_consumer",
)
DELIVERY_BATCH_SCALE_IMPLEMENTATION_CLASSIFICATION_HINTS = (
    "adapter",
    "builder",
    "consumer",
    "implementation",
    "runner",
)
SMALL_DELIVERY_BATCH_SCALES = {
    *(scale.value for scale in STRUCTURED_SMALL_DELIVERY_BATCH_SCALES),
    UNKNOWN_DELIVERY_BATCH_SCALE,
}
CONNECTED_ADAPTER_STATUSES = {
    "connected",
    "connected-read-only",
    "pre-tick-runnable",
}
CONNECTED_DELIVERY_ADAPTER_STATUSES = {
    "connected-delivery",
}
SOURCE_REGISTRY_SHADOW_FINDINGS = {
    "source_registry_missing",
    "stale_source_registry",
}
PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION = (
    "先在 LoopX 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run"
)
RUN_COMPACT_FIELDS = (
    "generated_at",
    "run_id",
    "goal_id",
    "parent_run_id",
    "spawned_by_goal_id",
    "agent_role",
    "classification",
    "agent_id",
    "agent_lane",
    "progress_scope",
    "delivery_batch_scale",
    "delivery_outcome",
    "lifecycle_phase",
    "lifecycle_flags",
    "recommended_action",
    "health_check",
    "result_status",
    "approval_state",
    "active_task_count",
    "active_priorities",
    "cache_check",
    "project_map",
    "json_exists",
    "markdown_exists",
)
SESSION_RUNTIME_READONLY_PROJECTION_KEYS = (
    "session_runtime_readonly_projection",
    "session_runtime_projection",
)
USAGE_PROXY_NOTE = "run-history proxy; excludes token counts and raw thread logs"
HUMAN_REWARD_COMPACT_FIELDS = (
    "recorded_at",
    "decision",
    "reward",
    "reason_summary",
    "follow_up",
    "lesson",
)
OPERATOR_GATE_COMPACT_FIELDS = (
    "recorded_at",
    "gate",
    "decision",
    "operator_question",
    "reason_summary",
    "follow_up",
    "agent_command",
)
OPERATOR_GATE_RESUME_CONTRACT_COMPACT_FIELDS = (
    "version",
    "goal_id",
    "run_id",
    "gate_id",
    "created_state_ref",
    "created_policy_version",
    "allowed_decisions",
    "operator_decision",
    "latest_state_ref",
    "freshness_check",
    "precondition_check",
    "migration_or_rebase_result",
    "resulting_action",
    "validation_after_resume",
)
CONTROLLER_READINESS_COMPACT_FIELDS = (
    "classification",
    "read_only_observer_ready",
    "decision_advisor_ready",
    "write_controller_ready",
    "missing_gates",
    "review_judgment",
    "next_handoff_condition",
)
CONTROLLER_READINESS_GATE_FIELDS = (
    "id",
    "ok",
    "review",
)
LIFECYCLE_PRIORITY = (
    "controller_ready",
    "reward_judged",
    "operator_approved",
    "controller_gated",
    "operator_gated",
    "adapter_inspected",
    "mapped",
    "refreshed",
    "connected",
    "registered",
    "planned",
    "run_recorded",
)
SECTION_HEADING_PATTERN = re.compile(r"^##+\s+(.+?)\s*$")
USER_TODO_HEADER_MARKERS = (
    "user todo",
    "owner review reading queue",
    "owner reading queue",
)
AGENT_TODO_HEADER_MARKERS = (
    "agent todo",
    "codex todo",
    "project agent todo",
)
MAX_STATUS_TODOS_PER_ROLE = 12
MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE = MAX_STATUS_TODOS_PER_ROLE
MAX_PROJECT_ASSET_TODO_ITEMS = 3
MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS = 8
MAX_TODO_VISIBILITY_LANE_ITEMS = 16
MAX_DEFERRED_TODO_VISIBILITY_ITEMS = 8
MAX_MONITOR_DUE_ITEMS = 1
MAX_ISSUE_META_SURFACE_ITEMS = 8
MAX_ISSUE_META_LABELS = 8
MAX_TODO_INDEX_ITEMS = 240
MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL = 500
PR_MERGED_EVENT_KINDS = {
    "pr_merge",
    "pr_merged",
    "pull_request_merge",
    "pull_request_merged",
}
PR_REF_PATTERN = re.compile(
    r"^(?:(?P<repo>[a-z0-9_.-]{1,80}/[a-z0-9_.-]{1,100}))?#(?P<number>[1-9][0-9]{0,8})$"
)
GITHUB_PULL_URL_PATTERN = re.compile(
    r"^https://github\.com/(?P<repo>[a-z0-9_.-]{1,80}/[a-z0-9_.-]{1,100})/pull/(?P<number>[1-9][0-9]{0,8})/?$",
    re.IGNORECASE,
)
ISSUE_META_SURFACE_SCHEMA_VERSION = "issue_meta_surface_v0"
ISSUE_META_SURFACE_ITEM_SCHEMA_VERSION = "issue_meta_surface_item_v0"
MAX_DEPENDENCY_BLOCKERS = 4
MAX_AUTONOMOUS_BACKLOG_CANDIDATES = 6
MAX_SUBAGENT_ACTIVITY_ITEMS = 5
MAX_SUBAGENT_SCOPE_ITEMS = 4
MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS = 3
MAX_AUTONOMOUS_REPLAN_TRIGGERS = 3
AUTONOMOUS_REPLAN_STALL_THRESHOLD = 2
DEAD_MONITOR_REPEAT_THRESHOLD = 6
AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD = 20
AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK = 30
AUTONOMOUS_PRIORITY_PATTERN = re.compile(r"^\s*\[(P[0-4][^\]]*)\]\s*(.+)$", re.IGNORECASE)
BACKLOG_HYGIENE_SECTION_HEADINGS = ("Next Action", "Operating Lessons")
BACKLOG_HYGIENE_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
ISSUE_META_SURFACE_SECTION_HEADINGS = ("Issue Meta Surface", "Issue/PR Meta Surface")
ISSUE_META_SURFACE_FIELD_PATTERN = re.compile(
    r"(?P<key>[a-z_][a-z0-9_-]*)=(?P<value>\"[^\"]+\"|'[^']+'|[^\s]+)"
)
BACKLOG_HYGIENE_HINT_PATTERN = re.compile(
    r"(?i)(?:\[p[0-4]\]|todo|backlog|follow[- ]?up|queue|audit|regression|smoke|cadence|mirror|monitor|sub-?agent|待办|回归|审计|修复|检查|推进)"
)
AUTONOMOUS_REPLAN_SCHEMA_VERSION = "autonomous_replan_obligation_v0"
DEAD_MONITOR_REPEAT_SCHEMA_VERSION = "dead_monitor_repeat_v0"
AUTONOMOUS_REPLAN_SECTION_HEADINGS = (
    "Next Action",
    "Operating Lessons",
)
AUTONOMOUS_REPLAN_TRIGGER_PATTERNS = (
    (
        "periodic_review",
        re.compile(r"(?i)(?:periodic review|periodic replan|review cadence|规划复盘|周期复盘|每几十轮)"),
    ),
    (
        "no_progress_streak",
        re.compile(r"(?i)(?:no[- ]?progress|stalled?|stall streak|没有实质进展|停转|连续[^。；;]*无进展)"),
    ),
    (
        "repeated_action_loop",
        re.compile(r"(?i)(?:repeated[- ]?action|action loop|same action|looped|重复动作|循环观察|反复观察)"),
    ),
    (
        "phase_transition",
        re.compile(r"(?i)(?:phase transition|next phase|stage transition|readiness .*done|阶段切换|进入下一阶段)"),
    ),
    (
        "backlog_mismatch",
        re.compile(r"(?i)(?:backlog mismatch|todo mismatch|next action mismatch|todo.*淹没|待办.*不一致)"),
    ),
    (
        "evidence_contradiction",
        re.compile(r"(?i)(?:evidence contradiction|contradictory evidence|stale evidence|stale latest-run|证据矛盾|状态矛盾)"),
    ),
    (
        "explicit_replan",
        re.compile(r"(?i)(?:autonomous replan|replan obligation|planning[- ]?trigger|重新规划|重规划|规划触发)"),
    ),
)
AUTONOMOUS_RUN_HISTORY_PROGRESS_OUTCOMES = PROGRESS_DELIVERY_OUTCOMES
AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS = {
    "quota_slot_spent",
    "quota_slot_voided",
    "delivery_completion_spend_accounted_v0",
}
AUTONOMOUS_RUN_HISTORY_STALL_PATTERN = re.compile(
    r"(?i)(?:monitor|observe|observation|poll|watch|quiet|no[-_ ]?op|no[-_ ]?progress|stalled?|unchanged|dependency|停转|无进展|重复|反复|观察|轮询)"
)
TODO_ARCHIVE_HEADER_MARKERS = (
    "todo archive",
    "work archive",
    "completed archive",
    "completed work",
    "完成归档",
    "待办归档",
)
TODO_ITEM_SCHEMA_VERSION = "todo_item_v0"
def normalize_todo_text(text: str, *, limit: int = 500) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def public_safe_compact_text(value: Any, *, limit: int = 220) -> str | None:
    text = normalize_todo_text(str(value or ""), limit=limit)
    if not text:
        return None
    if LOCAL_PATH_SURFACE_PATTERN.search(text) or SECRET_LIKE_SURFACE_PATTERN.search(text):
        return None
    return text


def public_safe_compact_list(value: Any, *, limit: int = MAX_SUBAGENT_SCOPE_ITEMS) -> list[str]:
    values = value if isinstance(value, list) else [value] if value else []
    result: list[str] = []
    for item in values:
        text = public_safe_compact_text(item, limit=160)
        if not text:
            continue
        result.append(text)
        if len(result) >= limit:
            break
    return result


def compact_session_runtime_source(source: Any) -> dict[str, Any]:
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


def compact_session_runtime_boundary(boundary: Any) -> dict[str, Any]:
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


def compact_session_runtime_first_screen(first_screen: Any) -> dict[str, Any]:
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


def compact_session_runtime_work_lane(contract: Any) -> dict[str, Any]:
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


def compact_session_runtime_attention_item(attention_item: Any) -> dict[str, Any]:
    if not isinstance(attention_item, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in ("kind", "priority", "title", "waiting_on"):
        value = public_safe_compact_text(attention_item.get(field), limit=220)
        if value:
            compact[field] = value
    return compact


def compact_session_runtime_readonly_projection(value: Any) -> dict[str, Any] | None:
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
    source = compact_session_runtime_source(value.get("source"))
    if source:
        compact["source"] = source
    boundary = compact_session_runtime_boundary(value.get("boundary"))
    if boundary:
        compact["boundary"] = boundary
    first_screen = compact_session_runtime_first_screen(value.get("first_screen"))
    if first_screen:
        compact["first_screen"] = first_screen
    work_lane = compact_session_runtime_work_lane(value.get("work_lane_contract"))
    if work_lane:
        compact["work_lane_contract"] = work_lane
    attention = compact_session_runtime_attention_item(value.get("attention_item"))
    if attention:
        compact["attention_item"] = attention
    return compact


def compact_session_runtime_projection_from_run(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    for key in SESSION_RUNTIME_READONLY_PROJECTION_KEYS:
        projection = compact_session_runtime_readonly_projection(run.get(key))
        if projection:
            return projection
    return compact_session_runtime_readonly_projection(run)


def _compact_numeric_map(value: Any, *, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    source = value
    selected_keys = keys or tuple(str(key) for key in source.keys())
    compact: dict[str, Any] = {}
    for key in selected_keys:
        raw = source.get(key)
        if isinstance(raw, bool) or raw is None:
            continue
        if isinstance(raw, (int, float)):
            compact[key] = raw
            continue
        try:
            if isinstance(raw, str) and raw.strip():
                compact[key] = float(raw) if "." in raw else int(raw)
        except ValueError:
            continue
    return compact


def _compact_loopx_command_records(value: Any, *, limit: int = 128) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    allowed_subcommands = {
        "quota should-run",
        "todo claim",
        "todo update",
        "todo complete",
        "refresh-state",
        "quota spend-slot",
        "status",
        "diagnose",
    }
    records: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        subcommand = public_safe_compact_text(item.get("subcommand"), limit=80)
        if subcommand not in allowed_subcommands:
            continue
        record: dict[str, str] = {"subcommand": subcommand}
        todo_id = public_safe_compact_text(item.get("todo_id"), limit=100)
        if todo_id and re.match(r"^todo_[A-Za-z0-9_-]{6,80}$", todo_id):
            record["todo_id"] = todo_id
        goal_id = public_safe_compact_text(item.get("goal_id"), limit=140)
        if goal_id and re.match(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,120}$", goal_id):
            record["goal_id"] = goal_id
        records.append(record)
        if len(records) >= limit:
            break
    return records


def _compact_benchmark_case_event_timeline(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    events: list[dict[str, Any]] = []
    for raw_event in value.get("events", []):
        if not isinstance(raw_event, dict):
            continue
        event: dict[str, Any] = {}
        for field in ("phase", "event", "status"):
            text = public_safe_compact_text(raw_event.get(field), limit=120)
            if text:
                event[field] = text
        if not {"phase", "event", "status"} <= set(event):
            continue
        for field in (
            "execution_style",
            "agent_operation_trace_status",
            "host_local_acp_bridge_progress_status",
            "host_local_acp_bridge_progress_signal_source",
            "last_decision",
            "recovery_stage",
            "recovery_exception_type",
            "runner_failure_class",
            "official_score_status",
            "score_failure_attribution",
        ):
            text = public_safe_compact_text(raw_event.get(field), limit=140)
            if text:
                event[field] = text
        for field in (
            "required",
            "initialized_before_agent",
            "consumed_by_solver",
            "official_score_passed",
            "selected_todo_completed_observed",
            "quota_spend_missing_after_repeated_complete",
        ):
            if isinstance(raw_event.get(field), bool):
                event[field] = raw_event[field]
        for field in (
            "index",
            "checkpoint_count",
            "state_read_count",
            "state_write_count",
            "solver_operation_count",
            "solver_probe_ready_count",
            "trajectory_event_count",
            "trajectory_round_count",
            "trajectory_tool_call_count",
            "acp_protocol_tool_call_count",
            "agent_bridge_request_count",
            "agent_bridge_task_facing_operation_count",
            "action_decision_count",
            "initial_prompt_count",
            "followup_prompt_count",
            "stop_decision_count",
            "max_rounds_budget",
            "host_local_idle_no_task_output_progress_streak",
            "host_local_idle_no_task_output_progress_streak_threshold",
            "final_round",
            "recovery_delta_events",
            "recovery_delta_tool_calls",
            "benchflow_agent_timeout_effective_sec",
            "local_codex_exec_timeout_sec",
            "todo_closeout_count",
            "refresh_state_count",
            "quota_spend_slot_count",
            "selected_todo_complete_count",
            "selected_todo_duplicate_complete_count",
            "agent_todo_complete_unique_todo_count",
            "non_selected_todo_complete_count",
            "todo_complete_without_todo_id_count",
        ):
            raw = raw_event.get(field)
            if isinstance(raw, int) and not isinstance(raw, bool):
                event[field] = max(0, raw)
        for field in ("best_round_reward", "official_score_value"):
            raw = raw_event.get(field)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                event[field] = raw
        labels = public_safe_compact_list(
            raw_event.get("failure_attribution_labels"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if labels:
            event["failure_attribution_labels"] = labels
        events.append(event)

    if not events:
        return {}

    compact: dict[str, Any] = {
        "schema_version": "skillsbench_case_event_timeline_v0",
        "source": "compact_public_signals",
        "raw_material_recorded": False,
        "event_count": len(events),
        "events": events[:12],
    }
    return compact


def _compact_goal_start_todo_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in ("raw_material_recorded",):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "completed_todo_id_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    for field in ("selected_p0_todo_id", "todo_identity_attribution"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(value.get("planned_todo_ids"), limit=8)
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    completed_ids = public_safe_compact_list(value.get("completed_todo_ids"), limit=8)
    if completed_ids:
        compact["completed_todo_ids"] = completed_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=8,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    planned_todos: list[dict[str, Any]] = []
    source_todos = value.get("planned_todos")
    if isinstance(source_todos, list):
        for item in source_todos[:8]:
            if not isinstance(item, dict):
                continue
            todo: dict[str, Any] = {}
            for field in ("todo_id", "role", "status", "text_public_safe"):
                text = public_safe_compact_text(item.get(field), limit=180)
                if text:
                    todo[field] = text
            for field in ("claim_count", "update_count", "complete_count"):
                raw = item.get(field)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    todo[field] = max(0, raw)
            if todo:
                planned_todos.append(todo)
    if planned_todos:
        compact["planned_todos"] = planned_todos
    return compact


def _compact_goal_start_product_mode_control_score(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "raw_material_recorded",
        "goal_start_plan_observed",
        "planner_before_todo_write",
        "same_priority_order_preserved",
        "selected_todo_claimed",
        "selected_todo_updated_before_solver",
        "selected_todo_completed_before_spend",
        "selected_todo_completed_observed",
        "selected_todo_spend_observed",
        "non_selected_todos_preserved_open_or_deferred",
        "quota_spend_missing_after_repeated_complete",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "component_count",
        "satisfied_component_count",
        "planned_todo_count",
        "planned_todo_count_expected",
        "planned_p0_count",
        "premature_done_signal_count",
        "agent_todo_claim_count",
        "agent_todo_update_count",
        "agent_todo_complete_count",
        "agent_todo_complete_unique_todo_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
        "agent_quota_spend_slot_count",
        "driver_todo_claim_count",
        "driver_todo_update_count",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool):
            compact[field] = max(0, raw)
    score = value.get("score")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        compact["score"] = float(score)
    for field in ("selected_p0_todo_id", "premature_done_stop_reason"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    planned_ids = public_safe_compact_list(value.get("planned_todo_ids"), limit=8)
    if planned_ids:
        compact["planned_todo_ids"] = planned_ids
    planned_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=8,
    )
    if planned_texts:
        compact["planned_todo_texts_public_safe"] = planned_texts
    snapshot = _compact_goal_start_todo_snapshot(value.get("goal_start_todo_snapshot"))
    if snapshot:
        compact["goal_start_todo_snapshot"] = snapshot
    return compact


def _benchmark_case_timeline_events_by_name(
    timeline: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    events = timeline.get("events") if isinstance(timeline.get("events"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if not isinstance(event, dict):
            continue
        name = public_safe_compact_text(event.get("event"), limit=120)
        if name and name not in result:
            result[name] = event
    return result


def _benchmark_positive_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 0


def _benchmark_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def build_skillsbench_post_run_debug_gate(
    run: dict[str, Any],
) -> dict[str, Any]:
    """Build the public-safe SkillsBench post-run debug gate packet."""

    if not isinstance(run, dict):
        return {}
    benchmark_id = public_safe_compact_text(run.get("benchmark_id"), limit=120) or ""
    timeline = _compact_benchmark_case_event_timeline(run.get("case_event_timeline"))
    if not benchmark_id.startswith("skillsbench"):
        return {}

    counters = (
        run.get("interaction_counters")
        if isinstance(run.get("interaction_counters"), dict)
        else {}
    )
    lifecycle = (
        run.get("product_mode_lifecycle_contract")
        if isinstance(run.get("product_mode_lifecycle_contract"), dict)
        else {}
    )
    official = (
        run.get("official_task_score")
        if isinstance(run.get("official_task_score"), dict)
        else {}
    )
    runner_failure = (
        run.get("runner_failure")
        if isinstance(run.get("runner_failure"), dict)
        else {}
    )
    verifier_artifact_recovery = (
        run.get("verifier_reward_artifact_recovery")
        if isinstance(run.get("verifier_reward_artifact_recovery"), dict)
        else {}
    )
    events = _benchmark_case_timeline_events_by_name(timeline)
    missing_fields: list[str] = []
    if not timeline:
        missing_fields.append("case_event_timeline")

    product_mode_required = bool(
        run.get("product_mode") is True
        or counters.get("product_mode") is True
        or lifecycle.get("required") is True
    )
    required_events = [
        "controller_decision_loop",
        "official_score_closeout",
    ]
    if product_mode_required:
        required_events.extend(
            [
                "case_goal_state_init",
                "orchestrated_loopx_lifecycle",
                "remote_command_bridge_consumption",
                "task_facing_activity",
                "agent_bridge_closeout",
            ]
        )
    for event_name in required_events:
        if timeline and event_name not in events:
            missing_fields.append(f"case_event_timeline.events.{event_name}")

    official_event = events.get("official_score_closeout", {})
    closeout_event = events.get("agent_bridge_closeout", {})
    controller_event = events.get("controller_decision_loop", {})
    driver_event = events.get("orchestrated_loopx_lifecycle", {})
    recovery_event = events.get("timeout_or_failure_closeout", {})
    activity_event = events.get("task_facing_activity", {})

    official_status = (
        public_safe_compact_text(
            official_event.get("status") or run.get("official_score_status"),
            limit=120,
        )
        or "unknown"
    )
    official_passed = official.get("passed")
    if not isinstance(official_passed, bool):
        official_passed = official_event.get("official_score_passed")
    official_score_value = official.get("value")
    if not isinstance(official_score_value, (int, float)) or isinstance(
        official_score_value,
        bool,
    ):
        official_score_value = run.get("official_score")
    closeout_status = public_safe_compact_text(
        closeout_event.get("status"),
        limit=120,
    ) or ("not_required" if not product_mode_required else "unknown")
    activity_status = (
        public_safe_compact_text(activity_event.get("status"), limit=120)
        or "unknown"
    )
    recovery_status = (
        public_safe_compact_text(recovery_event.get("status"), limit=120)
        or "not_observed"
    )
    agent_operation_trace_missing = bool(
        activity_status == "missing_agent_operation_trace"
        or lifecycle.get("agent_operation_trace_missing") is True
    )
    runner_recovery_blocked = recovery_status in {
        "user_loop_recovery_triggered",
        "runner_failure_recorded",
    }
    verifier_artifact_success = bool(
        verifier_artifact_recovery.get("passed") is True
        and (
            verifier_artifact_recovery.get("status")
            == "official_score_recovered_from_verifier_reward_artifact"
        )
    )
    lifecycle_required = lifecycle.get("required") is True or product_mode_required
    lifecycle_state_read_count = _benchmark_positive_int(
        lifecycle.get("state_read_count")
    ) or _benchmark_positive_int(driver_event.get("state_read_count"))
    lifecycle_state_write_count = _benchmark_positive_int(
        lifecycle.get("state_write_count")
    ) or _benchmark_positive_int(driver_event.get("state_write_count"))
    lifecycle_satisfied = lifecycle.get("satisfied")
    closeout_satisfied = bool(
        closeout_status in {"satisfied", "not_required"}
        or lifecycle.get("closeout_satisfied") is True
    )
    timeline_lifecycle_satisfied = bool(
        closeout_satisfied
        and (
            not lifecycle_required
            or (lifecycle_state_read_count > 0 and lifecycle_state_write_count > 0)
        )
    )
    effective_lifecycle_satisfied = bool(
        lifecycle_satisfied is True or timeline_lifecycle_satisfied
    )
    case_closeout_complete = bool(
        (
            not missing_fields
            and official_passed is True
            and verifier_artifact_success
        )
        or (
            not missing_fields
            and (not lifecycle_required or effective_lifecycle_satisfied)
            and official_status not in {"unknown", ""}
            and not agent_operation_trace_missing
            and not (official_status == "missing" and runner_recovery_blocked)
        )
    )

    first_blocker = "none"
    attribution_layer = "solution_level_unknown"
    if missing_fields:
        attribution_layer = "incomplete_public_debug_packet"
        first_blocker = missing_fields[0]
    elif (
        lifecycle_required
        and not verifier_artifact_success
        and (
        not effective_lifecycle_satisfied or agent_operation_trace_missing
        )
    ):
        attribution_layer = "loopx_lifecycle"
        first_blocker = public_safe_compact_text(
            lifecycle.get("missing_reason"),
            limit=140,
        ) or ""
        if agent_operation_trace_missing and not first_blocker:
            first_blocker = "remote_command_file_bridge_agent_operation_trace_missing"
        if not first_blocker:
            first_blocker = (
                public_safe_compact_text(lifecycle.get("missing_reason"), limit=140)
                or "loopx_lifecycle_incomplete"
            )
    elif closeout_status in {"missing", "partial"}:
        attribution_layer = "loopx_lifecycle"
        first_blocker = "loopx_closeout_incomplete"
    elif runner_recovery_blocked:
        attribution_layer = "timeout_or_runner"
        first_blocker = (
            public_safe_compact_text(
                recovery_event.get("recovery_exception_type")
                or recovery_event.get("runner_failure_class"),
                limit=140,
            )
            or "runner_or_timeout_closeout"
        )
    elif official_status == "missing":
        attribution_layer = "verifier_or_scorer"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_missing"
        )
    elif official_passed is True:
        attribution_layer = "clean_pass"
    elif isinstance(official_score_value, (int, float)) and official_score_value == 0:
        attribution_layer = "solution_level_unknown"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_zero_case_failure"
        )
    elif official_passed is False:
        attribution_layer = "solution_level_unknown"
        first_blocker = (
            public_safe_compact_text(run.get("score_failure_attribution"), limit=140)
            or "official_score_nonpassing"
        )

    packet_complete = not missing_fields
    if not packet_complete:
        next_case_gate = "blocked_missing_debug_packet"
        next_action = "write_public_safe_case_debug_packet_before_next_case"
    elif not case_closeout_complete:
        next_case_gate = "blocked_incomplete_case_closeout"
        next_action = "record_or_repair_case_closeout_before_next_case"
    elif attribution_layer == "clean_pass":
        next_case_gate = "open"
        next_action = "upsert_ledger_and_continue_or_compare_pair"
    else:
        next_case_gate = "open_with_attribution"
        next_action = "use_debug_packet_attribution_before_rotating_or_rerunning"

    labels = public_safe_compact_list(
        run.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    solution_quality = build_skillsbench_solution_quality_signals(run)
    gate: dict[str, Any] = {
        "schema_version": "skillsbench_post_run_debug_gate_v0",
        "source": "compact_public_signals",
        "packet_complete": packet_complete,
        "case_closeout_complete": case_closeout_complete,
        "next_case_gate": next_case_gate,
        "normal_progress_allowed": bool(packet_complete and case_closeout_complete),
        "first_blocker": first_blocker,
        "next_action": next_action,
        "attribution_layer": attribution_layer,
        "raw_material_recorded": False,
        "missing_field_count": len(missing_fields),
        "missing_fields": missing_fields[:MAX_BENCHMARK_RUN_LIST_ITEMS],
        "verifier_artifact_recovery_authoritative": verifier_artifact_success,
        "scorer_verifier": {
            "official_score_status": official_status,
            "official_score_passed": (
                official_passed if isinstance(official_passed, bool) else None
            ),
            "official_score_value": (
                official_score_value
                if isinstance(official_score_value, (int, float))
                and not isinstance(official_score_value, bool)
                else None
            ),
            "score_failure_attribution": (
                public_safe_compact_text(
                    run.get("score_failure_attribution"),
                    limit=140,
                )
                or "none"
            ),
        },
        "loopx_lifecycle": {
            "required": lifecycle_required,
            "satisfied": effective_lifecycle_satisfied,
            "closeout_status": closeout_status,
            "state_read_count": lifecycle_state_read_count,
            "state_write_count": lifecycle_state_write_count,
            "todo_closeout_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_todo_closeout_count")
            )
            or _benchmark_positive_int(closeout_event.get("todo_closeout_count")),
            "refresh_state_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_refresh_state_count")
            )
            or _benchmark_positive_int(closeout_event.get("refresh_state_count")),
            "quota_spend_slot_count": _benchmark_positive_int(
                lifecycle.get("agent_bridge_quota_spend_slot_count")
            )
            or _benchmark_positive_int(closeout_event.get("quota_spend_slot_count")),
        },
        "todo_flow": {
            "case_todo_seeded_or_init_observed": (
                events.get("case_goal_state_init", {}).get("status")
                in {"passed", "satisfied", "not_required"}
            ),
            "task_facing_activity_status": activity_status,
            "host_local_acp_bridge_progress_status": (
                public_safe_compact_text(
                    activity_event.get("host_local_acp_bridge_progress_status"),
                    limit=140,
                )
                or public_safe_compact_text(
                    counters.get("host_local_acp_bridge_progress_status"),
                    limit=140,
                )
                or "unknown"
            ),
            "host_local_acp_bridge_progress_signal_source": (
                public_safe_compact_text(
                    activity_event.get("host_local_acp_bridge_progress_signal_source"),
                    limit=140,
                )
                or public_safe_compact_text(
                    counters.get("host_local_acp_bridge_progress_signal_source"),
                    limit=140,
                )
                or "unknown"
            ),
            "acp_protocol_tool_call_count": _benchmark_positive_int(
                activity_event.get("acp_protocol_tool_call_count")
            )
            or _benchmark_positive_int(counters.get("private_trajectory_tool_call_count")),
            "agent_bridge_task_facing_operation_count": _benchmark_positive_int(
                activity_event.get("agent_bridge_task_facing_operation_count")
            )
            or _benchmark_positive_int(
                counters.get("remote_command_file_bridge_agent_task_facing_operation_count")
            ),
            "open_todo_count_public": _benchmark_positive_int(
                counters.get("open_todo_count")
            ),
            "host_local_idle_no_task_output_progress_streak": _benchmark_positive_int(
                counters.get("product_mode_host_local_idle_no_task_output_progress_streak")
            ),
            "host_local_idle_no_task_output_progress_streak_threshold": _benchmark_positive_int(
                counters.get(
                    "product_mode_host_local_idle_no_task_output_progress_streak_threshold"
                )
            ),
            "host_local_idle_no_task_output_progress_stop": counters.get(
                "product_mode_host_local_idle_no_task_output_progress_stop"
            )
            is True,
            "no_open_todo_below_passing_reward_streak": _benchmark_positive_int(
                counters.get(
                    "product_mode_no_open_todo_below_passing_reward_streak"
                )
            ),
            "no_open_todo_below_passing_reward_streak_threshold": _benchmark_positive_int(
                counters.get(
                    "product_mode_no_open_todo_below_passing_reward_streak_threshold"
                )
            ),
            "no_open_todo_below_passing_reward_stop": counters.get(
                "product_mode_no_open_todo_below_passing_reward_stop"
            )
            is True,
        },
        "controller": {
            "status": (
                public_safe_compact_text(controller_event.get("status"), limit=120)
                or "unknown"
            ),
            "action_decision_count": _benchmark_positive_int(
                controller_event.get("action_decision_count")
            ),
            "initial_prompt_count": _benchmark_positive_int(
                controller_event.get("initial_prompt_count")
            ),
            "followup_prompt_count": _benchmark_positive_int(
                controller_event.get("followup_prompt_count")
            ),
            "stop_decision_count": _benchmark_positive_int(
                controller_event.get("stop_decision_count")
            ),
            "max_rounds_budget": _benchmark_positive_int(
                controller_event.get("max_rounds_budget")
            ),
            "last_decision": (
                public_safe_compact_text(
                    controller_event.get("last_decision"),
                    limit=140,
                )
                or "unknown"
            ),
        },
        "timeout_fairness": {
            "runner_recovery_status": recovery_status,
            "recovery_exception_type": (
                public_safe_compact_text(
                    recovery_event.get("recovery_exception_type"),
                    limit=140,
                )
                or "none"
            ),
            "benchflow_agent_timeout_effective_sec": _benchmark_positive_int(
                recovery_event.get("benchflow_agent_timeout_effective_sec")
            ),
        },
        "boundary": {
            "task_text_read": False,
            "logs_read": False,
            "trajectory_read": False,
            "verifier_output_tail_public": False,
        },
    }
    if solution_quality:
        gate["solution_quality"] = solution_quality
    if labels:
        gate["failure_attribution_labels"] = labels
    if runner_failure:
        gate["runner_failure_class"] = (
            public_safe_compact_text(runner_failure.get("failure_class"), limit=140)
            or "unknown"
        )
    return gate


def _compact_benchmark_interaction_counters(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "prompt_policy_injected",
        "harness_skill_or_packet_injected",
        "raw_trace_recorded",
        "raw_task_prompt_recorded",
        "controller_trace_present",
        "loopx_automation_loop",
        "inner_codex_goal_mode",
        "curated_skills_visible",
        "product_mode",
        "goal_start_product_mode",
        "verifier_failure_feedback_todo_route",
        "verifier_failure_feedback_forwarded_to_agent",
        "verifier_failure_todo_required",
        "goal_start_plan_observed",
        "planner_before_todo_write",
        "same_priority_order_preserved",
        "selected_todo_claimed",
        "selected_todo_updated_before_solver",
        "selected_todo_completed_before_spend",
        "selected_todo_completed_observed",
        "non_selected_todos_preserved_open_or_deferred",
        "quota_spend_missing_after_repeated_complete",
        "blind_loop",
        "case_goal_state_packet_present",
        "case_goal_state_init_required",
        "case_goal_state_initialized_before_agent",
        "declared_done_requires_no_remaining_goals",
        "product_mode_lifecycle_checkpoint_required",
        "product_mode_solver_activity_required",
        "product_mode_solver_activity_gap",
        "product_mode_declared_done_below_passing_reward",
        "product_mode_no_open_todo_below_passing_reward_stop",
        "product_mode_host_local_idle_no_task_output_progress",
        "product_mode_host_local_idle_no_task_output_progress_stop",
        "product_mode_final_closeout_superseded_by_official_success",
        "product_mode_no_tool_call_lifecycle_abort",
        "agent_declared_done",
        "agent_declared_no_remaining_goals",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "controller_official_feedback_forwarded",
        "controller_blind_loop",
        "controller_official_success_observed",
        "controller_budget_cutoff_before_followup",
        "benchflow_user_loop_final_verify_recovery_enabled",
        "benchflow_user_loop_final_verify_recovery_triggered",
        "benchflow_user_loop_recovery_after_agent_activity",
        "benchflow_user_loop_recovery_preserved_final_verify",
        "benchflow_user_loop_recovery_raw_error_recorded",
        "benchflow_intermediate_soft_verify_final_only",
        "benchflow_intermediate_soft_verify_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_enabled",
        "benchflow_intermediate_soft_verify_timeout_triggered",
        "benchflow_intermediate_soft_verify_timeout_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_cleanup_requested",
        "benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read",
        "benchflow_intermediate_soft_verify_orphan_cleanup_requested",
        "benchflow_intermediate_soft_verify_orphan_cleanup_raw_logs_read",
        "private_trajectory_summary_present",
        "native_goal_worker_route",
        "native_goal_worker_connected",
        "native_goal_worker_trace_dir_present",
        "native_goal_worker_public_trace_read",
        "native_goal_worker_raw_material_recorded",
        "remote_command_file_bridge_consumed_by_solver",
        "remote_command_file_bridge_solver_trace_dir_present",
        "remote_command_file_bridge_solver_public_trace_read",
        "remote_command_file_bridge_solver_raw_material_recorded",
        "remote_command_file_bridge_agent_operation_trace_required",
        "remote_command_file_bridge_agent_operation_trace_satisfied",
        "remote_command_file_bridge_driver_lifecycle_trace_present",
        "remote_command_file_bridge_driver_lifecycle_raw_material_recorded",
        "host_local_acp_codex_exec_failure_trace_present",
        "host_local_acp_codex_exec_failure_raw_material_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "loopx_state_reads",
        "loopx_state_writes",
        "loopx_case_state_reads",
        "loopx_case_state_writes",
        "heartbeat_count",
        "controller_action_decisions",
        "controller_initial_prompt_count",
        "controller_followup_prompt_count",
        "controller_stop_decision_count",
        "controller_reward_observation_count",
        "controller_round_reward_count",
        "controller_official_success_observation_count",
        "controller_first_success_round",
        "declared_done_round",
        "planned_todo_count",
        "planned_p0_count",
        "agent_todo_complete_unique_todo_count",
        "selected_todo_complete_count",
        "selected_todo_duplicate_complete_count",
        "non_selected_todo_complete_count",
        "todo_complete_without_todo_id_count",
        "product_mode_lifecycle_checkpoint_count",
        "product_mode_lifecycle_checkpoint_round",
        "product_mode_solver_activity_gap_count",
        "product_mode_solver_activity_gap_round",
        "product_mode_declared_done_below_passing_reward_count",
        "product_mode_declared_done_below_passing_reward_round",
        "verifier_failure_feedback_todo_prompt_count",
        "verifier_failure_feedback_todo_round",
        "open_todo_count",
        "product_mode_no_open_todo_below_passing_reward_streak",
        "product_mode_no_open_todo_below_passing_reward_streak_threshold",
        "product_mode_no_open_todo_below_passing_reward_round",
        "product_mode_no_open_todo_below_passing_reward_stop_count",
        "product_mode_no_open_todo_below_passing_reward_stop_round",
        "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
        "product_mode_host_local_idle_no_task_output_progress_streak",
        "product_mode_host_local_idle_no_task_output_progress_streak_threshold",
        "product_mode_host_local_idle_no_task_output_progress_round",
        "product_mode_host_local_idle_no_task_output_progress_stop_count",
        "product_mode_host_local_idle_no_task_output_progress_stop_round",
        "product_mode_host_local_idle_no_task_output_progress_last_failure_trace_count",
        "product_mode_host_local_idle_no_task_output_progress_acp_tool_calls",
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_ops",
        "product_mode_host_local_idle_no_task_output_progress_bridge_task_successes",
        "product_mode_final_closeout_superseded_round",
        "product_mode_no_tool_call_lifecycle_abort_count",
        "product_mode_no_tool_call_lifecycle_abort_round",
        "controller_verifier_feedback_observation_count",
        "controller_official_feedback_blinded_count",
        "controller_official_feedback_forwarded_count",
        "controller_max_rounds_budget",
        "benchflow_user_loop_recovery_round",
        "benchflow_user_loop_recovery_delta_events",
        "benchflow_user_loop_recovery_delta_tool_calls",
        "benchflow_intermediate_soft_verify_call_count",
        "benchflow_intermediate_soft_verify_skipped_count",
        "benchflow_intermediate_soft_verify_timeout_sec",
        "benchflow_intermediate_soft_verify_timeout_override_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_container_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_match_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_alive_after_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_container_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_match_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_alive_after_count",
        "private_trajectory_event_count",
        "private_trajectory_round_count",
        "private_trajectory_tool_call_count",
        "loopx_cli_call_count",
        "loopx_cli_state_read_count",
        "loopx_cli_state_write_count",
        "loopx_case_state_path_count",
        "loopx_case_state_read_count",
        "loopx_case_state_write_count",
        "protected_path_mention_count",
        "protected_path_edit_signal_count",
        "codex_acp_text_bytes",
        "append_benchmark_run_success_count",
        "append_benchmark_run_schema_rejected_count",
        "worker_counter_trace_trial_count",
        "worker_benchmark_run_file_count",
        "worker_benchmark_run_schema_ok_count",
        "worker_self_validation_official_score_mismatch_count",
        "worker_validation_scope_ambiguous_official_score_failure_count",
        "worker_bridge_connected_official_score_failure_count",
        "worker_startup_blocker_count",
        "worker_setup_diagnostic_file_count",
        "worker_setup_diagnostic_schema_ok_count",
        "worker_submit_eligible_mismatch_count",
        "worker_bridge_writeback_loss_count",
        "environment_setup_failure_before_worker_count",
        "pre_worker_agent_setup_failure_count",
        "codex_runtime_goal_tool_trial_count",
        "native_goal_worker_connect_count",
        "native_goal_worker_trace_count",
        "native_goal_worker_lifecycle_trace_count",
        "native_goal_worker_prompt_received_count",
        "native_goal_worker_ok_count",
        "native_goal_worker_goal_get_count",
        "native_goal_worker_turn_start_count",
        "native_goal_worker_turn_completed_observed_count",
        "native_goal_worker_assistant_message_present_count",
        "native_goal_worker_assistant_context_only_count",
        "native_goal_worker_context_only_recovery_attempted_count",
        "native_goal_worker_context_only_recovery_succeeded_count",
        "native_goal_worker_context_only_followup_start_attempted_count",
        "native_goal_worker_context_only_followup_start_succeeded_count",
        "native_goal_worker_transport_reconnect_attempted_count",
        "native_goal_worker_transport_reconnect_succeeded_count",
        "native_goal_worker_goal_reactivation_attempted_count",
        "native_goal_worker_goal_reactivation_succeeded_count",
        "native_goal_worker_post_context_assistant_chars_total",
        "native_goal_worker_first_action_observed_count",
        "native_goal_worker_effective_action_observed_count",
        "remote_command_file_bridge_solver_trace_count",
        "remote_command_file_bridge_solver_probe_ready_count",
        "remote_command_file_bridge_solver_operation_count",
        "remote_command_file_bridge_agent_operation_trace_count",
        "remote_command_file_bridge_agent_request_count",
        "remote_command_file_bridge_agent_success_count",
        "remote_command_file_bridge_agent_failure_count",
        "remote_command_file_bridge_agent_loopx_cli_call_count",
        "remote_command_file_bridge_agent_loopx_state_read_count",
        "remote_command_file_bridge_agent_loopx_state_write_count",
        "remote_command_file_bridge_agent_todo_closeout_count",
        "remote_command_file_bridge_agent_refresh_state_count",
        "remote_command_file_bridge_agent_quota_spend_slot_count",
        "remote_command_file_bridge_agent_task_facing_operation_count",
        "remote_command_file_bridge_agent_task_facing_success_count",
        "remote_command_file_bridge_agent_task_facing_failure_count",
        "remote_command_file_bridge_driver_lifecycle_trace_count",
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count",
        "remote_command_file_bridge_driver_lifecycle_request_count",
        "remote_command_file_bridge_driver_lifecycle_success_count",
        "remote_command_file_bridge_driver_lifecycle_failure_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count",
        "host_local_acp_codex_exec_failure_trace_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "product_mode_declared_done_below_passing_reward_score",
        "product_mode_no_open_todo_below_passing_reward_score",
        "product_mode_host_local_idle_no_task_output_progress_score",
    ):
        raw = value.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            compact[field] = float(raw)
    for field in (
        "case_result_writeback",
        "counter_trust_level",
        "controller_trace_schema_version",
        "controller_trace_publicness",
        "case_goal_state_init_status",
        "case_goal_state_init_failed_phase",
        "case_goal_state_schema_version",
        "product_mode_lifecycle_checkpoint_missing_reason",
        "product_mode_solver_activity_missing_reason",
        "product_mode_declared_done_below_passing_reward_score_status",
        "product_mode_no_open_todo_below_passing_reward_score_status",
        "product_mode_host_local_idle_no_task_output_progress_score_status",
        "product_mode_host_local_idle_no_task_output_progress_category",
        "product_mode_host_local_idle_no_task_output_progress_policy",
        "product_mode_declared_done_policy",
        "product_mode_final_closeout_superseded_reason",
        "controller_budget_cutoff_reason",
        "benchflow_user_loop_recovery_stage",
        "benchflow_user_loop_recovery_exception_type",
        "benchflow_intermediate_soft_verify_policy",
        "benchflow_intermediate_soft_verify_timeout_stage",
        "benchflow_intermediate_soft_verify_timeout_cleanup_status",
        "benchflow_intermediate_soft_verify_orphan_cleanup_status",
        "remote_command_file_bridge_agent_operation_trace_status",
        "remote_command_file_bridge_consumption_decision",
        "remote_command_file_bridge_driver_lifecycle_execution_style",
        "native_goal_worker_reasoning_effort",
        "host_local_acp_codex_exec_failure_category",
        "host_local_acp_bridge_progress_status",
        "host_local_acp_bridge_progress_signal_source",
        "last_decision",
        "worker_submit_eligible_mismatch_reason",
        "worker_bridge_writeback_loss_reason",
    ):
        text = public_safe_compact_text(value.get(field), limit=100)
        if text:
            compact[field] = text
    case_state_path = public_safe_compact_text(
        value.get("case_goal_state_path"),
        limit=180,
    )
    if (
        case_state_path
        and "/.codex/goals/" in case_state_path
        and case_state_path.endswith("/ACTIVE_GOAL_STATE.md")
        and not re.search(r"^/(Users|private|var/folders)/", case_state_path)
    ):
        compact["case_goal_state_path"] = case_state_path

    for field in (
        "codex_runtime_goal_tool_calls",
        "trajectory_action_category_counts",
        "loopx_cli_state_usage_counts",
        "remote_command_file_bridge_agent_returncode_counts",
        "remote_command_file_bridge_agent_loopx_subcommand_counts",
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts",
        "remote_command_file_bridge_driver_lifecycle_command_counts",
        "remote_command_file_bridge_driver_lifecycle_returncode_counts",
    ):
        calls = _compact_numeric_map(value.get(field))
        if calls:
            compact[field] = calls
    selected_p0_todo_id = public_safe_compact_text(
        value.get("selected_p0_todo_id"),
        limit=100,
    )
    if selected_p0_todo_id:
        compact["selected_p0_todo_id"] = selected_p0_todo_id
    planned_todo_ids = public_safe_compact_list(
        value.get("planned_todo_ids"),
        limit=8,
    )
    if planned_todo_ids:
        compact["planned_todo_ids"] = planned_todo_ids
    planned_todo_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=8,
    )
    if planned_todo_texts:
        compact["planned_todo_texts_public_safe"] = planned_todo_texts
    command_records = _compact_loopx_command_records(
        value.get("remote_command_file_bridge_agent_successful_loopx_command_records")
    )
    if command_records:
        compact[
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        ] = command_records
    raw_loopx_cli_calls = value.get("loopx_cli_calls")
    if isinstance(raw_loopx_cli_calls, dict):
        calls = _compact_numeric_map(raw_loopx_cli_calls)
        if calls:
            compact["loopx_cli_calls"] = calls
    elif isinstance(raw_loopx_cli_calls, list):
        calls: list[dict[str, Any]] = []
        for item in raw_loopx_cli_calls[:8]:
            if not isinstance(item, dict):
                continue
            call: dict[str, Any] = {}
            round_value = item.get("round")
            if (
                isinstance(round_value, int)
                and not isinstance(round_value, bool)
                and round_value > 0
            ):
                call["round"] = round_value
            command = public_safe_compact_text(item.get("command"), limit=120)
            if command:
                call["command"] = command
            flags = item.get("flags")
            if isinstance(flags, list):
                compact_flags = [
                    flag
                    for flag in (
                        public_safe_compact_text(flag, limit=60)
                        for flag in flags[:8]
                    )
                    if flag
                ]
                if compact_flags:
                    call["flags"] = compact_flags
            if isinstance(item.get("raw_title_copied"), bool):
                call["raw_title_copied"] = item["raw_title_copied"]
            if isinstance(item.get("raw_output_copied"), bool):
                call["raw_output_copied"] = item["raw_output_copied"]
            if call:
                calls.append(call)
        if calls:
            compact["loopx_cli_calls"] = calls

    return compact


def _compact_product_mode_lifecycle_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "satisfied",
        "countable_treatment",
        "checkpoint_required",
        "closeout_required",
        "closeout_satisfied",
        "agent_operation_trace_required",
        "agent_operation_trace_satisfied",
        "agent_operation_trace_missing",
        "orchestrated_driver_lifecycle_satisfied",
        "orchestrated_driver_counts_as_product_mode",
        "quota_spend_missing_after_repeated_complete",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "state_read_count",
        "state_write_count",
        "checkpoint_count",
        "checkpoint_round",
        "agent_bridge_state_read_count",
        "agent_bridge_state_write_count",
        "agent_bridge_todo_closeout_count",
        "agent_bridge_refresh_state_count",
        "agent_bridge_quota_spend_slot_count",
        "driver_lifecycle_state_read_count",
        "driver_lifecycle_state_write_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    missing_reason = public_safe_compact_text(value.get("missing_reason"), limit=140)
    if missing_reason:
        compact["missing_reason"] = missing_reason
    trace_status = public_safe_compact_text(
        value.get("agent_operation_trace_status"),
        limit=120,
    )
    if trace_status:
        compact["agent_operation_trace_status"] = trace_status
    execution_style = public_safe_compact_text(value.get("execution_style"), limit=120)
    if execution_style:
        compact["execution_style"] = execution_style
    _normalize_product_mode_lifecycle_contract(compact)
    return compact


def _compact_native_goal_worker_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "required",
        "countable_baseline",
        "fresh_goal_thread_per_independent_attempt",
        "official_reward_feedback_forwarded_to_worker",
        "verifier_output_forwarded_to_worker",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "benchflow_max_rounds_budget",
        "initial_goal_turn_budget",
        "same_thread_followup_budget",
        "independent_attempt_budget",
        "trace_count",
        "ok_count",
        "goal_get_count",
        "turn_start_count",
        "assistant_message_present_count",
        "assistant_context_only_count",
        "context_only_recovery_attempted_count",
        "context_only_recovery_succeeded_count",
        "context_only_followup_start_attempted_count",
        "context_only_followup_start_succeeded_count",
        "transport_reconnect_attempted_count",
        "transport_reconnect_succeeded_count",
        "goal_reactivation_attempted_count",
        "goal_reactivation_succeeded_count",
        "post_context_assistant_chars_total",
        "first_action_observed_count",
        "effective_action_observed_count",
        "failure_trace_count",
        "bridge_task_facing_operation_count",
        "bridge_task_facing_success_count",
    ):
        field_value = value.get(field)
        if isinstance(field_value, int) and not isinstance(field_value, bool):
            compact[field] = field_value
    for field in (
        "session_policy",
        "max_rounds_budget_applies_to",
        "countability_source",
        "trace_status",
        "reasoning_effort",
        "failure_category",
        "first_blocker",
        "failure_label",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    return compact


def _compact_app_server_goal_round_semantics(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "route",
        "session_policy",
        "max_rounds_budget_applies_to",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "benchflow_max_rounds_budget",
        "initial_goal_turn_budget",
        "same_thread_followup_budget",
        "independent_attempt_budget",
    ):
        number = _benchmark_nonnegative_int(value.get(field))
        if number is not None:
            compact[field] = number
    for field in (
        "fresh_goal_thread_per_independent_attempt",
        "official_reward_feedback_forwarded_to_worker",
        "verifier_output_forwarded_to_worker",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact


def _normalize_product_mode_lifecycle_contract(contract: dict[str, Any]) -> None:
    """Repair old compact records whose bridge closeout evidence was copied late."""

    def positive_int(field: str) -> int:
        value = contract.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    agent_trace_required = contract.get("agent_operation_trace_required") is True
    agent_trace_satisfied = contract.get("agent_operation_trace_satisfied") is True
    agent_trace_missing = contract.get("agent_operation_trace_missing") is True
    agent_trace_ok = bool(
        not agent_trace_missing
        and (agent_trace_satisfied or not agent_trace_required)
    )
    agent_bridge_closeout_satisfied = bool(
        positive_int("agent_bridge_todo_closeout_count") > 0
        and positive_int("agent_bridge_refresh_state_count") > 0
        and positive_int("agent_bridge_quota_spend_slot_count") > 0
    )
    lifecycle_io_satisfied = bool(
        positive_int("state_read_count") > 0
        and positive_int("state_write_count") > 0
    )
    lifecycle_closeout_satisfied = bool(
        contract.get("closeout_satisfied") is True
        or agent_bridge_closeout_satisfied
    )
    if (
        contract.get("required") is True
        and agent_trace_ok
        and lifecycle_io_satisfied
        and lifecycle_closeout_satisfied
    ):
        contract["satisfied"] = True
        contract["countable_treatment"] = True
        contract["closeout_satisfied"] = True
        if contract.get("missing_reason") in {
            "missing_case_local_loopx_closeout",
            "remote_command_file_bridge_agent_operation_trace_missing",
        }:
            contract.pop("missing_reason", None)


def _repair_product_mode_lifecycle_missing_attribution(
    compact: dict[str, Any],
) -> None:
    contract = compact.get("product_mode_lifecycle_contract")
    if not isinstance(contract, dict):
        return
    if not (
        contract.get("required") is True
        and contract.get("satisfied") is True
        and contract.get("countable_treatment") is True
    ):
        return
    if compact.get("score_failure_attribution") != (
        "skillsbench_product_mode_lifecycle_missing"
    ):
        return

    labels = public_safe_compact_list(
        compact.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    stale_labels = {
        "skillsbench_product_mode_lifecycle_missing",
        "skillsbench_product_mode_uncountable_treatment",
        "skillsbench_case_local_loopx_state_not_observed",
        "skillsbench_remote_bridge_agent_no_requests",
        "skillsbench_remote_bridge_agent_operation_trace_missing",
    }
    labels = [label for label in labels if label not in stale_labels]

    official_score = compact.get("official_score")
    counters = compact.get("interaction_counters")
    if not isinstance(counters, dict):
        counters = {}

    def positive_counter(field: str) -> int:
        value = counters.get(field)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return 0

    def zero_counter_observed(field: str) -> bool:
        if field not in counters:
            return False
        value = counters.get(field)
        return isinstance(value, int) and not isinstance(value, bool) and value == 0

    solver_activity_gap = bool(
        counters.get("product_mode_solver_activity_gap") is True
        and (
            counters.get("product_mode_solver_activity_missing_reason")
            == "missing_task_facing_activity_or_agent_closeout_before_declared_done"
            or positive_counter("product_mode_solver_activity_gap_count") > 0
            or zero_counter_observed(
                "remote_command_file_bridge_agent_task_facing_operation_count"
            )
            or zero_counter_observed(
                "remote_command_file_bridge_agent_todo_closeout_count"
            )
        )
    )
    if solver_activity_gap:
        replacement = "skillsbench_product_mode_solver_activity_gap"
        labels = [
            label
            for label in labels
            if label
            not in {
                "official_verifier_solution_failure",
                "official_score_zero_case_failure",
            }
        ]
    elif isinstance(official_score, (int, float)) and not isinstance(
        official_score,
        bool,
    ) and official_score == 0:
        replacement = "official_verifier_solution_failure"
    else:
        replacement = "none"

    compact["score_failure_attribution"] = replacement
    if replacement != "none" and replacement not in labels:
        labels.insert(0, replacement)
    if labels:
        compact["failure_attribution_labels"] = labels[:MAX_BENCHMARK_RUN_LIST_ITEMS]
    else:
        compact.pop("failure_attribution_labels", None)


def _compact_benchmark_round_reward_trace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "source",
        "round_index_origin",
        "loop_score_policy",
        "official_score_policy",
    ):
        text = public_safe_compact_text(value.get(field), limit=100)
        if text:
            compact[field] = text
    for field in (
        "success_observed",
        "official_feedback_returned_to_agent",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "agent_declared_done",
        "agent_declared_no_remaining_goals",
        "product_mode_no_open_todo_below_passing_reward_stop",
        "official_score_recovered_from_controller_trace",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "first_success_round",
        "declared_done_round",
        "max_rounds_budget",
        "final_round",
        "best_reward_round",
        "official_score_recovered_round",
        "product_mode_no_open_todo_below_passing_reward_streak",
        "product_mode_no_open_todo_below_passing_reward_streak_threshold",
        "product_mode_no_open_todo_below_passing_reward_round",
        "product_mode_no_open_todo_below_passing_reward_stop_round",
        "product_mode_no_open_todo_below_passing_reward_open_todo_count_public",
    ):
        raw = value.get(field)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            compact[field] = raw
    for field in (
        "final_round_reward",
        "best_round_reward",
        "declared_done_score",
        "product_mode_no_open_todo_below_passing_reward_score",
    ):
        raw = value.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            compact[field] = float(raw)
    for field in ("product_mode_no_open_todo_below_passing_reward_score_status",):
        text = public_safe_compact_text(value.get(field), limit=100)
        if text:
            compact[field] = text
    for field in ("final_round_passed", "best_round_passed", "best_round_is_final"):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    records: list[dict[str, Any]] = []
    raw_records = value.get("records")
    if isinstance(raw_records, list):
        seen_rounds: set[int] = set()
        for item in raw_records:
            if not isinstance(item, dict):
                continue
            agent_round = item.get("agent_round")
            if (
                not isinstance(agent_round, int)
                or isinstance(agent_round, bool)
                or agent_round <= 0
                or agent_round in seen_rounds
            ):
                continue
            seen_rounds.add(agent_round)
            record: dict[str, Any] = {"agent_round": agent_round}
            for field in ("reward_present", "passed"):
                if isinstance(item.get(field), bool):
                    record[field] = item[field]
            reward = item.get("reward")
            if isinstance(reward, (int, float)) and not isinstance(reward, bool):
                record["reward"] = float(reward)
            tool_calls = item.get("tool_calls")
            if (
                isinstance(tool_calls, int)
                and not isinstance(tool_calls, bool)
                and tool_calls >= 0
            ):
                record["tool_calls"] = tool_calls
            records.append(record)
    if records:
        compact["records"] = sorted(records, key=lambda record: record["agent_round"])
    return compact


def _compact_benchmark_overhead_attribution_counters(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "source",
        "trace_publicness",
        "attribution_granularity",
        "worker_step_counter_status",
        "attribution_caveat",
        "timeout_tier",
    ):
        text = public_safe_compact_text(value.get(field), limit=160)
        if text:
            compact[field] = text

    for field in (
        "raw_logs_read",
        "raw_trace_recorded",
        "raw_task_prompt_recorded",
        "credential_values_recorded",
        "loopx_worker_cli_bridge_required",
        "observed_true_long_task_bar_met",
        "expected_hours_scale_bar_met",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    for field in (
        "wall_time_seconds",
        "wall_time_limit_seconds",
        "input_tokens",
        "cache_tokens",
        "output_tokens",
        "cost_usd",
        "trial_count",
        "errored_trial_count",
        "worker_bridge_event_count",
        "loopx_prompt_driven_case_cli_call_count",
        "worker_counter_trace_trial_count",
        "worker_benchmark_run_file_count",
        "worker_benchmark_run_schema_ok_count",
        "worker_self_validation_official_score_mismatch_count",
        "worker_validation_scope_ambiguous_official_score_failure_count",
        "worker_bridge_connected_official_score_failure_count",
        "worker_startup_blocker_count",
        "worker_setup_diagnostic_file_count",
        "worker_setup_diagnostic_schema_ok_count",
        "worker_submit_eligible_mismatch_count",
        "worker_bridge_writeback_loss_count",
        "environment_setup_failure_before_worker_count",
        "pre_worker_agent_setup_failure_count",
        "codex_runtime_goal_tool_trial_count",
        "loopx_cli_call_total",
        "loopx_required_cli_call_total",
        "loopx_optional_context_cli_call_total",
        "loopx_state_read_count",
        "loopx_state_write_count",
        "append_benchmark_run_success_count",
        "append_benchmark_run_schema_rejected_count",
        "codex_runtime_goal_tool_call_total",
    ):
        raw = value.get(field)
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            compact[field] = raw

    for field in ("worker_submit_eligible_mismatch_reason",):
        text = public_safe_compact_text(value.get(field), limit=160)
        if text:
            compact[field] = text

    for field in ("loopx_cli_calls", "codex_runtime_goal_tool_calls"):
        calls = _compact_numeric_map(value.get(field))
        if calls:
            compact[field] = calls

    return compact


def _compact_benchmark_preflight_guard(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "first_blocker",
        "loopx_mode_kwarg",
        "codex_goal_mode_invocation_surface",
        "codex_goal_mode_required_invocation_surface",
        "codex_goal_mode_baseline_claim_blocker",
        "codex_app_server_goal_worker_plan_schema",
        "runner_binary_resolution_policy",
        "simulator_setting",
    ):
        text = public_safe_compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    for field in (
        "runner_surface_checked",
        "local_execution_surface_checked",
        "codex_cli_surface_checked",
        "auth_surface_names_only",
        "auth_values_read",
        "artifact_redaction_required",
        "task_material_ready_required",
        "access_packet_prompt_injection_checked",
        "trace_counter_extraction_contract_checked",
        "loopx_mode_kwarg_checked",
        "codex_goal_mode_invocation_surface_checked",
        "codex_app_server_goal_baseline_requested",
        "codex_app_server_goal_worker_adapter_present",
        "codex_app_server_goal_worker_adapter_absent",
        "codex_app_server_goal_worker_turn_start_required",
        "codex_app_server_goal_proof_present",
        "codex_goal_mode_baseline_claim_allowed",
        "loopx_access_packet_absent",
        "loopx_cli_bridge_absent",
        "active_cli_bridge_enabled",
        "claim_requires_worker_cli_calls",
        "real_interface_use_observed",
        "uplift_claim_allowed",
        "active_user_assisted_treatment",
        "simulator_to_worker_injection_channel_available",
        "interactive_user_message_injection_checked",
        "initial_prompt_only_is_not_active_intervention",
        "no_oracle_audit_required",
        "assisted_score_kept_separate_from_official",
        "uvx_cli_present",
        "uvx_version_probe_ok",
        "docker_cli_present",
        "docker_version_probe_ok",
        "docker_server_available",
        "colima_cli_present",
        "colima_status_probe_ok",
        "codex_cli_present",
        "codex_version_probe_ok",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    text = public_safe_compact_text(value.get("worker_cli_bridge_surface"), limit=120)
    if text:
        compact["worker_cli_bridge_surface"] = text
    for field in ("required_worker_loopx_cli_call_total_min",):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact


def _compact_benchmark_runner_prerequisites(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "codex_acp_runtime_launch_preflight_stage",
        "codex_acp_runtime_launch_preflight_status",
        "agent_execution_mode",
        "benchflow_run_stage",
        "benchflow_agent_runtime_layer_status",
        "benchflow_agent_runtime_layer_mount_target",
        "loopx_source_mount_status",
        "loopx_source_mount_target",
        "codex_app_server_goal_worker_plan_schema",
        "benchflow_user_loop_recovery_exception_type",
        "benchflow_user_loop_recovery_stage",
        "benchflow_intermediate_soft_verify_policy",
        "benchflow_intermediate_soft_verify_timeout_stage",
        "benchflow_intermediate_soft_verify_timeout_cleanup_status",
        "benchflow_intermediate_soft_verify_orphan_cleanup_status",
        "benchflow_setup_stall_cleanup_status",
        "codex_api_egress_preflight_status",
        "codex_api_egress_preflight_error_kind",
        "codex_api_egress_mode_requested",
        "codex_api_egress_mode_resolved",
        "codex_api_reverse_tunnel_proxy_source",
        "codex_api_reverse_tunnel_proxy_scheme",
        "codex_api_reverse_tunnel_proxy_endpoint_kind",
        "remote_command_file_bridge_consumption_status",
        "remote_command_file_bridge_agent_operation_trace_status",
        "remote_command_file_bridge_driver_lifecycle_execution_style",
        "runner_interruption_kind",
        "runner_interruption_status",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "codex_acp_runtime_container_bootstrap",
        "codex_acp_runtime_dependency_preflight",
        "codex_acp_runtime_dependency_setup_skipped",
        "codex_acp_runtime_launch_preflight",
        "codex_acp_runtime_launch_preflight_raw_logs_read",
        "container_codex_acp_install_skipped",
        "benchflow_agent_install_skipped_by_runtime_layer",
        "preinstalled_benchflow_agent_runtime_required",
        "benchflow_agent_runtime_layer_ready",
        "benchflow_agent_runtime_mount_injected",
        "benchflow_agent_runtime_mount_read_only",
        "benchflow_agent_runtime_mount_source_recorded",
        "host_local_acp_launch",
        "remote_command_file_bridge_materialized",
        "remote_command_file_bridge_command_configured",
        "remote_command_file_bridge_agent_command_configured",
        "remote_command_file_bridge_agent_command_instrumented",
        "remote_command_file_bridge_probe_command_configured",
        "remote_command_file_bridge_solver_wiring_configured",
        "remote_command_file_bridge_consumed_by_solver",
        "remote_command_file_bridge_solver_trace_dir_present",
        "remote_command_file_bridge_solver_public_trace_read",
        "remote_command_file_bridge_solver_raw_material_recorded",
        "remote_command_file_bridge_agent_operation_trace_required",
        "remote_command_file_bridge_agent_operation_trace_satisfied",
        "remote_command_file_bridge_agent_operation_trace_present",
        "remote_command_file_bridge_driver_lifecycle_trace_present",
        "remote_command_file_bridge_driver_lifecycle_raw_material_recorded",
        "codex_app_server_goal_worker_adapter_present",
        "codex_app_server_goal_worker_turn_start_required",
        "codex_app_server_goal_worker_goal_get_required",
        "codex_app_server_goal_worker_runner_integration_ready",
        "benchflow_user_loop_final_verify_recovery_enabled",
        "benchflow_user_loop_final_verify_recovery_triggered",
        "benchflow_user_loop_recovery_after_agent_activity",
        "benchflow_user_loop_recovery_raw_error_recorded",
        "benchflow_user_loop_recovery_preserved_final_verify",
        "benchflow_intermediate_soft_verify_final_only",
        "benchflow_intermediate_soft_verify_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_enabled",
        "benchflow_intermediate_soft_verify_timeout_triggered",
        "benchflow_intermediate_soft_verify_timeout_raw_output_recorded",
        "benchflow_intermediate_soft_verify_timeout_cleanup_requested",
        "benchflow_intermediate_soft_verify_timeout_cleanup_raw_logs_read",
        "benchflow_intermediate_soft_verify_orphan_cleanup_requested",
        "benchflow_intermediate_soft_verify_orphan_cleanup_raw_logs_read",
        "goal_start_product_mode",
        "goal_start_plan_required",
        "goal_start_selected_p0_lifecycle_required",
        "verifier_failure_feedback_todo_route",
        "verifier_failure_feedback_forwarded_to_agent",
        "verifier_failure_todo_required",
        "benchflow_verifier_prep_timeout_override_enabled",
        "benchflow_verifier_prep_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_enabled",
        "benchflow_final_verifier_timeout_triggered",
        "benchflow_final_verifier_timeout_raw_command_recorded",
        "benchflow_final_verifier_timeout_raw_output_recorded",
        "loopx_source_mount_requested",
        "loopx_source_mount_ready",
        "loopx_source_mount_injected",
        "loopx_source_mount_read_only",
        "loopx_source_mount_source_recorded",
        "benchflow_setup_stall_timeout_enabled",
        "benchflow_setup_stall_timeout_triggered",
        "benchflow_setup_stall_raw_logs_read",
        "benchflow_setup_stall_before_agent_lifecycle",
        "benchflow_agent_install_started",
        "codex_api_egress_preflight_required",
        "codex_api_egress_preflight_ready",
        "codex_api_reverse_tunnel_required",
        "codex_api_reverse_tunnel_proxy_configured",
        "codex_api_reverse_tunnel_proxy_url_recorded",
        "benchflow_setup_stall_task_cancel_requested",
        "benchflow_setup_stall_task_cancel_acknowledged",
        "benchflow_setup_stall_task_cancel_timeout",
        "benchflow_setup_stall_cleanup_requested",
        "benchflow_setup_stall_cleanup_raw_logs_read",
        "runner_interrupted_before_official_result",
        "runner_interruption_compact_closeout_expected",
        "runner_interruption_raw_material_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "codex_acp_runtime_launch_preflight_rc",
        "benchflow_user_loop_recovery_round",
        "benchflow_user_loop_recovery_delta_events",
        "benchflow_user_loop_recovery_delta_tool_calls",
        "benchflow_intermediate_soft_verify_call_count",
        "benchflow_intermediate_soft_verify_skipped_count",
        "benchflow_intermediate_soft_verify_timeout_sec",
        "benchflow_intermediate_soft_verify_timeout_override_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_container_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_match_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_timeout_cleanup_alive_after_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_container_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_match_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_term_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_kill_sent_count",
        "benchflow_intermediate_soft_verify_orphan_cleanup_alive_after_count",
        "benchflow_verifier_prep_timeout_sec",
        "benchflow_final_verifier_timeout_sec",
        "benchflow_final_verifier_timeout_override_count",
        "benchflow_verifier_prep_timeout_override_count",
        "benchflow_verify_prep_timeout_override_count",
        "benchflow_soft_verify_prep_timeout_override_count",
        "benchflow_setup_stall_timeout_sec",
        "codex_api_reverse_tunnel_proxy_endpoint_port",
        "benchflow_setup_stall_cleanup_match_count",
        "benchflow_setup_stall_cleanup_term_sent_count",
        "benchflow_setup_stall_cleanup_kill_sent_count",
        "benchflow_setup_stall_cleanup_alive_after_count",
        "goal_start_planned_todo_count_expected",
        "remote_command_file_bridge_solver_trace_count",
        "remote_command_file_bridge_solver_probe_ready_count",
        "remote_command_file_bridge_solver_operation_count",
        "remote_command_file_bridge_agent_operation_trace_count",
        "remote_command_file_bridge_agent_request_count",
        "remote_command_file_bridge_agent_success_count",
        "remote_command_file_bridge_agent_failure_count",
        "remote_command_file_bridge_agent_loopx_cli_call_count",
        "remote_command_file_bridge_agent_loopx_state_read_count",
        "remote_command_file_bridge_agent_loopx_state_write_count",
        "remote_command_file_bridge_agent_task_facing_operation_count",
        "remote_command_file_bridge_agent_todo_closeout_count",
        "remote_command_file_bridge_agent_refresh_state_count",
        "remote_command_file_bridge_agent_quota_spend_slot_count",
        "remote_command_file_bridge_driver_lifecycle_trace_count",
        "remote_command_file_bridge_driver_lifecycle_checkpoint_count",
        "remote_command_file_bridge_driver_lifecycle_request_count",
        "remote_command_file_bridge_driver_lifecycle_success_count",
        "remote_command_file_bridge_driver_lifecycle_failure_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_cli_call_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_read_count",
        "remote_command_file_bridge_driver_lifecycle_loopx_state_write_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "remote_command_file_bridge_agent_operation_counts",
        "remote_command_file_bridge_agent_loopx_subcommand_counts",
        "remote_command_file_bridge_agent_successful_loopx_subcommand_counts",
        "remote_command_file_bridge_driver_lifecycle_command_counts",
        "remote_command_file_bridge_driver_lifecycle_returncode_counts",
    ):
        calls = _compact_numeric_map(value.get(field))
        if calls:
            compact[field] = calls
    planned_todo_ids = public_safe_compact_list(value.get("planned_todo_ids"), limit=8)
    if planned_todo_ids:
        compact["planned_todo_ids"] = planned_todo_ids
    planned_todo_texts = public_safe_compact_list(
        value.get("planned_todo_texts_public_safe"),
        limit=8,
    )
    if planned_todo_texts:
        compact["planned_todo_texts_public_safe"] = planned_todo_texts
    command_records = _compact_loopx_command_records(
        value.get("remote_command_file_bridge_agent_successful_loopx_command_records")
    )
    if command_records:
        compact[
            "remote_command_file_bridge_agent_successful_loopx_command_records"
        ] = command_records
    return compact


def _compact_benchmark_task_staging(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in ("schema_version",):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "staged",
        "include_task_skills",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "dockerfile_pip_bootstrap_patch_applied",
        "dockerfile_package_bootstrap_risk_preflight_blocked",
        "dockerfile_uv_bootstrap_risk_detected",
        "dockerfile_uv_bootstrap_mirror_patch_required",
        "dockerfile_uv_bootstrap_mirror_patch_applied",
        "dockerfile_uv_bootstrap_pip_fallback_patch_applied",
        "apt_retry_patch_applied",
        "apt_risk_preflight_blocked",
        "bootstrap_light_preflight_blocked",
        "bootstrap_light_fail_fast_defaulted",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_uv_bootstrap_mirror_patch_required",
        "verifier_uv_bootstrap_mirror_patch_applied",
        "dockerfile_apache_archive_mirror_patch_required",
        "dockerfile_apache_archive_mirror_patch_applied",
        "dockerfile_apache_archive_raw_url_recorded",
        "dockerfile_maven_mirror_patch_required",
        "dockerfile_maven_mirror_patch_applied",
        "dockerfile_maven_mirror_raw_url_recorded",
        "benchmark_egress_proxy_dockerfile_env_patch_required",
        "benchmark_egress_proxy_dockerfile_env_patch_applied",
        "benchmark_egress_proxy_dockerfile_java_opts_patch_applied",
        "benchmark_egress_proxy_dockerfile_env_raw_proxy_recorded",
        "verifier_bootstrap_risk_preflight_blocked",
        "verifier_bootstrap_fail_fast_defaulted",
        "app_skills_mount_patch_applied",
        "codex_acp_runtime_tools_patch_applied",
        "task_skills_removed",
        "original_task_mutated",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "dockerfile_pip_index_host",
        "bootstrap_light_blocker_kind",
        "dockerfile_uv_bootstrap_version",
        "dockerfile_uv_bootstrap_mirror_host",
        "verifier_uv_bootstrap_version",
        "verifier_uv_bootstrap_mirror_host",
        "dockerfile_apache_archive_mirror_host",
        "dockerfile_maven_mirror_host",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    count = value.get("bootstrap_light_blocking_field_count")
    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        compact["bootstrap_light_blocking_field_count"] = count
    count = value.get("benchmark_egress_proxy_dockerfile_env_key_count")
    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
        compact["benchmark_egress_proxy_dockerfile_env_key_count"] = count

    resource_cap = value.get("resource_cap_patch")
    if isinstance(resource_cap, dict):
        compact_resource_cap: dict[str, Any] = {}
        for field in ("schema_version", "reason"):
            text = public_safe_compact_text(resource_cap.get(field), limit=180)
            if text:
                compact_resource_cap[field] = text
        for field in ("applied", "original_task_mutated"):
            if isinstance(resource_cap.get(field), bool):
                compact_resource_cap[field] = resource_cap[field]
        for field in ("host_cpus", "requested_cpus", "effective_cpus"):
            raw = resource_cap.get(field)
            if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                compact_resource_cap[field] = raw
        if compact_resource_cap:
            compact["resource_cap_patch"] = compact_resource_cap
    return compact


def _compact_benchmark_task_setup_preflight(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "sandbox",
        "task_id",
        "first_blocker",
        "alternate_source_kind",
        "selection_recommendation",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "raw_task_text_read",
        "raw_logs_read",
        "raw_trajectory_read",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "dockerfile_pip_install_risk_detected",
        "dockerfile_pip_bootstrap_patch_required",
        "verifier_present",
        "verifier_bootstrap_risk_detected",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_external_download_risk_detected",
        "verifier_package_install_risk_detected",
        "dockerfile_present",
        "canonical_task_present",
        "alternate_source_supported_by_runner",
        "task_source_path_recorded",
        "task_source_content_recorded",
        "bootstrap_light_candidate_eligible",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    text = public_safe_compact_text(
        value.get("verifier_uv_bootstrap_version"),
        limit=180,
    )
    if text:
        compact["verifier_uv_bootstrap_version"] = text
    nearest_task_ids = public_safe_compact_list(
        value.get("nearest_canonical_task_ids"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if nearest_task_ids:
        compact["nearest_canonical_task_ids"] = nearest_task_ids
    verifier_risk_categories = public_safe_compact_list(
        value.get("verifier_bootstrap_risk_categories"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if verifier_risk_categories:
        compact["verifier_bootstrap_risk_categories"] = verifier_risk_categories
    bootstrap_light_blocking_fields = public_safe_compact_list(
        value.get("bootstrap_light_blocking_fields"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if bootstrap_light_blocking_fields:
        compact["bootstrap_light_blocking_fields"] = bootstrap_light_blocking_fields
    return compact


def _compact_benchmark_compose_setup_diagnostic(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "route",
        "failure_class",
        "runner_prerequisite_status",
        "task_setup_preflight_status",
        "fingerprint_confidence",
        "runner_error_len_bucket",
        "next_diagnostic_action",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "compose_setup_failure",
        "unclassified_compose_failure",
        "docker_daemon_unavailable",
        "volume_mount_failure",
        "environment_setup_failure",
        "agent_rounds_started",
        "official_score_missing",
        "official_result_json_materialized",
        "case_attempt_budget_should_count",
        "runner_launch_preflight_passed",
        "apt_setup_risk_detected",
        "apt_retry_patch_required",
        "verifier_uv_bootstrap_risk_detected",
        "verifier_uv_bootstrap_mirror_patch_required",
        "verifier_uv_bootstrap_mirror_patch_applied",
        "staged_task_prepared",
        "task_skills_removed",
        "codex_acp_runtime_tools_patch_applied",
        "resource_cap_applied",
        "raw_error_recorded",
        "raw_logs_read",
        "raw_task_text_read",
        "raw_trajectory_read",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "heartbeat_count",
        "controller_action_decision_count",
        "trajectory_round_count",
        "trajectory_tool_call_count",
        "loopx_cli_call_count",
        "round_reward_count",
        "progress_completed_trials",
        "progress_errored_trials",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    patterns = public_safe_compact_list(
        value.get("fingerprint_matched_patterns"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if patterns:
        compact["fingerprint_matched_patterns"] = patterns
    return compact


_SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS = {
    "compose_setup_blocked_before_agent_rounds": (
        "skillsbench_compose_setup_blocked_before_agent_rounds"
    ),
    "runner_setup_blocked_before_agent_rounds": (
        "skillsbench_runner_setup_blocked_before_agent_rounds"
    ),
}


def _skillsbench_compact_official_score_missing(compact: dict[str, Any]) -> bool:
    official = (
        compact.get("official_task_score")
        if isinstance(compact.get("official_task_score"), dict)
        else {}
    )
    value = official.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return False
    value = compact.get("official_score")
    return not (isinstance(value, (int, float)) and not isinstance(value, bool))


def _skillsbench_compact_pre_agent_setup_label(compact: dict[str, Any]) -> str:
    diagnostic = compact.get("compose_setup_diagnostic")
    if not isinstance(diagnostic, dict):
        return ""
    label = _SKILLSBENCH_PRE_AGENT_SETUP_STATUS_LABELS.get(
        str(diagnostic.get("status") or "")
    )
    if not label:
        return ""
    if compact.get("mode") != "skillsbench_codex_app_server_goal_baseline":
        return ""
    validation = (
        compact.get("validation") if isinstance(compact.get("validation"), dict) else {}
    )
    native_route = (
        compact.get("native_goal_worker_route")
        if "native_goal_worker_route" in compact
        else validation.get("native_goal_worker_route")
    )
    if native_route is not True:
        return ""
    native_connected = (
        compact.get("native_goal_worker_connected")
        if "native_goal_worker_connected" in compact
        else validation.get("native_goal_worker_connected")
    )
    if native_connected is True:
        return ""
    trace_count = (
        compact.get("native_goal_worker_trace_count")
        if "native_goal_worker_trace_count" in compact
        else validation.get("native_goal_worker_trace_count")
    )
    if (
        isinstance(trace_count, int)
        and not isinstance(trace_count, bool)
        and trace_count > 0
    ):
        return ""
    if diagnostic.get("agent_rounds_started") is True:
        return ""
    if not _skillsbench_compact_official_score_missing(compact):
        return ""
    return label


def _apply_skillsbench_pre_agent_setup_compact_projection(
    compact: dict[str, Any],
) -> None:
    label = _skillsbench_compact_pre_agent_setup_label(compact)
    if not label:
        return
    current = str(compact.get("score_failure_attribution") or "")
    if (
        current in {"", "none", "score_missing", "skillsbench_runner_error"}
        or current.startswith("skillsbench_native_goal_worker_")
    ):
        compact["score_failure_attribution"] = label
        compact["first_blocker"] = label
    labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str) and item
    ]
    for item in (
        label,
        "skillsbench_app_server_goal_pre_agent_materialization_blocked",
        "skillsbench_runner_setup_error",
    ):
        if item not in labels:
            labels.append(item)
    compact["failure_attribution_labels"] = labels[:MAX_BENCHMARK_RUN_LIST_ITEMS]
    attempt_accounting = compact.get("attempt_accounting")
    if isinstance(attempt_accounting, dict):
        attempt_accounting["failure_label"] = label
        attempt_accounting["failure_class"] = "job_materialization_failed"
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["exception_type"] = label
        runner_failure["failure_class"] = label
        runner_failure["pre_agent_setup_materialization_blocked"] = True
    validation = compact.get("validation")
    if isinstance(validation, dict):
        failed = [
            item
            for item in validation.get("failed_checks", [])
            if isinstance(item, str) and item
        ]
        failed = [
            item for item in failed if item != "native_goal_worker_public_trace_missing"
        ]
        if "pre_agent_setup_materialization_blocked" not in failed:
            failed.append("pre_agent_setup_materialization_blocked")
        validation["failed_checks"] = failed[:MAX_BENCHMARK_RUN_LIST_ITEMS]
        validation["all_passed"] = False
    compact["pre_agent_setup_materialization_blocked"] = True
    compact["native_goal_worker_pre_agent_setup_blocked"] = True


def _compact_benchmark_result_discovery(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "status",
        "selection_policy",
        "tie_breaker",
        "selected_relative_to_root",
        "selected_relative_to_job",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "candidate_count",
        "matched_candidate_count",
        "top_score_candidate_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("raw_logs_read", "raw_task_text_read", "raw_trajectory_read"):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    reasons = public_safe_compact_list(
        value.get("selection_reasons"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if reasons:
        compact["selection_reasons"] = reasons
    return compact


def _compact_active_user_assisted_treatment_preflight(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "pilot_schema_version",
        "active_injection_schema_version",
        "operator_simulator_run_schema_version",
        "simulator_setting",
        "next_step",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "proactive_intervention_allowed",
        "directive_feedback_allowed",
        "artificial_mildness_required",
        "frequency_budget_required",
        "visibility_policy_required",
        "no_oracle_audit_required",
        "assisted_collaboration_claim_allowed",
        "official_score_claim_allowed",
        "leaderboard_claim_allowed",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    channel = (
        value.get("simulator_to_worker_injection_channel")
        if isinstance(value.get("simulator_to_worker_injection_channel"), dict)
        else {}
    )
    compact_channel: dict[str, Any] = {}
    for field in (
        "schema_version",
        "first_blocker",
        "required_capability",
        "current_agent_surface",
        "active_user_feed_jsonl",
        "active_user_observation_json",
        "next_channel_requirement",
        "minimum_next_implementation",
        "required_missing_channel",
    ):
        text = public_safe_compact_text(channel.get(field), limit=140)
        if text:
            compact_channel[field] = text
    if isinstance(channel.get("checked_channel_count"), int) and not isinstance(
        channel.get("checked_channel_count"), bool
    ):
        compact_channel["checked_channel_count"] = channel["checked_channel_count"]
    checked_channels = (
        channel.get("checked_channels")
        if isinstance(channel.get("checked_channels"), list)
        else []
    )
    existing_channel_names = (
        channel.get("checked_channel_names")
        if isinstance(channel.get("checked_channel_names"), list)
        else []
    )
    channel_names: list[str] = [
        name
        for name in (
            public_safe_compact_text(item, limit=80)
            for item in existing_channel_names
        )
        if name
    ]
    required_missing_channel = ""
    for item in checked_channels:
        if not isinstance(item, dict):
            continue
        name = public_safe_compact_text(item.get("channel"), limit=80)
        verdict = public_safe_compact_text(item.get("verdict"), limit=80)
        if name:
            channel_names.append(name)
        if verdict == "required_missing" and name and not required_missing_channel:
            required_missing_channel = name
    if channel_names:
        compact_channel["checked_channel_names"] = channel_names[:5]
    if required_missing_channel:
        compact_channel["required_missing_channel"] = required_missing_channel
    for field in (
        "channel_available",
        "initial_prompt_only_is_not_active_intervention",
        "direct_codex_chat_injection_available",
        "audited_external_update_loop_available",
        "no_user_message_injected",
        "model_api_invoked",
        "raw_transcript_recorded",
    ):
        if isinstance(channel.get(field), bool):
            compact_channel[field] = channel[field]
    if compact_channel:
        compact["simulator_to_worker_injection_channel"] = compact_channel

    launcher_plan = _compact_active_user_private_launcher_plan(
        value.get("private_launcher_plan")
    )
    if launcher_plan:
        compact["private_launcher_plan"] = launcher_plan

    return compact


def _compact_active_user_private_launcher_plan(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "launch_surface",
        "first_blocker",
        "required_capability",
        "worker_start_marker",
        "active_user_feed_jsonl",
        "active_user_observation_json",
        "simulator_setting",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    contract = (
        value.get("codex_simulator_contract")
        if isinstance(value.get("codex_simulator_contract"), dict)
        else {}
    )
    compact_contract: dict[str, Any] = {}
    for field in (
        "schema_version",
        "simulator_kind",
        "codex_exec_command",
        "append_validated_output_command",
        "simulator_output_schema_version",
    ):
        text = public_safe_compact_text(contract.get(field), limit=500)
        if text:
            compact_contract[field] = text
    for field in (
        "manual_controller_feed_allowed",
        "formal_treatment_requires_model_backed_simulator",
        "controller_authored_feed_allowed",
    ):
        if isinstance(contract.get(field), bool):
            compact_contract[field] = contract[field]
    if compact_contract:
        compact["codex_simulator_contract"] = compact_contract
    if isinstance(value.get("ready"), bool):
        compact["ready"] = value["ready"]
    for field in ("sequence_steps", "required_evidence", "stop_conditions"):
        items = public_safe_compact_list(value.get(field), limit=8)
        if items:
            compact[field] = items
    for nested_name in ("claim_boundary", "public_boundary"):
        nested = value.get(nested_name) if isinstance(value.get(nested_name), dict) else {}
        compact_nested: dict[str, Any] = {}
        for key, nested_value in nested.items():
            safe_key = public_safe_compact_text(key, limit=80)
            if not safe_key:
                continue
            if isinstance(nested_value, bool):
                compact_nested[safe_key] = nested_value
            else:
                text = public_safe_compact_text(nested_value, limit=120)
                if text:
                    compact_nested[safe_key] = text
        if compact_nested:
            compact[nested_name] = compact_nested
    return compact


def _compact_active_user_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in ("schema_version", "bridge_surface", "channel_surface", "next_action"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "feed_present",
        "feed_path_recorded",
        "observed_after_worker_start",
        "worker_observation_proof",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "worker_start_seq",
        "valid_intervention_count",
        "invalid_line_count",
        "observed_intervention_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]

    latest = (
        value.get("latest_intervention")
        if isinstance(value.get("latest_intervention"), dict)
        else {}
    )
    compact_latest: dict[str, Any] = {}
    for field in ("channel", "type", "trigger", "message"):
        text = public_safe_compact_text(latest.get(field), limit=160)
        if text:
            compact_latest[field] = text
    if isinstance(latest.get("seq"), int) and not isinstance(latest.get("seq"), bool):
        compact_latest["seq"] = latest["seq"]
    for field in (
        "oracle_free",
        "hidden_tests_visible",
        "expected_solution_visible",
        "credential_values_visible",
        "private_material_visible",
    ):
        if isinstance(latest.get(field), bool):
            compact_latest[field] = latest[field]
    if compact_latest:
        compact["latest_intervention"] = compact_latest

    for source_field, compact_field in (
        ("claim_boundary", "claim_boundary"),
        ("public_boundary", "public_boundary"),
    ):
        source = (
            value.get(source_field)
            if isinstance(value.get(source_field), dict)
            else {}
        )
        compact_boundary: dict[str, Any] = {}
        for key, boundary_value in source.items():
            if isinstance(key, str) and isinstance(boundary_value, bool):
                safe_key = public_safe_compact_text(key, limit=80)
                if safe_key:
                    compact_boundary[safe_key] = boundary_value
        if compact_boundary:
            compact[compact_field] = compact_boundary
    return compact


def _compact_benchmark_claim_gate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    schema = public_safe_compact_text(value.get("schema_version"), limit=100)
    if schema:
        compact["schema_version"] = schema
    for field in (
        "requires_private_no_upload",
        "requires_worker_loopx_cli_calls",
        "reject_runner_bridge_calls_as_in_case_evidence",
        "reject_codex_runtime_goal_tool_calls_as_loopx_evidence",
        "uplift_claim_allowed",
        "leaderboard_claim_allowed",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("required_worker_loopx_cli_call_total_min",):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    return compact


def _compact_benchmark_private_runner_launch(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "launch_schema_version",
        "first_blocker",
        "argv_binary_name",
        "codex_goal_mode_invocation_surface",
        "codex_goal_mode_required_invocation_surface",
        "codex_goal_mode_baseline_claim_blocker",
        "codex_app_server_goal_worker_plan_schema",
        "task_material_readiness_status",
        "task_material_first_blocker",
    ):
        text = public_safe_compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    for field in (
        "uses_private_runner_env",
        "ready",
        "argv_present",
        "argv_binary_resolved_for_private_launch",
        "no_upload_boundary",
        "submit_eligible",
        "env_path_present",
        "active_user_writable_mount_requested",
        "active_user_writable_mount_target_present",
        "agent_import_path_present",
        "loopx_agent_kwargs_present",
        "codex_goal_mode_baseline_requested",
        "codex_app_server_goal_baseline_requested",
        "codex_app_server_goal_worker_adapter_present",
        "codex_app_server_goal_worker_turn_start_required",
        "codex_app_server_goal_proof_present",
        "codex_goal_mode_baseline_claim_allowed",
        "loopx_access_packet_absent",
        "loopx_worker_bridge_requested",
        "worker_materialization_probe_only",
        "task_material_readiness_checked",
        "task_material_ready_required",
        "task_material_ready",
        "setup_timeout_repair_profile",
        "auth_values_recorded",
        "raw_env_recorded",
        "raw_paths_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "env_probe_path_coverage_count",
        "task_material_candidate_count",
        "task_material_instruction_md_present_count",
        "task_material_task_toml_present_count",
    ):
        count = value.get(field)
        if isinstance(count, int) and not isinstance(count, bool):
            compact[field] = count
    active_user_mount_count = value.get("active_user_writable_mount_count")
    if isinstance(active_user_mount_count, int) and not isinstance(active_user_mount_count, bool):
        compact["active_user_writable_mount_count"] = active_user_mount_count
    coverage = value.get("env_probe_path_coverage")
    compact_coverage: dict[str, bool] = {}
    if isinstance(coverage, dict):
        compact_coverage = {
            str(key): ready
            for key, ready in coverage.items()
            if isinstance(key, str) and isinstance(ready, bool)
        }
    if compact_coverage:
        compact["env_probe_path_coverage"] = compact_coverage
    policy = value.get("timeout_multiplier_policy")
    if isinstance(policy, dict):
        compact_policy: dict[str, Any] = {}
        schema = public_safe_compact_text(policy.get("schema_version"), limit=120)
        if schema:
            compact_policy["schema_version"] = schema
        for field in (
            "any_timeout_multiplier_present",
            "non_default_timeout_multiplier_present",
            "agent_setup_timeout_multiplier_present",
            "changes_official_benchmark_timeout",
            "leaderboard_claim_allowed",
            "raw_argv_recorded",
        ):
            if isinstance(policy.get(field), bool):
                compact_policy[field] = policy[field]
        multipliers = policy.get("multipliers")
        if isinstance(multipliers, dict):
            compact_multipliers = {
                str(key): value
                for key, value in multipliers.items()
                if isinstance(key, str)
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            }
            if compact_multipliers:
                compact_policy["multipliers"] = compact_multipliers
        if compact_policy:
            compact["timeout_multiplier_policy"] = compact_policy
    repair_profile = _compact_benchmark_repair_profile(value.get("repair_profile"))
    if repair_profile:
        compact["repair_profile"] = repair_profile
    readiness = _compact_agent_setup_readiness(value.get("agent_setup_readiness"))
    if readiness:
        compact["agent_setup_readiness"] = readiness
    names = public_safe_compact_list(
        value.get("auth_surface_names_present"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if names:
        compact["auth_surface_names_present"] = names
    materialization = _compact_benchmark_post_launch_materialization(
        value.get("post_launch_materialization")
    )
    if materialization:
        compact["post_launch_materialization"] = materialization
    closeout = value.get("closeout_command_templates")
    if isinstance(closeout, dict):
        compact_closeout: dict[str, Any] = {}
        for field in (
            "schema_version",
            "display_command",
            "post_run_rule",
        ):
            text = public_safe_compact_text(closeout.get(field), limit=320)
            if text:
                compact_closeout[field] = text
        for field in (
            "history_append",
            "run_ledger_update",
            "atomic_ledger_upsert",
            "raw_paths_recorded",
            "raw_logs_read",
            "raw_task_text_read",
        ):
            if isinstance(closeout.get(field), bool):
                compact_closeout[field] = closeout[field]
        argv_template = public_safe_compact_list(
            closeout.get("argv_template"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS * 4,
        )
        if argv_template:
            compact_closeout["argv_template"] = argv_template
        if compact_closeout:
            compact["closeout_command_templates"] = compact_closeout
    return compact


def _compact_benchmark_repair_profile(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in ("schema_version", "repair_class"):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "enabled",
        "rerun_allowed_after_profile_applied",
        "raw_logs_required",
        "raw_task_text_required",
        "credential_values_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]

    for source_field in (
        "required_launch_overrides",
        "disallowed_launch_overrides",
    ):
        source = value.get(source_field)
        if not isinstance(source, dict):
            continue
        compact_source: dict[str, Any] = {}
        for key, raw_value in source.items():
            safe_key = public_safe_compact_text(key, limit=100)
            if not safe_key:
                continue
            if isinstance(raw_value, str):
                text_value = public_safe_compact_text(raw_value, limit=140)
                if text_value:
                    compact_source[safe_key] = text_value
            elif isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool):
                compact_source[safe_key] = raw_value
            elif isinstance(raw_value, bool):
                compact_source[safe_key] = raw_value
        if compact_source:
            compact[source_field] = compact_source
    return compact


def _compact_agent_setup_readiness(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "codex_install_strategy",
        "first_blocker",
        "next_action_after_setup_timeout",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "managed_codex_agent",
        "worker_bridge_requested",
        "worker_materialization_probe_only",
        "runtime_codex_install_allowed",
        "fail_fast_install_strategy",
        "setup_timeout_budget_explicit",
        "setup_timeout_repair_profile",
        "same_task_repeat_after_setup_timeout_allowed",
        "setup_failure_before_worker_counts_as_case_progress",
        "raw_argv_recorded",
        "raw_env_recorded",
        "raw_logs_read",
        "task_text_read",
        "trajectory_read",
        "credential_values_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    multiplier = value.get("agent_setup_timeout_multiplier")
    if isinstance(multiplier, (int, float)) and not isinstance(multiplier, bool):
        compact["agent_setup_timeout_multiplier"] = multiplier
    return compact


def _compact_benchmark_post_launch_materialization(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "first_blocker",
        "job_name",
        "external_handle_kind",
        "external_handle_state",
        "compact_monitor_class",
        "compact_failure_class",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "checked",
        "ready_for_launch_state",
        "ready_for_compact_result_ingest",
        "jobs_dir_present",
        "job_root_present",
        "job_lock_present",
        "job_result_present",
        "ready_for_compact_failure_marker",
        "external_handle_observed",
        "external_handle_terminal",
        "job_result_finished",
        "job_active_without_trial_result",
        "job_stale_active_without_trial_result",
        "job_result_updated_at_present",
        "stale_active_reconcile_requested",
        "raw_paths_recorded",
        "raw_logs_read",
        "raw_task_text_read",
        "trajectory_read",
        "raw_external_handle_payload_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "trial_result_present_count",
        "candidate_job_root_count",
        "job_running_trial_count",
        "job_pending_trial_count",
        "job_active_stale_seconds_threshold",
    ):
        count = value.get(field)
        if isinstance(count, int) and not isinstance(count, bool):
            compact[field] = count
    age = value.get("job_updated_age_seconds")
    if isinstance(age, (int, float)) and not isinstance(age, bool):
        compact["job_updated_age_seconds"] = round(float(age), 3)
    marker = value.get("compact_failure_marker")
    if isinstance(marker, dict):
        compact_marker: dict[str, Any] = {}
        for field in (
            "schema_version",
            "failure_class",
            "evidence_kind",
            "external_handle_kind",
            "external_handle_state",
            "terminal_state",
            "lifecycle_stage",
            "ledger_attempt_kind",
            "next_allowed_action",
        ):
            text = public_safe_compact_text(marker.get(field), limit=140)
            if text:
                compact_marker[field] = text
        for field in (
            "external_handle_terminal",
            "terminal_closeout",
            "runner_attempt_countable",
            "launch_state_countable",
            "case_attempt_countable",
            "benchmark_budget_countable",
            "job_result_present",
            "job_result_finished",
            "job_result_updated_at_present",
            "raw_paths_recorded",
            "raw_logs_read",
            "raw_task_text_read",
            "trajectory_read",
            "raw_external_handle_payload_recorded",
        ):
            if isinstance(marker.get(field), bool):
                compact_marker[field] = marker[field]
        trial_result_count = marker.get("trial_result_present_count")
        if isinstance(trial_result_count, int) and not isinstance(
            trial_result_count, bool
        ):
            compact_marker["trial_result_present_count"] = trial_result_count
        for field in (
            "job_running_trial_count",
            "job_pending_trial_count",
            "job_active_stale_seconds_threshold",
        ):
            count = marker.get(field)
            if isinstance(count, int) and not isinstance(count, bool):
                compact_marker[field] = count
        age = marker.get("job_updated_age_seconds")
        if isinstance(age, (int, float)) and not isinstance(age, bool):
            compact_marker["job_updated_age_seconds"] = round(float(age), 3)
        attempt_accounting = _compact_benchmark_attempt_accounting(
            marker.get("attempt_accounting")
        )
        if attempt_accounting:
            compact_marker["attempt_accounting"] = attempt_accounting
        if compact_marker:
            compact["compact_failure_marker"] = compact_marker
    return compact


def compact_benchmark_post_launch_materialization(value: Any) -> dict[str, Any] | None:
    compact = _compact_benchmark_post_launch_materialization(value)
    return compact or None


def _compact_benchmark_attempt_accounting(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "lifecycle_phase",
        "failure_label",
        "failure_class",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "launcher_attempt_countable",
        "case_attempt_countable",
        "solver_attempt_countable",
        "verifier_attempt_countable",
        "official_score_attempt_countable",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    attempts = value.get("attempts")
    if isinstance(attempts, dict):
        compact_attempts: dict[str, Any] = {}
        for phase in (
            "launcher",
            "case",
            "solver",
            "verifier",
            "official_score",
        ):
            phase_value = attempts.get(phase)
            if not isinstance(phase_value, dict):
                continue
            compact_phase: dict[str, bool] = {}
            for field in ("attempted", "countable"):
                if isinstance(phase_value.get(field), bool):
                    compact_phase[field] = phase_value[field]
            if compact_phase:
                compact_attempts[phase] = compact_phase
        if compact_attempts:
            compact["attempts"] = compact_attempts
    return compact


def _compact_worker_bridge_outcome(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "bridge_surface",
        "runner_return_status",
        "official_score_status",
        "trace_publicness",
        "next_action",
        "score_failure_attribution",
        "worker_submit_eligible_mismatch_reason",
        "worker_bridge_writeback_loss_reason",
        "worker_bridge_materialization_status",
        "worker_bridge_materialization_blocker",
        "worker_bridge_failure_attribution",
        "prompt_driven_first_blocker",
        "controller_last_decision",
        "repeat_blocked_by",
        "pre_worker_startup_blocker",
    ):
        text = public_safe_compact_text(value.get(field), limit=160)
        if text:
            compact[field] = text
    for field in (
        "worker_bridge_verified",
        "prompt_driven_loopx_trace_observed",
        "prompt_driven_loopx_lifecycle_observed",
        "counter_trace_present",
        "runner_return_completed",
        "official_score_completed",
        "side_effect_audit_passed",
        "raw_paths_recorded",
        "raw_trace_recorded",
        "credential_values_recorded",
        "runner_side_writeback_guaranteed",
        "worker_submit_eligible_mismatch_observed",
        "worker_bridge_writeback_loss_observed",
        "loopx_controller_trace_present",
        "loopx_controller_trace_public_safe",
        "controller_turn_completed_observed",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in (
        "worker_loopx_cli_call_total",
        "loopx_prompt_driven_case_cli_call_count",
        "required_worker_loopx_cli_call_total_min",
        "worker_self_validation_official_score_mismatch_count",
        "worker_validation_scope_ambiguous_official_score_failure_count",
        "worker_bridge_connected_official_score_failure_count",
        "worker_startup_blocker_count",
        "worker_setup_diagnostic_file_count",
        "worker_setup_diagnostic_schema_ok_count",
        "worker_submit_eligible_mismatch_count",
        "worker_bridge_writeback_loss_count",
        "environment_setup_failure_before_worker_count",
        "pre_worker_agent_setup_failure_count",
        "worker_runtime_exception_before_checkpoint_count",
        "verifier_failure_attribution_count",
        "verifier_dependency_failure_count",
        "controller_max_round_observed",
        "controller_max_rounds_budget",
        "controller_followup_prompt_count",
    ):
        if isinstance(value.get(field), int) and not isinstance(value.get(field), bool):
            compact[field] = value[field]
    round_timeout = value.get("controller_round_timeout_sec")
    if isinstance(round_timeout, (int, float)) and not isinstance(round_timeout, bool):
        compact["controller_round_timeout_sec"] = round_timeout
    score = value.get("official_score_value")
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        compact["official_score_value"] = score

    policy = value.get("wall_time_policy") if isinstance(value.get("wall_time_policy"), dict) else {}
    if policy:
        compact_policy: dict[str, Any] = {}
        for field in ("schema_version", "kind", "timeout_tier", "interrupt_reason"):
            text = public_safe_compact_text(policy.get(field), limit=140)
            if text:
                compact_policy[field] = text
        for field in (
            "interrupted",
            "changes_official_benchmark_timeout",
            "changes_official_task_resources",
            "official_timeout_comparable",
            "leaderboard_claim_allowed",
            "observed_true_long_task_bar_met",
            "expected_true_long_task_bar_met",
            "true_long_task_bar_met",
            "expected_hours_scale_bar_met",
        ):
            if isinstance(policy.get(field), bool):
                compact_policy[field] = policy[field]
        for field in (
            "wall_time_seconds",
            "wall_time_limit_seconds",
            "true_long_task_bar_seconds",
            "preferred_hours_scale_bar_seconds",
        ):
            number = policy.get(field)
            if isinstance(number, (int, float)) and not isinstance(number, bool):
                compact_policy[field] = number
        if compact_policy:
            compact["wall_time_policy"] = compact_policy

    labels = public_safe_compact_list(
        value.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if labels:
        compact["failure_attribution_labels"] = labels

    boundary = value.get("claim_boundary") if isinstance(value.get("claim_boundary"), dict) else {}
    if boundary:
        compact_boundary: dict[str, Any] = {}
        allowed = public_safe_compact_text(boundary.get("public_claim_allowed"), limit=180)
        if allowed:
            compact_boundary["public_claim_allowed"] = allowed
        for field in (
            "bridge_connectivity_claim_allowed",
            "case_success_claim_allowed",
            "official_score_claim_allowed",
            "leaderboard_claim_allowed",
        ):
            if isinstance(boundary.get(field), bool):
                compact_boundary[field] = boundary[field]
        forbidden = public_safe_compact_list(
            boundary.get("forbidden_claims"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if forbidden:
            compact_boundary["forbidden_claims"] = forbidden
        if compact_boundary:
            compact["claim_boundary"] = compact_boundary

    env_context = _compact_environment_setup_failure_context(
        value.get("environment_setup_failure_context")
    )
    if env_context:
        compact["environment_setup_failure_context"] = env_context

    return compact


def _compact_environment_setup_failure_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "surface",
        "failure_kind",
        "diagnostic_granularity",
        "exception_type",
        "timeout_signal",
        "resource_signal",
        "environment_setup_duration_tier",
        "next_probe",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "environment_setup_present",
        "environment_setup_started",
        "environment_setup_finished",
        "agent_setup_started",
        "agent_execution_started",
        "worker_trace_present",
        "worker_benchmark_run_present",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    seconds = value.get("environment_setup_duration_seconds")
    if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
        compact["environment_setup_duration_seconds"] = seconds
    return compact


def _compact_benchmark_episode_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {}
    for field in (
        "schema_version",
        "mode",
        "worker_topology",
        "loopx_role",
        "runner_role",
        "checkpoint_surface",
        "resumable_episode_style",
    ):
        text = public_safe_compact_text(value.get(field), limit=140)
        if text:
            compact[field] = text
    for field in (
        "runner_side_guaranteed_writeback",
        "does_not_spawn_additional_agents",
        "does_not_split_task_prompt",
        "does_not_change_task_solution_actor",
        "raw_trace_recorded",
        "product_mode",
        "blind_loop",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    interval = value.get("checkpoint_interval_seconds")
    if isinstance(interval, int) and not isinstance(interval, bool):
        compact["checkpoint_interval_seconds"] = interval
    return compact


def _benchmark_run_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_run")
    if isinstance(nested, dict) and nested.get("schema_version") == BENCHMARK_RUN_SCHEMA_VERSION:
        return nested
    if run.get("schema_version") == BENCHMARK_RUN_SCHEMA_VERSION:
        return run
    return None


def compact_benchmark_run(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_run_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_RUN_SCHEMA_VERSION}
    for field in ("source_runner", "benchmark_id", "job_name", "mode"):
        value = public_safe_compact_text(source.get(field), limit=120)
        if value:
            compact[field] = value
    trials_source = source.get("trials") if isinstance(source.get("trials"), list) else []
    first_trial = trials_source[0] if trials_source and isinstance(trials_source[0], dict) else {}
    case_ids_source = (
        source.get("case_ids") if isinstance(source.get("case_ids"), list) else []
    )
    case_id = (
        public_safe_compact_text(source.get("case_id"), limit=120)
        or public_safe_compact_text(source.get("task_id"), limit=120)
        or public_safe_compact_text(first_trial.get("task_id"), limit=120)
        or (
            public_safe_compact_text(case_ids_source[0], limit=120)
            if case_ids_source
            else None
        )
    )
    if case_id:
        compact["case_id"] = case_id
        case_ids = public_safe_compact_list(case_ids_source, limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        compact["case_ids"] = case_ids or [case_id]
    for field in (
        "worker_mode",
        "trace_publicness",
        "first_blocker",
        "score_failure_attribution",
        "validation_scope",
        "worker_submit_eligible_mismatch_reason",
        "worker_bridge_writeback_loss_reason",
        "worker_bridge_materialization_status",
        "worker_bridge_materialization_blocker",
        "worker_bridge_failure_attribution",
        "repeat_blocked_by",
        "pre_worker_startup_blocker",
        "environment_setup_probe_status",
        "runner_return_status",
        "official_score_source",
        "official_score_status",
        "skillsbench_route_semantics",
        "native_goal_mode_confirmation_status",
        "loopx_treatment_evidence_tier",
        "loopx_treatment_claim_blocker",
    ):
        value = public_safe_compact_text(source.get(field), limit=140)
        if value:
            compact[field] = value
    for field in (
        "loopx_cli_bridge_surface",
        "loopx_cli_bridge_contract",
        "loopx_cli_bridge_scope",
        "loopx_counter_scope",
    ):
        value = public_safe_compact_text(source.get(field), limit=140)
        if value:
            compact[field] = value
    for field in (
        "real_run",
        "submit_eligible",
        "case_semantics_changed_by_harness",
        "loopx_inside_case",
        "loopx_automation_loop",
        "product_mode",
        "official_score_comparable_to_native_codex",
        "official_score_comparable_to_loopx_treatment",
        "model_plus_harness_pair",
        "control_plane_score_applicable",
        "startup_surface_calibration",
        "hardened_install_surface",
        "hardened_install_baseline",
        "environment_setup_probe_run",
        "environment_setup_probe_cleared",
        "leaderboard_evidence",
        "loopx_cli_bridge_contract_available",
        "loopx_cli_bridge_trace_observed",
        "loopx_worker_cli_bridge_available",
        "loopx_worker_cli_bridge_trace_observed",
        "loopx_prompt_driven_trace_observed",
        "loopx_prompt_driven_lifecycle_observed",
        "loopx_controller_trace_present",
        "loopx_controller_trace_public_safe",
        "controller_turn_completed_observed",
        "assisted_collaboration_claim_allowed",
        "official_score_claim_allowed",
        "bridge_connectivity_claim_allowed",
        "case_success_claimed",
        "official_verifier_validation_present",
        "official_case_success",
        "active_user_simulator_injection_channel_available",
        "inner_codex_goal_mode",
        "native_goal_mode_requested",
        "native_goal_mode_invoked",
        "codex_acp_protocol_used",
        "blind_loop",
        "agent_declared_done",
        "official_feedback_blinded",
        "reward_feedback_forwarded",
        "native_goal_worker_route",
        "native_goal_worker_connected",
        "native_goal_worker_trace_dir_present",
        "native_goal_worker_public_trace_read",
        "native_goal_worker_raw_material_recorded",
        "remote_command_file_bridge_consumed_by_solver",
        "remote_command_file_bridge_solver_trace_dir_present",
        "remote_command_file_bridge_solver_public_trace_read",
        "remote_command_file_bridge_solver_raw_material_recorded",
        "strict_loopx_treatment_claim_allowed",
        "controller_trace_present",
    ):
        if isinstance(source.get(field), bool):
            compact[field] = source.get(field)
    for field in (
        "runner_loopx_cli_call_total",
        "worker_loopx_cli_call_total",
        "loopx_prompt_driven_case_cli_call_count",
        "loopx_prompt_driven_trace_file_count",
        "loopx_prompt_driven_compact_file_count",
        "worker_counter_trace_trial_count",
        "worker_benchmark_run_file_count",
        "worker_benchmark_run_schema_ok_count",
        "worker_self_validation_official_score_mismatch_count",
        "worker_validation_scope_ambiguous_official_score_failure_count",
        "worker_bridge_connected_official_score_failure_count",
        "worker_startup_blocker_count",
        "worker_setup_diagnostic_file_count",
        "worker_setup_diagnostic_schema_ok_count",
        "worker_submit_eligible_mismatch_count",
        "worker_bridge_writeback_loss_count",
        "environment_setup_failure_before_worker_count",
        "pre_worker_agent_setup_failure_count",
        "worker_runtime_exception_before_checkpoint_count",
        "verifier_failure_attribution_count",
        "verifier_dependency_failure_count",
        "official_zero_observation_count",
        "planned_worker_loopx_cli_call_total",
        "required_worker_loopx_cli_call_total_min",
        "native_goal_worker_connect_count",
        "native_goal_worker_trace_count",
        "native_goal_worker_lifecycle_trace_count",
        "native_goal_worker_prompt_received_count",
        "native_goal_worker_ok_count",
        "native_goal_worker_goal_get_count",
        "native_goal_worker_turn_start_count",
        "native_goal_worker_turn_completed_observed_count",
        "native_goal_worker_assistant_message_present_count",
        "native_goal_worker_assistant_context_only_count",
        "native_goal_worker_context_only_recovery_attempted_count",
        "native_goal_worker_context_only_recovery_succeeded_count",
        "native_goal_worker_context_only_followup_start_attempted_count",
        "native_goal_worker_context_only_followup_start_succeeded_count",
        "native_goal_worker_transport_reconnect_attempted_count",
        "native_goal_worker_transport_reconnect_succeeded_count",
        "native_goal_worker_goal_reactivation_attempted_count",
        "native_goal_worker_goal_reactivation_succeeded_count",
        "native_goal_worker_post_context_assistant_chars_total",
        "native_goal_worker_first_action_observed_count",
        "native_goal_worker_effective_action_observed_count",
        "remote_command_file_bridge_solver_trace_count",
        "remote_command_file_bridge_solver_probe_ready_count",
        "remote_command_file_bridge_solver_operation_count",
        "controller_max_round_observed",
        "controller_max_rounds_budget",
        "controller_initial_prompt_count",
        "controller_followup_prompt_count",
        "controller_action_decisions",
        "controller_no_active_todo_confirmed_count",
        "max_rounds_budget",
        "round_reward_count",
    ):
        if isinstance(source.get(field), int) and not isinstance(source.get(field), bool):
            compact[field] = source.get(field)
    for field in ("controller_round_timeout_sec",):
        if isinstance(source.get(field), (int, float)) and not isinstance(
            source.get(field), bool
        ):
            compact[field] = source.get(field)
    for field in ("controller_last_decision",):
        value = public_safe_compact_text(source.get(field), limit=120)
        if value:
            compact[field] = value
    for field in ("loopx_prompt_driven_event_counts",):
        calls = _compact_numeric_map(source.get(field))
        if calls:
            compact[field] = calls
    loop_contract = source.get("benchmark_loop_contract")
    if isinstance(loop_contract, dict):
        compact_loop_contract: dict[str, Any] = {}
        for field in (
            "schema_version",
            "route",
            "protocol_id",
            "claim_blocker",
        ):
            value = public_safe_compact_text(loop_contract.get(field), limit=120)
            if value:
                compact_loop_contract[field] = value
        for field in (
            "official_feedback_forwarded",
            "official_feedback_blinded",
            "blind_loop",
            "product_mode",
            "strict_treatment_claim_allowed",
        ):
            if isinstance(loop_contract.get(field), bool):
                compact_loop_contract[field] = loop_contract[field]
        if isinstance(loop_contract.get("max_rounds_budget"), int) and not isinstance(
            loop_contract.get("max_rounds_budget"),
            bool,
        ):
            compact_loop_contract["max_rounds_budget"] = loop_contract[
                "max_rounds_budget"
            ]
        if compact_loop_contract:
            compact["benchmark_loop_contract"] = compact_loop_contract
    if isinstance(source.get("official_score"), (int, float)) and not isinstance(
        source.get("official_score"),
        bool,
    ):
        compact["official_score"] = source.get("official_score")

    labels = public_safe_compact_list(
        source.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if labels:
        compact["failure_attribution_labels"] = labels
    worker_startup_blockers = public_safe_compact_list(
        source.get("worker_startup_blockers"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if worker_startup_blockers:
        compact["worker_startup_blockers"] = worker_startup_blockers
    worker_setup_diagnostic_blockers = public_safe_compact_list(
        source.get("worker_setup_diagnostic_blockers"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if worker_setup_diagnostic_blockers:
        compact["worker_setup_diagnostic_blockers"] = (
            worker_setup_diagnostic_blockers
        )
    runner_warning_labels = public_safe_compact_list(
        source.get("runner_warning_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    if runner_warning_labels:
        compact["runner_warning_labels"] = runner_warning_labels
    runner_prerequisites = _compact_benchmark_runner_prerequisites(
        source.get("runner_prerequisites")
    )
    if runner_prerequisites:
        compact["runner_prerequisites"] = runner_prerequisites
    result_discovery = _compact_benchmark_result_discovery(
        source.get("result_discovery")
    )
    if result_discovery:
        compact["result_discovery"] = result_discovery
    task_setup_preflight = _compact_benchmark_task_setup_preflight(
        source.get("task_setup_preflight")
    )
    if task_setup_preflight:
        compact["task_setup_preflight"] = task_setup_preflight
    task_staging = _compact_benchmark_task_staging(source.get("task_staging"))
    if task_staging:
        compact["task_staging"] = task_staging
    attempt_accounting = _compact_benchmark_attempt_accounting(
        source.get("attempt_accounting")
    )
    if attempt_accounting:
        compact["attempt_accounting"] = attempt_accounting

    official = source.get("official_task_score") if isinstance(source.get("official_task_score"), dict) else {}
    if official:
        compact_official: dict[str, Any] = {}
        kind = public_safe_compact_text(official.get("kind"), limit=80)
        if kind:
            compact_official["kind"] = kind
        for field in ("value", "passed"):
            if isinstance(official.get(field), (bool, int, float)):
                compact_official[field] = official.get(field)
        if compact_official:
            compact["official_task_score"] = compact_official

    claim_boundary = source.get("claim_boundary")
    if isinstance(claim_boundary, dict):
        compact_claim_boundary: dict[str, Any] = {}
        allowed = public_safe_compact_text(
            claim_boundary.get("public_claim_allowed"),
            limit=180,
        )
        if allowed:
            compact_claim_boundary["public_claim_allowed"] = allowed
        for field in (
            "bridge_connectivity_claim_allowed",
            "case_success_claim_allowed",
            "official_score_claim_allowed",
            "leaderboard_claim_allowed",
        ):
            if isinstance(claim_boundary.get(field), bool):
                compact_claim_boundary[field] = claim_boundary[field]
        forbidden = public_safe_compact_list(
            claim_boundary.get("forbidden_claims"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if forbidden:
            compact_claim_boundary["forbidden_claims"] = forbidden
        if compact_claim_boundary:
            compact["claim_boundary"] = compact_claim_boundary

    agent = source.get("agent") if isinstance(source.get("agent"), dict) else {}
    compact_agent: dict[str, Any] = {}
    for field in ("name", "import_path", "model"):
        value = public_safe_compact_text(agent.get(field), limit=120)
        if value:
            compact_agent[field] = value
    kwargs_keys = public_safe_compact_list(agent.get("kwargs_keys"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    if kwargs_keys:
        compact_agent["kwargs_keys"] = kwargs_keys
    if compact_agent:
        compact["agent"] = compact_agent

    model_control = source.get("model_control")
    if isinstance(model_control, dict):
        compact_model_control: dict[str, Any] = {}
        for field in (
            "schema_version",
            "requested_model",
            "reported_model",
            "control_method",
            "control_status",
            "actual_model_source",
        ):
            value = public_safe_compact_text(model_control.get(field), limit=140)
            if value:
                compact_model_control[field] = value
        if isinstance(model_control.get("actual_model_verified"), bool):
            compact_model_control["actual_model_verified"] = model_control[
                "actual_model_verified"
            ]
        warning_labels = public_safe_compact_list(
            model_control.get("warning_labels"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if warning_labels:
            compact_model_control["warning_labels"] = warning_labels
        if compact_model_control:
            compact["model_control"] = compact_model_control

    runner_failure = source.get("runner_failure")
    if isinstance(runner_failure, dict):
        compact_runner_failure: dict[str, Any] = {}
        for field in ("schema_version", "exception_type", "failure_class"):
            value = public_safe_compact_text(runner_failure.get(field), limit=140)
            if value:
                compact_runner_failure[field] = value
        for field in (
            "raw_error_recorded",
            "raw_logs_read",
            "raw_task_text_read",
            "raw_trajectory_read",
        ):
            if isinstance(runner_failure.get(field), bool):
                compact_runner_failure[field] = runner_failure[field]
        controller_cutoff = runner_failure.get("controller_cutoff")
        if isinstance(controller_cutoff, dict):
            compact_cutoff: dict[str, Any] = {}
            for field in ("schema_version", "reason"):
                value = public_safe_compact_text(
                    controller_cutoff.get(field),
                    limit=140,
                )
                if value:
                    compact_cutoff[field] = value
            if isinstance(controller_cutoff.get("cutoff_before_followup"), bool):
                compact_cutoff["cutoff_before_followup"] = controller_cutoff[
                    "cutoff_before_followup"
                ]
            for field in (
                "max_rounds_budget",
                "initial_prompt_count",
                "followup_prompt_count",
                "stop_decision_count",
            ):
                if isinstance(controller_cutoff.get(field), int) and not isinstance(
                    controller_cutoff.get(field),
                    bool,
                ):
                    compact_cutoff[field] = controller_cutoff[field]
            if compact_cutoff:
                compact_runner_failure["controller_cutoff"] = compact_cutoff
        user_loop_recovery = runner_failure.get("user_loop_recovery")
        if isinstance(user_loop_recovery, dict):
            compact_recovery: dict[str, Any] = {}
            for field in ("schema_version", "stage", "exception_type"):
                value = public_safe_compact_text(
                    user_loop_recovery.get(field),
                    limit=140,
                )
                if value:
                    compact_recovery[field] = value
            for field in ("preserved_final_verify", "raw_error_recorded"):
                if isinstance(user_loop_recovery.get(field), bool):
                    compact_recovery[field] = user_loop_recovery[field]
            for field in ("round", "delta_events", "delta_tool_calls"):
                if isinstance(user_loop_recovery.get(field), int) and not isinstance(
                    user_loop_recovery.get(field),
                    bool,
                ):
                    compact_recovery[field] = user_loop_recovery[field]
            if compact_recovery:
                compact_runner_failure["user_loop_recovery"] = compact_recovery
        native_goal_worker = runner_failure.get("native_goal_worker")
        if isinstance(native_goal_worker, dict):
            compact_native_worker: dict[str, Any] = {}
            for field in (
                "schema_version",
                "trace_status",
                "failure_label",
                "failure_category",
                "first_blocker",
            ):
                value = public_safe_compact_text(
                    native_goal_worker.get(field),
                    limit=140,
                )
                if value:
                    compact_native_worker[field] = value
            for field in (
                "trace_count",
            ):
                value = native_goal_worker.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    compact_native_worker[field] = value
            for field in (
                "raw_transcript_recorded",
                "raw_assistant_message_recorded",
            ):
                if isinstance(native_goal_worker.get(field), bool):
                    compact_native_worker[field] = native_goal_worker[field]
            if compact_native_worker:
                compact_runner_failure["native_goal_worker"] = compact_native_worker
        if compact_runner_failure:
            compact["runner_failure"] = compact_runner_failure

    fingerprint = source.get("runner_failure_fingerprint")
    if isinstance(fingerprint, dict):
        compact_fingerprint: dict[str, Any] = {}
        for field in (
            "schema_version",
            "error_len_bucket",
            "fingerprint_confidence",
        ):
            value = public_safe_compact_text(fingerprint.get(field), limit=100)
            if value:
                compact_fingerprint[field] = value
        if isinstance(fingerprint.get("line_count"), int) and not isinstance(
            fingerprint.get("line_count"),
            bool,
        ):
            compact_fingerprint["line_count"] = fingerprint["line_count"]
        matched_patterns = public_safe_compact_list(
            fingerprint.get("matched_patterns"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if matched_patterns:
            compact_fingerprint["matched_patterns"] = matched_patterns
        for field in (
            "error_present",
            "has_host_paths",
            "has_urls",
            "has_secret_like_tokens",
            "raw_error_recorded",
        ):
            if isinstance(fingerprint.get(field), bool):
                compact_fingerprint[field] = fingerprint[field]
        if compact_fingerprint:
            compact["runner_failure_fingerprint"] = compact_fingerprint

    compose_setup_diagnostic = _compact_benchmark_compose_setup_diagnostic(
        source.get("compose_setup_diagnostic")
    )
    if compose_setup_diagnostic:
        compact["compose_setup_diagnostic"] = compose_setup_diagnostic
        _apply_skillsbench_pre_agent_setup_compact_projection(compact)

    progress = _compact_numeric_map(
        source.get("progress"),
        keys=(
            "n_total_trials",
            "n_completed_trials",
            "n_errored_trials",
            "n_running_trials",
            "n_pending_trials",
            "n_cancelled_trials",
            "n_retries",
        ),
    )
    if progress:
        compact["progress"] = progress

    metrics = _compact_numeric_map(
        source.get("metrics"),
        keys=("input_tokens", "cache_tokens", "output_tokens", "cost_usd"),
    )
    if metrics:
        compact["metrics"] = metrics

    interaction_counters = _compact_benchmark_interaction_counters(
        source.get("interaction_counters")
    )
    if interaction_counters:
        compact["interaction_counters"] = interaction_counters

    goal_start_control_score = _compact_goal_start_product_mode_control_score(
        source.get("goal_start_product_mode_control_score")
    )
    if goal_start_control_score:
        compact["goal_start_product_mode_control_score"] = goal_start_control_score

    round_reward_trace = _compact_benchmark_round_reward_trace(
        source.get("round_reward_trace")
    )
    if round_reward_trace:
        compact["round_reward_trace"] = round_reward_trace

    overhead_attribution_counters = (
        _compact_benchmark_overhead_attribution_counters(
            source.get("overhead_attribution_counters")
        )
    )
    if overhead_attribution_counters:
        compact["overhead_attribution_counters"] = overhead_attribution_counters

    episode_policy = _compact_benchmark_episode_policy(source.get("episode_policy"))
    if episode_policy:
        compact["episode_policy"] = episode_policy

    product_mode_lifecycle_contract = _compact_product_mode_lifecycle_contract(
        source.get("product_mode_lifecycle_contract")
    )
    if product_mode_lifecycle_contract:
        compact["product_mode_lifecycle_contract"] = product_mode_lifecycle_contract
        _repair_product_mode_lifecycle_missing_attribution(compact)

    native_goal_worker_contract = _compact_native_goal_worker_contract(
        source.get("native_goal_worker_contract")
    )
    if native_goal_worker_contract:
        compact["native_goal_worker_contract"] = native_goal_worker_contract
    app_server_goal_round_semantics = _compact_app_server_goal_round_semantics(
        source.get("app_server_goal_round_semantics")
    )
    if app_server_goal_round_semantics:
        compact["app_server_goal_round_semantics"] = app_server_goal_round_semantics

    case_event_timeline = _compact_benchmark_case_event_timeline(
        source.get("case_event_timeline")
    )
    if case_event_timeline:
        compact["case_event_timeline"] = case_event_timeline

    preflight_guard = _compact_benchmark_preflight_guard(source.get("preflight_guard"))
    if preflight_guard:
        compact["preflight_guard"] = preflight_guard

    active_user_preflight = _compact_active_user_assisted_treatment_preflight(
        source.get("active_user_assisted_treatment_preflight")
    )
    if active_user_preflight:
        compact["active_user_assisted_treatment_preflight"] = active_user_preflight

    active_user_launcher_plan = _compact_active_user_private_launcher_plan(
        source.get("active_user_private_launcher_plan")
    )
    if active_user_launcher_plan:
        compact["active_user_private_launcher_plan"] = active_user_launcher_plan

    active_user_observation = _compact_active_user_observation(
        source.get("active_user_observation")
    )
    if active_user_observation:
        compact["active_user_observation"] = active_user_observation

    claim_gate = _compact_benchmark_claim_gate(source.get("claim_gate"))
    if claim_gate:
        compact["claim_gate"] = claim_gate

    private_runner_launch = _compact_benchmark_private_runner_launch(
        source.get("private_runner_launch_summary")
    )
    if private_runner_launch:
        compact["private_runner_launch_summary"] = private_runner_launch

    setup_timeout_repair_profile = _compact_benchmark_repair_profile(
        source.get("setup_timeout_repair_profile")
    )
    if setup_timeout_repair_profile:
        compact["setup_timeout_repair_profile"] = setup_timeout_repair_profile

    env_context = _compact_environment_setup_failure_context(
        source.get("environment_setup_failure_context")
    )
    if env_context:
        compact["environment_setup_failure_context"] = env_context

    worker_bridge_outcome = _compact_worker_bridge_outcome(
        source.get("worker_bridge_outcome")
    )
    if worker_bridge_outcome:
        compact["worker_bridge_outcome"] = worker_bridge_outcome

    validation = source.get("validation") if isinstance(source.get("validation"), dict) else {}
    if validation:
        failed = [
            str(key)
            for key, value in validation.items()
            if isinstance(key, str)
            and key not in BENCHMARK_VALIDATION_NEUTRAL_FALSE_FIELDS
            and isinstance(value, bool)
            and not value
        ][:MAX_BENCHMARK_RUN_LIST_ITEMS]
        native_goal_worker_trace_missing = (
            validation.get("native_goal_worker_route") is True
            and public_safe_compact_text(
                validation.get("native_goal_worker_trace_status"),
                limit=140,
            )
            in {
                "worker_connected_trace_dir_missing",
                "worker_connected_no_public_trace",
                "worker_connected_no_prompt_trace",
                "worker_prompt_received_no_turn_trace",
                "worker_connected_no_turn_trace",
                "worker_route_selected_not_connected",
            }
        )
        if (
            native_goal_worker_trace_missing
            and compact.get("pre_agent_setup_materialization_blocked") is not True
            and "native_goal_worker_public_trace_missing" not in failed
            and len(failed) < MAX_BENCHMARK_RUN_LIST_ITEMS
        ):
            failed.append("native_goal_worker_public_trace_missing")
        if (
            compact.get("pre_agent_setup_materialization_blocked") is True
            and "pre_agent_setup_materialization_blocked" not in failed
            and len(failed) < MAX_BENCHMARK_RUN_LIST_ITEMS
        ):
            failed.append("pre_agent_setup_materialization_blocked")
        compact_validation: dict[str, Any] = {
            "all_passed": not failed
            and all(
                bool(value)
                for key, value in validation.items()
                if isinstance(key, str)
                and key not in BENCHMARK_VALIDATION_NEUTRAL_FALSE_FIELDS
                and isinstance(value, bool)
            ),
            "failed_checks": failed,
        }
        for field in (
            "validation_scope",
            "case_success_claim_kind",
            "official_verifier_status",
            "native_goal_worker_trace_status",
            "native_goal_worker_failure_category",
            "native_goal_worker_first_blocker",
        ):
            text = public_safe_compact_text(validation.get(field), limit=140)
            if text:
                compact_validation[field] = text
        for field in (
            "native_goal_worker_trace_count",
            "native_goal_worker_lifecycle_trace_count",
            "native_goal_worker_prompt_received_count",
            "native_goal_worker_first_action_observed_count",
            "native_goal_worker_effective_action_observed_count",
        ):
            value = validation.get(field)
            if isinstance(value, int) and not isinstance(value, bool):
                compact_validation[field] = value
        for field in (
            "active_user_assisted_treatment_preflight",
            "bridge_connected",
            "bridge_connectivity_claim_allowed",
            "case_success_claimed",
            "official_verifier_validation_present",
            "official_case_success",
            "active_user_simulator_contract_checked",
            "simulator_to_worker_injection_channel_checked",
            "simulator_to_worker_injection_channel_probe_checked",
            "missing_simulator_to_worker_injection_channel_recorded",
            "simulator_to_worker_external_update_loop_available",
            "real_assisted_worker_observation_missing",
            "active_user_observation_fixture",
            "worker_observation_proof",
            "scripted_active_user_intervention_observed",
            "no_real_user_message_injected",
            "no_model_backed_simulator_invoked",
            "no_oracle_audit_required",
            "assisted_score_kept_separate_from_official",
            "real_result_reducer_materialized",
            "compact_run_read",
            "compact_result_read",
            "selected_tag_checked",
            "selected_image_only",
            "single_tag_only",
            "buggy_source_extracted",
            "fixed_source_not_extracted_to_host",
            "host_codex_cli_invoked",
            "patch_exported_from_buggy_source_git_diff",
            "patch_applied_in_container",
            "patch_hash_recorded",
            "patched_eval_exit_zero",
            "patched_eval_success_marker",
            "private_runner_script_materialized",
            "private_runner_manifest_materialized",
            "script_executable_bit_set",
            "script_content_not_public",
            "script_path_relative_only",
            "phase_order_rendered",
            "script_renders_source_extraction",
            "script_renders_observed_image_source_path",
            "script_renders_precheck_only",
            "script_handles_gitkeep_placeholder",
            "script_renders_git_baseline",
            "script_renders_host_codex",
            "script_renders_patch_export",
            "script_renders_selected_tag_eval",
            "script_renders_entrypoint_eval_commands",
            "script_renders_compact_evidence",
            "script_renders_real_result_reducer",
            "no_generator_codex_execution",
            "no_generator_docker_execution",
            "no_generator_model_api_invoked",
            "no_generator_upload",
            "no_generator_submit",
            "no_generator_public_ranking_path",
            "no_auth_material_sync",
            "no_upload",
            "no_submit",
            "no_public_ranking_path",
            "no_raw_logs_public",
            "no_patch_content_public",
            "no_absolute_paths_public",
            "no_codex_auth_sync",
            "no_credential_values_recorded",
            "no_reducer_codex_execution",
            "no_reducer_docker_execution",
            "worker_bridge_materialized_when_required",
            "worker_bridge_repeat_ready",
            "worker_startup_blocker_recorded",
            "loopx_controller_trace_present",
            "loopx_controller_trace_public_safe",
            "native_goal_worker_route",
            "native_goal_worker_connected",
            "native_goal_worker_trace_dir_present",
            "native_goal_worker_public_trace_read",
            "native_goal_worker_trace_observed",
            "native_goal_worker_countable_baseline",
            "runner_failure_compact_recorded",
            "no_raw_logs_read",
            "no_raw_task_text_read",
            "no_raw_trajectory_read",
            "no_leaderboard_upload_requested",
        ):
            if isinstance(validation.get(field), bool):
                compact_validation[field] = validation[field]
        compact["validation"] = compact_validation
        _apply_skillsbench_pre_agent_setup_compact_projection(compact)

    solution_quality = build_skillsbench_solution_quality_signals(compact)
    if solution_quality:
        compact["solution_quality_signals"] = solution_quality

    post_run_debug_gate = build_skillsbench_post_run_debug_gate(compact)
    if post_run_debug_gate:
        compact["post_run_debug_gate"] = post_run_debug_gate

    trials: list[dict[str, Any]] = []
    for trial in trials_source or []:
        if not isinstance(trial, dict):
            continue
        compact_trial: dict[str, Any] = {}
        for field in (
            "task_id",
            "trial_name",
            "source",
            "exception_type",
            "worker_start_status",
            "verifier_failure_attribution",
        ):
            value = public_safe_compact_text(trial.get(field), limit=140)
            if value:
                compact_trial[field] = value
        labels = public_safe_compact_list(
            trial.get("verifier_failure_attribution_labels"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if labels:
            compact_trial["verifier_failure_attribution_labels"] = labels
        agent_labels = public_safe_compact_list(
            trial.get("agent_failure_attribution_labels"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if agent_labels:
            compact_trial["agent_failure_attribution_labels"] = agent_labels
        reward = _compact_numeric_map(trial.get("reward"))
        if reward:
            compact_trial["reward"] = reward
        trial_metrics = _compact_numeric_map(
            trial.get("metrics"),
            keys=("input_tokens", "cache_tokens", "output_tokens", "cost_usd"),
        )
        if trial_metrics:
            compact_trial["metrics"] = trial_metrics
        for field in ("trajectory_present", "verifier_reward_present", "artifact_manifest_present", "trial_result_present"):
            if isinstance(trial.get(field), bool):
                compact_trial[field] = trial.get(field)
        env_context = _compact_environment_setup_failure_context(
            trial.get("environment_setup_failure_context")
        )
        if env_context:
            compact_trial["environment_setup_failure_context"] = env_context
        official_zero = trial.get("official_zero_observation")
        if isinstance(official_zero, dict):
            compact_zero: dict[str, Any] = {}
            for field in (
                "schema_version",
                "reward_value",
            ):
                value = official_zero.get(field)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    compact_zero[field] = value
                elif isinstance(value, str):
                    text = public_safe_compact_text(value, limit=80)
                    if text:
                        compact_zero[field] = text
            for field in (
                "detected",
                "exception_present",
                "environment_setup_completed",
                "agent_setup_completed",
                "agent_execution_completed",
                "verifier_completed",
                "raw_logs_read",
                "raw_trace_recorded",
                "task_text_read",
            ):
                if isinstance(official_zero.get(field), bool):
                    compact_zero[field] = official_zero[field]
            if compact_zero:
                compact_trial["official_zero_observation"] = compact_zero
        if compact_trial:
            trials.append(compact_trial)
            if len(trials) >= MAX_BENCHMARK_RUN_TRIALS:
                break
    if trials:
        compact["trials"] = trials
        raw_trials = source.get("trials")
        if isinstance(raw_trials, list):
            compact["trial_count"] = len(raw_trials)

    for field in ("evidence_files", "resume_or_inspect_commands", "stop_conditions"):
        values = public_safe_compact_list(source.get(field), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        if values:
            compact[field] = values

    read_boundary = source.get("read_boundary")
    if isinstance(read_boundary, dict):
        compact_boundary: dict[str, bool] = {}
        for field in (
            "compact_only",
            "raw_artifacts_read",
            "task_text_read",
            "trajectory_read",
            "controller_trace_read",
            "local_paths_recorded",
            "docker_invoked",
            "model_api_invoked",
            "upload_invoked",
        ):
            if isinstance(read_boundary.get(field), bool):
                compact_boundary[field] = read_boundary[field]
        if compact_boundary:
            compact["read_boundary"] = compact_boundary

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def worker_bridge_ingest_health_note(
    benchmark_run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Derive a compact agent-facing health note for worker-written run ingest."""

    if not isinstance(benchmark_run, dict):
        return None
    outcome = benchmark_run.get("worker_bridge_outcome")
    if not isinstance(outcome, dict):
        return None

    verified = bool(outcome.get("worker_bridge_verified"))
    runner_status = public_safe_compact_text(
        outcome.get("runner_return_status"),
        limit=120,
    )
    official_status = public_safe_compact_text(
        outcome.get("official_score_status"),
        limit=120,
    )
    bridge_surface = public_safe_compact_text(outcome.get("bridge_surface"), limit=120)
    trace_publicness = public_safe_compact_text(
        outcome.get("trace_publicness") or benchmark_run.get("trace_publicness"),
        limit=120,
    )
    materialization_status = public_safe_compact_text(
        outcome.get("worker_bridge_materialization_status")
        or benchmark_run.get("worker_bridge_materialization_status"),
        limit=120,
    )
    materialization_blocker = public_safe_compact_text(
        outcome.get("worker_bridge_materialization_blocker")
        or benchmark_run.get("worker_bridge_materialization_blocker")
        or benchmark_run.get("first_blocker"),
        limit=120,
    )
    failure_attribution = public_safe_compact_text(
        outcome.get("worker_bridge_failure_attribution")
        or benchmark_run.get("worker_bridge_failure_attribution"),
        limit=120,
    )
    cli_total = outcome.get("worker_loopx_cli_call_total")
    required_total = outcome.get("required_worker_loopx_cli_call_total_min")
    if isinstance(cli_total, bool) or not isinstance(cli_total, int):
        cli_total = 0
    if isinstance(required_total, bool) or not isinstance(required_total, int):
        required_total = 1

    validation = (
        benchmark_run.get("validation")
        if isinstance(benchmark_run.get("validation"), dict)
        else {}
    )
    validation_all_passed = validation.get("all_passed")
    if not isinstance(validation_all_passed, bool):
        validation_all_passed = None
    env_context = _compact_environment_setup_failure_context(
        outcome.get("environment_setup_failure_context")
        or benchmark_run.get("environment_setup_failure_context")
    )

    if materialization_status == "environment_setup_failed_before_worker":
        health_state = "environment_setup_failed_before_worker"
        evidence_layer = "not_ready"
        next_action = "diagnose benchmark environment setup before worker startup"
    elif materialization_status == "pre_worker_setup_failed":
        health_state = (
            materialization_blocker
            or "pre_worker_agent_setup_failed_before_bridge_checkpoint"
        )
        evidence_layer = "not_ready"
        next_action = "repair Codex agent setup/launcher before another run"
    elif materialization_status == "pre_worker_startup_blocker_recorded":
        health_state = materialization_blocker or "pre_worker_startup_blocker_recorded"
        evidence_layer = "compact_startup_blocker"
        next_action = "repair recorded worker startup blocker before another run"
    elif materialization_status == "runtime_exception_before_checkpoint":
        health_state = "worker_runtime_exception_before_bridge_checkpoint"
        evidence_layer = "not_ready"
        next_action = "diagnose compact worker runtime failure before another run"
    elif materialization_status == "not_materialized":
        health_state = "worker_bridge_not_materialized"
        evidence_layer = "not_ready"
        next_action = "repair launcher or worker startup bridge materialization before another run"
    elif not verified:
        health_state = "worker_bridge_evidence_incomplete"
        evidence_layer = "not_ready"
        next_action = "repair worker bridge compact evidence before another run"
    elif runner_status == "completed" and official_status == "completed":
        health_state = "official_score_ingested"
        evidence_layer = "official_sample_score"
        next_action = "compare against the selected baseline under no-upload policy"
    elif runner_status.startswith("interrupted"):
        health_state = "runner_return_blocked_after_worker_bridge"
        evidence_layer = "worker_bridge_verified_runner_blocker"
        next_action = "close runner return or record an explicit runner-return blocker"
    else:
        health_state = "worker_bridge_verified_pending_runner_return"
        evidence_layer = "worker_bridge_ingest_only"
        next_action = "finish runner return or append the pending-runner blocker"

    note: dict[str, Any] = {
        "schema_version": WORKER_BRIDGE_INGEST_HEALTH_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_RUN_SCHEMA_VERSION,
        "health_state": health_state,
        "evidence_layer": evidence_layer,
        "worker_bridge_verified": verified,
        "runner_return_status": runner_status or "unknown",
        "official_score_status": official_status or "unknown",
        "worker_loopx_cli_call_total": cli_total,
        "required_worker_loopx_cli_call_total_min": required_total,
        "worker_bridge_materialization_status": materialization_status or "unknown",
        "worker_bridge_materialization_blocker": materialization_blocker or "none",
        "worker_bridge_failure_attribution": failure_attribution or "none",
        "validation_all_passed": validation_all_passed,
        "next_action": next_action,
        "may_claim": [
            "worker bridge ingest health from compact benchmark_run_v0",
        ],
        "must_not_claim": [
            "leaderboard uplift",
            "official reward complete without official score status completed",
            "raw trace public",
        ],
    }
    if bridge_surface:
        note["bridge_surface"] = bridge_surface
    if trace_publicness:
        note["trace_publicness"] = trace_publicness
    if env_context:
        note["environment_setup_failure_context"] = env_context
    return note


def _benchmark_result_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_result")
    if isinstance(nested, dict) and nested.get("schema_version") == BENCHMARK_RESULT_SCHEMA_VERSION:
        return nested
    if run.get("schema_version") == BENCHMARK_RESULT_SCHEMA_VERSION:
        return run
    return None


def _compact_score_layer(value: Any, *, include_schema: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    if include_schema:
        schema = public_safe_compact_text(value.get("schema_version"), limit=80)
        if schema:
            compact["schema_version"] = schema
    for field in ("kind", "aggregation"):
        text = public_safe_compact_text(value.get(field), limit=80)
        if text:
            compact[field] = text
    if isinstance(value.get("passed"), bool):
        compact["passed"] = value.get("passed")
    score_value = value.get("value")
    if isinstance(score_value, (int, float)) and not isinstance(score_value, bool):
        compact["value"] = score_value
    return compact


def _compact_control_plane_score(value: Any) -> dict[str, Any]:
    compact = _compact_score_layer(value, include_schema=True)
    if not isinstance(value, dict):
        return compact
    components = value.get("components") if isinstance(value.get("components"), dict) else {}
    compact_components: dict[str, Any] = {}
    for component in CONTROL_PLANE_SCORE_COMPONENTS:
        score = components.get(component)
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            compact_components[component] = score
    if compact_components:
        compact["components"] = compact_components
        compact["component_order"] = list(compact_components.keys())
    return compact


def compact_benchmark_result(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_result_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_RESULT_SCHEMA_VERSION}
    for field in (
        "task_id",
        "scenario_id",
        "worker_mode",
        "harness_identity",
        "worker_surface",
        "terminal_state",
        "trace_publicness",
    ):
        value = public_safe_compact_text(source.get(field), limit=120)
        if value:
            compact[field] = value

    official_score = _compact_score_layer(source.get("official_task_score"))
    if official_score:
        compact["official_task_score"] = official_score
    control_score = _compact_control_plane_score(source.get("control_plane_score"))
    if control_score:
        compact["control_plane_score"] = control_score

    counts = _compact_numeric_map(
        source,
        keys=(
            "step_count",
            "wall_time_ms",
            "validation_pass_count",
            "validation_fail_count",
            "changed_file_count",
            "forbidden_access_count",
            "stale_state_error_count",
            "writeback_count",
            "spend_count",
            "spend_before_validation_count",
            "goal_tick_phase_coverage",
        ),
    )
    if counts:
        compact["counts"] = counts

    for field in ("open_todo_preserved", "archive_hygiene_passed", "queue_contract_passed", "state_reconstructable"):
        if isinstance(source.get(field), bool):
            compact[field] = source.get(field)

    labels = public_safe_compact_list(source.get("failure_attribution_labels"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    if labels:
        compact["failure_attribution_labels"] = labels

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def _benchmark_comparison_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_comparison")
    if isinstance(nested, dict) and nested.get("schema_version") == BENCHMARK_COMPARISON_SCHEMA_VERSION:
        return nested
    if run.get("schema_version") == BENCHMARK_COMPARISON_SCHEMA_VERSION:
        return run
    return None


def _compact_comparison_delta(value: Any) -> int | float | str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return public_safe_compact_text(value, limit=120)


def _compact_benchmark_baseline_failure_gate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    compact: dict[str, Any] = {
        "schema_version": BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION,
    }
    for field in (
        "baseline_mode",
        "baseline_scenario_id",
        "baseline_terminal_state",
        "failure_phase",
        "failure_class",
        "negative_selection_reason",
        "minimum_next_evidence",
        "next_action",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "baseline_failed",
        "control_plane_addressable",
        "treatment_eligible",
        "same_task_semantics",
        "same_runner_protocol",
        "trace_publicness_verified",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("baseline_attempt_count",):
        count = value.get(field)
        if isinstance(count, int) and not isinstance(count, bool):
            compact[field] = count
    for field in ("failure_attribution_labels", "evidence_refs"):
        values = public_safe_compact_list(value.get(field), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        if values:
            compact[field] = values
    if set(compact.keys()) == {"schema_version"}:
        return {}
    return compact


def compact_benchmark_comparison(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_comparison_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_COMPARISON_SCHEMA_VERSION}
    for field in ("task_id", "comparison_id", "decision_id", "benchmark_id", "baseline_scenario_id", "treatment_scenario_id", "next_action"):
        value = public_safe_compact_text(source.get(field), limit=180)
        if value:
            compact[field] = value

    mode_pair = public_safe_compact_list(source.get("mode_pair"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    if mode_pair:
        compact["mode_pair"] = mode_pair

    for field in (
        "scenario_count",
        "official_task_score_delta",
        "control_plane_score_delta",
        "cost_delta_usd",
        "with_loopx_overhead_ms",
        "with_loopx_extra_writebacks",
        "with_loopx_extra_spends",
        "checklist_pass_count",
    ):
        delta = _compact_comparison_delta(source.get(field))
        if delta is not None:
            compact[field] = delta

    for field in (
        "both_success",
        "ready_to_attempt_no_submit_setup_probe",
        "ready_to_run_real_benchmark",
        "ready_to_submit_leaderboard",
        "requires_explicit_authorization_for_real_execution",
    ):
        if isinstance(source.get(field), bool):
            compact[field] = source.get(field)

    for field in ("metrics_compared", "interrupt_fixture_markers", "stop_conditions", "failure_attribution_labels"):
        values = public_safe_compact_list(source.get(field), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        if values:
            compact[field] = values

    claim_boundary = source.get("claim_boundary")
    if isinstance(claim_boundary, dict):
        compact_claim_boundary: dict[str, bool] = {}
        for field in (
            "leaderboard_claim_allowed",
            "official_score_uplift_claim_allowed",
            "assisted_collaboration_claim_allowed",
            "raw_trace_excluded",
            "credential_values_recorded",
        ):
            if isinstance(claim_boundary.get(field), bool):
                compact_claim_boundary[field] = claim_boundary[field]
        if compact_claim_boundary:
            compact["claim_boundary"] = compact_claim_boundary

    baseline_gate = _compact_benchmark_baseline_failure_gate(source.get("baseline_failure_gate"))
    if baseline_gate:
        compact["baseline_failure_gate"] = baseline_gate

    decision = source.get("decision")
    if isinstance(decision, dict):
        compact_decision: dict[str, Any] = {}
        for field in ("score_uplift", "validation_enhancement_point"):
            if isinstance(decision.get(field), bool):
                compact_decision[field] = decision[field]
        why = public_safe_compact_text(decision.get("why"), limit=240)
        if why:
            compact_decision["why"] = why
        if compact_decision:
            compact["decision"] = compact_decision

    result_refs: list[dict[str, Any]] = []
    for item in source.get("result_refs") or []:
        if not isinstance(item, dict):
            continue
        compact_ref: dict[str, Any] = {}
        for field in ("scenario_id", "task_id", "result_id"):
            value = public_safe_compact_text(item.get(field), limit=140)
            if value:
                compact_ref[field] = value
        if compact_ref:
            result_refs.append(compact_ref)
            if len(result_refs) >= MAX_BENCHMARK_RUN_LIST_ITEMS:
                break
    if result_refs:
        compact["result_refs"] = result_refs

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def _benchmark_learning_ledger_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_learning_ledger")
    if isinstance(nested, dict) and nested.get("schema_version") == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION:
        return nested
    if run.get("schema_version") == BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION:
        return run
    return None


def compact_benchmark_learning_ledger(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_learning_ledger_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_LEARNING_LEDGER_SCHEMA_VERSION}
    for field in ("task_id", "comparison_id", "learning_status", "claim_strength"):
        value = public_safe_compact_text(source.get(field), limit=180)
        if value:
            compact[field] = value

    for field in ("official_task_score_delta", "control_plane_score_delta"):
        delta = _compact_comparison_delta(source.get(field))
        if delta is not None:
            compact[field] = delta

    for field in ("repair_candidates", "claim_blockers"):
        values = public_safe_compact_list(source.get(field), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        if values:
            compact[field] = values

    lifecycle_gate = source.get("lifecycle_gate")
    if isinstance(lifecycle_gate, dict):
        compact_gate: dict[str, Any] = {}
        for field in ("budget_count_allowed", "blocked_reason"):
            value = lifecycle_gate.get(field)
            if isinstance(value, bool):
                compact_gate[field] = value
            elif field == "blocked_reason":
                text = public_safe_compact_text(value, limit=160)
                if text:
                    compact_gate[field] = text
        if compact_gate:
            compact["lifecycle_gate"] = compact_gate

    learning_gate = source.get("learning_quota_gate")
    if isinstance(learning_gate, dict):
        compact_learning_gate: dict[str, Any] = {}
        for field in ("actionable_learning_present", "spend_allowed", "blocked_reason"):
            value = learning_gate.get(field)
            if isinstance(value, bool):
                compact_learning_gate[field] = value
            elif field == "blocked_reason":
                text = public_safe_compact_text(value, limit=160)
                if text:
                    compact_learning_gate[field] = text
        reasons = public_safe_compact_list(
            learning_gate.get("actionable_reasons"),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
        )
        if reasons:
            compact_learning_gate["actionable_reasons"] = reasons
        if compact_learning_gate:
            compact["learning_quota_gate"] = compact_learning_gate

    overhead = source.get("overhead")
    if isinstance(overhead, dict):
        compact_overhead: dict[str, Any] = {}
        for field in ("cost_delta_usd", "wall_time_delta_seconds_or_ms"):
            delta = _compact_comparison_delta(overhead.get(field))
            if delta is not None:
                compact_overhead[field] = delta
        label = public_safe_compact_text(overhead.get("label"), limit=120)
        if label:
            compact_overhead["label"] = label
        if compact_overhead:
            compact["overhead"] = compact_overhead

    routing = source.get("routing")
    if isinstance(routing, dict):
        compact_routing: dict[str, Any] = {}
        for field in ("repeat_allowed", "new_candidate_allowed"):
            if isinstance(routing.get(field), bool):
                compact_routing[field] = routing[field]
        next_action = public_safe_compact_text(routing.get("next_allowed_action"), limit=180)
        if next_action:
            compact_routing["next_allowed_action"] = next_action
        if compact_routing:
            compact["routing"] = compact_routing

    read_boundary = source.get("read_boundary")
    if isinstance(read_boundary, dict):
        compact_boundary: dict[str, bool] = {}
        for field in ("compact_only", "raw_artifacts_read", "task_text_read", "local_paths_recorded"):
            if isinstance(read_boundary.get(field), bool):
                compact_boundary[field] = read_boundary[field]
        if compact_boundary:
            compact["read_boundary"] = compact_boundary

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def _comparison_delta_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str) and value.strip():
            return float(value)
    except ValueError:
        return None
    return None


def benchmark_comparison_decision_note(comparison: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(comparison, dict) or comparison.get("schema_version") != BENCHMARK_COMPARISON_SCHEMA_VERSION:
        return None

    official_delta = _comparison_delta_number(comparison.get("official_task_score_delta"))
    control_delta = _comparison_delta_number(comparison.get("control_plane_score_delta"))
    symbolic_official = (
        comparison.get("official_task_score_delta")
        if isinstance(comparison.get("official_task_score_delta"), str)
        else None
    )
    both_success = comparison.get("both_success") if isinstance(comparison.get("both_success"), bool) else None
    submit_ready = comparison.get("ready_to_submit_leaderboard")
    real_ready = comparison.get("ready_to_run_real_benchmark")
    decision_summary = comparison.get("decision") if isinstance(comparison.get("decision"), dict) else {}
    validation_enhancement = (
        decision_summary.get("validation_enhancement_point")
        if isinstance(decision_summary.get("validation_enhancement_point"), bool)
        else None
    )
    score_uplift = (
        decision_summary.get("score_uplift")
        if isinstance(decision_summary.get("score_uplift"), bool)
        else None
    )
    failure_labels = public_safe_compact_list(
        comparison.get("failure_attribution_labels"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    baseline_gate = (
        comparison.get("baseline_failure_gate")
        if isinstance(comparison.get("baseline_failure_gate"), dict)
        else {}
    )
    baseline_failed = (
        baseline_gate.get("baseline_failed")
        if isinstance(baseline_gate.get("baseline_failed"), bool)
        else None
    )
    control_plane_addressable = (
        baseline_gate.get("control_plane_addressable")
        if isinstance(baseline_gate.get("control_plane_addressable"), bool)
        else None
    )
    treatment_eligible = (
        baseline_gate.get("treatment_eligible")
        if isinstance(baseline_gate.get("treatment_eligible"), bool)
        else None
    )

    evidence_layer = "comparison_summary"
    decision = "repeat"
    minimum_next_evidence = "repeat the paired comparison or record a blocker"
    may_claim = ["compact paired comparison is available"]
    must_not_claim = ["official leaderboard uplift"]

    if symbolic_official == "not_applicable_readiness_only":
        evidence_layer = "readiness_only"
        decision = "continue"
        minimum_next_evidence = "record no-submit setup evidence before any real benchmark run"
        may_claim.append("readiness boundary is documented")
        must_not_claim.append("benchmark pass/fail or score uplift")
    elif official_delta is None and control_delta is None and baseline_gate:
        if baseline_failed is True and control_plane_addressable is True and treatment_eligible is True:
            evidence_layer = "baseline_failure_gate"
            decision = "continue"
            minimum_next_evidence = (
                public_safe_compact_text(baseline_gate.get("minimum_next_evidence"), limit=180)
                or "run the treatment arm only for this control-plane-addressable baseline failure"
            )
            may_claim.append("baseline failure is control-plane-addressable and treatment-eligible")
            must_not_claim.append("treatment uplift before paired treatment evidence exists")
        else:
            evidence_layer = "baseline_failure_gate_negative_selection"
            decision = "defer"
            minimum_next_evidence = (
                public_safe_compact_text(baseline_gate.get("negative_selection_reason"), limit=180)
                or "select a baseline failure with public-safe control-plane-addressable attribution"
            )
            may_claim.append("candidate was screened by baseline-failure gate")
            must_not_claim.append("treatment execution on non-addressable or unverified baseline failures")
    elif official_delta == 0 and control_delta is not None and control_delta > 0:
        evidence_layer = "control_plane_only"
        decision = "continue"
        minimum_next_evidence = "convert the control-plane delta into a report note or repeat on an official-runner-compatible output"
        may_claim.append("control-plane delta improved while official score delta stayed zero")
        must_not_claim.append("benchmark pass/fail improvement from control-plane-only evidence")
    elif official_delta is not None and official_delta > 0:
        evidence_layer = "official_score_candidate"
        decision = "defer" if submit_ready is not True else "broaden"
        minimum_next_evidence = "verify benchmark protocol, submit eligibility, and side-effect audit before claiming official uplift"
        may_claim.append("official score candidate exists")
        must_not_claim.append("official uplift before protocol and submit-eligibility verification")
    elif official_delta == 0 and validation_enhancement is True and score_uplift is False:
        evidence_layer = "validation_enhancement_no_score_uplift"
        decision = "continue"
        minimum_next_evidence = "repeat on a stronger target or harden the recorded failure-attribution/writeback path"
        may_claim.append("validation or failure-attribution evidence improved while official score delta stayed zero")
        must_not_claim.append("official score uplift")
    elif both_success is False:
        evidence_layer = "failure_analysis"
        decision = "repeat"
        minimum_next_evidence = "attribute the failed scenario before broadening"
        may_claim.append("paired comparison found a failure needing attribution")
    elif real_ready is False:
        evidence_layer = "boundary_guarded"
        decision = "defer"
        minimum_next_evidence = "resolve real-run readiness blockers before execution"
        may_claim.append("real benchmark execution remains gated")

    note: dict[str, Any] = {
        "schema_version": BENCHMARK_COMPARISON_DECISION_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_COMPARISON_SCHEMA_VERSION,
        "decision": decision,
        "evidence_layer": evidence_layer,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": "stop before real benchmark execution, model-backed simulator work, private traces, or leaderboard claims without explicit approval",
        "may_claim": may_claim[:MAX_BENCHMARK_RUN_LIST_ITEMS],
        "must_not_claim": must_not_claim[:MAX_BENCHMARK_RUN_LIST_ITEMS],
        "report_section_hint": ["claim_boundary", "next_decision"],
    }
    for field in ("task_id", "comparison_id"):
        value = public_safe_compact_text(comparison.get(field), limit=140)
        if value:
            note[field] = value
    if official_delta is not None:
        note["official_task_score_delta"] = official_delta
    elif symbolic_official:
        note["official_task_score_delta"] = symbolic_official
    if control_delta is not None:
        note["control_plane_score_delta"] = control_delta
    elif isinstance(comparison.get("control_plane_score_delta"), str):
        note["control_plane_score_delta"] = public_safe_compact_text(comparison.get("control_plane_score_delta"), limit=120)
    if failure_labels:
        note["failure_attribution_labels"] = failure_labels
    if baseline_gate:
        compact_note_gate: dict[str, Any] = {
            "schema_version": BENCHMARK_BASELINE_FAILURE_GATE_SCHEMA_VERSION,
        }
        for field in ("baseline_mode", "failure_phase", "failure_class", "negative_selection_reason"):
            value = public_safe_compact_text(baseline_gate.get(field), limit=140)
            if value:
                compact_note_gate[field] = value
        for field, value in (
            ("baseline_failed", baseline_failed),
            ("control_plane_addressable", control_plane_addressable),
            ("treatment_eligible", treatment_eligible),
        ):
            if isinstance(value, bool):
                compact_note_gate[field] = value
        note["baseline_failure_gate"] = compact_note_gate
    if validation_enhancement is not None:
        note["validation_enhancement_point"] = validation_enhancement
    if score_uplift is not None:
        note["score_uplift"] = score_uplift
    return note


def _benchmark_experiment_report_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("benchmark_experiment_report")
    if isinstance(nested, dict) and nested.get("schema_version") == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION:
        return nested
    legacy_nested = run.get("benchmark_report")
    if isinstance(legacy_nested, dict) and legacy_nested.get("schema_version") == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION:
        return legacy_nested
    if run.get("schema_version") == BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION:
        return run
    return None


def compact_benchmark_experiment_report(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_experiment_report_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION}

    identity = source.get("experiment_identity") if isinstance(source.get("experiment_identity"), dict) else {}
    compact_identity: dict[str, Any] = {}
    for field in (
        "report_id",
        "benchmark_id",
        "task_slice",
        "worker_surface",
        "harness_identity",
        "harness_policy_version",
        "trace_publicness",
    ):
        value = public_safe_compact_text(identity.get(field), limit=140)
        if value:
            compact_identity[field] = value
    if compact_identity:
        compact["experiment_identity"] = compact_identity

    official = source.get("official_score") if isinstance(source.get("official_score"), dict) else {}
    compact_official: dict[str, Any] = {}
    for field in ("kind", "task_id_or_split", "runner_source"):
        value = public_safe_compact_text(official.get(field), limit=140)
        if value:
            compact_official[field] = value
    compact_official.update(
        _compact_numeric_map(
            official,
            keys=("native_score", "wrapped_score", "delta", "repetitions"),
        )
    )
    for field in ("submit_eligible", "leaderboard_evidence"):
        if isinstance(official.get(field), bool):
            compact_official[field] = official.get(field)
    if compact_official:
        compact["official_score"] = compact_official
    attempt_accounting = _compact_benchmark_attempt_accounting(
        source.get("attempt_accounting")
    )
    if attempt_accounting:
        compact["attempt_accounting"] = attempt_accounting

    passive = (
        source.get("passive_control_plane_score")
        if isinstance(source.get("passive_control_plane_score"), dict)
        else {}
    )
    compact_passive = _compact_numeric_map(
        passive,
        keys=(
            "restartability",
            "stale_state_avoidance",
            "evidence_discipline",
            "writeback_quality",
            "failure_attribution",
        ),
    )
    for field in ("overhead_bounded", "regression_avoidance_passed"):
        if isinstance(passive.get(field), bool):
            compact_passive[field] = passive.get(field)
    passive_events = public_safe_compact_list(passive.get("source_events"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    if passive_events:
        compact_passive["source_events"] = passive_events
    if compact_passive:
        compact["passive_control_plane_score"] = compact_passive

    simulator = (
        source.get("operator_simulator_ablation")
        if isinstance(source.get("operator_simulator_ablation"), dict)
        else {}
    )
    compact_simulator: dict[str, Any] = {}
    for field in ("enabled", "leaderboard_evidence"):
        if isinstance(simulator.get(field), bool):
            compact_simulator[field] = simulator.get(field)
    compact_simulator.update(_compact_numeric_map(simulator, keys=("intervention_count",)))
    reason = public_safe_compact_text(simulator.get("reason"), limit=180)
    if reason:
        compact_simulator["reason"] = reason
    if compact_simulator:
        compact["operator_simulator_ablation"] = compact_simulator

    claim_boundary = source.get("claim_boundary") if isinstance(source.get("claim_boundary"), dict) else {}
    compact_boundary: dict[str, Any] = {}
    for field in ("may_claim", "must_not_claim"):
        values = public_safe_compact_list(claim_boundary.get(field), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
        if values:
            compact_boundary[field] = values
    for field in ("source_decision_note_schema", "source_evidence_layer"):
        value = public_safe_compact_text(claim_boundary.get(field), limit=120)
        if value:
            compact_boundary[field] = value
    if compact_boundary:
        compact["claim_boundary"] = compact_boundary

    negative = source.get("negative_results") if isinstance(source.get("negative_results"), dict) else {}
    compact_negative: dict[str, Any] = {}
    if isinstance(negative.get("null_official_delta"), bool):
        compact_negative["null_official_delta"] = negative.get("null_official_delta")
    existing_layers = public_safe_compact_list(negative.get("negative_evidence_layers"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    failed_hypotheses = negative.get("failed_hypotheses") if isinstance(negative.get("failed_hypotheses"), list) else []
    layers: list[str] = list(existing_layers)
    for item in failed_hypotheses:
        if not isinstance(item, dict):
            continue
        layer = public_safe_compact_text(item.get("evidence_layer"), limit=120)
        if layer and layer not in layers:
            layers.append(layer)
        if len(layers) >= MAX_BENCHMARK_RUN_LIST_ITEMS:
            break
    if failed_hypotheses:
        compact_negative["failed_hypothesis_count"] = len(failed_hypotheses)
    elif isinstance(negative.get("failed_hypothesis_count"), int):
        compact_negative["failed_hypothesis_count"] = negative.get("failed_hypothesis_count")
    if layers:
        compact_negative["negative_evidence_layers"] = layers
    overhead_regressions = negative.get("overhead_regressions")
    if isinstance(overhead_regressions, list):
        compact_negative["overhead_regression_count"] = len(overhead_regressions)
    elif isinstance(negative.get("overhead_regression_count"), int):
        compact_negative["overhead_regression_count"] = negative.get("overhead_regression_count")
    if compact_negative:
        compact["negative_results"] = compact_negative

    next_decision = source.get("next_decision") if isinstance(source.get("next_decision"), dict) else {}
    compact_next: dict[str, Any] = {}
    for field in (
        "decision",
        "minimum_next_evidence",
        "stop_condition",
        "source_decision_note_schema",
        "readiness_decision",
        "failure_decision",
    ):
        value = public_safe_compact_text(next_decision.get(field), limit=180)
        if value:
            compact_next[field] = value
    if compact_next:
        compact["next_decision"] = compact_next

    report_sections = (
        "experiment_identity",
        "official_score",
        "passive_control_plane_score",
        "operator_simulator_ablation",
        "cost_latency_overhead",
        "failure_taxonomy",
        "reproducibility_artifacts",
        "claim_boundary",
        "negative_results",
        "next_decision",
    )
    compact["section_count"] = sum(1 for section in report_sections if isinstance(source.get(section), dict))

    if set(compact.keys()) == {"schema_version", "section_count"}:
        return None
    return compact


def benchmark_experiment_report_readiness_note(report: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(report, dict) or report.get("schema_version") != BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION:
        return None

    identity = report.get("experiment_identity") if isinstance(report.get("experiment_identity"), dict) else {}
    official = report.get("official_score") if isinstance(report.get("official_score"), dict) else {}
    simulator = (
        report.get("operator_simulator_ablation")
        if isinstance(report.get("operator_simulator_ablation"), dict)
        else {}
    )
    boundary = report.get("claim_boundary") if isinstance(report.get("claim_boundary"), dict) else {}
    negative = report.get("negative_results") if isinstance(report.get("negative_results"), dict) else {}
    next_decision = report.get("next_decision") if isinstance(report.get("next_decision"), dict) else {}

    submit_eligible = official.get("submit_eligible") if isinstance(official.get("submit_eligible"), bool) else None
    leaderboard_evidence = (
        official.get("leaderboard_evidence") if isinstance(official.get("leaderboard_evidence"), bool) else None
    )
    simulator_enabled = simulator.get("enabled") if isinstance(simulator.get("enabled"), bool) else None
    null_official_delta = (
        negative.get("null_official_delta") if isinstance(negative.get("null_official_delta"), bool) else None
    )
    negative_layers = public_safe_compact_list(
        negative.get("negative_evidence_layers"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    must_not_claim = public_safe_compact_list(boundary.get("must_not_claim"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    may_claim = public_safe_compact_list(boundary.get("may_claim"), limit=MAX_BENCHMARK_RUN_LIST_ITEMS)

    readiness = "fixture_ready"
    next_run_authorization = "fixture_only"
    minimum_next_evidence = public_safe_compact_text(
        next_decision.get("minimum_next_evidence"),
        limit=180,
    ) or "compact report summary plus boundary-preserving replay evidence"
    if submit_eligible is True and leaderboard_evidence is True:
        readiness = "review_required"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = "operator review of leaderboard evidence before publication"
    elif submit_eligible is True:
        readiness = "review_required"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = "leaderboard evidence or an explicit downgrade to fixture-only"
    elif simulator_enabled is True:
        readiness = "assisted_mode_separate"
        next_run_authorization = "requires_operator_approval"
        minimum_next_evidence = "operator-simulator ablation evidence kept separate from passive report evidence"
    elif null_official_delta is True or negative_layers:
        readiness = "negative_or_control_plane_only"
        next_run_authorization = "fixture_only"

    stop_condition = public_safe_compact_text(next_decision.get("stop_condition"), limit=180) or (
        "stop before real benchmark execution, model-backed simulator work, private traces, "
        "or leaderboard claims without explicit approval"
    )
    report_decision = public_safe_compact_text(next_decision.get("decision"), limit=80) or "continue"

    note: dict[str, Any] = {
        "schema_version": BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_EXPERIMENT_REPORT_SCHEMA_VERSION,
        "readiness": readiness,
        "next_run_authorization": next_run_authorization,
        "report_decision": report_decision,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": stop_condition,
        "report_section_hint": ["claim_boundary", "negative_results", "next_decision"],
    }
    for field in ("report_id", "benchmark_id", "task_slice"):
        value = public_safe_compact_text(identity.get(field), limit=140)
        if value:
            note[field] = value
    if may_claim:
        note["may_claim"] = may_claim
    if must_not_claim:
        note["must_not_claim"] = must_not_claim
    if negative_layers:
        note["negative_evidence_layers"] = negative_layers
    for field, value in (
        ("submit_eligible", submit_eligible),
        ("leaderboard_evidence", leaderboard_evidence),
        ("simulator_enabled", simulator_enabled),
        ("null_official_delta", null_official_delta),
    ):
        if isinstance(value, bool):
            note[field] = value
    return note


def benchmark_experiment_report_replay_decision(readiness_note: dict[str, Any] | None) -> dict[str, Any] | None:
    if (
        not isinstance(readiness_note, dict)
        or readiness_note.get("schema_version") != BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION
    ):
        return None

    readiness = public_safe_compact_text(readiness_note.get("readiness"), limit=120) or "fixture_ready"
    authorization = public_safe_compact_text(readiness_note.get("next_run_authorization"), limit=120) or "fixture_only"
    report_decision = public_safe_compact_text(readiness_note.get("report_decision"), limit=80) or "continue"

    if authorization == "fixture_only":
        replay_decision = "continue_fixture_replay" if report_decision in {"continue", "broaden"} else "repeat_fixture_replay"
        next_run_mode = "fixture_replay"
    elif authorization == "requires_operator_approval":
        replay_decision = "operator_review_required"
        next_run_mode = "operator_review"
    else:
        replay_decision = "defer_until_authorized"
        next_run_mode = "deferred"

    if readiness == "assisted_mode_separate":
        replay_decision = "separate_assisted_mode_before_replay"
        next_run_mode = "operator_review"

    minimum_next_evidence = public_safe_compact_text(
        readiness_note.get("minimum_next_evidence"),
        limit=180,
    ) or "boundary-preserving replay decision evidence"
    stop_condition = public_safe_compact_text(readiness_note.get("stop_condition"), limit=180) or (
        "stop before real benchmark execution, model-backed simulator work, private traces, "
        "or leaderboard claims without explicit approval"
    )
    negative_layers = public_safe_compact_list(
        readiness_note.get("negative_evidence_layers"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
    must_not_claim = public_safe_compact_list(
        readiness_note.get("must_not_claim"),
        limit=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )

    decision: dict[str, Any] = {
        "schema_version": BENCHMARK_EXPERIMENT_REPORT_REPLAY_DECISION_SCHEMA_VERSION,
        "source_schema_version": BENCHMARK_EXPERIMENT_REPORT_READINESS_SCHEMA_VERSION,
        "readiness": readiness,
        "authorization": authorization,
        "replay_decision": replay_decision,
        "next_run_mode": next_run_mode,
        "minimum_next_evidence": minimum_next_evidence,
        "stop_condition": stop_condition,
        "surface": "status_review_packet_only",
    }
    for field in ("report_id", "benchmark_id", "task_slice"):
        value = public_safe_compact_text(readiness_note.get(field), limit=140)
        if value:
            decision[field] = value
    if negative_layers:
        decision["negative_evidence_layers"] = negative_layers
    if must_not_claim:
        decision["must_not_claim"] = must_not_claim
    return decision


def _active_user_assisted_pilot_source(run: dict[str, Any]) -> dict[str, Any] | None:
    nested = run.get("active_user_assisted_pilot")
    if isinstance(nested, dict) and nested.get("schema_version") == ACTIVE_USER_ASSISTED_PILOT_SCHEMA_VERSION:
        return nested
    if run.get("schema_version") == ACTIVE_USER_ASSISTED_PILOT_SCHEMA_VERSION:
        return run
    return None


def compact_active_user_assisted_pilot(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _active_user_assisted_pilot_source(run)
    if not source:
        return None

    compact: dict[str, Any] = {"schema_version": ACTIVE_USER_ASSISTED_PILOT_SCHEMA_VERSION}
    for field in ("pilot_id", "benchmark_id", "task_id"):
        value = public_safe_compact_text(source.get(field), limit=140)
        if value:
            compact[field] = value

    trigger = source.get("trigger") if isinstance(source.get("trigger"), dict) else {}
    compact_trigger: dict[str, Any] = {}
    for field in ("kind", "assisted_score_kind"):
        value = public_safe_compact_text(trigger.get(field), limit=120)
        if value:
            compact_trigger[field] = value
    if isinstance(trigger.get("both_autonomous_modes_failed"), bool):
        compact_trigger["both_autonomous_modes_failed"] = trigger.get("both_autonomous_modes_failed")
    failed_modes = trigger.get("failed_autonomous_modes") if isinstance(trigger.get("failed_autonomous_modes"), list) else []
    if failed_modes:
        compact_trigger["failed_autonomous_mode_count"] = len(failed_modes)
        mode_names = []
        for item in failed_modes:
            if isinstance(item, str):
                mode = public_safe_compact_text(item, limit=100)
            elif isinstance(item, dict):
                mode = public_safe_compact_text(item.get("mode"), limit=100)
            else:
                continue
            if mode:
                mode_names.append(mode)
            if len(mode_names) >= MAX_BENCHMARK_RUN_LIST_ITEMS:
                break
        if mode_names:
            compact_trigger["failed_autonomous_modes"] = mode_names
    if compact_trigger:
        compact["trigger"] = compact_trigger

    active = source.get("active_injection_contract") if isinstance(source.get("active_injection_contract"), dict) else {}
    compact_active: dict[str, Any] = {}
    for field in ("schema_version", "simulator_setting"):
        value = public_safe_compact_text(active.get(field), limit=120)
        if value:
            compact_active[field] = value
    for field in ("proactive_intervention_allowed", "directive_feedback_allowed", "artificial_mildness_required"):
        if isinstance(active.get(field), bool):
            compact_active[field] = active.get(field)
    if compact_active:
        compact["active_injection_contract"] = compact_active

    budget = source.get("frequency_budget") if isinstance(source.get("frequency_budget"), dict) else {}
    compact_budget = _compact_numeric_map(
        budget,
        keys=(
            "max_interventions",
            "max_proactive_interventions",
            "min_worker_events_between_proactive",
            "max_chars_per_intervention",
        ),
    )
    if compact_budget:
        compact["frequency_budget"] = compact_budget

    visibility = source.get("visibility_policy") if isinstance(source.get("visibility_policy"), dict) else {}
    compact_visibility: dict[str, Any] = {}
    policy_id = public_safe_compact_text(visibility.get("policy_id"), limit=140)
    if policy_id:
        compact_visibility["policy_id"] = policy_id
    visibility_allowed_source = visibility.get("allowed")
    if visibility_allowed_source is None:
        visibility_allowed_source = visibility.get("allowed_visibility")
    allowed_visibility = public_safe_compact_list(visibility_allowed_source, limit=MAX_BENCHMARK_RUN_LIST_ITEMS)
    if allowed_visibility:
        compact_visibility["allowed_visibility"] = allowed_visibility
    if compact_visibility:
        compact["visibility_policy"] = compact_visibility

    operator_run = source.get("operator_simulator_run") if isinstance(source.get("operator_simulator_run"), dict) else {}
    compact_operator: dict[str, Any] = {}
    if operator_run.get("schema_version") == OPERATOR_SIMULATOR_RUN_SCHEMA_VERSION:
        compact_operator["schema_version"] = OPERATOR_SIMULATOR_RUN_SCHEMA_VERSION
    simulator_identity = (
        operator_run.get("simulator_identity")
        if isinstance(operator_run.get("simulator_identity"), dict)
        else operator_run
    )
    for field in ("setting", "model_family", "seed"):
        value = public_safe_compact_text(simulator_identity.get(field), limit=140)
        if value:
            compact_operator[field] = value
    interventions = operator_run.get("interventions") if isinstance(operator_run.get("interventions"), list) else []
    if interventions:
        compact_operator["intervention_count"] = len(interventions)
        compact_operator["proactive_intervention_count"] = sum(
            1 for item in interventions if isinstance(item, dict) and item.get("proactive") is True
        )
        compact_operator["no_oracle_audit_passed"] = all(
            isinstance(item, dict)
            and isinstance(item.get("no_oracle_audit"), dict)
            and not any(bool(value) for value in item["no_oracle_audit"].values())
            for item in interventions
        )
    else:
        for field in ("intervention_count", "proactive_intervention_count"):
            if isinstance(operator_run.get(field), int):
                compact_operator[field] = operator_run.get(field)
        if isinstance(operator_run.get("no_oracle_audit_passed"), bool):
            compact_operator["no_oracle_audit_passed"] = operator_run.get("no_oracle_audit_passed")
    official = (
        operator_run.get("official_task_score_reference")
        if isinstance(operator_run.get("official_task_score_reference"), dict)
        else {}
    )
    official_kind = public_safe_compact_text(official.get("kind"), limit=100)
    if not official_kind:
        official_kind = public_safe_compact_text(operator_run.get("official_task_score_kind"), limit=100)
    if official_kind:
        compact_operator["official_task_score_kind"] = official_kind
    if isinstance(operator_run.get("simulator_induced_error_count"), int):
        compact_operator["simulator_induced_error_count"] = operator_run.get("simulator_induced_error_count")
    frequency_audit = (
        operator_run.get("frequency_budget_audit")
        if isinstance(operator_run.get("frequency_budget_audit"), dict)
        else {}
    )
    if isinstance(frequency_audit.get("min_worker_events_between_proactive_satisfied"), bool):
        compact_operator["frequency_budget_satisfied"] = frequency_audit.get(
            "min_worker_events_between_proactive_satisfied"
        )
    elif isinstance(operator_run.get("frequency_budget_satisfied"), bool):
        compact_operator["frequency_budget_satisfied"] = operator_run.get("frequency_budget_satisfied")
    side_effect_audit = (
        operator_run.get("side_effect_audit")
        if isinstance(operator_run.get("side_effect_audit"), dict)
        else {}
    )
    if side_effect_audit:
        compact_operator["side_effect_audit_passed"] = not any(bool(value) for value in side_effect_audit.values())
    elif isinstance(operator_run.get("side_effect_audit_passed"), bool):
        compact_operator["side_effect_audit_passed"] = operator_run.get("side_effect_audit_passed")
    if compact_operator:
        compact["operator_simulator_run"] = compact_operator

    claim_boundary = source.get("claim_boundary") if isinstance(source.get("claim_boundary"), dict) else {}
    compact_boundary: dict[str, Any] = {}
    for field in ("official_score_claim_allowed", "assisted_collaboration_claim_allowed", "leaderboard_claim_allowed"):
        if isinstance(claim_boundary.get(field), bool):
            compact_boundary[field] = claim_boundary.get(field)
    if compact_boundary:
        compact["claim_boundary"] = compact_boundary

    next_decision = source.get("next_run_decision") if isinstance(source.get("next_run_decision"), dict) else {}
    if not next_decision and isinstance(operator_run.get("next_run_decision"), dict):
        next_decision = operator_run.get("next_run_decision")  # type: ignore[assignment]
    compact_next: dict[str, Any] = {}
    for field in ("decision", "minimum_next_evidence"):
        value = public_safe_compact_text(next_decision.get(field), limit=180)
        if value:
            compact_next[field] = value
    for field in ("requires_real_runner_approval", "keep_official_scores_separate"):
        if isinstance(next_decision.get(field), bool):
            compact_next[field] = next_decision.get(field)
    if compact_next:
        compact["next_run_decision"] = compact_next

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


def parse_state_frontmatter(state_text: str) -> dict[str, str]:
    if not state_text.startswith("---"):
        return {}
    parts = state_text.split("---", 2)
    if len(parts) < 3:
        return {}
    result: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def todo_role_for_heading(heading: str) -> str | None:
    normalized = heading.strip().lower()
    if any(marker in normalized for marker in TODO_ARCHIVE_HEADER_MARKERS):
        return None
    if any(marker in normalized for marker in USER_TODO_HEADER_MARKERS):
        return "user"
    if any(marker in normalized for marker in AGENT_TODO_HEADER_MARKERS):
        return "agent"
    return None


def todo_priority_parts(text: str) -> tuple[str | None, str]:
    return projection_todo_priority_parts(text)


def structured_todo_item(
    item: dict[str, Any],
    *,
    role: str | None,
    source_section: str | None,
    archive_state: str = "active",
) -> dict[str, Any]:
    text = normalize_todo_text(str(item.get("text") or ""))
    priority, title = todo_priority_parts(text)
    index = item.get("index")
    explicit_status = normalize_todo_status(item.get("status"))
    status = explicit_status or ("done" if item.get("done") else "open")
    done = todo_done_for_status(status) if explicit_status else bool(item.get("done"))
    todo_id = item.get("todo_id") or build_todo_id(
        role=role,
        source_section=source_section,
        index=index,
        text=text,
    )
    normalized = dict(item)
    normalized.update(
        {
            "schema_version": TODO_ITEM_SCHEMA_VERSION,
            "todo_id": todo_id,
            "role": role,
            "status": status,
            "done": done,
            "archive_state": archive_state,
            "source_section": source_section,
            "text": text,
            "task_class": normalize_todo_task_class(
                item.get("task_class"),
                text=text,
                action_kind=item.get("action_kind"),
            ),
        }
    )
    action_kind = normalize_todo_action_kind(item.get("action_kind"))
    if action_kind:
        normalized["action_kind"] = action_kind
    required_write_scopes = normalize_required_write_scopes(item.get("required_write_scopes"))
    if required_write_scopes:
        normalized["required_write_scopes"] = required_write_scopes
    required_capabilities = normalize_required_capabilities(item.get("required_capabilities"))
    if required_capabilities:
        normalized["required_capabilities"] = required_capabilities
    target_capabilities = normalize_target_capabilities(item.get("target_capabilities"))
    if target_capabilities:
        normalized["target_capabilities"] = target_capabilities
    decision_scope = normalize_todo_decision_scope(item.get("decision_scope"))
    if decision_scope:
        normalized["decision_scope"] = decision_scope
    required_decision_scopes = normalize_todo_required_decision_scopes(
        item.get("required_decision_scopes")
    )
    if required_decision_scopes:
        normalized["required_decision_scopes"] = required_decision_scopes
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    if claimed_by:
        normalized["claimed_by"] = claimed_by
    blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
    if blocks_agent:
        normalized["blocks_agent"] = blocks_agent
    global_gate = normalize_todo_global_gate(item.get("global_gate"))
    if global_gate is not None:
        normalized["global_gate"] = global_gate
    unblocks_todo_id = normalize_todo_id(item.get("unblocks_todo_id"))
    if unblocks_todo_id:
        normalized["unblocks_todo_id"] = unblocks_todo_id
    resume_when = normalize_todo_resume_when(item.get("resume_when"))
    if resume_when:
        normalized["resume_when"] = resume_when
    no_followup = normalize_todo_no_followup(item.get("no_followup"))
    if no_followup is not None:
        normalized["no_followup"] = no_followup
    if priority:
        normalized["priority"] = priority
        normalized["title"] = normalize_todo_text(title)
    return normalized


def compact_todo_item(item: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "done": bool(item.get("done")),
        "text": item.get("text"),
    }
    for key in (
        "schema_version",
        "todo_id",
        "role",
        "status",
        "priority",
        "title",
        "archive_state",
        "source_section",
        "task_class",
        "action_kind",
        "required_write_scopes",
        "required_capabilities",
        "target_capabilities",
        "decision_scope",
        "required_decision_scopes",
        "claimed_by",
        "blocks_agent",
        "global_gate",
        "unblocks_todo_id",
        "resume_when",
        "resume_condition",
        "resume_ready",
        "no_followup",
        "target_key",
        "cadence",
        "next_due_at",
        "expires_at",
        "last_checked_at",
        "result_hash",
        "consecutive_no_change",
        "material_change",
        "max_no_change_before_replan",
        "note",
        "evidence",
        "reason",
        "completed_at",
        "updated_at",
        "superseded_by",
    ):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    return compact


def compact_active_next_action_todo_item(item: dict[str, Any]) -> dict[str, Any]:
    compact = compact_todo_item(item)
    for key in (
        "note",
        "evidence",
        "reason",
        "completed_at",
        "updated_at",
        "superseded_by",
    ):
        compact.pop(key, None)
    return compact


def todo_item_task_class(item: dict[str, Any]) -> str:
    return projection_todo_item_task_class(item, task_text_keys=("text",))


def todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    return projection_todo_item_is_actionable_open(item)


def todo_item_next_due_at(item: dict[str, Any]) -> datetime | None:
    return projection_todo_item_next_due_at(item)


def todo_item_expires_at(item: dict[str, Any]) -> datetime | None:
    return projection_todo_item_expires_at(item)


def todo_item_is_expired_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    return projection_todo_item_is_expired_monitor(item, now=now)


def todo_item_is_due_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    return projection_todo_item_is_due_monitor(item, now=now, task_text_keys=("text",))


def todo_item_missing_monitor_schedule(
    item: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    return projection_todo_item_missing_monitor_schedule(
        item,
        now=now,
        task_text_keys=("text",),
    )


def todo_priority_rank(priority: Any) -> int:
    return projection_todo_priority_rank(priority)


def todo_projection_sort_key(item: dict[str, Any]) -> tuple[int, int]:
    return projection_todo_projection_sort_key(item, text_mode="prefix")


def claimed_visibility_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    return projection_todo_claimed_visibility_items(items, limit=limit)


def todo_item_is_deferred(item: dict[str, Any]) -> bool:
    return projection_todo_item_is_deferred(item)


def normalized_pr_ref_parts(value: Any) -> dict[str, Any] | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    pull_url_match = GITHUB_PULL_URL_PATTERN.match(candidate)
    if pull_url_match:
        return {
            "repo": pull_url_match.group("repo"),
            "number": int(pull_url_match.group("number")),
            "normalized": f"{pull_url_match.group('repo')}#{pull_url_match.group('number')}",
        }
    match = PR_REF_PATTERN.match(candidate)
    if not match:
        return None
    repo = match.group("repo")
    number = int(match.group("number"))
    normalized = f"{repo}#{number}" if repo else f"#{number}"
    return {"repo": repo, "number": number, "normalized": normalized}


def rollout_event_pr_refs(event: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    code_refs = event.get("code_refs") if isinstance(event.get("code_refs"), dict) else {}
    for value in (code_refs.get("pr_ref"), event.get("pr_ref")):
        parsed = normalized_pr_ref_parts(value)
        if parsed:
            refs.append(parsed)
    source_refs = event.get("source_refs")
    if isinstance(source_refs, list):
        for source_ref in source_refs:
            if not isinstance(source_ref, dict):
                continue
            if str(source_ref.get("kind") or "").strip().lower() not in {
                "pull_request",
                "pr",
            }:
                continue
            parsed = normalized_pr_ref_parts(source_ref.get("ref"))
            if parsed:
                refs.append(parsed)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str | None, int]] = set()
    for ref in refs:
        key = (ref.get("repo"), int(ref.get("number") or 0))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique


def pr_merged_condition(target: str, rollout_events: list[dict[str, Any]]) -> dict[str, Any]:
    condition: dict[str, Any] = {
        "pr_number": None,
        "pr_repo": None,
        "source": "rollout_event_log",
    }
    target_ref = normalized_pr_ref_parts(target)
    if not target_ref:
        condition["invalid_target"] = True
        return condition
    condition["pr_number"] = target_ref["number"]
    if target_ref.get("repo"):
        condition["pr_repo"] = target_ref["repo"]
    for event in rollout_events:
        if not isinstance(event, dict):
            continue
        if str(event.get("event_kind") or "").strip().lower() not in PR_MERGED_EVENT_KINDS:
            continue
        for event_ref in rollout_event_pr_refs(event):
            if int(event_ref.get("number") or 0) != int(target_ref["number"]):
                continue
            if target_ref.get("repo") and event_ref.get("repo") != target_ref.get("repo"):
                continue
            condition.update(
                {
                    "satisfied": True,
                    "matched_event_id": event.get("event_id"),
                    "matched_event_kind": event.get("event_kind"),
                    "matched_pr_ref": event_ref.get("normalized"),
                    "matched_event_at": event.get("recorded_at"),
                }
            )
            return condition
    return condition


def apply_resume_conditions(
    items: list[dict[str, Any]],
    *,
    resume_source_items: list[dict[str, Any]] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
) -> None:
    by_id: dict[str, dict[str, Any]] = {}
    for source_item in [*(resume_source_items or []), *items]:
        todo_id = normalize_todo_id(source_item.get("todo_id"))
        if todo_id:
            by_id[todo_id] = source_item
    for item in items:
        resume_when = normalize_todo_resume_when(item.get("resume_when"))
        if not resume_when:
            continue
        condition: dict[str, Any] = {
            "schema_version": "todo_resume_condition_v0",
            "resume_when": resume_when,
            "satisfied": False,
        }
        kind, separator, target = resume_when.partition(":")
        condition["kind"] = kind
        if separator:
            condition["target"] = target
        if kind == TODO_RESUME_KIND_TODO_DONE and target:
            target_item = by_id.get(target)
            condition["target_todo_id"] = target
            condition["target_status"] = (
                normalize_todo_status(target_item.get("status"))
                if isinstance(target_item, dict)
                else None
            )
            if isinstance(target_item, dict):
                condition["target_archive_state"] = target_item.get("archive_state")
                condition["target_source_section"] = target_item.get("source_section")
                condition["target_task_class"] = todo_item_task_class(target_item)
                target_claimed_by = normalize_todo_claimed_by(target_item.get("claimed_by"))
                if target_claimed_by:
                    condition["target_claimed_by"] = target_claimed_by
            condition["satisfied"] = condition["target_status"] == "done"
        elif kind == TODO_RESUME_KIND_PR_MERGED and target:
            condition.update(pr_merged_condition(target, rollout_events or []))
        else:
            condition["unsupported"] = True
        item["resume_condition"] = condition
        item["resume_ready"] = bool(condition.get("satisfied"))


def active_next_action_todo_ids(value: Any) -> set[str]:
    todo_ids: set[str] = set()
    for match in re.findall(r"\btodo_[A-Za-z0-9_-]+\b", str(value or "")):
        todo_id = normalize_todo_id(match)
        if todo_id:
            todo_ids.add(todo_id)
    return todo_ids


def compact_todo_group(
    items: list[dict[str, Any]],
    *,
    source_section: str | None,
    role: str | None = None,
    preferred_todo_ids: set[str] | None = None,
    resume_source_items: list[dict[str, Any]] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any] | None:
    if not items:
        return None
    items = [
        structured_todo_item(item, role=role, source_section=source_section)
        if isinstance(item, dict)
        else item
        for item in items
    ]
    structured_resume_source_items = [
        structured_todo_item(
            item,
            role=item.get("role") if isinstance(item.get("role"), str) else None,
            source_section=(
                item.get("source_section")
                if isinstance(item.get("source_section"), str)
                else source_section
            ),
            archive_state=(
                str(item.get("archive_state"))
                if item.get("archive_state") is not None
                else "active"
            ),
        )
        for item in (resume_source_items or [])
        if isinstance(item, dict)
    ]
    apply_resume_conditions(
        items,
        resume_source_items=structured_resume_source_items,
        rollout_events=rollout_events,
    )
    open_items = [item for item in items if not item.get("done")]
    terminal_items = [item for item in items if item.get("done")]
    deferred_items = [item for item in terminal_items if todo_item_is_deferred(item)]
    done_items = [item for item in terminal_items if not todo_item_is_deferred(item)]
    projected_open_items = sorted(open_items, key=todo_projection_sort_key)
    projected_deferred_items = sorted(deferred_items, key=todo_projection_sort_key)
    budgeted_items = [
        *projected_open_items,
        *projected_deferred_items,
        *done_items,
    ]
    claimed_open_items = [item for item in projected_open_items if item.get("claimed_by")]
    unclaimed_open_items = [item for item in projected_open_items if not item.get("claimed_by")]
    executable_items = [
        item
        for item in projected_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    resume_blocked_items = [
        item
        for item in projected_open_items
        if normalize_todo_resume_when(item.get("resume_when"))
        if item.get("resume_ready") is False
    ]
    monitor_items = [
        item
        for item in projected_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_due_items = [
        item
        for item in monitor_items
        if todo_item_is_due_monitor(item)
    ]
    monitor_schedule_gap_items = [
        item
        for item in monitor_items
        if todo_item_missing_monitor_schedule(item)
    ]
    claimed_advancement_items = [
        item
        for item in claimed_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    claimed_monitor_items = [
        item
        for item in claimed_open_items
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    preferred_ids = {
        todo_id
        for todo_id in (preferred_todo_ids or set())
        if normalize_todo_id(todo_id)
    }
    active_next_action_items = [
        item
        for item in projected_open_items
        if normalize_todo_id(item.get("todo_id")) in preferred_ids
    ]
    active_next_action_executable_items = [
        item
        for item in executable_items
        if normalize_todo_id(item.get("todo_id")) in preferred_ids
    ]
    summary = {
        "schema_version": "todo_summary_v0",
        "source_section": source_section,
        "total_count": len(items),
        "open_count": len(open_items),
        "done_count": len(terminal_items),
        "deferred_count": len(deferred_items),
        "first_open_items": [
            compact_todo_item(item) for item in projected_open_items[:3]
        ],
        "first_executable_items": [
            compact_todo_item(item) for item in executable_items[:3]
        ],
        "monitor_open_items": [
            compact_todo_item(item) for item in monitor_items
        ],
        "monitor_due_count": len(monitor_due_items),
        "monitor_due_items": [
            compact_todo_item(item)
            for item in monitor_due_items[:MAX_MONITOR_DUE_ITEMS]
        ],
        "monitor_schedule_gap_count": len(monitor_schedule_gap_items),
        "monitor_schedule_gap_items": [
            compact_todo_item(item)
            for item in monitor_schedule_gap_items[:MAX_MONITOR_DUE_ITEMS]
        ],
        "unclaimed_priority_open_items": [
            compact_todo_item(item)
            for item in unclaimed_open_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "claimed_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                claimed_open_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "claimed_advancement_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                claimed_advancement_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "claimed_monitor_open_items": [
            compact_todo_item(item)
            for item in claimed_visibility_items(
                claimed_monitor_items,
                limit=MAX_TODO_VISIBILITY_LANE_ITEMS,
            )
        ],
        "backlog_items": [
            compact_todo_item(item)
            for item in projected_open_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "executable_backlog_items": [
            compact_todo_item(item)
            for item in executable_items[:MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS]
        ],
        "deferred_items": [
            compact_todo_item(item)
            for item in projected_deferred_items[:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
        ],
        "deferred_resume_candidates": [
            compact_todo_item(item)
            for item in projected_deferred_items
            if item.get("resume_ready") is True
        ][:MAX_DEFERRED_TODO_VISIBILITY_ITEMS],
        "items": budgeted_items if item_limit is None else budgeted_items[:item_limit],
    }
    if resume_blocked_items:
        summary["resume_blocked_count"] = len(resume_blocked_items)
        summary["resume_blocked_items"] = [
            compact_todo_item(item)
            for item in resume_blocked_items[:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
        ]
    handoff_gates = build_todo_handoff_gate_states(items)
    if handoff_gates:
        summary["handoff_gates"] = handoff_gates
    if active_next_action_items:
        summary["active_next_action_items"] = [
            compact_active_next_action_todo_item(item)
            for item in active_next_action_items
        ]
    if active_next_action_executable_items:
        summary["active_next_action_executable_items"] = [
            compact_active_next_action_todo_item(item)
            for item in active_next_action_executable_items
        ]
    if claimed_open_items:
        summary["claimed_open_count"] = len(claimed_open_items)
        summary["unclaimed_open_count"] = len(open_items) - len(claimed_open_items)
        summary["claimed_advancement_open_count"] = len(claimed_advancement_items)
        summary["claimed_monitor_open_count"] = len(claimed_monitor_items)
    return summary


def attach_monitor_writeback_contract(
    fields: dict[str, Any],
    *,
    supported: bool,
    source: str,
) -> None:
    if supported:
        return
    contract = {
        "schema_version": MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION,
        "supported": False,
        "source": source,
    }
    for key in ("user_todos", "agent_todos"):
        summary = fields.get(key)
        if isinstance(summary, dict):
            summary["monitor_writeback"] = dict(contract)


def redacted_status_todo_fields(fields: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(fields)
    for key in ("user_todos", "agent_todos"):
        group = redacted.get(key)
        if not isinstance(group, dict):
            continue
        group_copy = dict(group)
        items: list[Any] = []
        for item in group_copy.get("items") or []:
            if not isinstance(item, dict):
                items.append(item)
                continue
            item_copy = dict(item)
            materials = item_copy.get("review_materials")
            if isinstance(materials, list):
                redacted_materials = []
                for material in materials:
                    if not isinstance(material, dict):
                        redacted_materials.append(material)
                        continue
                    material_copy = dict(material)
                    material_copy.pop("resolved_path", None)
                    redacted_materials.append(material_copy)
                item_copy["review_materials"] = redacted_materials
            items.append(item_copy)
        group_copy["items"] = items
        redacted[key] = group_copy
    return redacted


def parse_active_state_todos(
    state_text: str,
    *,
    goal: dict[str, Any] | None = None,
    state_path: Path | None = None,
    preferred_todo_ids: set[str] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any]:
    role: str | None = None
    source_sections: dict[str, str | None] = {"user": None, "agent": None}
    items: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    archive_items: list[dict[str, Any]] = []
    archive_mode = False
    archive_source_section: str | None = None
    current_todo: dict[str, Any] | None = None

    for line in state_text.splitlines():
        if line.startswith("## "):
            heading = line.lstrip("#").strip()
            normalized_heading = heading.strip().lower()
            archive_mode = any(
                marker in normalized_heading for marker in TODO_ARCHIVE_HEADER_MARKERS
            )
            archive_source_section = heading if archive_mode else None
            role = todo_role_for_heading(heading)
            current_todo = None
            if role and source_sections[role] is None:
                source_sections[role] = heading
            continue
        if role is None and not archive_mode:
            continue
        match = TODO_TASK_PATTERN.match(line)
        if match:
            marker, text = match.groups()
            status = todo_status_from_marker(marker)
            target_items = archive_items if archive_mode else items[str(role)]
            todo: dict[str, Any] = {
                "index": len(target_items) + 1,
                "done": todo_done_for_status(status),
                "status": status,
                "text": normalize_todo_text(text),
            }
            if archive_mode:
                todo["archive_state"] = "archive"
                todo["source_section"] = archive_source_section
            else:
                todo["archive_state"] = "active"
                todo["source_section"] = source_sections[str(role)]
                todo["role"] = role
            if goal is not None:
                materials = extract_review_materials(text, goal=goal, state_path=state_path)
                if materials:
                    todo["review_materials"] = materials
            target_items.append(todo)
            current_todo = todo
            continue
        if current_todo is None or not line.startswith((" ", "\t")):
            continue
        metadata = parse_todo_metadata_line(line)
        if metadata:
            current_todo.update(metadata)
            continue
        continuation = line.strip()
        if continuation:
            current_todo["text"] = normalize_todo_text(f"{current_todo.get('text', '')} {continuation}")

    result: dict[str, Any] = {}
    archived_resume_source_items = [
        item for item in archive_items if normalize_todo_id(item.get("todo_id"))
    ]
    resume_source_items = [*items["user"], *items["agent"], *archived_resume_source_items]
    user = compact_todo_group(
        items["user"],
        source_section=source_sections["user"],
        role="user",
        preferred_todo_ids=preferred_todo_ids,
        resume_source_items=resume_source_items,
        rollout_events=rollout_events,
        item_limit=item_limit,
    )
    agent = compact_todo_group(
        items["agent"],
        source_section=source_sections["agent"],
        role="agent",
        preferred_todo_ids=preferred_todo_ids,
        resume_source_items=resume_source_items,
        rollout_events=rollout_events,
        item_limit=item_limit,
    )
    if user:
        result["user_todos"] = user
    if agent:
        result["agent_todos"] = agent
    return result


def state_event_log_candidates(goal: dict[str, Any], *, state_path: Path) -> list[Path]:
    candidates: list[Path] = []
    for key in ("state_event_log", "state_events_file", "event_log"):
        resolved = resolve_goal_local_path(goal.get(key), goal, fallback_base=state_path.parent)
        if resolved is not None:
            candidates.append(resolved)
    candidates.append(state_path.with_name(STATE_EVENT_LOG_BASENAME))

    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def active_state_event_projection_fields(
    goal: dict[str, Any],
    *,
    state_path: Path,
    preferred_todo_ids: set[str] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any]:
    goal_id = str(goal.get("id") or "").strip()
    for event_log_path in state_event_log_candidates(goal, state_path=state_path):
        if not event_log_path.exists():
            continue
        try:
            events = AppendOnlyStateEventStore(event_log_path).load()
            if not events:
                continue
            projection = build_state_projection(events, goal_id=goal_id or None)
            projection_markdown = render_active_state_sections(projection)
            fields = parse_active_state_todos(
                projection_markdown,
                goal=goal,
                state_path=state_path,
                preferred_todo_ids=preferred_todo_ids,
                rollout_events=rollout_events,
                item_limit=item_limit,
            )
        except (OSError, StateEventError) as exc:
            return {
                "state_event_projection_warning": {
                    "schema_version": "event_sourced_state_read_warning_v0",
                    "source": "event_log",
                    "event_log": event_log_path.name,
                    "fallback": "markdown_active_state",
                    "reason": type(exc).__name__,
                }
            }
        if fields:
            fields["state_event_projection"] = {
                "schema_version": "event_sourced_state_status_projection_v0",
                "source": "event_log",
                "event_log": event_log_path.name,
                "source_event_count": projection.get("source_event_count"),
                "source_checksum": projection.get("source_checksum"),
                "last_event_id": projection.get("last_event_id"),
                "last_append_sequence": projection.get("last_append_sequence"),
                "projection_version": projection.get("projection_version"),
            }
            return fields
    return {}


def active_state_sections(state_text: str, headings: tuple[str, ...]) -> dict[str, list[str]]:
    wanted = {heading.lower(): heading for heading in headings}
    current: str | None = None
    sections: dict[str, list[str]] = {heading: [] for heading in headings}
    for line in state_text.splitlines():
        match = SECTION_HEADING_PATTERN.match(line)
        if match:
            normalized = match.group(1).strip().lower()
            current = wanted.get(normalized)
            continue
        if current:
            sections[current].append(line)
    return sections


def issue_meta_surface_blocks(lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("- ", "* ")):
            if current:
                blocks.append(" ".join(current))
            current = [stripped[2:].strip()]
            continue
        if current and line.startswith((" ", "\t")):
            current.append(stripped)
    if current:
        blocks.append(" ".join(current))
    return blocks


def issue_meta_public_value(value: Any, *, limit: int = 120) -> str | None:
    text = public_safe_compact_text(value, limit=limit)
    if not text:
        return None
    if "<" in text or ">" in text:
        return None
    return text.strip("\"'")


def issue_meta_list(value: Any, *, limit: int = MAX_ISSUE_META_LABELS) -> list[str]:
    if value is None:
        return []
    raw_values = re.split(r"[,;|]", str(value or ""))
    items: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        item = issue_meta_public_value(raw, limit=80)
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def parse_issue_meta_surface_block(block: str, *, index: int) -> dict[str, Any] | None:
    fields: dict[str, str] = {}
    for match in ISSUE_META_SURFACE_FIELD_PATTERN.finditer(block):
        key = str(match.group("key") or "").strip().lower().replace("-", "_")
        value = str(match.group("value") or "").strip().strip("\"'")
        if key and value:
            fields[key] = value
    if not fields:
        return None

    item: dict[str, Any] = {
        "schema_version": ISSUE_META_SURFACE_ITEM_SCHEMA_VERSION,
        "index": index,
    }
    alias_map = {
        "anchor_id": ("anchor_id", "id"),
        "repo_handle": ("repo_handle", "repo"),
        "issue_handle": ("issue_handle", "issue", "issue_or_pr", "issue_or_pr_handle"),
        "owner_route": ("owner_route", "owner"),
        "related_code_hint": ("related_code_hint", "related_code", "code"),
        "validation_surface": ("validation_surface", "validation"),
        "promotion_target": ("promotion_target", "promotion"),
        "status": ("status",),
        "freshness": ("freshness",),
    }
    for output_key, aliases in alias_map.items():
        raw_value = next((fields[alias] for alias in aliases if alias in fields), None)
        value = issue_meta_public_value(raw_value)
        if value:
            item[output_key] = value
    labels = issue_meta_list(fields.get("labels") or fields.get("label"))
    if labels:
        item["labels"] = labels

    required = ("repo_handle", "owner_route", "validation_surface", "promotion_target")
    if not all(item.get(key) for key in required):
        return None
    if not item.get("anchor_id"):
        repo = str(item.get("repo_handle") or "")
        issue = str(item.get("issue_handle") or "")
        anchor_basis = "|".join(part for part in (repo, issue, str(index)) if part)
        item["anchor_id"] = f"issue_anchor_{hashlib.sha1(anchor_basis.encode('utf-8')).hexdigest()[:10]}"
    return item


def parse_issue_meta_surface(state_text: str) -> dict[str, Any] | None:
    section_map = active_state_sections(state_text, ISSUE_META_SURFACE_SECTION_HEADINGS)
    for heading in ISSUE_META_SURFACE_SECTION_HEADINGS:
        lines = section_map.get(heading) or []
        blocks = issue_meta_surface_blocks(lines)
        items = [
            item
            for index, block in enumerate(blocks, start=1)
            for item in [parse_issue_meta_surface_block(block, index=index)]
            if item
        ]
        if items:
            return {
                "schema_version": ISSUE_META_SURFACE_SCHEMA_VERSION,
                "source_section": heading,
                "item_count": len(items),
                "items": items[:MAX_ISSUE_META_SURFACE_ITEMS],
            }
    return None


def active_state_section_entries(lines: list[str]) -> list[str]:
    entries: list[str] = []
    current: list[str] = []
    for line in lines:
        bullet_match = BACKLOG_HYGIENE_BULLET_PATTERN.match(line)
        if bullet_match:
            if current:
                entries.append(normalize_todo_text(" ".join(current)))
            current = [bullet_match.group(1)]
            continue
        if current and line.startswith((" ", "\t")):
            continuation = line.strip()
            if continuation:
                current.append(continuation)
            continue
        if current:
            entries.append(normalize_todo_text(" ".join(current)))
            current = []
        stripped = line.strip()
        if stripped:
            entries.append(stripped)
    if current:
        entries.append(normalize_todo_text(" ".join(current)))
    return entries


def backlog_hygiene_warning(state_text: str, *, agent_todos: dict[str, Any] | None) -> dict[str, Any] | None:
    try:
        agent_open_count = int(agent_todos.get("open_count") or 0) if isinstance(agent_todos, dict) else 0
    except (TypeError, ValueError):
        agent_open_count = 0
    if agent_open_count > 0:
        return None

    evidence: list[dict[str, Any]] = []
    sections = active_state_sections(state_text, BACKLOG_HYGIENE_SECTION_HEADINGS)
    for section, lines in sections.items():
        for line in lines:
            bullet_match = BACKLOG_HYGIENE_BULLET_PATTERN.match(line)
            if not bullet_match:
                continue
            text = public_safe_compact_text(bullet_match.group(1), limit=220)
            if not text:
                continue
            if section.lower() == "next action" or BACKLOG_HYGIENE_HINT_PATTERN.search(text):
                evidence.append({"section": section, "text": text})

    if not evidence:
        return None

    source_sections = sorted({str(item.get("section") or "") for item in evidence if item.get("section")})
    return {
        "kind": "hidden_backlog_without_agent_todo",
        "requires_agent_todo": True,
        "source_sections": source_sections,
        "agent_open_count": agent_open_count,
        "evidence_count": len(evidence),
        "first_evidence": evidence[:MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS],
        "recommended_action": (
            "mirror durable follow-up work into Agent Todo before heartbeat scheduling relies on "
            "Next Action or Operating Lessons"
        ),
    }


def autonomous_replan_obligation(
    state_text: str,
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    evidence: list[dict[str, Any]] = []
    seen_kinds: set[str] = set()
    sections = active_state_sections(state_text, AUTONOMOUS_REPLAN_SECTION_HEADINGS)
    for section, lines in sections.items():
        for entry in active_state_section_entries(lines):
            text = public_safe_compact_text(entry, limit=160)
            if not text:
                continue
            for kind, pattern in AUTONOMOUS_REPLAN_TRIGGER_PATTERNS:
                if kind in seen_kinds or not pattern.search(text):
                    continue
                evidence.append({"kind": kind, "section": section, "text": text})
                seen_kinds.add(kind)
                if len(evidence) >= MAX_AUTONOMOUS_REPLAN_TRIGGERS:
                    break
            if len(evidence) >= MAX_AUTONOMOUS_REPLAN_TRIGGERS:
                break
        if len(evidence) >= MAX_AUTONOMOUS_REPLAN_TRIGGERS:
            break

    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def build_autonomous_replan_obligation(
    evidence: list[dict[str, Any]],
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not evidence:
        return None

    dead_monitor_evidence = next(
        (item for item in evidence if item.get("kind") == "dead_monitor_repeat"),
        None,
    )
    first_open: dict[str, Any] = {}
    if isinstance(agent_todos, dict):
        open_items = agent_todos.get("first_open_items")
        if isinstance(open_items, list) and open_items and isinstance(open_items[0], dict):
            first_open = open_items[0]

    todo_actions: list[dict[str, Any]] = []
    first_open_text = public_safe_compact_text(first_open.get("text"), limit=140)
    if first_open_text:
        action: dict[str, Any] = {
            "action": "split",
            "role": "agent",
            "text": first_open_text,
        }
        if first_open.get("priority"):
            action["priority"] = first_open.get("priority")
        todo_actions.append(action)
    if dead_monitor_evidence:
        todo_actions.append(
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "resolve the repeated monitor target with watch-lane expiry, "
                    "a concrete blocker, todo supersede, or successor runnable todo"
                ),
            }
        )
    else:
        todo_actions.append(
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "write a compact replan record naming trigger, selected next slice, "
                    "validation command, and stop condition"
                ),
            }
        )
    if any(item.get("kind") in {"no_progress_streak", "repeated_action_loop"} for item in evidence):
        todo_actions.append(
            {
                "action": "retire",
                "role": "agent",
                "priority": "P2",
                "text": "retire or downgrade stale monitor-only next actions after the executable replan is selected",
            }
        )
    if any(item.get("kind") in {"periodic_review", "periodic_review_due"} for item in evidence):
        todo_actions.append(
            {
                "action": "ask_decision",
                "role": "user",
                "priority": "P2",
                "text": (
                    "ask the operator only if the review changes benchmark family, public claims, "
                    "resource budget, or protected scope"
                ),
            }
        )

    if dead_monitor_evidence:
        recommended_action = (
            "resolve a dead monitor loop: record watch-lane continuation with expiry, "
            "a concrete blocker, todo supersede, or successor runnable todo before "
            "another quiet monitor poll"
        )
    elif any(item.get("kind") in {"periodic_review", "periodic_review_due"} for item in evidence):
        recommended_action = (
            "run a bounded autonomous periodic review: keep, split, add, retire, or ask for "
            "a decision; then update todos and select the next validated slice"
        )
    else:
        recommended_action = (
            "run an autonomous replan after two consecutive stalled turns before another "
            "monitor-only or repeated action consumes the eligible turn"
        )

    result = {
        "schema_version": AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        "required": True,
        "stall_threshold": (
            DEAD_MONITOR_REPEAT_THRESHOLD
            if dead_monitor_evidence
            else AUTONOMOUS_REPLAN_STALL_THRESHOLD
        ),
        "trigger_count": len(evidence),
        "triggers": evidence,
        "guidance_actions": (
            ["set_watch_expiry", "write_blocker", "supersede_monitor", "create_successor"]
            if dead_monitor_evidence
            else ["keep", "split", "add", "retire", "ask_decision"]
        ),
        "todo_actions": todo_actions[:3],
        "next_validation_command": "python3 examples/autonomous-replan-obligation-smoke.py",
        "stop_condition": (
            "stop if the replan requires private material, credentials, destructive git, "
            "production actions, or owner-only decisions"
        ),
        "recommended_action": recommended_action,
    }
    if dead_monitor_evidence:
        result["dead_monitor_detector"] = {
            "schema_version": DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
            "monitor_target_id": dead_monitor_evidence.get("monitor_target_id"),
            "run_count": dead_monitor_evidence.get("run_count"),
            "threshold": dead_monitor_evidence.get("threshold"),
            "required_resolution": [
                "watch_lane_expiry",
                "blocker",
                "todo_supersede",
                "successor_runnable_todo",
            ],
        }
    return result


def _normalized_run_history_stall_signature(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _run_history_monitor_target(run: dict[str, Any]) -> dict[str, Any] | None:
    target = run.get("monitor_target")
    if isinstance(target, dict):
        return target
    event = run.get("monitor_event")
    if isinstance(event, dict) and isinstance(event.get("monitor_target"), dict):
        return event.get("monitor_target")
    return None


def _run_history_stall_signal(run: dict[str, Any]) -> dict[str, Any] | None:
    if autonomous_replan_ack_recorded(run):
        return None
    classification = str(run.get("classification") or "").strip()
    if not classification or classification in AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS:
        return None
    delivery_outcome = normalize_delivery_outcome(run.get("delivery_outcome"))
    if delivery_outcome in AUTONOMOUS_RUN_HISTORY_PROGRESS_OUTCOMES:
        return None
    recommended_action = public_safe_compact_text(run.get("recommended_action"), limit=140)
    health_check = public_safe_compact_text(run.get("health_check"), limit=140)
    combined = " ".join(
        value
        for value in (
            classification,
            recommended_action,
            health_check,
            delivery_outcome.value if delivery_outcome else "",
        )
        if value
    )
    if not combined or not AUTONOMOUS_RUN_HISTORY_STALL_PATTERN.search(combined):
        return None
    action_or_classification = recommended_action or classification
    signal = {
        "classification": classification,
        "generated_at": str(run.get("generated_at") or ""),
        "recommended_action": recommended_action,
        "delivery_outcome": delivery_outcome.value if delivery_outcome else None,
        "signature": _normalized_run_history_stall_signature(action_or_classification),
    }
    monitor_target = _run_history_monitor_target(run)
    if monitor_target:
        signal["monitor_target_id"] = str(monitor_target.get("target_id") or "")
        signal["monitor_target"] = {
            key: monitor_target.get(key)
            for key in ("schema_version", "target_id", "monitor_mode", "effective_action", "agent_id")
            if monitor_target.get(key)
        }
    return signal


def run_history_monitor_wait_already_acknowledged(
    latest_runs: list[dict[str, Any]] | None,
    *,
    signal_count: int,
) -> bool:
    """Return true when newer monitor-poll stalls already have a compact ack run behind them."""

    for run in (latest_runs or [])[signal_count:]:
        if not isinstance(run, dict):
            continue
        if autonomous_replan_ack_recorded(run):
            return True
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS:
            continue
        if classification == "quota_monitor_poll":
            continue
        return False
    return False


def autonomous_replan_ack_recorded(run: dict[str, Any]) -> bool:
    ack = run.get("autonomous_replan_ack")
    if not isinstance(ack, dict) or ack.get("recorded") is not True:
        return False
    delta_contract = ack.get("delta_contract")
    if not isinstance(delta_contract, dict):
        return False
    return delta_contract.get("delta_present") is True


def compact_autonomous_replan_ack(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict) or not autonomous_replan_ack_recorded(run):
        return None
    ack = run.get("autonomous_replan_ack")
    delta_contract = ack.get("delta_contract") if isinstance(ack, dict) else {}
    if not isinstance(delta_contract, dict):
        return None
    compact_delta = {
        "schema_version": delta_contract.get("schema_version"),
        "delta_present": bool(delta_contract.get("delta_present")),
        "delta_kinds": [
            str(item)
            for item in (delta_contract.get("delta_kinds") or [])
            if str(item or "").strip()
        ],
    }
    return {
        "schema_version": ack.get("schema_version"),
        "recorded": True,
        "source": ack.get("source"),
        "delta_contract": compact_delta,
    }


def latest_autonomous_replan_ack_for_projection(
    latest_runs: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Return the newest durable replan ACK, skipping neutral accounting runs."""

    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        replan_ack = compact_autonomous_replan_ack(run)
        if replan_ack:
            return replan_ack
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS:
            continue
        if classification == "quota_monitor_poll":
            continue
        return None
    return None


def autonomous_replan_periodic_review_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    durable_runs: list[dict[str, Any]] = []
    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        if autonomous_replan_ack_recorded(run):
            break
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS:
            continue
        durable_runs.append(run)
        if len(durable_runs) >= AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD:
            break

    if len(durable_runs) < AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD:
        return None

    evidence: list[dict[str, Any]] = [
        {
            "kind": "periodic_review_due",
            "section": "run_history",
            "text": (
                f"latest {len(durable_runs)} durable public run records since last autonomous "
                f"replan reached periodic review threshold {AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD}"
            ),
            "run_count": len(durable_runs),
            "threshold": AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD,
            "latest_generated_at": str(durable_runs[0].get("generated_at") or ""),
            "oldest_counted_generated_at": str(durable_runs[-1].get("generated_at") or ""),
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def autonomous_replan_obligation_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    signals: list[dict[str, Any]] = []
    signal_scan_limit = max(AUTONOMOUS_REPLAN_STALL_THRESHOLD, DEAD_MONITOR_REPEAT_THRESHOLD)
    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        classification = str(run.get("classification") or "").strip()
        if classification in AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS:
            continue
        signal = _run_history_stall_signal(run)
        if not signal:
            break
        signals.append(signal)
        if len(signals) >= signal_scan_limit:
            break

    stall_signals = signals[:AUTONOMOUS_REPLAN_STALL_THRESHOLD]
    if len(stall_signals) < AUTONOMOUS_REPLAN_STALL_THRESHOLD:
        return autonomous_replan_periodic_review_from_runs(
            latest_runs,
            agent_todos=agent_todos,
        )

    signatures = {str(signal.get("signature") or "") for signal in stall_signals if signal.get("signature")}
    classifications = {
        str(signal.get("classification") or "")
        for signal in stall_signals
        if signal.get("classification")
    }
    periodic_review = autonomous_replan_periodic_review_from_runs(
        latest_runs,
        agent_todos=agent_todos,
    )
    if len(signatures) > 1 and len(classifications) > 1:
        return periodic_review
    if classifications == {"quota_monitor_poll"}:
        monitor_signals = signals[:DEAD_MONITOR_REPEAT_THRESHOLD]
        if len(monitor_signals) < DEAD_MONITOR_REPEAT_THRESHOLD:
            return periodic_review
        monitor_classifications = {
            str(signal.get("classification") or "")
            for signal in monitor_signals
            if signal.get("classification")
        }
        if monitor_classifications != {"quota_monitor_poll"}:
            return periodic_review
        if run_history_monitor_wait_already_acknowledged(
            latest_runs,
            signal_count=len(monitor_signals),
        ):
            return periodic_review
        monitor_target_ids = {
            str(signal.get("monitor_target_id") or "")
            for signal in monitor_signals
            if signal.get("monitor_target_id")
        }
        if len(monitor_target_ids) != 1:
            return periodic_review
        monitor_target_id = next(iter(monitor_target_ids))
        evidence = [
            {
                "kind": "dead_monitor_repeat",
                "schema_version": DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
                "section": "run_history",
                "text": (
                    f"latest {DEAD_MONITOR_REPEAT_THRESHOLD} monitor polls repeated "
                    "the same monitor target without a material transition"
                ),
                "run_count": len(monitor_signals),
                "threshold": DEAD_MONITOR_REPEAT_THRESHOLD,
                "monitor_target_id": monitor_target_id,
                "latest_generated_at": signals[0].get("generated_at"),
            }
        ]
        return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)

    action = public_safe_compact_text(
        stall_signals[0].get("recommended_action") or stall_signals[0].get("classification"),
        limit=120,
    )
    evidence_text = (
        f"latest {AUTONOMOUS_REPLAN_STALL_THRESHOLD} public run records repeated "
        f"{action or 'the same monitor/no-progress action'}"
    )
    evidence: list[dict[str, Any]] = [
        {
            "kind": "run_history_no_progress_repeat",
            "section": "run_history",
            "text": evidence_text,
            "run_count": len(stall_signals),
            "latest_generated_at": stall_signals[0].get("generated_at"),
        }
    ]
    return build_autonomous_replan_obligation(evidence, agent_todos=agent_todos)


def open_todo_items(
    todos: dict[str, Any] | None,
    *,
    limit: int = MAX_PROJECT_ASSET_TODO_ITEMS,
    text_limit: int = 220,
    source_keys: tuple[str, ...] = ("first_open_items", "items"),
) -> list[dict[str, Any]]:
    if not isinstance(todos, dict):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    for source_key in source_keys:
        source_items = todos.get(source_key)
        if not isinstance(source_items, list):
            continue
        for item in source_items:
            if not isinstance(item, dict) or item.get("done"):
                continue
            text = normalize_todo_text(str(item.get("text") or ""), limit=text_limit)
            if not text:
                continue
            key = (item.get("index"), text)
            if key in seen:
                continue
            seen.add(key)
            compact = compact_todo_item(item)
            compact["done"] = False
            compact["text"] = text
            result.append(compact)
            if len(result) >= limit:
                return sorted(result, key=todo_projection_sort_key)
    return sorted(result, key=todo_projection_sort_key)


def todo_lane_items(
    todos: dict[str, Any] | None,
    lane: str,
    *,
    limit: int = MAX_STATUS_TODOS_PER_ROLE,
    text_limit: int = 220,
) -> list[dict[str, Any]]:
    return open_todo_items(
        todos,
        limit=limit,
        text_limit=text_limit,
        source_keys=(lane,),
    )


def first_open_todo_text(todos: dict[str, Any] | None) -> str | None:
    items = open_todo_items(todos, limit=1)
    if not items:
        return None
    return str(items[0].get("text") or "") or None


def project_asset_todo_summary(
    todos: dict[str, Any] | None,
    *,
    role: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(todos, dict):
        return None
    open_count = todos.get("open_count", 0)
    done_count = todos.get("done_count", 0)
    total_count = todos.get("total_count", 0)
    todo_role = str(role or todos.get("role") or "").strip().lower()
    metadata = project_asset_todo_projection_metadata(
        role=todo_role,
        item_limit=MAX_PROJECT_ASSET_TODO_ITEMS,
        deferred_item_limit=MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    )
    summary: dict[str, Any] = {
        "schema_version": todos.get("schema_version") or "todo_summary_v0",
        "source_section": "project_asset",
        "open": open_count,
        "done": done_count,
        "total": total_count,
        **metadata,
    }
    open_items = open_todo_items(todos, limit=MAX_PROJECT_ASSET_TODO_ITEMS)
    claimed_open_count = sum(1 for item in open_items if item.get("claimed_by"))
    if claimed_open_count or todos.get("claimed_open_count"):
        summary["claimed_open_count"] = todos.get("claimed_open_count", claimed_open_count)
        summary["unclaimed_open_count"] = todos.get(
            "unclaimed_open_count",
            max(0, int(summary.get("open") or 0) - int(summary["claimed_open_count"] or 0)),
        )
    if open_items:
        summary["items"] = open_items
        summary["next"] = open_items[0]["text"]
        if open_items[0].get("index") is not None:
            summary["next_index"] = open_items[0].get("index")
        if open_items[0].get("claimed_by"):
            summary["next_claimed_by"] = open_items[0].get("claimed_by")
    monitor_writeback = todos.get("monitor_writeback")
    if isinstance(monitor_writeback, dict):
        summary["monitor_writeback"] = dict(monitor_writeback)
    deferred_items = [
        compact_todo_item(item)
        for item in todos.get("deferred_items", [])
        if isinstance(item, dict)
    ][:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
    deferred_resume_candidates = [
        compact_todo_item(item)
        for item in todos.get("deferred_resume_candidates", [])
        if isinstance(item, dict)
    ][:MAX_DEFERRED_TODO_VISIBILITY_ITEMS]
    if todos.get("deferred_count") is not None:
        summary["deferred_count"] = todos.get("deferred_count")
        summary["deferred_visibility_limit"] = MAX_DEFERRED_TODO_VISIBILITY_ITEMS
    if deferred_items:
        summary["deferred_items"] = deferred_items
    if deferred_resume_candidates:
        summary["deferred_resume_candidates"] = deferred_resume_candidates
    executable_items = [
        item
        for item in open_todo_items(
            todos,
            limit=MAX_PROJECT_ASSET_TODO_ITEMS,
            source_keys=("first_executable_items", "executable_backlog_items", "items"),
        )
        if todo_item_is_actionable_open(item)
        if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    if executable_items:
        summary["first_executable_items"] = executable_items[:MAX_PROJECT_ASSET_TODO_ITEMS]
    for lane in (
        "gate_open_items",
        "current_agent_claimed_open_items",
        "active_next_action_items",
        "active_next_action_executable_items",
    ):
        lane_items = todo_lane_items(
            todos,
            lane,
            limit=MAX_PROJECT_ASSET_TODO_ITEMS,
        )
        if lane_items:
            summary[lane] = lane_items
    for count_key in (
        "claimed_advancement_open_count",
        "claimed_monitor_open_count",
    ):
        if todos.get(count_key) is not None:
            summary[count_key] = todos.get(count_key)
    return summary


def dependency_blocker_summary(
    items: list[dict[str, Any]],
    *,
    current_goal_id: str,
    limit: int = MAX_DEPENDENCY_BLOCKERS,
) -> dict[str, Any] | None:
    blockers: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id or goal_id == current_goal_id:
            continue
        user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else {}
        for todo in user_todos.get("items") or []:
            if not isinstance(todo, dict) or todo.get("done"):
                continue
            text = normalize_todo_text(str(todo.get("text") or ""), limit=220)
            if not text:
                continue
            blockers.append(
                {
                    "goal_id": goal_id,
                    "status": item.get("status"),
                    "waiting_on": item.get("waiting_on"),
                    "severity": item.get("severity"),
                    "index": todo.get("index"),
                    "text": text,
                    "source": "user_todos",
                }
            )
    if not blockers:
        return None
    return {
        "source": "attention_queue.user_todos",
        "open_count": len(blockers),
        "items": blockers[:limit],
    }


def attach_dependency_blockers(items: list[dict[str, Any]]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id:
            continue
        blockers = dependency_blocker_summary(items, current_goal_id=goal_id)
        if blockers:
            item["dependency_blockers"] = blockers


def first_open_todo_item(todos: dict[str, Any] | None) -> dict[str, Any] | None:
    for todo in open_todo_items(todos):
        if not isinstance(todo, dict) or todo.get("done"):
            continue
        return todo
    return None


def autonomous_priority_label(text: str) -> str | None:
    match = AUTONOMOUS_PRIORITY_PATTERN.match(text)
    if not match:
        return None
    return match.group(1).strip().upper()


def autonomous_priority_rank(priority: str | None) -> int:
    if not priority:
        return 50
    match = re.match(r"P([0-4])", priority)
    if not match:
        return 50
    return int(match.group(1))


def autonomous_todo_candidates(
    items: list[dict[str, Any]],
    *,
    task_class: str,
    allowed_waiting_on: set[str] | None = None,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    allowed_waiting_on = allowed_waiting_on or {"codex"}
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("waiting_on") not in allowed_waiting_on:
            continue
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        if quota.get("state") != "eligible":
            continue
        todos = item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
        for todo in open_todo_items(todos):
            if not todo_item_is_actionable_open(todo):
                continue
            todo_class = normalize_todo_task_class(
                todo.get("task_class"),
                text=str(todo.get("text") or ""),
                action_kind=todo.get("action_kind"),
            )
            if todo_class != task_class:
                continue
            text = normalize_todo_text(str(todo.get("text") or ""), limit=240)
            if not text:
                continue
            priority = autonomous_priority_label(text)
            candidates.append(
                {
                    "goal_id": item.get("goal_id"),
                    "status": item.get("status"),
                    "waiting_on": item.get("waiting_on"),
                    "quota_state": quota.get("state"),
                    "priority": priority,
                    "todo_index": todo.get("index"),
                    "task_class": todo_class,
                    "text": text,
                    "source": "agent_todos",
                }
            )
            action_kind = normalize_todo_action_kind(todo.get("action_kind"))
            if action_kind:
                candidates[-1]["action_kind"] = action_kind
    if not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            autonomous_priority_rank(candidate.get("priority") if isinstance(candidate.get("priority"), str) else None),
            str(candidate.get("goal_id") or ""),
            int(candidate.get("todo_index") or 0),
        )
    )
    return {
        "source": "attention_queue.agent_todos",
        "open_count": len(candidates),
        "task_class": task_class,
        "items": candidates[:limit],
    }


def autonomous_backlog_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    return autonomous_todo_candidates(
        items,
        task_class=TODO_TASK_CLASS_ADVANCEMENT,
        limit=limit,
    )


def autonomous_monitor_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    return autonomous_todo_candidates(
        items,
        task_class=TODO_TASK_CLASS_MONITOR,
        allowed_waiting_on={"codex", MONITOR_SIGNAL_WAITING_ON},
        limit=limit,
    )


def _subagent_state(run: dict[str, Any]) -> str | None:
    for field in ("result_status", "state", "status", "classification"):
        value = public_safe_compact_text(run.get(field), limit=80)
        if value:
            return value
    return None


def _subagent_quota_spend(run: dict[str, Any]) -> int:
    for field in ("quota_spend", "quota_slots", "spent_slots"):
        raw = run.get(field)
        if isinstance(raw, bool):
            continue
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            pass
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    raw_slots = quota_event.get("slots")
    try:
        return max(0, int(raw_slots))
    except (TypeError, ValueError):
        return 0


def compact_subagent_run(
    raw: dict[str, Any],
    *,
    parent_goal_id: str | None = None,
    parent_run_id: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    run_id = public_safe_compact_text(
        raw.get("run_id") or raw.get("id") or raw.get("generated_at"),
        limit=120,
    )
    role = public_safe_compact_text(raw.get("agent_role") or raw.get("role"), limit=80)
    state = _subagent_state(raw)
    if not (run_id or role or state):
        return None

    compact: dict[str, Any] = {}
    if run_id:
        compact["run_id"] = run_id
    goal_id = public_safe_compact_text(raw.get("goal_id") or raw.get("id"), limit=120)
    if goal_id:
        compact["goal_id"] = goal_id
    parent_run = public_safe_compact_text(raw.get("parent_run_id") or parent_run_id, limit=120)
    if parent_run:
        compact["parent_run_id"] = parent_run
    spawned_by = public_safe_compact_text(raw.get("spawned_by_goal_id") or parent_goal_id, limit=120)
    if spawned_by:
        compact["spawned_by_goal_id"] = spawned_by
    if role:
        compact["agent_role"] = role
    if state:
        compact["state"] = state
    for field in ("claim_id", "approval_state"):
        value = public_safe_compact_text(raw.get(field), limit=120)
        if value:
            compact[field] = value
    work_scope = public_safe_compact_list(raw.get("work_scope") or raw.get("scope"))
    if work_scope:
        compact["work_scope"] = work_scope
    touched_paths = public_safe_compact_list(raw.get("touched_paths") or raw.get("changed_files"))
    if touched_paths:
        compact["touched_paths"] = touched_paths
    raw_touched = raw.get("touched_paths") or raw.get("changed_files")
    if isinstance(raw_touched, list):
        compact["touched_path_count"] = len(raw_touched)
    handoff = public_safe_compact_text(raw.get("handoff_summary") or raw.get("summary"), limit=260)
    if handoff:
        compact["handoff_summary"] = handoff
    quota_spend = _subagent_quota_spend(raw)
    if quota_spend:
        compact["quota_spend_slots"] = quota_spend
    return compact


def subagent_activity_for_goal(goal: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(goal, dict):
        return None
    parent_goal_id = str(goal.get("id") or "")
    latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    children: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_child(raw: dict[str, Any], *, parent_run_id: str | None = None) -> None:
        child = compact_subagent_run(
            raw,
            parent_goal_id=parent_goal_id or None,
            parent_run_id=parent_run_id,
        )
        if not child:
            return
        key = (
            str(child.get("run_id") or ""),
            str(child.get("goal_id") or ""),
            str(child.get("agent_role") or ""),
        )
        if key in seen:
            return
        seen.add(key)
        children.append(child)

    for run in latest_runs:
        if not isinstance(run, dict):
            continue
        parent_run_id = str(run.get("run_id") or run.get("generated_at") or "")
        for child in run.get("subagents") or []:
            if isinstance(child, dict):
                add_child(child, parent_run_id=parent_run_id)
        if run.get("parent_run_id") or run.get("spawned_by_goal_id") or run.get("agent_role"):
            add_child(run, parent_run_id=str(run.get("parent_run_id") or ""))

    if not children:
        return None
    limited = children[:MAX_SUBAGENT_ACTIVITY_ITEMS]
    completed_states = {"completed", "done", "success", "passed"}
    active_states = {"running", "active", "in_progress", "queued", "started"}
    completed = sum(1 for child in children if str(child.get("state") or "").lower() in completed_states)
    active = sum(1 for child in children if str(child.get("state") or "").lower() in active_states)
    quota_spend = sum(int(child.get("quota_spend_slots") or 0) for child in children)
    summary: dict[str, Any] = {
        "source": "run_history",
        "parent_goal_id": parent_goal_id,
        "child_count": len(children),
        "visible_child_count": len(limited),
        "completed_count": completed,
        "active_count": active,
        "quota_spend_slots": quota_spend,
        "items": limited,
        "proxy_note": "compact child-run projection only; parent controller remains the authority for locks, writes, and merge decisions",
    }
    return summary


def active_state_projection_warning(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(goal, dict) or not goal.get("registry_member") or not isinstance(current_run, dict):
        return None
    state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=Path.cwd())
    if state_path is None or not state_path.exists():
        return None
    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return None

    frontmatter = parse_state_frontmatter(state_text)
    active_updated_at = frontmatter.get("updated_at")
    active_digest = hashlib.sha256(state_text.encode("utf-8")).hexdigest()[:16]
    run_state = current_run.get("state") if isinstance(current_run.get("state"), dict) else {}
    run_frontmatter = run_state.get("frontmatter") if isinstance(run_state.get("frontmatter"), dict) else {}
    run_state_updated_at = run_frontmatter.get("updated_at")
    run_state_digest = str(run_state.get("sha256_16") or "")
    latest_run_generated_at = str(current_run.get("generated_at") or "")

    active_dt = parse_timestamp(active_updated_at)
    run_state_dt = parse_timestamp(run_state_updated_at)
    run_generated_dt = parse_timestamp(latest_run_generated_at)
    active_newer_than_run_state = bool(active_dt and run_state_dt and active_dt > run_state_dt)
    active_newer_than_run = bool(active_dt and run_generated_dt and active_dt > run_generated_dt)
    digest_mismatch = bool(run_state_digest and active_digest != run_state_digest)
    if not (active_newer_than_run_state or active_newer_than_run or digest_mismatch):
        return None
    for run in goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []:
        if not isinstance(run, dict):
            continue
        if str(run.get("progress_scope") or "") != AGENT_LANE_PROGRESS_SCOPE:
            continue
        agent_run_state = run.get("state") if isinstance(run.get("state"), dict) else {}
        agent_run_frontmatter = (
            agent_run_state.get("frontmatter")
            if isinstance(agent_run_state.get("frontmatter"), dict)
            else {}
        )
        agent_run_digest = str(agent_run_state.get("sha256_16") or "")
        agent_run_updated_at = agent_run_frontmatter.get("updated_at")
        agent_run_state_dt = parse_timestamp(agent_run_updated_at)
        agent_run_generated_dt = parse_timestamp(str(run.get("generated_at") or ""))
        if agent_run_digest and agent_run_digest == active_digest:
            return None
        if active_dt and agent_run_state_dt and active_dt <= agent_run_state_dt:
            return None
        if active_dt and not agent_run_state_dt and agent_run_generated_dt and active_dt <= agent_run_generated_dt:
            return None

    reasons: list[str] = []
    if active_newer_than_run:
        reasons.append("active_state_updated_after_latest_run")
    if active_newer_than_run_state:
        reasons.append("active_state_updated_after_latest_run_snapshot")
    if digest_mismatch:
        reasons.append("active_state_digest_differs_from_latest_run_snapshot")

    return {
        "kind": "stale_latest_run_projection",
        "source": "active_state_vs_latest_run",
        "severity": "warning",
        "requires_refresh_state": True,
        "reason": ",".join(reasons),
        "active_state_updated_at": active_updated_at,
        "latest_run_generated_at": latest_run_generated_at,
        "latest_run_state_updated_at": run_state_updated_at,
        "latest_run_classification": current_run.get("classification"),
        "recommended_action": "run refresh-state before trusting latest_run-derived routing",
    }


def is_handoff_ready_run(run: dict[str, Any]) -> bool:
    classification = str(run.get("classification") or "")
    if classification in HANDOFF_READY_CLASSIFICATIONS:
        return True
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    return bool(
        operator_gate
        and operator_gate.get("decision") == "approve"
        and operator_gate.get("agent_command")
    )


def run_has_external_evidence_watch_signal(run: dict[str, Any]) -> bool:
    """Return true only for explicit external-evidence watch state.

    Feature names may legitimately start with words such as "monitor"; routing
    to an external-evidence wait must come from structured state or explicit
    legacy external-evidence classifications, not broad classification prefixes.
    """

    waiting_on = str(run.get("waiting_on") or "").strip()
    execution_waiting_on = str(run.get("execution_waiting_on") or "").strip()
    if waiting_on == "external_evidence" or execution_waiting_on == "external_evidence":
        return True
    if isinstance(run.get("external_evidence_observation"), dict):
        return True
    monitor_event = run.get("monitor_event")
    if isinstance(monitor_event, dict):
        event_waiting_on = str(monitor_event.get("waiting_on") or "").strip()
        monitor_mode = str(monitor_event.get("monitor_mode") or "").strip()
        monitor_kind = str(monitor_event.get("monitor_kind") or "").strip()
        if event_waiting_on == "external_evidence":
            return True
        if monitor_mode.startswith("external_") or monitor_kind == "external_evidence":
            return True
    classification = str(run.get("classification") or "")
    return classification.startswith(LEGACY_EXTERNAL_EVIDENCE_CLASSIFICATION_PREFIXES)


def is_custom_post_handoff_work_run(run: dict[str, Any]) -> bool:
    classification = str(run.get("classification") or "")
    if not classification:
        return False
    if is_status_neutral_run(run) or is_handoff_ready_run(run):
        return False
    if classification in CODEX_READY_CLASSIFICATIONS:
        return False
    if classification in USER_OR_CONTROLLER_CLASSIFICATIONS or classification in BLOCKING_CLASSIFICATIONS:
        return False
    if run_has_external_evidence_watch_signal(run):
        return False
    return True


def delivery_batch_scale_for_run(run: dict[str, Any]) -> str:
    explicit = normalize_delivery_batch_scale(run.get("delivery_batch_scale"))
    if explicit:
        return explicit.value
    if str(run.get("delivery_batch_scale") or "").strip():
        return UNKNOWN_DELIVERY_BATCH_SCALE
    classification = str(run.get("classification") or "")
    if not classification:
        return UNKNOWN_DELIVERY_BATCH_SCALE
    normalized = classification.lower()
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_TEST_ONLY_CLASSIFICATION_HINTS):
        return DeliveryBatchScale.TEST_ONLY.value
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_MULTI_SURFACE_CLASSIFICATION_HINTS):
        return DeliveryBatchScale.MULTI_SURFACE.value
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_IMPLEMENTATION_CLASSIFICATION_HINTS):
        return DeliveryBatchScale.IMPLEMENTATION.value
    return DeliveryBatchScale.SINGLE_SURFACE.value


def _classification_contains_any(classification: str, hints: list[Any]) -> bool:
    normalized = classification.lower()
    return any(str(hint or "").strip().lower() in normalized for hint in hints if str(hint or "").strip())


def delivery_outcome_for_run(run: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    explicit = normalize_delivery_outcome(run.get("delivery_outcome"))
    if explicit:
        return explicit.value
    if str(run.get("delivery_outcome") or "").strip():
        return DELIVERY_OUTCOME_UNKNOWN
    classification = str(run.get("classification") or "")
    if not classification:
        return DELIVERY_OUTCOME_UNKNOWN
    floor = execution_profile_outcome_floor(profile)
    outcome_markers = floor.get("outcome_markers") if isinstance(floor.get("outcome_markers"), list) else []
    surface_hints = floor.get("surface_only_hints") if isinstance(floor.get("surface_only_hints"), list) else []
    if not outcome_markers and not surface_hints:
        return DELIVERY_OUTCOME_NOT_CONFIGURED
    marker_hit = _classification_contains_any(classification, outcome_markers)
    surface_hit = _classification_contains_any(classification, surface_hints)
    if surface_hit:
        return DeliveryOutcome.SURFACE_ONLY.value
    if marker_hit:
        return DeliveryOutcome.OUTCOME_PROGRESS.value
    return DeliveryOutcome.OUTCOME_GAP.value


def outcome_floor_configured(profile: dict[str, Any] | None) -> bool:
    floor = execution_profile_outcome_floor(profile)
    return bool(floor.get("outcome_markers") or floor.get("surface_only_hints"))


def outcome_gap_streak(runs: list[dict[str, Any]], profile: dict[str, Any] | None = None) -> int:
    if not outcome_floor_configured(profile):
        return 0
    streak = 0
    for run in runs:
        outcome = delivery_outcome_for_run(run, profile)
        normalized = normalize_delivery_outcome(outcome)
        if normalized in PROGRESS_DELIVERY_OUTCOMES or outcome == DELIVERY_OUTCOME_NOT_CONFIGURED:
            break
        streak += 1
    return streak


def compact_post_handoff_run(run: dict[str, Any], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for field in ("generated_at", "classification", "health_check", "json_exists", "markdown_exists"):
        if field in run:
            compact[field] = run[field]
    compact["delivery_batch_scale"] = delivery_batch_scale_for_run(run)
    outcome = delivery_outcome_for_run(run, profile)
    if outcome != DELIVERY_OUTCOME_NOT_CONFIGURED:
        compact["delivery_outcome"] = outcome
    compact["delivery_turn_kind"] = delivery_turn_kind_for_run(
        run,
        delivery_outcome=outcome,
    )
    benchmark_run = compact_benchmark_run(run)
    if benchmark_run:
        compact["benchmark_run_summary"] = benchmark_run
        health_note = worker_bridge_ingest_health_note(benchmark_run)
        if health_note:
            compact["worker_bridge_ingest_health_note"] = health_note
    benchmark_result = compact_benchmark_result(run)
    if benchmark_result:
        compact["benchmark_result_summary"] = benchmark_result
    benchmark_comparison = compact_benchmark_comparison(run)
    if benchmark_comparison:
        compact["benchmark_comparison_summary"] = benchmark_comparison
        decision_note = benchmark_comparison_decision_note(benchmark_comparison)
        if decision_note:
            compact["benchmark_comparison_decision_note"] = decision_note
    benchmark_learning_ledger = compact_benchmark_learning_ledger(run)
    if benchmark_learning_ledger:
        compact["benchmark_learning_ledger_summary"] = benchmark_learning_ledger
    benchmark_report = compact_benchmark_experiment_report(run)
    if benchmark_report:
        compact["benchmark_experiment_report_summary"] = benchmark_report
        readiness_note = benchmark_experiment_report_readiness_note(benchmark_report)
        if readiness_note:
            compact["benchmark_experiment_report_readiness_note"] = readiness_note
            replay_decision = benchmark_experiment_report_replay_decision(readiness_note)
            if replay_decision:
                compact["benchmark_experiment_report_replay_decision"] = replay_decision
    active_user_pilot = compact_active_user_assisted_pilot(run)
    if active_user_pilot:
        compact["active_user_assisted_pilot_summary"] = active_user_pilot
    return compact


def small_delivery_batch_scale_streak(runs: list[dict[str, Any]]) -> int:
    streak = 0
    for run in runs:
        if delivery_batch_scale_for_run(run) not in SMALL_DELIVERY_BATCH_SCALES:
            break
        streak += 1
    return streak


def project_asset_handoff_state(
    *,
    ready: bool,
    project_asset: dict[str, Any],
    latest_runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    runs = [run for run in latest_runs or [] if isinstance(run, dict)]
    profile = compact_execution_profile(
        project_asset.get("execution_profile")
        if isinstance(project_asset.get("execution_profile"), dict)
        else None
    )
    parsed_runs = [
        (run, parse_timestamp(run.get("generated_at")))
        for run in runs
    ]
    parsed_runs = [(run, generated_at) for run, generated_at in parsed_runs if generated_at]
    parsed_runs.sort(key=lambda item: item[1], reverse=True)

    handoff_run: dict[str, Any] | None = None
    handoff_at: datetime | None = None
    for run, generated_at in parsed_runs:
        if is_handoff_ready_run(run):
            handoff_run = run
            handoff_at = generated_at
            break

    post_handoff_run: dict[str, Any] | None = None
    recent_post_handoff_runs: list[dict[str, Any]] = []
    if handoff_at is None and ready:
        recent_post_handoff_runs = [
            run
            for run, _generated_at in parsed_runs
            if is_custom_post_handoff_work_run(run)
        ]
        if recent_post_handoff_runs:
            post_handoff_run = recent_post_handoff_runs[0]
        latest_validation = (
            project_asset.get("latest_validation")
            if isinstance(project_asset.get("latest_validation"), dict)
            else {}
        )
        if latest_validation and post_handoff_run is None:
            latest_validation_run = {
                "generated_at": latest_validation.get("generated_at"),
                "classification": latest_validation.get("classification"),
            }
            if is_custom_post_handoff_work_run(latest_validation_run):
                post_handoff_run = latest_validation_run
                recent_post_handoff_runs = [latest_validation_run]
            else:
                handoff_at = parse_timestamp(latest_validation.get("generated_at"))
                handoff_run = latest_validation_run

    if handoff_at is not None and post_handoff_run is None:
        for run, generated_at in parsed_runs:
            if generated_at <= handoff_at:
                continue
            if is_status_neutral_run(run) or is_handoff_ready_run(run):
                continue
            recent_post_handoff_runs.append(run)
        if recent_post_handoff_runs:
            post_handoff_run = recent_post_handoff_runs[0]

    if post_handoff_run and not recent_post_handoff_runs:
        recent_post_handoff_runs = [post_handoff_run]
    if len(recent_post_handoff_runs) > 3:
        recent_post_handoff_runs = recent_post_handoff_runs[:3]

    if post_handoff_run:
        handoff_status = "post_handoff_run_seen"
    elif ready:
        handoff_status = "ready_waiting_for_run"
    else:
        handoff_status = "not_ready"

    state: dict[str, Any] = {
        "handoff_status": handoff_status,
        "post_handoff_run_seen": bool(post_handoff_run),
    }
    if handoff_run and handoff_run.get("generated_at"):
        state["handoff_ready_at"] = handoff_run.get("generated_at")
    if handoff_run and handoff_run.get("classification"):
        state["handoff_ready_classification"] = handoff_run.get("classification")
    if post_handoff_run:
        state["post_handoff_latest_run"] = compact_post_handoff_run(post_handoff_run, profile)
    if recent_post_handoff_runs:
        state["post_handoff_recent_runs"] = [
            compact_post_handoff_run(run, profile)
            for run in recent_post_handoff_runs
        ]
        state["post_handoff_small_scale_streak"] = small_delivery_batch_scale_streak(
            recent_post_handoff_runs
        )
        if outcome_floor_configured(profile):
            state["post_handoff_outcome_gap_streak"] = outcome_gap_streak(
                recent_post_handoff_runs,
                profile,
            )
    return state


def project_asset_handoff_readiness(
    item: dict[str, Any],
    *,
    latest_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return None

    check_projection = project_asset_handoff_check_projection(item)
    if not check_projection:
        return None
    checks = check_projection["checks"]
    goal_id = str(item.get("goal_id") or "").strip()
    readiness: dict[str, Any] = {
        "ready": all(checks.values()),
        "codex_ready": bool(check_projection.get("codex_ready")),
        "source": "project_asset",
        "quota_state": check_projection.get("quota_state") or "unknown",
        "handoff_interface_budget": handoff_budget_contract(),
        "checks": checks,
    }
    readiness.update(
        project_asset_handoff_state(
            ready=bool(check_projection.get("state_trace_ready")),
            project_asset=project_asset,
            latest_runs=latest_runs,
        )
    )
    if goal_id:
        readiness["next_probe"] = f"loopx review-packet --goal-id {goal_id} --handoff-only"
    return readiness


def enrich_project_asset(
    item: dict[str, Any],
    *,
    user_todos: dict[str, Any] | None = None,
    agent_todos: dict[str, Any] | None = None,
    quota: dict[str, Any] | None = None,
    latest_validation: dict[str, Any] | None = None,
    latest_runs: list[dict[str, Any]] | None = None,
    execution_profile: dict[str, Any] | None = None,
    orchestration: dict[str, Any] | None = None,
    subagent_activity: dict[str, Any] | None = None,
    interface_budget_cadence: dict[str, Any] | None = None,
) -> None:
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return
    user_summary = project_asset_todo_summary(user_todos, role="user")
    if user_summary:
        project_asset["user_todos"] = user_summary
    agent_summary = project_asset_todo_summary(agent_todos, role="agent")
    if agent_summary:
        project_asset["agent_todos"] = agent_summary
    todo_projection_gap = project_asset_todo_projection_gap(
        user_todos=user_todos,
        agent_todos=agent_todos,
    )
    if todo_projection_gap:
        project_asset["todo_projection_gap"] = todo_projection_gap
        item["todo_projection_gap"] = todo_projection_gap
    else:
        project_asset.pop("todo_projection_gap", None)
        item.pop("todo_projection_gap", None)
    quota_summary = project_asset_quota_summary(quota)
    if quota_summary:
        project_asset["quota"] = quota_summary
    if execution_profile is not None:
        project_asset["execution_profile"] = compact_execution_profile(execution_profile)
    if orchestration is not None:
        project_asset["orchestration"] = compact_orchestration_policy(orchestration)
    if subagent_activity:
        project_asset["subagent_activity"] = subagent_activity
    if interface_budget_cadence:
        project_asset["interface_budget_cadence"] = interface_budget_cadence
    if latest_validation:
        project_asset["latest_validation"] = latest_validation
    readiness = project_asset_handoff_readiness(item, latest_runs=latest_runs)
    if readiness:
        item["handoff_readiness"] = readiness
    quota_state = ""
    if isinstance(quota, dict):
        quota_state = str(quota.get("state") or "").strip()
    if not quota_state and isinstance(project_asset.get("quota"), dict):
        quota_state = str(project_asset["quota"].get("state") or "").strip()
    user_todo_open_count = None
    if isinstance(user_todos, dict):
        try:
            user_todo_open_count = int(user_todos.get("open_count"))
        except (TypeError, ValueError):
            user_todo_open_count = None
    elif isinstance(project_asset.get("user_todos"), dict):
        try:
            user_todo_open_count = int(project_asset["user_todos"].get("open_count"))
        except (TypeError, ValueError):
            user_todo_open_count = None
    cadence_hint = build_long_task_cadence_hint(
        execution_profile=(
            project_asset.get("execution_profile")
            if isinstance(project_asset.get("execution_profile"), dict)
            else None
        ),
        latest_runs=latest_runs,
        handoff_readiness=readiness,
        quota_state=quota_state or None,
        user_todo_open_count=user_todo_open_count,
    )
    project_asset["long_task_cadence_hint"] = cadence_hint
    item["long_task_cadence_hint"] = cadence_hint


def active_state_todo_fields(
    goal: dict[str, Any],
    *,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=Path.cwd())
    if state_path is None or not state_path.exists():
        return {}
    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    next_action_entries = active_state_next_action_entries(state_text, limit=3)
    preferred_todo_ids: set[str] = set()
    for entry in next_action_entries:
        preferred_todo_ids.update(active_next_action_todo_ids(entry))
    rollout_events: list[dict[str, Any]] = []
    goal_id = str(goal.get("id") or "").strip()
    if runtime_root is not None and goal_id:
        rollout_events = load_rollout_events(
            rollout_event_log_path(runtime_root, goal_id),
            limit=MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
        )
    event_fields = active_state_event_projection_fields(
        goal,
        state_path=state_path,
        preferred_todo_ids=preferred_todo_ids,
        rollout_events=rollout_events,
    )
    if event_fields.get("user_todos") or event_fields.get("agent_todos"):
        fields = event_fields
        attach_monitor_writeback_contract(
            fields,
            supported=False,
            source="event_projection_read_model",
        )
    else:
        fields = parse_active_state_todos(
            state_text,
            goal=goal,
            state_path=state_path,
            preferred_todo_ids=preferred_todo_ids,
            rollout_events=rollout_events,
        )
        attach_monitor_writeback_contract(
            fields,
            supported=True,
            source="markdown_active_state",
        )
        if event_fields:
            fields.update(event_fields)
    issue_meta_surface = parse_issue_meta_surface(state_text)
    if issue_meta_surface:
        fields["issue_meta_surface"] = issue_meta_surface
    if next_action_entries:
        fields["active_state_next_action"] = next_action_entries[0]
        fields["active_state_next_action_entries"] = next_action_entries
    warning = backlog_hygiene_warning(
        state_text,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if warning:
        fields["backlog_hygiene_warning"] = warning
    archive_warning = completed_todo_archive_warning(
        fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None
    )
    if archive_warning:
        fields["completed_todo_archive_warning"] = archive_warning
    replan_obligation = autonomous_replan_obligation(
        state_text,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if replan_obligation:
        fields["autonomous_replan_obligation"] = replan_obligation
    projection_gap = state_projection_gap_warning(
        state_text,
        user_todos=fields.get("user_todos") if isinstance(fields.get("user_todos"), dict) else None,
        agent_todos=fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None,
    )
    if projection_gap:
        fields["state_projection_gap"] = projection_gap
    if fields:
        fields = redacted_status_todo_fields(fields)
    return fields


def attention_item(
    *,
    goal_id: str,
    status: str,
    waiting_on: str,
    severity: str,
    recommended_action: str,
    source: str,
    operator_question: str | None = None,
    agent_command: str | None = None,
    controller_stage: str | None = None,
    missing_gates: list[str] | None = None,
    next_handoff_condition: str | None = None,
    lifecycle_phase: str | None = None,
    lifecycle_flags: list[str] | None = None,
    user_todos: dict[str, Any] | None = None,
    agent_todos: dict[str, Any] | None = None,
    todo_state_file: str | None = None,
    dreaming_proposal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_asset = build_project_asset(
        status=status,
        waiting_on=waiting_on,
        recommended_action=recommended_action,
        operator_question=operator_question,
        agent_command=agent_command,
        missing_gates=missing_gates,
        next_handoff_condition=next_handoff_condition,
    )
    item = {
        "goal_id": goal_id,
        "status": status,
        "waiting_on": waiting_on,
        "severity": severity,
        "recommended_action": recommended_action,
        "project_asset": project_asset,
        "source": source,
    }
    if operator_question:
        item["operator_question"] = operator_question
    if agent_command:
        item["agent_command"] = agent_command
    if controller_stage:
        item["controller_stage"] = controller_stage
    if missing_gates:
        item["missing_gates"] = missing_gates
    if next_handoff_condition:
        item["next_handoff_condition"] = next_handoff_condition
    if lifecycle_phase:
        item["lifecycle_phase"] = lifecycle_phase
    if lifecycle_flags:
        item["lifecycle_flags"] = lifecycle_flags
    if user_todos:
        item["user_todos"] = user_todos
    if agent_todos:
        item["agent_todos"] = agent_todos
    if todo_state_file:
        item["todo_state_file"] = todo_state_file
    if dreaming_proposal:
        dreaming_lane_badge = compact_dreaming_lane_badge(dreaming_proposal)
        item["dreaming_proposal"] = dreaming_proposal
        item["project_asset"]["dreaming_proposal"] = dreaming_proposal
        if dreaming_lane_badge:
            item["dreaming_lane_badge"] = dreaming_lane_badge
            item["project_asset"]["dreaming_lane_badge"] = dreaming_lane_badge
    return item


def sync_connected_attention_action_from_todos(item: dict[str, Any]) -> None:
    if item.get("status") != "connected_without_run":
        return
    agent_action = first_open_todo_text(
        item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
    )
    if not agent_action:
        return
    item["recommended_action"] = agent_action
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["next_action"] = agent_action


def active_state_todo_attention_item(
    goal: dict[str, Any],
    fields: dict[str, Any],
    current_run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Surface active-state todos even when the latest run classification is passive."""

    user_todos = fields.get("user_todos") if isinstance(fields.get("user_todos"), dict) else None
    agent_todos = fields.get("agent_todos") if isinstance(fields.get("agent_todos"), dict) else None
    active_next_action = public_safe_compact_text(
        fields.get("active_state_next_action"),
        limit=320,
    )
    user_action = public_safe_compact_text(first_open_todo_text(user_todos), limit=320)
    agent_action = public_safe_compact_text(first_open_todo_text(agent_todos), limit=320)
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)
    goal_id = str(goal.get("id") or "unknown-goal")

    if user_action or todo_summary_open_count(user_todos) > 0:
        return attention_item(
            goal_id=goal_id,
            status="active_state_user_todo",
            waiting_on="controller",
            severity="action",
            recommended_action=(
                user_action
                or active_next_action
                or "resolve the open user todo from the active goal state"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    if agent_action or todo_summary_open_count(agent_todos) > 0:
        return attention_item(
            goal_id=goal_id,
            status="active_state_agent_todo",
            waiting_on="codex",
            severity="action",
            recommended_action=(
                agent_action
                or active_next_action
                or "run the open agent todo from the active goal state"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    projection_gap = fields.get("state_projection_gap")
    if isinstance(projection_gap, dict):
        return attention_item(
            goal_id=goal_id,
            status="state_projection_gap",
            waiting_on="codex",
            severity="action",
            recommended_action=str(
                projection_gap.get("recommended_action")
                or "expand the active-state Next Action into parseable todos"
            ),
            source="active_state",
            **lifecycle_fields,
        )

    return None


def todo_summary_open_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    for key in ("open_count", "open"):
        value = summary.get(key)
        if isinstance(value, int):
            return max(0, value)
    return len(
        [
            item
            for item in open_todo_items(summary, limit=MAX_STATUS_TODOS_PER_ROLE)
            if todo_item_is_actionable_open(item)
        ]
    )


def todo_summary_lane_items(summary: dict[str, Any] | None, lane: str) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    raw_items = summary.get(lane)
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict)]


def attention_item_is_monitor_quiet_display_candidate(item: dict[str, Any]) -> bool:
    if item.get("waiting_on") != "codex" or item.get("severity") != "action":
        return False
    agent_todos = item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None
    if not agent_todos:
        return False
    user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else None
    if todo_summary_open_count(user_todos) > 0:
        return False
    open_count = todo_summary_open_count(agent_todos)
    if open_count <= 0:
        return False
    monitor_items = [
        item
        for item in todo_summary_lane_items(agent_todos, "monitor_open_items")
        if todo_item_is_actionable_open(item)
    ]
    executable_items = [
        *todo_summary_lane_items(agent_todos, "first_executable_items"),
        *todo_summary_lane_items(agent_todos, "executable_backlog_items"),
        *todo_summary_lane_items(agent_todos, "claimed_advancement_open_items"),
    ]
    if any(todo_item_is_actionable_open(todo) for todo in executable_items):
        return False
    return len(monitor_items) == open_count


def quiet_monitor_display_action(raw_action: str | None) -> str:
    action = str(raw_action or "").strip()
    if not action:
        return MONITOR_DISPLAY_FALLBACK_ACTION
    lowered = action.lower()
    if lowered.startswith("no immediate agent work"):
        return action
    if lowered.startswith("quiet monitor only until "):
        suffix = action[len("Quiet monitor only until ") :].strip()
        if suffix:
            return f"No immediate agent work; keep the monitor quiet until {suffix}"
    if lowered.startswith("wait quietly"):
        return f"No immediate agent work; {action[0].lower()}{action[1:]}"
    return f"No immediate agent work; monitor quietly. Context: {action}"


def normalize_monitor_quiet_attention_display(item: dict[str, Any]) -> None:
    if not attention_item_is_monitor_quiet_display_candidate(item):
        return
    old_waiting_on = str(item.get("waiting_on") or "")
    old_severity = str(item.get("severity") or "")
    display_action = quiet_monitor_display_action(str(item.get("recommended_action") or ""))
    item["execution_waiting_on"] = old_waiting_on
    item["waiting_on"] = MONITOR_SIGNAL_WAITING_ON
    item["severity"] = "watch"
    item["recommended_action"] = display_action
    item["monitor_display"] = {
        "schema_version": MONITOR_DISPLAY_SCHEMA_VERSION,
        "mode": "monitor_quiet",
        "no_immediate_agent_work": True,
        "execution_waiting_on": old_waiting_on,
        "execution_severity": old_severity,
        "waiting_on": MONITOR_SIGNAL_WAITING_ON,
        "severity": "watch",
        "material_transition": (
            "write back only a material monitor transition, regression, or concrete blocker"
        ),
    }
    project_asset = item.get("project_asset")
    if isinstance(project_asset, dict):
        project_asset["owner"] = MONITOR_SIGNAL_WAITING_ON
        project_asset["gate"] = "none"
        project_asset["support_mode"] = "read_only_observer"
        project_asset["next_action"] = display_action
        project_asset["stop_condition"] = MONITOR_DISPLAY_STOP_CONDITION
        project_asset["monitor_display"] = dict(item["monitor_display"])


def compact_global_registry_shadow_finding(finding: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "kind": str(finding.get("kind") or "global_registry_finding"),
        "severity": str(finding.get("severity") or "action"),
        "source": "global_registry",
    }
    if finding.get("message"):
        compact["message"] = str(finding.get("message"))
    if finding.get("recommended_action"):
        compact["recommended_action"] = str(finding.get("recommended_action"))
    return compact


def attach_global_registry_shadow_finding(item: dict[str, Any], finding: dict[str, Any]) -> None:
    shadows = item.setdefault("global_registry_shadow_findings", [])
    if isinstance(shadows, list):
        shadows.append(compact_global_registry_shadow_finding(finding))
    project_asset = item.get("project_asset")
    if not isinstance(project_asset, dict):
        return
    summary = project_asset.setdefault("global_registry_shadow_findings", {"open": 0, "kinds": []})
    if not isinstance(summary, dict):
        return
    summary["open"] = int(summary.get("open") or 0) + 1
    kinds = summary.setdefault("kinds", [])
    kind = str(finding.get("kind") or "global_registry_finding")
    if isinstance(kinds, list) and kind not in kinds:
        kinds.append(kind)


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def resolve_goal_local_path(raw: Any, goal: dict[str, Any], *, fallback_base: Path) -> Path | None:
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    if path.is_absolute():
        return path
    repo = goal.get("repo")
    if repo:
        return Path(str(repo)).expanduser() / path
    return fallback_base / path


def global_registry_finding(
    *,
    kind: str,
    severity: str,
    message: str,
    recommended_action: str,
    goal_id: str | None = None,
    path: Path | None = None,
    goal_ids: list[str] | None = None,
) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "kind": kind,
        "severity": severity,
        "message": message,
        "recommended_action": recommended_action,
    }
    if goal_id:
        finding["goal_id"] = goal_id
    if path:
        finding["path"] = str(path)
    if goal_ids:
        finding["goal_ids"] = goal_ids
    return finding


def collect_global_registry_health(
    *,
    registry_path: Path,
    runtime_root: Path,
    current_registry: dict[str, Any],
) -> dict[str, Any]:
    global_path = global_registry_path(runtime_root)
    if not global_path.exists():
        return {
            "available": False,
            "ok": True,
            "registry": str(global_path),
            "current_registry": str(registry_path),
            "current_registry_is_global": False,
            "summary": {"high": 0, "action": 0, "info": 0, "checks": 0, "findings": 0},
            "findings": [],
            "checks": [],
        }

    global_registry = load_registry(global_path)
    global_goals = registry_goals(global_registry)
    current_goals = registry_goals(current_registry)
    current_ids = {str(goal.get("id")) for goal in current_goals if goal.get("id")}
    global_ids = [str(goal.get("id")) for goal in global_goals if goal.get("id")]
    global_id_set = set(global_ids)
    source_registries: set[str] = set()
    findings: list[dict[str, Any]] = []
    checks: list[str] = []

    current_is_global = same_path(registry_path, global_path)
    id_counts = Counter(global_ids)
    for goal_id, count in sorted(id_counts.items()):
        if count <= 1:
            continue
        findings.append(
            global_registry_finding(
                kind="duplicate_goal_id",
                severity="high",
                goal_id=goal_id,
                message=f"global registry contains {count} entries for `{goal_id}`",
                recommended_action="deduplicate the global registry before trusting multi-project routing",
            )
        )

    for goal in global_goals:
        goal_id = str(goal.get("id") or "unknown-goal")
        source_path = resolve_goal_local_path(goal.get("source_registry"), goal, fallback_base=global_path.parent)
        if source_path:
            source_registries.add(str(source_path))
            if not source_path.exists():
                findings.append(
                    global_registry_finding(
                        kind="source_registry_missing",
                        severity="action",
                        goal_id=goal_id,
                        path=source_path,
                        message=f"`{goal_id}` source registry is missing",
                        recommended_action=f"reconnect `{goal_id}` from its project or archive it if the project is obsolete",
                    )
                )
            else:
                synced_at = parse_timestamp(goal.get("synced_at"))
                if synced_at:
                    source_mtime = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc)
                    if source_mtime > synced_at.astimezone(timezone.utc) + timedelta(seconds=5):
                        findings.append(
                            global_registry_finding(
                                kind="stale_source_registry",
                                severity="action",
                                goal_id=goal_id,
                                path=source_path,
                                message=f"`{goal_id}` source registry changed after its last global sync",
                                recommended_action=(
                                    f"run `loopx sync-global --goal-id {goal_id}` from the source project"
                                ),
                            )
                        )

        state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=global_path.parent)
        if state_path and not state_path.exists():
            findings.append(
                global_registry_finding(
                    kind="state_file_missing",
                    severity="action",
                    goal_id=goal_id,
                    path=state_path,
                    message=f"`{goal_id}` active state file is missing",
                    recommended_action=f"repair `{goal_id}` state_file or reconnect the project",
                )
            )
        if not state_path:
            findings.append(
                global_registry_finding(
                    kind="state_file_not_declared",
                    severity="action",
                    goal_id=goal_id,
                    message=f"`{goal_id}` does not declare a state_file",
                    recommended_action=f"reconnect `{goal_id}` with a durable active goal state file",
                )
            )

    missing_from_current = sorted(global_id_set - current_ids)
    if not current_is_global and missing_from_current:
        shown = missing_from_current[:8]
        findings.append(
            global_registry_finding(
                kind="current_registry_scope_excludes_global_goals",
                severity="info",
                message=f"current registry excludes {len(missing_from_current)} global goal(s)",
                recommended_action=(
                    "for multi-project dashboard/controller status, run `loopx status` "
                    "without `--registry`, pass the global registry, or start `serve-status --global-registry`"
                ),
                goal_ids=shown,
            )
        )

    checks.append(f"global registry goals checked: {len(global_goals)}")
    checks.append(f"global source registries checked: {len(source_registries)}")
    severity_counts = Counter(str(finding.get("severity") or "info") for finding in findings)
    return {
        "available": True,
        "ok": severity_counts.get("high", 0) == 0,
        "registry": str(global_path),
        "current_registry": str(registry_path),
        "current_registry_is_global": current_is_global,
        "global_goal_count": len(global_goals),
        "current_goal_count": len(current_goals),
        "source_registry_count": len(source_registries),
        "summary": {
            "high": severity_counts.get("high", 0),
            "action": severity_counts.get("action", 0),
            "info": severity_counts.get("info", 0),
            "checks": len(checks),
            "findings": len(findings),
        },
        "findings": findings,
        "checks": checks,
    }


def is_status_neutral_run(run: dict[str, Any]) -> bool:
    return (
        str(run.get("classification") or "") in STATUS_NEUTRAL_CLASSIFICATIONS
        or str(run.get("progress_scope") or "") == AGENT_LANE_PROGRESS_SCOPE
    )


def latest_agent_lane_run(goal: dict[str, Any]) -> dict[str, Any] | None:
    runs = goal.get("latest_runs")
    if not isinstance(runs, list):
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("progress_scope") or "") == AGENT_LANE_PROGRESS_SCOPE:
            return run
    return None


def compact_agent_lane_recommendation(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    action = public_safe_compact_text(run.get("recommended_action"), limit=220)
    if not action:
        return None
    compact: dict[str, Any] = {
        "schema_version": "agent_lane_recommendation_v0",
        "progress_scope": AGENT_LANE_PROGRESS_SCOPE,
        "recommended_action": action,
    }
    for field in (
        "agent_id",
        "agent_lane",
        "classification",
        "generated_at",
        "delivery_batch_scale",
        "delivery_outcome",
    ):
        if run.get(field) is not None:
            compact[field] = run.get(field)
    return compact


def latest_run_recommended_action_for_projection(
    *,
    current_status_run: dict[str, Any] | None,
    agent_lane_recommendation: dict[str, Any] | None,
    active_state_next_action: Any = None,
    limit: int = 320,
) -> tuple[str | None, str | None]:
    latest_action = public_safe_compact_text(
        current_status_run.get("recommended_action")
        if isinstance(current_status_run, dict)
        else None,
        limit=limit,
    )
    if not isinstance(agent_lane_recommendation, dict):
        return latest_action, "latest_status_run" if latest_action else None

    lane_action = public_safe_compact_text(
        agent_lane_recommendation.get("recommended_action"),
        limit=limit,
    )
    if not lane_action:
        return latest_action, "latest_status_run" if latest_action else None
    if not active_state_next_action or not actions_are_projection_aligned(
        active_state_next_action,
        lane_action,
    ):
        return latest_action, "latest_status_run" if latest_action else None

    latest_aligned = bool(
        latest_action
        and actions_are_projection_aligned(active_state_next_action, latest_action)
    )
    lane_dt = parse_timestamp(agent_lane_recommendation.get("generated_at"))
    latest_dt = parse_timestamp(
        current_status_run.get("generated_at")
        if isinstance(current_status_run, dict)
        else None
    )
    lane_is_newer = bool(lane_dt and latest_dt and lane_dt >= latest_dt)
    if not latest_action or not latest_aligned or lane_is_newer:
        return lane_action, "agent_lane_recommendation"
    return latest_action, "latest_status_run"


def latest_run(goal: dict[str, Any]) -> dict[str, Any] | None:
    status_run = goal.get("latest_status_run")
    if isinstance(status_run, dict) and not is_status_neutral_run(status_run):
        return status_run

    runs = goal.get("latest_runs")
    if not isinstance(runs, list) or not runs:
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if is_status_neutral_run(run):
            continue
        return run
    return None


def ordered_lifecycle_flags(flags: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped = [flag for flag in flags if flag and not (flag in seen or seen.add(flag))]
    priority = {phase: index for index, phase in enumerate(LIFECYCLE_PRIORITY)}
    return sorted(deduped, key=lambda phase: priority.get(phase, len(priority)))


def primary_lifecycle_phase(flags: list[str], fallback: str = "registered") -> str:
    ordered = ordered_lifecycle_flags(flags)
    return ordered[0] if ordered else fallback


def run_lifecycle_flags(run: dict[str, Any] | None) -> list[str]:
    if not isinstance(run, dict):
        return []

    flags: list[str] = []
    classification = str(run.get("classification") or "")
    if classification == "state_refreshed":
        flags.append("refreshed")
    elif classification == "read_only_project_map" or isinstance(run.get("project_map"), dict):
        flags.append("mapped")
    elif classification:
        flags.append("adapter_inspected")
    else:
        flags.append("run_recorded")

    if compact_human_reward(run.get("human_reward")):
        flags.append("reward_judged")

    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        if operator_gate.get("decision") == "approve":
            flags.append("operator_approved")
        else:
            flags.append("operator_gated")

    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        if readiness.get("decision_advisor_ready") or readiness.get("write_controller_ready"):
            flags.append("controller_ready")
        elif readiness.get("read_only_observer_ready") or readiness.get("classification"):
            flags.append("controller_gated")

    return ordered_lifecycle_flags(flags)


def run_lifecycle_phase(run: dict[str, Any] | None) -> str:
    return primary_lifecycle_phase(run_lifecycle_flags(run), fallback="run_recorded")


def goal_lifecycle_fields(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any]:
    if current_run:
        flags = run_lifecycle_flags(current_run)
        return {
            "lifecycle_phase": primary_lifecycle_phase(flags),
            "lifecycle_flags": flags,
        }

    adapter_status = str(goal.get("adapter_status") or "")
    status = str(goal.get("status") or "")
    flags: list[str]
    if adapter_status in CONNECTED_ADAPTER_STATUSES:
        flags = ["connected"]
    elif "planned" in status or adapter_status == "planned":
        flags = ["planned"]
    else:
        flags = ["registered"]
    flags = ordered_lifecycle_flags(flags)
    return {
        "lifecycle_phase": primary_lifecycle_phase(flags),
        "lifecycle_flags": flags,
    }


def readiness_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if not readiness:
        return {}
    fields: dict[str, Any] = {}
    if readiness.get("classification"):
        fields["controller_stage"] = readiness.get("classification")
    missing = readiness.get("missing_gates")
    if isinstance(missing, list):
        public_missing = [str(gate) for gate in missing if gate]
        if public_missing:
            fields["missing_gates"] = public_missing
    if readiness.get("next_handoff_condition"):
        fields["next_handoff_condition"] = readiness.get("next_handoff_condition")
    return fields


def operator_gate_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(run, dict):
        return {}
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if not operator_gate:
        return {}
    fields: dict[str, Any] = {}
    if operator_gate.get("decision") != "approve" and operator_gate.get("operator_question"):
        fields["operator_question"] = normalize_operator_question(
            str(operator_gate.get("operator_question") or ""),
            goal_id=str(run.get("goal_id") or ""),
            gate=str(operator_gate.get("gate") or DEFAULT_OPERATOR_GATE),
        )
    if operator_gate.get("decision") == "approve" and operator_gate.get("agent_command"):
        fields["agent_command"] = operator_gate.get("agent_command")
    if operator_gate.get("follow_up"):
        fields["next_handoff_condition"] = operator_gate.get("follow_up")
    return fields


def compact_server_planning_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    compact: dict[str, Any] = {}
    for field in ("schema_version", "lane", "authority"):
        text = public_safe_compact_text(value.get(field), limit=120)
        if text:
            compact[field] = text
    for field in (
        "may_rank_candidate_todos",
        "may_suggest_evidence_probes",
        "may_emit_refactor_warnings",
        "may_execute_protected_actions",
        "may_read_private_material",
        "may_mutate_active_state",
        "may_append_delivery_history",
        "may_spend_delivery_quota",
        "promotion_required",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    for field in ("promotion_requirements", "allowed_outputs", "forbidden_outputs"):
        items = public_safe_compact_list(value.get(field), limit=8)
        if items:
            compact[field] = items
    return compact


def compact_dreaming_proposal(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    classification = str(run.get("classification") or "")
    if classification not in DREAMING_ADVISORY_CLASSIFICATIONS:
        return None
    raw = run.get("dreaming") if isinstance(run.get("dreaming"), dict) else {}
    proposal: dict[str, Any] = {
        "schema_version": "dreaming_proposal_v0",
        "classification": classification,
        "advisory": True,
        "promoted_to_delivery": False,
        "execution_allowed": False,
        "delivery_spend_allowed": False,
    }
    for key in ("proposal_id", "lane", "evidence_window", "proposal_type", "confidence"):
        value = public_safe_compact_text(raw.get(key), limit=80)
        if value:
            proposal[key] = value
    server_planning_contract = compact_server_planning_contract(raw.get("server_planning_contract"))
    if server_planning_contract:
        proposal["server_planning_contract"] = server_planning_contract
    if raw.get("requires_project_controller") is not None:
        proposal["requires_project_controller"] = bool(raw.get("requires_project_controller"))
    question = public_safe_compact_text(
        run.get("operator_question") or raw.get("operator_question"),
        limit=220,
    )
    if question:
        proposal["operator_question"] = question
    return proposal


def compact_dreaming_lane_badge(proposal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(proposal, dict):
        return None
    classification = public_safe_compact_text(proposal.get("classification"), limit=80)
    badge: dict[str, Any] = {
        "schema_version": "dreaming_lane_badge_v0",
        "lane": "dreaming",
        "label": "Dreaming",
        "advisory": bool(proposal.get("advisory", True)),
        "interrupts_delivery": False,
        "review_required": True,
        "execution_allowed": False,
        "delivery_spend_allowed": False,
        "promoted_to_delivery": False,
    }
    if classification:
        badge["status"] = classification
    for field in ("proposal_id", "proposal_type", "confidence", "evidence_window"):
        value = public_safe_compact_text(proposal.get(field), limit=80)
        if value:
            badge[field] = value
    server_contract = proposal.get("server_planning_contract")
    if isinstance(server_contract, dict):
        lane = public_safe_compact_text(server_contract.get("lane"), limit=80)
        authority = public_safe_compact_text(server_contract.get("authority"), limit=120)
        if lane or authority:
            badge["server_planning"] = {
                key: value
                for key, value in {
                    "lane": lane,
                    "authority": authority,
                }.items()
                if value
            }
    return badge


def dreaming_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    proposal = compact_dreaming_proposal(run)
    if not proposal:
        return {}
    fields: dict[str, Any] = {"dreaming_proposal": proposal}
    question = proposal.get("operator_question")
    if question:
        fields["operator_question"] = normalize_operator_question(
            str(question),
            goal_id=str((run or {}).get("goal_id") or ""),
            gate="dreaming_proposal_review",
        )
    return fields


def legacy_runtime_goal_attention(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    readiness_fields: dict[str, Any],
) -> dict[str, Any] | None:
    if not goal.get("legacy_runtime_goal") or not current_run:
        return None

    goal_id = str(goal.get("id") or "unknown-goal")
    json_exists = bool(current_run.get("json_exists"))
    markdown_exists = bool(current_run.get("markdown_exists"))
    classification = str(current_run.get("classification") or "unknown")
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)

    actionable_classification = (
        classification in BLOCKING_CLASSIFICATIONS
        or classification in USER_OR_CONTROLLER_CLASSIFICATIONS
        or classification in CODEX_READY_CLASSIFICATIONS
    )
    if not actionable_classification and json_exists and markdown_exists:
        return None

    if not json_exists or not markdown_exists:
        severity = "high"
        action = (
            "repair this unregistered runtime goal or preview cleanup with "
            f"`loopx archive-runtime --goal-id {goal_id}` before trusting multi-project status"
        )
    elif classification in BLOCKING_CLASSIFICATIONS:
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


def session_runtime_status_waiting_on(value: Any, *, monitor_only: bool = False) -> str:
    waiting_on = str(value or "").strip().lower()
    if waiting_on in {"agent", "codex"}:
        return "codex"
    if waiting_on in {"controller", "human", "operator", "owner", "user", "user_or_controller"}:
        return "user_or_controller"
    if waiting_on in {"runtime", "external_evidence"}:
        return "external_evidence"
    if waiting_on in {"none", "monitor", MONITOR_SIGNAL_WAITING_ON} or monitor_only:
        return MONITOR_SIGNAL_WAITING_ON
    return "codex"


def session_runtime_status_label(projection: dict[str, Any]) -> str:
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
) -> dict[str, Any]:
    first_screen = projection.get("first_screen") if isinstance(projection.get("first_screen"), dict) else {}
    work_lane = projection.get("work_lane_contract") if isinstance(projection.get("work_lane_contract"), dict) else {}
    boundary = projection.get("boundary") if isinstance(projection.get("boundary"), dict) else {}
    monitor_only = bool(work_lane.get("monitor_only"))
    waiting_on = session_runtime_status_waiting_on(
        first_screen.get("waiting_on"),
        monitor_only=monitor_only,
    )
    recommended_action = public_safe_compact_text(
        first_screen.get("recommended_action") or (current_run or {}).get("recommended_action"),
        limit=320,
    ) or "inspect the session-runtime projection and choose the next safe action"
    severity = "watch" if waiting_on in {"external_evidence", MONITOR_SIGNAL_WAITING_ON} else "action"
    if boundary.get("raw_material_detected"):
        severity = "high"
    item = attention_item(
        goal_id=str(goal.get("id") or projection.get("goal_id") or "unknown-goal"),
        status=session_runtime_status_label(projection),
        waiting_on=waiting_on,
        severity=severity,
        recommended_action=recommended_action,
        source="session_runtime_projection",
        **goal_lifecycle_fields(goal, current_run),
    )
    attach_session_runtime_projection(item, projection)
    return item


def goal_attention(goal: dict[str, Any]) -> dict[str, Any] | None:
    goal_id = str(goal.get("id") or "unknown-goal")
    adapter_status = str(goal.get("adapter_status") or "")
    adapter_kind = str(goal.get("adapter_kind") or "")
    current_run = latest_run(goal)
    readiness_fields = readiness_attention_fields(current_run)
    operator_gate_fields = operator_gate_attention_fields(current_run)
    dreaming_fields = dreaming_attention_fields(current_run)
    attention_fields = {**readiness_fields, **operator_gate_fields, **dreaming_fields}
    lifecycle_fields = goal_lifecycle_fields(goal, current_run)

    if goal.get("legacy_runtime_goal"):
        return legacy_runtime_goal_attention(goal, current_run, readiness_fields)

    if not current_run:
        if adapter_status in CONNECTED_ADAPTER_STATUSES:
            return attention_item(
                goal_id=goal_id,
                status="connected_without_run",
                waiting_on="codex",
                severity="action",
                recommended_action="run the first read-only adapter tick and save a compact run record",
                source="run_history",
                **lifecycle_fields,
            )
        if adapter_status == "planned" and adapter_kind.endswith("_read_only_map_v0"):
            command = f"loopx read-only-map --goal-id {goal_id} --dry-run"
            return attention_item(
                goal_id=goal_id,
                status=str(goal.get("status") or "planned"),
                waiting_on="user_or_controller",
                severity="action",
                recommended_action=PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION,
                operator_question=default_operator_question(goal_id, DEFAULT_OPERATOR_GATE),
                agent_command=command,
                source="registry",
                **lifecycle_fields,
            )
        return attention_item(
            goal_id=goal_id,
            status=str(goal.get("status") or "no_run"),
            waiting_on="controller",
            severity="action",
            recommended_action="connect an adapter or run a read-only map before expecting runtime status",
            source="registry",
            **lifecycle_fields,
        )

    json_exists = bool(current_run.get("json_exists"))
    markdown_exists = bool(current_run.get("markdown_exists"))
    if not json_exists or not markdown_exists:
        return attention_item(
            goal_id=goal_id,
            status="run_artifact_missing",
            waiting_on="codex",
            severity="high",
            recommended_action="repair or regenerate the latest run artifacts before trusting status",
            source="run_history",
            **attention_fields,
            **lifecycle_fields,
        )

    session_projection = compact_session_runtime_projection_from_run(current_run)
    if session_projection:
        return session_runtime_projection_attention(goal, current_run, session_projection)

    classification = str(current_run.get("classification") or "unknown")
    action = str(current_run.get("recommended_action") or "inspect the latest run and choose one next action")
    registry_waiting_on = str(goal.get("waiting_on") or "")
    if registry_waiting_on in REGISTRY_WAITING_ON_OVERRIDES:
        registry_attention_fields = dict(attention_fields)
        if goal.get("operator_question"):
            registry_attention_fields["operator_question"] = normalize_operator_question(
                str(goal.get("operator_question") or ""),
                goal_id=goal_id,
                gate=str(goal.get("operator_gate") or DEFAULT_OPERATOR_GATE),
            )
        if goal.get("next_handoff_condition"):
            registry_attention_fields["next_handoff_condition"] = str(goal.get("next_handoff_condition") or "")
        return attention_item(
            goal_id=goal_id,
            status=str(goal.get("attention_status") or classification),
            waiting_on=registry_waiting_on,
            severity="watch" if registry_waiting_on == "external_evidence" else "action",
            recommended_action=str(goal.get("recommended_action") or action),
            source="registry",
            **registry_attention_fields,
            **lifecycle_fields,
        )
    if classification in BLOCKING_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="user_or_controller",
            severity="high",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if classification in USER_OR_CONTROLLER_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="user_or_controller",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if classification in CODEX_READY_CLASSIFICATIONS:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="codex",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if adapter_status in CONNECTED_DELIVERY_ADAPTER_STATUSES:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="codex",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if run_has_external_evidence_watch_signal(current_run):
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="external_evidence",
            severity="watch",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    if adapter_status in CONNECTED_ADAPTER_STATUSES:
        return attention_item(
            goal_id=goal_id,
            status=classification,
            waiting_on="codex",
            severity="action",
            recommended_action=action,
            source="latest_run",
            **attention_fields,
            **lifecycle_fields,
        )
    return None


def build_task_graph_projection(
    item: dict[str, Any],
    *,
    goal: dict[str, Any],
    goal_latest_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    return _build_task_graph_projection_read_model(
        item,
        goal=goal,
        goal_latest_runs=goal_latest_runs,
        public_safe_compact_text=public_safe_compact_text,
        normalize_todo_status=normalize_todo_status,
        todo_done_for_status=todo_done_for_status,
        todo_status_open=TODO_STATUS_OPEN,
        open_todo_items=open_todo_items,
        max_status_todos_per_role=MAX_STATUS_TODOS_PER_ROLE,
        todo_item_task_class=todo_item_task_class,
        user_gate_task_class=TODO_TASK_CLASS_USER_GATE,
        todo_summary_open_count=todo_summary_open_count,
        latest_run=latest_run,
    )

def attach_goal_channel_projection(
    item: dict[str, Any],
    *,
    goal: dict[str, Any],
    goal_latest_runs: list[dict[str, Any]],
) -> None:
    """Attach a read-only frontstage projection to a status attention item."""

    run_history_goal = dict(goal)
    run_history_goal["latest_runs"] = goal_latest_runs
    quota_payload: dict[str, Any] = {
        "status": item.get("status"),
        "waiting_on": item.get("waiting_on"),
        "recommended_action": item.get("recommended_action"),
    }
    if isinstance(item.get("quota"), dict):
        quota_payload["quota"] = item["quota"]
    item["goal_channel_projection"] = build_goal_channel_projection(
        goal_id=str(item.get("goal_id") or goal.get("id") or ""),
        status_item=item,
        quota_payload=quota_payload,
        run_history_goal=run_history_goal,
    )


def build_attention_queue(
    *,
    contract: dict[str, Any],
    history: dict[str, Any],
    global_registry: dict[str, Any],
    runtime_root: Path | None = None,
    include_task_graph: bool = False,
    goal_id_filter: str | None = None,
) -> dict[str, Any]:
    health_items: list[dict[str, Any]] = []
    history_items: list[dict[str, Any]] = []
    if contract.get("ok") is False:
        health_items.append(
            attention_item(
                goal_id="loopx-contract",
                status="contract_check_failed",
                waiting_on="codex",
                severity="high",
                recommended_action="fix contract errors before advancing goal adapters",
                source="contract",
            )
        )

    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        active_state_fields: dict[str, Any] | None = None
        active_state_item: dict[str, Any] | None = None
        current_status_run = latest_run(goal)
        goal_latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
        if goal.get("registry_member"):
            active_state_fields = active_state_todo_fields(goal, runtime_root=runtime_root)
            active_state_item = active_state_todo_attention_item(goal, active_state_fields, current_status_run)
        if active_state_item and active_state_item.get("waiting_on") in {"controller", "user_or_controller"}:
            item = active_state_item
        else:
            item = goal_attention(goal)
            if not item:
                item = active_state_item
        if item:
            agent_lane_recommendation = compact_agent_lane_recommendation(
                latest_agent_lane_run(goal)
            )
            active_state_next_action = (
                active_state_fields.get("active_state_next_action")
                if isinstance(active_state_fields, dict)
                else None
            )
            latest_run_action, latest_run_action_source = latest_run_recommended_action_for_projection(
                current_status_run=current_status_run,
                agent_lane_recommendation=agent_lane_recommendation,
                active_state_next_action=active_state_next_action,
            )
            if latest_run_action:
                item["latest_run_recommended_action"] = latest_run_action
                if latest_run_action_source:
                    item["latest_run_recommended_action_source"] = latest_run_action_source
                if isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["latest_run_recommended_action"] = latest_run_action
                    if latest_run_action_source:
                        item["project_asset"][
                            "latest_run_recommended_action_source"
                        ] = latest_run_action_source
            replan_ack = compact_autonomous_replan_ack(
                current_status_run
            ) or latest_autonomous_replan_ack_for_projection(goal_latest_runs)
            if replan_ack:
                item["autonomous_replan_ack"] = replan_ack
                if isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["autonomous_replan_ack"] = replan_ack
            control_plane = compact_control_plane_policy(goal.get("control_plane"))
            if control_plane:
                item["control_plane"] = control_plane
            if agent_lane_recommendation:
                item["agent_lane_recommendation"] = agent_lane_recommendation
            subagent_activity = subagent_activity_for_goal(goal)
            interface_budget_cadence = interface_budget_cadence_for_runs(goal_latest_runs)
            projection_warning = active_state_projection_warning(goal, latest_run(goal))
            enrich_project_asset(
                item,
                latest_validation=project_asset_latest_validation(latest_run(goal)),
                latest_runs=goal_latest_runs,
                execution_profile=(
                    goal.get("execution_profile")
                    if isinstance(goal.get("execution_profile"), dict)
                    else None
                ),
                orchestration=(
                    goal.get("spawn_policy")
                    if isinstance(goal.get("spawn_policy"), dict)
                    else None
                ),
                subagent_activity=subagent_activity,
                interface_budget_cadence=interface_budget_cadence,
            )
            if control_plane and isinstance(item.get("project_asset"), dict):
                item["project_asset"]["control_plane"] = control_plane
            if agent_lane_recommendation and isinstance(item.get("project_asset"), dict):
                item["project_asset"]["agent_lane_recommendation"] = agent_lane_recommendation
            if projection_warning:
                item["stale_latest_run_warning"] = projection_warning
                if isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["stale_latest_run_warning"] = projection_warning
            if goal.get("registry_member"):
                if active_state_fields is None:
                    active_state_fields = active_state_todo_fields(goal, runtime_root=runtime_root)
                item.update(active_state_fields)
                if isinstance(item.get("project_asset"), dict):
                    active_next_action = item.get("active_state_next_action")
                    if active_next_action:
                        item["project_asset"]["active_state_next_action"] = active_next_action
                    issue_meta_surface = (
                        item.get("issue_meta_surface")
                        if isinstance(item.get("issue_meta_surface"), dict)
                        else None
                    )
                    if issue_meta_surface:
                        item["project_asset"]["issue_meta_surface"] = issue_meta_surface
                    next_action_warning = next_action_projection_warning(
                        active_state_next_action=active_next_action,
                        latest_run_recommended_action=item.get("latest_run_recommended_action"),
                    )
                    if next_action_warning:
                        item["next_action_projection_warning"] = next_action_warning
                        item["project_asset"]["next_action_projection_warning"] = next_action_warning
                sync_connected_attention_action_from_todos(item)
                backlog_warning = (
                    item.get("backlog_hygiene_warning")
                    if isinstance(item.get("backlog_hygiene_warning"), dict)
                    else None
                )
                if backlog_warning and isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["backlog_hygiene_warning"] = backlog_warning
                projection_gap = (
                    item.get("state_projection_gap")
                    if isinstance(item.get("state_projection_gap"), dict)
                    else None
                )
                if projection_gap and isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["state_projection_gap"] = projection_gap
                archive_warning = (
                    item.get("completed_todo_archive_warning")
                    if isinstance(item.get("completed_todo_archive_warning"), dict)
                    else None
                )
                if archive_warning and isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["completed_todo_archive_warning"] = archive_warning
                replan_obligation = (
                    item.get("autonomous_replan_obligation")
                    if isinstance(item.get("autonomous_replan_obligation"), dict)
                    else None
                )
                if not replan_obligation:
                    replan_obligation = autonomous_replan_obligation_from_runs(
                        goal_latest_runs,
                        agent_todos=item.get("agent_todos")
                        if isinstance(item.get("agent_todos"), dict)
                        else None,
                    )
                    if replan_obligation:
                        item["autonomous_replan_obligation"] = replan_obligation
                if replan_obligation and isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["autonomous_replan_obligation"] = replan_obligation
                item["quota"] = quota_status(
                    goal,
                    waiting_on=str(item.get("waiting_on") or ""),
                    severity=str(item.get("severity") or ""),
                    lifecycle_phase=item.get("lifecycle_phase"),
                    lifecycle_flags=item.get("lifecycle_flags"),
                    status=item.get("status"),
                )
                enrich_project_asset(
                    item,
                    user_todos=item.get("user_todos") if isinstance(item.get("user_todos"), dict) else None,
                    agent_todos=item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None,
                    quota=item.get("quota") if isinstance(item.get("quota"), dict) else None,
                    latest_runs=goal_latest_runs,
                    subagent_activity=subagent_activity,
                    interface_budget_cadence=interface_budget_cadence,
                )
                guarded_quota = quota_with_handoff_outcome_floor(
                    item.get("quota") if isinstance(item.get("quota"), dict) else {},
                    waiting_on=str(item.get("waiting_on") or ""),
                    project_asset=item.get("project_asset")
                    if isinstance(item.get("project_asset"), dict)
                    else None,
                    handoff_readiness=item.get("handoff_readiness")
                    if isinstance(item.get("handoff_readiness"), dict)
                    else None,
                )
                if guarded_quota != item.get("quota"):
                    item["quota"] = guarded_quota
                    enrich_project_asset(
                        item,
                        user_todos=item.get("user_todos") if isinstance(item.get("user_todos"), dict) else None,
                        agent_todos=item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None,
                        quota=guarded_quota,
                        latest_runs=goal_latest_runs,
                        subagent_activity=subagent_activity,
                        interface_budget_cadence=interface_budget_cadence,
                    )
                normalize_monitor_quiet_attention_display(item)
            if include_task_graph:
                task_graph_projection = build_task_graph_projection(
                    item,
                    goal=goal,
                    goal_latest_runs=goal_latest_runs,
                )
                if task_graph_projection:
                    item["task_graph_projection"] = task_graph_projection
            attach_goal_channel_projection(
                item,
                goal=goal,
                goal_latest_runs=goal_latest_runs,
            )
            history_items.append(item)

    live_quota_items_by_goal: dict[str, list[dict[str, Any]]] = {}
    for item in history_items:
        if isinstance(item.get("quota"), dict):
            live_quota_items_by_goal.setdefault(str(item.get("goal_id") or ""), []).append(item)

    for finding in global_registry.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        if finding.get("severity") not in {"high", "action"}:
            continue
        goal_id = str(finding.get("goal_id") or "global-registry")
        if goal_id_filter:
            finding_goal_ids = [
                str(item)
                for item in (finding.get("goal_ids") or [])
                if str(item or "").strip()
            ]
            if goal_id != goal_id_filter and goal_id_filter not in finding_goal_ids:
                continue
        live_items = live_quota_items_by_goal.get(goal_id, [])
        if finding.get("kind") in SOURCE_REGISTRY_SHADOW_FINDINGS and live_items:
            for item in live_items:
                attach_global_registry_shadow_finding(item, finding)
            continue
        health_items.append(
            attention_item(
                goal_id=goal_id,
                status=str(finding.get("kind") or "global_registry_finding"),
                waiting_on="codex",
                severity=str(finding.get("severity") or "action"),
                recommended_action=str(finding.get("recommended_action") or "inspect global registry health"),
                source="global_registry",
            )
        )

    items = [*health_items, *history_items]
    attach_dependency_blockers(items)
    backlog_candidates = autonomous_backlog_candidates(items)
    monitor_candidates = autonomous_monitor_candidates(items)

    queue = {
        "available": True,
        "item_count": len(items),
        "needs_user_or_controller": sum(
            1 for item in items if item["waiting_on"] in {"user_or_controller", "controller"}
        ),
        "needs_controller": sum(1 for item in items if item["waiting_on"] == "controller"),
        "needs_codex": sum(1 for item in items if item["waiting_on"] == "codex"),
        "watching_external_evidence": sum(1 for item in items if item["waiting_on"] == "external_evidence"),
        "watching_monitor": sum(1 for item in items if item["waiting_on"] == MONITOR_SIGNAL_WAITING_ON),
        "items": items,
    }
    if goal_id_filter:
        queue["goal_filter"] = goal_id_filter
        queue["goal_filter_applied"] = True
    if backlog_candidates:
        queue["autonomous_backlog_candidates"] = backlog_candidates
    if monitor_candidates:
        queue["autonomous_monitor_candidates"] = monitor_candidates
    return queue


def compact_human_reward(reward: Any) -> dict[str, Any] | None:
    if not isinstance(reward, dict):
        return None
    compact = {field: reward[field] for field in HUMAN_REWARD_COMPACT_FIELDS if field in reward}
    lesson = compact.get("lesson")
    if isinstance(lesson, dict):
        compact["lesson"] = {
            field: lesson[field]
            for field in ("schema_version", "kind", "summary", "avoid", "prefer")
            if field in lesson
        }
    return compact or None


def compact_operator_gate(operator_gate: Any) -> dict[str, Any] | None:
    if not isinstance(operator_gate, dict):
        return None
    compact = {field: operator_gate[field] for field in OPERATOR_GATE_COMPACT_FIELDS if field in operator_gate}
    return compact or None


def compact_operator_gate_resume_contract(contract: Any) -> dict[str, Any] | None:
    if not isinstance(contract, dict):
        return None
    compact = {
        field: contract[field]
        for field in OPERATOR_GATE_RESUME_CONTRACT_COMPACT_FIELDS
        if field in contract
    }
    interrupt = contract.get("interrupt_payload") if isinstance(contract.get("interrupt_payload"), dict) else {}
    if interrupt:
        compact["interrupt_payload"] = {
            field: interrupt[field]
            for field in ("question", "choices")
            if field in interrupt
        }
    return compact or None


def compact_controller_readiness(readiness: Any) -> dict[str, Any] | None:
    if not isinstance(readiness, dict):
        return None
    compact = {
        field: readiness[field]
        for field in CONTROLLER_READINESS_COMPACT_FIELDS
        if field in readiness
    }
    gates = []
    for gate in readiness.get("gates") or []:
        if not isinstance(gate, dict):
            continue
        gates.append({field: gate[field] for field in CONTROLLER_READINESS_GATE_FIELDS if field in gate})
    if gates:
        compact["gates"] = gates
    return compact or None


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    compact = {field: run[field] for field in RUN_COMPACT_FIELDS if field in run}
    flags = run_lifecycle_flags(run)
    compact.setdefault("lifecycle_phase", primary_lifecycle_phase(flags, fallback="run_recorded"))
    compact.setdefault("lifecycle_flags", flags)
    reward = compact_human_reward(run.get("human_reward"))
    if reward:
        compact["human_reward"] = reward
    operator_gate = compact_operator_gate(run.get("operator_gate"))
    if operator_gate:
        compact["operator_gate"] = operator_gate
    replan_ack = compact_autonomous_replan_ack(run)
    if replan_ack:
        compact["autonomous_replan_ack"] = replan_ack
    resume_contract = compact_operator_gate_resume_contract(run.get("operator_gate_resume_contract"))
    if resume_contract:
        compact["operator_gate_resume_contract"] = resume_contract
    readiness = compact_controller_readiness(run.get("controller_readiness"))
    if readiness:
        compact["controller_readiness"] = readiness
    merge_decision = public_safe_compact_text(run.get("merge_decision"), limit=240)
    if merge_decision:
        compact["merge_decision"] = merge_decision
    subagents = [
        child
        for child in (
            compact_subagent_run(
                child_run,
                parent_goal_id=str(run.get("goal_id") or ""),
                parent_run_id=str(run.get("run_id") or run.get("generated_at") or ""),
            )
            for child_run in (run.get("subagents") or [])
            if isinstance(child_run, dict)
        )
        if child
    ]
    if subagents:
        compact["subagents"] = subagents[:MAX_SUBAGENT_ACTIVITY_ITEMS]
        compact["subagent_count"] = len(subagents)
    benchmark_run = compact_benchmark_run(run)
    if benchmark_run:
        compact["benchmark_run_summary"] = benchmark_run
        health_note = worker_bridge_ingest_health_note(benchmark_run)
        if health_note:
            compact["worker_bridge_ingest_health_note"] = health_note
    benchmark_result = compact_benchmark_result(run)
    if benchmark_result:
        compact["benchmark_result_summary"] = benchmark_result
    benchmark_comparison = compact_benchmark_comparison(run)
    if benchmark_comparison:
        compact["benchmark_comparison_summary"] = benchmark_comparison
        decision_note = benchmark_comparison_decision_note(benchmark_comparison)
        if decision_note:
            compact["benchmark_comparison_decision_note"] = decision_note
    benchmark_learning_ledger = compact_benchmark_learning_ledger(run)
    if benchmark_learning_ledger:
        compact["benchmark_learning_ledger_summary"] = benchmark_learning_ledger
    benchmark_report = compact_benchmark_experiment_report(run)
    if benchmark_report:
        compact["benchmark_experiment_report_summary"] = benchmark_report
        readiness_note = benchmark_experiment_report_readiness_note(benchmark_report)
        if readiness_note:
            compact["benchmark_experiment_report_readiness_note"] = readiness_note
            replay_decision = benchmark_experiment_report_replay_decision(readiness_note)
            if replay_decision:
                compact["benchmark_experiment_report_replay_decision"] = replay_decision
    active_user_pilot = compact_active_user_assisted_pilot(run)
    if active_user_pilot:
        compact["active_user_assisted_pilot_summary"] = active_user_pilot
    session_projection = compact_session_runtime_projection_from_run(run)
    if session_projection:
        compact["session_runtime_projection"] = session_projection
    return compact


def build_run_history(history: dict[str, Any], *, display_limit: int | None = None) -> dict[str, Any]:
    display_limit = None if display_limit is None else max(0, display_limit)
    goals: list[dict[str, Any]] = []
    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        current_run = latest_run(goal)
        lifecycle_fields = goal_lifecycle_fields(goal, current_run)
        subagent_activity = subagent_activity_for_goal(goal)
        latest_runs = [
            compact_run(run)
            for run in goal.get("latest_runs") or []
            if isinstance(run, dict)
        ]
        if display_limit is not None:
            latest_runs = latest_runs[:display_limit]
        goals.append(
            {
                "id": goal.get("id"),
                "domain": goal.get("domain"),
                "status": goal.get("status"),
                "lifecycle_phase": lifecycle_fields["lifecycle_phase"],
                "lifecycle_flags": lifecycle_fields["lifecycle_flags"],
                "registry_member": goal.get("registry_member"),
                "legacy_runtime_goal": goal.get("legacy_runtime_goal"),
                "adapter_kind": goal.get("adapter_kind"),
                "adapter_status": goal.get("adapter_status"),
                "coordination": goal.get("coordination") if isinstance(goal.get("coordination"), dict) else None,
                "guards": goal.get("guards") if isinstance(goal.get("guards"), list) else [],
                "next_probe": goal.get("next_probe"),
                "authority_registry": goal.get("authority_registry"),
                "quota": quota_status(goal) if goal.get("registry_member") else None,
                "index_exists": goal.get("index_exists"),
                "raw_index_records": goal.get("raw_index_records"),
                "unique_runs": goal.get("unique_runs"),
                "subagent_activity": subagent_activity,
                "latest_status_run": compact_run(current_run) if current_run else None,
                "latest_runs": latest_runs,
            }
        )

    recent_runs = [
        compact_run(run)
        for run in history.get("runs") or []
        if isinstance(run, dict)
    ]
    if display_limit is not None:
        recent_runs = recent_runs[:display_limit]
    return {
        "available": True,
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "goals": goals,
        "recent_runs": recent_runs,
    }


def quota_spend_slots(run: dict[str, Any]) -> int:
    classification = str(run.get("classification") or "")
    if classification not in {"quota_slot_spent", "quota_slot_voided"}:
        return 0
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    raw_slots = quota_event.get("slots", 1)
    try:
        slots = max(0, int(raw_slots))
    except (TypeError, ValueError):
        slots = 1
    if classification == "quota_slot_voided" or str(quota_event.get("event_type") or "") == "quota_slot_voided":
        return -slots
    return slots


def is_automation_run(run: dict[str, Any]) -> bool:
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    source = str(quota_event.get("source") or run.get("source") or "").lower()
    if source in {"heartbeat", "automation", "cron"}:
        return True
    if "heartbeat" in source or "automation" in source:
        return True
    return str(run.get("classification") or "") in {"quota_slot_spent", "quota_slot_voided"}


def is_progress_signal_run(run: dict[str, Any]) -> bool:
    classification = str(run.get("classification") or "")
    return bool(classification and classification not in {"quota_slot_spent", "quota_slot_voided", "state_refreshed"})


def blank_usage_goal(goal_id: str) -> dict[str, Any]:
    return {
        "goal_id": goal_id,
        "runs_24h": 0,
        "runs_7d": 0,
        "quota_spend_slots_24h": 0,
        "quota_spend_slots_7d": 0,
        "automation_run_count_24h": 0,
        "automation_run_count_7d": 0,
        "progress_signal_run_count_24h": 0,
        "progress_signal_run_count_7d": 0,
        "project_share_24h": 0.0,
    }


def blank_event_class_counts() -> dict[str, int]:
    return {event_class: 0 for event_class in EVENT_LEDGER_CLASSES}


def blank_event_ledger_goal(goal_id: str) -> dict[str, Any]:
    return {
        "goal_id": goal_id,
        "events_24h": 0,
        "events_7d": 0,
        "benchmark_runs_24h": 0,
        "benchmark_runs_7d": 0,
        "by_class_24h": blank_event_class_counts(),
        "by_class_7d": blank_event_class_counts(),
        "latest_event_class": None,
        "latest_event_at": None,
        "latest_benchmark_run": None,
    }


def event_ledger_event_class(run: dict[str, Any]) -> str:
    classification = str(run.get("classification") or "").lower()
    if classification == "quota_slot_spent" or isinstance(run.get("quota_event"), dict):
        return "accounting"
    if (
        compact_benchmark_run(run)
        or compact_benchmark_result(run)
        or compact_benchmark_comparison(run)
        or compact_benchmark_learning_ledger(run)
        or compact_benchmark_experiment_report(run)
        or compact_active_user_assisted_pilot(run)
    ):
        return "evidence"
    if (
        classification in EVENT_LEDGER_DECISION_CLASSIFICATIONS
        or "operator_gate" in classification
        or "human_reward" in classification
        or "reward" in classification
        or isinstance(run.get("human_reward"), dict)
        or isinstance(run.get("operator_gate"), dict)
        or isinstance(run.get("operator_gate_resume_contract"), dict)
    ):
        return "decision"
    if classification in EVENT_LEDGER_EVIDENCE_CLASSIFICATIONS:
        return "evidence"
    if run_has_external_evidence_watch_signal(run):
        return "evidence"
    if any(hint in classification for hint in EVENT_LEDGER_EVIDENCE_HINTS):
        return "evidence"
    if any(
        key in run
        for key in (
            "active_priorities",
            "active_task_count",
            "artifact",
            "artifacts",
            "cache_check",
            "controller_readiness",
            "project_map",
        )
    ):
        return "evidence"
    if classification in EVENT_LEDGER_STATE_CLASSIFICATIONS or classification.endswith("_refreshed"):
        return "state"
    return "work"


def build_event_ledger_summary(history: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    totals = {
        "events_24h": 0,
        "events_7d": 0,
        "benchmark_runs_24h": 0,
        "benchmark_runs_7d": 0,
        "by_class_24h": blank_event_class_counts(),
        "by_class_7d": blank_event_class_counts(),
    }
    goals: dict[str, dict[str, Any]] = {}
    sample_count = 0

    for run in history.get("runs") or []:
        if not isinstance(run, dict):
            continue
        sample_count += 1
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        event_class = event_ledger_event_class(run)
        goal_id = str(run.get("goal_id") or "unknown-goal")
        goal = goals.setdefault(goal_id, blank_event_ledger_goal(goal_id))
        latest_event_at = parse_timestamp(goal.get("latest_event_at"))
        if latest_event_at is None or generated_at > latest_event_at:
            goal["latest_event_class"] = event_class
            goal["latest_event_at"] = generated_at.isoformat()
        benchmark_run = compact_benchmark_run(run)
        if benchmark_run:
            latest_benchmark_at = parse_timestamp(
                (goal.get("latest_benchmark_run") or {}).get("generated_at")
                if isinstance(goal.get("latest_benchmark_run"), dict)
                else None
            )
            if latest_benchmark_at is None or generated_at > latest_benchmark_at:
                goal["latest_benchmark_run"] = {
                    "generated_at": generated_at.isoformat(),
                    "classification": run.get("classification"),
                    **benchmark_run,
                }

        if generated_at >= cutoff_7d:
            totals["events_7d"] += 1
            totals["by_class_7d"][event_class] += 1
            goal["events_7d"] += 1
            goal["by_class_7d"][event_class] += 1
            if benchmark_run:
                totals["benchmark_runs_7d"] += 1
                goal["benchmark_runs_7d"] += 1
        if generated_at >= cutoff_24h:
            totals["events_24h"] += 1
            totals["by_class_24h"][event_class] += 1
            goal["events_24h"] += 1
            goal["by_class_24h"][event_class] += 1
            if benchmark_run:
                totals["benchmark_runs_24h"] += 1
                goal["benchmark_runs_24h"] += 1

    goal_rows = sorted(
        goals.values(),
        key=lambda item: (
            item["events_24h"],
            item["events_7d"],
            item["goal_id"],
        ),
        reverse=True,
    )
    return {
        "available": True,
        "source": "run_history",
        "generated_at": now.isoformat(),
        "sample_run_count": sample_count,
        "proxy_note": EVENT_LEDGER_PROXY_NOTE,
        "event_classes": list(EVENT_LEDGER_CLASSES),
        "totals": totals,
        "goals": goal_rows,
    }


def build_promotion_readiness_summary(
    history: dict[str, Any],
    *,
    runtime_root: Path | None = None,
    goal_id_filter: str | None = None,
) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    latest_at: datetime | None = None
    sample_count = 0
    source = "run_history"
    for run in history.get("runs") or []:
        if not isinstance(run, dict):
            continue
        classification = str(run.get("classification") or "")
        if classification not in PROMOTION_READINESS_CLASSIFICATIONS:
            continue
        sample_count += 1
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        if latest_at is None or generated_at > latest_at:
            latest_at = generated_at
            latest = run

    if latest is None and runtime_root is not None:
        full_scan_latest = latest_promotion_readiness_event(
            runtime_root,
            goal_id=goal_id_filter,
        )
        if full_scan_latest.get("available"):
            latest = full_scan_latest
            source = "run_history_full_scan"

    if latest is None:
        readiness = add_promotion_readiness_freshness(
            {
                "available": False,
                "source": source,
                "reason": (
                    "no canary promotion readiness run found in full run history"
                    if runtime_root is not None
                    else "no canary promotion readiness run found in sampled history"
                ),
            }
        )
    else:
        readiness = add_promotion_readiness_freshness(
            {
                "available": True,
                "source": source,
                "goal_id": latest.get("goal_id"),
                "generated_at": latest.get("generated_at"),
                "classification": latest.get("classification"),
                "delivery_batch_scale": latest.get("delivery_batch_scale"),
                "delivery_outcome": latest.get("delivery_outcome"),
                "recommended_action": latest.get("recommended_action"),
                "json_exists": bool(latest.get("json_exists")),
                "markdown_exists": bool(latest.get("markdown_exists")),
            }
        )
    readiness.update(
        {
            "sample_run_count": sample_count,
            "proxy_note": PROMOTION_READINESS_PROXY_NOTE,
            "freshness_window_hours": PROMOTION_READINESS_FRESHNESS_HOURS,
        }
    )
    return readiness


def build_status_contract() -> dict[str, Any]:
    return {
        "schema_version": STATUS_CONTRACT_SCHEMA_VERSION,
        "minimum_dashboard_schema_version": MINIMUM_DASHBOARD_STATUS_CONTRACT_SCHEMA_VERSION,
        "producer": "loopx status",
        "reload_hint": STATUS_CONTRACT_RELOAD_HINT,
    }


def _compact_status_contract_signals(
    value: Any,
    *,
    limit: int = STATUS_CONTRACT_SIGNAL_LIMIT,
) -> dict[str, Any]:
    items = [str(item).strip() for item in value or [] if str(item).strip()]
    bounded = items[: max(0, limit)]
    return {
        "items": bounded,
        "total_count": len(items),
        "truncated": len(items) > len(bounded),
    }


def build_contract_health_projection(contract: dict[str, Any]) -> dict[str, Any]:
    errors = _compact_status_contract_signals(contract.get("errors"))
    warnings = _compact_status_contract_signals(contract.get("warnings"))
    return {
        "contract_summary": contract.get("summary"),
        "contract_errors": errors["items"],
        "contract_errors_total_count": errors["total_count"],
        "contract_errors_truncated": errors["truncated"],
        "contract_warnings": warnings["items"],
        "contract_warnings_total_count": warnings["total_count"],
        "contract_warnings_truncated": warnings["truncated"],
    }


def decision_event_kinds(run: dict[str, Any]) -> list[str]:
    kinds: list[str] = []
    if isinstance(run.get("human_reward"), dict):
        kinds.append("human_reward")
    if isinstance(run.get("operator_gate"), dict):
        kinds.append("operator_gate")
    if isinstance(run.get("operator_gate_resume_contract"), dict):
        kinds.append("operator_gate_resume_contract")

    classification = str(run.get("classification") or "").lower()
    if not kinds and (
        classification in EVENT_LEDGER_DECISION_CLASSIFICATIONS
        or classification.startswith(DECISION_FRESHNESS_CLASSIFICATION_PREFIXES)
    ):
        kinds.append("decision_classification")
    return kinds


def decision_freshness_reason(*, stale_by_age: bool, newer_event_count: int) -> str:
    if stale_by_age and newer_event_count:
        return "decision older than freshness window and newer sampled events exist; rebase at decision point"
    if stale_by_age:
        return "decision older than freshness window; rebase at decision point"
    if newer_event_count:
        return "newer sampled events exist after decision; rebase at decision point"
    return "no newer sampled events inside freshness window"


def build_decision_freshness_summary(history: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DECISION_FRESHNESS_WINDOW_DAYS)
    runs = [run for run in history.get("runs") or [] if isinstance(run, dict)]
    items: list[dict[str, Any]] = []
    stale_count = 0
    rebase_required_count = 0
    fresh_count = 0

    indexed_runs: list[tuple[dict[str, Any], datetime, str]] = []
    for run in runs:
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        indexed_runs.append((run, generated_at, str(run.get("goal_id") or "unknown-goal")))

    for run, decision_at, goal_id in indexed_runs:
        for decision_kind in decision_event_kinds(run):
            newer_class_counts = blank_event_class_counts()
            newer_event_count = 0
            for other_run, other_at, other_goal_id in indexed_runs:
                if other_goal_id != goal_id or other_at <= decision_at or other_at < cutoff:
                    continue
                newer_event_count += 1
                newer_class_counts[event_ledger_event_class(other_run)] += 1

            stale_by_age = decision_at < cutoff
            if stale_by_age:
                stale_count += 1
            requires_rebase = stale_by_age or newer_event_count > 0
            if requires_rebase:
                rebase_required_count += 1
            else:
                fresh_count += 1
            if stale_by_age:
                freshness_state = "stale_rebase_required"
            elif newer_event_count:
                freshness_state = "rebase_required"
            else:
                freshness_state = "fresh"

            items.append(
                {
                    "goal_id": goal_id,
                    "decision_kind": decision_kind,
                    "decision_at": decision_at.isoformat(),
                    "classification": run.get("classification"),
                    "age_days": round(max(0.0, (now - decision_at).total_seconds() / 86400), 2),
                    "stale_by_age": stale_by_age,
                    "newer_event_count_7d": newer_event_count,
                    "newer_event_classes_7d": newer_class_counts,
                    "freshness_state": freshness_state,
                    "requires_decision_point_rebase": requires_rebase,
                    "reason": decision_freshness_reason(
                        stale_by_age=stale_by_age,
                        newer_event_count=newer_event_count,
                    ),
                }
            )

    items.sort(
        key=lambda item: (
            1 if item["requires_decision_point_rebase"] else 0,
            item["age_days"],
            item["newer_event_count_7d"],
            item["decision_at"],
        ),
        reverse=True,
    )
    return {
        "available": True,
        "source": "run_history",
        "generated_at": now.isoformat(),
        "sample_run_count": len(runs),
        "window_days": DECISION_FRESHNESS_WINDOW_DAYS,
        "proxy_note": DECISION_FRESHNESS_PROXY_NOTE,
        "summary": {
            "decision_count": len(items),
            "stale_count": stale_count,
            "rebase_required_count": rebase_required_count,
            "fresh_count": fresh_count,
        },
        "items": items[:DECISION_FRESHNESS_ITEM_LIMIT],
    }


def build_usage_summary(history: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)
    totals = {
        "runs_24h": 0,
        "runs_7d": 0,
        "quota_spend_slots_24h": 0,
        "quota_spend_slots_7d": 0,
        "automation_run_count_24h": 0,
        "automation_run_count_7d": 0,
        "progress_signal_run_count_24h": 0,
        "progress_signal_run_count_7d": 0,
    }
    goals: dict[str, dict[str, Any]] = {}
    sample_count = 0

    for run in history.get("runs") or []:
        if not isinstance(run, dict):
            continue
        sample_count += 1
        generated_at = parse_timestamp(run.get("generated_at"))
        if generated_at is None:
            continue
        goal_id = str(run.get("goal_id") or "unknown-goal")
        goal = goals.setdefault(goal_id, blank_usage_goal(goal_id))
        slots = quota_spend_slots(run)
        automation_event = is_automation_run(run)
        progress_signal = is_progress_signal_run(run)

        if generated_at >= cutoff_7d:
            totals["runs_7d"] += 1
            goal["runs_7d"] += 1
            totals["quota_spend_slots_7d"] += slots
            goal["quota_spend_slots_7d"] += slots
            if automation_event:
                totals["automation_run_count_7d"] += 1
                goal["automation_run_count_7d"] += 1
            if progress_signal:
                totals["progress_signal_run_count_7d"] += 1
                goal["progress_signal_run_count_7d"] += 1
        if generated_at >= cutoff_24h:
            totals["runs_24h"] += 1
            goal["runs_24h"] += 1
            totals["quota_spend_slots_24h"] += slots
            goal["quota_spend_slots_24h"] += slots
            if automation_event:
                totals["automation_run_count_24h"] += 1
                goal["automation_run_count_24h"] += 1
            if progress_signal:
                totals["progress_signal_run_count_24h"] += 1
                goal["progress_signal_run_count_24h"] += 1

    if totals["runs_24h"]:
        for goal in goals.values():
            goal["project_share_24h"] = round(goal["runs_24h"] / totals["runs_24h"], 3)

    goal_rows = sorted(
        goals.values(),
        key=lambda item: (
            item["runs_24h"],
            item["quota_spend_slots_24h"],
            item["runs_7d"],
            item["goal_id"],
        ),
        reverse=True,
    )
    return {
        "available": True,
        "source": "run_history",
        "generated_at": now.isoformat(),
        "sample_run_count": sample_count,
        "proxy_note": USAGE_PROXY_NOTE,
        "totals": totals,
        "goals": goal_rows,
    }


def _todo_index_key(goal_id: str, todo: dict[str, Any]) -> tuple[str, str]:
    todo_id = normalize_todo_id(todo.get("todo_id")) or ""
    if todo_id:
        return goal_id, todo_id
    return goal_id, f"synthetic:{todo.get('role') or ''}:{todo.get('index') or ''}:{todo.get('text') or ''}"


def _indexed_status_todo(
    *,
    goal_id: str,
    role: str,
    todo: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    text = public_safe_compact_text(todo.get("title") or todo.get("text"), limit=320)
    if not text:
        return None
    item = compact_todo_item(todo)
    item.update(
        {
            "schema_version": TODO_INDEX_ITEM_SCHEMA_VERSION,
            "goal_id": goal_id,
            "role": role,
            "source": source,
            "text": text,
            "title": public_safe_compact_text(todo.get("title"), limit=320) or text,
        }
    )
    return item


def _rollout_event_todo_status(event: dict[str, Any]) -> str:
    status = normalize_todo_status(event.get("status"))
    if status:
        return status
    kind = str(event.get("event_kind") or "")
    if kind in {"todo_complete", "todo_archive_completed"}:
        return "done"
    if kind == "todo_supersede":
        return "deferred"
    return "open"


def _indexed_rollout_todo_event(event: dict[str, Any]) -> dict[str, Any] | None:
    todo_id = normalize_todo_id(event.get("todo_id"))
    goal_id = str(event.get("goal_id") or "").strip()
    if not goal_id or not todo_id:
        return None
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    role = str(details.get("role") or "agent").strip().lower()
    if role not in {"user", "agent"}:
        role = "agent"
    status = _rollout_event_todo_status(event)
    summary = public_safe_compact_text(
        event.get("summary") or f"{event.get('event_kind') or 'todo_event'} recorded for {todo_id}",
        limit=320,
    )
    if not summary:
        summary = f"todo event recorded for {todo_id}"
    return {
        "schema_version": TODO_INDEX_ITEM_SCHEMA_VERSION,
        "goal_id": goal_id,
        "todo_id": todo_id,
        "role": role,
        "status": status,
        "done": todo_done_for_status(status),
        "index": 0,
        "text": summary,
        "title": summary,
        "source": "rollout_event_log",
        "event_count": 1,
        "event_kinds": [str(event.get("event_kind") or "todo_event")],
        "latest_event_kind": str(event.get("event_kind") or "todo_event"),
        "latest_event_at": public_safe_compact_text(event.get("recorded_at"), limit=80),
        "latest_event_status": status,
        "agent_id": public_safe_compact_text(event.get("agent_id"), limit=120),
    }


def build_todo_index(
    *,
    queue: dict[str, Any],
    history: dict[str, Any],
    runtime_root: Path,
    limit: int = MAX_TODO_INDEX_ITEMS,
) -> dict[str, Any]:
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    current_count = 0
    for item in queue.get("items") or []:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("goal_id") or "")
        if not goal_id:
            continue
        for role in ("user", "agent"):
            todos = item.get(f"{role}_todos")
            if not isinstance(todos, dict):
                continue
            for todo in todos.get("items") or []:
                if not isinstance(todo, dict):
                    continue
                indexed_item = _indexed_status_todo(
                    goal_id=goal_id,
                    role=role,
                    todo=todo,
                    source="attention_queue",
                )
                if indexed_item is None:
                    continue
                indexed[_todo_index_key(goal_id, indexed_item)] = indexed_item
                current_count += 1

    rollout_event_count = 0
    goal_ids = [
        str(goal.get("id") or "")
        for goal in history.get("goals") or []
        if isinstance(goal, dict) and str(goal.get("id") or "")
    ]
    for goal_id in sorted(set(goal_ids)):
        events = load_rollout_events(
            rollout_event_log_path(runtime_root, goal_id),
            limit=MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
        )
        for event in events:
            if not isinstance(event, dict) or not str(event.get("event_kind") or "").startswith("todo_"):
                continue
            rollout_event_count += 1
            event_item = _indexed_rollout_todo_event(event)
            if event_item is None:
                continue
            key = _todo_index_key(goal_id, event_item)
            existing = indexed.get(key)
            if existing:
                existing["event_count"] = int(existing.get("event_count") or 0) + 1
                kinds = list(existing.get("event_kinds") or [])
                latest_kind = event_item.get("latest_event_kind")
                if latest_kind and latest_kind not in kinds:
                    kinds.append(latest_kind)
                existing["event_kinds"] = kinds
                existing["latest_event_kind"] = latest_kind
                existing["latest_event_at"] = event_item.get("latest_event_at")
                existing["latest_event_status"] = event_item.get("latest_event_status")
                if event_item.get("status"):
                    existing["status"] = event_item.get("status")
                    existing["done"] = bool(event_item.get("done"))
                if event_item.get("agent_id"):
                    existing["agent_id"] = event_item.get("agent_id")
                continue
            indexed[key] = event_item

    items = sorted(
        indexed.values(),
        key=lambda item: (
            0 if not item.get("done") else 1,
            str(item.get("goal_id") or ""),
            str(item.get("todo_id") or ""),
            str(item.get("latest_event_at") or ""),
        ),
    )
    return {
        "schema_version": TODO_INDEX_SCHEMA_VERSION,
        "source": "attention_queue_and_rollout_event_log",
        "total_count": len(items),
        "current_projected_count": current_count,
        "rollout_event_count": rollout_event_count,
        "item_limit": limit,
        "items": items[: max(0, limit)],
    }


def collect_status(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool = False,
    goal_id: str | None = None,
) -> dict[str, Any]:
    display_limit = max(0, limit)
    control_plane_limit = max(display_limit, STATUS_CONTROL_PLANE_CONTEXT_LIMIT)
    goal_filter = str(goal_id or "").strip() or None
    registry = load_registry(registry_path)
    runtime_root = resolve_runtime_root(registry, runtime_root_override)
    global_registry = collect_global_registry_health(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=registry,
    )
    include_runtime_goals = bool(global_registry.get("current_registry_is_global"))
    history = collect_history(
        registry_path=registry_path,
        runtime_root=runtime_root,
        goal_id=goal_filter,
        limit=control_plane_limit,
        include_runtime_goals=include_runtime_goals,
    )
    contract = check_contract(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
    )
    queue = build_attention_queue(
        contract=contract,
        history=history,
        global_registry=global_registry,
        runtime_root=runtime_root,
        include_task_graph=include_task_graph,
        goal_id_filter=goal_filter,
    )
    run_history = build_run_history(history, display_limit=display_limit)
    event_ledger_summary = build_event_ledger_summary(history)
    promotion_readiness_summary = build_promotion_readiness_summary(
        history,
        runtime_root=runtime_root,
        goal_id_filter=goal_filter,
    )
    promotion_gate = build_promotion_gate(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
    )
    decision_freshness_summary = build_decision_freshness_summary(history)
    usage_summary = build_usage_summary(history)
    todo_index = build_todo_index(
        queue=queue,
        history=history,
        runtime_root=runtime_root,
        limit=max(MAX_TODO_INDEX_ITEMS, display_limit),
    )
    return {
        "ok": bool(contract.get("ok")) and bool(global_registry.get("ok", True)),
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "status_contract": build_status_contract(),
        "goal_filter": goal_filter,
        **build_contract_health_projection(contract),
        "contract": {
            "ok": contract.get("ok"),
            "summary": contract.get("summary"),
            "errors": contract.get("errors") or [],
            "warnings": contract.get("warnings") or [],
            "checks": contract.get("checks") or [],
        },
        "global_registry": global_registry,
        "attention_queue": queue,
        "run_history": run_history,
        "event_ledger_summary": event_ledger_summary,
        "promotion_readiness_summary": promotion_readiness_summary,
        "promotion_gate": promotion_gate,
        "decision_freshness_summary": decision_freshness_summary,
        "usage_summary": usage_summary,
        "todo_index": todo_index,
    }


def render_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Status",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- runs: `{payload.get('run_count')}`",
    ]

    status_contract = (
        payload.get("status_contract")
        if isinstance(payload.get("status_contract"), dict)
        else {}
    )
    if status_contract:
        lines.append(
            "- status_contract: "
            f"schema_version={status_contract.get('schema_version')}, "
            f"minimum_dashboard_schema_version={status_contract.get('minimum_dashboard_schema_version')}, "
            f"producer={status_contract.get('producer')}"
        )
    if payload.get("goal_filter"):
        lines.append(f"- goal_filter: `{payload.get('goal_filter')}`")

    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    lines.append(
        "- contract: "
        f"ok={contract.get('ok')}, "
        f"errors={summary.get('errors')}, "
        f"warnings={summary.get('warnings')}, "
        f"checks={summary.get('checks')}"
    )
    contract_errors = (
        payload.get("contract_errors") if isinstance(payload.get("contract_errors"), list) else []
    )
    contract_warnings = (
        payload.get("contract_warnings") if isinstance(payload.get("contract_warnings"), list) else []
    )
    if contract_errors or contract_warnings:
        lines.extend(["", "## Status Contract Signals"])
        for item in contract_errors:
            lines.append(f"- error: {item}")
        if payload.get("contract_errors_truncated"):
            lines.append(
                f"- contract_errors_truncated: total={payload.get('contract_errors_total_count')}"
            )
        for item in contract_warnings:
            lines.append(f"- warning: {item}")
        if payload.get("contract_warnings_truncated"):
            lines.append(
                f"- contract_warnings_truncated: total={payload.get('contract_warnings_total_count')}"
            )

    global_registry = payload.get("global_registry") if isinstance(payload.get("global_registry"), dict) else {}
    global_summary = (
        global_registry.get("summary")
        if isinstance(global_registry.get("summary"), dict)
        else {}
    )
    lines.extend(
        [
            "- global_registry: "
            f"available={global_registry.get('available')}, "
            f"ok={global_registry.get('ok')}, "
            f"findings={global_summary.get('findings')}, "
            f"high={global_summary.get('high')}, "
            f"action={global_summary.get('action')}, "
            f"info={global_summary.get('info')}",
        ]
    )

    event_ledger = (
        payload.get("event_ledger_summary")
        if isinstance(payload.get("event_ledger_summary"), dict)
        else {}
    )
    _append_event_ledger_summary_markdown(
        lines,
        event_ledger,
        event_classes=EVENT_LEDGER_CLASSES,
    )

    promotion_readiness = (
        payload.get("promotion_readiness_summary")
        if isinstance(payload.get("promotion_readiness_summary"), dict)
        else {}
    )
    _append_promotion_readiness_summary_markdown(lines, promotion_readiness)

    promotion_gate = (
        payload.get("promotion_gate")
        if isinstance(payload.get("promotion_gate"), dict)
        else {}
    )
    _append_promotion_gate_markdown(lines, promotion_gate)

    decision_freshness = (
        payload.get("decision_freshness_summary")
        if isinstance(payload.get("decision_freshness_summary"), dict)
        else {}
    )
    _append_decision_freshness_summary_markdown(lines, decision_freshness)

    usage = payload.get("usage_summary") if isinstance(payload.get("usage_summary"), dict) else {}
    _append_usage_summary_markdown(lines, usage)

    queue = payload.get("attention_queue") if isinstance(payload.get("attention_queue"), dict) else {}
    _append_attention_queue_summary_markdown(lines, queue)
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    goals = _goals_by_id(payload)
    if not items:
        lines.append("- none")
    for item in items:
        if not isinstance(item, dict):
            continue
        authority_summary = _authority_registry_markdown_summary(goals.get(str(item.get("goal_id") or "")))
        _append_attention_queue_item_header_markdown(
            lines,
            item,
            authority_summary=authority_summary,
        )
        project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
        agent_lane_next_action = (
            project_asset.get("agent_lane_next_action")
            if isinstance(project_asset.get("agent_lane_next_action"), dict)
            else item.get("agent_lane_next_action")
            if isinstance(item.get("agent_lane_next_action"), dict)
            else {}
        )
        agent_lane_frontier_hint = (
            project_asset.get("agent_lane_frontier_hint")
            if isinstance(project_asset.get("agent_lane_frontier_hint"), dict)
            else item.get("agent_lane_frontier_hint")
            if isinstance(item.get("agent_lane_frontier_hint"), dict)
            else {}
        )
        goal_todo_scope_suffix = " scope=goal_all_agents" if agent_lane_next_action else ""
        lines.append(
            "  - project_asset_source: "
            + (
                "project_asset"
                if project_asset
                else "legacy/raw fallback; owner/gate/stop are not project_asset-backed"
            )
        )
        if project_asset:
            lines.append(
                "  - project_asset: "
                f"owner={_markdown_scalar(project_asset.get('owner') or '')} "
                f"gate={_markdown_scalar(project_asset.get('gate') or '')} "
                f"stop={_markdown_scalar(project_asset.get('stop_condition') or '')}"
            )
            asset_next_action = _markdown_scalar(project_asset.get("next_action") or "")
            if asset_next_action:
                lines.append(f"    - asset_next_action: {asset_next_action}")
            asset_active_next_action = _markdown_scalar(
                project_asset.get("active_state_next_action") or ""
            )
            if asset_active_next_action:
                lines.append(f"    - asset_active_state_next_action: {asset_active_next_action}")
            asset_latest_run_action = _markdown_scalar(
                project_asset.get("latest_run_recommended_action") or ""
            )
            if asset_latest_run_action:
                lines.append(f"    - asset_latest_run_recommended_action: {asset_latest_run_action}")
            agent_lane_recommendation = (
                project_asset.get("agent_lane_recommendation")
                if isinstance(project_asset.get("agent_lane_recommendation"), dict)
                else {}
            )
            if agent_lane_recommendation:
                lane = _markdown_scalar(agent_lane_recommendation.get("agent_lane") or "")
                agent = _markdown_scalar(agent_lane_recommendation.get("agent_id") or "")
                recommendation = _markdown_scalar(
                    agent_lane_recommendation.get("recommended_action") or ""
                )
                lines.append(
                    "    - agent_lane_recommendation: "
                    f"agent={agent} lane={lane} action={recommendation}"
                )
            agent_member = (
                project_asset.get("agent_member")
                if isinstance(project_asset.get("agent_member"), dict)
                else item.get("agent_member")
                if isinstance(item.get("agent_member"), dict)
                else {}
            )
            if agent_member:
                current_claims = ",".join(
                    _markdown_scalar(claim)
                    for claim in (agent_member.get("current_claims") or [])
                    if str(claim or "").strip()
                )
                lines.append(
                    "    - agent_member: "
                    f"agent={_markdown_scalar(agent_member.get('agent_id') or '')} "
                    f"role={_markdown_scalar(agent_member.get('role') or '')} "
                    f"scope={_markdown_scalar(agent_member.get('scope_summary') or '')} "
                    f"worktree_policy={_markdown_scalar(agent_member.get('worktree_policy') or '')} "
                    f"claims={_markdown_scalar(current_claims)} "
                    f"handoff_agent={_markdown_scalar(agent_member.get('handoff_agent') or '')} "
                    f"source={_markdown_scalar(agent_member.get('profile_source') or '')} "
                    "authority=advisory_projection"
                )
            if agent_lane_next_action:
                agent = _markdown_scalar(agent_lane_next_action.get("agent_id") or "")
                todo_id = _markdown_scalar(agent_lane_next_action.get("todo_id") or "")
                selected_by = _markdown_scalar(agent_lane_next_action.get("selected_by") or "")
                confidence = _markdown_scalar(agent_lane_next_action.get("confidence") or "")
                action = _markdown_scalar(agent_lane_next_action.get("text") or "")
                lines.append(
                    "    - current_agent_todo: "
                    f"agent={agent} todo_id={todo_id} selected_by={selected_by} "
                    f"confidence={confidence} source=agent_lane_next_action action={action}"
                )
            if agent_lane_frontier_hint:
                lines.append(
                    "    - agent_lane_frontier_hint: "
                    f"agent={_markdown_scalar(agent_lane_frontier_hint.get('agent_id') or '')} "
                    f"decision={_markdown_scalar(agent_lane_frontier_hint.get('decision') or '')} "
                    f"source={_markdown_scalar(agent_lane_frontier_hint.get('source') or '')} "
                    f"reason_code={_markdown_scalar(agent_lane_frontier_hint.get('reason_code') or '')} "
                    f"target_todo_id={_markdown_scalar(agent_lane_frontier_hint.get('target_todo_id') or '')}"
                )
            goal_frontier = (
                project_asset.get("goal_frontier_projection")
                if isinstance(project_asset.get("goal_frontier_projection"), dict)
                else item.get("goal_frontier_projection")
                if isinstance(item.get("goal_frontier_projection"), dict)
                else {}
            )
            if goal_frontier:
                remaining = (
                    goal_frontier.get("remaining_advancement_frontier")
                    if isinstance(goal_frontier.get("remaining_advancement_frontier"), dict)
                    else {}
                )
                deferred_successors = (
                    goal_frontier.get("deferred_successors")
                    if isinstance(goal_frontier.get("deferred_successors"), dict)
                    else {}
                )
                acceptance_gaps = (
                    goal_frontier.get("acceptance_gaps")
                    if isinstance(goal_frontier.get("acceptance_gaps"), list)
                    else []
                )
                lines.append(
                    "    - goal_frontier_projection: "
                    f"replan_required={goal_frontier.get('replan_required')} "
                    f"current_agent_advancement={remaining.get('current_agent_claimed_advancement_count')} "
                    f"unclaimed_advancement={remaining.get('unclaimed_advancement_count')} "
                    f"other_agent_advancement={remaining.get('other_agent_claimed_advancement_count')} "
                    f"deferred_ready={deferred_successors.get('ready_count')} "
                    f"acceptance_gaps={len(acceptance_gaps)}"
                )
            dreaming_lane_badge = (
                project_asset.get("dreaming_lane_badge")
                if isinstance(project_asset.get("dreaming_lane_badge"), dict)
                else {}
            )
            if dreaming_lane_badge:
                lines.append(
                    "    - dreaming_lane_badge: "
                    f"lane={_markdown_scalar(dreaming_lane_badge.get('lane') or '')} "
                    f"status={_markdown_scalar(dreaming_lane_badge.get('status') or '')} "
                    f"proposal_id={_markdown_scalar(dreaming_lane_badge.get('proposal_id') or '')} "
                    f"advisory={dreaming_lane_badge.get('advisory')} "
                    f"interrupts_delivery={dreaming_lane_badge.get('interrupts_delivery')} "
                    f"execution_allowed={dreaming_lane_badge.get('execution_allowed')}"
                )
            asset_execution_profile = (
                project_asset.get("execution_profile")
                if isinstance(project_asset.get("execution_profile"), dict)
                else None
            )
            if asset_execution_profile:
                lines.append(
                    "    - execution_profile: "
                    f"{_markdown_scalar(execution_profile_summary(asset_execution_profile))}"
                )
            long_task_cadence_hint = (
                project_asset.get("long_task_cadence_hint")
                if isinstance(project_asset.get("long_task_cadence_hint"), dict)
                else None
            )
            if long_task_cadence_hint:
                lines.append(
                    "    - long_task_cadence_hint: "
                    f"{_markdown_scalar(long_task_cadence_hint_summary(long_task_cadence_hint))}"
                )
            asset_orchestration = (
                project_asset.get("orchestration")
                if isinstance(project_asset.get("orchestration"), dict)
                else None
            )
            if asset_orchestration:
                lines.append(
                    "    - orchestration: "
                    f"{_markdown_scalar(orchestration_policy_summary(asset_orchestration))}"
                )
            subagent_activity = (
                project_asset.get("subagent_activity")
                if isinstance(project_asset.get("subagent_activity"), dict)
                else {}
            )
            if subagent_activity:
                lines.append(
                    "    - subagent_activity: "
                    f"children={subagent_activity.get('child_count')} "
                    f"visible={subagent_activity.get('visible_child_count')} "
                    f"active={subagent_activity.get('active_count')} "
                    f"completed={subagent_activity.get('completed_count')} "
                    f"quota_slots={subagent_activity.get('quota_spend_slots')}"
                )
                for child in (subagent_activity.get("items") or [])[:3]:
                    if not isinstance(child, dict):
                        continue
                    role = _markdown_scalar(child.get("agent_role") or "subagent")
                    state = _markdown_scalar(child.get("state") or "unknown")
                    run_id = _markdown_scalar(child.get("run_id") or "")
                    parent_run_id = _markdown_scalar(child.get("parent_run_id") or "")
                    lines.append(
                        f"      - child_run: role={role} state={state} "
                        f"run_id={run_id} parent_run_id={parent_run_id}"
                    )
            asset_user_todos = (
                project_asset.get("user_todos")
                if isinstance(project_asset.get("user_todos"), dict)
                else {}
            )
            asset_agent_todos = (
                project_asset.get("agent_todos")
                if isinstance(project_asset.get("agent_todos"), dict)
                else {}
            )
            if asset_user_todos or asset_agent_todos:
                todo_parts = []
                if asset_user_todos:
                    todo_parts.append(f"user_open={asset_user_todos.get('open')}")
                    if asset_user_todos.get("claimed_open_count"):
                        todo_parts.append(f"user_claimed={asset_user_todos.get('claimed_open_count')}")
                if asset_agent_todos:
                    todo_parts.append(f"agent_open={asset_agent_todos.get('open')}")
                    if asset_agent_todos.get("claimed_open_count"):
                        todo_parts.append(f"agent_claimed={asset_agent_todos.get('claimed_open_count')}")
                lines.append(f"    - asset_todos: {' '.join(todo_parts)}")
                if asset_user_todos.get("next"):
                    claimed = asset_user_todos.get("next_claimed_by")
                    claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                    lines.append(f"      - asset_user_todo: {_markdown_scalar(asset_user_todos.get('next') or '')}{claim_suffix}")
                for todo in (asset_user_todos.get("items") or [])[1:3]:
                    if isinstance(todo, dict) and todo.get("text"):
                        index = todo.get("index")
                        suffix = f"[{index}]" if index is not None else ""
                        claimed = todo.get("claimed_by")
                        claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                        lines.append(f"      - asset_user_todo{suffix}: {_markdown_scalar(todo.get('text') or '')}{claim_suffix}")
                if asset_agent_todos.get("next"):
                    claimed = asset_agent_todos.get("next_claimed_by")
                    claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                    lines.append(
                        f"      - asset_agent_todo: "
                        f"{_markdown_scalar(asset_agent_todos.get('next') or '')}"
                        f"{claim_suffix}{goal_todo_scope_suffix}"
                    )
                for todo in (asset_agent_todos.get("items") or [])[1:3]:
                    if isinstance(todo, dict) and todo.get("text"):
                        index = todo.get("index")
                        suffix = f"[{index}]" if index is not None else ""
                        claimed = todo.get("claimed_by")
                        claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                        lines.append(
                            f"      - asset_agent_todo{suffix}: "
                            f"{_markdown_scalar(todo.get('text') or '')}"
                            f"{claim_suffix}{goal_todo_scope_suffix}"
                        )
            asset_quota = (
                project_asset.get("quota")
                if isinstance(project_asset.get("quota"), dict)
                else {}
            )
            if asset_quota:
                lines.append(
                    "    - asset_quota: "
                    f"compute={asset_quota.get('compute')} "
                    f"state={asset_quota.get('state')} "
                    f"slots={asset_quota.get('spent_slots')}/{asset_quota.get('allowed_slots')}"
                )
            projection_warning = (
                project_asset.get("stale_latest_run_warning")
                if isinstance(project_asset.get("stale_latest_run_warning"), dict)
                else {}
            )
            if projection_warning:
                lines.append(
                    "    - stale_latest_run_warning: "
                    f"requires_refresh_state={projection_warning.get('requires_refresh_state')} "
                    f"active_state_updated_at={_markdown_scalar(projection_warning.get('active_state_updated_at') or '')} "
                    f"latest_run_generated_at={_markdown_scalar(projection_warning.get('latest_run_generated_at') or '')} "
                    f"reason={_markdown_scalar(projection_warning.get('reason') or '')}"
                )
            next_action_warning = (
                project_asset.get("next_action_projection_warning")
                if isinstance(project_asset.get("next_action_projection_warning"), dict)
                else item.get("next_action_projection_warning")
                if isinstance(item.get("next_action_projection_warning"), dict)
                else {}
            )
            if next_action_warning:
                lines.append(
                    "    - next_action_projection_warning: "
                    f"requires_state_writeback={next_action_warning.get('requires_state_writeback')} "
                    f"reason={_markdown_scalar(next_action_warning.get('reason') or '')}"
                )
            backlog_warning = (
                project_asset.get("backlog_hygiene_warning")
                if isinstance(project_asset.get("backlog_hygiene_warning"), dict)
                else {}
            )
            if backlog_warning:
                lines.append(
                    "    - backlog_hygiene_warning: "
                    f"requires_agent_todo={backlog_warning.get('requires_agent_todo')} "
                    f"evidence_count={backlog_warning.get('evidence_count')} "
                    f"source_sections={_markdown_scalar(','.join(backlog_warning.get('source_sections') or []))}"
                )
            projection_gap = (
                project_asset.get("state_projection_gap")
                if isinstance(project_asset.get("state_projection_gap"), dict)
                else {}
            )
            if projection_gap:
                lines.append(
                    "    - state_projection_gap: "
                    f"requires_todo_expansion={projection_gap.get('requires_todo_expansion')} "
                    f"user_open={projection_gap.get('user_open_count')} "
                    f"agent_open={projection_gap.get('agent_open_count')} "
                    f"target_roles={_markdown_scalar(','.join(projection_gap.get('target_roles') or []))}"
                )
            todo_projection_gap = (
                project_asset.get("todo_projection_gap")
                if isinstance(project_asset.get("todo_projection_gap"), dict)
                else {}
            )
            if todo_projection_gap:
                lines.append(
                    "    - todo_projection_gap: "
                    f"missing_roles={_markdown_scalar(','.join(todo_projection_gap.get('missing_roles') or []))} "
                    f"source={_markdown_scalar(todo_projection_gap.get('source') or '')}"
                )
            archive_warning = (
                project_asset.get("completed_todo_archive_warning")
                if isinstance(project_asset.get("completed_todo_archive_warning"), dict)
                else {}
            )
            if archive_warning:
                lines.append(
                    "    - completed_todo_archive_warning: "
                    f"requires_archive={archive_warning.get('requires_archive')} "
                    f"active_done={archive_warning.get('active_done_count')} "
                    f"max_active_done={archive_warning.get('max_active_done_count')} "
                    f"archive_section={_markdown_scalar(archive_warning.get('archive_section') or '')}"
                )
            replan_obligation = (
                project_asset.get("autonomous_replan_obligation")
                if isinstance(project_asset.get("autonomous_replan_obligation"), dict)
                else {}
            )
            if replan_obligation:
                trigger_kinds = [
                    str(trigger.get("kind") or "")
                    for trigger in replan_obligation.get("triggers") or []
                    if isinstance(trigger, dict) and trigger.get("kind")
                ]
                lines.append(
                    "    - autonomous_replan_obligation: "
                    f"required={replan_obligation.get('required')} "
                    f"trigger_count={replan_obligation.get('trigger_count')} "
                    f"triggers={_markdown_scalar(','.join(trigger_kinds))}"
                )
            interface_budget_cadence = (
                project_asset.get("interface_budget_cadence")
                if isinstance(project_asset.get("interface_budget_cadence"), dict)
                else {}
            )
            if interface_budget_cadence:
                lines.append(
                    "    - interface_budget_cadence: "
                    f"overdue={interface_budget_cadence.get('overdue')} "
                    f"within_budget={interface_budget_cadence.get('within_budget')} "
                    f"checked_at={_markdown_scalar(interface_budget_cadence.get('checked_at') or '')} "
                    f"next_check_due_at={_markdown_scalar(interface_budget_cadence.get('next_check_due_at') or '')} "
                    f"tightest={_markdown_scalar(interface_budget_cadence.get('tightest_surface') or '')}/"
                    f"{_markdown_scalar(interface_budget_cadence.get('tightest_metric') or '')} "
                    f"headroom={interface_budget_cadence.get('headroom_remaining')} "
                    f"recommendation={_markdown_scalar(interface_budget_cadence.get('recommendation') or '')}"
                )
            latest_validation = (
                project_asset.get("latest_validation")
                if isinstance(project_asset.get("latest_validation"), dict)
                else {}
            )
            if latest_validation:
                lines.append(
                    "    - latest_validation: "
                    f"classification={_markdown_scalar(latest_validation.get('classification') or '')} "
                    f"at={_markdown_scalar(latest_validation.get('generated_at') or '')}"
                )
            session_projection = (
                project_asset.get("session_runtime_projection")
                if isinstance(project_asset.get("session_runtime_projection"), dict)
                else {}
            )
            if session_projection:
                first_screen = (
                    session_projection.get("first_screen")
                    if isinstance(session_projection.get("first_screen"), dict)
                    else {}
                )
                boundary = (
                    session_projection.get("boundary")
                    if isinstance(session_projection.get("boundary"), dict)
                    else {}
                )
                source = (
                    session_projection.get("source")
                    if isinstance(session_projection.get("source"), dict)
                    else {}
                )
                lines.append(
                    "    - session_runtime_projection: "
                    f"waiting_on={_markdown_scalar(first_screen.get('waiting_on') or '')} "
                    f"agent_can_continue={first_screen.get('agent_can_continue')} "
                    f"user_action_required={first_screen.get('user_action_required')} "
                    f"gate={_markdown_scalar(first_screen.get('gate_state') or '')} "
                    f"raw_material_detected={boundary.get('raw_material_detected')} "
                    f"runtime_writeback_allowed={boundary.get('runtime_writeback_allowed')} "
                    f"host={_markdown_scalar(source.get('host_kind') or '')}"
                )
                if first_screen.get("first_user_todo"):
                    lines.append(
                        "      - session_runtime_user_todo: "
                        f"{_markdown_scalar(first_screen.get('first_user_todo') or '')}"
                    )
                if first_screen.get("first_agent_todo"):
                    lines.append(
                        "      - session_runtime_agent_todo: "
                        f"{_markdown_scalar(first_screen.get('first_agent_todo') or '')}"
                    )
            handoff_readiness = (
                item.get("handoff_readiness")
                if isinstance(item.get("handoff_readiness"), dict)
                else {}
            )
            if handoff_readiness:
                lines.append(
                    "    - handoff_readiness: "
                    f"ready={handoff_readiness.get('ready')} "
                    f"codex_ready={handoff_readiness.get('codex_ready')} "
                    f"source={_markdown_scalar(handoff_readiness.get('source') or '')} "
                    f"quota_state={_markdown_scalar(handoff_readiness.get('quota_state') or '')}"
                )
                interface_budget = (
                    handoff_readiness.get("handoff_interface_budget")
                    if isinstance(handoff_readiness.get("handoff_interface_budget"), dict)
                    else {}
                )
                if interface_budget:
                    lines.append(
                        "      - handoff_interface_budget: "
                        f"mode={_markdown_scalar(interface_budget.get('mode') or '')} "
                        f"max_lines={interface_budget.get('max_lines')} "
                        f"max_chars={interface_budget.get('max_chars')}"
                    )
                checks = (
                    handoff_readiness.get("checks")
                    if isinstance(handoff_readiness.get("checks"), dict)
                    else {}
                )
                passed = [key for key, value in checks.items() if value]
                failed = [key for key, value in checks.items() if not value]
                if checks:
                    lines.append(
                        "      - handoff_checks: "
                        f"pass={','.join(passed) if passed else '-'} "
                        f"fail={','.join(failed) if failed else '-'}"
                    )
                lines.append(
                    "      - handoff_state: "
                    f"status={_markdown_scalar(handoff_readiness.get('handoff_status') or '')} "
                    f"post_handoff_run_seen={handoff_readiness.get('post_handoff_run_seen')} "
                    f"ready_at={_markdown_scalar(handoff_readiness.get('handoff_ready_at') or '')}"
                )
                latest_handoff_run = (
                    handoff_readiness.get("post_handoff_latest_run")
                    if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
                    else {}
                )
                if latest_handoff_run:
                    outcome_suffix = ""
                    if latest_handoff_run.get("delivery_outcome"):
                        outcome_suffix = (
                            " "
                            f"outcome={_markdown_scalar(latest_handoff_run.get('delivery_outcome') or '')}"
                        )
                    turn_kind_suffix = ""
                    if latest_handoff_run.get("delivery_turn_kind"):
                        turn_kind_suffix = (
                            " "
                            f"turn_kind={_markdown_scalar(latest_handoff_run.get('delivery_turn_kind') or '')}"
                        )
                    lines.append(
                        "      - post_handoff_run: "
                        f"classification={_markdown_scalar(latest_handoff_run.get('classification') or '')} "
                        f"at={_markdown_scalar(latest_handoff_run.get('generated_at') or '')} "
                        f"scale={_markdown_scalar(latest_handoff_run.get('delivery_batch_scale') or '')}"
                        f"{outcome_suffix}"
                        f"{turn_kind_suffix}"
                    )
                recent_handoff_runs = (
                    handoff_readiness.get("post_handoff_recent_runs")
                    if isinstance(handoff_readiness.get("post_handoff_recent_runs"), list)
                    else []
                )
                recent_scales = [
                    _markdown_scalar(str(run.get("delivery_batch_scale") or ""))
                    for run in recent_handoff_runs
                    if isinstance(run, dict)
                ]
                if recent_scales:
                    recent_outcomes = [
                        _markdown_scalar(str(run.get("delivery_outcome") or ""))
                        for run in recent_handoff_runs
                        if isinstance(run, dict) and run.get("delivery_outcome")
                    ]
                    outcome_text = f" outcome={','.join(recent_outcomes)}" if recent_outcomes else ""
                    recent_turn_kinds = [
                        _markdown_scalar(str(run.get("delivery_turn_kind") or ""))
                        for run in recent_handoff_runs
                        if isinstance(run, dict) and run.get("delivery_turn_kind")
                    ]
                    turn_kind_text = (
                        f" turn_kind={','.join(recent_turn_kinds)}" if recent_turn_kinds else ""
                    )
                    gap_text = (
                        f" outcome_gap_streak={handoff_readiness.get('post_handoff_outcome_gap_streak')}"
                        if "post_handoff_outcome_gap_streak" in handoff_readiness
                        else ""
                    )
                    lines.append(
                        "      - post_handoff_recent_scales: "
                        f"{','.join(recent_scales)} "
                        f"small_streak={handoff_readiness.get('post_handoff_small_scale_streak', 0)}"
                        f"{outcome_text}"
                        f"{turn_kind_text}"
                        f"{gap_text}"
                    )
                if handoff_readiness.get("next_probe"):
                    handoff_probe = _markdown_scalar(handoff_readiness.get("next_probe") or "")
                    lines.append(f"      - handoff_probe: `{handoff_probe}`")
        user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else {}
        if user_todos:
            todo_parts = [
                f"open={user_todos.get('open_count')}",
                f"done={user_todos.get('done_count')}",
                f"total={user_todos.get('total_count')}",
            ]
            if user_todos.get("claimed_open_count"):
                todo_parts.insert(1, f"claimed={user_todos.get('claimed_open_count')}")
                todo_parts.insert(2, f"unclaimed={user_todos.get('unclaimed_open_count', 0)}")
            lines.append(f"  - user_todos: {' '.join(todo_parts)}")
            for todo in user_todos.get("items") or []:
                if not isinstance(todo, dict) or todo.get("done"):
                    continue
                claimed = todo.get("claimed_by")
                claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                lines.append(f"    - next_user_todo: {_markdown_scalar(todo.get('text') or '')}{claim_suffix}")
                for material in todo.get("review_materials") or []:
                    if not isinstance(material, dict):
                        continue
                    lines.append(
                        "      - review_material: "
                        f"{_markdown_scalar(material.get('label') or material.get('path') or '')} "
                        f"exists={material.get('exists')}"
                    )
                break
        agent_todos = item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else {}
        if agent_todos:
            todo_parts = [
                f"open={agent_todos.get('open_count')}",
                f"done={agent_todos.get('done_count')}",
                f"total={agent_todos.get('total_count')}",
            ]
            if agent_todos.get("claimed_open_count"):
                todo_parts.insert(1, f"claimed={agent_todos.get('claimed_open_count')}")
                todo_parts.insert(2, f"unclaimed={agent_todos.get('unclaimed_open_count', 0)}")
            lines.append(f"  - agent_todos: {' '.join(todo_parts)}")
            for todo in agent_todos.get("items") or []:
                if not isinstance(todo, dict) or todo.get("done"):
                    continue
                claimed = todo.get("claimed_by")
                claim_suffix = f" claimed_by={_markdown_scalar(claimed)}" if claimed else ""
                lines.append(
                    f"    - next_agent_todo: "
                    f"{_markdown_scalar(todo.get('text') or '')}"
                    f"{claim_suffix}{goal_todo_scope_suffix}"
                )
                break
        dependency_blockers = (
            item.get("dependency_blockers")
            if isinstance(item.get("dependency_blockers"), dict)
            else {}
        )
        if dependency_blockers:
            lines.append(
                "  - dependency_blockers: "
                f"open={dependency_blockers.get('open_count')} "
                f"source={_markdown_scalar(dependency_blockers.get('source') or '')}"
            )
            for blocker in dependency_blockers.get("items") or []:
                if not isinstance(blocker, dict):
                    continue
                lines.append(
                    "    - dependency_user_todo: "
                    f"goal={_markdown_scalar(blocker.get('goal_id') or '')} "
                    f"waiting_on={_markdown_scalar(blocker.get('waiting_on') or '')} "
                    f"text={_markdown_scalar(blocker.get('text') or '')}"
                )
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        if quota:
            lines.append(
                "  - quota: "
                f"compute={quota.get('compute')} "
                f"state={quota.get('state')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
                f"reason={quota.get('reason')}"
            )
        control_plane = item.get("control_plane") if isinstance(item.get("control_plane"), dict) else None
        if control_plane:
            lines.append(f"  - control_plane: {control_plane_policy_summary(control_plane)}")
        operator_question = item.get("operator_question")
        agent_command = item.get("agent_command")
        if operator_question:
            lines.append(f"  - operator_question: {operator_question}")
            if agent_command:
                goal_id = item.get("goal_id")
                lines.append(
                    "  - operator_gate_dry_run: "
                    f"`loopx operator-gate --goal-id {goal_id} --decision approve "
                    '--reason-summary "<public-safe reason>" --dry-run`'
                )
        if agent_command:
            lines.append(f"  - agent_command: `{agent_command}`")
        gates = item.get("missing_gates") if isinstance(item.get("missing_gates"), list) else []
        gate_text = ", ".join(str(gate) for gate in gates if gate)
        controller_stage = item.get("controller_stage")
        next_condition = item.get("next_handoff_condition")
        if controller_stage or gate_text:
            lines.append(
                "  - gates: "
                f"stage={controller_stage or 'none'} "
                f"missing={gate_text or 'none'}"
            )
        if next_condition:
            lines.append(f"  - next_handoff_condition: {next_condition}")

    run_history = payload.get("run_history") if isinstance(payload.get("run_history"), dict) else {}
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    lines.extend(
        [
            "",
            "## Run History",
            "- summary: "
            f"goals={run_history.get('goal_count')}, "
            f"runs={run_history.get('run_count')}",
        ]
    )
    if not run_goals:
        lines.append("- none")
    for goal in run_goals:
        if not isinstance(goal, dict):
            continue
        lines.append(
            "- "
            f"`{goal.get('id')}`: "
            f"status={goal.get('status')} "
            f"phase={goal.get('lifecycle_phase')} "
            f"adapter={goal.get('adapter_kind')}:{goal.get('adapter_status')} "
            f"records={goal.get('raw_index_records')} "
            f"unique_runs={goal.get('unique_runs')}"
        )
        quota = goal.get("quota") if isinstance(goal.get("quota"), dict) else {}
        if quota:
            lines.append(
                "  - quota: "
                f"compute={quota.get('compute')} "
                f"state={quota.get('state')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')}"
            )
        latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
        if latest_runs:
            latest = latest_runs[0]
            if isinstance(latest, dict):
                reward = latest.get("human_reward") if isinstance(latest.get("human_reward"), dict) else {}
                reward_text = (
                    f" reward={reward.get('decision')}:{reward.get('reward')}"
                    if reward
                    else ""
                )
                operator_gate = (
                    latest.get("operator_gate")
                    if isinstance(latest.get("operator_gate"), dict)
                    else {}
                )
                operator_gate_text = (
                    f" operator_gate={operator_gate.get('gate')}:{operator_gate.get('decision')}"
                    if operator_gate
                    else ""
                )
                readiness = (
                    latest.get("controller_readiness")
                    if isinstance(latest.get("controller_readiness"), dict)
                    else {}
                )
                readiness_text = (
                    f" readiness={readiness.get('classification')}"
                    if readiness
                    else ""
                )
                lines.append(
                    "  - latest: "
                    f"{latest.get('generated_at')} "
                    f"classification={latest.get('classification')} "
                    f"phase={latest.get('lifecycle_phase')} "
                    f"artifacts={latest.get('json_exists')}/{latest.get('markdown_exists')}"
                    f"{reward_text}"
                    f"{operator_gate_text}"
                    f"{readiness_text}"
                )
                if reward:
                    _append_human_reward_markdown(lines, goal.get("id"), reward)
                resume_contract = (
                    latest.get("operator_gate_resume_contract")
                    if isinstance(latest.get("operator_gate_resume_contract"), dict)
                    else {}
                )
                if resume_contract:
                    _append_operator_gate_resume_contract_markdown(lines, resume_contract)

    for title, key in (("Errors", "errors"), ("Warnings", "warnings"), ("Checks", "checks")):
        entries = contract.get(key) if isinstance(contract.get(key), list) else []
        if entries:
            lines.extend(["", f"## {title}"])
            lines.extend(f"- {entry}" for entry in entries)

    findings = (
        global_registry.get("findings")
        if isinstance(global_registry.get("findings"), list)
        else []
    )
    if findings:
        lines.extend(["", "## Global Registry Findings"])
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                "- "
                f"{finding.get('severity')} "
                f"{finding.get('kind')} "
                f"goal={finding.get('goal_id') or finding.get('goal_ids') or 'global'}: "
                f"{finding.get('message')}"
            )
            if finding.get("recommended_action"):
                lines.append(f"  - action: {finding.get('recommended_action')}")

    return "\n".join(lines)
