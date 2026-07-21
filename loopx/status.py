from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .benchmark_adapters.skillsbench_verifier_bootstrap import (
    apply_skillsbench_verifier_bootstrap_missing_score_attribution,
)
from .benchmark_core import compact_benchmark_canonical_lifecycle
from .control_plane import compact_control_plane_policy
from .control_plane.status_collection import (
    StatusCollectionContext,
    collect_status as _collect_status_read_model,
)
from .control_plane.status_runtime_summaries import (
    StatusRuntimeSummaryContext,
    build_status_runtime_summaries as _build_status_runtime_summaries_read_model,
)
from .contract import check_contract
from .control_plane.work_items.delivery_batch_scale import (
    SMALL_DELIVERY_BATCH_SCALES as STRUCTURED_SMALL_DELIVERY_BATCH_SCALES,
    UNKNOWN_DELIVERY_BATCH_SCALE,
)
from .control_plane.work_items.delivery_outcome import (
    DELIVERY_OUTCOME_NOT_CONFIGURED,
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
)
from .control_plane.goals.goal_channel_projection import build_goal_channel_projection
from .handoff_budget import handoff_budget_contract
from .history import collect_history, load_registry
from .history import STATUS_NEUTRAL_CLASSIFICATIONS as HISTORY_STATUS_NEUTRAL_CLASSIFICATIONS
from .interface_budget import interface_budget_cadence_for_runs
from .long_task_cadence import build_long_task_cadence_hint
from .operator_gate import DEFAULT_OPERATOR_GATE, default_operator_question, normalize_operator_question
from .orchestration import compact_orchestration_policy
from .paths import global_registry_path, resolve_runtime_root
from .control_plane.work_items.task_graph import (
    build_task_graph_projection as _build_task_graph_projection_read_model,
)
from .control_plane.work_items.project_asset import (
    TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION as TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION,
    TODO_PROJECTION_VIEW_SCHEMA_VERSION as TODO_PROJECTION_VIEW_SCHEMA_VERSION,
    attach_active_state_project_asset_fields as _attach_active_state_project_asset_fields,
    build_project_asset,
    enrich_project_asset as _enrich_project_asset_read_model,
    project_asset_handoff_check_projection,
    project_asset_latest_validation,
    project_asset_quota_state,
    project_asset_quota_summary,
    project_asset_summary_is_public_safe as project_asset_summary_is_public_safe,
    project_asset_todo_projection_gap,
    project_asset_user_todo_open_count,
)
from .control_plane.todos.completed_archive import completed_todo_archive_warning
from .control_plane.handoff.project_handoff import (
    project_asset_handoff_readiness as _project_asset_handoff_readiness_read_model,
    project_asset_handoff_state as _project_asset_handoff_state_read_model,
)
from .control_plane.work_items.autonomous_candidates import (
    MAX_AUTONOMOUS_TODO_CANDIDATES as _MAX_AUTONOMOUS_TODO_CANDIDATES,
    autonomous_backlog_candidates as _autonomous_backlog_candidates_read_model,
    autonomous_monitor_candidates as _autonomous_monitor_candidates_read_model,
)
from .control_plane.agents.agent_lane_recommendation import (
    compact_agent_lane_recommendation as _compact_agent_lane_recommendation_read_model,
    is_status_neutral_run as _is_status_neutral_run_read_model,
    latest_agent_lane_run as _latest_agent_lane_run_read_model,
    latest_run_recommended_action_for_projection as _latest_run_recommended_action_for_projection_read_model,
)
from .control_plane.goals.active_state_sections import (
    active_state_section_entries as _active_state_section_entries_read_model,
    active_state_sections as _active_state_sections_read_model,
)
from .control_plane.goals.active_state_metadata import (
    parse_state_frontmatter,
)
from .control_plane.goals.active_state_event_projection import (
    active_state_event_projection_fields as _active_state_event_projection_fields_read_model,
    state_event_log_candidates as _state_event_log_candidates_read_model,
)
from .control_plane.todos.active_state_todos import (
    MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION as _MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION,
    active_state_todo_fields as _active_state_todo_fields_read_model,
)
from .control_plane.todos.active_state_todo_parser import (
    parse_active_state_todos,
)
from .control_plane.work_items.attention_item import (
    attention_item as _attention_item_read_model,
)
from .control_plane.work_items.attention_queue import (
    AttentionQueueContext,
    build_attention_queue as _build_attention_queue_read_model,
    build_attention_queue_projection as _build_attention_queue_projection_read_model,
    merge_global_registry_findings as _merge_global_registry_findings_read_model,
)
from .control_plane.work_items.attention_routing import (
    goal_attention as _goal_attention_read_model,
)
from .control_plane.work_items.attention_fields import (
    operator_gate_attention_fields as _operator_gate_attention_fields_read_model,
    readiness_attention_fields as _readiness_attention_fields_read_model,
)
from .control_plane.work_items.autonomous_replan_ack import (
    AUTONOMOUS_REPLAN_ACK_MATERIAL_RUN_WINDOW,
    autonomous_replan_ack_recorded,
    compact_autonomous_replan_ack,
    latest_autonomous_replan_ack_for_projection as _latest_autonomous_replan_ack_for_projection_read_model,
)
from .control_plane.work_items.autonomous_replan_obligation import (
    AUTONOMOUS_REPLAN_STALL_THRESHOLD as _AUTONOMOUS_REPLAN_STALL_THRESHOLD_READ_MODEL,
    AUTONOMOUS_REPLAN_TRIGGER_PATTERNS as _AUTONOMOUS_REPLAN_TRIGGER_PATTERNS_READ_MODEL,
    MAX_AUTONOMOUS_REPLAN_TRIGGERS as _MAX_AUTONOMOUS_REPLAN_TRIGGERS_READ_MODEL,
    autonomous_replan_obligation_from_state as _autonomous_replan_obligation_from_state_read_model,
    autonomous_replan_obligation_from_runs as _autonomous_replan_obligation_from_runs_read_model,
    autonomous_replan_periodic_review_from_runs as _autonomous_replan_periodic_review_from_runs_read_model,
    build_autonomous_replan_obligation as _build_autonomous_replan_obligation_read_model,
    run_history_monitor_wait_already_acknowledged as _run_history_monitor_wait_already_acknowledged_read_model,
    run_history_stall_signal as _run_history_stall_signal_read_model,
)
from .control_plane.work_items.backlog_hygiene import (
    MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS as _MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS_READ_MODEL,
    backlog_hygiene_warning as _backlog_hygiene_warning_read_model,
)
from .control_plane.goals.dreaming import (
    compact_dreaming_lane_badge as _compact_dreaming_lane_badge_read_model,
    compact_dreaming_proposal as _compact_dreaming_proposal_read_model,
    compact_server_planning_contract as _compact_server_planning_contract_read_model,
    dreaming_attention_fields as _dreaming_attention_fields_read_model,
)
from .control_plane.work_items.delivery_signals import (
    classification_contains_any as _classification_contains_any_read_model,
    delivery_batch_scale_for_run as _delivery_batch_scale_for_run_read_model,
    delivery_outcome_for_run as _delivery_outcome_for_run_read_model,
    outcome_floor_configured as _outcome_floor_configured_read_model,
    outcome_gap_streak as _outcome_gap_streak_read_model,
    small_delivery_batch_scale_streak as _small_delivery_batch_scale_streak_read_model,
)
from .control_plane.scheduler.monitor_display import (
    attention_item_is_monitor_quiet_display_candidate as _attention_item_is_monitor_quiet_display_candidate,
    normalize_monitor_quiet_attention_display as _normalize_monitor_quiet_attention_display,
    quiet_monitor_display_action as _quiet_monitor_display_action,
    todo_summary_lane_items as _todo_summary_lane_items,
    todo_summary_open_count as _todo_summary_open_count,
)
from .control_plane.runtime.run_compaction import (
    RUN_BASE_COMPACT_FIELDS,
    attach_run_summary_projections as _attach_run_summary_projections_read_model,
    compact_controller_readiness,
    compact_human_reward,
    compact_operator_gate,
    compact_operator_gate_resume_contract,
    compact_run_base as _compact_run_base_read_model,
)
from .control_plane.runtime.benchmark_projection import (
    benchmark_run_source as _benchmark_run_source_read_model,
    build_benchmark_solution_quality_signals,
    compact_benchmark_run_core as _compact_benchmark_run_core_read_model,
)
from .control_plane.runtime.benchmark_event_timeline import (
    compact_benchmark_case_event_timeline,
)
from .control_plane.runtime.benchmark_comparison import (
    benchmark_comparison_decision_note as _benchmark_comparison_decision_note_read_model,
    compact_benchmark_comparison as _compact_benchmark_comparison_read_model,
)
from .control_plane.runtime.benchmark_attempt_accounting import (
    compact_benchmark_attempt_accounting as _compact_benchmark_attempt_accounting,
)
from .control_plane.runtime.benchmark_experiment_report import (
    benchmark_experiment_report_readiness_note,
    benchmark_experiment_report_replay_decision,
    compact_benchmark_experiment_report,
)
from .control_plane.runtime.benchmark_learning_ledger import (
    compact_benchmark_learning_ledger,
)
from .control_plane.runtime.benchmark_result import compact_benchmark_result
from .control_plane.runtime.benchmark_lifecycle_contracts import (
    compact_app_server_goal_round_semantics as _compact_app_server_goal_round_semantics,
    compact_native_goal_worker_contract as _compact_native_goal_worker_contract,
    compact_product_mode_lifecycle_contract as _compact_product_mode_lifecycle_contract,
)
from .control_plane.runtime.benchmark_run_metrics import (
    compact_benchmark_overhead_attribution_counters as _compact_benchmark_overhead_attribution_counters,
    compact_benchmark_round_reward_trace as _compact_benchmark_round_reward_trace,
)
from .control_plane.runtime.goal_start_control_score import (
    compact_goal_start_product_mode_control_score,
)
from .control_plane.runtime.public_safety import (
    compact_loopx_command_records as _compact_loopx_command_records,
    compact_numeric_map as _compact_numeric_map,
    public_safe_compact_list,
    public_safe_compact_text,
)
from .control_plane.runtime.run_ingest_health import (
    compact_environment_setup_failure_context,
    compact_worker_bridge_outcome,
    worker_bridge_ingest_health_note,
)
from .control_plane.runtime.time import parse_timestamp
from .control_plane.runtime.run_history import (
    latest_run as _latest_run_read_model,
)
from .control_plane.runtime.decision_freshness import (
    DECISION_FRESHNESS_CLASSIFICATION_PREFIXES,
    DECISION_FRESHNESS_ITEM_LIMIT,
    DECISION_FRESHNESS_PROXY_NOTE,
    DECISION_FRESHNESS_WINDOW_DAYS,
)
from .control_plane.runtime.promotion_readiness import (
    PROMOTION_READINESS_PROXY_NOTE,
)
from .control_plane.handoff.handoff_runs import (
    is_custom_post_handoff_work_run as _is_custom_post_handoff_work_run_read_model,
    is_handoff_ready_run as _is_handoff_ready_run_read_model,
    run_has_external_evidence_watch_signal as _run_has_external_evidence_watch_signal_read_model,
)
from .control_plane.goals.global_registry_shadow import (
    attach_global_registry_shadow_finding,
)
from .control_plane.goals.global_registry_health import (
    collect_global_registry_health as _collect_global_registry_health_read_model,
)
from .control_plane.goals.path_resolution import resolve_goal_local_path, same_path
from .control_plane.goals.goal_channel import (
    attach_goal_channel_projection as _attach_goal_channel_projection_read_model,
)
from .control_plane.goals.goal_vision import (
    compact_goal_vision_packet as _compact_goal_vision_packet_read_model,
)
from .control_plane.work_items.issue_meta_surface import (
    parse_issue_meta_surface as _parse_issue_meta_surface_read_model,
)
from .control_plane.work_items.lifecycle import (
    goal_lifecycle_fields as _goal_lifecycle_fields_read_model,
    ordered_lifecycle_flags as _ordered_lifecycle_flags_read_model,
    primary_lifecycle_phase as _primary_lifecycle_phase_read_model,
    run_lifecycle_flags as _run_lifecycle_flags_read_model,
    run_lifecycle_phase as _run_lifecycle_phase_read_model,
)
from .control_plane.runtime.session_runtime import (
    compact_session_runtime_projection_from_run,
    legacy_runtime_goal_attention as _legacy_runtime_goal_attention_read_model,
)
from .control_plane.runtime.skillsbench_post_run_debug import (
    build_skillsbench_post_run_debug_gate,
)
from .control_plane.agents.subagent_activity import (
    MAX_SUBAGENT_ACTIVITY_ITEMS,
    compact_subagent_run,
    subagent_activity_for_goal,
)
from .control_plane.agents.management_projection import (
    build_agent_management_projection as _build_agent_management_projection_read_model,
)
from .control_plane.runtime.stale_latest_run import (
    stale_latest_run_projection_warning as _stale_latest_run_projection_warning_read_model,
)
from .control_plane.work_items.status_contract import (
    build_contract_health_projection as _build_contract_health_projection_read_model,
    build_status_contract as _build_status_contract_read_model,
)
from .control_plane.todos.todo_summary import (
    MAX_DEFERRED_TODO_VISIBILITY_ITEMS as _TODO_SUMMARY_MAX_DEFERRED_TODO_VISIBILITY_ITEMS,
    MAX_DEPENDENCY_BLOCKERS as _TODO_SUMMARY_MAX_DEPENDENCY_BLOCKERS,
    MAX_MONITOR_DUE_ITEMS as _TODO_SUMMARY_MAX_MONITOR_DUE_ITEMS,
    MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS as _TODO_SUMMARY_MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS,
    MAX_PROJECT_ASSET_TODO_ITEMS as _TODO_SUMMARY_MAX_PROJECT_ASSET_TODO_ITEMS,
    MAX_STATUS_TODOS_PER_ROLE as _TODO_SUMMARY_MAX_STATUS_TODOS_PER_ROLE,
    MAX_TODO_VISIBILITY_LANE_ITEMS as _TODO_SUMMARY_MAX_TODO_VISIBILITY_LANE_ITEMS,
    active_state_todo_attention_item as _active_state_todo_attention_item_read_model,
    active_next_action_todo_ids,
    attach_dependency_blockers,
    claimed_visibility_items as claimed_visibility_items,
    compact_todo_group as compact_todo_group,
    compact_todo_item as compact_todo_item,
    first_open_todo_text,
    normalize_todo_text,
    open_todo_items,
    project_asset_todo_summary,
    sync_connected_attention_action_from_todos as _sync_connected_attention_action_from_todos_read_model,
    todo_lane_items as todo_lane_items,
    todo_item_is_actionable_open,
    todo_item_is_deferred as todo_item_is_deferred,
    todo_item_is_due_monitor as todo_item_is_due_monitor,
    todo_item_missing_monitor_schedule as todo_item_missing_monitor_schedule,
    todo_item_next_due_at as todo_item_next_due_at,
    todo_item_task_class,
    todo_projection_sort_key as todo_projection_sort_key,
)
from .control_plane.todos.todo_index import (
    MAX_TODO_INDEX_ITEMS,
    MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
)
from .promotion_gate import build_promotion_gate
from .quota import quota_status, quota_with_handoff_outcome_floor
from .registry import registry_goals
from .rollout_event_log import load_rollout_events, rollout_event_log_path
from .state_projection import (
    active_state_next_action_entries,
    actions_are_projection_aligned,
    next_action_projection_warning,
    state_projection_gap_warning,
)
from .control_plane.todos.contract import (
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    normalize_todo_status,
    normalize_todo_task_class as normalize_todo_task_class,
    todo_done_for_status,
)
from .control_plane.todos.projection import (
    todo_item_is_expired_monitor as todo_item_is_expired_monitor,
)


_PUBLIC_COMPAT_REEXPORTS = {
    "TODO_PROJECTION_DETAIL_POINTER_SCHEMA_VERSION": "loopx.control_plane.work_items.project_asset",
    "TODO_PROJECTION_VIEW_SCHEMA_VERSION": "loopx.control_plane.work_items.project_asset",
    "project_asset_summary_is_public_safe": "loopx.control_plane.work_items.project_asset",
    "claimed_visibility_items": "loopx.control_plane.todos.todo_summary",
    "compact_todo_group": "loopx.control_plane.todos.todo_summary",
    "compact_todo_item": "loopx.control_plane.todos.todo_summary",
    "todo_lane_items": "loopx.control_plane.todos.todo_summary",
    "todo_item_is_deferred": "loopx.control_plane.todos.todo_summary",
    "todo_item_is_due_monitor": "loopx.control_plane.todos.todo_summary",
    "todo_item_missing_monitor_schedule": "loopx.control_plane.todos.todo_summary",
    "todo_item_next_due_at": "loopx.control_plane.todos.todo_summary",
    "todo_projection_sort_key": "loopx.control_plane.todos.todo_summary",
    "normalize_todo_task_class": "loopx.control_plane.todos.contract",
    "todo_item_is_expired_monitor": "loopx.control_plane.todos.projection",
}


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
BENCHMARK_RUN_SCHEMA_VERSION = "benchmark_run_v0"
ACTIVE_USER_ASSISTED_PILOT_SCHEMA_VERSION = "active_user_assisted_pilot_v0"
OPERATOR_SIMULATOR_RUN_SCHEMA_VERSION = "operator_simulator_run_v0"
MAX_BENCHMARK_RUN_TRIALS = 3
MAX_BENCHMARK_RUN_LIST_ITEMS = 5
STATUS_CONTRACT_SCHEMA_VERSION = 2
MINIMUM_DASHBOARD_STATUS_CONTRACT_SCHEMA_VERSION = 2
STATUS_CONTRACT_RELOAD_HINT = "scripts/macos-dashboard-launchagent.sh restart"
STATUS_CONTRACT_SIGNAL_LIMIT = 3
MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION = _MONITOR_WRITEBACK_CONTRACT_SCHEMA_VERSION
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
RUN_COMPACT_FIELDS = RUN_BASE_COMPACT_FIELDS
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
MAX_STATUS_TODOS_PER_ROLE = _TODO_SUMMARY_MAX_STATUS_TODOS_PER_ROLE
MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE = MAX_STATUS_TODOS_PER_ROLE
MAX_PROJECT_ASSET_TODO_ITEMS = _TODO_SUMMARY_MAX_PROJECT_ASSET_TODO_ITEMS
MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS = _TODO_SUMMARY_MAX_PROJECT_ASSET_TODO_BACKLOG_ITEMS
MAX_TODO_VISIBILITY_LANE_ITEMS = _TODO_SUMMARY_MAX_TODO_VISIBILITY_LANE_ITEMS
MAX_DEFERRED_TODO_VISIBILITY_ITEMS = _TODO_SUMMARY_MAX_DEFERRED_TODO_VISIBILITY_ITEMS
MAX_MONITOR_DUE_ITEMS = _TODO_SUMMARY_MAX_MONITOR_DUE_ITEMS
MAX_DEPENDENCY_BLOCKERS = _TODO_SUMMARY_MAX_DEPENDENCY_BLOCKERS
MAX_AUTONOMOUS_BACKLOG_CANDIDATES = _MAX_AUTONOMOUS_TODO_CANDIDATES
MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS = _MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS_READ_MODEL
MAX_AUTONOMOUS_REPLAN_TRIGGERS = _MAX_AUTONOMOUS_REPLAN_TRIGGERS_READ_MODEL
AUTONOMOUS_REPLAN_STALL_THRESHOLD = _AUTONOMOUS_REPLAN_STALL_THRESHOLD_READ_MODEL
DEAD_MONITOR_REPEAT_THRESHOLD = 6
AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD = AUTONOMOUS_REPLAN_ACK_MATERIAL_RUN_WINDOW
AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK = 30
BACKLOG_HYGIENE_SECTION_HEADINGS = ("Next Action", "Operating Lessons")
BACKLOG_HYGIENE_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
BACKLOG_HYGIENE_HINT_PATTERN = re.compile(
    r"(?i)(?:\[p[0-4]\]|todo|backlog|follow[- ]?up|queue|audit|regression|smoke|cadence|mirror|monitor|sub-?agent|待办|回归|审计|修复|检查|推进)"
)
AUTONOMOUS_REPLAN_SCHEMA_VERSION = "autonomous_replan_obligation_v0"
DEAD_MONITOR_REPEAT_SCHEMA_VERSION = "dead_monitor_repeat_v0"
AUTONOMOUS_REPLAN_SECTION_HEADINGS = (
    "Next Action",
    "Operating Lessons",
)
AUTONOMOUS_REPLAN_TRIGGER_PATTERNS = _AUTONOMOUS_REPLAN_TRIGGER_PATTERNS_READ_MODEL
AUTONOMOUS_RUN_HISTORY_PROGRESS_OUTCOMES = PROGRESS_DELIVERY_OUTCOMES
AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS = {
    "quota_slot_spent",
    "quota_slot_voided",
    "delivery_completion_spend_accounted_v0",
}
AUTONOMOUS_RUN_HISTORY_STALL_PATTERN = re.compile(
    r"(?i)(?:monitor|observe|observation|poll|watch|quiet|no[-_ ]?op|no[-_ ]?progress|stalled?|unchanged|dependency|停转|无进展|重复|反复|观察|轮询)"
)


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
        "product_mode_typed_repair_required",
        "product_mode_typed_repair_pending",
        "product_mode_typed_repair_todo_identity_observed",
        "product_mode_typed_repair_task_or_validation_delta",
        "product_mode_typed_repair_delta_observed",
        "product_mode_typed_repair_terminal",
        "product_mode_typed_repair_terminal_receipt_consistent",
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
        "product_mode_typed_repair_trigger_round",
        "product_mode_typed_repair_round_entered",
        "product_mode_typed_repair_round_entered_count",
        "product_mode_typed_repair_resolved_round",
        "product_mode_typed_repair_task_facing_success_delta",
        "product_mode_typed_repair_terminal_round",
        "product_mode_typed_repair_open_todo_count_public",
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
        "native_goal_worker_normal_followup_attempted_count",
        "native_goal_worker_normal_followup_succeeded_count",
        "native_goal_worker_normal_followup_start_attempted_count",
        "native_goal_worker_normal_followup_start_succeeded_count",
        "native_goal_worker_finish_guard_followup_attempted_count",
        "native_goal_worker_finish_guard_followup_succeeded_count",
        "native_goal_worker_finish_guard_followup_start_attempted_count",
        "native_goal_worker_finish_guard_followup_start_succeeded_count",
        "native_goal_worker_incomplete_turn_status_count",
        "native_goal_worker_incomplete_after_completion_event_count",
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
        "host_local_acp_codex_exec_recoverable_failure_trace_count",
        "host_local_acp_codex_exec_fatal_failure_trace_count",
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
        "product_mode_typed_repair_policy_id",
        "product_mode_typed_repair_terminal_reason",
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
        "loopx_runner_source_fingerprint_status",
        "loopx_runner_source_first_blocker",
        "loopx_runner_source_git_head",
        "loopx_runner_source_expected_git_head",
        "loopx_runner_source_error_kind",
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
        "goal_start_guided_command_required",
        "goal_start_agent_authored_plan_required",
        "goal_start_host_preseed_forbidden",
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
        "loopx_runner_source_git_head_recorded",
        "loopx_runner_source_expected_git_head_recorded",
        "loopx_runner_source_matches_expected",
        "loopx_runner_source_path_recorded",
        "loopx_runner_source_raw_git_output_recorded",
    ):
        if isinstance(value.get(field), bool):
            compact[field] = value[field]
    lifecycle = compact_benchmark_canonical_lifecycle(
        value.get("benchmark_canonical_lifecycle")
    )
    if lifecycle:
        compact["benchmark_canonical_lifecycle"] = lifecycle
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
        "benchflow_final_verifier_outer_timeout_override_count",
        "benchflow_verifier_prep_timeout_override_count",
        "benchflow_verify_prep_timeout_override_count",
        "benchflow_soft_verify_prep_timeout_override_count",
        "benchflow_setup_stall_timeout_requested_sec",
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
        "canonical_equivalent_status",
        "registry_source_kind",
        "registry_source_status",
        "registry_task_path",
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
        "registry_task_present",
        "registry_task_path_recorded",
        "registry_excluded",
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
        "primary_setup_failure_category",
        "apt_failure_subtype",
        "pip_failure_subtype",
        "retryability",
        "next_diagnostic_action",
    ):
        text = public_safe_compact_text(value.get(field), limit=180)
        if text:
            compact[field] = text
    for field in (
        "compose_setup_failure",
        "unclassified_compose_failure",
        "docker_daemon_unavailable",
        "apt_repository_failure",
        "pip_bootstrap_failure",
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
        "setup_stall_timeout_requested_sec",
        "setup_stall_timeout_sec",
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
    for field in (
        "terminal_failure_dependency_classes",
        "terminal_failure_reason_codes",
        "terminal_failure_dependency_endpoints",
    ):
        values = public_safe_compact_list(
            value.get(field),
            limit=MAX_BENCHMARK_RUN_LIST_ITEMS * 2,
        )
        if values:
            compact[field] = values
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


def _sync_skillsbench_runner_failure_root_blockers(
    compact: dict[str, Any],
) -> None:
    runner_failure = compact.get("runner_failure")
    if not isinstance(runner_failure, dict):
        return
    if not _skillsbench_compact_official_score_missing(compact):
        return

    blocker = public_safe_compact_text(
        compact.get("score_failure_attribution"),
        limit=140,
    )
    if blocker in {None, "none", "score_missing"}:
        blocker = public_safe_compact_text(
            runner_failure.get("failure_class"),
            limit=140,
        )
    if not blocker:
        return

    replaceable = {
        None,
        "none",
        "score_missing",
        "skillsbench_runner_error",
    }
    for field in ("first_blocker", "repeat_blocked_by"):
        if compact.get(field) in replaceable:
            compact[field] = blocker


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


def _mark_skillsbench_pre_task_attempt_accounting(
    compact: dict[str, Any],
    *,
    failure_label: str,
) -> None:
    attempt_accounting = compact.get("attempt_accounting")
    if not isinstance(attempt_accounting, dict):
        return
    attempt_accounting["lifecycle_phase"] = "runner_accepted_args"
    attempt_accounting["failure_label"] = failure_label
    attempt_accounting["failure_class"] = "job_materialization_failed"
    attempt_accounting["launcher_attempt_countable"] = True
    for field in (
        "case_attempt_countable",
        "solver_attempt_countable",
        "verifier_attempt_countable",
        "official_score_attempt_countable",
    ):
        attempt_accounting[field] = False
    attempts = attempt_accounting.get("attempts")
    if not isinstance(attempts, dict):
        return
    launcher = attempts.get("launcher")
    if isinstance(launcher, dict):
        launcher["attempted"] = True
        launcher["countable"] = True
    for phase_name in ("case", "solver", "verifier", "official_score"):
        phase = attempts.get(phase_name)
        if isinstance(phase, dict):
            phase["attempted"] = False
            phase["countable"] = False


def _apply_skillsbench_benchmark_egress_preflight_compact_projection(
    compact: dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
) -> None:
    source = source if isinstance(source, dict) else {}
    source_runner_config = (
        source.get("runner_config")
        if isinstance(source.get("runner_config"), dict)
        else {}
    )
    proxy_required = (
        compact.get("benchmark_egress_proxy_required") is True
        or source_runner_config.get("benchmark_egress_proxy_required") is True
    )
    proxy_ready = (
        compact.get("benchmark_egress_proxy_ready") is True
        or source_runner_config.get("benchmark_egress_proxy_ready") is True
    )
    proxy_status = public_safe_compact_text(
        compact.get("benchmark_egress_proxy_status")
        or source_runner_config.get("benchmark_egress_proxy_status"),
        limit=120,
    )
    benchmark_failure_statuses = {
        "failed",
        "invalid_proxy_value",
        "missing_required_proxy",
        "proxy_auth_required",
        "proxy_connect_rejected",
        "unsupported_proxy_scheme",
    }
    benchmark_blocked = bool(
        proxy_required
        and not proxy_ready
        and proxy_status in benchmark_failure_statuses
    )
    codex_required = (
        compact.get("codex_api_egress_preflight_required") is True
        or source_runner_config.get("codex_api_egress_preflight_required") is True
    )
    codex_ready = (
        compact.get("codex_api_egress_preflight_ready") is True
        or source_runner_config.get("codex_api_egress_preflight_ready") is True
    )
    codex_status = public_safe_compact_text(
        compact.get("codex_api_egress_preflight_status")
        or source_runner_config.get("codex_api_egress_preflight_status"),
        limit=120,
    )
    codex_failure_statuses = {
        "failed",
        "missing_reverse_tunnel_proxy",
        "proxy_auth_required",
        "proxy_connect_rejected",
        "unsupported_egress_mode",
        "unsupported_proxy_scheme",
    }
    codex_blocked = bool(
        codex_required and not codex_ready and codex_status in codex_failure_statuses
    )
    if not benchmark_blocked and not codex_blocked:
        return
    if not _skillsbench_compact_official_score_missing(compact):
        return

    if benchmark_blocked:
        label = "skillsbench_benchmark_egress_proxy_preflight_blocked"
        status_label = f"skillsbench_benchmark_egress_proxy_{proxy_status}"
        blocker_key = "benchmark_egress_proxy_preflight_blocked"
    else:
        label = "skillsbench_codex_api_egress_preflight_blocked"
        status_label = f"skillsbench_codex_api_egress_{codex_status}"
        blocker_key = "codex_api_egress_preflight_blocked"
    compact["score_failure_attribution"] = label
    compact["first_blocker"] = label
    compact["repeat_blocked_by"] = label
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False

    labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str)
        and item
        and item
        not in {
            "skillsbench_product_mode_uncountable_treatment",
            "skillsbench_remote_bridge_agent_operation_trace_missing",
            "skillsbench_verifier_package_install_risk",
            "skillsbench_verifier_uv_install_or_download_failure",
            "verifier_dependency_install_failure",
        }
    ]
    primary_labels = (
        label,
        "skillsbench_environment_setup_error",
        status_label,
    )
    labels = list(primary_labels) + [
        item for item in labels if item not in primary_labels
    ]
    compact["failure_attribution_labels"] = labels[:MAX_BENCHMARK_RUN_LIST_ITEMS]

    _mark_skillsbench_pre_task_attempt_accounting(
        compact,
        failure_label=label,
    )
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = label
        runner_failure[blocker_key] = True

    validation = (
        compact.get("validation")
        if isinstance(compact.get("validation"), dict)
        else {}
    )
    validation[blocker_key] = True
    validation["raw_verifier_output_read"] = False
    validation["all_passed"] = False
    compact["validation"] = validation

    if benchmark_blocked:
        compact["benchmark_egress_proxy_diagnostic"] = {
            "schema_version": "skillsbench_benchmark_egress_proxy_diagnostic_v0",
            "status": "benchmark_egress_proxy_preflight_blocked",
            "score_failure_attribution": label,
            "proxy_required": True,
            "proxy_ready": False,
            "proxy_status": proxy_status,
            "proxy_error_kind": public_safe_compact_text(
                compact.get("benchmark_egress_proxy_error_kind")
                or source_runner_config.get("benchmark_egress_proxy_error_kind"),
                limit=120,
            ),
            "proxy_mode_requested": public_safe_compact_text(
                compact.get("benchmark_egress_proxy_mode_requested")
                or source_runner_config.get("benchmark_egress_proxy_mode_requested"),
                limit=80,
            ),
            "proxy_mode_effective": public_safe_compact_text(
                compact.get("benchmark_egress_proxy_mode_effective")
                or source_runner_config.get("benchmark_egress_proxy_mode_effective"),
                limit=80,
            ),
            "proxy_url_recorded": False,
            "raw_logs_read": False,
            "raw_task_text_read": False,
            "raw_trajectory_read": False,
            "next_diagnostic_action": (
                "configure_valid_private_benchmark_egress_proxy"
            ),
        }
        return

    compact["codex_api_egress_diagnostic"] = {
        "schema_version": "skillsbench_codex_api_egress_diagnostic_v0",
        "status": "codex_api_egress_preflight_blocked",
        "score_failure_attribution": label,
        "egress_required": True,
        "egress_ready": False,
        "egress_status": codex_status,
        "egress_error_kind": public_safe_compact_text(
            compact.get("codex_api_egress_preflight_error_kind")
            or source_runner_config.get("codex_api_egress_preflight_error_kind"),
            limit=120,
        ),
        "egress_mode_requested": public_safe_compact_text(
            compact.get("codex_api_egress_mode_requested")
            or source_runner_config.get("codex_api_egress_mode_requested"),
            limit=80,
        ),
        "egress_mode_effective": public_safe_compact_text(
            compact.get("codex_api_egress_mode_resolved")
            or source_runner_config.get("codex_api_egress_mode_resolved"),
            limit=80,
        ),
        "reverse_tunnel_required": (
            compact.get("codex_api_reverse_tunnel_required") is True
            or source_runner_config.get("codex_api_reverse_tunnel_required") is True
        ),
        "proxy_url_recorded": False,
        "raw_logs_read": False,
        "raw_task_text_read": False,
        "raw_trajectory_read": False,
        "next_diagnostic_action": "restore_required_private_egress_then_retry",
    }


def _apply_skillsbench_runner_source_fingerprint_compact_projection(
    compact: dict[str, Any],
    *,
    source: dict[str, Any] | None = None,
) -> None:
    source = source if isinstance(source, dict) else {}
    prerequisites = (
        compact.get("runner_prerequisites")
        if isinstance(compact.get("runner_prerequisites"), dict)
        else {}
    )
    source_config = (
        source.get("runner_config")
        if isinstance(source.get("runner_config"), dict)
        else {}
    )
    status = public_safe_compact_text(
        prerequisites.get("loopx_runner_source_fingerprint_status")
        or source_config.get("loopx_runner_source_fingerprint_status"),
        limit=80,
    )
    blocker = public_safe_compact_text(
        prerequisites.get("loopx_runner_source_first_blocker")
        or source_config.get("loopx_runner_source_first_blocker"),
        limit=120,
    )
    if (
        status != "mismatched_expected"
        or blocker != "loopx_runner_source_git_head_mismatch"
        or not _skillsbench_compact_official_score_missing(compact)
    ):
        return

    compact["score_failure_attribution"] = blocker
    compact["first_blocker"] = blocker
    compact["repeat_blocked_by"] = blocker
    compact["official_score_comparable_to_native_codex"] = False
    compact["official_score_comparable_to_loopx_treatment"] = False

    verifier_labels = {
        "verifier_dependency_bootstrap_timeout",
        "verifier_dependency_install_failure",
        "verifier_uv_install_or_download_failure",
        "skillsbench_verifier_bootstrap_missing_official_score",
        "skillsbench_verifier_bootstrap_preflight_blocked",
        "skillsbench_verifier_package_install_risk",
    }
    labels = [
        item
        for item in compact.get("failure_attribution_labels", [])
        if isinstance(item, str) and item and item not in verifier_labels
    ]
    primary_labels = (
        blocker,
        "skillsbench_runner_source_fingerprint_mismatch",
        "skillsbench_runner_setup_error",
    )
    labels = list(primary_labels) + [
        item for item in labels if item not in primary_labels
    ]
    compact["failure_attribution_labels"] = labels[:MAX_BENCHMARK_RUN_LIST_ITEMS]

    _mark_skillsbench_pre_task_attempt_accounting(
        compact,
        failure_label=blocker,
    )
    runner_failure = compact.get("runner_failure")
    if isinstance(runner_failure, dict):
        runner_failure["failure_class"] = blocker
        runner_failure["runner_source_fingerprint_mismatch"] = True

    validation = (
        compact.get("validation")
        if isinstance(compact.get("validation"), dict)
        else {}
    )
    validation["runner_source_fingerprint_mismatch"] = True
    validation["all_passed"] = False
    compact["validation"] = validation

    compose_setup_diagnostic = compact.get("compose_setup_diagnostic")
    if isinstance(compose_setup_diagnostic, dict):
        compose_setup_diagnostic["case_attempt_budget_should_count"] = False


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


def compact_benchmark_run(run: dict[str, Any]) -> dict[str, Any] | None:
    source = _benchmark_run_source_read_model(
        run,
        schema_version=BENCHMARK_RUN_SCHEMA_VERSION,
    )
    if not source:
        return None

    trials_source = (
        source.get("trials") if isinstance(source.get("trials"), list) else []
    )
    compact = _compact_benchmark_run_core_read_model(
        source,
        schema_version=BENCHMARK_RUN_SCHEMA_VERSION,
        max_list_items=MAX_BENCHMARK_RUN_LIST_ITEMS,
    )
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
            "apt_failure_subtype",
            "pip_failure_subtype",
            "retryability",
        ):
            value = public_safe_compact_text(fingerprint.get(field), limit=100)
            if value:
                compact_fingerprint[field] = value
        line_count = fingerprint.get("line_count")
        if isinstance(line_count, int) and not isinstance(line_count, bool):
            compact_fingerprint["line_count"] = line_count
        for field, limit in (
            ("matched_patterns", MAX_BENCHMARK_RUN_LIST_ITEMS * 4),
            ("failure_line_dependency_classes", MAX_BENCHMARK_RUN_LIST_ITEMS * 2),
            ("failure_reason_codes", MAX_BENCHMARK_RUN_LIST_ITEMS * 2),
            (
                "terminal_failure_dependency_classes",
                MAX_BENCHMARK_RUN_LIST_ITEMS * 2,
            ),
            ("terminal_failure_reason_codes", MAX_BENCHMARK_RUN_LIST_ITEMS * 2),
            ("failure_dependency_endpoints", MAX_BENCHMARK_RUN_LIST_ITEMS * 2),
            (
                "terminal_failure_dependency_endpoints",
                MAX_BENCHMARK_RUN_LIST_ITEMS * 2,
            ),
        ):
            values = public_safe_compact_list(fingerprint.get(field), limit=limit)
            if values:
                compact_fingerprint[field] = values
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

    goal_start_control_score = compact_goal_start_product_mode_control_score(
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

    case_event_timeline = compact_benchmark_case_event_timeline(
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

    env_context = compact_environment_setup_failure_context(
        source.get("environment_setup_failure_context")
    )
    if env_context:
        compact["environment_setup_failure_context"] = env_context

    worker_bridge_outcome = compact_worker_bridge_outcome(
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

    _apply_skillsbench_runner_source_fingerprint_compact_projection(
        compact,
        source=source,
    )
    _apply_skillsbench_benchmark_egress_preflight_compact_projection(
        compact,
        source=source,
    )
    apply_skillsbench_verifier_bootstrap_missing_score_attribution(
        compact,
        task_staging=compact.get("task_staging"),
        setup_preflight=compact.get("task_setup_preflight"),
    )

    _sync_skillsbench_runner_failure_root_blockers(compact)

    if solution_quality := build_benchmark_solution_quality_signals(compact):
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
        env_context = compact_environment_setup_failure_context(
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


def state_event_log_candidates(goal: dict[str, Any], *, state_path: Path) -> list[Path]:
    return _state_event_log_candidates_read_model(
        goal,
        state_path=state_path,
        resolve_goal_local_path=resolve_goal_local_path,
        event_log_basename=STATE_EVENT_LOG_BASENAME,
    )


def active_state_event_projection_fields(
    goal: dict[str, Any],
    *,
    state_path: Path,
    preferred_todo_ids: set[str] | None = None,
    rollout_events: list[dict[str, Any]] | None = None,
    item_limit: int | None = MAX_STATUS_TODOS_PER_ROLE,
) -> dict[str, Any]:
    return _active_state_event_projection_fields_read_model(
        goal,
        state_path=state_path,
        resolve_goal_local_path=resolve_goal_local_path,
        parse_active_state_todos=parse_active_state_todos,
        preferred_todo_ids=preferred_todo_ids,
        rollout_events=rollout_events,
        item_limit=item_limit,
        event_log_basename=STATE_EVENT_LOG_BASENAME,
    )


def active_state_sections(state_text: str, headings: tuple[str, ...]) -> dict[str, list[str]]:
    return _active_state_sections_read_model(
        state_text,
        headings,
        section_heading_pattern=SECTION_HEADING_PATTERN,
    )


def parse_issue_meta_surface(state_text: str) -> dict[str, Any] | None:
    return _parse_issue_meta_surface_read_model(
        state_text,
        section_parser=active_state_sections,
        public_safe_compact_text=public_safe_compact_text,
    )


def active_state_section_entries(lines: list[str]) -> list[str]:
    return _active_state_section_entries_read_model(
        lines,
        bullet_pattern=BACKLOG_HYGIENE_BULLET_PATTERN,
        normalize_text=normalize_todo_text,
    )


def backlog_hygiene_warning(state_text: str, *, agent_todos: dict[str, Any] | None) -> dict[str, Any] | None:
    return _backlog_hygiene_warning_read_model(
        state_text,
        agent_todos=agent_todos,
        section_headings=BACKLOG_HYGIENE_SECTION_HEADINGS,
        section_parser=active_state_sections,
        bullet_pattern=BACKLOG_HYGIENE_BULLET_PATTERN,
        hint_pattern=BACKLOG_HYGIENE_HINT_PATTERN,
        public_safe_compact_text=public_safe_compact_text,
        max_evidence_items=MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS,
    )


def autonomous_replan_obligation(
    state_text: str,
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _autonomous_replan_obligation_from_state_read_model(
        state_text,
        agent_todos=agent_todos,
        section_headings=AUTONOMOUS_REPLAN_SECTION_HEADINGS,
        section_parser=active_state_sections,
        section_entries=active_state_section_entries,
        public_safe_compact_text=public_safe_compact_text,
        build_autonomous_replan_obligation=build_autonomous_replan_obligation,
    )


def build_autonomous_replan_obligation(
    evidence: list[dict[str, Any]],
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _build_autonomous_replan_obligation_read_model(
        evidence,
        agent_todos=agent_todos,
        public_safe_compact_text=public_safe_compact_text,
        autonomous_replan_schema_version=AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        autonomous_replan_stall_threshold=AUTONOMOUS_REPLAN_STALL_THRESHOLD,
        dead_monitor_repeat_threshold=DEAD_MONITOR_REPEAT_THRESHOLD,
        dead_monitor_repeat_schema_version=DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
    )


def _run_history_stall_signal(run: dict[str, Any]) -> dict[str, Any] | None:
    return _run_history_stall_signal_read_model(
        run,
        autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
        neutral_classifications=AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS,
        progress_outcomes=AUTONOMOUS_RUN_HISTORY_PROGRESS_OUTCOMES,
        stall_pattern=AUTONOMOUS_RUN_HISTORY_STALL_PATTERN,
        public_safe_compact_text=public_safe_compact_text,
        normalize_delivery_outcome=normalize_delivery_outcome,
    )


def run_history_monitor_wait_already_acknowledged(
    latest_runs: list[dict[str, Any]] | None,
    *,
    signal_count: int,
) -> bool:
    return _run_history_monitor_wait_already_acknowledged_read_model(
        latest_runs,
        signal_count=signal_count,
        autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
        neutral_classifications=AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS,
    )


def latest_autonomous_replan_ack_for_projection(
    latest_runs: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    return _latest_autonomous_replan_ack_for_projection_read_model(
        latest_runs,
        neutral_classifications=AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS,
    )


def autonomous_replan_periodic_review_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _autonomous_replan_periodic_review_from_runs_read_model(
        latest_runs,
        agent_todos=agent_todos,
        autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
        neutral_classifications=AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS,
        periodic_run_threshold=AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD,
        build_autonomous_replan_obligation=build_autonomous_replan_obligation,
    )


def autonomous_replan_obligation_from_runs(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_todos: dict[str, Any] | None,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    return _autonomous_replan_obligation_from_runs_read_model(
        latest_runs,
        agent_todos=agent_todos,
        agent_id=agent_id,
        autonomous_replan_ack_recorded=autonomous_replan_ack_recorded,
        neutral_classifications=AUTONOMOUS_RUN_HISTORY_NEUTRAL_CLASSIFICATIONS,
        progress_outcomes=AUTONOMOUS_RUN_HISTORY_PROGRESS_OUTCOMES,
        stall_pattern=AUTONOMOUS_RUN_HISTORY_STALL_PATTERN,
        public_safe_compact_text=public_safe_compact_text,
        normalize_delivery_outcome=normalize_delivery_outcome,
        build_autonomous_replan_obligation=build_autonomous_replan_obligation,
        autonomous_replan_stall_threshold=AUTONOMOUS_REPLAN_STALL_THRESHOLD,
        dead_monitor_repeat_threshold=DEAD_MONITOR_REPEAT_THRESHOLD,
        dead_monitor_repeat_schema_version=DEAD_MONITOR_REPEAT_SCHEMA_VERSION,
        periodic_run_threshold=AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD,
    )


def autonomous_backlog_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    return _autonomous_backlog_candidates_read_model(
        items,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        normalize_todo_text=normalize_todo_text,
        advancement_task_class=TODO_TASK_CLASS_ADVANCEMENT,
        limit=limit,
    )


def autonomous_monitor_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    return _autonomous_monitor_candidates_read_model(
        items,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        normalize_todo_text=normalize_todo_text,
        monitor_task_class=TODO_TASK_CLASS_MONITOR,
        monitor_signal_waiting_on=MONITOR_SIGNAL_WAITING_ON,
        limit=limit,
    )


def build_attention_queue_projection(
    *,
    items: list[dict[str, Any]],
    goal_id_filter: str | None,
    autonomous_backlog_candidates: dict[str, Any] | None,
    autonomous_monitor_candidates: dict[str, Any] | None,
) -> dict[str, Any]:
    return _build_attention_queue_projection_read_model(
        items=items,
        goal_id_filter=goal_id_filter,
        autonomous_backlog_candidates=autonomous_backlog_candidates,
        autonomous_monitor_candidates=autonomous_monitor_candidates,
        monitor_signal_waiting_on=MONITOR_SIGNAL_WAITING_ON,
    )


def active_state_projection_warning(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any] | None:
    return _stale_latest_run_projection_warning_read_model(
        goal,
        current_run,
        agent_lane_progress_scope=AGENT_LANE_PROGRESS_SCOPE,
        resolve_goal_local_path=lambda raw, goal_value: resolve_goal_local_path(
            raw,
            goal_value,
            fallback_base=Path.cwd(),
        ),
        parse_state_frontmatter=parse_state_frontmatter,
        parse_timestamp=parse_timestamp,
    )


def is_handoff_ready_run(run: dict[str, Any]) -> bool:
    return _is_handoff_ready_run_read_model(
        run,
        handoff_ready_classifications=HANDOFF_READY_CLASSIFICATIONS,
        compact_operator_gate=compact_operator_gate,
    )


def run_has_external_evidence_watch_signal(run: dict[str, Any]) -> bool:
    """Return true only for explicit external-evidence watch state.

    Feature names may legitimately start with words such as "monitor"; routing
    to an external-evidence wait must come from structured state or explicit
    legacy external-evidence classifications, not broad classification prefixes.
    """

    return _run_has_external_evidence_watch_signal_read_model(
        run,
        legacy_external_evidence_classification_prefixes=LEGACY_EXTERNAL_EVIDENCE_CLASSIFICATION_PREFIXES,
    )


def is_custom_post_handoff_work_run(run: dict[str, Any]) -> bool:
    return _is_custom_post_handoff_work_run_read_model(
        run,
        is_status_neutral_run=is_status_neutral_run,
        is_handoff_ready_run=is_handoff_ready_run,
        run_has_external_evidence_watch_signal=run_has_external_evidence_watch_signal,
        codex_ready_classifications=CODEX_READY_CLASSIFICATIONS,
        user_or_controller_classifications=USER_OR_CONTROLLER_CLASSIFICATIONS,
        blocking_classifications=BLOCKING_CLASSIFICATIONS,
    )


def delivery_batch_scale_for_run(run: dict[str, Any]) -> str:
    return _delivery_batch_scale_for_run_read_model(
        run,
        test_only_hints=DELIVERY_BATCH_SCALE_TEST_ONLY_CLASSIFICATION_HINTS,
        multi_surface_hints=DELIVERY_BATCH_SCALE_MULTI_SURFACE_CLASSIFICATION_HINTS,
        implementation_hints=DELIVERY_BATCH_SCALE_IMPLEMENTATION_CLASSIFICATION_HINTS,
    )


def _classification_contains_any(classification: str, hints: list[Any]) -> bool:
    return _classification_contains_any_read_model(classification, hints)


def delivery_outcome_for_run(run: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    return _delivery_outcome_for_run_read_model(
        run,
        profile,
        execution_profile_outcome_floor=execution_profile_outcome_floor,
    )


def outcome_floor_configured(profile: dict[str, Any] | None) -> bool:
    return _outcome_floor_configured_read_model(
        profile,
        execution_profile_outcome_floor=execution_profile_outcome_floor,
    )


def outcome_gap_streak(runs: list[dict[str, Any]], profile: dict[str, Any] | None = None) -> int:
    return _outcome_gap_streak_read_model(
        runs,
        profile,
        delivery_outcome_for_run=delivery_outcome_for_run,
        outcome_floor_configured=outcome_floor_configured,
    )


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
    return _attach_run_summary_projections_read_model(
        compact,
        run,
        compact_benchmark_run=compact_benchmark_run,
        worker_bridge_ingest_health_note=worker_bridge_ingest_health_note,
        compact_benchmark_result=compact_benchmark_result,
        compact_benchmark_comparison=_compact_benchmark_comparison_read_model,
        benchmark_comparison_decision_note=_benchmark_comparison_decision_note_read_model,
        compact_benchmark_learning_ledger=compact_benchmark_learning_ledger,
        compact_benchmark_experiment_report=compact_benchmark_experiment_report,
        benchmark_experiment_report_readiness_note=(
            benchmark_experiment_report_readiness_note
        ),
        benchmark_experiment_report_replay_decision=(
            benchmark_experiment_report_replay_decision
        ),
        compact_active_user_assisted_pilot=compact_active_user_assisted_pilot,
        compact_session_runtime_projection_from_run=(
            compact_session_runtime_projection_from_run
        ),
    )


def small_delivery_batch_scale_streak(runs: list[dict[str, Any]]) -> int:
    return _small_delivery_batch_scale_streak_read_model(
        runs,
        delivery_batch_scale_for_run=delivery_batch_scale_for_run,
        small_delivery_batch_scales=SMALL_DELIVERY_BATCH_SCALES,
    )


def project_asset_handoff_state(
    *,
    ready: bool,
    project_asset: dict[str, Any],
    latest_runs: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return _project_asset_handoff_state_read_model(
        ready=ready,
        project_asset=project_asset,
        latest_runs=latest_runs,
        compact_execution_profile=compact_execution_profile,
        parse_timestamp=parse_timestamp,
        is_handoff_ready_run=is_handoff_ready_run,
        is_custom_post_handoff_work_run=is_custom_post_handoff_work_run,
        is_status_neutral_run=is_status_neutral_run,
        compact_post_handoff_run=compact_post_handoff_run,
        small_delivery_batch_scale_streak=small_delivery_batch_scale_streak,
        outcome_floor_configured=outcome_floor_configured,
        outcome_gap_streak=outcome_gap_streak,
    )


def project_asset_handoff_readiness(
    item: dict[str, Any],
    *,
    latest_runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    return _project_asset_handoff_readiness_read_model(
        item,
        latest_runs=latest_runs,
        project_asset_handoff_check_projection=project_asset_handoff_check_projection,
        handoff_budget_contract=handoff_budget_contract,
        project_asset_handoff_state=project_asset_handoff_state,
    )


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
    _enrich_project_asset_read_model(
        item,
        user_todos=user_todos,
        agent_todos=agent_todos,
        quota=quota,
        latest_validation=latest_validation,
        latest_runs=latest_runs,
        execution_profile=execution_profile,
        orchestration=orchestration,
        subagent_activity=subagent_activity,
        interface_budget_cadence=interface_budget_cadence,
        project_asset_todo_summary=project_asset_todo_summary,
        project_asset_todo_projection_gap=project_asset_todo_projection_gap,
        project_asset_quota_summary=project_asset_quota_summary,
        compact_execution_profile=compact_execution_profile,
        compact_orchestration_policy=compact_orchestration_policy,
        project_asset_handoff_readiness=project_asset_handoff_readiness,
        project_asset_quota_state=project_asset_quota_state,
        project_asset_user_todo_open_count=project_asset_user_todo_open_count,
        build_long_task_cadence_hint=build_long_task_cadence_hint,
    )


def active_state_todo_fields(
    goal: dict[str, Any],
    *,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    return _active_state_todo_fields_read_model(
        goal,
        runtime_root=runtime_root,
        resolve_goal_local_path=resolve_goal_local_path,
        active_state_next_action_entries=active_state_next_action_entries,
        active_next_action_todo_ids=active_next_action_todo_ids,
        load_rollout_events=load_rollout_events,
        rollout_event_log_path=rollout_event_log_path,
        max_todo_index_rollout_events_per_goal=MAX_TODO_INDEX_ROLLOUT_EVENTS_PER_GOAL,
        active_state_event_projection_fields=active_state_event_projection_fields,
        parse_active_state_todos=parse_active_state_todos,
        parse_issue_meta_surface=parse_issue_meta_surface,
        backlog_hygiene_warning=backlog_hygiene_warning,
        completed_todo_archive_warning=completed_todo_archive_warning,
        autonomous_replan_obligation=autonomous_replan_obligation,
        state_projection_gap_warning=state_projection_gap_warning,
    )


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
    return _attention_item_read_model(
        goal_id=goal_id,
        status=status,
        waiting_on=waiting_on,
        severity=severity,
        recommended_action=recommended_action,
        source=source,
        build_project_asset=build_project_asset,
        compact_dreaming_lane_badge=compact_dreaming_lane_badge,
        operator_question=operator_question,
        agent_command=agent_command,
        controller_stage=controller_stage,
        missing_gates=missing_gates,
        next_handoff_condition=next_handoff_condition,
        lifecycle_phase=lifecycle_phase,
        lifecycle_flags=lifecycle_flags,
        user_todos=user_todos,
        agent_todos=agent_todos,
        todo_state_file=todo_state_file,
        dreaming_proposal=dreaming_proposal,
    )


def sync_connected_attention_action_from_todos(item: dict[str, Any]) -> None:
    _sync_connected_attention_action_from_todos_read_model(
        item,
        first_open_todo_text=first_open_todo_text,
    )


def active_state_todo_attention_item(
    goal: dict[str, Any],
    fields: dict[str, Any],
    current_run: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return _active_state_todo_attention_item_read_model(
        goal,
        fields,
        current_run,
        public_safe_compact_text=public_safe_compact_text,
        first_open_todo_text=first_open_todo_text,
        todo_summary_open_count=todo_summary_open_count,
        goal_lifecycle_fields=goal_lifecycle_fields,
        attention_item=attention_item,
    )


def todo_summary_open_count(summary: dict[str, Any] | None) -> int:
    return _todo_summary_open_count(
        summary,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        fallback_limit=MAX_STATUS_TODOS_PER_ROLE,
    )


def todo_summary_lane_items(summary: dict[str, Any] | None, lane: str) -> list[dict[str, Any]]:
    return _todo_summary_lane_items(summary, lane)


def attention_item_is_monitor_quiet_display_candidate(item: dict[str, Any]) -> bool:
    return _attention_item_is_monitor_quiet_display_candidate(
        item,
        open_todo_items=open_todo_items,
        todo_item_is_actionable_open=todo_item_is_actionable_open,
        fallback_limit=MAX_STATUS_TODOS_PER_ROLE,
    )


def quiet_monitor_display_action(raw_action: str | None) -> str:
    return _quiet_monitor_display_action(
        raw_action,
        fallback_action=MONITOR_DISPLAY_FALLBACK_ACTION,
    )


def normalize_monitor_quiet_attention_display(item: dict[str, Any]) -> None:
    _normalize_monitor_quiet_attention_display(
        item,
        is_monitor_quiet_display_candidate=attention_item_is_monitor_quiet_display_candidate,
        display_fallback_action=MONITOR_DISPLAY_FALLBACK_ACTION,
        monitor_signal_waiting_on=MONITOR_SIGNAL_WAITING_ON,
        monitor_display_schema_version=MONITOR_DISPLAY_SCHEMA_VERSION,
        monitor_display_stop_condition=MONITOR_DISPLAY_STOP_CONDITION,
    )


def merge_global_registry_attention_findings(
    *,
    health_items: list[dict[str, Any]],
    history_items: list[dict[str, Any]],
    findings: list[Any],
    goal_id_filter: str | None,
) -> None:
    _merge_global_registry_findings_read_model(
        health_items=health_items,
        history_items=history_items,
        findings=findings,
        goal_id_filter=goal_id_filter,
        source_registry_shadow_findings=SOURCE_REGISTRY_SHADOW_FINDINGS,
        attention_item=attention_item,
        attach_global_registry_shadow_finding=attach_global_registry_shadow_finding,
    )


def collect_global_registry_health(
    *,
    registry_path: Path,
    runtime_root: Path,
    current_registry: dict[str, Any],
) -> dict[str, Any]:
    return _collect_global_registry_health_read_model(
        registry_path=registry_path,
        runtime_root=runtime_root,
        current_registry=current_registry,
        global_registry_path=global_registry_path,
        load_registry=load_registry,
        registry_goals=registry_goals,
        same_path=same_path,
        resolve_goal_local_path=resolve_goal_local_path,
        parse_timestamp=parse_timestamp,
    )


def is_status_neutral_run(run: dict[str, Any]) -> bool:
    return _is_status_neutral_run_read_model(
        run,
        status_neutral_classifications=STATUS_NEUTRAL_CLASSIFICATIONS,
        agent_lane_progress_scope=AGENT_LANE_PROGRESS_SCOPE,
    )


def latest_agent_lane_run(goal: dict[str, Any]) -> dict[str, Any] | None:
    return _latest_agent_lane_run_read_model(
        goal,
        agent_lane_progress_scope=AGENT_LANE_PROGRESS_SCOPE,
    )


def compact_agent_lane_recommendation(run: dict[str, Any] | None) -> dict[str, Any] | None:
    return _compact_agent_lane_recommendation_read_model(
        run,
        agent_lane_progress_scope=AGENT_LANE_PROGRESS_SCOPE,
        public_safe_compact_text=public_safe_compact_text,
    )


def latest_run_recommended_action_for_projection(
    *,
    current_status_run: dict[str, Any] | None,
    agent_lane_recommendation: dict[str, Any] | None,
    active_state_next_action: Any = None,
    preferred_agent_id: str | None = None,
    limit: int = 320,
) -> tuple[str | None, str | None]:
    return _latest_run_recommended_action_for_projection_read_model(
        current_status_run=current_status_run,
        agent_lane_recommendation=agent_lane_recommendation,
        active_state_next_action=active_state_next_action,
        preferred_agent_id=preferred_agent_id,
        limit=limit,
        public_safe_compact_text=public_safe_compact_text,
        actions_are_projection_aligned=actions_are_projection_aligned,
        parse_timestamp=parse_timestamp,
    )


def latest_run(goal: dict[str, Any]) -> dict[str, Any] | None:
    return _latest_run_read_model(
        goal,
        is_status_neutral_run=is_status_neutral_run,
    )


def ordered_lifecycle_flags(flags: list[str]) -> list[str]:
    return _ordered_lifecycle_flags_read_model(
        flags,
        lifecycle_priority=LIFECYCLE_PRIORITY,
    )


def primary_lifecycle_phase(flags: list[str], fallback: str = "registered") -> str:
    return _primary_lifecycle_phase_read_model(
        flags,
        lifecycle_priority=LIFECYCLE_PRIORITY,
        fallback=fallback,
    )


def run_lifecycle_flags(run: dict[str, Any] | None) -> list[str]:
    return _run_lifecycle_flags_read_model(
        run,
        lifecycle_priority=LIFECYCLE_PRIORITY,
        compact_human_reward=compact_human_reward,
        compact_operator_gate=compact_operator_gate,
        compact_controller_readiness=compact_controller_readiness,
    )


def run_lifecycle_phase(run: dict[str, Any] | None) -> str:
    return _run_lifecycle_phase_read_model(
        run,
        lifecycle_priority=LIFECYCLE_PRIORITY,
        compact_human_reward=compact_human_reward,
        compact_operator_gate=compact_operator_gate,
        compact_controller_readiness=compact_controller_readiness,
    )


def goal_lifecycle_fields(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any]:
    return _goal_lifecycle_fields_read_model(
        goal,
        current_run,
        lifecycle_priority=LIFECYCLE_PRIORITY,
        connected_adapter_statuses=CONNECTED_ADAPTER_STATUSES,
        compact_human_reward=compact_human_reward,
        compact_operator_gate=compact_operator_gate,
        compact_controller_readiness=compact_controller_readiness,
    )


def readiness_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    return _readiness_attention_fields_read_model(
        run,
        compact_controller_readiness=compact_controller_readiness,
    )


def operator_gate_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    return _operator_gate_attention_fields_read_model(
        run,
        compact_operator_gate=compact_operator_gate,
        normalize_operator_question=normalize_operator_question,
        default_operator_gate=DEFAULT_OPERATOR_GATE,
    )


def compact_server_planning_contract(value: Any) -> dict[str, Any]:
    return _compact_server_planning_contract_read_model(
        value,
        public_safe_compact_text=public_safe_compact_text,
        public_safe_compact_list=public_safe_compact_list,
    )


def compact_dreaming_proposal(run: dict[str, Any] | None) -> dict[str, Any] | None:
    return _compact_dreaming_proposal_read_model(
        run,
        dreaming_advisory_classifications=DREAMING_ADVISORY_CLASSIFICATIONS,
        public_safe_compact_text=public_safe_compact_text,
        public_safe_compact_list=public_safe_compact_list,
    )


def compact_dreaming_lane_badge(proposal: dict[str, Any] | None) -> dict[str, Any] | None:
    return _compact_dreaming_lane_badge_read_model(
        proposal,
        public_safe_compact_text=public_safe_compact_text,
    )


def dreaming_attention_fields(run: dict[str, Any] | None) -> dict[str, Any]:
    return _dreaming_attention_fields_read_model(
        run,
        dreaming_advisory_classifications=DREAMING_ADVISORY_CLASSIFICATIONS,
        public_safe_compact_text=public_safe_compact_text,
        public_safe_compact_list=public_safe_compact_list,
        normalize_operator_question=normalize_operator_question,
    )


def legacy_runtime_goal_attention(
    goal: dict[str, Any],
    current_run: dict[str, Any] | None,
    readiness_fields: dict[str, Any],
) -> dict[str, Any] | None:
    return _legacy_runtime_goal_attention_read_model(
        goal,
        current_run,
        readiness_fields,
        attention_item=attention_item,
        goal_lifecycle_fields=goal_lifecycle_fields,
        blocking_classifications=BLOCKING_CLASSIFICATIONS,
        user_or_controller_classifications=USER_OR_CONTROLLER_CLASSIFICATIONS,
        codex_ready_classifications=CODEX_READY_CLASSIFICATIONS,
    )


def goal_attention(goal: dict[str, Any]) -> dict[str, Any] | None:
    return _goal_attention_read_model(
        goal,
        latest_run=latest_run,
        readiness_attention_fields=readiness_attention_fields,
        operator_gate_attention_fields=operator_gate_attention_fields,
        dreaming_attention_fields=dreaming_attention_fields,
        goal_lifecycle_fields=goal_lifecycle_fields,
        legacy_runtime_goal_attention=legacy_runtime_goal_attention,
        compact_session_runtime_projection_from_run=compact_session_runtime_projection_from_run,
        public_safe_compact_text=public_safe_compact_text,
        attention_item=attention_item,
        run_has_external_evidence_watch_signal=run_has_external_evidence_watch_signal,
        default_operator_question=default_operator_question,
        normalize_operator_question=normalize_operator_question,
        monitor_signal_waiting_on=MONITOR_SIGNAL_WAITING_ON,
        default_operator_gate=DEFAULT_OPERATOR_GATE,
        planned_controller_opt_in_recommended_action=PLANNED_CONTROLLER_OPT_IN_RECOMMENDED_ACTION,
        connected_adapter_statuses=CONNECTED_ADAPTER_STATUSES,
        connected_delivery_adapter_statuses=CONNECTED_DELIVERY_ADAPTER_STATUSES,
        registry_waiting_on_overrides=REGISTRY_WAITING_ON_OVERRIDES,
        blocking_classifications=BLOCKING_CLASSIFICATIONS,
        user_or_controller_classifications=USER_OR_CONTROLLER_CLASSIFICATIONS,
        codex_ready_classifications=CODEX_READY_CLASSIFICATIONS,
    )


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
    _attach_goal_channel_projection_read_model(
        item,
        goal=goal,
        goal_latest_runs=goal_latest_runs,
        build_goal_channel_projection=build_goal_channel_projection,
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
    return _build_attention_queue_read_model(
        contract=contract,
        history=history,
        global_registry=global_registry,
        context=AttentionQueueContext(
            active_state_todo_fields=active_state_todo_fields,
            active_state_todo_attention_item=active_state_todo_attention_item,
            latest_run=latest_run,
            goal_attention=goal_attention,
            compact_agent_lane_recommendation=compact_agent_lane_recommendation,
            latest_agent_lane_run=latest_agent_lane_run,
            latest_run_recommended_action_for_projection=latest_run_recommended_action_for_projection,
            compact_autonomous_replan_ack=compact_autonomous_replan_ack,
            latest_autonomous_replan_ack_for_projection=latest_autonomous_replan_ack_for_projection,
            compact_control_plane_policy=compact_control_plane_policy,
            subagent_activity_for_goal=subagent_activity_for_goal,
            interface_budget_cadence_for_runs=interface_budget_cadence_for_runs,
            active_state_projection_warning=active_state_projection_warning,
            enrich_project_asset=enrich_project_asset,
            project_asset_latest_validation=project_asset_latest_validation,
            attach_active_state_project_asset_fields=_attach_active_state_project_asset_fields,
            sync_connected_attention_action_from_todos=sync_connected_attention_action_from_todos,
            quota_status=quota_status,
            quota_with_handoff_outcome_floor=quota_with_handoff_outcome_floor,
            normalize_monitor_quiet_attention_display=normalize_monitor_quiet_attention_display,
            build_task_graph_projection=build_task_graph_projection,
            attach_goal_channel_projection=attach_goal_channel_projection,
            attach_dependency_blockers=attach_dependency_blockers,
            autonomous_backlog_candidates=autonomous_backlog_candidates,
            autonomous_monitor_candidates=autonomous_monitor_candidates,
            attention_item=attention_item,
            attach_global_registry_shadow_finding=attach_global_registry_shadow_finding,
            next_action_projection_warning=next_action_projection_warning,
            autonomous_replan_obligation_from_runs=autonomous_replan_obligation_from_runs,
            source_registry_shadow_findings=SOURCE_REGISTRY_SHADOW_FINDINGS,
            monitor_signal_waiting_on=MONITOR_SIGNAL_WAITING_ON,
        ),
        runtime_root=runtime_root,
        include_task_graph=include_task_graph,
        goal_id_filter=goal_id_filter,
    )


def compact_run(run: dict[str, Any]) -> dict[str, Any]:
    compact = _compact_run_base_read_model(
        run,
        run_compact_fields=RUN_COMPACT_FIELDS,
        run_lifecycle_flags=run_lifecycle_flags,
        primary_lifecycle_phase=primary_lifecycle_phase,
        compact_human_reward=compact_human_reward,
        compact_operator_gate=compact_operator_gate,
        compact_autonomous_replan_ack=compact_autonomous_replan_ack,
        compact_operator_gate_resume_contract=compact_operator_gate_resume_contract,
        compact_controller_readiness=compact_controller_readiness,
        public_safe_compact_text=public_safe_compact_text,
        compact_subagent_run=compact_subagent_run,
        max_subagent_activity_items=MAX_SUBAGENT_ACTIVITY_ITEMS,
        compact_agent_vision=_compact_goal_vision_packet_read_model,
    )
    return _attach_run_summary_projections_read_model(
        compact,
        run,
        compact_benchmark_run=compact_benchmark_run,
        worker_bridge_ingest_health_note=worker_bridge_ingest_health_note,
        compact_benchmark_result=compact_benchmark_result,
        compact_benchmark_comparison=_compact_benchmark_comparison_read_model,
        benchmark_comparison_decision_note=_benchmark_comparison_decision_note_read_model,
        compact_benchmark_learning_ledger=compact_benchmark_learning_ledger,
        compact_benchmark_experiment_report=compact_benchmark_experiment_report,
        benchmark_experiment_report_readiness_note=benchmark_experiment_report_readiness_note,
        benchmark_experiment_report_replay_decision=benchmark_experiment_report_replay_decision,
        compact_active_user_assisted_pilot=compact_active_user_assisted_pilot,
        compact_session_runtime_projection_from_run=compact_session_runtime_projection_from_run,
    )


def build_status_contract() -> dict[str, Any]:
    return _build_status_contract_read_model(
        schema_version=STATUS_CONTRACT_SCHEMA_VERSION,
        minimum_dashboard_schema_version=MINIMUM_DASHBOARD_STATUS_CONTRACT_SCHEMA_VERSION,
        reload_hint=STATUS_CONTRACT_RELOAD_HINT,
    )


def build_contract_health_projection(contract: dict[str, Any]) -> dict[str, Any]:
    return _build_contract_health_projection_read_model(
        contract,
        signal_limit=STATUS_CONTRACT_SIGNAL_LIMIT,
    )


def build_status_runtime_summary_context() -> StatusRuntimeSummaryContext:
    return StatusRuntimeSummaryContext(
        latest_run=latest_run,
        goal_lifecycle_fields=goal_lifecycle_fields,
        subagent_activity_for_goal=subagent_activity_for_goal,
        compact_run=compact_run,
        quota_status=quota_status,
        parse_timestamp=parse_timestamp,
        compact_benchmark_run=compact_benchmark_run,
        compact_benchmark_result=compact_benchmark_result,
        compact_benchmark_comparison=_compact_benchmark_comparison_read_model,
        compact_benchmark_learning_ledger=compact_benchmark_learning_ledger,
        compact_benchmark_experiment_report=compact_benchmark_experiment_report,
        compact_active_user_assisted_pilot=compact_active_user_assisted_pilot,
        run_has_external_evidence_watch_signal=run_has_external_evidence_watch_signal,
        decision_classifications=EVENT_LEDGER_DECISION_CLASSIFICATIONS,
        evidence_classifications=EVENT_LEDGER_EVIDENCE_CLASSIFICATIONS,
        evidence_hints=EVENT_LEDGER_EVIDENCE_HINTS,
        state_classifications=EVENT_LEDGER_STATE_CLASSIFICATIONS,
        promotion_readiness_classifications=PROMOTION_READINESS_CLASSIFICATIONS,
        add_promotion_readiness_freshness=add_promotion_readiness_freshness,
        latest_promotion_readiness_event=latest_promotion_readiness_event,
        promotion_readiness_freshness_hours=PROMOTION_READINESS_FRESHNESS_HOURS,
        promotion_readiness_proxy_note=PROMOTION_READINESS_PROXY_NOTE,
        public_safe_compact_text=public_safe_compact_text,
        decision_freshness_classification_prefixes=DECISION_FRESHNESS_CLASSIFICATION_PREFIXES,
        decision_freshness_window_days=DECISION_FRESHNESS_WINDOW_DAYS,
        decision_freshness_item_limit=DECISION_FRESHNESS_ITEM_LIMIT,
        decision_freshness_proxy_note=DECISION_FRESHNESS_PROXY_NOTE,
    )


def build_status_runtime_summaries(
    *,
    history: dict[str, Any],
    queue: dict[str, Any],
    runtime_root: Path,
    goal_id_filter: str | None,
    display_limit: int,
    todo_index_limit: int,
) -> dict[str, Any]:
    return _build_status_runtime_summaries_read_model(
        history=history,
        queue=queue,
        runtime_root=runtime_root,
        goal_id_filter=goal_id_filter,
        display_limit=display_limit,
        todo_index_limit=todo_index_limit,
        context=build_status_runtime_summary_context(),
    )


def build_status_collection_context() -> StatusCollectionContext:
    return StatusCollectionContext(
        load_registry=load_registry,
        resolve_runtime_root=resolve_runtime_root,
        collect_global_registry_health=collect_global_registry_health,
        collect_history=collect_history,
        check_contract=check_contract,
        build_attention_queue=build_attention_queue,
        build_runtime_summaries=build_status_runtime_summaries,
        build_promotion_gate=build_promotion_gate,
        build_status_contract=build_status_contract,
        build_contract_health_projection=build_contract_health_projection,
        build_agent_management_projection=_build_agent_management_projection_read_model,
        status_control_plane_context_limit=STATUS_CONTROL_PLANE_CONTEXT_LIMIT,
        max_todo_index_items=MAX_TODO_INDEX_ITEMS,
    )


def collect_status(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
    include_task_graph: bool = False,
    goal_id: str | None = None,
) -> dict[str, Any]:
    return _collect_status_read_model(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
        include_task_graph=include_task_graph,
        goal_id=goal_id,
        context=build_status_collection_context(),
    )
