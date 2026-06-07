from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import re
from typing import Any

from .control_plane import compact_control_plane_policy, control_plane_policy_summary
from .contract import check_contract
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
from .handoff_budget import handoff_budget_contract
from .history import collect_history, load_registry
from .interface_budget import interface_budget_cadence_for_runs
from .materials import extract_review_materials
from .operator_gate import DEFAULT_OPERATOR_GATE, default_operator_question, normalize_operator_question
from .orchestration import compact_orchestration_policy, orchestration_policy_summary
from .paths import global_registry_path, resolve_runtime_root
from .promotion_gate import build_promotion_gate
from .quota import quota_status, quota_with_handoff_outcome_floor
from .registry import registry_goals


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
}
STATUS_NEUTRAL_CLASSIFICATIONS = {
    "quota_slot_spent",
}
HANDOFF_READY_CLASSIFICATIONS = {
    "operator_gate_approved",
    "controller_opted_in_waiting_for_run",
}
USER_OR_CONTROLLER_CLASSIFICATIONS = {
    "needs_human_reward",
    "needs_controller_opt_in",
    "needs_user_relay",
    "ready_for_controller_opt_in",
    "ready_for_user_relay",
    "operator_gate_deferred",
    "operator_gate_rejected",
}
REGISTRY_WAITING_ON_OVERRIDES = {
    "user_or_controller",
    "controller",
    "codex",
    "external_evidence",
}
WATCH_CLASSIFICATION_PREFIXES = ("await_", "monitor_")
BLOCKING_CLASSIFICATIONS = {
    "blocked_by_safety",
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
    "single_surface",
    "test_only",
    "unknown",
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
    "先在 Goal Harness 完成 operator 判断；同意后项目 Agent 只执行 read-only map dry-run"
)
RUN_COMPACT_FIELDS = (
    "generated_at",
    "run_id",
    "goal_id",
    "parent_run_id",
    "spawned_by_goal_id",
    "agent_role",
    "classification",
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
USAGE_PROXY_NOTE = "run-history proxy; excludes token counts and raw thread logs"
HUMAN_REWARD_COMPACT_FIELDS = (
    "recorded_at",
    "decision",
    "reward",
    "reason_summary",
    "follow_up",
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
TODO_TASK_PATTERN = re.compile(r"^\s*[-*]\s+\[([ xX-])\]\s+(.+?)\s*$")
SECTION_HEADING_PATTERN = re.compile(r"^##+\s+(.+?)\s*$")
LOCAL_PATH_SURFACE_PATTERN = re.compile(r"(?<!<)/(?:Users|Volumes|var/folders|tmp|private/tmp)/[^\s`'\"<>]+")
SECRET_LIKE_SURFACE_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+[a-z0-9._~+/=-]{16,}|(?<![a-z0-9_])(?:ak|sk)[-_=:][a-z0-9_=-]{10,}|\btoken\s*[=:]\s*[^\s`'\"<>]{12,})"
)
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
MAX_DEPENDENCY_BLOCKERS = 4
MAX_AUTONOMOUS_BACKLOG_CANDIDATES = 6
MAX_SUBAGENT_ACTIVITY_ITEMS = 5
MAX_SUBAGENT_SCOPE_ITEMS = 4
MAX_BACKLOG_HYGIENE_EVIDENCE_ITEMS = 3
MAX_AUTONOMOUS_REPLAN_TRIGGERS = 3
AUTONOMOUS_PRIORITY_PATTERN = re.compile(r"^\s*\[(P[0-4][^\]]*)\]\s*(.+)$", re.IGNORECASE)
BACKLOG_HYGIENE_SECTION_HEADINGS = ("Next Action", "Operating Lessons")
BACKLOG_HYGIENE_BULLET_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$")
BACKLOG_HYGIENE_HINT_PATTERN = re.compile(
    r"(?i)(?:\[p[0-4]\]|todo|backlog|follow[- ]?up|queue|audit|regression|smoke|cadence|mirror|monitor|sub-?agent|待办|回归|审计|修复|检查|推进)"
)
AUTONOMOUS_REPLAN_SCHEMA_VERSION = "autonomous_replan_obligation_v0"
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
TODO_ARCHIVE_HEADER_MARKERS = (
    "todo archive",
    "work archive",
    "completed archive",
    "completed work",
    "完成归档",
    "待办归档",
)
TODO_ITEM_SCHEMA_VERSION = "todo_item_v0"
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
TODO_TASK_CLASS_VALUES = {TODO_TASK_CLASS_ADVANCEMENT, TODO_TASK_CLASS_MONITOR}
TODO_MONITOR_PATTERNS = (
    re.compile(r"(?i)\bdependency monitor\b"),
    re.compile(r"(?i)\bobservation lane\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)observe\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)poll\b"),
    re.compile(r"(?i)(?:^|[:：]\s*)watch\b"),
    re.compile(r"(?i)\bmonitor-only\b"),
)
TODO_ADVANCEMENT_PATTERNS = (
    re.compile(r"(?i)(?:^|[:：]\s*)(?:implement|add|make|fix|build|wire|define|compare|run|repair|archive|publish|merge|write|attribute)\b"),
    re.compile(r"(?i)\b(?:implementation slice|validation-backed patch|smoke fixture)\b"),
)


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

    validation = source.get("validation") if isinstance(source.get("validation"), dict) else {}
    if validation:
        failed = [
            str(key)
            for key, value in validation.items()
            if isinstance(key, str) and isinstance(value, bool) and not value
        ][:MAX_BENCHMARK_RUN_LIST_ITEMS]
        compact["validation"] = {
            "all_passed": not failed and all(bool(value) for value in validation.values() if isinstance(value, bool)),
            "failed_checks": failed,
        }

    trials: list[dict[str, Any]] = []
    for trial in source.get("trials") or []:
        if not isinstance(trial, dict):
            continue
        compact_trial: dict[str, Any] = {}
        for field in ("task_id", "trial_name", "source", "exception_type"):
            value = public_safe_compact_text(trial.get(field), limit=140)
            if value:
                compact_trial[field] = value
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

    if set(compact.keys()) == {"schema_version"}:
        return None
    return compact


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
    match = AUTONOMOUS_PRIORITY_PATTERN.match(text)
    if not match:
        return None, text
    return match.group(1).strip().upper(), match.group(2).strip()


def todo_task_class_for_text(text: str) -> str:
    compact = normalize_todo_text(text)
    for pattern in TODO_MONITOR_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_MONITOR
    for pattern in TODO_ADVANCEMENT_PATTERNS:
        if pattern.search(compact):
            return TODO_TASK_CLASS_ADVANCEMENT
    return TODO_TASK_CLASS_ADVANCEMENT


def normalize_todo_task_class(value: Any, *, text: str) -> str:
    candidate = str(value or "").strip()
    if candidate in TODO_TASK_CLASS_VALUES:
        return candidate
    return todo_task_class_for_text(text)


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
    status = "done" if item.get("done") else "open"
    identity = "|".join(str(part or "") for part in (role, source_section, index, text))
    normalized = dict(item)
    normalized.update(
        {
            "schema_version": TODO_ITEM_SCHEMA_VERSION,
            "todo_id": f"todo_{hashlib.sha1(identity.encode('utf-8')).hexdigest()[:12]}",
            "role": role,
            "status": status,
            "archive_state": archive_state,
            "source_section": source_section,
            "text": text,
            "task_class": normalize_todo_task_class(item.get("task_class"), text=text),
        }
    )
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
    for key in ("schema_version", "todo_id", "role", "status", "priority", "title", "archive_state", "source_section", "task_class"):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    return compact


def compact_todo_group(
    items: list[dict[str, Any]],
    *,
    source_section: str | None,
    role: str | None = None,
) -> dict[str, Any] | None:
    if not items:
        return None
    items = [
        structured_todo_item(item, role=role, source_section=source_section)
        if isinstance(item, dict)
        else item
        for item in items
    ]
    open_items = [item for item in items if not item.get("done")]
    done_items = [item for item in items if item.get("done")]
    return {
        "schema_version": "todo_summary_v0",
        "source_section": source_section,
        "total_count": len(items),
        "open_count": len(open_items),
        "done_count": len(done_items),
        "first_open_items": [compact_todo_item(item) for item in open_items[:3]],
        "items": items[:MAX_STATUS_TODOS_PER_ROLE],
    }


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


def parse_active_state_todos(state_text: str, *, goal: dict[str, Any] | None = None, state_path: Path | None = None) -> dict[str, Any]:
    role: str | None = None
    source_sections: dict[str, str | None] = {"user": None, "agent": None}
    items: dict[str, list[dict[str, Any]]] = {"user": [], "agent": []}
    current_todo: dict[str, Any] | None = None

    for line in state_text.splitlines():
        if line.startswith("## "):
            heading = line.lstrip("#").strip()
            role = todo_role_for_heading(heading)
            current_todo = None
            if role and source_sections[role] is None:
                source_sections[role] = heading
            continue
        if role is None:
            continue
        match = TODO_TASK_PATTERN.match(line)
        if match:
            marker, text = match.groups()
            todo: dict[str, Any] = {
                "index": len(items[role]) + 1,
                "done": marker.lower() == "x",
                "text": normalize_todo_text(text),
            }
            if goal is not None:
                materials = extract_review_materials(text, goal=goal, state_path=state_path)
                if materials:
                    todo["review_materials"] = materials
            items[role].append(todo)
            current_todo = todo
            continue
        if current_todo is None or not line.startswith((" ", "\t")):
            continue
        continuation = line.strip()
        if continuation:
            current_todo["text"] = normalize_todo_text(f"{current_todo.get('text', '')} {continuation}")

    result: dict[str, Any] = {}
    user = compact_todo_group(items["user"], source_section=source_sections["user"], role="user")
    agent = compact_todo_group(items["agent"], source_section=source_sections["agent"], role="agent")
    if user:
        result["user_todos"] = user
    if agent:
        result["agent_todos"] = agent
    return result


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

    if len(evidence) < 2:
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

    if not evidence:
        return None

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

    return {
        "schema_version": AUTONOMOUS_REPLAN_SCHEMA_VERSION,
        "required": True,
        "trigger_count": len(evidence),
        "triggers": evidence,
        "todo_actions": todo_actions[:3],
        "next_validation_command": "python3 examples/autonomous-replan-obligation-smoke.py",
        "stop_condition": (
            "stop if the replan requires private material, credentials, destructive git, "
            "production actions, or owner-only decisions"
        ),
        "recommended_action": (
            "run an autonomous replan before another monitor-only or repeated action consumes the eligible turn"
        ),
    }


def completed_todo_archive_warning(agent_todos: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(agent_todos, dict):
        return None
    try:
        done_count = int(agent_todos.get("done_count") or 0)
    except (TypeError, ValueError):
        done_count = 0
    if done_count <= MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE:
        return None
    try:
        open_count = int(agent_todos.get("open_count") or 0)
    except (TypeError, ValueError):
        open_count = 0
    return {
        "kind": "completed_agent_todo_archive_required",
        "requires_archive": True,
        "archive_section": "Completed Work Archive",
        "active_done_count": done_count,
        "active_open_count": open_count,
        "max_active_done_count": MAX_ACTIVE_DONE_TODOS_BEFORE_ARCHIVE,
        "recommended_action": (
            "move older completed Agent Todo entries into a dedicated Completed Work Archive "
            "until the active Agent Todo section keeps only current open work and a small recent-done tail"
        ),
    }


def project_asset_owner(waiting_on: str) -> str:
    if waiting_on == "codex":
        return "codex"
    if waiting_on == "external_evidence":
        return "external_evidence"
    if waiting_on == "controller":
        return "controller"
    if waiting_on == "user_or_controller":
        return "user_or_controller"
    return waiting_on or "unknown"


def project_asset_gate(
    *,
    waiting_on: str,
    operator_question: str | None,
    missing_gates: list[str] | None,
    status: str,
) -> str:
    if operator_question:
        return "operator_question"
    if missing_gates:
        return str(missing_gates[0])
    if waiting_on in {"user_or_controller", "controller"}:
        return status or waiting_on
    if waiting_on == "external_evidence":
        return "external_evidence"
    return "none"


def project_asset_stop_condition(
    *,
    waiting_on: str,
    next_handoff_condition: str | None,
    agent_command: str | None,
) -> str:
    if next_handoff_condition:
        return next_handoff_condition
    if waiting_on == "user_or_controller":
        return "stop until the user or controller decision is recorded"
    if waiting_on == "controller":
        return "stop until the controller or owner resolves this gate"
    if waiting_on == "external_evidence":
        return "stop until external evidence changes"
    if agent_command:
        return "stop if the command fails or needs write, production, or additional approval"
    return "stop if the next action needs reward, gate approval, write control, or production access"


def project_asset_support_mode(
    *,
    waiting_on: str,
    operator_question: str | None,
    missing_gates: list[str] | None,
    status: str,
    recommended_action: str,
    agent_command: str | None,
) -> str:
    surface = " ".join(
        str(value or "")
        for value in (status, recommended_action, agent_command, " ".join(missing_gates or []))
    ).lower()
    if "reward" in surface:
        return "reward_capture"
    if operator_question or missing_gates or waiting_on in {"user_or_controller", "controller"}:
        return "decision_support"
    if waiting_on == "external_evidence":
        return "read_only_observer"
    if agent_command or waiting_on == "codex":
        return "selective_assist"
    return "read_only_observer"


def project_asset_next_safe_command(agent_command: str | None) -> str | None:
    if not agent_command:
        return None
    return public_safe_compact_text(agent_command, limit=320)


def open_todo_items(
    todos: dict[str, Any] | None,
    *,
    limit: int = MAX_PROJECT_ASSET_TODO_ITEMS,
    text_limit: int = 220,
) -> list[dict[str, Any]]:
    if not isinstance(todos, dict):
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    for source_items in (todos.get("first_open_items"), todos.get("items")):
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
                return result
    return result


def first_open_todo_text(todos: dict[str, Any] | None) -> str | None:
    items = open_todo_items(todos, limit=1)
    if not items:
        return None
    return str(items[0].get("text") or "") or None


def project_asset_todo_summary(todos: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(todos, dict):
        return None
    summary: dict[str, Any] = {
        "schema_version": todos.get("schema_version") or "todo_summary_v0",
        "source_section": "project_asset",
        "open": todos.get("open_count", 0),
        "done": todos.get("done_count", 0),
        "total": todos.get("total_count", 0),
    }
    open_items = open_todo_items(todos)
    if open_items:
        summary["items"] = open_items
        summary["next"] = open_items[0]["text"]
        if open_items[0].get("index") is not None:
            summary["next_index"] = open_items[0].get("index")
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
    if not isinstance(todos, dict):
        return None
    for todo in todos.get("items") or []:
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


def autonomous_backlog_candidates(
    items: list[dict[str, Any]],
    *,
    limit: int = MAX_AUTONOMOUS_BACKLOG_CANDIDATES,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("waiting_on") != "codex":
            continue
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        if quota.get("state") != "eligible":
            continue
        todo = first_open_todo_item(item.get("agent_todos") if isinstance(item.get("agent_todos"), dict) else None)
        if not todo:
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
                "text": text,
                "source": "agent_todos",
            }
        )
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
        "items": candidates[:limit],
    }


def project_asset_quota_summary(quota: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(quota, dict):
        return None
    summary: dict[str, Any] = {
        "compute": quota.get("compute"),
        "state": quota.get("state"),
        "spent_slots": quota.get("spent_slots"),
        "allowed_slots": quota.get("allowed_slots"),
    }
    if quota.get("reason"):
        summary["reason"] = normalize_todo_text(str(quota.get("reason") or ""), limit=220)
    return summary


def project_asset_latest_validation(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    signal: dict[str, Any] = {}
    for field in ("generated_at", "classification"):
        value = run.get(field)
        if value:
            signal[field] = value
    summary = run.get("health_check") or run.get("recommended_action")
    if summary:
        signal["summary"] = normalize_todo_text(str(summary), limit=260)
    return signal or None


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


def project_asset_summary_is_public_safe(project_asset: dict[str, Any]) -> bool:
    text = repr(project_asset)
    return not LOCAL_PATH_SURFACE_PATTERN.search(text) and not SECRET_LIKE_SURFACE_PATTERN.search(text)


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
    if classification.startswith(WATCH_CLASSIFICATION_PREFIXES):
        return False
    return True


def delivery_batch_scale_for_run(run: dict[str, Any]) -> str:
    explicit = str(run.get("delivery_batch_scale") or "").strip()
    if explicit:
        return explicit
    classification = str(run.get("classification") or "")
    if not classification:
        return "unknown"
    normalized = classification.lower()
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_TEST_ONLY_CLASSIFICATION_HINTS):
        return "test_only"
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_MULTI_SURFACE_CLASSIFICATION_HINTS):
        return "multi_surface"
    if any(hint in normalized for hint in DELIVERY_BATCH_SCALE_IMPLEMENTATION_CLASSIFICATION_HINTS):
        return "implementation"
    return "single_surface"


def _classification_contains_any(classification: str, hints: list[Any]) -> bool:
    normalized = classification.lower()
    return any(str(hint or "").strip().lower() in normalized for hint in hints if str(hint or "").strip())


def delivery_outcome_for_run(run: dict[str, Any], profile: dict[str, Any] | None = None) -> str:
    explicit = str(run.get("delivery_outcome") or "").strip()
    if explicit:
        return explicit
    classification = str(run.get("classification") or "")
    if not classification:
        return "unknown"
    floor = execution_profile_outcome_floor(profile)
    outcome_markers = floor.get("outcome_markers") if isinstance(floor.get("outcome_markers"), list) else []
    surface_hints = floor.get("surface_only_hints") if isinstance(floor.get("surface_only_hints"), list) else []
    if not outcome_markers and not surface_hints:
        return "not_configured"
    marker_hit = _classification_contains_any(classification, outcome_markers)
    surface_hit = _classification_contains_any(classification, surface_hints)
    if surface_hit:
        return "surface_only"
    if marker_hit:
        return "outcome_progress"
    return "outcome_gap"


def outcome_floor_configured(profile: dict[str, Any] | None) -> bool:
    floor = execution_profile_outcome_floor(profile)
    return bool(floor.get("outcome_markers") or floor.get("surface_only_hints"))


def outcome_gap_streak(runs: list[dict[str, Any]], profile: dict[str, Any] | None = None) -> int:
    if not outcome_floor_configured(profile):
        return 0
    streak = 0
    for run in runs:
        outcome = delivery_outcome_for_run(run, profile)
        if outcome in {"outcome_progress", "primary_goal_outcome", "not_configured"}:
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
    if outcome != "not_configured":
        compact["delivery_outcome"] = outcome
    benchmark_run = compact_benchmark_run(run)
    if benchmark_run:
        compact["benchmark_run_summary"] = benchmark_run
    benchmark_result = compact_benchmark_result(run)
    if benchmark_result:
        compact["benchmark_result_summary"] = benchmark_result
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

    quota = project_asset.get("quota") if isinstance(project_asset.get("quota"), dict) else {}
    if not quota and isinstance(item.get("quota"), dict):
        quota = item["quota"]

    next_action = str(project_asset.get("next_action") or "").strip()
    item_action = str(item.get("recommended_action") or "").strip()
    stop_condition = str(project_asset.get("stop_condition") or "").strip()
    quota_state = str(quota.get("state") or "").strip()
    waiting_on = str(item.get("waiting_on") or "").strip()
    goal_id = str(item.get("goal_id") or "").strip()
    codex_ready = waiting_on == "codex" and quota_state == "eligible"
    checks = {
        "project_asset_backed": True,
        "same_source_should_run": bool(quota and next_action and (not item_action or item_action == next_action)),
        "codex_ready": codex_ready,
        "handoff_has_next_action": bool(next_action),
        "handoff_has_stop_condition": bool(stop_condition),
        "handoff_sanitized_surface": project_asset_summary_is_public_safe(project_asset),
    }
    state_trace_ready = all(
        checks[key]
        for key in (
            "project_asset_backed",
            "same_source_should_run",
            "handoff_has_next_action",
            "handoff_has_stop_condition",
            "handoff_sanitized_surface",
        )
    )
    readiness: dict[str, Any] = {
        "ready": all(checks.values()),
        "codex_ready": codex_ready,
        "source": "project_asset",
        "quota_state": quota_state or "unknown",
        "handoff_interface_budget": handoff_budget_contract(),
        "checks": checks,
    }
    readiness.update(
        project_asset_handoff_state(
            ready=state_trace_ready,
            project_asset=project_asset,
            latest_runs=latest_runs,
        )
    )
    if goal_id:
        readiness["next_probe"] = f"goal-harness review-packet --goal-id {goal_id} --handoff-only"
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
    user_summary = project_asset_todo_summary(user_todos)
    if user_summary:
        project_asset["user_todos"] = user_summary
    agent_summary = project_asset_todo_summary(agent_todos)
    if agent_summary:
        project_asset["agent_todos"] = agent_summary
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


def build_project_asset(
    *,
    status: str,
    waiting_on: str,
    recommended_action: str,
    operator_question: str | None,
    agent_command: str | None,
    missing_gates: list[str] | None,
    next_handoff_condition: str | None,
) -> dict[str, Any]:
    asset = {
        "owner": project_asset_owner(waiting_on),
        "gate": project_asset_gate(
            waiting_on=waiting_on,
            operator_question=operator_question,
            missing_gates=missing_gates,
            status=status,
        ),
        "support_mode": project_asset_support_mode(
            waiting_on=waiting_on,
            operator_question=operator_question,
            missing_gates=missing_gates,
            status=status,
            recommended_action=recommended_action,
            agent_command=agent_command,
        ),
        "next_action": recommended_action,
        "stop_condition": project_asset_stop_condition(
            waiting_on=waiting_on,
            next_handoff_condition=next_handoff_condition,
            agent_command=agent_command,
        ),
    }
    next_safe_command = project_asset_next_safe_command(agent_command)
    if next_safe_command:
        asset["next_safe_command"] = next_safe_command
    return asset


def active_state_todo_fields(goal: dict[str, Any]) -> dict[str, Any]:
    state_path = resolve_goal_local_path(goal.get("state_file"), goal, fallback_base=Path.cwd())
    if state_path is None or not state_path.exists():
        return {}
    try:
        state_text = state_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    fields = parse_active_state_todos(state_text, goal=goal, state_path=state_path)
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
    return item


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
                                    f"run `goal-harness sync-global --goal-id {goal_id}` from the source project"
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
                    "for multi-project dashboard/controller status, run `goal-harness status` "
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
    return str(run.get("classification") or "") in STATUS_NEUTRAL_CLASSIFICATIONS


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
            f"`goal-harness archive-runtime --goal-id {goal_id}` before trusting multi-project status"
        )
    elif classification in BLOCKING_CLASSIFICATIONS:
        severity = "high"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `goal-harness archive-runtime --goal-id {goal_id}` "
            "so multi-project status stays authoritative"
        )
    else:
        severity = "action"
        action = (
            f"latest classification is {classification}; add this runtime goal to the registry "
            f"or preview cleanup with `goal-harness archive-runtime --goal-id {goal_id}` "
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


def goal_attention(goal: dict[str, Any]) -> dict[str, Any] | None:
    goal_id = str(goal.get("id") or "unknown-goal")
    adapter_status = str(goal.get("adapter_status") or "")
    adapter_kind = str(goal.get("adapter_kind") or "")
    current_run = latest_run(goal)
    readiness_fields = readiness_attention_fields(current_run)
    operator_gate_fields = operator_gate_attention_fields(current_run)
    attention_fields = {**readiness_fields, **operator_gate_fields}
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
            command = f"goal-harness read-only-map --goal-id {goal_id} --dry-run"
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
    if classification.startswith(WATCH_CLASSIFICATION_PREFIXES):
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


def build_attention_queue(
    *,
    contract: dict[str, Any],
    history: dict[str, Any],
    global_registry: dict[str, Any],
) -> dict[str, Any]:
    health_items: list[dict[str, Any]] = []
    history_items: list[dict[str, Any]] = []
    if contract.get("ok") is False:
        health_items.append(
            attention_item(
                goal_id="goal-harness-contract",
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
        item = goal_attention(goal)
        if item:
            control_plane = compact_control_plane_policy(goal.get("control_plane"))
            if control_plane:
                item["control_plane"] = control_plane
            goal_latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
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
            if projection_warning:
                item["stale_latest_run_warning"] = projection_warning
                if isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["stale_latest_run_warning"] = projection_warning
            if goal.get("registry_member"):
                item.update(active_state_todo_fields(goal))
                backlog_warning = (
                    item.get("backlog_hygiene_warning")
                    if isinstance(item.get("backlog_hygiene_warning"), dict)
                    else None
                )
                if backlog_warning and isinstance(item.get("project_asset"), dict):
                    item["project_asset"]["backlog_hygiene_warning"] = backlog_warning
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

    queue = {
        "available": True,
        "item_count": len(items),
        "needs_user_or_controller": sum(
            1 for item in items if item["waiting_on"] in {"user_or_controller", "controller"}
        ),
        "needs_controller": sum(1 for item in items if item["waiting_on"] == "controller"),
        "needs_codex": sum(1 for item in items if item["waiting_on"] == "codex"),
        "watching_external_evidence": sum(1 for item in items if item["waiting_on"] == "external_evidence"),
        "items": items,
    }
    if backlog_candidates:
        queue["autonomous_backlog_candidates"] = backlog_candidates
    return queue


def compact_human_reward(reward: Any) -> dict[str, Any] | None:
    if not isinstance(reward, dict):
        return None
    compact = {field: reward[field] for field in HUMAN_REWARD_COMPACT_FIELDS if field in reward}
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


def _markdown_scalar(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|").strip()


def _goals_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    run_history = payload.get("run_history") if isinstance(payload.get("run_history"), dict) else {}
    goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for goal in goals:
        if not isinstance(goal, dict):
            continue
        goal_id = str(goal.get("id") or "")
        if goal_id:
            result[goal_id] = goal
    return result


def _authority_registry_markdown_summary(goal: dict[str, Any] | None) -> str | None:
    registry = goal.get("authority_registry") if isinstance(goal, dict) else None
    if not isinstance(registry, dict) or not registry.get("declared"):
        return None
    materials = int(registry.get("project_material_count") or 0)
    topics = int(registry.get("topic_authority_count") or 0)
    if materials <= 0 and topics <= 0:
        return None
    return (
        f"entries={int(registry.get('default_entries_present') or 0)}/"
        f"{int(registry.get('default_entry_count') or 0)} "
        f"topics={topics} "
        f"materials={materials} "
        f"repositories={int(registry.get('project_material_repository_count') or 0)} "
        f"owner_review_required={int(registry.get('project_material_owner_review_required_count') or 0)} "
        f"stale={int(registry.get('project_material_stale_count') or 0)} "
        f"current_authority={int(registry.get('project_material_current_authority_count') or 0)} "
        f"risk={_markdown_scalar(registry.get('conflict_risk') or 'unknown')}"
    )


def _append_human_reward_markdown(lines: list[str], goal_id: Any, reward: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("recorded_at", "decision", "reward"):
        value = reward.get(field)
        if value:
            headline_parts.append(f"{field}={_markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - human_reward: {' '.join(headline_parts)}")
    reason = reward.get("reason_summary")
    if reason:
        lines.append(f"      - reason_summary: {_markdown_scalar(reason)}")
    follow_up = reward.get("follow_up")
    if follow_up:
        lines.append(f"      - follow_up: {_markdown_scalar(follow_up)}")
    if goal_id:
        lines.append(
            "      - project_agent_visibility: "
            f"`goal-harness history --goal-id {_markdown_scalar(goal_id)} --limit 3`"
        )


def _append_operator_gate_resume_contract_markdown(lines: list[str], contract: dict[str, Any]) -> None:
    headline_parts = []
    for field in ("version", "gate_id", "operator_decision"):
        value = contract.get(field)
        if value:
            headline_parts.append(f"{field}={_markdown_scalar(value)}")
    if not headline_parts:
        headline_parts.append("recorded=True")
    lines.append(f"    - operator_gate_resume_contract: {' '.join(headline_parts)}")
    for field in (
        "latest_state_ref",
        "freshness_check",
        "precondition_check",
        "migration_or_rebase_result",
        "validation_after_resume",
    ):
        value = contract.get(field)
        if value:
            lines.append(f"      - {field}: {_markdown_scalar(value)}")


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
    benchmark_result = compact_benchmark_result(run)
    if benchmark_result:
        compact["benchmark_result_summary"] = benchmark_result
    return compact


def build_run_history(history: dict[str, Any]) -> dict[str, Any]:
    goals: list[dict[str, Any]] = []
    for goal in history.get("goals") or []:
        if not isinstance(goal, dict):
            continue
        current_run = latest_run(goal)
        lifecycle_fields = goal_lifecycle_fields(goal, current_run)
        subagent_activity = subagent_activity_for_goal(goal)
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
                "latest_runs": [
                    compact_run(run)
                    for run in goal.get("latest_runs") or []
                    if isinstance(run, dict)
                ],
            }
        )

    recent_runs = [
        compact_run(run)
        for run in history.get("runs") or []
        if isinstance(run, dict)
    ]
    return {
        "available": True,
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "goals": goals,
        "recent_runs": recent_runs,
    }


def quota_spend_slots(run: dict[str, Any]) -> int:
    if str(run.get("classification") or "") != "quota_slot_spent":
        return 0
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    raw_slots = quota_event.get("slots", 1)
    try:
        return max(0, int(raw_slots))
    except (TypeError, ValueError):
        return 1


def is_automation_run(run: dict[str, Any]) -> bool:
    quota_event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else {}
    source = str(quota_event.get("source") or run.get("source") or "").lower()
    if source in {"heartbeat", "automation", "cron"}:
        return True
    if "heartbeat" in source or "automation" in source:
        return True
    return str(run.get("classification") or "") == "quota_slot_spent"


def is_progress_signal_run(run: dict[str, Any]) -> bool:
    classification = str(run.get("classification") or "")
    return bool(classification and classification not in {"quota_slot_spent", "state_refreshed"})


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
    if compact_benchmark_run(run) or compact_benchmark_result(run):
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
    if classification.startswith(WATCH_CLASSIFICATION_PREFIXES):
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
        full_scan_latest = latest_promotion_readiness_event(runtime_root)
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
        "producer": "goal-harness status",
        "reload_hint": STATUS_CONTRACT_RELOAD_HINT,
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


def collect_status(
    *,
    registry_path: Path,
    runtime_root_override: str | None,
    scan_roots: list[Path],
    limit: int,
) -> dict[str, Any]:
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
        goal_id=None,
        limit=limit,
        include_runtime_goals=include_runtime_goals,
    )
    contract = check_contract(
        registry_path=registry_path,
        runtime_root_override=runtime_root_override,
        scan_roots=scan_roots,
        limit=limit,
    )
    queue = build_attention_queue(contract=contract, history=history, global_registry=global_registry)
    run_history = build_run_history(history)
    event_ledger_summary = build_event_ledger_summary(history)
    promotion_readiness_summary = build_promotion_readiness_summary(
        history,
        runtime_root=runtime_root,
    )
    promotion_gate = build_promotion_gate(
        registry_path=registry_path,
        runtime_root_override=str(runtime_root),
    )
    decision_freshness_summary = build_decision_freshness_summary(history)
    usage_summary = build_usage_summary(history)
    return {
        "ok": bool(contract.get("ok")) and bool(global_registry.get("ok", True)),
        "registry": str(registry_path),
        "runtime_root": str(runtime_root),
        "goal_count": history.get("goal_count"),
        "run_count": history.get("run_count"),
        "status_contract": build_status_contract(),
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
    }


def _event_class_count_text(counts: dict[str, Any]) -> str:
    return " ".join(
        f"{event_class}={counts.get(event_class, 0)}"
        for event_class in EVENT_LEDGER_CLASSES
    )


def render_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Goal Harness Status",
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

    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    summary = contract.get("summary") if isinstance(contract.get("summary"), dict) else {}
    lines.append(
        "- contract: "
        f"ok={contract.get('ok')}, "
        f"errors={summary.get('errors')}, "
        f"warnings={summary.get('warnings')}, "
        f"checks={summary.get('checks')}"
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
    event_totals = (
        event_ledger.get("totals")
        if isinstance(event_ledger.get("totals"), dict)
        else {}
    )
    if event_ledger.get("available") and event_totals:
        by_class_24h = (
            event_totals.get("by_class_24h")
            if isinstance(event_totals.get("by_class_24h"), dict)
            else {}
        )
        by_class_7d = (
            event_totals.get("by_class_7d")
            if isinstance(event_totals.get("by_class_7d"), dict)
            else {}
        )
        lines.extend(
            [
                "",
                "## Event Ledger Summary",
                "- summary: "
                f"source={_markdown_scalar(event_ledger.get('source') or '')} "
                f"samples={event_ledger.get('sample_run_count')} "
                f"events_24h={event_totals.get('events_24h')} "
                f"events_7d={event_totals.get('events_7d')} "
                f"benchmark_runs_24h={event_totals.get('benchmark_runs_24h', 0)} "
                f"benchmark_runs_7d={event_totals.get('benchmark_runs_7d', 0)} "
                f"classes_24h={_event_class_count_text(by_class_24h)} "
                f"classes_7d={_event_class_count_text(by_class_7d)}",
            ]
        )
        event_goals = (
            event_ledger.get("goals")
            if isinstance(event_ledger.get("goals"), list)
            else []
        )
        for goal in event_goals[:3]:
            if not isinstance(goal, dict):
                continue
            goal_by_class_24h = (
                goal.get("by_class_24h")
                if isinstance(goal.get("by_class_24h"), dict)
                else {}
            )
            lines.append(
                "- "
                f"`{_markdown_scalar(goal.get('goal_id') or '')}`: "
                f"events_24h={goal.get('events_24h')} "
                f"events_7d={goal.get('events_7d')} "
                f"benchmark_runs_24h={goal.get('benchmark_runs_24h', 0)} "
                f"benchmark_runs_7d={goal.get('benchmark_runs_7d', 0)} "
                f"latest={_markdown_scalar(goal.get('latest_event_class') or '')} "
                f"classes_24h={_event_class_count_text(goal_by_class_24h)}"
            )

    promotion_readiness = (
        payload.get("promotion_readiness_summary")
        if isinstance(payload.get("promotion_readiness_summary"), dict)
        else {}
    )
    if promotion_readiness:
        lines.extend(
            [
                "",
                "## Promotion Readiness Summary",
                "- summary: "
                f"source={_markdown_scalar(promotion_readiness.get('source') or '')} "
                f"available={promotion_readiness.get('available')} "
                f"samples={promotion_readiness.get('sample_run_count')} "
                f"freshness={_markdown_scalar(promotion_readiness.get('freshness_status') or '')} "
                f"age_hours={promotion_readiness.get('age_hours')} "
                f"requires_readiness_run={promotion_readiness.get('requires_readiness_run')} "
                f"window_hours={promotion_readiness.get('freshness_window_hours')}",
                "- latest: "
                f"goal={_markdown_scalar(promotion_readiness.get('goal_id') or '')} "
                f"generated_at={_markdown_scalar(promotion_readiness.get('generated_at') or '')} "
                f"classification={_markdown_scalar(promotion_readiness.get('classification') or '')} "
                f"outcome={_markdown_scalar(promotion_readiness.get('delivery_outcome') or '')} "
                f"artifacts={promotion_readiness.get('json_exists')}/{promotion_readiness.get('markdown_exists')}",
            ]
        )

    promotion_gate = (
        payload.get("promotion_gate")
        if isinstance(payload.get("promotion_gate"), dict)
        else {}
    )
    promotion_gate_readiness = (
        promotion_gate.get("readiness")
        if isinstance(promotion_gate.get("readiness"), dict)
        else {}
    )
    if promotion_gate:
        lines.extend(
            [
                "",
                "## Promotion Gate",
                "- gate: "
                f"state={_markdown_scalar(promotion_gate.get('gate_state') or '')} "
                f"can_promote={promotion_gate.get('can_promote')} "
                f"should_warn={promotion_gate.get('should_warn')} "
                f"non_blocking={promotion_gate.get('non_blocking')} "
                f"freshness={_markdown_scalar(promotion_gate_readiness.get('freshness_status') or '')} "
                f"requires_readiness_run={promotion_gate_readiness.get('requires_readiness_run')}",
                "- latest: "
                f"generated_at={_markdown_scalar(promotion_gate_readiness.get('generated_at') or '')} "
                f"age_hours={promotion_gate_readiness.get('age_hours')} "
                f"action={_markdown_scalar(promotion_gate.get('recommended_action') or '')}",
            ]
        )
        if promotion_gate.get("warning_message"):
            lines.append(
                "- warning: "
                f"{_markdown_scalar(promotion_gate.get('warning_message') or '')}"
            )

    decision_freshness = (
        payload.get("decision_freshness_summary")
        if isinstance(payload.get("decision_freshness_summary"), dict)
        else {}
    )
    decision_summary = (
        decision_freshness.get("summary")
        if isinstance(decision_freshness.get("summary"), dict)
        else {}
    )
    if decision_freshness.get("available") and decision_summary:
        lines.extend(
            [
                "",
                "## Decision Freshness Summary",
                "- summary: "
                f"source={_markdown_scalar(decision_freshness.get('source') or '')} "
                f"samples={decision_freshness.get('sample_run_count')} "
                f"window_days={decision_freshness.get('window_days')} "
                f"decisions={decision_summary.get('decision_count')} "
                f"stale={decision_summary.get('stale_count')} "
                f"rebase_required={decision_summary.get('rebase_required_count')} "
                f"fresh={decision_summary.get('fresh_count')}",
            ]
        )
        decision_items = (
            decision_freshness.get("items")
            if isinstance(decision_freshness.get("items"), list)
            else []
        )
        for item in decision_items[:3]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"`{_markdown_scalar(item.get('goal_id') or '')}`: "
                f"kind={_markdown_scalar(item.get('decision_kind') or '')} "
                f"state={_markdown_scalar(item.get('freshness_state') or '')} "
                f"age_days={item.get('age_days')} "
                f"newer_7d={item.get('newer_event_count_7d')} "
                f"decision_at={_markdown_scalar(item.get('decision_at') or '')}"
            )

    usage = payload.get("usage_summary") if isinstance(payload.get("usage_summary"), dict) else {}
    usage_totals = usage.get("totals") if isinstance(usage.get("totals"), dict) else {}
    if usage.get("available") and usage_totals:
        lines.extend(
            [
                "",
                "## Usage Summary",
                "- summary: "
                f"source={_markdown_scalar(usage.get('source') or '')} "
                f"samples={usage.get('sample_run_count')} "
                f"runs_24h={usage_totals.get('runs_24h')} "
                f"runs_7d={usage_totals.get('runs_7d')} "
                f"quota_slots_24h={usage_totals.get('quota_spend_slots_24h')} "
                f"quota_slots_7d={usage_totals.get('quota_spend_slots_7d')} "
                f"automation_24h={usage_totals.get('automation_run_count_24h')} "
                f"automation_7d={usage_totals.get('automation_run_count_7d')} "
                f"progress_signals_24h={usage_totals.get('progress_signal_run_count_24h')} "
                f"progress_signals_7d={usage_totals.get('progress_signal_run_count_7d')}",
            ]
        )
        usage_goals = usage.get("goals") if isinstance(usage.get("goals"), list) else []
        for goal in usage_goals[:3]:
            if not isinstance(goal, dict):
                continue
            lines.append(
                "- "
                f"`{_markdown_scalar(goal.get('goal_id') or '')}`: "
                f"runs_24h={goal.get('runs_24h')} "
                f"runs_7d={goal.get('runs_7d')} "
                f"quota_slots_24h={goal.get('quota_spend_slots_24h')} "
                f"automation_24h={goal.get('automation_run_count_24h')} "
                f"progress_signals_24h={goal.get('progress_signal_run_count_24h')} "
                f"share_24h={goal.get('project_share_24h')}"
            )

    queue = payload.get("attention_queue") if isinstance(payload.get("attention_queue"), dict) else {}
    lines.extend(
        [
            "",
            "## Attention Queue",
            "- summary: "
            f"items={queue.get('item_count')}, "
            f"needs_user_or_controller={queue.get('needs_user_or_controller')}, "
            f"needs_controller={queue.get('needs_controller')}, "
            f"needs_codex={queue.get('needs_codex')}, "
            f"watching_external_evidence={queue.get('watching_external_evidence')}",
        ]
    )
    items = queue.get("items") if isinstance(queue.get("items"), list) else []
    goals = _goals_by_id(payload)
    backlog = (
        queue.get("autonomous_backlog_candidates")
        if isinstance(queue.get("autonomous_backlog_candidates"), dict)
        else {}
    )
    if backlog:
        lines.append(
            "- autonomous_backlog_candidates: "
            f"open={backlog.get('open_count')} "
            f"source={_markdown_scalar(backlog.get('source') or '')}"
        )
        for candidate in backlog.get("items") or []:
            if not isinstance(candidate, dict):
                continue
            priority_text = ""
            if candidate.get("priority"):
                priority_text = f" priority={_markdown_scalar(candidate.get('priority') or '')}"
            lines.append(
                "  - autonomous_candidate: "
                f"goal={_markdown_scalar(candidate.get('goal_id') or '')}"
                f"{priority_text} "
                f"text={_markdown_scalar(candidate.get('text') or '')}"
            )
    if not items:
        lines.append("- none")
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("recommended_action") or "").replace("|", "\\|")
        lines.append(
            "- "
            f"`{item.get('goal_id')}`: "
            f"status={item.get('status')} "
            f"phase={item.get('lifecycle_phase')} "
            f"waiting_on={item.get('waiting_on')} "
            f"severity={item.get('severity')} "
            f"source={item.get('source')}"
        )
        if action:
            lines.append(f"  - action: {action}")
        authority_summary = _authority_registry_markdown_summary(goals.get(str(item.get("goal_id") or "")))
        if authority_summary:
            lines.append(f"  - authority_material: {authority_summary}")
        project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
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
                if asset_agent_todos:
                    todo_parts.append(f"agent_open={asset_agent_todos.get('open')}")
                lines.append(f"    - asset_todos: {' '.join(todo_parts)}")
                if asset_user_todos.get("next"):
                    lines.append(f"      - asset_user_todo: {_markdown_scalar(asset_user_todos.get('next') or '')}")
                for todo in (asset_user_todos.get("items") or [])[1:3]:
                    if isinstance(todo, dict) and todo.get("text"):
                        index = todo.get("index")
                        suffix = f"[{index}]" if index is not None else ""
                        lines.append(f"      - asset_user_todo{suffix}: {_markdown_scalar(todo.get('text') or '')}")
                if asset_agent_todos.get("next"):
                    lines.append(f"      - asset_agent_todo: {_markdown_scalar(asset_agent_todos.get('next') or '')}")
                for todo in (asset_agent_todos.get("items") or [])[1:3]:
                    if isinstance(todo, dict) and todo.get("text"):
                        index = todo.get("index")
                        suffix = f"[{index}]" if index is not None else ""
                        lines.append(f"      - asset_agent_todo{suffix}: {_markdown_scalar(todo.get('text') or '')}")
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
                    lines.append(
                        "      - post_handoff_run: "
                        f"classification={_markdown_scalar(latest_handoff_run.get('classification') or '')} "
                        f"at={_markdown_scalar(latest_handoff_run.get('generated_at') or '')} "
                        f"scale={_markdown_scalar(latest_handoff_run.get('delivery_batch_scale') or '')}"
                        f"{outcome_suffix}"
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
                        f"{gap_text}"
                    )
                if handoff_readiness.get("next_probe"):
                    handoff_probe = _markdown_scalar(handoff_readiness.get("next_probe") or "")
                    lines.append(f"      - handoff_probe: `{handoff_probe}`")
        user_todos = item.get("user_todos") if isinstance(item.get("user_todos"), dict) else {}
        if user_todos:
            lines.append(
                "  - user_todos: "
                f"open={user_todos.get('open_count')} "
                f"done={user_todos.get('done_count')} "
                f"total={user_todos.get('total_count')}"
            )
            for todo in user_todos.get("items") or []:
                if not isinstance(todo, dict) or todo.get("done"):
                    continue
                lines.append(f"    - next_user_todo: {_markdown_scalar(todo.get('text') or '')}")
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
            lines.append(
                "  - agent_todos: "
                f"open={agent_todos.get('open_count')} "
                f"done={agent_todos.get('done_count')} "
                f"total={agent_todos.get('total_count')}"
            )
            for todo in agent_todos.get("items") or []:
                if not isinstance(todo, dict) or todo.get("done"):
                    continue
                lines.append(f"    - next_agent_todo: {_markdown_scalar(todo.get('text') or '')}")
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
                    f"`goal-harness operator-gate --goal-id {goal_id} --decision approve "
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
