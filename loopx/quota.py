from __future__ import annotations

from copy import deepcopy
from enum import Enum
import fnmatch
import hashlib
import json
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .benchmark_core import compact_run_permission_policy_for_quota
from .boundary_authority import checkpointed_boundary_authority_summary
from .control_plane import (
    compact_control_plane_policy,
    control_plane_policy_summary,
    control_plane_self_repair_allows,
)
from .delivery_outcome import (
    ACCOUNTABLE_DELIVERY_OUTCOMES,
    DeliveryOutcome,
    normalize_delivery_outcome,
)
from .execution_profile import (
    execution_profile_outcome_floor,
    execution_profile_summary,
    outcome_floor_threshold,
)
from .long_task_cadence import long_task_cadence_hint_summary
from .orchestration import compact_orchestration_policy, orchestration_policy_summary
from .policies.execution_obligation import build_execution_obligation
from .policies.outcome_followthrough import build_outcome_followthrough_hint
from .policies.scheduler_hint import build_scheduler_hint
from .policies.work_lane import (
    WORK_LANE_CONTRACT_SCHEMA_VERSION,
    build_work_lane_contract as build_work_lane_contract_policy,
)
from .state_projection import is_user_wait_text, next_action_projection_warning
from .todo_contract import (
    TODO_STATUS_DEFERRED,
    TODO_STATUS_OPEN,
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_BLOCKER,
    TODO_TASK_CLASS_MONITOR,
    TODO_TASK_CLASS_USER_GATE,
    next_action_requires_advancement_text,
    normalize_required_capabilities,
    normalize_target_capabilities,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
    normalize_todo_decision_scope,
    normalize_todo_id,
    normalize_todo_required_decision_scopes,
    normalize_todo_resume_when,
    normalize_required_write_scopes,
    normalize_todo_status,
    normalize_todo_task_class,
)
from .todo_handoff_gate import HandoffGateState, build_todo_handoff_gate_states


DEFAULT_COMPUTE_QUOTA = 1.0
DEFAULT_WINDOW_HOURS = 24
DEFAULT_SLOT_MINUTES = 1
QUOTA_STATE_ORDER = (
    "blocked_health",
    "operator_gate",
    "focus_wait",
    "eligible",
    "waiting",
    "throttled",
    "paused",
)
QUOTA_SLOT_SPENT_CLASSIFICATION = "quota_slot_spent"
QUOTA_SLOT_VOIDED_CLASSIFICATION = "quota_slot_voided"
QUOTA_MONITOR_POLL_CLASSIFICATION = "quota_monitor_poll"
DEFAULT_SLOT_SPEND_SOURCE = "heartbeat"
VALID_SLOT_SPEND_SOURCES = {"heartbeat", "controller", "adapter"}
USER_GATE_ACTION_KIND_HINTS = (
    "approval",
    "approve",
    "boundary",
    "gate",
    "blocker",
    "credential",
    "private",
    "production",
    "leaderboard",
    "submission",
    "public_claim",
)
FOCUS_WAIT_LIFECYCLE_MARKERS = {
    "continuation_boundary",
    "focus_wait",
}
FOCUS_WAIT_REASON = (
    "focus wait: delivery lane has a continuation boundary or missing novelty; "
    "wait for new evidence, owner input, external eval, or a clean baseline before "
    "spending delivery compute"
)
READ_ONLY_MAP_ADAPTER_SUFFIX = "_read_only_map_v0"
HANDOFF_READINESS_COMPACT_FIELDS = (
    "ready",
    "codex_ready",
    "source",
    "quota_state",
    "handoff_status",
    "post_handoff_run_seen",
    "post_handoff_small_scale_streak",
    "post_handoff_outcome_gap_streak",
    "handoff_interface_budget",
)
POST_HANDOFF_RUN_COMPACT_FIELDS = (
    "generated_at",
    "classification",
    "progress_scope",
    "delivery_batch_scale",
    "delivery_outcome",
    "delivery_turn_kind",
    "health_check",
    "json_exists",
    "markdown_exists",
)
AUTONOMOUS_CANDIDATE_CONTEXT_FIELDS = (
    "source",
    "open_count",
    "task_class",
    "items",
)
SELF_REPAIR_SPEND_ACTIONS = {
    "control_plane_health_repair",
    "control_plane_projection_repair",
    "state_projection_gap_repair",
    "boundary_projection_repair",
}
STALL_HEALTH_ITEM_COMPACT_FIELDS = (
    "goal_id",
    "status",
    "waiting_on",
    "severity",
    "source",
    "recommended_action",
)
DECISION_FRESHNESS_WARNING_ITEM_LIMIT = 3
DEPENDENCY_OBSERVATION_CLASSIFICATION_HINTS = (
    "dependency_observed",
    "dependency_observation",
    "dependency_monitor",
)
EXTERNAL_EVIDENCE_OBSERVATION_SCHEMA_VERSION = "external_evidence_observation_obligation_v0"
INTERACTION_CONTRACT_SCHEMA_VERSION = "loopx_interaction_contract_v0"
PROTOCOL_ACTION_PACKET_SCHEMA_VERSION = "protocol_action_packet_v0"
AUTOMATION_LIVENESS_SCHEMA_VERSION = "automation_liveness_v0"
CAPABILITY_GATE_SCHEMA_VERSION = "capability_gate_v0"
SIDE_AGENT_WORKSPACE_GUARD_SCHEMA_VERSION = "side_agent_workspace_guard_v0"
AGENT_CLAIM_SCOPE_SCHEMA_VERSION = "agent_claim_scope_v0"
SIDE_AGENT_CLAIM_SCOPE_SCHEMA_VERSION = AGENT_CLAIM_SCOPE_SCHEMA_VERSION
AGENT_LANE_NEXT_ACTION_SCHEMA_VERSION = "agent_lane_next_action_v0"
AGENT_SCOPE_FRONTIER_SCHEMA_VERSION = "agent_scope_frontier_v0"
AGENT_LANE_FRONTIER_HINT_SCHEMA_VERSION = "agent_lane_frontier_hint_v0"
QUOTA_MONITOR_TARGET_SCHEMA_VERSION = "quota_monitor_target_v0"


class AgentScopeFrontierAction(str, Enum):
    AGENT_SCOPE_EXHAUSTED = "agent_scope_exhausted"
    AGENT_SCOPE_WAIT = "agent_scope_wait"
    REASSIGNMENT_REQUIRED = "reassignment_required"
    SUCCESSOR_REPLAN_REQUIRED = "successor_replan_required"


class AgentLaneFrontierHintDecision(str, Enum):
    CLAIM_UNOWNED_IN_SCOPE = "claim_unowned_in_scope"
    ADD_NEXT_ADVANCEMENT = "add_next_advancement"
    RECORD_NO_FOLLOWUP = "record_no_followup"
    QUIET_NOOP_BLOCKER = "quiet_noop_blocker"


DEFAULT_AVAILABLE_CAPABILITIES = (
    "shell",
    "filesystem_read",
    "filesystem_write",
)
CAPABILITY_REPAIR_BRIDGE_HINTS = {
    "benchmark_runner",
    "external_evidence_poll",
    "worker_bridge",
    "cli_bridge",
}
CAPABILITY_OWNER_GATE_HINTS = {
    "network",
    "credentials",
    "production_access",
}
TODO_BACKLOG_ITEM_LIMIT = 8
TODO_DEFERRED_VISIBILITY_LIMIT = 8
TODO_VISIBILITY_LANE_LIMIT = 16
MONITOR_DUE_ITEM_LIMIT = 1
TODO_MISSING_PRIORITY_RANK = 50
TODO_MISSING_INDEX = 999999
EXTERNAL_EVIDENCE_OBSERVE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:poll(?:ing)?|observ(?:e|ing)|watch(?:ing)?|await(?:ing)?|wait\s+for|monitor(?:ing)?)\b.*\b"
        r"(?:compact|result|artifact|marker|job|thread|run[-_\s]?id|worker|controller|writeback|trial[_\s-]?result)\b"
    ),
    re.compile(
        r"(?i)\bwhen\b.*\b(?:result|artifact|marker|trial[_\s-]?result)\b.*\b"
        r"(?:ingest|write\s*back|writeback|validate|review)\b"
    ),
)
EXTERNAL_EVIDENCE_LAUNCHED_PATTERNS = (
    re.compile(r"(?i)\b(?:launched|started|spawned|running|alive|materialized)\b.*\b(?:polling|result|marker)\b"),
    re.compile(r"(?i)(?:launched|started|spawned|running|alive|materialized)[_\s-]+(?:polling|result|marker)"),
    re.compile(r"(?i)\bready_for_compact_polling\b"),
    re.compile(r"(?i)\bcompact\b.*\bresult\b.*\b(?:not\s+ready|ingest\s+not\s+ready)\b"),
)
EXTERNAL_EVIDENCE_HANDLE_ABSENT_PATTERNS = (
    re.compile(
        r"(?i)\b(?:no|without|absent|missing)\b.*\b"
        r"(?:observable\s+)?(?:handle|channel|writeback|launch\s+summary|run[-_\s]?id|job)\b"
    ),
    re.compile(
        r"(?i)\b(?:handle|channel|writeback|launch\s+summary|run[-_\s]?id|job)\b.*\b"
        r"(?:absent|missing|not\s+available|does\s+not\s+exist|exists\s+yet)\b"
    ),
)

def _now_local() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _run_file_stem(generated_at: str) -> str:
    return re.sub(r"[^0-9A-Za-z-]+", "-", generated_at).strip("-")


def _unique_run_artifact_paths(runs_dir: Path, stem: str, suffix: str) -> tuple[Path, Path]:
    candidate = runs_dir / f"{stem}-{suffix}.json"
    markdown_candidate = runs_dir / f"{stem}-{suffix}.md"
    if not candidate.exists() and not markdown_candidate.exists():
        return candidate, markdown_candidate
    index = 2
    while True:
        candidate = runs_dir / f"{stem}-{suffix}-{index}.json"
        markdown_candidate = runs_dir / f"{stem}-{suffix}-{index}.md"
        if not candidate.exists() and not markdown_candidate.exists():
            return candidate, markdown_candidate
        index += 1


def _validate_goal_id_path_segment(goal_id: str) -> str:
    value = goal_id.strip()
    if not value:
        raise ValueError("goal id is required")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("goal id must be a single path segment")
    if Path(value).name != value:
        raise ValueError("goal id must not include path traversal")
    return value


def _number(value: Any, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _int_number(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _clamp_compute(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 2)


def _text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_text_values(item))
        return values
    return [str(value)]


def _has_focus_wait_marker(*values: Any) -> bool:
    for value in values:
        for text in _text_values(value):
            marker = text.strip().lower()
            if marker in FOCUS_WAIT_LIFECYCLE_MARKERS:
                return True
    return False


def _latest_run_progress_scope(run: dict[str, Any]) -> str:
    explicit = str(run.get("progress_scope") or "").strip()
    if explicit:
        return explicit
    classification = str(run.get("classification") or "").strip().lower()
    if any(hint in classification for hint in DEPENDENCY_OBSERVATION_CLASSIFICATION_HINTS):
        return "dependency_observation"
    return "primary_goal"


def _item_progress_scope(item: dict[str, Any]) -> str:
    explicit = str(item.get("progress_scope") or "").strip()
    if explicit:
        return explicit
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    project_explicit = str(project_asset.get("progress_scope") or "").strip()
    if project_explicit:
        return project_explicit
    handoff_readiness = (
        item.get("handoff_readiness")
        if isinstance(item.get("handoff_readiness"), dict)
        else {}
    )
    latest_handoff_run = (
        handoff_readiness.get("post_handoff_latest_run")
        if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
        else {}
    )
    if latest_handoff_run:
        return _latest_run_progress_scope(latest_handoff_run)
    return _latest_run_progress_scope(
        {
            "classification": item.get("status") or item.get("latest_run_classification"),
            "progress_scope": item.get("latest_run_progress_scope"),
        }
    )


def _external_evidence_poll_signal(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Detect launched external work whose next safe step is observation."""

    if (
        isinstance(agent_todo_summary, dict)
        and _todo_summary_claim_scope_agent_id(agent_todo_summary)
        and _open_todo_count(agent_todo_summary) <= 0
    ):
        return None

    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    action_texts = [
        str(value or "").strip()
        for value in (
            project_asset.get("next_action"),
            project_asset.get("recommended_action"),
            item.get("next_action"),
            item.get("recommended_action"),
        )
        if str(value or "").strip()
    ]
    todo_texts: list[str] = []
    launched_texts: list[str] = [
        str(value or "").strip()
        for value in (
            item.get("status"),
            item.get("latest_run_classification"),
            item.get("lifecycle_phase"),
        )
        if str(value or "").strip()
    ]
    lifecycle_flags = item.get("lifecycle_flags")
    if isinstance(lifecycle_flags, list):
        launched_texts.extend(
            str(value or "").strip()
            for value in lifecycle_flags
            if str(value or "").strip()
        )
    if isinstance(agent_todo_summary, dict):
        items = agent_todo_summary.get("first_open_items")
        if isinstance(items, list):
            for item_value in items:
                if not isinstance(item_value, dict):
                    continue
                for key in ("title", "text"):
                    value = str(item_value.get(key) or "").strip()
                    if value:
                        todo_texts.append(value)
                for key in ("note", "evidence", "reason"):
                    value = str(item_value.get(key) or "").strip()
                    if value:
                        launched_texts.append(value)

    all_texts = [*action_texts, *todo_texts, *launched_texts]
    if not all_texts:
        return None

    direct_observe_action = any(
        pattern.search(text)
        for pattern in EXTERNAL_EVIDENCE_OBSERVE_PATTERNS
        for text in action_texts
    )
    direct_observe_todo = any(
        pattern.search(text)
        for pattern in EXTERNAL_EVIDENCE_OBSERVE_PATTERNS
        for text in todo_texts
    )
    direct_observe_state = any(
        pattern.search(text)
        for pattern in EXTERNAL_EVIDENCE_OBSERVE_PATTERNS
        for text in launched_texts
    )
    launched_wait = bool(action_texts) and any(
        pattern.search(text)
        for pattern in EXTERNAL_EVIDENCE_LAUNCHED_PATTERNS
        for text in launched_texts
    )
    handle_absent = any(
        pattern.search(text)
        for pattern in EXTERNAL_EVIDENCE_HANDLE_ABSENT_PATTERNS
        for text in action_texts
    )
    if handle_absent and not launched_wait and not direct_observe_action and not direct_observe_state:
        return None
    direct_observe = direct_observe_action or direct_observe_todo or direct_observe_state
    if not direct_observe and not launched_wait:
        return None

    observation_target = next((text for text in action_texts if text), None) or next(
        (text for text in todo_texts if text),
        "",
    )
    return {
        "source": "active_state_or_latest_run",
        "trigger": "implicit_launched_external_poll",
        "observation_target": observation_target,
        "matched_signal": "launched_wait" if launched_wait else "direct_observe",
        "matched_channel": (
            "action"
            if launched_wait or direct_observe_action
            else "todo"
            if direct_observe_todo
            else "state"
        ),
    }


def _post_handoff_latest_run(item: dict[str, Any]) -> dict[str, Any]:
    handoff_readiness = (
        item.get("handoff_readiness")
        if isinstance(item.get("handoff_readiness"), dict)
        else {}
    )
    latest_run = (
        handoff_readiness.get("post_handoff_latest_run")
        if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
        else {}
    )
    return latest_run


def _outcome_followthrough_hint(item: dict[str, Any]) -> dict[str, Any] | None:
    return build_outcome_followthrough_hint(_post_handoff_latest_run(item))


def _work_lane_contract(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    progress_scope = _item_progress_scope(item)
    external_poll_signal = _external_evidence_poll_signal(item, agent_todo_summary=agent_todo_summary)
    todo_counts = _open_todo_task_counts(agent_todo_summary)
    due_monitor_items = _todo_summary_monitor_due_items(agent_todo_summary)
    due_monitor_count = _todo_summary_monitor_due_count(
        agent_todo_summary,
        due_items=due_monitor_items,
    )
    first_due_monitor = due_monitor_items[0] if due_monitor_items else None
    first_advancement = _first_executable_todo_item(agent_todo_summary)
    due_monitor_preempts_advancement = bool(
        first_due_monitor
        and (
            first_advancement is None
            or _todo_priority_rank(first_due_monitor) < _todo_priority_rank(first_advancement)
        )
    )
    return build_work_lane_contract_policy(
        progress_scope=progress_scope,
        external_poll_signal=external_poll_signal,
        todo_counts=todo_counts,
        monitor_due_count=due_monitor_count,
        due_monitor_items=due_monitor_items,
        first_advancement=first_advancement,
        due_monitor_preempts_advancement=due_monitor_preempts_advancement,
        outcome_followthrough=_outcome_followthrough_hint(item),
        next_action_requires_advancement=_next_action_requires_advancement(item),
        monitor_due_item_limit=MONITOR_DUE_ITEM_LIMIT,
    )


def _external_evidence_observation_obligation(
    item: dict[str, Any],
    *,
    state: str,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the machine contract for a waiting external-evidence monitor."""

    explicit_wait = state == "waiting" and str(item.get("waiting_on") or "") == "external_evidence"
    poll_signal = _external_evidence_poll_signal(item, agent_todo_summary=agent_todo_summary)
    if not explicit_wait and not poll_signal:
        return None
    if (
        not explicit_wait
        and poll_signal
        and isinstance(agent_todo_summary, dict)
        and _todo_summary_claim_scope_agent_id(agent_todo_summary)
        and _open_todo_count(agent_todo_summary) <= 0
    ):
        return None
    if (
        not explicit_wait
        and isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == "advancement_task"
    ):
        return None
    next_todo = ""
    if isinstance(agent_todo_summary, dict):
        next_todo = str(agent_todo_summary.get("next") or "").strip()
        if not next_todo:
            items = agent_todo_summary.get("first_open_items")
            if isinstance(items, list):
                for item_value in items:
                    if isinstance(item_value, dict) and str(item_value.get("text") or "").strip():
                        next_todo = str(item_value.get("text") or "").strip()
                        break
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    observation_target = next_todo or str(
        project_asset.get("next_action") or item.get("recommended_action") or ""
    ).strip()
    if poll_signal and poll_signal.get("observation_target"):
        observation_target = str(poll_signal.get("observation_target") or observation_target)

    return {
        "schema_version": EXTERNAL_EVIDENCE_OBSERVATION_SCHEMA_VERSION,
        "required": True,
        "kind": "external_evidence_monitor" if explicit_wait else "launched_external_work_monitor",
        "trigger": "registry_waiting_on_external_evidence"
        if explicit_wait
        else poll_signal.get("trigger"),
        "signal_source": poll_signal.get("source") if poll_signal else "registry",
        "scope": "read_only_observation",
        "must_attempt_observation": True,
        "delivery_allowed": False,
        "requires_observable_handle": True,
        "observable_handle_examples": [
            "thread_id",
            "automation_id",
            "job_id",
            "lock_or_result_marker",
            "compact_writeback_path",
        ],
        "observation_sources": [
            "active_state",
            "recommended_action",
            "goal_boundary.next_probe",
            "project_asset.agent_todos.next",
            "connected controller or thread status",
        ],
        "observation_target": _protocol_action_text(observation_target, limit=320),
        "if_handle_missing": (
            "write a compact blocker or launch-readiness fault; do not treat the "
            "missing worker/controller handle as unchanged external evidence"
        ),
        "if_handle_live_and_unchanged": "quiet_noop_no_spend",
        "if_material_transition": (
            "write back the compact result/blocker/state transition, validate, then "
            "spend exactly once when the writeback is substantive"
        ),
        "spend_policy": (
            "no spend for read-only unchanged observation; spend only after validated "
            "compact transition or blocker writeback"
        ),
    }


def _focus_wait_quota(payload: dict[str, Any]) -> dict[str, Any]:
    quota = dict(payload)
    quota["state"] = "focus_wait"
    quota["reason"] = FOCUS_WAIT_REASON
    quota["blocked_action_scope"] = "delivery_focus"
    quota["focus_wait"] = True
    return quota


def quota_with_handoff_outcome_floor(
    quota: dict[str, Any],
    *,
    waiting_on: str | None = None,
    project_asset: dict[str, Any] | None = None,
    handoff_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if waiting_on != "codex":
        return quota
    if not isinstance(handoff_readiness, dict) or not handoff_readiness:
        return quota
    profile = (
        project_asset.get("execution_profile")
        if isinstance(project_asset, dict) and isinstance(project_asset.get("execution_profile"), dict)
        else None
    )
    outcome_gap_streak = handoff_readiness.get("post_handoff_outcome_gap_streak")
    if not isinstance(outcome_gap_streak, int) or outcome_gap_streak <= 0:
        return quota
    threshold = outcome_floor_threshold(profile)
    if outcome_gap_streak < threshold:
        return quota
    state = str(quota.get("state") or "eligible")
    if state in {"blocked_health", "operator_gate", "waiting", "paused", "throttled"}:
        return quota

    floor = execution_profile_outcome_floor(profile)
    must_advance = [
        str(value).strip()
        for value in (floor.get("must_advance") if isinstance(floor.get("must_advance"), list) else [])
        if str(value).strip()
    ]
    avoid = [
        str(value).strip()
        for value in (floor.get("avoid") if isinstance(floor.get("avoid"), list) else [])
        if str(value).strip()
    ]
    reason_parts = [
        f"handoff outcome floor not met: outcome_gap_streak={outcome_gap_streak}/{threshold}",
        "report blocker without spend or return with outcome-scale evidence",
    ]
    if must_advance:
        reason_parts.append(f"must_advance={'+'.join(must_advance)}")
    if avoid:
        reason_parts.append(f"avoid={'+'.join(avoid)}")

    blocked = dict(quota)
    blocked["state"] = "focus_wait"
    blocked["reason"] = "; ".join(reason_parts)
    blocked["blocked_action_scope"] = "delivery_outcome_floor"
    blocked["focus_wait"] = True
    blocked["handoff_outcome_floor_block"] = True
    blocked["post_handoff_outcome_gap_streak"] = outcome_gap_streak
    blocked["outcome_gap_threshold"] = threshold
    if must_advance:
        blocked["must_advance"] = must_advance
        blocked["safe_bypass_allowed"] = True
        blocked["safe_bypass_kind"] = "outcome_floor_recovery"
        blocked["safe_bypass_policy"] = (
            "Outcome-floor recovery only: attempt one bounded "
            f"{'+'.join(must_advance)} evidence segment or write back a concrete blocker; "
            "avoid surface-only work; spend only after validated evidence/blocker writeback."
        )
    if avoid:
        blocked["avoid"] = avoid
    return blocked


def _quota_with_focus_wait_override(
    quota: dict[str, Any],
    *,
    waiting_on: str | None = None,
    lifecycle_phase: Any = None,
    lifecycle_flags: Any = None,
    status: Any = None,
) -> dict[str, Any]:
    if waiting_on != "codex":
        return quota
    if not _has_focus_wait_marker(lifecycle_phase, lifecycle_flags, status):
        return quota
    state = str(quota.get("state") or "eligible")
    if state in {"blocked_health", "operator_gate", "waiting", "paused"}:
        return quota
    return _focus_wait_quota(quota)


def goal_quota_config(goal: dict[str, Any] | None) -> dict[str, Any]:
    raw = goal.get("quota") if goal and isinstance(goal.get("quota"), dict) else {}
    if goal and "compute_quota" in goal and "compute" not in raw:
        raw = {**raw, "compute": goal.get("compute_quota")}
    compute = _clamp_compute(_number(raw.get("compute"), default=DEFAULT_COMPUTE_QUOTA))
    window_hours = max(1, _int_number(raw.get("window_hours"), default=DEFAULT_WINDOW_HOURS))
    slot_minutes = max(1, _int_number(raw.get("slot_minutes"), default=DEFAULT_SLOT_MINUTES))
    spent_slots = max(0, _int_number(raw.get("spent_slots"), default=0))
    default_allowed_slots = round((window_hours * 60 / slot_minutes) * compute)
    allowed_slots = max(0, _int_number(raw.get("allowed_slots"), default=default_allowed_slots))
    payload: dict[str, Any] = {
        "compute": compute,
        "window_hours": window_hours,
        "slot_minutes": slot_minutes,
        "allowed_slots": allowed_slots,
        "spent_slots": spent_slots,
    }
    if raw.get("next_eligible_at"):
        payload["next_eligible_at"] = str(raw.get("next_eligible_at"))
    return payload


def _load_quota_event_from_run(run: dict[str, Any]) -> dict[str, Any] | None:
    if str(run.get("classification") or "") not in {
        QUOTA_SLOT_SPENT_CLASSIFICATION,
        QUOTA_SLOT_VOIDED_CLASSIFICATION,
    }:
        return None
    event = run.get("quota_event") if isinstance(run.get("quota_event"), dict) else None
    if event:
        return event

    raw_json_path = str(run.get("json_path") or "")
    if not raw_json_path:
        return None
    json_path = Path(raw_json_path).expanduser()
    if not json_path.exists():
        return None
    try:
        record = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    event = record.get("quota_event") if isinstance(record.get("quota_event"), dict) else None
    return event


def _quota_event_run_key(run: dict[str, Any], event: dict[str, Any]) -> str:
    return str(event.get("run_generated_at") or run.get("generated_at") or "")


def goal_quota_with_spend_ledger(
    goal: dict[str, Any] | None,
    runs: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = goal_quota_config(goal)
    goal_id = str(goal.get("id") or "") if goal else ""
    current_time = now or datetime.now(timezone.utc).astimezone()
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    window_start = current_time - timedelta(hours=int(payload["window_hours"]))
    spent_by_run: dict[str, int] = {}
    voided_by_run: dict[str, int] = {}
    spend_event_count = 0
    void_event_count = 0

    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        generated_at = _parse_timestamp(run.get("generated_at"))
        if generated_at is None or generated_at < window_start or generated_at > current_time:
            continue
        event = _load_quota_event_from_run(run)
        if not event:
            continue
        event_type = str(event.get("event_type") or "")
        slots = max(0, _int_number(event.get("slots"), default=0))
        if slots <= 0:
            continue
        if event_type == QUOTA_SLOT_SPENT_CLASSIFICATION:
            run_key = _quota_event_run_key(run, event)
            if not run_key:
                continue
            spent_by_run[run_key] = spent_by_run.get(run_key, 0) + slots
            spend_event_count += 1
        elif event_type == QUOTA_SLOT_VOIDED_CLASSIFICATION:
            voided_run_generated_at = str(event.get("voided_run_generated_at") or "")
            if not voided_run_generated_at:
                continue
            voided_by_run[voided_run_generated_at] = voided_by_run.get(voided_run_generated_at, 0) + slots
            void_event_count += 1

    spent_slots = 0
    for run_key, slots in spent_by_run.items():
        spent_slots += max(0, slots - voided_by_run.get(run_key, 0))
    payload["spent_slots"] = spent_slots
    payload["spend_source"] = "runtime_events"
    payload["spend_event_count"] = spend_event_count
    if void_event_count:
        payload["void_event_count"] = void_event_count
    return payload


def quota_status(
    goal: dict[str, Any] | None,
    *,
    waiting_on: str | None = None,
    severity: str | None = None,
    lifecycle_phase: Any = None,
    lifecycle_flags: Any = None,
    status: Any = None,
) -> dict[str, Any]:
    payload = goal_quota_config(goal)
    compute = float(payload["compute"])
    spent_slots = int(payload["spent_slots"])
    allowed_slots = int(payload["allowed_slots"])

    if compute <= 0:
        state = "paused"
        reason = "compute quota is 0; automatic agent turns are paused"
    elif severity == "high":
        state = "blocked_health"
        reason = "health or contract blocker must clear before compute is spent"
    elif waiting_on in {"user_or_controller", "controller"}:
        state = "operator_gate"
        reason = "operator gate blocks gated delivery; safe non-gated steering may continue"
        payload["blocked_action_scope"] = "gated_delivery"
        payload["safe_bypass_allowed"] = True
        payload["safe_bypass_policy"] = (
            "Do not execute agent_command, adapter work, write-control, production actions, "
            "or the gated path. A heartbeat may spend one bounded turn on read-only steering, "
            "analysis, documentation, or another priority-stack item that does not depend on this gate."
        )
    elif waiting_on == "external_evidence":
        state = "waiting"
        reason = "external evidence is still pending; do not spend delivery compute yet"
    elif waiting_on == "codex" and _has_focus_wait_marker(lifecycle_phase, lifecycle_flags, status):
        state = "focus_wait"
        reason = FOCUS_WAIT_REASON
        payload["blocked_action_scope"] = "delivery_focus"
        payload["focus_wait"] = True
    elif waiting_on == "codex":
        if allowed_slots > 0 and spent_slots >= allowed_slots:
            state = "throttled"
            reason = f"{compute:g} compute quota spent {spent_slots}/{allowed_slots} slots in this window"
        else:
            state = "eligible"
            reason = f"{compute:g} compute quota; eligible for the next automatic agent turn"
    else:
        state = "waiting"
        reason = "no active Codex-ready work is currently selected"

    payload["state"] = state
    payload["reason"] = reason
    return payload


def _latest_run(goal: dict[str, Any]) -> dict[str, Any]:
    latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
    if latest_runs and isinstance(latest_runs[0], dict):
        return latest_runs[0]
    return {}


def _quota_sort_key(item: dict[str, Any]) -> tuple[int, float, int, str]:
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    state = str(quota.get("state") or "waiting")
    state_index = QUOTA_STATE_ORDER.index(state) if state in QUOTA_STATE_ORDER else len(QUOTA_STATE_ORDER)
    compute = _number(quota.get("compute"), default=DEFAULT_COMPUTE_QUOTA)
    spent_slots = _int_number(quota.get("spent_slots"), default=0)
    return (state_index, -compute, spent_slots, str(item.get("goal_id") or ""))


def _compact_todo_summary_item(item: dict[str, Any], *, text: str | None = None) -> dict[str, Any]:
    compact: dict[str, Any] = {
        "index": item.get("index"),
        "text": text if text is not None else item.get("text"),
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
    ):
        if item.get(key) is not None:
            compact[key] = item.get(key)
    required_write_scopes = normalize_required_write_scopes(compact.get("required_write_scopes"))
    if required_write_scopes:
        compact["required_write_scopes"] = required_write_scopes
    else:
        compact.pop("required_write_scopes", None)
    decision_scope = normalize_todo_decision_scope(compact.get("decision_scope"))
    if decision_scope:
        compact["decision_scope"] = decision_scope
    else:
        compact.pop("decision_scope", None)
    required_decision_scopes = normalize_todo_required_decision_scopes(
        compact.get("required_decision_scopes")
    )
    if required_decision_scopes:
        compact["required_decision_scopes"] = required_decision_scopes
    else:
        compact.pop("required_decision_scopes", None)
    compact["task_class"] = _todo_task_class(compact)
    return compact


def _available_capabilities(value: Any) -> list[str]:
    capabilities = list(DEFAULT_AVAILABLE_CAPABILITIES)
    for capability in normalize_required_capabilities(value):
        if capability not in capabilities:
            capabilities.append(capability)
    return capabilities


def _capability_missing_action(missing: list[str]) -> str:
    missing_set = set(missing)
    if not missing_set:
        return "run"
    if missing_set & CAPABILITY_REPAIR_BRIDGE_HINTS:
        return "repair_bridge"
    if missing_set & CAPABILITY_OWNER_GATE_HINTS:
        return "ask_owner"
    return "skip"


def _capability_candidate_item(
    item: dict[str, Any],
    *,
    missing: list[str],
    missing_target_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    text = str(item.get("text") or "").strip()
    payload = _compact_todo_summary_item(item, text=text)
    required = normalize_required_capabilities(item.get("required_capabilities"))
    targets = normalize_target_capabilities(item.get("target_capabilities"))
    payload["required_capabilities"] = required
    if targets:
        payload["target_capabilities"] = targets
    payload["missing_capabilities"] = missing
    payload["capability_action"] = _capability_missing_action(missing)
    missing_targets = normalize_target_capabilities(missing_target_capabilities)
    if missing_targets:
        payload["missing_target_capabilities"] = missing_targets
    if missing_targets and set(missing_targets) & CAPABILITY_REPAIR_BRIDGE_HINTS:
        payload["capability_repair_mode"] = True
        payload["capability_action"] = "repair_bridge"
    return payload


def _unblock_handoff_rank(
    raw_item: dict[str, Any],
    *,
    agent_id: str | None,
) -> int:
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    blocks_agent = normalize_todo_blocks_agent(raw_item.get("blocks_agent"))
    return (
        0
        if agent_id
        and claimed_by == agent_id
        and blocks_agent
        and blocks_agent != agent_id
        else 1
    )


def _primary_review_rank(raw_item: dict[str, Any], *, agent_id: str | None) -> int:
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    action_kind = str(raw_item.get("action_kind") or "").strip()
    return (
        0
        if agent_id
        and claimed_by == agent_id
        and (action_kind == "primary_review" or action_kind.startswith("primary_review_"))
        else 1
    )


def _agent_lane_candidate_sort_key(
    raw_item: dict[str, Any],
    *,
    agent_id: str | None,
    primary_agent: str | None,
    preferred_todo_ids: set[str] | None = None,
) -> tuple[int, int, int, int, int, int, int]:
    preferred_todo_ids = preferred_todo_ids or set()
    todo_id = str(raw_item.get("todo_id") or "").strip()
    active_next_rank = 0 if todo_id and todo_id in preferred_todo_ids else 1
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    claim_rank = 0 if agent_id and claimed_by == agent_id else 1
    repair_rank = 0 if raw_item.get("capability_repair_mode") is True else 1
    return (
        active_next_rank,
        claim_rank,
        _unblock_handoff_rank(raw_item, agent_id=agent_id),
        _todo_priority_rank(raw_item),
        _primary_review_rank(raw_item, agent_id=agent_id),
        repair_rank,
        _todo_index_rank(raw_item),
    )


def _sort_capability_runnable_candidates(
    runnable: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(agent_identity, dict):
        return runnable, None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return runnable, None
    primary_agent = normalize_todo_claimed_by(agent_identity.get("primary_agent"))
    policy = "active_next_then_claim_then_unblock_handoff_then_priority_then_repair"
    return (
        sorted(
            runnable,
            key=lambda item: _agent_lane_candidate_sort_key(
                item,
                agent_id=agent_id,
                primary_agent=primary_agent,
            ),
        ),
        policy,
    )


def _capability_gate(
    agent_todo_summary: dict[str, Any] | None,
    *,
    available_capabilities: list[str],
    agent_identity: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    active_next_action_executable_items = agent_todo_summary.get(
        "active_next_action_executable_items"
    )
    executable_backlog_items = agent_todo_summary.get("executable_backlog_items")
    first_executable_items = agent_todo_summary.get("first_executable_items")
    if (
        isinstance(active_next_action_executable_items, list)
        and active_next_action_executable_items
    ):
        raw_items = [
            *active_next_action_executable_items,
            *(
                executable_backlog_items
                if isinstance(executable_backlog_items, list)
                else []
            ),
        ]
        source = "agent_todo_summary.active_next_action_executable_items"
    elif isinstance(executable_backlog_items, list) and executable_backlog_items:
        raw_items = executable_backlog_items
        source = "agent_todo_summary.executable_backlog_items"
    elif isinstance(first_executable_items, list) and first_executable_items:
        raw_items = first_executable_items
        source = "agent_todo_summary.first_executable_items"
    else:
        raw_items = []
        source = "agent_todo_summary.executable_backlog_items"
    deduped_raw_items: list[Any] = []
    seen_raw: set[tuple[str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            deduped_raw_items.append(item)
            continue
        identity = (
            str(item.get("todo_id") or ""),
            str(item.get("text") or "").strip(),
        )
        if identity in seen_raw:
            continue
        seen_raw.add(identity)
        deduped_raw_items.append(item)
    raw_items = deduped_raw_items
    candidates = [
        item
        for item in raw_items
        if isinstance(item, dict)
        and _todo_item_is_actionable_open(item)
        and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    if not candidates:
        return None

    available = _available_capabilities(available_capabilities)
    blocked: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []
    saw_requirement = False
    for item in candidates:
        required = normalize_required_capabilities(item.get("required_capabilities"))
        targets = normalize_target_capabilities(item.get("target_capabilities"))
        if required or targets:
            saw_requirement = True
        hard_required = [capability for capability in required if capability not in targets]
        missing = [capability for capability in hard_required if capability not in available]
        missing_targets = [capability for capability in targets if capability not in available]
        if missing:
            blocked.append(_capability_candidate_item(item, missing=missing))
            continue
        runnable.append(
            _capability_candidate_item(
                item,
                missing=[],
                missing_target_capabilities=missing_targets,
            )
        )

    if not saw_requirement and not blocked:
        return None
    if runnable:
        runnable, candidate_order_policy = _sort_capability_runnable_candidates(
            runnable,
            agent_identity=agent_identity,
        )
        runnable_required: list[str] = []
        blocked_missing: list[str] = []
        repair_missing: list[str] = []
        for item in runnable:
            for capability in item.get("required_capabilities") or []:
                if capability not in runnable_required:
                    runnable_required.append(str(capability))
            if item.get("capability_repair_mode") is True:
                for capability in item.get("missing_target_capabilities") or []:
                    if capability not in repair_missing:
                        repair_missing.append(str(capability))
        for item in blocked:
            for capability in item.get("missing_capabilities") or []:
                if capability not in blocked_missing:
                    blocked_missing.append(str(capability))
        return {
            "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
            "source": source,
            "required": runnable_required,
            "available": available,
            "missing": [],
            "action": "run",
            "decision_owner": "agent",
            "selection_policy": "agent_steering_audit_over_runnable_candidates",
            "candidate_order_policy": candidate_order_policy or "projection_order",
            "runnable_count": len(runnable),
            "runnable_candidates": runnable,
            "blocked_candidates": blocked,
            "blocked_missing": blocked_missing,
            "repair_missing": repair_missing,
            "repair_candidate_count": sum(
                1 for item in runnable if item.get("capability_repair_mode") is True
            ),
            "reason": "capability gate projected runnable candidate set; agent chooses the actual todo",
        }

    missing_all: list[str] = []
    required_all: list[str] = []
    for item in blocked:
        for capability in item.get("required_capabilities") or []:
            if capability not in required_all:
                required_all.append(str(capability))
        for capability in item.get("missing_capabilities") or []:
            if capability not in missing_all:
                missing_all.append(str(capability))
    action = _capability_missing_action(missing_all)
    return {
        "schema_version": CAPABILITY_GATE_SCHEMA_VERSION,
        "source": source,
        "required": required_all,
        "available": available,
        "missing": missing_all,
        "action": action,
        "decision_owner": "capability_gate",
        "selection_policy": "no_runnable_candidate",
        "runnable_count": 0,
        "runnable_candidates": [],
        "blocked_candidates": blocked,
        "blocks_delivery": True,
        "reason": "all visible executable todo candidates require unavailable capabilities",
        "owner_action": (
            "provide an environment with the missing capability, mark the todo blocked, "
            "or add a lower-risk fallback todo"
        )
        if action == "ask_owner"
        else None,
    }


def _todo_priority_label(item: dict[str, Any]) -> str | None:
    priority = item.get("priority")
    if isinstance(priority, str) and priority.strip():
        return priority.strip().upper()
    text = " ".join(
        str(value or "")
        for value in (item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    match = re.search(r"\bP([0-4])\b", text.upper())
    if not match:
        return None
    return f"P{match.group(1)}"


def _todo_priority_rank(item: dict[str, Any]) -> int:
    priority = _todo_priority_label(item)
    if not priority:
        return TODO_MISSING_PRIORITY_RANK
    match = re.match(r"P([0-4])", priority)
    if not match:
        return TODO_MISSING_PRIORITY_RANK
    return int(match.group(1))


def _todo_index_rank(item: dict[str, Any]) -> int:
    try:
        return int(item.get("index"))
    except (TypeError, ValueError):
        return TODO_MISSING_INDEX


def _todo_projection_sort_key(item: dict[str, Any]) -> tuple[int, int]:
    return (_todo_priority_rank(item), _todo_index_rank(item))


def _claimed_visibility_items(items: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0 or len(items) <= limit:
        return items[:limit]
    claim_order: list[str] = []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if not claimed_by:
            continue
        if claimed_by not in buckets:
            buckets[claimed_by] = []
            claim_order.append(claimed_by)
        buckets[claimed_by].append(item)
    if not buckets:
        return items[:limit]

    original_index = {id(item): index for index, item in enumerate(items)}
    per_claimant_cap = max(1, limit // len(buckets))
    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    for claimed_by in claim_order:
        taken = 0
        for item in buckets[claimed_by]:
            if taken >= per_claimant_cap:
                break
            if len(selected) >= limit:
                break
            selected.append(item)
            selected_ids.add(id(item))
            taken += 1
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for item in items:
            if id(item) in selected_ids:
                continue
            selected.append(item)
            selected_ids.add(id(item))
            if len(selected) >= limit:
                break

    return sorted(selected, key=lambda item: original_index.get(id(item), 999999))[:limit]


def _agent_claim_scoped_open_items(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(agent_identity, dict):
        return open_items, None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return open_items, None

    def claim_bucket(item: dict[str, Any]) -> int:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claimed_by == agent_id:
            return 0
        if not claimed_by:
            return 1
        return 2

    current_agent_items = [item for item in open_items if claim_bucket(item) == 0]
    unclaimed_items = [item for item in open_items if claim_bucket(item) == 1]
    other_agent_claimed_items = [item for item in open_items if claim_bucket(item) == 2]
    selectable_items = sorted(
        [*current_agent_items, *unclaimed_items],
        key=lambda item: (claim_bucket(item), *_todo_projection_sort_key(item)),
    )
    claim_scope = {
        "schema_version": AGENT_CLAIM_SCOPE_SCHEMA_VERSION,
        "agent_id": agent_id,
        "agent_role": str(agent_identity.get("role") or ""),
        "primary_agent": normalize_todo_claimed_by(agent_identity.get("primary_agent")),
        "selection_order": "current_agent_claimed_then_unclaimed",
        "selectable_open_count": len(selectable_items),
        "current_agent_claimed_open_count": len(current_agent_items),
        "unclaimed_open_count": len(unclaimed_items),
        "other_agent_claimed_open_count": len(other_agent_claimed_items),
        "other_agent_claimed_weight": "diagnostic_only",
        "other_agent_claimed_items": [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in _claimed_visibility_items(other_agent_claimed_items, limit=3)
        ],
        "blocked_claimed_open_count": len(other_agent_claimed_items),
        "blocked_claimed_items": [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in _claimed_visibility_items(other_agent_claimed_items, limit=3)
        ],
    }
    return selectable_items, claim_scope


def _todo_item_claimed_by_agent_or_unclaimed(item: dict[str, Any], *, agent_id: str) -> bool:
    claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
    return not claimed_by or claimed_by == agent_id


def _agent_scope_selectable_todo_item(
    item: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
) -> bool:
    if not isinstance(agent_identity, dict):
        return True
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return True
    blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
    if blocks_agent and blocks_agent != agent_id:
        return False
    return _todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)


def _agent_scope_filter_user_gate_items(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    if not isinstance(agent_identity, dict):
        return open_items, [], None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return open_items, [], None

    current_agent_items: list[dict[str, Any]] = []
    other_agent_scoped_items: list[dict[str, Any]] = []
    for item in open_items:
        blocks_agent = normalize_todo_blocks_agent(item.get("blocks_agent"))
        if blocks_agent:
            if blocks_agent != agent_id:
                other_agent_scoped_items.append(item)
                continue
            current_agent_items.append(item)
            continue
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claimed_by and claimed_by != agent_id:
            other_agent_scoped_items.append(item)
            continue
        current_agent_items.append(item)
    if not other_agent_scoped_items:
        return open_items, [], None

    return (
        current_agent_items,
        other_agent_scoped_items,
        {
            "schema_version": "agent_scoped_user_gate_filter_v0",
            "agent_id": agent_id,
            "policy": (
                "user todos scoped to another agent by blocks_agent or claimed_by "
                "remain visible but do not block this agent's quota lane"
            ),
            "current_agent_blocking_open_count": len(current_agent_items),
            "other_agent_scoped_open_count": len(other_agent_scoped_items),
        },
    )


def _todo_summary_visibility_lanes(
    open_items: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    claimed_items = [item for item in open_items if normalize_todo_claimed_by(item.get("claimed_by"))]
    unclaimed_items = [item for item in open_items if not normalize_todo_claimed_by(item.get("claimed_by"))]
    claimed_advancement_items = [
        item
        for item in claimed_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    claimed_monitor_items = [
        item
        for item in claimed_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]

    def compact_items(items: list[dict[str, Any]], *, limit: int = TODO_BACKLOG_ITEM_LIMIT) -> list[dict[str, Any]]:
        return [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in items[:limit]
        ]

    lanes: dict[str, Any] = {
        "unclaimed_priority_open_items": compact_items(unclaimed_items),
        "claimed_open_items": compact_items(
            _claimed_visibility_items(claimed_items, limit=TODO_VISIBILITY_LANE_LIMIT),
            limit=TODO_VISIBILITY_LANE_LIMIT,
        ),
        "claimed_advancement_open_items": compact_items(
            _claimed_visibility_items(
                claimed_advancement_items,
                limit=TODO_VISIBILITY_LANE_LIMIT,
            ),
            limit=TODO_VISIBILITY_LANE_LIMIT,
        ),
        "claimed_monitor_open_items": compact_items(
            _claimed_visibility_items(
                claimed_monitor_items,
                limit=TODO_VISIBILITY_LANE_LIMIT,
            ),
            limit=TODO_VISIBILITY_LANE_LIMIT,
        ),
    }
    if claimed_items:
        lanes["claimed_advancement_open_count"] = len(claimed_advancement_items)
        lanes["claimed_monitor_open_count"] = len(claimed_monitor_items)

    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_items = [
            item
            for item in claimed_items
            if normalize_todo_claimed_by(item.get("claimed_by")) == agent_id
        ]
        claimed_by_others_items = [
            item
            for item in claimed_items
            if normalize_todo_claimed_by(item.get("claimed_by")) != agent_id
        ]
        current_agent_advancement_items = [
            item
            for item in current_agent_items
            if _todo_item_is_actionable_open(item)
            if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        ]
        current_agent_monitor_items = [
            item
            for item in current_agent_items
            if _todo_item_is_actionable_open(item)
            if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
        ]
        lanes.update(
            {
                "current_agent_claimed_open_items": compact_items(
                    current_agent_items,
                    limit=TODO_VISIBILITY_LANE_LIMIT,
                ),
                "current_agent_claimed_advancement_items": compact_items(
                    current_agent_advancement_items,
                    limit=TODO_VISIBILITY_LANE_LIMIT,
                ),
                "current_agent_claimed_monitor_items": compact_items(
                    current_agent_monitor_items,
                    limit=TODO_VISIBILITY_LANE_LIMIT,
                ),
                "claimed_by_others_items": compact_items(claimed_by_others_items),
                "current_agent_claimed_open_count": len(current_agent_items),
                "current_agent_claimed_advancement_count": len(current_agent_advancement_items),
                "current_agent_claimed_monitor_count": len(current_agent_monitor_items),
                "claimed_by_others_count": len(claimed_by_others_items),
            }
        )
    return lanes


def _todo_item_is_deferred(item: dict[str, Any]) -> bool:
    return (normalize_todo_status(item.get("status")) or "") == TODO_STATUS_DEFERRED


def _todo_summary_deferred_items(value: dict[str, Any], key: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    source_items = value.get(key) if isinstance(value.get(key), list) else []
    if not source_items and key == "deferred_items":
        source_items = [
            item
            for item in value.get("items", [])
            if isinstance(item, dict) and _todo_item_is_deferred(item)
        ]
    items: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        compact = _compact_todo_summary_item(item, text=text)
        resume_when = normalize_todo_resume_when(item.get("resume_when"))
        if resume_when:
            compact["resume_when"] = resume_when
        if item.get("resume_condition") is not None:
            compact["resume_condition"] = item.get("resume_condition")
        if item.get("resume_ready") is not None:
            compact["resume_ready"] = bool(item.get("resume_ready"))
        if _todo_item_is_deferred(compact):
            items.append(compact)
    return sorted(items, key=_todo_projection_sort_key)


def _agent_claim_filtered_deferred_items(
    items: list[dict[str, Any]],
    *,
    agent_id: str | None,
    claim: str,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in items:
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claim == "current" and claimed_by != agent_id:
            continue
        if claim == "unclaimed" and claimed_by:
            continue
        if claim == "other" and (not claimed_by or claimed_by == agent_id):
            continue
        selected.append(item)
    return selected


def _deferred_visibility_lanes(
    value: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    deferred_items = _todo_summary_deferred_items(value, "deferred_items")
    deferred_resume_candidates = [
        item
        for item in _todo_summary_deferred_items(value, "deferred_resume_candidates")
        if item.get("resume_ready") is True
    ]
    if not deferred_items and not deferred_resume_candidates and not value.get("deferred_count"):
        return {}

    lanes: dict[str, Any] = {
        "deferred_count": value.get("deferred_count", len(deferred_items)),
        "deferred_visibility_limit": TODO_DEFERRED_VISIBILITY_LIMIT,
        "deferred_items": deferred_items[:TODO_DEFERRED_VISIBILITY_LIMIT],
        "deferred_resume_candidates": deferred_resume_candidates[:TODO_DEFERRED_VISIBILITY_LIMIT],
    }
    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="current",
        )
        unclaimed_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="unclaimed",
        )
        other_agent_candidates = _agent_claim_filtered_deferred_items(
            deferred_resume_candidates,
            agent_id=agent_id,
            claim="other",
        )
        lanes.update(
            {
                "current_agent_deferred_resume_candidates": current_agent_candidates[:TODO_DEFERRED_VISIBILITY_LIMIT],
                "unclaimed_deferred_resume_candidates": unclaimed_candidates[:TODO_DEFERRED_VISIBILITY_LIMIT],
                "other_agent_deferred_resume_candidates": other_agent_candidates[:TODO_DEFERRED_VISIBILITY_LIMIT],
                "current_agent_deferred_resume_count": len(current_agent_candidates),
                "unclaimed_deferred_resume_count": len(unclaimed_candidates),
                "other_agent_deferred_resume_count": len(other_agent_candidates),
                "deferred_resume_selection_policy": (
                    "quota may wake the current side-agent only for ready deferred "
                    "todos claimed by that agent or unclaimed; other-agent deferred "
                    "todos remain diagnostic visibility"
                ),
            }
        )
    return lanes


def _todo_summary_source_items(value: dict[str, Any]) -> list[dict[str, Any]]:
    source_keys = (
        "active_next_action_items",
        "active_next_action_executable_items",
        "first_open_items",
        "backlog_items",
        "unclaimed_priority_open_items",
        "claimed_open_items",
        "claimed_advancement_open_items",
        "claimed_monitor_open_items",
        "current_agent_claimed_open_items",
        "current_agent_claimed_advancement_items",
        "current_agent_claimed_monitor_items",
        "items",
    )
    open_items: list[dict[str, Any]] = []
    for key in source_keys:
        source_items = value.get(key) if isinstance(value.get(key), list) else []
        for item in source_items:
            if not isinstance(item, dict) or item.get("done") is True:
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            duplicate = any(
                existing.get("todo_id") == item.get("todo_id")
                if item.get("todo_id") and existing.get("todo_id")
                else existing.get("index") == item.get("index")
                and str(existing.get("text") or "").strip() == text
                for existing in open_items
            )
            if duplicate:
                continue
            open_items.append(_compact_todo_summary_item(item, text=text))
    return open_items


def _todo_summary_handoff_gates(value: dict[str, Any]) -> list[dict[str, Any]]:
    projected = value.get("handoff_gates")
    if isinstance(projected, list):
        return [item for item in projected if isinstance(item, dict)]
    source_items = value.get("items") if isinstance(value.get("items"), list) else []
    return build_todo_handoff_gate_states(source_items)


def _handoff_gate_lanes(
    value: dict[str, Any],
    *,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any]:
    handoff_gates = _todo_summary_handoff_gates(value)
    if not handoff_gates:
        return {}
    lanes: dict[str, Any] = {
        "handoff_gate_count": len(handoff_gates),
        "handoff_gates": handoff_gates[:TODO_BACKLOG_ITEM_LIMIT],
    }
    agent_id = (
        normalize_todo_claimed_by(agent_identity.get("agent_id"))
        if isinstance(agent_identity, dict)
        else None
    )
    if agent_id:
        current_agent_items = [
            item
            for item in handoff_gates
            if normalize_todo_blocks_agent(item.get("blocks_agent")) == agent_id
        ]
        cleared_without_successor = [
            item
            for item in current_agent_items
            if item.get("gate_state")
            == HandoffGateState.CLEARED_WITHOUT_SUCCESSOR.value
        ]
        lanes.update(
            {
                "current_agent_handoff_gate_count": len(current_agent_items),
                "current_agent_handoff_gates": current_agent_items[:TODO_BACKLOG_ITEM_LIMIT],
                "current_agent_cleared_without_successor_handoff_count": len(
                    cleared_without_successor
                ),
                "current_agent_cleared_without_successor_handoff_gates": (
                    cleared_without_successor[:TODO_BACKLOG_ITEM_LIMIT]
                ),
            }
        )
    return lanes


def _is_user_gate_todo_item(item: dict[str, Any]) -> bool:
    if _todo_task_class(item) == TODO_TASK_CLASS_USER_GATE:
        return True
    action_kind = str(item.get("action_kind") or "").strip().lower()
    if not action_kind:
        return False
    return any(hint in action_kind for hint in USER_GATE_ACTION_KIND_HINTS)


def _summarize_user_todos(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    all_open_items = sorted(
        _todo_summary_source_items(value),
        key=_todo_projection_sort_key,
    )
    blocking_open_items = all_open_items
    other_agent_scoped_items: list[dict[str, Any]] = []
    agent_scope_filter: dict[str, Any] | None = None
    if filter_user_gate_blocks_agent:
        (
            blocking_open_items,
            other_agent_scoped_items,
            agent_scope_filter,
        ) = _agent_scope_filter_user_gate_items(
            all_open_items,
            agent_identity=agent_identity,
        )
    open_items, claim_scope = _agent_claim_scoped_open_items(
        blocking_open_items,
        agent_identity=agent_identity,
    )
    executable_items = [
        item
        for item in open_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    monitor_items = [
        item
        for item in open_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_due_items = [
        item
        for item in monitor_items
        if _todo_item_is_due_monitor(item)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ]
    claimed_open_items = [item for item in blocking_open_items if item.get("claimed_by")]
    gate_items = [
        item
        for item in open_items
        if _is_user_gate_todo_item(item)
    ]
    active_next_action_items = [
        _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        for item in (value.get("active_next_action_items") or [])
        if isinstance(item, dict)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ] if isinstance(value.get("active_next_action_items"), list) else []
    active_next_action_executable_items = [
        _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        for item in (value.get("active_next_action_executable_items") or [])
        if isinstance(item, dict)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ] if isinstance(value.get("active_next_action_executable_items"), list) else []
    open_count = value.get("open_count", len(all_open_items))
    if claim_scope is not None:
        open_count = len(open_items)
    if agent_scope_filter is not None:
        open_count = len(blocking_open_items)
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section"),
        "total_count": value.get("total_count"),
        "open_count": open_count,
        "done_count": value.get("done_count"),
        "first_open_items": open_items[:3],
        "first_executable_items": executable_items[:3],
        "gate_open_items": gate_items[:3],
        "monitor_open_items": monitor_items,
        "monitor_due_count": len(monitor_due_items),
        "monitor_due_items": monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "active_next_action_items": active_next_action_items,
        "active_next_action_executable_items": active_next_action_executable_items,
        "backlog_items": open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    summary.update(
        _todo_summary_visibility_lanes(
            blocking_open_items,
            agent_identity=agent_identity,
        )
    )
    summary.update(
        _deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
        )
    )
    summary.update(
        _handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
        )
    )
    if claimed_open_items or value.get("claimed_open_count"):
        summary["claimed_open_count"] = value.get("claimed_open_count", len(claimed_open_items))
        summary["unclaimed_open_count"] = value.get(
            "unclaimed_open_count",
            max(0, int(open_count or 0) - len(claimed_open_items)),
        )
    if claim_scope:
        summary["claim_scope"] = claim_scope
    if agent_scope_filter:
        summary["agent_scope_filter"] = agent_scope_filter
        summary["all_open_count"] = value.get("open_count", len(all_open_items))
        summary["other_agent_scoped_open_count"] = len(other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    return summary


def _summarize_project_asset_todos(
    value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if (
        isinstance(value.get("items"), list)
        or isinstance(value.get("first_open_items"), list)
    ) and (
        "total_count" in value or "open_count" in value or "done_count" in value
    ):
        return _summarize_user_todos(
            value,
            agent_identity=agent_identity,
            filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
        )

    all_open_items = sorted(
        _todo_summary_source_items(value),
        key=_todo_projection_sort_key,
    )
    if not all_open_items:
        next_text = str(value.get("next") or "").strip()
        next_index = value.get("next_index", 1)
        all_open_items = [{"index": next_index, "text": next_text}] if next_text else []
        next_claimed_by = str(value.get("next_claimed_by") or "").strip()
        if all_open_items and next_claimed_by:
            all_open_items[0]["claimed_by"] = next_claimed_by
    blocking_open_items = all_open_items
    other_agent_scoped_items: list[dict[str, Any]] = []
    agent_scope_filter: dict[str, Any] | None = None
    if filter_user_gate_blocks_agent:
        (
            blocking_open_items,
            other_agent_scoped_items,
            agent_scope_filter,
        ) = _agent_scope_filter_user_gate_items(
            all_open_items,
            agent_identity=agent_identity,
        )
    open_items, claim_scope = _agent_claim_scoped_open_items(
        blocking_open_items,
        agent_identity=agent_identity,
    )
    executable_items = [
        item
        for item in open_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
    ]
    monitor_items = [
        item
        for item in open_items
        if _todo_item_is_actionable_open(item)
        if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
    ]
    monitor_due_items = [
        item
        for item in monitor_items
        if _todo_item_is_due_monitor(item)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ]
    active_next_action_items = [
        _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        for item in (value.get("active_next_action_items") or [])
        if isinstance(item, dict)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ] if isinstance(value.get("active_next_action_items"), list) else []
    active_next_action_executable_items = [
        _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
        for item in (value.get("active_next_action_executable_items") or [])
        if isinstance(item, dict)
        if _agent_scope_selectable_todo_item(item, agent_identity=agent_identity)
    ] if isinstance(value.get("active_next_action_executable_items"), list) else []
    claimed_open_items = [item for item in blocking_open_items if item.get("claimed_by")]
    open_count = value.get("open", value.get("open_count", len(all_open_items)))
    if claim_scope is not None:
        open_count = len(open_items)
    if agent_scope_filter is not None:
        open_count = len(blocking_open_items)
    summary = {
        "schema_version": value.get("schema_version"),
        "source_section": value.get("source_section") or "project_asset",
        "total_count": value.get("total", value.get("total_count")),
        "open_count": open_count,
        "done_count": value.get("done", value.get("done_count")),
        "first_open_items": open_items[:3],
        "first_executable_items": executable_items[:3],
        "monitor_open_items": monitor_items,
        "monitor_due_count": len(monitor_due_items),
        "monitor_due_items": monitor_due_items[:MONITOR_DUE_ITEM_LIMIT],
        "active_next_action_items": active_next_action_items,
        "active_next_action_executable_items": active_next_action_executable_items,
        "backlog_items": open_items[:TODO_BACKLOG_ITEM_LIMIT],
        "executable_backlog_items": executable_items[:TODO_BACKLOG_ITEM_LIMIT],
    }
    summary.update(
        _todo_summary_visibility_lanes(
            blocking_open_items,
            agent_identity=agent_identity,
        )
    )
    summary.update(
        _deferred_visibility_lanes(
            value,
            agent_identity=agent_identity,
        )
    )
    summary.update(
        _handoff_gate_lanes(
            value,
            agent_identity=agent_identity,
        )
    )
    if claimed_open_items or value.get("claimed_open_count"):
        summary["claimed_open_count"] = value.get("claimed_open_count", len(claimed_open_items))
        summary["unclaimed_open_count"] = value.get(
            "unclaimed_open_count",
            max(0, int(open_count or 0) - len(claimed_open_items)),
        )
    if claim_scope:
        summary["claim_scope"] = claim_scope
    if agent_scope_filter:
        summary["agent_scope_filter"] = agent_scope_filter
        summary["all_open_count"] = value.get("open", value.get("open_count", len(all_open_items)))
        summary["other_agent_scoped_open_count"] = len(other_agent_scoped_items)
        summary["other_agent_scoped_items"] = [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in other_agent_scoped_items[:TODO_VISIBILITY_LANE_LIMIT]
        ]
    return summary


def _is_canonical_attention_todo_summary(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("schema_version") == "todo_summary_v0":
        return True
    source_section = str(value.get("source_section") or "").strip().lower()
    if source_section.startswith("raw "):
        return False
    return source_section in {"agent todo", "user todo"}


def _select_todo_summary(
    canonical_value: Any,
    project_asset_value: Any,
    *,
    agent_identity: dict[str, Any] | None = None,
    filter_user_gate_blocks_agent: bool = False,
) -> dict[str, Any] | None:
    canonical_summary = _summarize_user_todos(
        canonical_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
    )
    project_asset_summary = _summarize_project_asset_todos(
        project_asset_value,
        agent_identity=agent_identity,
        filter_user_gate_blocks_agent=filter_user_gate_blocks_agent,
    )
    if _is_canonical_attention_todo_summary(canonical_value):
        return canonical_summary or project_asset_summary
    return project_asset_summary or canonical_summary


def _same_todo_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_id = str(left.get("todo_id") or "").strip()
    right_id = str(right.get("todo_id") or "").strip()
    if left_id and right_id:
        return left_id == right_id
    return (
        left.get("index") == right.get("index")
        and str(left.get("text") or "").strip() == str(right.get("text") or "").strip()
    )


def _blocked_priority_fallback(
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    first_open = (
        agent_todo_summary.get("first_open_items")
        if isinstance(agent_todo_summary.get("first_open_items"), list)
        else []
    )
    first_executable = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    selected = next((item for item in first_executable if isinstance(item, dict)), None)
    if not selected:
        return None

    blocked_items: list[dict[str, Any]] = []
    for item in first_open:
        if not isinstance(item, dict):
            continue
        if _same_todo_identity(item, selected):
            break
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        if item.get("done") is True:
            continue
        status = normalize_todo_status(item.get("status")) or TODO_STATUS_OPEN
        if status == TODO_STATUS_OPEN:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        blocked_items.append(_compact_todo_summary_item(item, text=text))

    if not blocked_items:
        return None
    selected_text = str(selected.get("text") or "").strip()
    selected_item = _compact_todo_summary_item(selected, text=selected_text) if selected_text else dict(selected)
    return {
        "schema_version": "blocked_priority_fallback_v0",
        "kind": "blocked_priority_fallback",
        "severity": "warning",
        "notify_user": True,
        "requires_user_action": False,
        "reason": (
            "a higher-priority agent todo is blocked or deferred before the "
            "selected executable fallback"
        ),
        "blocked_items": blocked_items[:3],
        "selected_executable": selected_item,
        "recommended_action": (
            "Surface the blocked core todo and why fallback is being selected; "
            "continue the fallback only if it still matches the latest user priority."
        ),
    }


_ACTION_SCOPE_STOPWORDS = {
    "a",
    "an",
    "and",
    "approve",
    "approved",
    "approval",
    "before",
    "blocked",
    "continue",
    "decide",
    "decision",
    "for",
    "from",
    "gate",
    "gated",
    "goal",
    "harness",
    "internal",
    "material",
    "next",
    "open",
    "owner",
    "p0",
    "p1",
    "p2",
    "p3",
    "provide",
    "read",
    "registered",
    "safe",
    "should",
    "sync",
    "the",
    "todo",
    "until",
    "user",
    "whether",
    "with",
}


def _action_scope_tokens_from_text(text: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            text.lower().replace("_", " ").replace("-", " "),
        )
        if len(token) > 1 and token not in _ACTION_SCOPE_STOPWORDS
    }


def _todo_action_kind_tokens(item: dict[str, Any]) -> set[str]:
    return _action_scope_tokens_from_text(str(item.get("action_kind") or ""))


def _todo_action_scope_tokens(item: dict[str, Any]) -> set[str]:
    text = " ".join(
        str(value or "")
        for value in (item.get("action_kind"), item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    return _action_scope_tokens_from_text(text)


_DECISION_SCOPE_GRANULARITY_RANK = {
    "action": 0,
    "lane": 1,
    "goal": 2,
    "project": 3,
    "global": 4,
}


def _decision_scope_covers(gate_scope: dict[str, Any], required_scope: dict[str, Any]) -> bool:
    gate = normalize_todo_decision_scope(gate_scope)
    required = normalize_todo_decision_scope(required_scope)
    if not gate or not required:
        return False
    if gate["kind"] != required["kind"]:
        return False
    if gate["scope_key"] not in {required["scope_key"], "*"}:
        return False
    return _DECISION_SCOPE_GRANULARITY_RANK[gate["granularity"]] >= _DECISION_SCOPE_GRANULARITY_RANK[
        required["granularity"]
    ]


def _decision_scope_gate_relation(
    gate: dict[str, Any],
    agent_item: dict[str, Any],
) -> dict[str, Any] | None:
    gate_scope = normalize_todo_decision_scope(gate.get("decision_scope"))
    required_scopes = normalize_todo_required_decision_scopes(
        agent_item.get("required_decision_scopes")
    )
    if not gate_scope:
        return None
    if not required_scopes:
        return {
            "schema_version": "decision_scope_relation_v0",
            "source": "decision_scope",
            "state": "independent",
            "reason": "agent_todo_has_no_required_decision_scopes",
            "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
            "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
            "decision_scope": gate_scope,
            "required_decision_scopes": [],
        }
    for required_scope in required_scopes:
        if _decision_scope_covers(gate_scope, required_scope):
            return {
                "schema_version": "decision_scope_relation_v0",
                "source": "decision_scope",
                "state": "gate_covers_action",
                "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
                "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
                "decision_scope": gate_scope,
                "matched_required_decision_scope": required_scope,
                "required_decision_scopes": required_scopes,
            }
    return {
        "schema_version": "decision_scope_relation_v0",
        "source": "decision_scope",
        "state": "independent",
        "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
        "agent_todo_id": normalize_todo_id(agent_item.get("todo_id")),
        "decision_scope": gate_scope,
        "required_decision_scopes": required_scopes,
    }


def _todo_gate_relation(gate: dict[str, Any], agent_item: dict[str, Any]) -> dict[str, Any] | None:
    decision_scope_relation = _decision_scope_gate_relation(gate, agent_item)
    if decision_scope_relation:
        return decision_scope_relation

    target_todo_id = normalize_todo_id(gate.get("unblocks_todo_id"))
    if not target_todo_id:
        return None
    agent_todo_id = normalize_todo_id(agent_item.get("todo_id"))
    return {
        "schema_version": "todo_gate_relation_v0",
        "source": "unblocks_todo_id",
        "state": "gate_targets_todo" if target_todo_id == agent_todo_id else "independent",
        "gate_todo_id": normalize_todo_id(gate.get("todo_id")),
        "target_todo_id": target_todo_id,
        "agent_todo_id": agent_todo_id,
    }


def _user_gate_blocks_agent_item(gate: dict[str, Any], agent_item: dict[str, Any]) -> bool:
    relation = _todo_gate_relation(gate, agent_item)
    if relation:
        return relation.get("state") in {"gate_targets_todo", "gate_covers_action"}

    gate_action_tokens = _todo_action_kind_tokens(gate)
    agent_action_tokens = _todo_action_kind_tokens(agent_item)
    if gate_action_tokens and agent_action_tokens:
        return bool(gate_action_tokens & agent_action_tokens)
    if agent_action_tokens:
        # A prose-only user gate may still be user-visible, but it is not
        # precise enough to block an explicitly scoped agent action.
        return False

    gate_tokens = _todo_action_scope_tokens(gate)
    agent_tokens = _todo_action_scope_tokens(agent_item)
    if not gate_tokens or not agent_tokens:
        return False
    if gate_action_tokens:
        return len(gate_action_tokens & agent_tokens) >= 2
    return len(gate_tokens & agent_tokens) >= 3


def _scoped_user_gate_fallback(
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    *,
    allow_unrelated_gate: bool = False,
) -> dict[str, Any] | None:
    gates = _open_user_gate_todo_items(user_todo_summary)
    if not gates or not isinstance(agent_todo_summary, dict):
        return None

    executable_items = (
        agent_todo_summary.get("executable_backlog_items")
        if isinstance(agent_todo_summary.get("executable_backlog_items"), list)
        else agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    executable_items = [item for item in executable_items if isinstance(item, dict)]
    claim_scope = (
        agent_todo_summary.get("claim_scope")
        if isinstance(agent_todo_summary.get("claim_scope"), dict)
        else None
    )
    if claim_scope:
        agent_id = normalize_todo_claimed_by(claim_scope.get("agent_id"))
        executable_items = [
            item
            for item in executable_items
            if normalize_todo_claimed_by(item.get("claimed_by")) in {"", agent_id}
        ]
    blocked_items: list[dict[str, Any]] = []
    selected: dict[str, Any] | None = None
    blocking_gate: dict[str, Any] | None = None
    for item in executable_items:
        matching_gate = next(
            (gate for gate in gates if _user_gate_blocks_agent_item(gate, item)),
            None,
        )
        if matching_gate:
            blocking_gate = blocking_gate or matching_gate
            text = str(item.get("text") or "").strip()
            blocked_item = _compact_todo_summary_item(item, text=text)
            relation = _todo_gate_relation(matching_gate, item)
            if relation:
                blocked_item["todo_gate_relation"] = relation
            blocked_items.append(blocked_item)
            continue
        if selected is None:
            selected = item

    if selected is None:
        return None
    if not blocking_gate and not allow_unrelated_gate:
        return None

    selected_text = str(selected.get("text") or "").strip()
    gate_to_surface = blocking_gate or gates[0]
    selected_item = _compact_todo_summary_item(selected, text=selected_text)
    selected_relation = _todo_gate_relation(gate_to_surface, selected)
    if selected_relation:
        selected_item["todo_gate_relation"] = selected_relation
    gate_text = str(gate_to_surface.get("text") or "").strip()
    reason = (
        "an open user_gate blocks a scoped agent todo, but a non-dependent "
        "executable fallback remains available"
        if blocking_gate
        else (
            "an open user_gate blocks a different action scope, but the selected "
            "executable agent todo is non-dependent and safe to advance"
        )
    )
    return {
        "schema_version": "scoped_user_gate_fallback_v0",
        "kind": "scoped_user_gate_fallback",
        "notify_user": True,
        "requires_user_action": True,
        "reason": reason,
        "blocked_user_gate": _compact_todo_summary_item(gate_to_surface, text=gate_text),
        "blocked_agent_items": blocked_items[:3],
        "selected_executable": selected_item,
        "recommended_action": (
            "Notify the user about the scoped gate; then execute the selected "
            "non-gated fallback and spend only after validated writeback."
        ),
    }


def _first_executable_todo_text(agent_todo_summary: dict[str, Any] | None) -> str | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    items = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        text = _protocol_action_text(item.get("text"), limit=320)
        if text:
            return text
    return None


def _first_monitor_todo_text(agent_todo_summary: dict[str, Any] | None) -> str | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    for key in ("monitor_due_items", "monitor_open_items"):
        items = agent_todo_summary.get(key) if isinstance(agent_todo_summary.get(key), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _todo_item_is_actionable_open(item):
                continue
            if _todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
                continue
            text = _protocol_action_text(item.get("text"), limit=320)
            if text:
                return text
    return None


def _agent_scoped_user_gate_override(
    *,
    state: str,
    item: dict[str, Any],
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if state != "operator_gate":
        return None
    if not isinstance(agent_identity, dict):
        return None
    if not isinstance(user_todo_summary, dict):
        return None
    if _open_todo_count(user_todo_summary) > 0:
        return None
    other_count = _open_todo_count(
        {"open_count": user_todo_summary.get("other_agent_scoped_open_count")}
    )
    if other_count <= 0:
        return None
    if item.get("operator_question") or item.get("missing_gates"):
        return None
    selected_action = _first_executable_todo_text(agent_todo_summary)
    if not selected_action:
        selected_action = _first_monitor_todo_text(agent_todo_summary)
    if not selected_action:
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    return {
        "schema_version": "agent_scoped_user_gate_override_v0",
        "kind": "agent_scoped_user_gate_override",
        "agent_id": agent_id,
        "from_state": "operator_gate",
        "to_state": "eligible",
        "other_agent_scoped_open_count": other_count,
        "selected_action": selected_action,
        "reason": (
            "the open user gate is scoped to another agent via blocks_agent or claimed_by; "
            "this agent still has an executable in-scope todo"
        ),
    }


def _agent_lane_next_action(
    *,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    capability_gate: dict[str, Any] | None,
    active_next_action: Any = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id or not isinstance(agent_todo_summary, dict):
        return None

    candidate_sources: list[tuple[str, list[Any]]] = []
    candidate_sources.append(
        (
            "agent_todo_summary.active_next_action_executable_items",
            agent_todo_summary.get("active_next_action_executable_items")
            if isinstance(agent_todo_summary.get("active_next_action_executable_items"), list)
            else [],
        )
    )
    if isinstance(capability_gate, dict) and capability_gate.get("action") == "run":
        candidate_sources.append(
            (
                "capability_gate.runnable_candidates",
                capability_gate.get("runnable_candidates")
                if isinstance(capability_gate.get("runnable_candidates"), list)
                else [],
            )
        )
    candidate_sources.append(
        (
            "agent_todo_summary.first_executable_items",
            agent_todo_summary.get("first_executable_items")
            if isinstance(agent_todo_summary.get("first_executable_items"), list)
            else [],
        )
    )
    candidate_sources.append(
        (
            "agent_todo_summary.executable_backlog_items",
            agent_todo_summary.get("executable_backlog_items")
            if isinstance(agent_todo_summary.get("executable_backlog_items"), list)
            else [],
        )
    )

    preferred_todo_ids = _todo_ids_from_action(active_next_action)

    primary_agent = normalize_todo_claimed_by(agent_identity.get("primary_agent"))

    seen: set[tuple[str, str]] = set()
    for source, raw_items in candidate_sources:
        source_candidates: list[dict[str, Any]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            if not _todo_item_is_actionable_open(raw_item):
                continue
            if _todo_task_class(raw_item) != TODO_TASK_CLASS_ADVANCEMENT:
                continue
            text = _protocol_action_text(raw_item.get("text"), limit=500)
            if not text:
                continue
            identity = (str(raw_item.get("todo_id") or ""), text)
            if identity in seen:
                continue
            claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
            if claimed_by and claimed_by != agent_id:
                continue
            seen.add(identity)
            source_candidates.append(raw_item)
        for raw_item in sorted(
            source_candidates,
            key=lambda item: _agent_lane_candidate_sort_key(
                item,
                agent_id=agent_id,
                primary_agent=primary_agent,
                preferred_todo_ids=preferred_todo_ids,
            ),
        ):
            text = _protocol_action_text(raw_item.get("text"), limit=500)
            claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
            todo_id = str(raw_item.get("todo_id") or "").strip()
            selected_by = (
                "active_next_action_todo"
                if todo_id and todo_id in preferred_todo_ids
                else
                "current_agent_claimed_todo"
                if claimed_by == agent_id
                else "unclaimed_todo"
            )
            payload = _compact_todo_summary_item(raw_item, text=text)
            if selected_by == "unclaimed_todo":
                payload["claim_required_before_work"] = True
            blocks_agent = normalize_todo_blocks_agent(raw_item.get("blocks_agent"))
            unblocks_todo_id = normalize_todo_id(raw_item.get("unblocks_todo_id"))
            if blocks_agent:
                payload["unblock_handoff"] = {"blocks_agent": blocks_agent}
                if unblocks_todo_id:
                    payload["unblock_handoff"]["unblocks_todo_id"] = unblocks_todo_id
            for key in (
                "missing_capabilities",
                "missing_target_capabilities",
                "capability_action",
                "capability_repair_mode",
            ):
                if raw_item.get(key) is not None:
                    payload[key] = raw_item.get(key)
            payload.update(
                {
                    "schema_version": AGENT_LANE_NEXT_ACTION_SCHEMA_VERSION,
                    "agent_id": agent_id,
                    "primary_agent": normalize_todo_claimed_by(
                        agent_identity.get("primary_agent")
                    ),
                    "source": source,
                    "selected_by": selected_by,
                    "confidence": (
                        "selected"
                        if selected_by
                        in {"active_next_action_todo", "current_agent_claimed_todo"}
                        else "candidate"
                    ),
                    "preserves_goal_next_action": True,
                }
            )
            return payload
    return None


def _count_advancement_items(items: Any, *, claimed_by: str | None = None) -> int:
    if not isinstance(items, list):
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        item_claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claimed_by == "__unclaimed__":
            if item_claimed_by:
                continue
        elif claimed_by is not None and item_claimed_by != claimed_by:
            continue
        count += 1
    return count


def _agent_scope_frontier_action(value: Any) -> AgentScopeFrontierAction | None:
    try:
        return AgentScopeFrontierAction(str(value or ""))
    except ValueError:
        return None


def _first_compact_todo_id(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        todo_id = normalize_todo_id(item.get("todo_id"))
        if todo_id:
            return todo_id
    return None


def _agent_lane_frontier_hint(
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_lane_next_action: dict[str, Any] | None,
    agent_scope_frontier: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict) or agent_identity.get("role") != "side-agent":
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return None
    primary_agent = normalize_todo_claimed_by(agent_identity.get("primary_agent"))

    def build_hint(
        decision: AgentLaneFrontierHintDecision,
        *,
        source: str,
        reason_code: str,
        target_todo_id: str | None = None,
        quiet_noop_allowed: bool,
        next_cli_action: str | None = None,
    ) -> dict[str, Any]:
        hint: dict[str, Any] = {
            "schema_version": AGENT_LANE_FRONTIER_HINT_SCHEMA_VERSION,
            "decision": decision.value,
            "agent_id": agent_id,
            "primary_agent": primary_agent,
            "source": source,
            "reason_code": reason_code,
            "quiet_noop_allowed": quiet_noop_allowed,
            "uses_structured_frontier": True,
        }
        if target_todo_id:
            hint["target_todo_id"] = target_todo_id
        if next_cli_action:
            hint["next_cli_action"] = next_cli_action
        return hint

    if isinstance(agent_lane_next_action, dict):
        selected_by = str(agent_lane_next_action.get("selected_by") or "")
        claim_required = agent_lane_next_action.get("claim_required_before_work") is True
        target_todo_id = normalize_todo_id(agent_lane_next_action.get("todo_id"))
        if selected_by == "unclaimed_todo" or claim_required:
            action = None
            if target_todo_id:
                action = (
                    f"loopx todo claim --goal-id {goal_id} --todo-id {target_todo_id} "
                    f"--claimed-by {agent_id}"
                )
            return build_hint(
                AgentLaneFrontierHintDecision.CLAIM_UNOWNED_IN_SCOPE,
                source="agent_lane_next_action",
                reason_code="unclaimed_advancement_selected",
                target_todo_id=target_todo_id,
                quiet_noop_allowed=False,
                next_cli_action=action,
            )

    frontier = agent_scope_frontier if isinstance(agent_scope_frontier, dict) else {}
    frontier_action = _agent_scope_frontier_action(frontier.get("action"))
    if frontier_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED:
        cleared_todo_id = _first_compact_todo_id(
            frontier.get("cleared_without_successor_handoff_gates")
        )
        if cleared_todo_id:
            return build_hint(
                AgentLaneFrontierHintDecision.RECORD_NO_FOLLOWUP,
                source="agent_scope_frontier",
                reason_code="cleared_handoff_without_successor",
                target_todo_id=cleared_todo_id,
                quiet_noop_allowed=False,
                next_cli_action=(
                    f"loopx todo complete --goal-id {goal_id} --todo-id {cleared_todo_id} "
                    "--no-follow-up --evidence '<public-safe rationale>'"
                ),
            )
        deferred_todo_id = _first_compact_todo_id(frontier.get("deferred_resume_candidates"))
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="successor_replan_required",
            target_todo_id=deferred_todo_id,
            quiet_noop_allowed=False,
        )

    if frontier_action in {
        AgentScopeFrontierAction.AGENT_SCOPE_WAIT,
        AgentScopeFrontierAction.REASSIGNMENT_REQUIRED,
    }:
        blocker_todo_id = _first_compact_todo_id(frontier.get("blocking_handoff_gates"))
        if not blocker_todo_id:
            blocker_todo_id = _first_compact_todo_id(frontier.get("other_agent_claimed_items"))
        if blocker_todo_id:
            return build_hint(
                AgentLaneFrontierHintDecision.QUIET_NOOP_BLOCKER,
                source="agent_scope_frontier",
                reason_code="blocked_by_other_agent_frontier",
                target_todo_id=blocker_todo_id,
                quiet_noop_allowed=True,
            )
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="no_current_agent_advancement_todo",
            quiet_noop_allowed=True,
        )

    if frontier_action == AgentScopeFrontierAction.AGENT_SCOPE_EXHAUSTED:
        return build_hint(
            AgentLaneFrontierHintDecision.ADD_NEXT_ADVANCEMENT,
            source="agent_scope_frontier",
            reason_code="agent_scope_exhausted",
            quiet_noop_allowed=True,
        )

    if not isinstance(agent_todo_summary, dict):
        return None
    current_advancement_count = int(
        agent_todo_summary.get("current_agent_claimed_advancement_count") or 0
    )
    current_monitor_count = int(agent_todo_summary.get("current_agent_claimed_monitor_count") or 0)
    unclaimed_count = _count_advancement_items(
        agent_todo_summary.get("unclaimed_priority_open_items"),
        claimed_by="__unclaimed__",
    )
    lane = str(work_lane_contract.get("lane") or "") if isinstance(work_lane_contract, dict) else ""
    if current_advancement_count == 0 and unclaimed_count == 0 and current_monitor_count > 0:
        return build_hint(
            AgentLaneFrontierHintDecision.QUIET_NOOP_BLOCKER,
            source="agent_todo_summary",
            reason_code="only_current_agent_monitor_work_remains",
            quiet_noop_allowed=lane != TODO_TASK_CLASS_ADVANCEMENT,
        )
    return None


def _agent_scope_deferred_resume_candidates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "current_agent_deferred_resume_candidates",
        "unclaimed_deferred_resume_candidates",
    ):
        value = agent_todo_summary.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
    if not candidates:
        value = agent_todo_summary.get("deferred_resume_candidates")
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
                if claimed_by and claimed_by != agent_id:
                    continue
                candidates.append(item)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        if item.get("resume_ready") is not True:
            continue
        if not _todo_item_is_deferred(item):
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(_compact_todo_summary_item(item, text=str(item.get("text") or "").strip()))
    return sorted(unique, key=_todo_projection_sort_key)


def _agent_scope_cleared_without_successor_handoff_gates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for key in (
        "current_agent_cleared_without_successor_handoff_gates",
        "handoff_gates",
    ):
        value = agent_todo_summary.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if normalize_todo_blocks_agent(item.get("blocks_agent")) != agent_id:
                continue
            if item.get("gate_state") != HandoffGateState.CLEARED_WITHOUT_SUCCESSOR.value:
                continue
            candidates.append(item)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        compact = dict(item)
        compact["text"] = str(item.get("text") or "").strip()
        unique.append(compact)
    return sorted(
        unique,
        key=lambda item: (
            -int(item.get("index") or 0),
            str(item.get("todo_id") or ""),
        ),
    )


def _agent_scope_blocking_handoff_gates(
    agent_todo_summary: dict[str, Any],
    *,
    agent_id: str,
) -> list[dict[str, Any]]:
    gates = agent_todo_summary.get("current_agent_handoff_gates")
    if not isinstance(gates, list):
        gates = agent_todo_summary.get("handoff_gates")
    if not isinstance(gates, list):
        return []
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in gates:
        if not isinstance(item, dict):
            continue
        if normalize_todo_blocks_agent(item.get("blocks_agent")) != agent_id:
            continue
        if item.get("gate_state") != HandoffGateState.BLOCKING.value:
            continue
        identity = str(item.get("todo_id") or item.get("index") or item.get("text") or "")
        if identity in seen:
            continue
        seen.add(identity)
        compact = dict(item)
        compact["text"] = str(item.get("text") or "").strip()
        selected.append(compact)
    return sorted(selected, key=_todo_projection_sort_key)


def _agent_scope_no_candidate_frontier(
    *,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    agent_lane_next_action: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    candidate_should_run: bool,
) -> dict[str, Any] | None:
    if not candidate_should_run:
        return None
    if not isinstance(agent_identity, dict) or agent_identity.get("role") != "side-agent":
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id or not isinstance(agent_todo_summary, dict):
        return None
    if isinstance(agent_lane_next_action, dict):
        return None
    has_advancement_contract = (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == TODO_TASK_CLASS_ADVANCEMENT
        and work_lane_contract.get("must_attempt_work") is True
    )

    current_agent_count = int(agent_todo_summary.get("current_agent_claimed_advancement_count") or 0)
    current_agent_count = max(
        current_agent_count,
        _count_advancement_items(
            agent_todo_summary.get("current_agent_claimed_advancement_items"),
            claimed_by=agent_id,
        ),
    )
    unclaimed_count = _count_advancement_items(
        agent_todo_summary.get("unclaimed_priority_open_items"),
        claimed_by="__unclaimed__",
    )
    executable_items = agent_todo_summary.get("executable_backlog_items")
    if isinstance(executable_items, list):
        current_agent_count = max(
            current_agent_count,
            _count_advancement_items(executable_items, claimed_by=agent_id),
        )
        unclaimed_count = max(
            unclaimed_count,
            _count_advancement_items(executable_items, claimed_by="__unclaimed__"),
        )
    if current_agent_count > 0 or unclaimed_count > 0:
        return None

    deferred_resume_candidates = _agent_scope_deferred_resume_candidates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if deferred_resume_candidates:
        first_candidate = deferred_resume_candidates[0]
        candidate_todo_id = str(first_candidate.get("todo_id") or "").strip() or "<todo_id>"
        reason = (
            f"current side-agent {agent_id} has no open current/unclaimed "
            "advancement candidate, but a deferred successor resume condition is satisfied"
        )
        recommended_action = (
            "Run a bounded successor replan before delivery: reopen, supersede, "
            f"or record a no-follow-up rationale for {candidate_todo_id}."
        )
        return {
            "schema_version": AGENT_SCOPE_FRONTIER_SCHEMA_VERSION,
            "agent_id": agent_id,
            "primary_agent": normalize_todo_claimed_by(agent_identity.get("primary_agent")),
            "action": AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
            "effective_action": AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
            "blocks_delivery": True,
            "requires_replan": True,
            "quiet_noop_allowed": False,
            "spend_policy": "spend once after validated successor replan/todo writeback",
            "reason": reason,
            "recommended_action": recommended_action,
            "candidate_counts": {
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "deferred_resume_candidate_count": len(deferred_resume_candidates),
            },
            "deferred_resume_candidates": deferred_resume_candidates[:3],
        }

    blocking_handoff_gates = _agent_scope_blocking_handoff_gates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if blocking_handoff_gates:
        blocking_review_claimants = sorted(
            {
                claimed_by
                for item in blocking_handoff_gates
                for claimed_by in [normalize_todo_claimed_by(item.get("claimed_by"))]
                if claimed_by
            }
        )
        owner = ", ".join(blocking_review_claimants) or "the owning agent"
        reason = (
            f"current side-agent {agent_id} has no current/unclaimed advancement "
            f"candidate; blocking handoff work is claimed by {owner}"
        )
        recommended_action = (
            f"Keep {agent_id} active but quiet: wait for {owner} to finish the "
            "blocking handoff, reassign it, or create a concrete current-agent/"
            "unclaimed advancement todo before delivery."
        )
        return {
            "schema_version": AGENT_SCOPE_FRONTIER_SCHEMA_VERSION,
            "agent_id": agent_id,
            "primary_agent": normalize_todo_claimed_by(agent_identity.get("primary_agent")),
            "action": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "effective_action": AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
            "blocks_delivery": True,
            "quiet_noop_allowed": True,
            "spend_policy": "no quota spend while the current agent has no in-scope runnable candidate",
            "reason": reason,
            "recommended_action": recommended_action,
            "candidate_counts": {
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "blocking_handoff_gate_count": len(blocking_handoff_gates),
            },
            "other_claimants": blocking_review_claimants,
            "blocking_review_claimants": blocking_review_claimants,
            "blocking_handoff_gates": blocking_handoff_gates[:3],
        }

    cleared_handoff_gates = _agent_scope_cleared_without_successor_handoff_gates(
        agent_todo_summary,
        agent_id=agent_id,
    )
    if cleared_handoff_gates:
        first_item = cleared_handoff_gates[0]
        blocker_todo_id = str(first_item.get("todo_id") or "").strip() or "<todo_id>"
        unblocks_todo_id = normalize_todo_id(first_item.get("unblocks_todo_id"))
        target_text = (
            f" for unblocked todo {unblocks_todo_id}"
            if unblocks_todo_id
            else ""
        )
        reason = (
            f"current side-agent {agent_id} has no open current/unclaimed "
            f"advancement candidate, but blocking handoff {blocker_todo_id}"
            f"{target_text} is already done without a projected successor"
        )
        recommended_action = (
            "Run a bounded successor replan before quiet wait: reopen or supersede "
            f"{blocker_todo_id} into a concrete {agent_id}/unclaimed advancement todo, "
            "or record an explicit no-follow-up rationale."
        )
        return {
            "schema_version": AGENT_SCOPE_FRONTIER_SCHEMA_VERSION,
            "agent_id": agent_id,
            "primary_agent": normalize_todo_claimed_by(agent_identity.get("primary_agent")),
            "action": AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
            "effective_action": AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
            "blocks_delivery": True,
            "requires_replan": True,
            "quiet_noop_allowed": False,
            "spend_policy": "spend once after validated successor replan/todo writeback",
            "reason": reason,
            "recommended_action": recommended_action,
            "candidate_counts": {
                "current_agent_claimed_advancement_count": current_agent_count,
                "unclaimed_advancement_count": unclaimed_count,
                "cleared_without_successor_handoff_count": len(cleared_handoff_gates),
            },
            "cleared_without_successor_handoff_gates": cleared_handoff_gates[:3],
        }

    claimed_advancement_items = (
        agent_todo_summary.get("claimed_advancement_open_items")
        if isinstance(agent_todo_summary.get("claimed_advancement_open_items"), list)
        else []
    )
    other_advancement_items = [
        item
        for item in claimed_advancement_items
        if isinstance(item, dict)
        and _todo_item_is_actionable_open(item)
        and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        and normalize_todo_claimed_by(item.get("claimed_by")) not in {None, "", agent_id}
    ]
    other_claimants = sorted(
        {
            claimed_by
            for item in other_advancement_items
            for claimed_by in [normalize_todo_claimed_by(item.get("claimed_by"))]
            if claimed_by
        }
    )
    blocking_review_items = [
        item
        for item in other_advancement_items
        if normalize_todo_claimed_by(item.get("blocks_agent")) == agent_id
    ]
    blocking_review_claimants = sorted(
        {
            claimed_by
            for item in blocking_review_items
            for claimed_by in [normalize_todo_claimed_by(item.get("claimed_by"))]
            if claimed_by
        }
    )
    claim_scope = (
        agent_todo_summary.get("claim_scope")
        if isinstance(agent_todo_summary.get("claim_scope"), dict)
        else {}
    )
    primary_agent = normalize_todo_claimed_by(agent_identity.get("primary_agent"))
    if not has_advancement_contract and not other_advancement_items:
        return None
    if other_advancement_items:
        if blocking_review_claimants:
            action = AgentScopeFrontierAction.AGENT_SCOPE_WAIT
            owner = ", ".join(blocking_review_claimants)
            reason = (
                f"current side-agent {agent_id} has no current/unclaimed advancement "
                f"candidate; blocking handoff work is claimed by {owner}"
            )
            recommended_action = (
                f"Keep {agent_id} active but quiet: wait for {owner} to finish the "
                "blocking handoff, reassign it, or create a concrete current-agent/"
                "unclaimed advancement todo before delivery."
            )
        else:
            action = (
                AgentScopeFrontierAction.AGENT_SCOPE_WAIT
                if primary_agent and primary_agent in other_claimants
                else AgentScopeFrontierAction.REASSIGNMENT_REQUIRED
            )
            owner = primary_agent or ", ".join(other_claimants) or "the owning agent"
            reason = (
                f"current side-agent {agent_id} has no current/unclaimed advancement "
                f"candidate; visible advancement work is claimed by {owner}"
            )
            recommended_action = (
                f"Keep {agent_id} active but quiet: wait for {owner} to finish, "
                "reassign, or create a concrete current-agent/unclaimed advancement "
                "todo before delivery."
            )
    else:
        action = AgentScopeFrontierAction.AGENT_SCOPE_EXHAUSTED
        reason = (
            f"current side-agent {agent_id} has no projected current/unclaimed "
            "advancement candidate despite a goal-level advancement lane"
        )
        recommended_action = (
            f"Keep {agent_id} active but quiet until LoopX projects a concrete "
            "current-agent or unclaimed advancement todo, or the primary reassigns work."
        )

    return {
        "schema_version": AGENT_SCOPE_FRONTIER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "primary_agent": primary_agent,
        "action": action.value,
        "effective_action": action.value,
        "blocks_delivery": True,
        "quiet_noop_allowed": True,
        "spend_policy": "no quota spend while the current agent has no in-scope runnable candidate",
        "reason": reason,
        "recommended_action": recommended_action,
        "candidate_counts": {
            "current_agent_claimed_advancement_count": current_agent_count,
            "unclaimed_advancement_count": unclaimed_count,
            "other_agent_claimed_advancement_count": len(other_advancement_items),
            "other_agent_claimed_open_count": int(
                claim_scope.get("other_agent_claimed_open_count") or 0
            ),
        },
        "other_claimants": other_claimants,
        "blocking_review_claimants": blocking_review_claimants,
        "other_agent_claimed_items": [
            _compact_todo_summary_item(item, text=str(item.get("text") or "").strip())
            for item in other_advancement_items[:3]
        ],
    }


def _todo_ids_from_action(value: Any) -> set[str]:
    text = str(value or "")
    if not text:
        return set()
    return set(re.findall(r"\btodo_[A-Za-z0-9_]+\b", text))


def _selected_recommended_action(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> Any:
    raw_action = item.get("recommended_action")
    if (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("monitor_kind") == "todo_monitor_due"
        and work_lane_contract.get("must_attempt_work") is True
    ):
        due_items = (
            work_lane_contract.get("monitor_due_items")
            if isinstance(work_lane_contract.get("monitor_due_items"), list)
            else []
        )
        for due_item in due_items:
            if not isinstance(due_item, dict):
                continue
            text = _protocol_action_text(due_item.get("text"), limit=320)
            if text:
                return text
        return raw_action
    if (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == "advancement_task"
        and "open_agent_todo" in (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
    ):
        return _first_executable_todo_text(agent_todo_summary) or raw_action
    return raw_action


def _work_lane_due_monitor_attempt(work_lane_contract: dict[str, Any] | None) -> bool:
    return bool(
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("monitor_kind") == "todo_monitor_due"
        and work_lane_contract.get("must_attempt_work") is True
    )


def _selected_action_with_agent_lane(
    selected_action: Any,
    *,
    agent_lane_next_action: dict[str, Any] | None,
) -> Any:
    if not isinstance(agent_lane_next_action, dict):
        return selected_action
    if agent_lane_next_action.get("source") not in {
        "capability_gate.runnable_candidates",
        "agent_todo_summary.active_next_action_executable_items",
    }:
        return selected_action
    selected_by = agent_lane_next_action.get("selected_by")
    confidence = agent_lane_next_action.get("confidence")
    if selected_by not in {"active_next_action_todo", "current_agent_claimed_todo", "unclaimed_todo"}:
        return selected_action
    if confidence not in {"selected", "candidate"}:
        return selected_action
    lane_text = str(agent_lane_next_action.get("text") or "").strip()
    return lane_text or selected_action


def _selected_action_with_capability_gate(
    selected_action: Any,
    *,
    capability_gate: dict[str, Any] | None,
) -> Any:
    if not isinstance(capability_gate, dict) or capability_gate.get("action") != "run":
        return selected_action
    blocked = (
        capability_gate.get("blocked_candidates")
        if isinstance(capability_gate.get("blocked_candidates"), list)
        else []
    )
    if not any(
        isinstance(item, dict)
        and _actions_are_projection_aligned(selected_action, item.get("text"))
        for item in blocked
    ):
        return selected_action
    runnable = (
        capability_gate.get("runnable_candidates")
        if isinstance(capability_gate.get("runnable_candidates"), list)
        else []
    )
    for item in runnable:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            return text
    return selected_action


def _normalize_action_for_compare(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    text = re.sub(r"^(?:agent|user|owner|codex)\s*:\s*", "", text)
    text = re.sub(r"^\[(?:p[0-9]+|[^\]]+)\]\s*", "", text)
    return text


def _action_label_for_compare(value: Any) -> str:
    text = _normalize_action_for_compare(value)
    match = re.match(r"([^:]{8,120}):", text)
    if match:
        return match.group(1).strip()
    return text[:120].strip()


def _action_prefix_for_compare(value: Any) -> str:
    text = _normalize_action_for_compare(value)
    text = re.split(r"[,.;:，。；：]", text, maxsplit=1)[0].strip()
    words = text.split()
    if len(words) >= 4:
        return " ".join(words[:6])
    return text


def _actions_are_projection_aligned(left: Any, right: Any) -> bool:
    left_text = _normalize_action_for_compare(left)
    right_text = _normalize_action_for_compare(right)
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    left_label = _action_label_for_compare(left_text)
    right_label = _action_label_for_compare(right_text)
    for label, text in ((left_label, right_text), (right_label, left_text)):
        if label and len(label) >= 8 and label in text:
            return True
    left_prefix = _action_prefix_for_compare(left_text)
    right_prefix = _action_prefix_for_compare(right_text)
    for prefix, text in ((left_prefix, right_text), (right_prefix, left_text)):
        if prefix and len(prefix) >= 24 and prefix in text:
            return True
    shorter, longer = sorted((left_text, right_text), key=len)
    return len(shorter) >= 32 and shorter in longer


def _state_action_projection_warning(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
    selected_action: Any,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == "advancement_task"
        and "open_agent_todo"
        in (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
    ):
        return None
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    active_next_action = str(
        item.get("active_state_next_action")
        or project_asset.get("next_action")
        or ""
    ).strip()
    selected_text = str(selected_action or "").strip()
    if not active_next_action or not selected_text:
        return None
    if isinstance(agent_todo_summary, dict):
        claim_scope = agent_todo_summary.get("claim_scope")
        first_executable = (
            agent_todo_summary.get("first_executable_items")
            if isinstance(agent_todo_summary.get("first_executable_items"), list)
            else []
        )
        selected_item = next((item for item in first_executable if isinstance(item, dict)), None)
        selected_claimed_by = normalize_todo_claimed_by(
            selected_item.get("claimed_by") if selected_item else None
        )
        claim_agent_id = normalize_todo_claimed_by(
            claim_scope.get("agent_id") if isinstance(claim_scope, dict) else None
        )
        if (
            selected_item
            and selected_claimed_by
            and claim_agent_id
            and selected_claimed_by == claim_agent_id
        ):
            return None
    if _actions_are_projection_aligned(active_next_action, selected_text):
        return None
    return {
        "schema_version": "state_action_projection_warning_v0",
        "kind": "state_action_projection_mismatch",
        "severity": "warning",
        "requires_state_writeback": True,
        "active_state_next_action": _protocol_action_text(active_next_action, limit=320),
        "selected_recommended_action": _protocol_action_text(selected_text, limit=320),
        "reason": (
            "quota selected the executable backlog item, but the active state's visible "
            "Next Action still points at a different action"
        ),
        "recommended_action": (
            "sync the active state Next Action to the selected protocol action, or treat "
            "protocol_action_packet / interaction_contract as authoritative over stale "
            "Next Action text"
        ),
    }


def _todo_write_hint(goal_id: str) -> dict[str, str]:
    return {
        "rule": (
            "Write concrete user/owner actions to User Todo, not Next Action, docs, or chat."
        ),
        "user_todo_command_template": (
            f"loopx todo add --goal-id {goal_id} --role user "
            "--text '<public-safe user/owner action>'"
        ),
        "agent_todo_command_template": (
            f"loopx todo add --goal-id {goal_id} --role agent "
            "--text '<public-safe agent action>'"
        ),
        "section": "User Todo / Owner Review Reading Queue",
    }


def _compact_handoff_readiness(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {field: value[field] for field in HANDOFF_READINESS_COMPACT_FIELDS if field in value}
    latest_run = (
        value.get("post_handoff_latest_run")
        if isinstance(value.get("post_handoff_latest_run"), dict)
        else {}
    )
    if latest_run:
        compact["post_handoff_latest_run"] = {
            field: latest_run[field]
            for field in POST_HANDOFF_RUN_COMPACT_FIELDS
            if field in latest_run
        }
    recent_runs = (
        value.get("post_handoff_recent_runs")
        if isinstance(value.get("post_handoff_recent_runs"), list)
        else []
    )
    compact_recent_runs: list[dict[str, Any]] = []
    for run in recent_runs:
        if not isinstance(run, dict):
            continue
        compact_run = {
            field: run[field]
            for field in POST_HANDOFF_RUN_COMPACT_FIELDS
            if field in run
        }
        if compact_run:
            compact_recent_runs.append(compact_run)
    if compact_recent_runs:
        compact["post_handoff_recent_runs"] = compact_recent_runs[:3]
    return compact or None


def _quota_execution_profile_summary(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact: dict[str, Any] = {}
    for field in ("cadence", "minimum_scale", "spend_rule"):
        if value.get(field):
            compact[field] = value[field]
    must_include = value.get("must_include")
    if isinstance(must_include, list) and must_include:
        compact["must_include"] = [str(item) for item in must_include[:3]]
    policy = (
        value.get("degradation_policy")
        if isinstance(value.get("degradation_policy"), dict)
        else {}
    )
    if policy.get("small_scale_streak_threshold") is not None:
        compact["small_scale_streak_threshold"] = policy.get("small_scale_streak_threshold")
    floor = execution_profile_outcome_floor(value)
    if floor:
        outcome_markers = (
            floor.get("outcome_markers")
            if isinstance(floor.get("outcome_markers"), list)
            else []
        )
        surface_hints = (
            floor.get("surface_only_hints")
            if isinstance(floor.get("surface_only_hints"), list)
            else []
        )
        compact["outcome_floor"] = {
            "configured": bool(outcome_markers or surface_hints),
            "surface_streak_threshold": floor.get("surface_streak_threshold"),
            "must_advance": [
                str(item)
                for item in (
                    floor.get("must_advance")
                    if isinstance(floor.get("must_advance"), list)
                    else []
                )[:2]
            ],
        }
    return compact or None


def _quota_execution_profile_boundary_summary(value: Any) -> dict[str, Any] | None:
    summary = _quota_execution_profile_summary(value)
    if not summary:
        return None
    compact = {}
    if summary.get("minimum_scale"):
        compact["minimum_scale"] = summary["minimum_scale"]
    return compact or None


def _compact_autonomous_candidate_context(
    value: Any,
    *,
    goal_id: str | None = None,
    limit: int = 3,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {field: value[field] for field in AUTONOMOUS_CANDIDATE_CONTEXT_FIELDS if field in value}
    items = compact.get("items")
    if isinstance(items, list):
        compact_items: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if goal_id and str(item.get("goal_id") or "") != goal_id:
                continue
            compact_item = {
                key: item[key]
                for key in ("goal_id", "task_class", "text")
                if item.get(key) is not None
            }
            if compact_item:
                compact_items.append(compact_item)
            if len(compact_items) >= limit:
                break
        if not compact_items:
            return None
        compact["items"] = compact_items
        compact["open_count"] = len(compact_items)
    return compact or None


def _protocol_action_text(value: Any, *, limit: int = 220) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _protocol_action_label(value: Any, *, limit: int = 80) -> str | None:
    text = _protocol_action_text(value)
    if not text:
        return None
    head, separator, _tail = text.partition(":")
    if separator and "[" in head and "]" in head and 8 <= len(head) <= limit:
        return head.strip()
    return _protocol_action_text(text, limit=limit)


def _protocol_todo_actions(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    first_open_items = summary.get("first_open_items")
    if not isinstance(first_open_items, list):
        return []
    actions: list[str] = []
    for item in first_open_items:
        if not isinstance(item, dict):
            continue
        text = _protocol_action_label(item.get("text"))
        if not text:
            continue
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def _user_todo_item_is_explicitly_non_gating(item: dict[str, Any]) -> bool:
    if item.get("gating") is False or item.get("non_gating") is True:
        return True
    if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR:
        return True
    action_kind = str(item.get("action_kind") or "").strip().lower()
    return action_kind in {
        "monitor",
        "observe",
        "watch",
        "fyi",
        "informational",
        "non_gating",
    }


def _user_channel_action_todo_actions(summary: Any, *, limit: int = 3) -> list[str]:
    if not isinstance(summary, dict):
        return []
    first_open_items = summary.get("first_open_items")
    if not isinstance(first_open_items, list):
        return []
    actions: list[str] = []
    for item in first_open_items:
        if not isinstance(item, dict):
            continue
        if _user_todo_item_is_explicitly_non_gating(item):
            continue
        text = _protocol_action_label(item.get("text"))
        if not text:
            continue
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def _user_channel_action_required(payload: dict[str, Any]) -> bool:
    return bool(payload.get("requires_user_action")) or bool(
        _user_channel_action_todo_actions(payload.get("user_todo_summary"))
    )


def _protocol_first_candidate_action(payload: dict[str, Any]) -> str | None:
    goal_id = str(payload.get("goal_id") or "")
    agent_lane_next_action = (
        payload.get("agent_lane_next_action")
        if isinstance(payload.get("agent_lane_next_action"), dict)
        else {}
    )
    lane_text = _protocol_action_label(agent_lane_next_action.get("text"))
    if lane_text:
        todo_id = str(agent_lane_next_action.get("todo_id") or "").strip()
        return f"{todo_id}: {lane_text}" if todo_id else lane_text
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if capability_gate.get("action") == "run":
        runnable_candidates = (
            capability_gate.get("runnable_candidates")
            if isinstance(capability_gate.get("runnable_candidates"), list)
            else []
        )
        if runnable_candidates:
            return (
                f"choose one of {len(runnable_candidates)} "
                "capability-runnable todo(s) after steering audit"
            )
    scoped_fallback = (
        payload.get("scoped_user_gate_fallback")
        if isinstance(payload.get("scoped_user_gate_fallback"), dict)
        else {}
    )
    selected = (
        scoped_fallback.get("selected_executable")
        if isinstance(scoped_fallback.get("selected_executable"), dict)
        else {}
    )
    text = _protocol_action_label(selected.get("text"))
    if text:
        return text

    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane.get("monitor_kind") == "todo_monitor_due":
        due_items = (
            work_lane.get("monitor_due_items")
            if isinstance(work_lane.get("monitor_due_items"), list)
            else []
        )
        for item in due_items:
            if not isinstance(item, dict):
                continue
            text = _protocol_action_label(item.get("text"))
            if text:
                todo_id = str(item.get("todo_id") or "").strip()
                return f"{todo_id}: {text}" if todo_id else text

    agent_todos = (
        payload.get("agent_todo_summary")
        if isinstance(payload.get("agent_todo_summary"), dict)
        else {}
    )
    for key in ("first_executable_items", "first_open_items"):
        items = agent_todos.get(key) if isinstance(agent_todos.get(key), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not _todo_item_is_actionable_open(item):
                continue
            if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
                continue
            text = _protocol_action_label(item.get("text"))
            if text:
                return text

    backlog = (
        payload.get("autonomous_backlog_candidates")
        if isinstance(payload.get("autonomous_backlog_candidates"), dict)
        else {}
    )
    items = backlog.get("items") if isinstance(backlog.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if goal_id and str(item.get("goal_id") or "") != goal_id:
            continue
        text = _protocol_action_label(item.get("text"))
        if text:
            return text

    reason_codes = (
        work_lane.get("reason_codes")
        if isinstance(work_lane.get("reason_codes"), list)
        else []
    )
    if "next_action_requires_advancement" in reason_codes:
        text = _protocol_action_text(payload.get("recommended_action"))
        if text:
            return text
    for key in ("action", "obligation"):
        text = _protocol_action_text(work_lane.get(key))
        if text:
            return text
    return _protocol_action_text(payload.get("recommended_action"))


def _protocol_monitor_action(payload: dict[str, Any]) -> str | None:
    goal_id = str(payload.get("goal_id") or "")
    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane.get("obligation") == "quiet_until_material_monitor_transition":
        return "quiet until a material monitor transition, regression, or concrete blocker appears"
    monitors = (
        payload.get("autonomous_monitor_candidates")
        if isinstance(payload.get("autonomous_monitor_candidates"), dict)
        else {}
    )
    items = monitors.get("items") if isinstance(monitors.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if goal_id and str(item.get("goal_id") or "") != goal_id:
            continue
        text = _protocol_action_label(item.get("text"), limit=160)
        if text:
            return text
    return None


def _protocol_action_packet(payload: dict[str, Any]) -> dict[str, Any]:
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    work_lane = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    scheduler_hint = (
        payload.get("scheduler_hint")
        if isinstance(payload.get("scheduler_hint"), dict)
        else {}
    )
    requires_user_action = _user_channel_action_required(payload)
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))
    scoped_user_gate_fallback = isinstance(payload.get("scoped_user_gate_fallback"), dict)
    bounded_delivery_with_user_notice = (
        requires_user_action
        and not scoped_user_gate_fallback
        and must_attempt_work
        and bool(
            execution_obligation.get(
                "delivery_allowed",
                payload.get("normal_delivery_allowed")
                or payload.get("recovery_delivery_allowed")
                or payload.get("self_repair_allowed")
                or payload.get("should_run"),
            )
        )
    )
    quiet_noop_allowed = (
        not requires_user_action
        and not must_attempt_work
        and not scoped_user_gate_fallback
    )

    user_actions = _protocol_todo_actions(payload.get("user_todo_summary"))
    if requires_user_action and not user_actions:
        capability_gate = (
            payload.get("capability_gate")
            if isinstance(payload.get("capability_gate"), dict)
            else {}
        )
        if capability_gate.get("action") == "ask_owner":
            owner_action = _protocol_action_text(capability_gate.get("owner_action"))
            if owner_action:
                user_actions = [owner_action]
        for key in ("gate_prompt", "operator_question", "open_todo_notify_reason"):
            if user_actions:
                break
            text = _protocol_action_text(payload.get(key))
            if text:
                user_actions = [text]
                break

    if requires_user_action and scoped_user_gate_fallback:
        primary_actor = "agent_with_user_gate"
        agent_action_required = True
        agent_action = _protocol_first_candidate_action(payload) or (
            "surface the scoped user gate, then advance one non-gated fallback"
        )
    elif bounded_delivery_with_user_notice:
        primary_actor = "agent_with_user_gate"
        agent_action_required = True
        agent_action = _protocol_first_candidate_action(payload) or "advance one bounded segment"
    elif requires_user_action:
        primary_actor = "user"
        agent_action_required = False
        capability_gate = (
            payload.get("capability_gate")
            if isinstance(payload.get("capability_gate"), dict)
            else {}
        )
        agent_action = (
            capability_gate.get("owner_action")
            if capability_gate.get("action") == "ask_owner"
            and capability_gate.get("owner_action")
            else "wait for user/owner action after surfacing the blocker or gate"
        )
    elif must_attempt_work:
        primary_actor = "agent"
        agent_action_required = True
        agent_action = _protocol_first_candidate_action(payload) or "advance one bounded segment"
    else:
        primary_actor = "agent"
        agent_action_required = False
        agent_action = _protocol_monitor_action(payload) or "quiet no-op; no material transition"

    action_key = (
        "agent_action"
        if agent_action_required
        else "user_action"
        if requires_user_action
        else "agent_action"
    )
    action_value = (
        agent_action
        if agent_action_required
        else user_actions[0]
        if requires_user_action and user_actions
        else agent_action
    )
    summary_parts = [
        f"actor={primary_actor}",
        f"user_action_required={str(requires_user_action).lower()}",
        f"agent_action_required={str(agent_action_required).lower()}",
        f"quiet_noop_allowed={str(quiet_noop_allowed).lower()}",
    ]
    if work_lane.get("lane"):
        summary_parts.append(f"lane={work_lane.get('lane')}")
    if automation_liveness.get("automation_action"):
        summary_parts.append(f"automation={automation_liveness.get('automation_action')}")
    if scheduler_hint.get("action"):
        summary_parts.append(f"scheduler={scheduler_hint.get('action')}")
    if automation_liveness.get("pause_allowed") is False:
        summary_parts.append("pause_allowed=false")
    summary_parts.append("llm=no_api")
    if user_actions and (not requires_user_action or action_key != "user_action"):
        summary_parts.append("user_action_pending=true")
        text = _protocol_action_text(user_actions[0], limit=80)
        if text:
            summary_parts.append(f"user_action={text}")
    text = _protocol_action_text(action_value, limit=80)
    if text:
        summary_parts.append(f"{action_key}={text}")
    return {
        "schema_version": PROTOCOL_ACTION_PACKET_SCHEMA_VERSION,
        "summary": " ".join(summary_parts),
    }


def _interaction_mode(payload: dict[str, Any]) -> str:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    kind = str(execution_obligation.get("kind") or "")
    effective_action = str(payload.get("effective_action") or "")
    state = str(payload.get("state") or "")
    if payload.get("scoped_user_gate_fallback"):
        return "scoped_user_gate_fallback"
    if effective_action == "automation_prompt_upgrade_required":
        return "automation_prompt_upgrade"
    if _user_channel_action_required(payload):
        if (
            bool(execution_obligation.get("must_attempt_work"))
            and bool(
                execution_obligation.get(
                    "delivery_allowed",
                    payload.get("normal_delivery_allowed")
                    or payload.get("recovery_delivery_allowed")
                    or payload.get("self_repair_allowed")
                    or payload.get("should_run"),
                )
            )
        ):
            return "bounded_delivery_with_user_notice"
        if payload.get("notify_user_on_gate") or state == "operator_gate":
            return "user_gate"
        if payload.get("notify_user_on_open_todo"):
            return "user_todo_blocker_push"
        return "user_action_required"
    if kind == "external_evidence_observation_required":
        return "external_evidence_observation"
    if kind == "autonomous_replan_required":
        return "autonomous_replan"
    agent_scope_action = _agent_scope_frontier_action(effective_action)
    if agent_scope_action is not None:
        return agent_scope_action.value
    if effective_action == "monitor_quiet_skip":
        return "monitor_quiet_skip"
    if payload.get("recovery_delivery_allowed") or effective_action == "outcome_floor_recovery":
        return "outcome_floor_recovery"
    if effective_action == "capability_bridge_repair":
        return "capability_bridge_repair"
    if effective_action == "side_agent_workspace_repair":
        return "side_agent_workspace_repair"
    if effective_action == "boundary_projection_repair":
        return "boundary_projection_repair"
    if payload.get("self_repair_allowed"):
        return "control_plane_self_repair"
    if payload.get("normal_delivery_allowed") or payload.get("should_run"):
        return "bounded_delivery"
    if heartbeat_recommendation.get("stop_if_unchanged"):
        return "mapped_noop_if_unchanged"
    if state == "blocked_health":
        return "health_blocked"
    if state == "throttled":
        return "quota_throttled"
    if state in {"waiting", "focus_wait"}:
        return "blocked_wait"
    return "skip"


def _interaction_primary_agent_action(payload: dict[str, Any], *, mode: str) -> str:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    if mode == "external_evidence_observation":
        external_observation = (
            payload.get("external_evidence_observation")
            if isinstance(payload.get("external_evidence_observation"), dict)
            else {}
        )
        observation_target = _protocol_action_text(
            external_observation.get("observation_target"),
            limit=220,
        )
        if observation_target:
            return observation_target
        return (
            "verify an observable external handle or compact writeback channel; "
            "write a compact blocker when it is absent"
        )
    if mode == "autonomous_replan":
        return "run one bounded self-repair or replan segment before another quiet no-op"
    if mode == "monitor_quiet_skip":
        return "record at most one no-spend monitor-poll event, rerun the guard, then stay quiet if unchanged"
    if _agent_scope_frontier_action(mode) is not None:
        agent_scope_frontier = (
            payload.get("agent_scope_frontier")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else {}
        )
        action = _protocol_action_text(agent_scope_frontier.get("recommended_action"), limit=260)
        return action or "stay quiet until this agent has a concrete in-scope runnable todo"
    if mode == "scoped_user_gate_fallback":
        return _protocol_first_candidate_action(payload) or (
            "surface the scoped user gate, then advance one non-gated fallback"
        )
    if mode == "bounded_delivery_with_user_notice":
        return _protocol_first_candidate_action(payload) or "advance one bounded validated segment"
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return "wait for user/owner action after surfacing the blocker or gate"
    if mode == "outcome_floor_recovery":
        return "produce the required outcome-floor evidence artifact or write the concrete blocker"
    if mode == "capability_bridge_repair":
        return "repair or materialize the missing bridge capability, rewrite the todo, or write a compact blocker"
    if mode == "side_agent_workspace_repair":
        return "create or switch to an independent worktree/branch, then rerun quota guard before file edits"
    if mode == "automation_prompt_upgrade":
        return "regenerate the installed automation prompt with a registered agent id and scope, then rerun quota guard"
    if mode == "control_plane_self_repair":
        return "repair the bounded control-plane/status projection fault exposed by quota"
    if mode == "boundary_projection_repair":
        return "repair goal_boundary.write_scope projection before attempting the selected write"
    if mode == "bounded_delivery":
        return _protocol_first_candidate_action(payload) or "advance one bounded validated segment"
    if mode == "mapped_noop_if_unchanged":
        return "confirm no new instruction/evidence/todo/stale source/safe handoff, then quiet no-op"
    if execution_obligation.get("contract_obligation"):
        return str(execution_obligation.get("contract_obligation"))
    return "do not run delivery work for this goal in this turn"


def _interaction_next_cli_actions(payload: dict[str, Any], *, mode: str) -> list[str]:
    goal_id = str(payload.get("goal_id") or "<GOAL_ID>")
    if mode == "automation_prompt_upgrade":
        automation_prompt_upgrade = (
            payload.get("automation_prompt_upgrade")
            if isinstance(payload.get("automation_prompt_upgrade"), dict)
            else {}
        )
        actions = [
            str(automation_prompt_upgrade.get("primary_example_command") or "").strip(),
            str(automation_prompt_upgrade.get("side_agent_example_command") or "").strip(),
        ]
        return [action for action in actions if action] or [
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} --agent-id <registered-agent> --agent-scope '<scope>'",
        ]
    if mode == "monitor_quiet_skip":
        return [
            f"loopx quota monitor-poll --goal-id {goal_id} --source heartbeat --execute",
            f"loopx --format json quota should-run --goal-id {goal_id}",
        ]
    if mode == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        agent_scope_frontier = (
            payload.get("agent_scope_frontier")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else {}
        )
        candidates = (
            agent_scope_frontier.get("deferred_resume_candidates")
            if isinstance(agent_scope_frontier.get("deferred_resume_candidates"), list)
            else []
        )
        first_candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        todo_id = str(first_candidate.get("todo_id") or "<todo_id>")
        return [
            f"loopx todo update --goal-id {goal_id} --todo-id {todo_id} --status open --note '<public-safe successor replan reason>'",
            f"loopx refresh-state --goal-id {goal_id} --classification successor_replan_recorded --delivery-batch-scale single_surface --delivery-outcome outcome_progress",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if _agent_scope_frontier_action(mode) is not None:
        agent_identity = (
            payload.get("agent_identity")
            if isinstance(payload.get("agent_identity"), dict)
            else {}
        )
        agent_arg = (
            f" --agent-id {agent_identity.get('agent_id')}"
            if agent_identity.get("agent_id")
            else ""
        )
        return [
            "no quota spend while this agent has no in-scope runnable candidate",
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}",
        ]
    if mode == "external_evidence_observation":
        return [
            "read approved controller/job/marker/writeback surfaces only",
            f"loopx refresh-state --goal-id {goal_id} --classification <compact_blocker_or_transition>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if mode == "side_agent_workspace_repair":
        agent_identity = (
            payload.get("agent_identity")
            if isinstance(payload.get("agent_identity"), dict)
            else {}
        )
        agent_arg = (
            f" --agent-id {agent_identity.get('agent_id')}"
            if agent_identity.get("agent_id")
            else ""
        )
        return [
            "create or switch to an independent git worktree/branch",
            f"loopx --format json quota should-run --goal-id {goal_id}{agent_arg}",
        ]
    if mode == "autonomous_replan":
        return [
            "run one bounded autonomous replan slice and write back the selected next action/todo changes",
            f"loopx refresh-state --goal-id {goal_id} --classification autonomous_replan_recorded --autonomous-replan-recorded --repair-delta-kind <delta_kind> --delivery-batch-scale <scale> --delivery-outcome <outcome>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if mode in {
        "bounded_delivery",
        "outcome_floor_recovery",
        "capability_bridge_repair",
        "control_plane_self_repair",
        "boundary_projection_repair",
        "scoped_user_gate_fallback",
        "bounded_delivery_with_user_notice",
    }:
        return [
            f"loopx refresh-state --goal-id {goal_id} --classification <validated_progress>",
            f"loopx quota spend-slot --goal-id {goal_id} --slots 1 --source heartbeat --execute",
        ]
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return ["no quota spend for blocker-push/gate-notification"]
    return ["no quota spend without validated transition/blocker writeback"]


def _interaction_spend_policy(
    execution_obligation: dict[str, Any],
    heartbeat_recommendation: dict[str, Any],
    *,
    mode: str,
    spend_after_validation: bool,
) -> str | None:
    if mode in {"user_gate", "user_todo_blocker_push", "user_action_required"}:
        return "no spend for gate or blocker push"
    if mode == "monitor_quiet_skip":
        return "no spend for unchanged monitor poll"
    if mode == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        return "spend once after validated successor replan/todo writeback"
    if _agent_scope_frontier_action(mode) is not None:
        return "no spend while the current agent has no in-scope runnable candidate"
    if mode == "side_agent_workspace_repair":
        return "no spend for moving side-agent work into an independent worktree"
    if mode == "automation_prompt_upgrade":
        return "no spend until the automation reruns quota guard with --agent-id"
    if spend_after_validation:
        return "spend once after validated writeback"
    raw_policy = execution_obligation.get("spend_policy") or heartbeat_recommendation.get(
        "spend_policy"
    )
    if isinstance(raw_policy, str) and len(raw_policy) <= 80:
        return raw_policy
    return "no spend without validated transition"


def _interaction_contract(payload: dict[str, Any]) -> dict[str, Any]:
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    mode = _interaction_mode(payload)
    user_required = _user_channel_action_required(payload)
    scoped_user_gate_fallback = mode == "scoped_user_gate_fallback"
    bounded_delivery_with_user_notice = mode == "bounded_delivery_with_user_notice"
    must_attempt = bool(execution_obligation.get("must_attempt_work")) if (
        not user_required or scoped_user_gate_fallback or bounded_delivery_with_user_notice
    ) else False
    delivery_allowed = (
        not user_required
        or scoped_user_gate_fallback
        or bounded_delivery_with_user_notice
    ) and bool(
        execution_obligation.get(
            "delivery_allowed",
            payload.get("normal_delivery_allowed")
            or payload.get("recovery_delivery_allowed")
            or payload.get("self_repair_allowed")
            or payload.get("should_run"),
        )
    )
    quiet_noop_allowed = (
        not user_required
        and not must_attempt
        and (
            _agent_scope_frontier_action(mode) is not None
            or mode
            in {
                "monitor_quiet_skip",
                "mapped_noop_if_unchanged",
                "quota_throttled",
                "blocked_wait",
                "skip",
            }
        )
    )
    spend_allowed_now = False
    spend_after_validation = mode in {
        "bounded_delivery",
        "outcome_floor_recovery",
        "capability_bridge_repair",
        "autonomous_replan",
        "control_plane_self_repair",
        "boundary_projection_repair",
        "external_evidence_observation",
        AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
        "scoped_user_gate_fallback",
        "bounded_delivery_with_user_notice",
    }
    user_channel: dict[str, Any] = {
        "action_required": user_required,
        "notify": "NOTIFY" if user_required else heartbeat_recommendation.get("notify", "DONT_NOTIFY"),
    }
    if user_required:
        user_channel["max_items"] = 3
    user_reason = (
        payload.get("open_todo_notify_reason")
        or payload.get("gate_prompt")
        or payload.get("operator_question")
        or (
            payload.get("blocked_priority_fallback", {}).get("reason")
            if isinstance(payload.get("blocked_priority_fallback"), dict)
            else None
        )
        or (
            payload.get("scoped_user_gate_fallback", {}).get("reason")
            if isinstance(payload.get("scoped_user_gate_fallback"), dict)
            else None
        )
        or (
            "open user todo requires user-visible follow-up while independent "
            "agent work may continue"
            if _user_channel_action_todo_actions(payload.get("user_todo_summary"))
            else None
        )
        or (
            payload.get("agent_scope_frontier", {}).get("reason")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else None
        )
        or (
            payload.get("capability_gate", {}).get("reason")
            if isinstance(payload.get("capability_gate"), dict)
            else None
        )
    )
    if user_reason:
        user_channel["reason"] = user_reason

    contract = {
        "schema_version": INTERACTION_CONTRACT_SCHEMA_VERSION,
        "mode": mode,
        "user_channel": user_channel,
        "agent_channel": {
            "must_attempt": must_attempt,
            "delivery_allowed": delivery_allowed,
            "quiet_noop_allowed": quiet_noop_allowed,
            "primary_action": _interaction_primary_agent_action(payload, mode=mode),
        },
        "cli_channel": {
            "next_cli_actions": _interaction_next_cli_actions(payload, mode=mode),
            "spend_allowed_now": spend_allowed_now,
            "spend_after_validation": spend_after_validation,
            "spend_policy": _interaction_spend_policy(
                execution_obligation,
                heartbeat_recommendation,
                mode=mode,
                spend_after_validation=spend_after_validation,
            ),
        },
    }
    if mode in {
        "user_gate",
        "user_todo_blocker_push",
        "user_action_required",
        "outcome_floor_recovery",
        "external_evidence_observation",
        "scoped_user_gate_fallback",
    } or payload.get("blocked_priority_fallback"):
        contract["fallback_policy"] = {"do_not_cancel_on_block": True}
    return contract


def _automation_liveness(payload: dict[str, Any]) -> dict[str, Any]:
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    effective_action = str(payload.get("effective_action") or "")
    recommended_mode = str(heartbeat_recommendation.get("recommended_mode") or "")
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))

    base = {
        "schema_version": AUTOMATION_LIVENESS_SCHEMA_VERSION,
        "keep_active": True,
        "pause_allowed": False,
        "pause_policy": (
            "pause/delete only after a bounded self-repair or replan path is itself "
            "stuck for two more eligible turns"
        ),
    }
    if effective_action == "monitor_quiet_skip" or recommended_mode == "monitor_quiet_until_material_transition":
        return {
            **base,
            "automation_action": "keep_active_quiet",
            "reason": (
                "monitor-only quiet skip is a liveness-preserving no-op, not a "
                "self-stop signal"
            ),
            "next_trigger": (
                "material monitor transition, regression, concrete blocker, or "
                "autonomous_replan_required"
            ),
            "spend_policy": "no quota spend for unchanged monitor-only polls",
        }
    if effective_action == "automation_prompt_upgrade_required":
        return {
            **base,
            "automation_action": "repair_automation_prompt_identity",
            "reason": (
                "the installed automation is stale or unscoped; keep the automation "
                "active but block delivery until it reruns with a registered agent id"
            ),
            "spend_policy": "no quota spend for identity prompt upgrade preflight",
        }
    if effective_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        return {
            **base,
            "automation_action": "execute_bounded_work",
            "reason": (
                "a ready deferred successor is visible to this agent; run a bounded "
                "successor replan or write a no-follow-up rationale before another quiet no-op"
            ),
            "next_trigger": "deferred successor replan writeback or fresh quota guard",
            "spend_policy": "spend once only after validated successor replan/todo writeback",
        }
    if _agent_scope_frontier_action(effective_action) is not None:
        return {
            **base,
            "automation_action": "keep_active_quiet",
            "reason": (
                "the current agent has no in-scope runnable candidate; this is a "
                "liveness-preserving no-op until work is reassigned or projected"
            ),
            "next_trigger": (
                "handoff owner progress, reassignment, or a current-agent/unclaimed "
                "advancement todo"
            ),
            "spend_policy": "no quota spend for agent-scoped no-candidate checks",
        }
    if must_attempt_work or recommended_mode == "autonomous_replan_required":
        return {
            **base,
            "automation_action": "execute_bounded_work",
            "reason": (
                "execution_obligation requires a bounded progress or replan segment "
                "before another quiet no-op"
            ),
            "spend_policy": "spend once only after validation and durable writeback",
        }
    if recommended_mode == "mapped_noop_if_unchanged":
        return {
            **base,
            "automation_action": "keep_active_noop_if_unchanged",
            "reason": (
                "unchanged mapped state should stay quiet and active until new evidence "
                "or a concrete safe handoff appears"
            ),
            "spend_policy": "no quota spend for unchanged mapped no-op checks",
        }
    return {
        **base,
        "automation_action": "keep_active",
        "reason": "heartbeat liveness should be preserved unless the repair path is stuck",
        "spend_policy": (
            "follow heartbeat_recommendation; spend only after validated delivery or "
            "safe-bypass writeback"
        ),
    }


def _scheduler_hint(payload: dict[str, Any], *, include_detail: bool = False) -> dict[str, Any]:
    return build_scheduler_hint(
        payload,
        user_action_required=_user_channel_action_required(payload),
        agent_scope_frontier_actions=[action.value for action in AgentScopeFrontierAction],
        include_detail=include_detail,
    )


def _goal_boundary(goal: dict[str, Any], item: dict[str, Any] | None = None) -> dict[str, Any] | None:
    boundary: dict[str, Any] = {}
    adapter_kind = goal.get("adapter_kind")
    adapter_status = goal.get("adapter_status")
    if adapter_kind or adapter_status:
        boundary["adapter"] = {
            "kind": adapter_kind,
            "status": adapter_status,
        }
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    write_scope = coordination.get("write_scope") if isinstance(coordination.get("write_scope"), list) else []
    requires_approval = (
        coordination.get("requires_parent_approval")
        if isinstance(coordination.get("requires_parent_approval"), list)
        else []
    )
    normalized_write_scope: list[str] = []
    for value in write_scope:
        scope = str(value).strip()
        if scope and scope not in normalized_write_scope:
            normalized_write_scope.append(scope)
    boundary_authority = checkpointed_boundary_authority_summary(coordination)
    if boundary_authority:
        for scope in normalize_required_write_scopes(boundary_authority.get("active_write_scope")):
            if scope not in normalized_write_scope:
                normalized_write_scope.append(scope)
        boundary["checkpointed_boundary_authority"] = boundary_authority
    if normalized_write_scope:
        boundary["write_scope"] = normalized_write_scope
    if requires_approval:
        boundary["requires_parent_approval"] = [
            str(value) for value in requires_approval if str(value).strip()
        ]
    guards = goal.get("guards") if isinstance(goal.get("guards"), list) else []
    if guards:
        boundary["guards"] = [str(value) for value in guards if str(value).strip()]
    if goal.get("next_probe"):
        boundary["next_probe"] = str(goal.get("next_probe"))
    spawn_policy = goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else None
    if spawn_policy is not None:
        boundary["orchestration"] = compact_orchestration_policy(spawn_policy)
    project_asset_source = item if item is not None else goal
    for policy_source in (goal, project_asset_source):
        if not isinstance(policy_source, dict):
            continue
        policy = compact_run_permission_policy_for_quota(
            policy_source.get("run_permission_policy")
            or policy_source.get("run_permission_policy_v0")
        )
        if policy:
            boundary["run_permission_policy"] = policy
            break
    if isinstance(project_asset_source, dict) and project_asset_source.get("project_asset"):
        project_asset = project_asset_source.get("project_asset")
        if isinstance(project_asset, dict):
            policy = compact_run_permission_policy_for_quota(
                project_asset.get("run_permission_policy")
                or project_asset.get("run_permission_policy_v0")
            )
            if policy:
                boundary["run_permission_policy"] = policy
            if project_asset.get("stop_condition"):
                boundary["stop_condition"] = project_asset.get("stop_condition")
            if isinstance(project_asset.get("execution_profile"), dict):
                boundary["execution_profile"] = _quota_execution_profile_boundary_summary(
                    project_asset["execution_profile"]
                )
            if isinstance(project_asset.get("orchestration"), dict):
                boundary["orchestration"] = compact_orchestration_policy(project_asset["orchestration"])
    if boundary:
        boundary["rule"] = "stay_in_scope_or_stop"
        return boundary
    return None


def _quota_registered_agents(goal: dict[str, Any]) -> list[str]:
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    raw_values = coordination.get("registered_agents")
    if raw_values is None:
        raw_values = goal.get("registered_agents")
    if isinstance(raw_values, str):
        raw_values = [raw_values]
    if not isinstance(raw_values, list):
        return []
    agents: list[str] = []
    for value in raw_values:
        candidate = value
        if isinstance(candidate, dict):
            candidate = candidate.get("id") or candidate.get("agent_id") or candidate.get("name")
        normalized = normalize_todo_claimed_by(candidate)
        if normalized and normalized not in agents:
            agents.append(normalized)
    return agents


def _quota_primary_agent(goal: dict[str, Any]) -> str | None:
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    for candidate in (coordination.get("primary_agent"), goal.get("primary_agent")):
        normalized = normalize_todo_claimed_by(candidate)
        if normalized:
            return normalized
    return None


def _quota_agent_identity(goal: dict[str, Any], *, agent_id: str | None) -> dict[str, Any] | None:
    normalized_agent_id = normalize_todo_claimed_by(agent_id) if agent_id else None
    if agent_id and not normalized_agent_id:
        raise ValueError("agent_id must be a public-safe registered agent id")
    registered_agents = _quota_registered_agents(goal)
    if not normalized_agent_id:
        return None
    if not registered_agents:
        raise ValueError(
            "quota should-run --agent-id requires coordination.registered_agents; "
            "register this agent identity first"
        )
    if normalized_agent_id not in registered_agents:
        raise ValueError(
            f"agent_id={normalized_agent_id!r} is not registered; "
            f"registered_agents={', '.join(registered_agents)}"
        )
    primary_agent = _quota_primary_agent(goal)
    return {
        "agent_id": normalized_agent_id,
        "registered": True,
        "role": "primary-agent" if primary_agent and normalized_agent_id == primary_agent else "side-agent",
        "primary_agent": primary_agent,
        "registered_agents": registered_agents,
    }


def _is_same_or_child_path(path: Path, root: Path) -> bool:
    try:
        current = path.expanduser().resolve()
        target = root.expanduser().resolve()
    except OSError:
        return False
    return current == target or target in current.parents


def _git_command_output(path: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1.5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def _git_worktree_root(path: Path) -> Path | None:
    output = _git_command_output(path, "rev-parse", "--show-toplevel")
    if not output:
        return None
    try:
        return Path(output).expanduser().resolve()
    except OSError:
        return None


def _git_common_dir(path: Path) -> Path | None:
    root = _git_worktree_root(path)
    if root is None:
        return None
    output = _git_command_output(root, "rev-parse", "--git-common-dir")
    if not output:
        return None
    common = Path(output).expanduser()
    if not common.is_absolute():
        common = root / common
    try:
        return common.resolve()
    except OSError:
        return None


def _side_agent_workspace_guard(
    goal: dict[str, Any],
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict) or agent_identity.get("role") != "side-agent":
        return None
    repo_value = goal.get("repo") or goal.get("project") or goal.get("root")
    if not repo_value:
        return None
    repo_path = Path(str(repo_value)).expanduser()
    if not repo_path.is_absolute():
        return None
    current_path = Path.cwd()
    current_workspace = ""
    if _is_same_or_child_path(current_path, repo_path):
        current_workspace = "primary_checkout"
    else:
        primary_root = _git_worktree_root(repo_path) or repo_path
        current_root = _git_worktree_root(current_path)
        primary_common = _git_common_dir(primary_root)
        current_common = _git_common_dir(current_path) if current_root else None
        if current_root is None:
            current_workspace = "not_git_worktree"
        elif primary_common is None or current_common is None or current_common != primary_common:
            current_workspace = "foreign_git_worktree"
        elif current_root == primary_root:
            current_workspace = "primary_checkout"
    if not current_workspace:
        return None
    return {
        "schema_version": SIDE_AGENT_WORKSPACE_GUARD_SCHEMA_VERSION,
        "source": "quota.should-run",
        "action": "move_to_independent_worktree",
        "current_workspace": current_workspace,
        "required_workspace": "independent_git_worktree",
        "blocks_delivery": True,
        "agent_id": agent_identity.get("agent_id"),
        "primary_agent": agent_identity.get("primary_agent"),
        "reason": (
            "side-agent quota guard is not running from an independent worktree for "
            "the registered project; normal delivery must move before repository edits"
        ),
        "required_action": (
            "create or switch to an independent git worktree/branch for this side-agent "
            "lane, then rerun quota should-run with the same --agent-id before editing files"
        ),
    }


def _automation_prompt_upgrade(
    goal: dict[str, Any],
    *,
    goal_id: str,
    agent_identity: dict[str, Any] | None,
) -> dict[str, Any] | None:
    registered_agents = _quota_registered_agents(goal)
    if not registered_agents or agent_identity:
        return None
    primary_agent = _quota_primary_agent(goal)
    primary_hint = primary_agent if primary_agent in registered_agents else registered_agents[0]
    side_hint = next((agent for agent in registered_agents if agent != primary_hint), primary_hint)
    return {
        "contract": "identity_aware_heartbeat_prompt_v1",
        "required": True,
        "blocks_should_run": True,
        "reason": (
            "coordination.registered_agents is configured, but quota should-run "
            "was called without --agent-id; the installed automation prompt is "
            "likely stale or unscoped"
        ),
        "registered_agents": registered_agents,
        "primary_agent": primary_agent,
        "recommended_action": (
            "Regenerate the installed heartbeat automation prompt with a "
            "registered --agent-id and at least one --agent-scope, then rerun "
            "quota should-run with the same --agent-id."
        ),
        "primary_example_command": (
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} "
            f"--agent-id {primary_hint} --agent-scope "
            "'primary review, verification, merge, and coordination'"
        ),
        "side_agent_example_command": (
            f"loopx heartbeat-prompt --thin --goal-id {goal_id} "
            f"--agent-id {side_hint} --agent-scope "
            "'bounded side-agent work in an independent worktree'"
        ),
    }


def _build_gate_prompt(
    item: dict[str, Any],
    *,
    user_todo_summary: dict[str, Any] | None = None,
) -> str | None:
    question = str(item.get("operator_question") or "").strip()
    recommended_action = str(item.get("recommended_action") or "").strip()
    next_handoff_condition = str(item.get("next_handoff_condition") or "").strip()
    missing_gates = [
        str(gate).strip()
        for gate in (item.get("missing_gates") if isinstance(item.get("missing_gates"), list) else [])
        if str(gate).strip()
    ]
    if user_todo_summary is None:
        user_todo_summary = _summarize_user_todos(item.get("user_todos"))
    first_open = (
        user_todo_summary.get("first_open_items")
        if isinstance(user_todo_summary, dict) and isinstance(user_todo_summary.get("first_open_items"), list)
        else []
    )
    other_agent_scoped_items = (
        user_todo_summary.get("other_agent_scoped_items")
        if isinstance(user_todo_summary, dict)
        and isinstance(user_todo_summary.get("other_agent_scoped_items"), list)
        else []
    )

    if not any(
        [
            question,
            recommended_action,
            next_handoff_condition,
            missing_gates,
            first_open,
            other_agent_scoped_items,
        ]
    ):
        return None

    lines = ["请用户/控制器确认当前 gate："]
    if question:
        lines.append(f"- 问题：{question}")
    if recommended_action:
        lines.append(f"- 当前建议：{recommended_action}")
    if next_handoff_condition:
        lines.append(f"- 放行条件：{next_handoff_condition}")
    if missing_gates:
        lines.append(f"- 缺失 gate：{', '.join(missing_gates)}")
    if isinstance(user_todo_summary, dict) and first_open:
        open_count = user_todo_summary.get("open_count")
        lines.append(f"- 用户待办：{open_count} 项未完成，优先确认：")
        for todo in first_open:
            index = todo.get("index")
            prefix = f"  {index}. " if index is not None else "  - "
            lines.append(f"{prefix}{todo.get('text')}")
    elif isinstance(user_todo_summary, dict) and other_agent_scoped_items:
        scoped_count = user_todo_summary.get("other_agent_scoped_open_count")
        all_open_count = user_todo_summary.get("all_open_count")
        count = scoped_count if scoped_count is not None else len(other_agent_scoped_items)
        suffix = f"（全局共 {all_open_count} 项）" if all_open_count is not None else ""
        lines.append(f"- 当前 agent 无阻塞用户待办；其他 agent/global 用户待办：{count} 项{suffix}，优先确认：")
        for todo in other_agent_scoped_items[:3]:
            index = todo.get("index")
            prefix = f"  {index}. " if index is not None else "  - "
            lines.append(f"{prefix}{todo.get('text')}")
    lines.append("- 建议回复格式：同意 / 不同意 / 已完成 / 仍待确认 + 一句话原因。")
    return "\n".join(lines)


def _should_notify_user_on_open_todo(
    *,
    state: str,
    waiting_on: str,
    user_todo_summary: dict[str, Any] | None,
) -> bool:
    if state == "operator_gate":
        return False
    if not isinstance(user_todo_summary, dict):
        return False
    try:
        open_count = int(user_todo_summary.get("open_count") or 0)
    except (TypeError, ValueError):
        open_count = 0
    if open_count <= 0:
        return False
    if state in {"focus_wait", "waiting"}:
        return True
    return waiting_on in {"user_or_controller", "controller", "external_evidence"}


def _open_todo_notify_reason(*, state: str, waiting_on: str) -> str:
    if state == "focus_wait":
        return "open user todo can unblock focus_wait after owner evidence, external eval, or a clean baseline changes"
    if waiting_on == "external_evidence":
        return "open user todo can provide or defer the external-evidence checkpoint"
    if waiting_on in {"user_or_controller", "controller"}:
        return "open user todo can resolve the user/controller blocker"
    return "open user todo can resolve the current waiting lane"


def _supports_read_only_project_map(adapter_kind: Any) -> bool:
    kind = str(adapter_kind or "").strip()
    return kind == "read_only_project_map_v0" or kind.endswith(READ_ONLY_MAP_ADAPTER_SUFFIX)


def _open_todo_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    try:
        return max(0, int(summary.get("open_count") or 0))
    except (TypeError, ValueError):
        return 0


def _open_user_gate_todo_items(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    candidates: list[dict[str, Any]] = []
    for key in ("gate_open_items", "first_open_items"):
        values = summary.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict) or item.get("done") is True:
                continue
            if not _is_user_gate_todo_item(item):
                continue
            item_key = (item.get("todo_id"), item.get("index"), item.get("text"))
            if any(
                (existing.get("todo_id"), existing.get("index"), existing.get("text"))
                == item_key
                for existing in candidates
            ):
                continue
            candidates.append(item)
    return candidates


def _has_open_user_gate_todo(summary: dict[str, Any] | None) -> bool:
    return bool(_open_user_gate_todo_items(summary))


def _user_gate_todo_notify_reason(summary: dict[str, Any] | None) -> str:
    items = _open_user_gate_todo_items(summary)
    if not items:
        return "open user todo can resolve the current gate"
    first = items[0]
    action_kind = str(first.get("action_kind") or "").strip()
    if action_kind:
        return f"open user_gate todo requires owner decision before {action_kind}"
    return "open user_gate todo requires owner decision before agent execution"


def _todo_task_class(item: dict[str, Any]) -> str:
    text = " ".join(
        str(value or "")
        for value in (item.get("title"), item.get("text"))
        if str(value or "").strip()
    )
    return normalize_todo_task_class(
        item.get("task_class"),
        text=text,
        action_kind=item.get("action_kind"),
    )


def _todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    if item.get("done") is True:
        return False
    status = normalize_todo_status(item.get("status")) or TODO_STATUS_OPEN
    return status == TODO_STATUS_OPEN


def _todo_item_next_due_at(item: dict[str, Any]) -> datetime | None:
    return _parse_timestamp(item.get("next_due_at"))


def _todo_item_expires_at(item: dict[str, Any]) -> datetime | None:
    return _parse_timestamp(item.get("expires_at"))


def _todo_item_is_expired_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    expires_at = _todo_item_expires_at(item)
    if expires_at is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return expires_at <= current_time


def _todo_item_is_due_monitor(item: dict[str, Any], *, now: datetime | None = None) -> bool:
    if not _todo_item_is_actionable_open(item):
        return False
    if _todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
        return False
    if _todo_item_is_expired_monitor(item, now=now):
        return False
    next_due_at = _todo_item_next_due_at(item)
    if next_due_at is None:
        return False
    current_time = now or datetime.now(timezone.utc)
    return next_due_at <= current_time


def _todo_summary_claim_scope_agent_id(summary: dict[str, Any]) -> str | None:
    claim_scope = summary.get("claim_scope") if isinstance(summary.get("claim_scope"), dict) else {}
    return normalize_todo_claimed_by(claim_scope.get("agent_id"))


def _todo_summary_monitor_due_items(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(summary, dict):
        return []
    projected_items = summary.get("monitor_due_items")
    if isinstance(projected_items, list):
        due_items = [
            item
            for item in projected_items
            if isinstance(item, dict)
            if _todo_item_is_actionable_open(item)
            if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
        ]
    else:
        raw_items = summary.get("monitor_open_items")
        due_items = [
            item
            for item in (raw_items if isinstance(raw_items, list) else [])
            if isinstance(item, dict)
            if _todo_item_is_due_monitor(item)
        ]
    agent_id = _todo_summary_claim_scope_agent_id(summary)
    if agent_id:
        due_items = [
            item
            for item in due_items
            if _todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
        ]
    return sorted(due_items, key=_todo_projection_sort_key)


def _todo_summary_monitor_due_count(
    summary: dict[str, Any] | None,
    *,
    due_items: list[dict[str, Any]] | None = None,
) -> int:
    if not isinstance(summary, dict):
        return 0
    agent_id = _todo_summary_claim_scope_agent_id(summary)
    if agent_id:
        raw_items = summary.get("monitor_open_items")
        if isinstance(raw_items, list):
            return len(
                [
                    item
                    for item in raw_items
                    if isinstance(item, dict)
                    if _todo_item_is_due_monitor(item)
                    if _todo_item_claimed_by_agent_or_unclaimed(item, agent_id=agent_id)
                ]
            )
        return len(due_items if due_items is not None else _todo_summary_monitor_due_items(summary))
    projected_count = summary.get("monitor_due_count")
    if isinstance(projected_count, int):
        return max(0, projected_count)
    return len(due_items if due_items is not None else _todo_summary_monitor_due_items(summary))


def _first_executable_todo_item(agent_todo_summary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(agent_todo_summary, dict):
        return None
    items = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        return item
    return None


def _open_todo_task_counts(summary: dict[str, Any] | None) -> dict[str, int]:
    open_count = _open_todo_count(summary)
    classified_items: list[dict[str, Any]] = []
    seen: set[tuple[Any, str]] = set()
    executable_backlog_items: list[dict[str, Any]] | None = None
    monitor_open_items: list[dict[str, Any]] | None = None
    if isinstance(summary, dict):
        raw_executable_backlog = summary.get("executable_backlog_items")
        if isinstance(raw_executable_backlog, list):
            executable_backlog_items = [
                item
                for item in raw_executable_backlog
                if isinstance(item, dict)
                if _todo_item_is_actionable_open(item)
                if _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            ]
        raw_monitor_open = summary.get("monitor_open_items")
        if isinstance(raw_monitor_open, list):
            monitor_open_items = [
                item
                for item in raw_monitor_open
                if isinstance(item, dict)
                if _todo_item_is_actionable_open(item)
                if _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
            ]
        for key in (
            "first_executable_items",
            "first_open_items",
            "monitor_open_items",
        ):
            source_items = summary.get(key)
            if not isinstance(source_items, list):
                continue
            for item in source_items:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                identity = (item.get("index"), text)
                if identity in seen:
                    continue
                seen.add(identity)
                classified_items.append(item)
    if executable_backlog_items is not None:
        advancement_count = len(executable_backlog_items)
    else:
        visible_open = min(open_count, len(classified_items))
        advancement_visible_count = sum(
            1
            for item in classified_items[:visible_open]
            if _todo_item_is_actionable_open(item)
            and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
        )
        hidden_count = max(0, open_count - visible_open)
        advancement_count = advancement_visible_count + hidden_count
    if monitor_open_items is not None:
        monitor_visible_count = len(monitor_open_items)
    else:
        visible_open = min(open_count, len(classified_items))
        monitor_visible_count = sum(
            1
            for item in classified_items[:visible_open]
            if _todo_item_is_actionable_open(item)
            and _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
        )
    monitor_due_count = _todo_summary_monitor_due_count(summary)
    hidden_count = max(0, open_count - len(classified_items))
    return {
        "open": open_count,
        "advancement": advancement_count,
        "monitor": monitor_visible_count,
        "monitor_due": monitor_due_count,
        "hidden": hidden_count,
    }


def _outcome_floor_blocker_already_projected(
    agent_todo_summary: dict[str, Any] | None,
) -> bool:
    if not isinstance(agent_todo_summary, dict):
        return False
    if _open_todo_count(agent_todo_summary) <= 0:
        return False

    executable_items = (
        agent_todo_summary.get("first_executable_items")
        if isinstance(agent_todo_summary.get("first_executable_items"), list)
        else []
    )
    if any(
        isinstance(item, dict) and _todo_item_is_actionable_open(item)
        for item in executable_items
    ):
        return False

    first_open = (
        agent_todo_summary.get("first_open_items")
        if isinstance(agent_todo_summary.get("first_open_items"), list)
        else []
    )
    visible_open = [
        item
        for item in first_open
        if isinstance(item, dict) and _todo_item_is_actionable_open(item)
    ]
    if not visible_open:
        return False
    visible_classes = [_todo_task_class(item) for item in visible_open]
    return (
        TODO_TASK_CLASS_BLOCKER in visible_classes
        and all(task_class != TODO_TASK_CLASS_ADVANCEMENT for task_class in visible_classes)
    )


def _next_action_requires_advancement(item: dict[str, Any]) -> bool:
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    values = (
        project_asset.get("next_action"),
        project_asset.get("recommended_action"),
        item.get("next_action"),
        item.get("recommended_action"),
    )
    text = " ".join(str(value or "") for value in values if str(value or "").strip())
    return next_action_requires_advancement_text(text)


def _has_lifecycle_marker(*values: Any, marker: str) -> bool:
    target = marker.strip().lower()
    for value in values:
        for text in _text_values(value):
            if text.strip().lower() == target:
                return True
    return False


def _compact_health_items(items: list[Any], *, limit: int = 3) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        payload = {field: item.get(field) for field in STALL_HEALTH_ITEM_COMPACT_FIELDS if item.get(field)}
        if payload:
            compact.append(payload)
        if len(compact) >= limit:
            break
    return compact


def _stall_self_repair_hint(
    item: dict[str, Any],
    *,
    state: str,
    plan_ok: bool,
    health_items: list[Any],
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    control_plane = compact_control_plane_policy(item.get("control_plane"))
    if not control_plane:
        return None

    if not plan_ok and control_plane_self_repair_allows(control_plane, "health_blocker_repair"):
        blockers = _compact_health_items(health_items)
        if blockers:
            return {
                "source": "quota.should-run",
                "trigger": "health_blocker",
                "recommended_mode": "repair_control_plane_health",
                "effective_action": "control_plane_health_repair",
                "allowed": True,
                "notify": "DONT_NOTIFY",
                "reason": "status or contract health blocks normal delivery; spend one bounded turn on control-plane repair instead of quiet spinning",
                "repair_focus": "inspect the compact health blocker, repair registry/status/contract projection or public-boundary scan scope, validate, write a durable event, then spend once",
                "spend_policy": "append exactly one heartbeat spend only after the health blocker is repaired, validated, and written back",
                "control_plane": control_plane,
                "blocking_health_items": blockers,
            }

    waiting_on = str(item.get("waiting_on") or "")
    has_user_todos = _open_todo_count(user_todo_summary) > 0
    has_agent_todos = _open_todo_count(agent_todo_summary) > 0
    has_next_action = bool(str(item.get("recommended_action") or "").strip())
    has_project_asset = isinstance(item.get("project_asset"), dict)
    unknown_waiting_owner = waiting_on in {"", "none", "unknown", "null"}
    if (
        control_plane_self_repair_allows(control_plane, "waiting_projection_repair")
        and state == "waiting"
        and unknown_waiting_owner
        and not has_user_todos
        and (has_next_action or has_agent_todos or has_project_asset)
    ):
        return {
            "source": "quota.should-run",
            "trigger": "waiting_without_owner_projection",
            "recommended_mode": "repair_waiting_projection",
            "effective_action": "control_plane_projection_repair",
            "allowed": True,
            "notify": "DONT_NOTIFY",
            "reason": "goal is waiting without a concrete owner/evidence gate while current action or agent backlog exists",
            "repair_focus": "rebase from registry, active state, status, and run history; either project waiting_on=codex for safe agent work or write the concrete user/controller/evidence blocker",
            "spend_policy": "append exactly one heartbeat spend only after the projection or blocker writeback is validated",
            "control_plane": control_plane,
        }

    return None


def _state_projection_gap(item: dict[str, Any], project_asset: dict[str, Any]) -> dict[str, Any] | None:
    gap = (
        item.get("state_projection_gap")
        if isinstance(item.get("state_projection_gap"), dict)
        else project_asset.get("state_projection_gap")
        if isinstance(project_asset.get("state_projection_gap"), dict)
        else None
    )
    if not isinstance(gap, dict):
        return None
    if gap.get("requires_todo_expansion") is not True:
        return None
    return _revalidate_state_projection_gap(gap)


def _revalidate_state_projection_gap(gap: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(gap, dict):
        return None
    evidence_items = gap.get("first_evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        return gap

    retained: list[dict[str, Any]] = []
    removed_user_wait = False
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        is_user_wait_evidence = (
            item.get("target_role") == "user"
            and item.get("kind") == "next_action_waits_without_user_todo"
        )
        if is_user_wait_evidence and not is_user_wait_text(item.get("text")):
            removed_user_wait = True
            continue
        retained.append(item)

    if not removed_user_wait:
        return gap
    if not retained:
        target_roles = {
            str(role).strip()
            for role in gap.get("target_roles", [])
            if str(role or "").strip()
        }
        return None if target_roles <= {"user"} else gap

    revised = dict(gap)
    revised["first_evidence"] = retained
    revised["evidence_count"] = len(retained)
    revised["target_roles"] = sorted(
        {
            str(item.get("target_role") or "").strip()
            for item in retained
            if str(item.get("target_role") or "").strip()
        }
    )
    return revised


def _state_projection_gap_repair_hint(
    gap: dict[str, Any] | None,
    *,
    candidate_should_run: bool,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not gap:
        return None
    if _open_todo_count(user_todo_summary) > 0 or _open_todo_count(agent_todo_summary) > 0:
        return None
    must_attempt = bool(
        work_lane_contract
        and work_lane_contract.get("must_attempt_work") is True
    )
    if not candidate_should_run and not must_attempt:
        return None
    return {
        "source": "quota.should-run",
        "trigger": "state_projection_gap",
        "recommended_mode": "repair_state_projection_gap",
        "effective_action": "state_projection_gap_repair",
        "allowed": True,
        "notify": "DONT_NOTIFY",
        "reason": (
            "active state has actionable Next Action / gate prose but no open "
            "User Todo or Agent Todo projection"
        ),
        "repair_focus": (
            "run one replan/todo-expansion/blocker-writeback slice: convert executable "
            "Next Action into concrete Agent Todo, or convert owner/user gates into "
            "User Todo, then refresh state before normal delivery"
        ),
        "spend_policy": (
            "append exactly one heartbeat spend only after the projection repair is "
            "validated and written back; do not spend for merely reporting the gap"
        ),
        "state_projection_gap": gap,
    }


def _write_scope_allowed(required_scope: str, allowed_scopes: list[str]) -> bool:
    required = str(required_scope or "").strip()
    if not required:
        return True
    for allowed in allowed_scopes:
        pattern = str(allowed or "").strip()
        if not pattern:
            continue
        if required == pattern:
            return True
        if fnmatch.fnmatchcase(required, pattern):
            return True
    return False


def _boundary_projection_repair_hint(
    goal_boundary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    *,
    candidate_should_run: bool,
) -> dict[str, Any] | None:
    if not candidate_should_run or not isinstance(agent_todo_summary, dict):
        return None
    candidate_items: list[dict[str, Any]] = []
    for key in ("first_executable_items", "first_open_items"):
        value = agent_todo_summary.get(key)
        if isinstance(value, list):
            candidate_items.extend(item for item in value if isinstance(item, dict))
    selected: dict[str, Any] | None = None
    for item in candidate_items:
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        required = normalize_required_write_scopes(item.get("required_write_scopes"))
        if required:
            selected = item
            break
    if not selected:
        return None

    required_scopes = normalize_required_write_scopes(selected.get("required_write_scopes"))
    boundary = goal_boundary if isinstance(goal_boundary, dict) else {}
    allowed_scopes = normalize_required_write_scopes(boundary.get("write_scope"))
    missing_scopes = [
        scope
        for scope in required_scopes
        if not _write_scope_allowed(scope, allowed_scopes)
    ]
    if not missing_scopes:
        return None
    selected_text = _protocol_action_text(selected.get("text"), limit=220)
    boundary_authority = (
        boundary.get("checkpointed_boundary_authority")
        if isinstance(boundary.get("checkpointed_boundary_authority"), dict)
        else None
    )
    repair: dict[str, Any] = {
        "source": "quota.should-run",
        "trigger": "required_write_scope_missing_from_goal_boundary",
        "recommended_mode": "repair_boundary_projection",
        "effective_action": "boundary_projection_repair",
        "blocked_action_scope": "boundary_projection",
        "allowed": True,
        "notify": "DONT_NOTIFY",
        "reason": (
            "selected executable todo requires write scope not present in "
            "goal_boundary.write_scope"
        ),
        "repair_focus": (
            "repair the checkpointed decision projection: either add the approved "
            "scope to goal_boundary.write_scope, rewrite the todo inside the current "
            "boundary, or create a concrete user/controller gate"
        ),
        "spend_policy": (
            "append exactly one heartbeat spend only after boundary projection repair, "
            "todo rewrite, or blocker writeback is validated"
        ),
        "required_write_scopes": required_scopes,
        "allowed_write_scopes": allowed_scopes,
        "missing_write_scopes": missing_scopes,
        "selected_todo": {
            key: selected.get(key)
            for key in ("todo_id", "index", "priority", "task_class", "action_kind")
            if selected.get(key) is not None
        },
        "selected_todo_text": selected_text,
    }
    if boundary_authority:
        repair["checkpointed_boundary_authority"] = {
            "schema_version": boundary_authority.get("schema_version"),
            "active_count": boundary_authority.get("active_count"),
            "inactive_count": boundary_authority.get("inactive_count"),
            "active_write_scope": boundary_authority.get("active_write_scope"),
        }
        inactive_candidates = []
        for entry in boundary_authority.get("entries") or []:
            if not isinstance(entry, dict) or entry.get("active") is True:
                continue
            scopes = normalize_required_write_scopes(entry.get("write_scope"))
            if any(_write_scope_allowed(scope, scopes) for scope in missing_scopes):
                inactive_candidates.append(
                    {
                        key: entry.get(key)
                        for key in (
                            "decision_id",
                            "source",
                            "recorded_at",
                            "expires_at",
                            "freshness",
                            "inactive_reasons",
                            "write_scope",
                        )
                        if entry.get(key) is not None
                    }
                )
        if inactive_candidates:
            repair["inactive_authority_candidates"] = inactive_candidates[:3]
    return repair


def _control_plane_post_handoff_observation_hint(item: dict[str, Any]) -> dict[str, Any] | None:
    control_plane = compact_control_plane_policy(item.get("control_plane"))
    self_repair = (
        control_plane.get("self_repair")
        if isinstance(control_plane.get("self_repair"), dict)
        else {}
    )
    if self_repair.get("enabled") is not True:
        return None
    if str(item.get("adapter_kind") or "") != "harness_self_improvement":
        return None
    if item.get("agent_command"):
        return None

    handoff_readiness = (
        item.get("handoff_readiness")
        if isinstance(item.get("handoff_readiness"), dict)
        else {}
    )
    latest_run = (
        handoff_readiness.get("post_handoff_latest_run")
        if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
        else {}
    )
    if handoff_readiness.get("post_handoff_run_seen") is not True:
        return None
    if str(handoff_readiness.get("handoff_status") or "") != "post_handoff_run_seen":
        return None
    if normalize_delivery_outcome(latest_run.get("delivery_outcome")) != DeliveryOutcome.PRIMARY_GOAL_OUTCOME:
        return None

    return {
        "source": "quota.should-run",
        "recommended_mode": "post_handoff_observe_if_unchanged",
        "stop_if_unchanged": True,
        "notify": "DONT_NOTIFY",
        "reason": (
            "control-plane self-repair is enabled and the latest post-handoff "
            "implementation run already reached the primary outcome; inspect "
            "registry/status/run history/repo state, then stay quiet if no new "
            "evidence or concrete safe work is found"
        ),
        "spend_policy": (
            "do not append quota spend for an unchanged post-handoff observation; "
            "spend only after a new validated artifact, repair, or durable state "
            "writeback advances the control-plane contract"
        ),
        "latest_run": {
            key: latest_run.get(key)
            for key in POST_HANDOFF_RUN_COMPACT_FIELDS
            if latest_run.get(key) is not None
        },
    }


def _heartbeat_recommendation(
    item: dict[str, Any],
    *,
    goal_id: str,
    state: str,
    should_run: bool,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None = None,
    stall_self_repair: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = str(item.get("status") or "")
    waiting_on = str(item.get("waiting_on") or "")
    adapter_kind = str(item.get("adapter_kind") or "")
    lifecycle_phase = item.get("lifecycle_phase")
    lifecycle_flags = item.get("lifecycle_flags")
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
    replan_obligation = (
        item.get("autonomous_replan_obligation")
        if isinstance(item.get("autonomous_replan_obligation"), dict)
        else project_asset.get("autonomous_replan_obligation")
        if isinstance(project_asset.get("autonomous_replan_obligation"), dict)
        else None
    )
    has_user_todos = _open_todo_count(user_todo_summary) > 0
    has_agent_todos = _open_todo_count(agent_todo_summary) > 0
    work_lane_contract = work_lane_contract or _work_lane_contract(item, agent_todo_summary=agent_todo_summary)

    base: dict[str, Any] = {
        "source": "quota.should-run",
        "recommended_mode": "skip",
        "notify": "DONT_NOTIFY",
        "spend_policy": "do not append quota spend unless a completed bounded progress segment produced substantive progress",
    }

    if state == "operator_gate":
        return {
            **base,
            "recommended_mode": "ask_operator_gate",
            "notify": "NOTIFY",
            "spend_policy": "do not append quota spend while asking the operator gate",
            "reason": "operator gate blocks the gated delivery path",
        }
    if stall_self_repair and stall_self_repair.get("allowed"):
        return {
            **base,
            "recommended_mode": stall_self_repair.get("recommended_mode") or "repair_control_plane_stall",
            "notify": stall_self_repair.get("notify") or "DONT_NOTIFY",
            "spend_policy": stall_self_repair.get("spend_policy") or base["spend_policy"],
            "reason": stall_self_repair.get("reason") or "control-plane stall requires bounded repair",
            "repair_focus": stall_self_repair.get("repair_focus"),
        }
    if state in {"focus_wait", "waiting"} and has_user_todos:
        return {
            **base,
            "recommended_mode": "blocker_push_notify",
            "notify": "NOTIFY",
            "repeat_notification_required": True,
            "spend_policy": "do not append quota spend for the blocker-push turn",
            "reason": _open_todo_notify_reason(state=state, waiting_on=waiting_on),
        }
    if state == "focus_wait" and quota.get("handoff_outcome_floor_block"):
        if quota.get("outcome_floor_blocker_projected"):
            return {
                **base,
                "recommended_mode": "outcome_floor_blocker_projected_noop",
                "notify": "DONT_NOTIFY",
                "spend_policy": (
                    "do not append quota spend while the same concrete outcome-floor "
                    "blocker is already projected and no executable agent todo exists"
                ),
                "reason": str(
                    quota.get("reason")
                    or "outcome-floor blocker is already projected; wait for fresh outcome evidence"
                ),
            }
        if quota.get("safe_bypass_allowed"):
            return {
                **base,
                "recommended_mode": "outcome_floor_recovery",
                "notify": "DONT_NOTIFY",
                "spend_policy": (
                    "append exactly one quota spend only after a validated "
                    "ranker/cross-domain evidence artifact or concrete blocker writeback; "
                    "do not spend for another surface-only report"
                ),
                "reason": str(quota.get("reason") or "handoff outcome floor is not met"),
            }
        return {
            **base,
            "recommended_mode": "report_handoff_outcome_blocker",
            "notify": "NOTIFY",
            "spend_policy": "do not append quota spend while reporting the handoff outcome-floor blocker",
            "reason": str(quota.get("reason") or "handoff outcome floor is not met"),
        }
    if not should_run:
        return {
            **base,
            "recommended_mode": "quota_skip",
            "reason": f"quota state is {state}; skip delivery compute",
        }
    if replan_obligation and replan_obligation.get("required"):
        payload = {
            **base,
            "recommended_mode": "autonomous_replan_required",
            "notify": "DONT_NOTIFY",
            "replan_obligation": {
                "schema_version": replan_obligation.get("schema_version"),
                "stall_threshold": replan_obligation.get("stall_threshold"),
                "trigger_count": replan_obligation.get("trigger_count"),
                "triggers": replan_obligation.get("triggers") or [],
                "next_validation_command": replan_obligation.get("next_validation_command"),
                "stop_condition": replan_obligation.get("stop_condition"),
            },
            "spend_policy": (
                "append exactly one heartbeat spend only after executing the selected "
                "replan slice, validating it, and writing back todo split/add/retire state"
            ),
            "reason": (
                "status exposes an autonomous replan obligation; advance the "
                "planning-trigger slice before another monitor-only or repeated action"
            ),
        }
        return payload

    if item.get("agent_command"):
        return {
            **base,
            "recommended_mode": "run_agent_command",
            "command": str(item.get("agent_command")),
            "notify": "DONT_NOTIFY",
            "spend_policy": "append exactly one heartbeat spend after the command completes and validation/writeback are saved",
            "reason": "current status exposes an approved project-agent command",
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is False
        and has_user_todos
    ):
        return {
            **base,
            "recommended_mode": "monitor_quiet_until_material_transition",
            "spend_policy": (
                "do not append quota spend or repeat a blocker notification for a "
                "monitor-only poll; keep the open user todo visible in the payload and "
                "wait for a material monitor transition"
            ),
            "reason": (
                "monitor-only polling has no material transition to write back; the "
                "current open user todo is already part of the durable active state"
            ),
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is False
        and not has_user_todos
    ):
        return {
            **base,
            "recommended_mode": "monitor_quiet_until_material_transition",
            "spend_policy": (
                "do not append quota spend until a material monitor transition, regression, "
                "or concrete blocker is validated and written back"
            ),
            "reason": "all visible open agent todos are monitor-class work with no material transition to record",
        }

    if (
        work_lane_contract
        and work_lane_contract.get("lane") == "continuous_monitor"
        and work_lane_contract.get("must_attempt_work") is True
        and not has_user_todos
    ):
        latest_run: dict[str, Any] = {}
        handoff_readiness = (
            item.get("handoff_readiness")
            if isinstance(item.get("handoff_readiness"), dict)
            else {}
        )
        latest_handoff_run = (
            handoff_readiness.get("post_handoff_latest_run")
            if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
            else {}
        )
        if latest_handoff_run:
            latest_run = {
                key: latest_handoff_run.get(key)
                for key in POST_HANDOFF_RUN_COMPACT_FIELDS
                if latest_handoff_run.get(key) is not None
            }
            latest_run["progress_scope"] = _latest_run_progress_scope(latest_handoff_run)
        payload = {
            **base,
            "recommended_mode": "follow_work_lane_contract",
            "spend_policy": (
                "follow work_lane_contract.obligation; spend only after validated "
                "advancement, concrete blocker writeback, or a material monitor transition"
            ),
            "reason": (
                "work_lane_contract is the machine contract for monitor-vs-advancement routing"
            ),
        }
        if latest_run:
            payload["latest_run"] = latest_run
        return payload

    if status == "connected_without_run" and _supports_read_only_project_map(adapter_kind):
        return {
            **base,
            "recommended_mode": "run_first_read_only_map",
            "command": f"loopx read-only-map --goal-id {goal_id}",
            "notify": "NOTIFY",
            "spend_policy": "append exactly one heartbeat spend after the read-only map run is saved and validated",
            "reason": "connected read-only project has no saved compact run yet",
        }

    mapped = (
        status == "read_only_project_map"
        or _has_lifecycle_marker(lifecycle_phase, lifecycle_flags, marker="mapped")
    )
    if mapped and not any([has_user_todos, has_agent_todos, item.get("agent_command")]):
        return {
            **base,
            "recommended_mode": "mapped_noop_if_unchanged",
            "stop_if_unchanged": True,
            "spend_policy": (
                "do not run another dry-run or append quota spend when the latest read-only map is still current "
                "and there is no new user instruction, owner evidence, agent todo, stale source, or safe handoff"
            ),
            "reason": "latest compact read-only map already exists; wait for new evidence or a concrete safe action",
        }

    post_handoff_observation = _control_plane_post_handoff_observation_hint(item)
    if post_handoff_observation and not has_user_todos:
        latest_observed_run = (
            post_handoff_observation.get("latest_run")
            if isinstance(post_handoff_observation.get("latest_run"), dict)
            else {}
        )
        progress_scope = _latest_run_progress_scope(latest_observed_run)
        if isinstance(latest_observed_run, dict) and latest_observed_run:
            latest_observed_run.setdefault("progress_scope", progress_scope)
        if has_agent_todos and progress_scope == "dependency_observation":
            return {
                **base,
                **{
                    key: value
                    for key, value in post_handoff_observation.items()
                    if key != "stop_if_unchanged"
                },
                "recommended_mode": "follow_work_lane_contract",
                "spend_policy": (
                    "follow work_lane_contract.obligation; spend only after validated "
                    "advancement, concrete blocker writeback, or a material monitor transition"
                ),
                "reason": (
                    "latest post-handoff run was dependency observation; the work lane "
                    "contract decides whether to advance backlog or record a material transition"
                ),
            }
        if has_agent_todos:
            active_observation = {
                key: value
                for key, value in post_handoff_observation.items()
                if key != "stop_if_unchanged"
            }
            return {
                **base,
                **active_observation,
                "recommended_mode": "post_handoff_observe_then_backlog_step",
                "spend_policy": (
                    "observe registry/status/run history/repo state first; if unchanged, "
                    "advance exactly one bounded agent-todo backlog segment and append quota "
                    "spend only after validation and durable writeback"
                ),
                "reason": (
                    "latest post-handoff implementation reached the primary outcome, but "
                    "an open agent todo remains; observe for new blockers first, then "
                    "advance one bounded backlog step instead of quiet idling"
                ),
            }
        return {
            **base,
            **post_handoff_observation,
        }

    return {
        **base,
        "recommended_mode": "steering_audit_then_one_step",
        "spend_policy": "append exactly one heartbeat spend only after a bounded progress segment is validated and written back",
        "reason": "eligible Codex-ready goal requires the standard steering audit before delivery",
    }


def _execution_obligation(
    *,
    should_run: bool,
    effective_action: str,
    heartbeat_recommendation: dict[str, Any],
    work_lane_contract: dict[str, Any] | None = None,
    external_evidence_observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_execution_obligation(
        should_run=should_run,
        effective_action=effective_action,
        heartbeat_recommendation=heartbeat_recommendation,
        work_lane_contract=work_lane_contract,
        external_evidence_observation=external_evidence_observation,
        successor_replan_mode=AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value,
    )


def build_quota_plan(status_payload: dict[str, Any], *, mode: str = "status") -> dict[str, Any]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    queue_by_goal = {
        str(item.get("goal_id")): item
        for item in queue_items
        if isinstance(item, dict) and item.get("goal_id")
    }
    health_items = [
        item
        for item in queue_items
        if isinstance(item, dict) and not isinstance(item.get("quota"), dict)
    ]

    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    status_goals = status_payload.get("goals") if isinstance(status_payload.get("goals"), list) else []
    status_goal_by_id = {
        str(goal.get("id") or ""): goal
        for goal in status_goals
        if isinstance(goal, dict) and goal.get("id")
    }
    registry_goal_by_id = _registry_goal_by_id(status_payload)
    groups: dict[str, list[dict[str, Any]]] = {state: [] for state in QUOTA_STATE_ORDER}
    groups["unknown"] = []

    for goal in run_goals:
        if not isinstance(goal, dict) or not goal.get("registry_member"):
            continue
        goal_id = str(goal.get("id") or "")
        status_goal = status_goal_by_id.get(goal_id) or registry_goal_by_id.get(goal_id) or {}
        attention = queue_by_goal.get(goal_id, {})
        project_asset = (
            attention.get("project_asset")
            if isinstance(attention.get("project_asset"), dict)
            else {}
        )
        project_asset_quota = (
            project_asset.get("quota")
            if isinstance(project_asset.get("quota"), dict)
            else {}
        )
        latest = _latest_run(goal)
        waiting_on = attention.get("waiting_on") or "none"
        lifecycle_phase = attention.get("lifecycle_phase") or goal.get("lifecycle_phase")
        lifecycle_flags = attention.get("lifecycle_flags") or goal.get("lifecycle_flags")
        status = attention.get("status") or goal.get("status")
        control_plane = (
            compact_control_plane_policy(attention.get("control_plane"))
            or compact_control_plane_policy(project_asset.get("control_plane"))
            or compact_control_plane_policy(goal.get("control_plane"))
        )
        raw_quota = attention.get("quota") if isinstance(attention.get("quota"), dict) else goal.get("quota")
        if project_asset_quota:
            raw_quota_base = raw_quota if isinstance(raw_quota, dict) else {}
            quota = {**raw_quota_base, **project_asset_quota}
        elif isinstance(raw_quota, dict):
            quota = raw_quota
            quota = _quota_with_focus_wait_override(
                quota,
                waiting_on=str(waiting_on or ""),
                lifecycle_phase=lifecycle_phase,
                lifecycle_flags=lifecycle_flags,
                status=status,
            )
        else:
            quota = quota_status(
                goal,
                waiting_on=str(waiting_on or ""),
                severity=str(attention.get("severity") or ""),
                lifecycle_phase=lifecycle_phase,
                lifecycle_flags=lifecycle_flags,
                status=status,
            )
        quota = quota_with_handoff_outcome_floor(
            quota,
            waiting_on=str(waiting_on or ""),
            project_asset=project_asset,
            handoff_readiness=attention.get("handoff_readiness")
            if isinstance(attention.get("handoff_readiness"), dict)
            else None,
        )
        state = str(quota.get("state") or "waiting")
        item: dict[str, Any] = {
            "goal_id": goal_id,
            "status": status,
            "lifecycle_phase": lifecycle_phase,
            "lifecycle_flags": lifecycle_flags,
            "waiting_on": waiting_on,
            "severity": attention.get("severity") or "info",
            "source": attention.get("source") or "run_history",
            "recommended_action": project_asset.get("next_action")
            or attention.get("recommended_action")
            or latest.get("recommended_action"),
            "adapter_kind": goal.get("adapter_kind"),
            "adapter_status": goal.get("adapter_status"),
            "repo": (
                goal.get("repo")
                or goal.get("project")
                or goal.get("root")
                or status_goal.get("repo")
                or status_goal.get("project")
                or status_goal.get("root")
            ),
            "coordination": goal.get("coordination") if isinstance(goal.get("coordination"), dict) else None,
            "spawn_policy": goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else None,
            "guards": goal.get("guards") if isinstance(goal.get("guards"), list) else [],
            "next_probe": goal.get("next_probe"),
            "latest_run_generated_at": latest.get("generated_at"),
            "quota": quota,
        }
        if control_plane:
            item["control_plane"] = control_plane
        if project_asset:
            item["project_asset"] = project_asset
            item["project_asset_source"] = "project_asset"
        else:
            item["project_asset_source"] = "legacy_raw_fallback"
        for optional_field in (
            "operator_question",
            "agent_command",
            "controller_stage",
            "missing_gates",
            "next_handoff_condition",
            "handoff_readiness",
            "user_todos",
            "agent_todos",
            "active_state_next_action",
            "active_state_next_action_entries",
        ):
            if optional_field in attention:
                if optional_field == "handoff_readiness":
                    compact_handoff = _compact_handoff_readiness(attention[optional_field])
                    if compact_handoff:
                        item[optional_field] = compact_handoff
                else:
                    item[optional_field] = attention[optional_field]
        groups.setdefault(state, []).append(item)

    for state_items in groups.values():
        state_items.sort(key=_quota_sort_key)

    ordered_items = [
        item
        for state in QUOTA_STATE_ORDER
        for item in groups.get(state, [])
    ] + groups.get("unknown", [])
    next_automatic_turn = (groups.get("eligible") or [None])[0]
    summary = {
        "registered_goals": len(ordered_items),
        "health_blockers": len(health_items),
        "next_automatic_turn": next_automatic_turn.get("goal_id") if next_automatic_turn else None,
        "states": {state: len(groups.get(state, [])) for state in QUOTA_STATE_ORDER},
    }
    if groups.get("unknown"):
        summary["states"]["unknown"] = len(groups["unknown"])

    return {
        "ok": status_payload.get("ok"),
        "mode": mode,
        "registry": status_payload.get("registry"),
        "runtime_root": status_payload.get("runtime_root"),
        "goal_count": status_payload.get("goal_count"),
        "run_count": status_payload.get("run_count"),
        "summary": summary,
        "next_automatic_turn": next_automatic_turn,
        "groups": groups,
        "health_items": health_items,
    }


def _quota_plan_items(plan: dict[str, Any]) -> list[dict[str, Any]]:
    groups = plan.get("groups") if isinstance(plan.get("groups"), dict) else {}
    items: list[dict[str, Any]] = []
    for state_items in groups.values():
        if not isinstance(state_items, list):
            continue
        items.extend(item for item in state_items if isinstance(item, dict))
    return items


def _decision_freshness_warning(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any] | None:
    freshness = (
        status_payload.get("decision_freshness_summary")
        if isinstance(status_payload.get("decision_freshness_summary"), dict)
        else {}
    )
    raw_items = freshness.get("items") if isinstance(freshness.get("items"), list) else []
    items: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("goal_id") or "") != goal_id:
            continue
        if item.get("requires_decision_point_rebase") is not True:
            continue
        items.append(
            {
                "goal_id": item.get("goal_id"),
                "decision_kind": item.get("decision_kind"),
                "freshness_state": item.get("freshness_state"),
                "decision_at": item.get("decision_at"),
                "classification": item.get("classification"),
                "age_days": item.get("age_days"),
                "newer_event_count_7d": item.get("newer_event_count_7d"),
                "reason": item.get("reason"),
            }
        )

    if not items:
        return None
    summary = freshness.get("summary") if isinstance(freshness.get("summary"), dict) else {}
    return {
        "source": freshness.get("source") or "run_history",
        "window_days": freshness.get("window_days"),
        "message": (
            "decision-point rebase required before reusing sampled reward/gate state; "
            "refresh registry, ACTIVE_GOAL_STATE, quota, policy, and run status first"
        ),
        "rebase_required_count": len(items),
        "global_rebase_required_count": summary.get("rebase_required_count"),
        "global_stale_count": summary.get("stale_count"),
        "items": items[:DECISION_FRESHNESS_WARNING_ITEM_LIMIT],
    }


def _promotion_readiness_warning(status_payload: dict[str, Any]) -> dict[str, Any] | None:
    readiness = (
        status_payload.get("promotion_readiness_summary")
        if isinstance(status_payload.get("promotion_readiness_summary"), dict)
        else {}
    )
    if not readiness:
        return None
    freshness_status = str(readiness.get("freshness_status") or "unknown")
    requires_readiness_run = readiness.get("requires_readiness_run") is True
    available = readiness.get("available")
    if available is not False and not requires_readiness_run and freshness_status == "fresh":
        return None

    return {
        "source": readiness.get("source") or "run_history",
        "available": available,
        "freshness_status": freshness_status,
        "requires_readiness_run": requires_readiness_run,
        "freshness_window_hours": readiness.get("freshness_window_hours"),
        "age_hours": readiness.get("age_hours"),
        "sample_run_count": readiness.get("sample_run_count"),
        "goal_id": readiness.get("goal_id"),
        "generated_at": readiness.get("generated_at"),
        "classification": readiness.get("classification"),
        "json_exists": readiness.get("json_exists"),
        "markdown_exists": readiness.get("markdown_exists"),
        "reason": readiness.get("reason"),
        "message": (
            "promotion readiness evidence is missing, stale, or unknown; run canary readiness smoke"
        ),
    }


def _recent_reward_lessons(status_payload: dict[str, Any], *, goal_id: str) -> list[dict[str, Any]]:
    run_history = (
        status_payload.get("run_history")
        if isinstance(status_payload.get("run_history"), dict)
        else {}
    )
    goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    goal = next(
        (
            candidate
            for candidate in goals
            if isinstance(candidate, dict) and str(candidate.get("id") or "") == goal_id
        ),
        None,
    )
    if not isinstance(goal, dict):
        return []
    lessons: list[dict[str, Any]] = []
    for run in goal.get("latest_runs") or []:
        if not isinstance(run, dict):
            continue
        reward = run.get("human_reward") if isinstance(run.get("human_reward"), dict) else {}
        lesson = reward.get("lesson") if isinstance(reward.get("lesson"), dict) else {}
        if not lesson:
            continue
        lessons.append(
            {
                "generated_at": run.get("generated_at"),
                "decision": reward.get("decision"),
                "reward": reward.get("reward"),
                "kind": lesson.get("kind"),
                "summary": lesson.get("summary"),
                "avoid": lesson.get("avoid") if isinstance(lesson.get("avoid"), list) else [],
                "prefer": lesson.get("prefer") if isinstance(lesson.get("prefer"), list) else [],
            }
        )
    return lessons


def _reward_lesson_projection_warning(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    recommended_action: str | None,
) -> dict[str, Any] | None:
    action = str(recommended_action or "").strip()
    if not action:
        return None
    action_lower = action.lower()
    action_tokens = _action_scope_tokens_from_text(action)
    matches: list[dict[str, Any]] = []
    for lesson in _recent_reward_lessons(status_payload, goal_id=goal_id):
        for avoid in lesson.get("avoid") or []:
            avoid_text = str(avoid or "").strip()
            if not avoid_text:
                continue
            avoid_tokens = _action_scope_tokens_from_text(avoid_text)
            exact_match = avoid_text.lower() in action_lower
            if not exact_match and not avoid_tokens:
                continue
            token_overlap = sorted(action_tokens & avoid_tokens)
            if not exact_match and len(token_overlap) < min(2, len(avoid_tokens)):
                continue
            matches.append(
                {
                    "generated_at": lesson.get("generated_at"),
                    "decision": lesson.get("decision"),
                    "kind": lesson.get("kind"),
                    "summary": lesson.get("summary"),
                    "avoid": avoid_text,
                    "token_overlap": token_overlap[:5],
                }
            )
    if not matches:
        return None
    return {
        "schema_version": "reward_lesson_projection_warning_v0",
        "source": "run_history.human_reward.lesson",
        "goal_id": goal_id,
        "message": (
            "recommended_action overlaps a recent human_reward lesson avoid rule; "
            "rebase the route or update the affected todo/next action before continuing"
        ),
        "recommended_action": action,
        "match_count": len(matches),
        "matches": matches[:3],
    }


def _registry_goal_by_id(status_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    registry_value = status_payload.get("registry")
    if not registry_value:
        return {}
    registry_path = Path(str(registry_value)).expanduser()
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    goals = payload.get("goals") if isinstance(payload, dict) else None
    if not isinstance(goals, list):
        return {}
    return {
        str(goal.get("id") or ""): goal
        for goal in goals
        if isinstance(goal, dict) and goal.get("id")
    }


def _recovery_delivery_allowed(quota: dict[str, Any], *, plan_ok: bool) -> bool:
    return (
        bool(plan_ok)
        and quota.get("safe_bypass_allowed") is True
        and str(quota.get("safe_bypass_kind") or "") == "outcome_floor_recovery"
    )


def _effective_action(
    *,
    normal_delivery_allowed: bool,
    recovery_delivery_allowed: bool,
    self_repair_allowed: bool,
    capability_repair_allowed: bool = False,
    workspace_repair_allowed: bool = False,
    stall_self_repair: dict[str, Any] | None,
    state: str,
    quota: dict[str, Any],
) -> str:
    if normal_delivery_allowed:
        return "normal_run"
    if recovery_delivery_allowed:
        return "outcome_floor_recovery"
    if workspace_repair_allowed:
        return "side_agent_workspace_repair"
    if self_repair_allowed:
        repair_action = (
            stall_self_repair.get("effective_action")
            if isinstance(stall_self_repair, dict)
            else None
        )
        return str(repair_action or "control_plane_repair")
    if capability_repair_allowed:
        return "capability_bridge_repair"
    if state == "operator_gate":
        return "operator_gate_notify"
    if state == "blocked_health":
        return "blocked_health"
    if state == "throttled":
        return "throttled_skip"
    if state in {"focus_wait", "waiting"}:
        return "blocked_wait"
    if quota.get("focus_wait"):
        return "blocked_wait"
    return "quota_skip"


def build_quota_should_run(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    agent_id: str | None = None,
    available_capabilities: Any = None,
    include_scheduler_detail: bool = False,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    plan = build_quota_plan(status_payload, mode="should-run")
    item = next((candidate for candidate in _quota_plan_items(plan) if candidate.get("goal_id") == safe_goal_id), None)
    health_items = plan.get("health_items") if isinstance(plan.get("health_items"), list) else []
    health_item = next(
        (
            candidate
            for candidate in health_items
            if isinstance(candidate, dict) and candidate.get("goal_id") == safe_goal_id
        ),
        None,
    )

    if item:
        quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
        state = str(quota.get("state") or "unknown")
        normal_delivery_allowed = bool(plan.get("ok")) and state == "eligible"
        recovery_allowed = _recovery_delivery_allowed(quota, plan_ok=bool(plan.get("ok")))
        reason = str(quota.get("reason") or "quota state is not eligible")
        if not plan.get("ok"):
            reason = "status or contract health is not ok; skip automatic compute"
        project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
        agent_identity = _quota_agent_identity(item, agent_id=agent_id)
        user_todo_summary = _select_todo_summary(
            item.get("user_todos"),
            project_asset.get("user_todos") if project_asset else None,
            agent_identity=agent_identity,
            filter_user_gate_blocks_agent=True,
        )
        agent_todo_summary = _select_todo_summary(
            item.get("agent_todos"),
            project_asset.get("agent_todos") if project_asset else None,
            agent_identity=agent_identity,
        )
        agent_scoped_user_gate_override = _agent_scoped_user_gate_override(
            state=state,
            item=item,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            agent_identity=agent_identity,
        )
        if agent_scoped_user_gate_override:
            quota = {
                **quota,
                "state": "eligible",
                "agent_scoped_user_gate_override": agent_scoped_user_gate_override,
                "reason": agent_scoped_user_gate_override["reason"],
            }
            state = "eligible"
            normal_delivery_allowed = bool(plan.get("ok"))
            recovery_allowed = _recovery_delivery_allowed(
                quota,
                plan_ok=bool(plan.get("ok")),
            )
            reason = str(agent_scoped_user_gate_override["reason"])
        outcome_floor_blocker_projected = (
            recovery_allowed
            and _outcome_floor_blocker_already_projected(agent_todo_summary)
        )
        if outcome_floor_blocker_projected:
            quota = {
                **quota,
                "safe_bypass_allowed": False,
                "safe_bypass_kind": None,
                "outcome_floor_blocker_projected": True,
                "reason": (
                    "handoff outcome floor blocker already projected: no executable "
                    "agent todo exists; wait for fresh ranker/cross-domain evidence "
                    "or a new manifest before spending recovery compute"
                ),
            }
            recovery_allowed = False
            reason = str(quota["reason"])
        goal_boundary = _goal_boundary(item)
        workspace_guard = _side_agent_workspace_guard(item, agent_identity)
        automation_prompt_upgrade = _automation_prompt_upgrade(
            item,
            goal_id=safe_goal_id,
            agent_identity=agent_identity,
        )
        automation_prompt_upgrade_required = bool(
            automation_prompt_upgrade
            and automation_prompt_upgrade.get("blocks_should_run") is True
        )
        blocked_priority_fallback = _blocked_priority_fallback(agent_todo_summary)
        stall_self_repair = _stall_self_repair_hint(
            item,
            state=state,
            plan_ok=bool(plan.get("ok")),
            health_items=health_items,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
        )
        self_repair_allowed = bool(stall_self_repair and stall_self_repair.get("allowed"))
        work_lane_contract = _work_lane_contract(item, agent_todo_summary=agent_todo_summary)
        capability_gate = _capability_gate(
            agent_todo_summary,
            available_capabilities=_available_capabilities(available_capabilities),
            agent_identity=agent_identity,
        )
        capability_repair_allowed = False
        workspace_repair_allowed = False
        projection_gap = _state_projection_gap(item, project_asset)
        projection_gap_repair = _state_projection_gap_repair_hint(
            projection_gap,
            candidate_should_run=bool(
                normal_delivery_allowed or recovery_allowed or self_repair_allowed
            ),
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        if projection_gap_repair:
            stall_self_repair = projection_gap_repair
            self_repair_allowed = True
            normal_delivery_allowed = False
            recovery_allowed = False
            reason = str(projection_gap_repair.get("reason") or reason)
        boundary_projection_repair = _boundary_projection_repair_hint(
            goal_boundary,
            agent_todo_summary,
            candidate_should_run=bool(
                normal_delivery_allowed or recovery_allowed or self_repair_allowed
            ),
        )
        if boundary_projection_repair:
            stall_self_repair = boundary_projection_repair
            self_repair_allowed = True
            normal_delivery_allowed = False
            recovery_allowed = False
            reason = str(boundary_projection_repair.get("reason") or reason)
        if capability_gate and capability_gate.get("action") != "run":
            normal_delivery_allowed = False
            recovery_allowed = False
            if capability_gate.get("action") == "repair_bridge":
                capability_repair_allowed = True
                reason = str(capability_gate.get("reason") or "capability bridge repair required")
            else:
                reason = str(capability_gate.get("reason") or "selected todo capability is unavailable")
        if workspace_guard:
            normal_delivery_allowed = False
            recovery_allowed = False
            self_repair_allowed = False
            capability_repair_allowed = False
            workspace_repair_allowed = True
            reason = str(workspace_guard.get("reason") or "side-agent workspace guard blocks delivery")
        if automation_prompt_upgrade_required:
            normal_delivery_allowed = False
            recovery_allowed = False
            self_repair_allowed = False
            capability_repair_allowed = False
            workspace_repair_allowed = False
            reason = str(
                automation_prompt_upgrade.get("reason")
                or "identity-aware automation prompt upgrade is required"
            )
        should_run = bool(
            normal_delivery_allowed
            or recovery_allowed
            or self_repair_allowed
            or capability_repair_allowed
            or workspace_repair_allowed
        )
        effective_action = _effective_action(
            normal_delivery_allowed=normal_delivery_allowed,
            recovery_delivery_allowed=recovery_allowed,
            self_repair_allowed=self_repair_allowed,
            capability_repair_allowed=capability_repair_allowed,
            workspace_repair_allowed=workspace_repair_allowed,
            stall_self_repair=stall_self_repair,
            state=state,
            quota=quota,
        )
        if automation_prompt_upgrade_required:
            should_run = False
            effective_action = "automation_prompt_upgrade_required"
        recommendation_item = {**item, "quota": quota}
        heartbeat_recommendation = _heartbeat_recommendation(
            recommendation_item,
            goal_id=safe_goal_id,
            state=state,
            should_run=should_run,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
            stall_self_repair=stall_self_repair,
        )
        if capability_gate and capability_gate.get("action") == "repair_bridge":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "repair_capability_bridge",
                "notify": "DONT_NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "append exactly one quota spend only after a validated bridge "
                    "repair, todo rewrite, or compact blocker writeback"
                ),
            }
        elif capability_gate and capability_gate.get("action") == "ask_owner":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "ask_owner_for_capability",
                "notify": "NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": "do not append quota spend while asking for missing capability",
            }
        elif capability_gate and capability_gate.get("action") == "skip":
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "capability_skip",
                "notify": "DONT_NOTIFY",
                "reason": capability_gate.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": "do not append quota spend while all executable todos lack current capabilities",
            }
        if workspace_guard:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "repair_side_agent_workspace",
                "notify": "DONT_NOTIFY",
                "reason": workspace_guard.get("reason") or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "do not append quota spend for workspace relocation; rerun quota "
                    "from the independent worktree before delivery"
                ),
            }
        if automation_prompt_upgrade_required:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "automation_prompt_upgrade",
                "notify": "DONT_NOTIFY",
                "reason": automation_prompt_upgrade.get("reason")
                or heartbeat_recommendation.get("reason"),
                "spend_policy": (
                    "do not append quota spend for stale/unscoped automation; "
                    "rerun quota should-run from an identity-scoped prompt"
                ),
            }
        if blocked_priority_fallback and should_run:
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "notify": "NOTIFY",
                "reason": blocked_priority_fallback.get("reason")
                or heartbeat_recommendation.get("reason"),
                "blocked_priority_fallback": blocked_priority_fallback,
            }
        external_evidence_observation = _external_evidence_observation_obligation(
            item,
            state=state,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        if external_evidence_observation and not workspace_guard:
            normal_delivery_allowed = False
            should_run = True
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": "external_evidence_observe_or_blocker",
                "notify": "DONT_NOTIFY",
                "reason": (
                    "waiting external evidence requires a read-only observation "
                    "or compact blocker before quiet no-op"
                ),
                "spend_policy": external_evidence_observation.get("spend_policy")
                or heartbeat_recommendation.get("spend_policy"),
            }
            effective_action = "external_evidence_observe"
            reason = "external evidence monitor requires read-only observation before quiet no-op"
        monitor_quiet_skip = (
            normal_delivery_allowed
            and not recovery_allowed
            and not self_repair_allowed
            and isinstance(work_lane_contract, dict)
            and work_lane_contract.get("obligation") == "quiet_until_material_monitor_transition"
            and work_lane_contract.get("must_attempt_work") is False
            and heartbeat_recommendation.get("recommended_mode") == "monitor_quiet_until_material_transition"
            and heartbeat_recommendation.get("notify") == "DONT_NOTIFY"
        )
        if monitor_quiet_skip:
            normal_delivery_allowed = False
            should_run = False
            effective_action = "monitor_quiet_skip"
            reason = str(
                heartbeat_recommendation.get("reason")
                or "monitor-only polling has no material transition; skip delivery compute"
            )
        selected_recommended_action = _selected_recommended_action(
            item,
            agent_todo_summary=agent_todo_summary,
            work_lane_contract=work_lane_contract,
        )
        due_monitor_attempt = _work_lane_due_monitor_attempt(work_lane_contract)
        if capability_gate and not due_monitor_attempt:
            if capability_gate.get("action") in {"repair_bridge", "ask_owner", "skip"}:
                selected_recommended_action = (
                    capability_gate.get("owner_action")
                    or capability_gate.get("reason")
                    or selected_recommended_action
                )
            else:
                selected_recommended_action = _selected_action_with_capability_gate(
                    selected_recommended_action,
                    capability_gate=capability_gate,
                )
        if workspace_guard:
            selected_recommended_action = (
                workspace_guard.get("required_action")
                or workspace_guard.get("reason")
                or selected_recommended_action
            )
        if automation_prompt_upgrade_required:
            selected_recommended_action = (
                automation_prompt_upgrade.get("recommended_action")
                or automation_prompt_upgrade.get("reason")
                or selected_recommended_action
            )
        agent_lane_next_action = None
        if not due_monitor_attempt:
            agent_lane_next_action = _agent_lane_next_action(
                agent_identity=agent_identity,
                agent_todo_summary=agent_todo_summary,
                capability_gate=capability_gate,
                active_next_action=(
                    item.get("active_state_next_action")
                    or (
                        item.get("project_asset", {}).get("next_action")
                        if isinstance(item.get("project_asset"), dict)
                        else None
                    )
                ),
            )
            selected_recommended_action = _selected_action_with_agent_lane(
                selected_recommended_action,
                agent_lane_next_action=agent_lane_next_action,
            )
        agent_scope_frontier = _agent_scope_no_candidate_frontier(
            agent_identity=agent_identity,
            agent_todo_summary=agent_todo_summary,
            agent_lane_next_action=agent_lane_next_action,
            work_lane_contract=work_lane_contract,
            candidate_should_run=bool(should_run and normal_delivery_allowed),
        )
        agent_lane_frontier_hint = _agent_lane_frontier_hint(
            goal_id=safe_goal_id,
            agent_identity=agent_identity,
            agent_todo_summary=agent_todo_summary,
            agent_lane_next_action=agent_lane_next_action,
            agent_scope_frontier=agent_scope_frontier,
            work_lane_contract=work_lane_contract,
        )
        if agent_scope_frontier and agent_lane_frontier_hint:
            agent_scope_frontier["frontier_hint"] = agent_lane_frontier_hint
        if agent_scope_frontier:
            frontier_action = str(agent_scope_frontier.get("effective_action") or "")
            successor_replan_required = (
                frontier_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value
            )
            normal_delivery_allowed = False
            should_run = bool(successor_replan_required)
            effective_action = frontier_action
            reason = str(agent_scope_frontier.get("reason") or reason)
            selected_recommended_action = (
                agent_scope_frontier.get("recommended_action")
                or selected_recommended_action
            )
            heartbeat_recommendation = {
                **heartbeat_recommendation,
                "recommended_mode": effective_action,
                "notify": "DONT_NOTIFY",
                "reason": reason,
                "spend_policy": agent_scope_frontier.get("spend_policy")
                or "do not append quota spend while the current agent has no in-scope runnable candidate",
            }
        state_action_projection_warning = _state_action_projection_warning(
            item,
            agent_todo_summary=agent_todo_summary,
            selected_action=selected_recommended_action,
            work_lane_contract=work_lane_contract,
        )
        active_state_next_action_text = _protocol_action_text(
            item.get("active_state_next_action")
            or project_asset.get("active_state_next_action")
            or project_asset.get("next_action"),
            limit=320,
        )
        latest_run_recommended_action_text = _protocol_action_text(
            item.get("latest_run_recommended_action")
            or project_asset.get("latest_run_recommended_action"),
            limit=320,
        )
        agent_lane_next_action_text = _protocol_action_text(
            agent_lane_next_action.get("text") if isinstance(agent_lane_next_action, dict) else None,
            limit=320,
        )
        next_action_warning = next_action_projection_warning(
            active_state_next_action=active_state_next_action_text,
            latest_run_recommended_action=latest_run_recommended_action_text,
            agent_lane_next_action=agent_lane_next_action_text,
        )
        agent_scope_action = _agent_scope_frontier_action(effective_action)
        payload = {
            "ok": bool(plan.get("ok")) or self_repair_allowed or capability_repair_allowed or workspace_repair_allowed,
            "status_health_ok": bool(plan.get("ok")),
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": (
                "run"
                if normal_delivery_allowed
                else "observe"
                if external_evidence_observation
                else "safe_bypass_recovery"
                if recovery_allowed
                else "self_repair"
                if self_repair_allowed
                else "repair_bridge"
                if capability_repair_allowed
                else "workspace_guard"
                if workspace_repair_allowed
                else "automation_prompt_upgrade"
                if automation_prompt_upgrade_required
                else agent_scope_action.value
                if agent_scope_action is not None
                else "skip"
            ),
            "should_run": should_run,
            "normal_delivery_allowed": normal_delivery_allowed,
            "recovery_delivery_allowed": recovery_allowed,
            "self_repair_allowed": self_repair_allowed,
            "capability_repair_allowed": capability_repair_allowed,
            "workspace_repair_allowed": workspace_repair_allowed,
            "effective_action": effective_action,
            "actionable_by_codex": bool(
                should_run
                or recovery_allowed
                or external_evidence_observation
                or capability_repair_allowed
                or workspace_repair_allowed
            ),
            "reason": (
                str(stall_self_repair.get("reason"))
                if self_repair_allowed and isinstance(stall_self_repair, dict)
                else reason
            ),
            "quota": quota,
            "state": state,
            "blocked_action_scope": (
                boundary_projection_repair.get("blocked_action_scope")
                if boundary_projection_repair
                else quota.get("blocked_action_scope")
            ),
            "safe_bypass_allowed": bool(quota.get("safe_bypass_allowed")),
            "safe_bypass_kind": quota.get("safe_bypass_kind"),
            "safe_bypass_policy": quota.get("safe_bypass_policy"),
            "waiting_on": item.get("waiting_on"),
            "status": item.get("status"),
            "lifecycle_phase": item.get("lifecycle_phase"),
            "lifecycle_flags": item.get("lifecycle_flags"),
            "source": item.get("source"),
            "project_asset_source": item.get("project_asset_source"),
            "recommended_action": selected_recommended_action,
            "active_state_next_action": active_state_next_action_text or None,
            "latest_run_recommended_action": latest_run_recommended_action_text or None,
            "execution_profile": _quota_execution_profile_summary(
                project_asset.get("execution_profile")
            )
            if project_asset
            else None,
            "long_task_cadence_hint": (
                project_asset.get("long_task_cadence_hint")
                if project_asset and isinstance(project_asset.get("long_task_cadence_hint"), dict)
                else (
                    item.get("long_task_cadence_hint")
                    if isinstance(item.get("long_task_cadence_hint"), dict)
                    else None
                )
            ),
            "handoff_readiness": item.get("handoff_readiness"),
            "heartbeat_recommendation": heartbeat_recommendation,
            "execution_obligation": _execution_obligation(
                should_run=should_run,
                effective_action=effective_action,
                heartbeat_recommendation=heartbeat_recommendation,
                work_lane_contract=work_lane_contract,
                external_evidence_observation=external_evidence_observation,
            ),
            "goal_boundary": goal_boundary,
            "plan_summary": plan.get("summary"),
            "todo_write_hint": _todo_write_hint(safe_goal_id),
        }
        if agent_identity:
            payload["agent_identity"] = agent_identity
        if agent_lane_next_action:
            payload["agent_lane_next_action"] = agent_lane_next_action
        if agent_lane_frontier_hint:
            payload["agent_lane_frontier_hint"] = agent_lane_frontier_hint
        if agent_scope_frontier:
            payload["agent_scope_frontier"] = agent_scope_frontier
        if workspace_guard:
            payload["workspace_guard"] = workspace_guard
        if automation_prompt_upgrade:
            payload["automation_prompt_upgrade"] = automation_prompt_upgrade
        if agent_scoped_user_gate_override:
            payload["agent_scoped_user_gate_override"] = agent_scoped_user_gate_override
        if work_lane_contract:
            payload["work_lane_contract"] = work_lane_contract
        if capability_gate:
            payload["capability_gate"] = capability_gate
            if capability_gate.get("action") == "ask_owner":
                payload["notify_user_on_capability_gate"] = True
        if external_evidence_observation:
            payload["external_evidence_observation"] = external_evidence_observation
        control_plane = compact_control_plane_policy(item.get("control_plane"))
        if control_plane:
            payload["control_plane"] = control_plane
        if stall_self_repair:
            payload["stall_self_repair"] = stall_self_repair
        if projection_gap:
            payload["state_projection_gap"] = projection_gap
        if boundary_projection_repair:
            payload["boundary_projection_gap"] = boundary_projection_repair
        if item.get("operator_question"):
            payload["operator_question"] = item.get("operator_question")
        if item.get("missing_gates"):
            payload["missing_gates"] = item.get("missing_gates")
        if user_todo_summary:
            payload["user_todo_summary"] = user_todo_summary
            repeat_open_todo_notification = (
                heartbeat_recommendation.get("repeat_notification_required") is True
            )
            user_gate_todo_open = _has_open_user_gate_todo(user_todo_summary)
            if user_gate_todo_open:
                payload["notify_user_on_gate"] = True
                payload["open_todo_notify_reason"] = _user_gate_todo_notify_reason(
                    user_todo_summary
                )
                payload["open_todo_notification_policy"] = "repeat_until_resolved"
            elif _should_notify_user_on_open_todo(
                state=state,
                waiting_on=str(item.get("waiting_on") or ""),
                user_todo_summary=user_todo_summary,
            ) or repeat_open_todo_notification:
                payload["notify_user_on_open_todo"] = True
                payload["open_todo_notify_reason"] = _open_todo_notify_reason(
                    state=state,
                    waiting_on=str(item.get("waiting_on") or ""),
                )
                if repeat_open_todo_notification:
                    payload["open_todo_notify_reason"] = (
                        heartbeat_recommendation.get("reason")
                        or "no-work polling should ask the current open user todo"
                    )
                    payload["open_todo_notification_policy"] = "repeat_until_resolved"
        scoped_user_gate_fallback = _scoped_user_gate_fallback(
            user_todo_summary,
            agent_todo_summary,
            allow_unrelated_gate=bool(payload.get("safe_bypass_allowed")),
        )
        if scoped_user_gate_fallback:
            payload["scoped_user_gate_fallback"] = scoped_user_gate_fallback
            payload["should_run"] = True
            if payload.get("decision") == "skip":
                payload["decision"] = "safe_bypass_user_gate_fallback"
            if payload.get("effective_action") in {"skip", "monitor_quiet_skip", None}:
                payload["effective_action"] = "scoped_user_gate_fallback"
            execution_obligation_payload = (
                dict(payload.get("execution_obligation"))
                if isinstance(payload.get("execution_obligation"), dict)
                else {}
            )
            execution_obligation_payload.update(
                {
                    "must_attempt_work": True,
                    "kind": "scoped_user_gate_fallback",
                    "minimum": "one_non_gated_fallback_segment_after_user_gate_notice",
                    "delivery_allowed": True,
                    "notify_is_execution_gate": False,
                    "contract": "scoped_user_gate_fallback",
                    "contract_obligation": scoped_user_gate_fallback.get(
                        "recommended_action"
                    ),
                    "reason": scoped_user_gate_fallback.get("reason"),
                }
            )
            payload["execution_obligation"] = execution_obligation_payload
            payload["safe_bypass_allowed"] = True
            payload["safe_bypass_kind"] = "scoped_user_gate_fallback"
            payload["safe_bypass_policy"] = (
                "The user gate blocks only the matched agent action scope. Surface "
                "that gate, then advance the selected non-gated fallback; spend only "
                "after validated writeback."
            )
            payload["actionable_by_codex"] = True
        payload["requires_user_action"] = bool(
            state == "operator_gate"
            or payload.get("notify_user_on_gate") is True
            or payload.get("notify_user_on_open_todo") is True
            or payload.get("notify_user_on_capability_gate") is True
        )
        if agent_todo_summary:
            payload["agent_todo_summary"] = agent_todo_summary
        if blocked_priority_fallback:
            payload["blocked_priority_fallback"] = blocked_priority_fallback
        attention_queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
        backlog_context = _compact_autonomous_candidate_context(
            attention_queue.get("autonomous_backlog_candidates"),
            goal_id=safe_goal_id,
        )
        if backlog_context:
            payload["autonomous_backlog_candidates"] = backlog_context
        monitor_context = _compact_autonomous_candidate_context(
            attention_queue.get("autonomous_monitor_candidates"),
            goal_id=safe_goal_id,
        )
        if monitor_context:
            payload["autonomous_monitor_candidates"] = monitor_context
        projection_warning = (
            item.get("stale_latest_run_warning")
            if isinstance(item.get("stale_latest_run_warning"), dict)
            else project_asset.get("stale_latest_run_warning")
            if isinstance(project_asset.get("stale_latest_run_warning"), dict)
            else None
        )
        if projection_warning:
            payload["stale_latest_run_warning"] = projection_warning
        if state_action_projection_warning:
            payload["state_action_projection_warning"] = state_action_projection_warning
        if next_action_warning:
            payload["next_action_projection_warning"] = next_action_warning
        backlog_warning = (
            item.get("backlog_hygiene_warning")
            if isinstance(item.get("backlog_hygiene_warning"), dict)
            else project_asset.get("backlog_hygiene_warning")
            if isinstance(project_asset.get("backlog_hygiene_warning"), dict)
            else None
        )
        if backlog_warning:
            payload["backlog_hygiene_warning"] = backlog_warning
        archive_warning = (
            item.get("completed_todo_archive_warning")
            if isinstance(item.get("completed_todo_archive_warning"), dict)
            else project_asset.get("completed_todo_archive_warning")
            if isinstance(project_asset.get("completed_todo_archive_warning"), dict)
            else None
        )
        if archive_warning:
            payload["completed_todo_archive_warning"] = archive_warning
        replan_obligation = (
            item.get("autonomous_replan_obligation")
            if isinstance(item.get("autonomous_replan_obligation"), dict)
            else project_asset.get("autonomous_replan_obligation")
            if isinstance(project_asset.get("autonomous_replan_obligation"), dict)
            else None
        )
        if replan_obligation:
            payload["autonomous_replan_obligation"] = replan_obligation
        dreaming_proposal = (
            item.get("dreaming_proposal")
            if isinstance(item.get("dreaming_proposal"), dict)
            else project_asset.get("dreaming_proposal")
            if isinstance(project_asset.get("dreaming_proposal"), dict)
            else None
        )
        if dreaming_proposal:
            payload["dreaming_proposal"] = dreaming_proposal
        dreaming_lane_badge = (
            item.get("dreaming_lane_badge")
            if isinstance(item.get("dreaming_lane_badge"), dict)
            else project_asset.get("dreaming_lane_badge")
            if isinstance(project_asset.get("dreaming_lane_badge"), dict)
            else None
        )
        if dreaming_lane_badge:
            payload["dreaming_lane_badge"] = dreaming_lane_badge
        interface_budget_cadence = (
            project_asset.get("interface_budget_cadence")
            if isinstance(project_asset.get("interface_budget_cadence"), dict)
            else None
        )
        if interface_budget_cadence:
            payload["interface_budget_cadence"] = interface_budget_cadence
        decision_warning = _decision_freshness_warning(status_payload, goal_id=safe_goal_id)
        if decision_warning:
            payload["decision_freshness_warning"] = decision_warning
        promotion_warning = _promotion_readiness_warning(status_payload)
        if promotion_warning:
            payload["promotion_readiness_warning"] = promotion_warning
        reward_lesson_warning = _reward_lesson_projection_warning(
            status_payload,
            goal_id=safe_goal_id,
            recommended_action=selected_recommended_action,
        )
        if reward_lesson_warning:
            payload["reward_lesson_projection_warning"] = reward_lesson_warning
        gate_prompt = (
            _build_gate_prompt(item, user_todo_summary=user_todo_summary)
            if state == "operator_gate"
            else None
        )
        if gate_prompt:
            payload["gate_prompt"] = gate_prompt
            payload["notify_user_on_gate"] = True
        if item.get("next_handoff_condition"):
            payload["next_handoff_condition"] = item.get("next_handoff_condition")
        if should_run and item.get("agent_command"):
            payload["agent_command"] = item.get("agent_command")
        payload["automation_liveness"] = _automation_liveness(payload)
        payload["interaction_contract"] = _interaction_contract(payload)
        payload["scheduler_hint"] = _scheduler_hint(payload, include_detail=include_scheduler_detail)
        payload["protocol_action_packet"] = _protocol_action_packet(payload)
        return payload

    if health_item:
        return {
            "ok": False,
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": "skip",
            "should_run": False,
            "reason": str(health_item.get("recommended_action") or "health item blocks automatic compute"),
            "state": "blocked_health",
            "waiting_on": health_item.get("waiting_on"),
            "status": health_item.get("status"),
            "source": health_item.get("source"),
            "recommended_action": health_item.get("recommended_action"),
            "plan_summary": plan.get("summary"),
        }

    return {
        "ok": False,
        "mode": "should-run",
        "goal_id": safe_goal_id,
        "decision": "skip",
        "should_run": False,
        "reason": "goal is not present in the registered quota plan",
        "state": "unknown",
        "waiting_on": None,
        "status": "goal_not_found",
        "source": "quota",
        "recommended_action": "run `loopx registry` and connect or sync the goal before spending compute",
        "plan_summary": plan.get("summary"),
    }


def _queue_item_for_goal(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any]:
    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    return next(
        (
            item
            for item in queue_items
            if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id
        ),
        {},
    )


def _set_quota_for_goal(status_payload: dict[str, Any], *, goal_id: str, quota: dict[str, Any]) -> None:
    run_history = status_payload.get("run_history") if isinstance(status_payload.get("run_history"), dict) else {}
    run_goals = run_history.get("goals") if isinstance(run_history.get("goals"), list) else []
    for goal in run_goals:
        if isinstance(goal, dict) and str(goal.get("id") or "") == goal_id:
            goal["quota"] = dict(quota)

    queue = status_payload.get("attention_queue") if isinstance(status_payload.get("attention_queue"), dict) else {}
    queue_items = queue.get("items") if isinstance(queue.get("items"), list) else []
    for item in queue_items:
        if isinstance(item, dict) and str(item.get("goal_id") or "") == goal_id:
            item["quota"] = dict(quota)
            project_asset = item.get("project_asset") if isinstance(item.get("project_asset"), dict) else {}
            if project_asset:
                project_asset["quota"] = dict(quota)


def build_quota_slot_preview(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
    agent_id: str | None = None,
    available_capabilities: Any = None,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    safe_slots = max(1, _int_number(slots, default=1))
    before = build_quota_should_run(
        status_payload,
        goal_id=safe_goal_id,
        agent_id=agent_id,
        available_capabilities=available_capabilities,
    )
    safe_bypass_spend = (
        (
            before.get("state") == "operator_gate"
            or before.get("recovery_delivery_allowed") is True
            or before.get("effective_action") == "outcome_floor_recovery"
        )
        and before.get("safe_bypass_allowed") is True
    )
    self_repair_spend = before.get("effective_action") in SELF_REPAIR_SPEND_ACTIONS
    capability_repair_spend = (
        before.get("effective_action") == "capability_bridge_repair"
        and before.get("capability_repair_allowed") is True
    )
    workspace_repair_no_spend = (
        before.get("effective_action") == "side_agent_workspace_repair"
        and before.get("workspace_repair_allowed") is True
    )
    if workspace_repair_no_spend:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "appended": False,
            "registry_mutated": False,
            "reason": (
                "side-agent workspace guard requires moving to an independent "
                "worktree and rerunning quota should-run before quota spend"
            ),
            "before": before,
            "after": None,
        }
    raw_runtime_root = status_payload.get("runtime_root")
    delivery_completion_run = (
        _latest_unspent_accountable_delivery_run(Path(str(raw_runtime_root)).expanduser(), safe_goal_id)
        if raw_runtime_root
        else None
    )
    delivery_completion_spend = (
        delivery_completion_run is not None
        and before.get("ok")
        and (
            not before.get("should_run")
            or before.get("effective_action") == "external_evidence_observe"
        )
        and not safe_bypass_spend
        and str(before.get("state") or "") in {"waiting", "focus_wait", "operator_gate", "eligible"}
    )
    if not before.get("ok") or (
        not before.get("should_run")
        and not safe_bypass_spend
        and not capability_repair_spend
        and not delivery_completion_spend
    ):
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "appended": False,
            "registry_mutated": False,
            "reason": before.get("reason") or "goal is not eligible for quota accounting preview",
            "before": before,
            "after": None,
        }

    before_quota = before.get("quota") if isinstance(before.get("quota"), dict) else {}
    if not before_quota:
        return {
            "ok": False,
            "mode": "spend-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "slots": safe_slots,
            "appended": False,
            "registry_mutated": False,
            "reason": "goal has no quota payload to preview",
            "before": before,
            "after": None,
        }

    queue_item = _queue_item_for_goal(status_payload, goal_id=safe_goal_id)
    after_status = deepcopy(status_payload)
    after_goal = {
        "quota": {
            **before_quota,
            "spent_slots": _int_number(before_quota.get("spent_slots"), default=0) + safe_slots,
        }
    }
    after_quota = quota_status(
        after_goal,
        waiting_on=str(before.get("waiting_on") or ""),
        severity=str(queue_item.get("severity") or ""),
        lifecycle_phase=before.get("lifecycle_phase") or queue_item.get("lifecycle_phase"),
        lifecycle_flags=before.get("lifecycle_flags") or queue_item.get("lifecycle_flags"),
        status=before.get("status") or queue_item.get("status"),
    )
    _set_quota_for_goal(after_status, goal_id=safe_goal_id, quota=after_quota)
    after = build_quota_should_run(
        after_status,
        goal_id=safe_goal_id,
        agent_id=agent_id,
        available_capabilities=available_capabilities,
    )

    return {
        "ok": True,
        "mode": "spend-slot",
        "dry_run": True,
        "goal_id": safe_goal_id,
        "slots": safe_slots,
        "appended": False,
        "registry_mutated": False,
        "before": before,
        "after": after,
        "would_throttle": after.get("state") == "throttled",
        "reason": (
            f"dry-run preview: spending {safe_slots} slot(s) accounts for latest "
            f"validated delivery {delivery_completion_run.get('classification')} "
            f"after current {before.get('state')} guard"
            if delivery_completion_spend and delivery_completion_run
            else (
                f"dry-run preview: spending {safe_slots} slot(s) would move "
                f"{safe_goal_id} from {before.get('state')} to {after.get('state')}"
            )
        ),
        "rolling_window_note": (
            "before -> after is a same-status-payload projection. Later quota status "
            "recomputes spent_slots from quota_slot_spent events still inside window_hours, "
            "so the visible total can stay flat if an older spend expires."
        ),
        "safe_bypass_spend": safe_bypass_spend,
        "self_repair_spend": self_repair_spend,
        "capability_repair_spend": capability_repair_spend,
        "delivery_completion_spend": delivery_completion_spend,
        "delivery_run_generated_at": delivery_completion_run.get("generated_at")
        if delivery_completion_run
        else None,
        "delivery_run_classification": delivery_completion_run.get("classification")
        if delivery_completion_run
        else None,
    }


def _compact_quota_decision(decision: dict[str, Any]) -> dict[str, Any]:
    quota = decision.get("quota") if isinstance(decision.get("quota"), dict) else {}
    return {
        "should_run": bool(decision.get("should_run")),
        "normal_delivery_allowed": bool(decision.get("normal_delivery_allowed")),
        "recovery_delivery_allowed": bool(decision.get("recovery_delivery_allowed")),
        "effective_action": decision.get("effective_action"),
        "self_repair_allowed": bool(decision.get("self_repair_allowed")),
        "capability_repair_allowed": bool(decision.get("capability_repair_allowed")),
        "workspace_repair_allowed": bool(decision.get("workspace_repair_allowed")),
        "state": str(decision.get("state") or ""),
        "safe_bypass_allowed": bool(decision.get("safe_bypass_allowed")),
        "safe_bypass_kind": decision.get("safe_bypass_kind"),
        "blocked_action_scope": decision.get("blocked_action_scope"),
        "compute": quota.get("compute"),
        "window_hours": quota.get("window_hours"),
        "slot_minutes": quota.get("slot_minutes"),
        "spent_slots": quota.get("spent_slots"),
        "allowed_slots": quota.get("allowed_slots"),
    }


def _quota_decision_agent_id(decision: dict[str, Any]) -> str | None:
    agent_identity = (
        decision.get("agent_identity")
        if isinstance(decision.get("agent_identity"), dict)
        else {}
    )
    return normalize_todo_claimed_by(agent_identity.get("agent_id"))


def _monitor_target_summary(value: Any, *, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _quota_monitor_target(before: dict[str, Any], *, monitor_mode: str) -> dict[str, Any]:
    action_summary = _monitor_target_summary(
        before.get("recommended_action") or before.get("reason") or "",
        limit=160,
    )
    agent_id = _quota_decision_agent_id(before) or ""
    parts = {
        "goal_id": str(before.get("goal_id") or ""),
        "agent_id": agent_id,
        "monitor_mode": str(monitor_mode or ""),
        "effective_action": str(before.get("effective_action") or ""),
        "action_summary": action_summary,
    }
    target_id = hashlib.sha256(
        json.dumps(parts, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    target: dict[str, Any] = {
        "schema_version": QUOTA_MONITOR_TARGET_SCHEMA_VERSION,
        "target_id": target_id,
        "monitor_mode": parts["monitor_mode"],
        "effective_action": parts["effective_action"],
        "action_summary": action_summary,
    }
    if agent_id:
        target["agent_id"] = agent_id
    return target


def _work_lane_reason_codes(work_lane_contract: dict[str, Any]) -> set[str]:
    reason_codes = work_lane_contract.get("reason_codes")
    if not isinstance(reason_codes, list):
        return set()
    return {str(value) for value in reason_codes if str(value or "").strip()}


def _allows_no_spend_external_monitor_poll(decision: dict[str, Any]) -> bool:
    """Return True when should-run represents observation, not delivery completion."""

    work_lane_contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    reason_codes = _work_lane_reason_codes(work_lane_contract)
    monitor_policy = str(work_lane_contract.get("monitor_policy") or "")
    if decision.get("requires_user_action") is True:
        return False
    if decision.get("should_run") is not True:
        return False
    if work_lane_contract.get("must_attempt_work") is not True:
        return False
    if monitor_policy not in {
        "material_transition_only",
        "read_only_observation_then_no_spend_if_unchanged",
    }:
        return False
    if reason_codes.intersection({"external_monitor_context", "external_evidence_poll_signal"}):
        return True
    return bool(decision.get("external_evidence_observation"))


MONITOR_CADENCE_PATTERN = re.compile(
    r"^\s*(?P<count>[1-9][0-9]{0,4})\s*"
    r"(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.IGNORECASE,
)


def _parse_monitor_counter(value: Any) -> int:
    try:
        return max(0, int(str(value or "0").strip()))
    except ValueError:
        return 0


def _monitor_cadence_delta(value: Any) -> timedelta | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    match = MONITOR_CADENCE_PATTERN.match(candidate)
    if not match:
        return None
    count = int(match.group("count"))
    unit = match.group("unit").lower()
    if unit.startswith("s"):
        return timedelta(seconds=count)
    if unit.startswith("m"):
        return timedelta(minutes=count)
    if unit.startswith("h"):
        return timedelta(hours=count)
    return timedelta(days=count)


def _monitor_next_due_at(
    *,
    generated_at: str,
    cadence: Any = None,
    explicit_next_due_at: Any = None,
) -> str | None:
    explicit = str(explicit_next_due_at or "").strip()
    if explicit:
        if _parse_timestamp(explicit) is None:
            raise ValueError("--next-due-at must be an ISO timestamp")
        return explicit
    delta = _monitor_cadence_delta(cadence)
    if delta is None:
        return None
    checked_at = _parse_timestamp(generated_at)
    if checked_at is None:
        checked_at = datetime.now(timezone.utc)
    return (checked_at + delta).astimezone().replace(microsecond=0).isoformat()


def _quota_decision_due_monitor_item(decision: dict[str, Any]) -> dict[str, Any]:
    item = (
        decision.get("agent_lane_next_action")
        if isinstance(decision.get("agent_lane_next_action"), dict)
        else {}
    )
    if _todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
        item = {}
    if item:
        return item
    contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    selected_todo_id = normalize_todo_id(contract.get("selected_todo_id"))
    due_items = contract.get("monitor_due_items") if isinstance(contract.get("monitor_due_items"), list) else []
    for due_item in due_items:
        if not isinstance(due_item, dict):
            continue
        if selected_todo_id and normalize_todo_id(due_item.get("todo_id")) != selected_todo_id:
            continue
        if _todo_task_class(due_item) == TODO_TASK_CLASS_MONITOR:
            return due_item
    return item


def _allows_due_monitor_poll(
    decision: dict[str, Any],
    *,
    todo_id: str | None = None,
    target_key: str | None = None,
) -> bool:
    contract = (
        decision.get("work_lane_contract")
        if isinstance(decision.get("work_lane_contract"), dict)
        else {}
    )
    if contract.get("obligation") != "attempt_due_monitor":
        return False
    if contract.get("must_attempt_work") is not True:
        return False
    item = _quota_decision_due_monitor_item(decision)
    if not item:
        return False
    if todo_id and normalize_todo_id(item.get("todo_id")) != normalize_todo_id(todo_id):
        return False
    if target_key:
        item_target_key = str(item.get("target_key") or "").strip()
        if item_target_key != str(target_key).strip():
            return False
    return True


def _resolve_monitor_todo_item(
    *,
    registry_path: Path,
    goal_id: str,
    todo_id: str | None = None,
    target_key: str | None = None,
) -> dict[str, Any]:
    from .todos import list_goal_todos

    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    safe_target_key = str(target_key or "").strip()
    if not normalized_todo_id and not safe_target_key:
        raise ValueError("monitor todo writeback requires --todo-id or --target-key")
    payload = list_goal_todos(registry_path=registry_path, goal_id=goal_id, role="agent")
    matches: list[dict[str, Any]] = []
    for item in payload.get("todos") if isinstance(payload.get("todos"), list) else []:
        if not isinstance(item, dict):
            continue
        if normalized_todo_id and normalize_todo_id(item.get("todo_id")) == normalized_todo_id:
            matches.append(item)
            continue
        if safe_target_key and str(item.get("target_key") or "").strip() == safe_target_key:
            matches.append(item)
    if not matches:
        target = normalized_todo_id or safe_target_key
        raise ValueError(f"monitor todo target {target!r} was not found")
    if len(matches) > 1:
        raise ValueError(f"monitor target_key {safe_target_key!r} matched multiple todos; pass --todo-id")
    item = matches[0]
    if _todo_task_class(item) != TODO_TASK_CLASS_MONITOR:
        raise ValueError("monitor-poll todo writeback target must be task_class=continuous_monitor")
    return item


def _write_monitor_poll_todo_state(
    *,
    registry_path: Path,
    goal_id: str,
    generated_at: str,
    execute: bool,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    cadence: str | None = None,
    next_due_at: str | None = None,
    reason_summary: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any] | None:
    from .todos import add_goal_todo, update_goal_todo

    if not todo_id and not target_key:
        return None
    safe_result_hash = str(result_hash or "").strip()
    if not safe_result_hash:
        raise ValueError("monitor todo writeback requires --result-hash")
    item = _resolve_monitor_todo_item(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=todo_id,
        target_key=target_key,
    )
    resolved_todo_id = normalize_todo_id(item.get("todo_id"))
    if not resolved_todo_id:
        raise ValueError("resolved monitor todo has no stable todo_id")
    safe_target_key = str(target_key or item.get("target_key") or "").strip()
    effective_cadence = str(cadence or item.get("cadence") or "").strip()
    effective_next_due_at = _monitor_next_due_at(
        generated_at=generated_at,
        cadence=effective_cadence,
        explicit_next_due_at=next_due_at,
    )
    if not material_change and not effective_next_due_at:
        raise ValueError(
            "unchanged monitor todo writeback requires --next-due-at or a parseable cadence such as 30m/2h/1d"
        )
    previous_hash = str(item.get("result_hash") or "").strip()
    previous_no_change = _parse_monitor_counter(item.get("consecutive_no_change"))
    consecutive_no_change = (
        0
        if material_change or (previous_hash and previous_hash != safe_result_hash)
        else previous_no_change + 1
    )
    monitor_metadata: dict[str, Any] = {
        "last_checked_at": generated_at,
        "result_hash": safe_result_hash,
        "consecutive_no_change": str(consecutive_no_change),
        "material_change": "true" if material_change else "false",
    }
    if safe_target_key:
        monitor_metadata["target_key"] = safe_target_key
    if effective_cadence:
        monitor_metadata["cadence"] = effective_cadence
    if effective_next_due_at:
        monitor_metadata["next_due_at"] = effective_next_due_at
    update_result = update_goal_todo(
        registry_path=registry_path,
        goal_id=goal_id,
        todo_id=resolved_todo_id,
        role="agent",
        reason=reason_summary,
        monitor_metadata=monitor_metadata,
        dry_run=not execute,
    )
    next_results: list[dict[str, Any]] = []
    if material_change and next_agent_todo:
        next_results.append(
            add_goal_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                role="agent",
                text=next_agent_todo,
                task_class=TODO_TASK_CLASS_ADVANCEMENT,
                action_kind="advance",
                claimed_by=next_claimed_by,
                unblocks_todo_id=resolved_todo_id,
                dry_run=not execute,
            )
        )
    if material_change and next_user_todo:
        next_results.append(
            add_goal_todo(
                registry_path=registry_path,
                goal_id=goal_id,
                role="user",
                text=next_user_todo,
                task_class=TODO_TASK_CLASS_USER_GATE,
                action_kind="gate",
                agent_id=agent_id,
                unblocks_todo_id=resolved_todo_id,
                dry_run=not execute,
            )
        )
    return {
        "schema_version": "monitor_poll_todo_writeback_v0",
        "dry_run": not execute,
        "goal_id": goal_id,
        "todo_id": resolved_todo_id,
        "target_key": safe_target_key or None,
        "result_hash": safe_result_hash,
        "material_change": material_change,
        "consecutive_no_change": consecutive_no_change,
        "last_checked_at": generated_at,
        "next_due_at": effective_next_due_at,
        "cadence": effective_cadence or None,
        "todo_update": update_result,
        "next_todos": next_results,
    }


def build_quota_monitor_poll_event(
    before: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    generated_at: str | None = None,
    reason_summary: str | None = None,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
) -> dict[str, Any]:
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota monitor-poll source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    external_monitor_poll = _allows_no_spend_external_monitor_poll(before)
    due_monitor_poll = _allows_due_monitor_poll(
        before,
        todo_id=todo_id,
        target_key=target_key,
    )
    if before.get("effective_action") != "monitor_quiet_skip" and not external_monitor_poll and not due_monitor_poll:
        raise ValueError(
            "quota monitor-poll requires a monitor_quiet_skip, due monitor todo, or external monitor observation decision"
        )
    recommendation = (
        before.get("heartbeat_recommendation")
        if isinstance(before.get("heartbeat_recommendation"), dict)
        else {}
    )
    if (
        recommendation.get("recommended_mode") != "monitor_quiet_until_material_transition"
        and not external_monitor_poll
        and not due_monitor_poll
    ):
        raise ValueError("quota monitor-poll requires monitor_quiet_until_material_transition mode")
    monitor_mode = (
        "external_monitor_observed_without_material_transition"
        if external_monitor_poll
        else (
            "due_monitor_material_transition"
            if due_monitor_poll and material_change
            else (
                "due_monitor_observed_without_material_transition"
                if due_monitor_poll
                else "monitor_quiet_until_material_transition"
            )
        )
    )
    monitor_target = _quota_monitor_target(before, monitor_mode=monitor_mode)
    safe_reason_summary = str(reason_summary or "").strip()
    if not safe_reason_summary:
        safe_reason_summary = (
            "external monitor observation produced no material transition"
            if external_monitor_poll
            else recommendation.get("reason")
            or before.get("reason")
            or "monitor-only poll had no material transition"
        )
    safe_agent_id = _quota_decision_agent_id(before)

    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": before.get("goal_id"),
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "recommended_action": before.get("recommended_action") or recommendation.get("reason") or before.get("reason"),
        "health_check": (
            "due monitor material transition observed; follow-up state updated; no quota spend by monitor-poll"
            if due_monitor_poll and material_change
            else (
                "due monitor observation unchanged; no quota spend; next due updated"
                if due_monitor_poll
                else (
                    "external monitor observation unchanged; no quota spend; no material transition"
            if external_monitor_poll
            else "monitor-only poll unchanged; no quota spend; no material transition"
                )
            )
        ),
        "delivery_outcome": (
            DeliveryOutcome.OUTCOME_PROGRESS.value
            if due_monitor_poll and material_change
            else DeliveryOutcome.SURFACE_ONLY.value
        ),
        "monitor_target": monitor_target,
        "monitor_event": {
            "event_type": QUOTA_MONITOR_POLL_CLASSIFICATION,
            "source": safe_source,
            "monitor_mode": monitor_mode,
            "monitor_target": monitor_target,
            "reason_summary": safe_reason_summary,
            "material_change": material_change,
            "todo_id": normalize_todo_id(todo_id) if todo_id else None,
            "target_key": str(target_key or "").strip() or None,
            "result_hash": str(result_hash or "").strip() or None,
            "before": _compact_quota_decision(before),
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["monitor_event"]["agent_id"] = safe_agent_id
    return record


def build_quota_slot_spend_event(
    preview: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not preview.get("ok"):
        raise ValueError(preview.get("reason") or "quota slot spend requires an eligible preview")
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota slot spend source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    before = preview.get("before") if isinstance(preview.get("before"), dict) else {}
    after = preview.get("after") if isinstance(preview.get("after"), dict) else {}
    safe_agent_id = _quota_decision_agent_id(before)
    slots = max(1, _int_number(preview.get("slots"), default=1))
    before_compact = _compact_quota_decision(before)
    after_compact = _compact_quota_decision(after)
    if _int_number(after_compact.get("spent_slots"), default=0) != _int_number(
        before_compact.get("spent_slots"), default=0
    ) + slots:
        raise ValueError("after.spent_slots must equal before.spent_slots + slots")
    self_repair_spend = (
        before_compact["should_run"] is True
        and before_compact["effective_action"] in SELF_REPAIR_SPEND_ACTIONS
        and before_compact["self_repair_allowed"] is True
    )
    capability_repair_spend = (
        before_compact["should_run"] is True
        and before_compact["effective_action"] == "capability_bridge_repair"
        and before_compact["capability_repair_allowed"] is True
    )
    delivery_completion_spend = bool(preview.get("delivery_completion_spend"))
    eligible_spend = (
        before_compact["should_run"] is True
        and before_compact["state"] == "eligible"
        and before_compact["effective_action"] != "external_evidence_observe"
        and not self_repair_spend
        and not capability_repair_spend
        and before_compact["workspace_repair_allowed"] is not True
    )
    safe_bypass_spend = (
        (
            before_compact["state"] == "operator_gate"
            or before_compact["recovery_delivery_allowed"] is True
            or before_compact["effective_action"] == "outcome_floor_recovery"
        )
        and before_compact["safe_bypass_allowed"] is True
    )
    if (
        not eligible_spend
        and not safe_bypass_spend
        and not self_repair_spend
        and not capability_repair_spend
        and not delivery_completion_spend
    ):
        raise ValueError(
            "quota slot spend requires an eligible, safe-bypass, control-plane self-repair, "
            "capability bridge repair, or latest validated delivery-completion quota should-run decision"
        )

    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": preview.get("goal_id"),
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "recommended_action": after.get("recommended_action") or "inspect next quota should-run decision",
        "health_check": (
            "quota should-run eligible; quota slot spend event public-safe"
            if eligible_spend
            else (
                "quota outcome-floor recovery safe-bypass; quota slot spend event public-safe"
                if before_compact.get("effective_action") == "outcome_floor_recovery"
                else (
                    "quota control-plane self-repair; quota slot spend event public-safe"
                    if self_repair_spend
                    else (
                        "quota capability bridge repair; quota slot spend event public-safe"
                        if capability_repair_spend
                        else (
                            "quota validated delivery completion; quota slot spend event public-safe"
                            if delivery_completion_spend
                            else "quota safe-bypass operator gate; quota slot spend event public-safe"
                        )
                    )
                )
            )
        ),
        "quota_event": {
            "event_type": QUOTA_SLOT_SPENT_CLASSIFICATION,
            "source": safe_source,
            "slots": slots,
            "reason_summary": (
                f"{slots} automatic agent slot(s) completed under an eligible quota guard"
                if eligible_spend
                else (
                    f"{slots} automatic agent slot(s) completed as outcome-floor recovery safe-bypass work"
                    if before_compact.get("effective_action") == "outcome_floor_recovery"
                    else (
                        f"{slots} automatic agent slot(s) completed as control-plane self-repair work"
                        if self_repair_spend
                        else (
                            f"{slots} automatic agent slot(s) completed as capability bridge repair work"
                            if capability_repair_spend
                            else (
                                f"{slots} automatic agent slot(s) accounted after validated delivery "
                                f"{preview.get('delivery_run_classification')}"
                                if delivery_completion_spend
                                else f"{slots} automatic agent slot(s) completed as safe-bypass work under an operator gate"
                            )
                        )
                    )
                )
            ),
            "delivery_run_generated_at": preview.get("delivery_run_generated_at")
            if delivery_completion_spend
            else None,
            "delivery_run_classification": preview.get("delivery_run_classification")
            if delivery_completion_spend
            else None,
            "before": before_compact,
            "after": after_compact,
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["quota_event"]["agent_id"] = safe_agent_id
    return record


def _load_goal_run_index_records(runtime_root: Path, goal_id: str) -> list[dict[str, Any]]:
    index_path = runtime_root / "goals" / goal_id / "runs" / "index.jsonl"
    if not index_path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _latest_unspent_accountable_delivery_run(runtime_root: Path, goal_id: str) -> dict[str, Any] | None:
    """Return the latest run only when it is a delivery that still needs accounting."""

    for run in reversed(_load_goal_run_index_records(runtime_root, goal_id)):
        classification = str(run.get("classification") or "").strip()
        if classification == QUOTA_SLOT_VOIDED_CLASSIFICATION:
            continue
        if classification == QUOTA_SLOT_SPENT_CLASSIFICATION:
            return None
        if classification == QUOTA_MONITOR_POLL_CLASSIFICATION:
            return None
        delivery_outcome = normalize_delivery_outcome(run.get("delivery_outcome"))
        if delivery_outcome in ACCOUNTABLE_DELIVERY_OUTCOMES:
            return run
        return None
    return None


def record_quota_monitor_poll(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    registry_path: Path | None = None,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    agent_id: str | None = None,
    todo_id: str | None = None,
    target_key: str | None = None,
    result_hash: str | None = None,
    material_change: bool = False,
    cadence: str | None = None,
    next_due_at: str | None = None,
    next_agent_todo: str | None = None,
    next_user_todo: str | None = None,
    next_claimed_by: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    before = build_quota_should_run(status_payload, goal_id=safe_goal_id, agent_id=agent_id)
    normalized_todo_id = normalize_todo_id(todo_id) if todo_id else None
    safe_target_key = str(target_key or "").strip() or None
    safe_result_hash = str(result_hash or "").strip() or None

    def failure(reason: str) -> dict[str, Any]:
        return {
            "ok": False,
            "mode": "monitor-poll",
            "dry_run": not execute,
            "goal_id": safe_goal_id,
            "appended": False,
            "registry_mutated": False,
            "source": str(source or DEFAULT_SLOT_SPEND_SOURCE).strip() or DEFAULT_SLOT_SPEND_SOURCE,
            "agent_id": normalize_todo_claimed_by(agent_id),
            "todo_id": normalized_todo_id,
            "target_key": safe_target_key,
            "result_hash": safe_result_hash,
            "material_change": material_change,
            "reason": reason,
            "before": before,
            "after": None,
        }

    if material_change and not (normalized_todo_id or safe_target_key):
        return failure("`quota monitor-poll --material-change` requires --todo-id or --target-key")
    if (next_agent_todo or next_user_todo) and not material_change:
        return failure("`--next-agent-todo` and `--next-user-todo` require --material-change")
    due_monitor_poll = _allows_due_monitor_poll(
        before,
        todo_id=normalized_todo_id,
        target_key=safe_target_key,
    )
    if (
        before.get("effective_action") != "monitor_quiet_skip"
        and not _allows_no_spend_external_monitor_poll(before)
        and not due_monitor_poll
    ):
        return failure(
            "monitor-poll requires monitor_quiet_skip, due monitor todo, "
            "or external monitor observation"
        )

    generated_at = _now_local()
    todo_writeback = None
    if normalized_todo_id or safe_target_key:
        if registry_path is None:
            raise ValueError("monitor todo writeback requires registry_path")
        todo_writeback = _write_monitor_poll_todo_state(
            registry_path=registry_path,
            goal_id=safe_goal_id,
            generated_at=generated_at,
            execute=execute,
            todo_id=normalized_todo_id,
            target_key=safe_target_key,
            result_hash=result_hash,
            material_change=material_change,
            cadence=cadence,
            next_due_at=next_due_at,
            reason_summary=reason_summary,
            next_agent_todo=next_agent_todo,
            next_user_todo=next_user_todo,
            next_claimed_by=next_claimed_by,
            agent_id=agent_id,
        )
    record = build_quota_monitor_poll_event(
        before,
        source=source,
        generated_at=generated_at,
        reason_summary=reason_summary,
        todo_id=(todo_writeback or {}).get("todo_id") or normalized_todo_id,
        target_key=(todo_writeback or {}).get("target_key") or safe_target_key,
        result_hash=(todo_writeback or {}).get("result_hash") or result_hash,
        material_change=material_change,
    )
    if todo_writeback:
        record["monitor_event"]["todo_writeback"] = {
            key: value
            for key, value in todo_writeback.items()
            if key
            in {
                "schema_version",
                "dry_run",
                "goal_id",
                "todo_id",
                "target_key",
                "result_hash",
                "material_change",
                "consecutive_no_change",
                "last_checked_at",
                "next_due_at",
                "cadence",
            }
        }
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = _run_file_stem(generated_at)
    json_path, markdown_path = _unique_run_artifact_paths(runs_dir, stem, "quota-monitor-poll")
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "delivery_outcome": record["delivery_outcome"],
        "monitor_target": record["monitor_target"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]
    if record["monitor_event"].get("todo_id"):
        index_record["todo_id"] = record["monitor_event"]["todo_id"]
    if record["monitor_event"].get("target_key"):
        index_record["target_key"] = record["monitor_event"]["target_key"]
    if record["monitor_event"].get("material_change"):
        index_record["material_change"] = record["monitor_event"]["material_change"]

    after_status = deepcopy(status_payload)
    if execute:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_quota_monitor_poll_markdown(record) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
        run_history = after_status.get("run_history") if isinstance(after_status.get("run_history"), dict) else {}
        for goal in run_history.get("goals") if isinstance(run_history.get("goals"), list) else []:
            if isinstance(goal, dict) and str(goal.get("id") or "") == safe_goal_id:
                latest_runs = goal.get("latest_runs") if isinstance(goal.get("latest_runs"), list) else []
                goal["latest_runs"] = [index_record, *latest_runs]
                runs = goal.get("runs") if isinstance(goal.get("runs"), list) else []
                goal["runs"] = [index_record, *runs]
        recent_runs = run_history.get("recent_runs") if isinstance(run_history.get("recent_runs"), list) else []
        run_history["recent_runs"] = [index_record, *recent_runs]

    after = build_quota_should_run(after_status, goal_id=safe_goal_id, agent_id=agent_id)
    return {
        "ok": True,
        "mode": "monitor-poll",
        "dry_run": not execute,
        "goal_id": safe_goal_id,
        "appended": execute,
        "registry_mutated": False,
        "source": record["monitor_event"]["source"],
        "classification": QUOTA_MONITOR_POLL_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "todo_id": record["monitor_event"].get("todo_id"),
        "target_key": record["monitor_event"].get("target_key"),
        "material_change": record["monitor_event"].get("material_change"),
        "monitor_event": record["monitor_event"],
        "todo_writeback": todo_writeback,
        "health_check": record["health_check"],
        "delivery_outcome": record["delivery_outcome"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "before": before,
        "after": after,
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} monitor poll event: "
            f"{safe_goal_id} effective_action={before.get('effective_action')}"
        ),
    }


def _find_quota_spend_run(
    runtime_root: Path,
    *,
    goal_id: str,
    generated_at: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    for run in reversed(_load_goal_run_index_records(runtime_root, goal_id)):
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        if str(run.get("generated_at") or "") != generated_at:
            continue
        if str(run.get("classification") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
            continue
        event = _load_quota_event_from_run(run)
        if not event or str(event.get("event_type") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
            continue
        return run, event
    return None


def build_quota_slot_void_preview(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    voided_run_generated_at: str,
    agent_id: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    safe_voided_at = str(voided_run_generated_at or "").strip()
    if not safe_voided_at:
        return {
            "ok": False,
            "mode": "void-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "appended": False,
            "registry_mutated": False,
            "reason": "`quota void-slot` requires --void-generated-at",
        }

    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    target = _find_quota_spend_run(runtime_root, goal_id=safe_goal_id, generated_at=safe_voided_at)
    if target is None:
        return {
            "ok": False,
            "mode": "void-slot",
            "dry_run": True,
            "goal_id": safe_goal_id,
            "voided_run_generated_at": safe_voided_at,
            "appended": False,
            "registry_mutated": False,
            "reason": "target quota_slot_spent run was not found in the goal runtime index",
        }
    target_run, target_event = target
    slots = max(1, _int_number(target_event.get("slots"), default=1))
    before = build_quota_should_run(status_payload, goal_id=safe_goal_id, agent_id=agent_id)
    before_quota = before.get("quota") if isinstance(before.get("quota"), dict) else {}
    after = deepcopy(before)
    after_quota = deepcopy(before_quota)
    after_quota["spent_slots"] = max(0, _int_number(before_quota.get("spent_slots"), default=0) - slots)
    after["quota"] = after_quota
    return {
        "ok": True,
        "mode": "void-slot",
        "dry_run": True,
        "goal_id": safe_goal_id,
        "slots": slots,
        "voided_run_generated_at": safe_voided_at,
        "voided_run_classification": target_run.get("classification"),
        "voided_run_json_path": target_run.get("json_path"),
        "appended": False,
        "registry_mutated": False,
        "before": before,
        "after": after,
        "would_throttle": False,
        "reason": (
            f"dry-run preview: voiding {slots} slot(s) from {safe_goal_id} "
            f"quota spend run {safe_voided_at}"
        ),
        "rolling_window_note": (
            "quota void-slot appends a quota_slot_voided accounting event. It does not delete the "
            "original spend event; rolling-window ledgers subtract the void only when the target "
            "spend event is inside the same accounting window."
        ),
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
    }


def build_quota_slot_void_event(
    preview: dict[str, Any],
    *,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if not preview.get("ok"):
        raise ValueError(preview.get("reason") or "quota slot void requires a valid preview")
    safe_source = str(source or DEFAULT_SLOT_SPEND_SOURCE).strip()
    if safe_source not in VALID_SLOT_SPEND_SOURCES:
        raise ValueError(f"quota slot void source must be one of: {', '.join(sorted(VALID_SLOT_SPEND_SOURCES))}")
    safe_reason = str(reason_summary or "").strip() or "void duplicate or invalid quota slot spend event"
    before = preview.get("before") if isinstance(preview.get("before"), dict) else {}
    after = preview.get("after") if isinstance(preview.get("after"), dict) else {}
    safe_agent_id = _quota_decision_agent_id(before)
    record = {
        "generated_at": generated_at or _now_local(),
        "goal_id": preview.get("goal_id"),
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "recommended_action": safe_reason,
        "health_check": "quota slot void event public-safe; original spend preserved for audit",
        "quota_event": {
            "event_type": QUOTA_SLOT_VOIDED_CLASSIFICATION,
            "source": safe_source,
            "slots": max(1, _int_number(preview.get("slots"), default=1)),
            "reason_summary": safe_reason,
            "voided_run_generated_at": preview.get("voided_run_generated_at"),
            "voided_run_classification": preview.get("voided_run_classification"),
            "before": _compact_quota_decision(before) if before else {},
            "after": _compact_quota_decision(after) if after else {},
        },
    }
    if safe_agent_id:
        record["agent_id"] = safe_agent_id
        record["quota_event"]["agent_id"] = safe_agent_id
    return record


def void_quota_slot(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    voided_run_generated_at: str,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    reason_summary: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    preview = build_quota_slot_void_preview(
        status_payload,
        goal_id=safe_goal_id,
        voided_run_generated_at=voided_run_generated_at,
        agent_id=agent_id,
    )
    if not preview.get("ok"):
        return preview

    generated_at = _now_local()
    record = build_quota_slot_void_event(
        preview,
        source=source,
        reason_summary=reason_summary,
        generated_at=generated_at,
    )
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = _run_file_stem(generated_at)
    json_path, markdown_path = _unique_run_artifact_paths(runs_dir, stem, "quota-slot-voided")
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]
    payload = {
        **preview,
        "dry_run": not execute,
        "appended": execute,
        "registry_mutated": False,
        "source": record["quota_event"]["source"],
        "classification": QUOTA_SLOT_VOIDED_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "quota_event": record["quota_event"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} quota slot void event: "
            f"{safe_goal_id} voided {record['quota_event']['slots']} slot(s) from "
            f"{record['quota_event']['voided_run_generated_at']}"
        ),
    }
    if execute:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_quota_slot_preview_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def spend_quota_slot(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
    agent_id: str | None = None,
    available_capabilities: Any = None,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    preview = build_quota_slot_preview(
        status_payload,
        goal_id=safe_goal_id,
        slots=slots,
        agent_id=agent_id,
        available_capabilities=available_capabilities,
    )
    if not preview.get("ok"):
        return preview

    generated_at = _now_local()
    record = build_quota_slot_spend_event(preview, source=source, generated_at=generated_at)
    raw_runtime_root = status_payload.get("runtime_root")
    if not raw_runtime_root:
        raise ValueError("status payload does not include runtime_root")
    runtime_root = Path(str(raw_runtime_root)).expanduser()
    runs_dir = runtime_root / "goals" / safe_goal_id / "runs"
    stem = _run_file_stem(generated_at)
    json_path, markdown_path = _unique_run_artifact_paths(runs_dir, stem, "quota-slot-spent")
    index_path = runs_dir / "index.jsonl"
    index_record = {
        "generated_at": generated_at,
        "goal_id": safe_goal_id,
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "recommended_action": record["recommended_action"],
        "health_check": record["health_check"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }
    if record.get("agent_id"):
        index_record["agent_id"] = record["agent_id"]

    payload = {
        **preview,
        "dry_run": not execute,
        "appended": execute,
        "registry_mutated": False,
        "source": record["quota_event"]["source"],
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "generated_at": generated_at,
        "agent_id": record.get("agent_id"),
        "quota_event": record["quota_event"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "index_path": str(index_path),
        "reason": (
            f"{'appended' if execute else 'dry-run preview'} quota slot spend event: "
            f"{safe_goal_id} {record['quota_event']['before']['spent_slots']}->"
            f"{record['quota_event']['after']['spent_slots']} slots"
        ),
    }
    if execute:
        runs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(render_quota_slot_preview_markdown(payload) + "\n", encoding="utf-8")
        with index_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(index_record, ensure_ascii=False) + "\n")
    return payload


def render_quota_markdown(payload: dict[str, Any]) -> str:
    title = "Quota Plan" if payload.get("mode") == "plan" else "Quota Status"
    lines = [
        f"# LoopX {title}",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- goals: `{payload.get('goal_count')}`",
        f"- runs: `{payload.get('run_count')}`",
    ]
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    states = summary.get("states") if isinstance(summary.get("states"), dict) else {}
    state_text = ", ".join(f"{state}={states.get(state, 0)}" for state in QUOTA_STATE_ORDER)
    lines.append(
        "- summary: "
        f"registered_goals={summary.get('registered_goals')}, "
        f"health_blockers={summary.get('health_blockers')}, "
        f"next_automatic_turn={summary.get('next_automatic_turn') or 'none'}"
    )
    lines.append(f"- states: {state_text}")

    next_turn = payload.get("next_automatic_turn") if isinstance(payload.get("next_automatic_turn"), dict) else {}
    lines.extend(["", "## Next Automatic Turn"])
    if next_turn:
        quota = next_turn.get("quota") if isinstance(next_turn.get("quota"), dict) else {}
        lines.append(
            "- "
            f"`{next_turn.get('goal_id')}` "
            f"compute={quota.get('compute')} "
            f"slot_minutes={quota.get('slot_minutes')} "
            f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
            f"action={next_turn.get('recommended_action') or 'inspect latest run'}"
        )
    else:
        lines.append("- none")

    health_items = payload.get("health_items") if isinstance(payload.get("health_items"), list) else []
    if health_items:
        lines.extend(["", "## Health Items"])
        for item in health_items:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- "
                f"`{item.get('goal_id')}` "
                f"severity={item.get('severity')} "
                f"waiting_on={item.get('waiting_on')} "
                f"action={item.get('recommended_action')}"
            )

    groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
    lines.extend(["", "## Groups"])
    render_states = list(QUOTA_STATE_ORDER)
    if groups.get("unknown"):
        render_states.append("unknown")
    for state in render_states:
        items = groups.get(state) if isinstance(groups.get(state), list) else []
        if payload.get("mode") == "plan" and not items:
            continue
        lines.extend(["", f"### {state}"])
        if not items:
            lines.append("- none")
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
            action = str(item.get("recommended_action") or "").replace("|", "\\|")
            lines.append(
                "- "
                f"`{item.get('goal_id')}`: "
                f"compute={quota.get('compute')} "
                f"slot_minutes={quota.get('slot_minutes')} "
                f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')} "
                f"waiting_on={item.get('waiting_on')} "
                f"status={item.get('status')} "
                f"phase={item.get('lifecycle_phase')}"
            )
            reason = quota.get("reason")
            if reason:
                lines.append(f"  - reason: {reason}")
            if action:
                lines.append(f"  - action: {action}")
            control_plane = item.get("control_plane") if isinstance(item.get("control_plane"), dict) else None
            if control_plane:
                lines.append(f"  - control_plane: {control_plane_policy_summary(control_plane)}")
            if item.get("agent_command"):
                lines.append(f"  - agent_command: `{item.get('agent_command')}`")
            if item.get("next_handoff_condition"):
                lines.append(f"  - next_handoff_condition: {item.get('next_handoff_condition')}")
    return "\n".join(lines)


def render_quota_slot_preview_markdown(payload: dict[str, Any]) -> str:
    before = payload.get("before") if isinstance(payload.get("before"), dict) else {}
    after = payload.get("after") if isinstance(payload.get("after"), dict) else {}
    before_quota = before.get("quota") if isinstance(before.get("quota"), dict) else {}
    after_quota = after.get("quota") if isinstance(after.get("quota"), dict) else {}
    lines = [
        "# LoopX Quota Slot Preview",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification') or QUOTA_SLOT_SPENT_CLASSIFICATION}`",
        f"- agent_id: `{payload.get('agent_id') or ''}`",
        f"- slots: `{payload.get('slots')}`",
        f"- appended: `{payload.get('appended')}`",
        f"- registry_mutated: `{payload.get('registry_mutated')}`",
        f"- would_throttle: `{payload.get('would_throttle')}`",
    ]
    if payload.get("json_path"):
        lines.append(f"- json_path: `{payload.get('json_path')}`")
    if payload.get("index_path"):
        lines.append(f"- index_path: `{payload.get('index_path')}`")
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    if before:
        lines.append(
            "- before: "
            f"state={before.get('state')} "
            f"should_run={before.get('should_run')} "
            f"slots={before_quota.get('spent_slots')}/{before_quota.get('allowed_slots')}"
        )
    if after:
        lines.append(
            "- after: "
            f"state={after.get('state')} "
            f"should_run={after.get('should_run')} "
            f"slots={after_quota.get('spent_slots')}/{after_quota.get('allowed_slots')}"
        )
        summary = after.get("plan_summary") if isinstance(after.get("plan_summary"), dict) else {}
        if summary:
            lines.append(f"- after_plan_next_automatic_turn: {summary.get('next_automatic_turn') or 'none'}")
    if payload.get("rolling_window_note"):
        lines.append(f"- rolling_window_note: {payload.get('rolling_window_note')}")
    return "\n".join(lines)


def render_quota_monitor_poll_markdown(payload: dict[str, Any]) -> str:
    event = payload.get("monitor_event") if isinstance(payload.get("monitor_event"), dict) else {}
    before = event.get("before") if isinstance(event.get("before"), dict) else {}
    todo_writeback = event.get("todo_writeback") if isinstance(event.get("todo_writeback"), dict) else {}
    lines = [
        "# LoopX Quota Monitor Poll",
        "",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- agent_id: `{payload.get('agent_id') or event.get('agent_id') or ''}`",
        f"- source: `{event.get('source')}`",
        f"- effective_action: `{before.get('effective_action')}`",
        f"- monitor_target: `{(event.get('monitor_target') or {}).get('target_id') if isinstance(event.get('monitor_target'), dict) else ''}`",
        f"- todo_id: `{event.get('todo_id') or ''}`",
        f"- target_key: `{event.get('target_key') or ''}`",
        f"- material_change: `{event.get('material_change')}`",
        f"- should_run: `{before.get('should_run')}`",
        f"- self_repair_allowed: `{before.get('self_repair_allowed')}`",
        f"- state: `{before.get('state')}`",
        f"- health_check: {payload.get('health_check')}",
        f"- reason: {event.get('reason_summary')}",
    ]
    if todo_writeback:
        lines.append(
            "- todo_writeback: "
            f"dry_run={todo_writeback.get('dry_run')} "
            f"consecutive_no_change={todo_writeback.get('consecutive_no_change')} "
            f"last_checked_at={todo_writeback.get('last_checked_at')} "
            f"next_due_at={todo_writeback.get('next_due_at')}"
        )
    return "\n".join(lines)


def render_quota_should_run_markdown(payload: dict[str, Any]) -> str:
    quota = payload.get("quota") if isinstance(payload.get("quota"), dict) else {}
    lines = [
        "# LoopX Quota Should Run",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- should_run: `{payload.get('should_run')}`",
        f"- normal_delivery_allowed: `{payload.get('normal_delivery_allowed')}`",
        f"- recovery_delivery_allowed: `{payload.get('recovery_delivery_allowed')}`",
        f"- self_repair_allowed: `{payload.get('self_repair_allowed')}`",
        f"- effective_action: `{payload.get('effective_action')}`",
        f"- actionable_by_codex: `{payload.get('actionable_by_codex')}`",
        f"- state: `{payload.get('state')}`",
        f"- waiting_on: `{payload.get('waiting_on')}`",
        f"- status: `{payload.get('status')}`",
    ]
    if payload.get("project_asset_source"):
        lines.append(f"- project_asset_source: {payload.get('project_asset_source')}")
    agent_identity = (
        payload.get("agent_identity")
        if isinstance(payload.get("agent_identity"), dict)
        else {}
    )
    if agent_identity:
        lines.append(
            "- agent_identity: "
            f"agent_id={agent_identity.get('agent_id')} "
            f"role={agent_identity.get('role')} "
            f"primary_agent={agent_identity.get('primary_agent')}"
        )
    if payload.get("active_state_next_action"):
        lines.append(f"- active_state_next_action: {payload.get('active_state_next_action')}")
    if payload.get("latest_run_recommended_action"):
        lines.append(
            f"- latest_run_recommended_action: {payload.get('latest_run_recommended_action')}"
        )
    agent_lane_next_action = (
        payload.get("agent_lane_next_action")
        if isinstance(payload.get("agent_lane_next_action"), dict)
        else {}
    )
    if agent_lane_next_action:
        lines.append(
            "- agent_lane_next_action: "
            f"todo_id={agent_lane_next_action.get('todo_id')} "
            f"selected_by={agent_lane_next_action.get('selected_by')} "
            f"confidence={agent_lane_next_action.get('confidence')}"
        )
        if agent_lane_next_action.get("text"):
            lines.append(f"- agent_lane_next_action_text: {agent_lane_next_action.get('text')}")
    agent_lane_frontier_hint = (
        payload.get("agent_lane_frontier_hint")
        if isinstance(payload.get("agent_lane_frontier_hint"), dict)
        else {}
    )
    if agent_lane_frontier_hint:
        lines.append(
            "- agent_lane_frontier_hint: "
            f"decision={agent_lane_frontier_hint.get('decision')} "
            f"source={agent_lane_frontier_hint.get('source')} "
            f"reason_code={agent_lane_frontier_hint.get('reason_code')} "
            f"target_todo_id={agent_lane_frontier_hint.get('target_todo_id')}"
        )
    agent_scope_frontier = (
        payload.get("agent_scope_frontier")
        if isinstance(payload.get("agent_scope_frontier"), dict)
        else {}
    )
    if agent_scope_frontier:
        lines.append(
            "- agent_scope_frontier: "
            f"action={agent_scope_frontier.get('action')} "
            f"agent_id={agent_scope_frontier.get('agent_id')} "
            f"quiet_noop_allowed={agent_scope_frontier.get('quiet_noop_allowed')}"
        )
        if agent_scope_frontier.get("reason"):
            lines.append(f"- agent_scope_frontier_reason: {agent_scope_frontier.get('reason')}")
        deferred_resume_candidates = (
            agent_scope_frontier.get("deferred_resume_candidates")
            if isinstance(agent_scope_frontier.get("deferred_resume_candidates"), list)
            else []
        )
        if deferred_resume_candidates:
            first_candidate = (
                deferred_resume_candidates[0]
                if isinstance(deferred_resume_candidates[0], dict)
                else {}
            )
            lines.append(
                "- agent_scope_deferred_resume_candidates: "
                f"`{len(deferred_resume_candidates)}` "
                f"top_todo_id={first_candidate.get('todo_id')}"
            )
    automation_prompt_upgrade = (
        payload.get("automation_prompt_upgrade")
        if isinstance(payload.get("automation_prompt_upgrade"), dict)
        else {}
    )
    if automation_prompt_upgrade:
        lines.append(
            "- automation_prompt_upgrade: "
            f"required={automation_prompt_upgrade.get('required')} "
            f"blocks_should_run={automation_prompt_upgrade.get('blocks_should_run')} "
            f"contract={automation_prompt_upgrade.get('contract')}"
        )
        if automation_prompt_upgrade.get("recommended_action"):
            lines.append(f"- automation_prompt_upgrade_action: {automation_prompt_upgrade.get('recommended_action')}")
        if automation_prompt_upgrade.get("primary_example_command"):
            lines.append(f"- automation_prompt_upgrade_primary: {automation_prompt_upgrade.get('primary_example_command')}")
        if automation_prompt_upgrade.get("side_agent_example_command"):
            lines.append(f"- automation_prompt_upgrade_side: {automation_prompt_upgrade.get('side_agent_example_command')}")
    capability_gate = (
        payload.get("capability_gate")
        if isinstance(payload.get("capability_gate"), dict)
        else {}
    )
    if capability_gate:
        lines.append(
            "- capability_gate: "
            f"action={capability_gate.get('action')} "
            f"required={capability_gate.get('required')} "
            f"missing={capability_gate.get('missing')}"
        )
        if capability_gate.get("decision_owner"):
            lines.append(f"- capability_gate_decision_owner: {capability_gate.get('decision_owner')}")
        runnable_candidates = (
            capability_gate.get("runnable_candidates")
            if isinstance(capability_gate.get("runnable_candidates"), list)
            else []
        )
        if runnable_candidates:
            lines.append(f"- capability_gate_runnable_candidates: `{len(runnable_candidates)}`")
        blocked_candidates = (
            capability_gate.get("blocked_candidates")
            if isinstance(capability_gate.get("blocked_candidates"), list)
            else []
        )
        if blocked_candidates:
            lines.append(f"- capability_gate_blocked_candidates: `{len(blocked_candidates)}`")
    workspace_guard = (
        payload.get("workspace_guard")
        if isinstance(payload.get("workspace_guard"), dict)
        else {}
    )
    if workspace_guard:
        lines.append(
            "- workspace_guard: "
            f"action={workspace_guard.get('action')} "
            f"current_workspace={workspace_guard.get('current_workspace')} "
            f"required_workspace={workspace_guard.get('required_workspace')}"
        )
        if workspace_guard.get("required_action"):
            lines.append(f"- workspace_guard_action: {workspace_guard.get('required_action')}")
    stale_latest_run_warning = (
        payload.get("stale_latest_run_warning")
        if isinstance(payload.get("stale_latest_run_warning"), dict)
        else {}
    )
    if stale_latest_run_warning:
        lines.append(
            "- stale_latest_run_warning: "
            f"requires_refresh_state={stale_latest_run_warning.get('requires_refresh_state')} "
            f"active_state_updated_at={stale_latest_run_warning.get('active_state_updated_at')} "
            f"latest_run_generated_at={stale_latest_run_warning.get('latest_run_generated_at')} "
            f"reason={stale_latest_run_warning.get('reason')}"
        )
        if stale_latest_run_warning.get("recommended_action"):
            lines.append(f"- stale_latest_run_action: {stale_latest_run_warning.get('recommended_action')}")
    state_action_projection_warning = (
        payload.get("state_action_projection_warning")
        if isinstance(payload.get("state_action_projection_warning"), dict)
        else {}
    )
    if state_action_projection_warning:
        lines.append(
            "- state_action_projection_warning: "
            f"requires_state_writeback={state_action_projection_warning.get('requires_state_writeback')} "
            f"reason={state_action_projection_warning.get('reason')}"
        )
        if state_action_projection_warning.get("selected_recommended_action"):
            lines.append(
                "- state_action_selected: "
                f"{state_action_projection_warning.get('selected_recommended_action')}"
            )
        if state_action_projection_warning.get("active_state_next_action"):
            lines.append(
                "- state_action_visible_next: "
                f"{state_action_projection_warning.get('active_state_next_action')}"
            )
        if state_action_projection_warning.get("recommended_action"):
            lines.append(
                f"- state_action_projection_action: {state_action_projection_warning.get('recommended_action')}"
            )
    next_action_projection = (
        payload.get("next_action_projection_warning")
        if isinstance(payload.get("next_action_projection_warning"), dict)
        else {}
    )
    if next_action_projection:
        lines.append(
            "- next_action_projection_warning: "
            f"requires_state_writeback={next_action_projection.get('requires_state_writeback')} "
            f"reason={next_action_projection.get('reason')}"
        )
        if next_action_projection.get("latest_run_recommended_action"):
            lines.append(
                "- latest_run_projection_action: "
                f"{next_action_projection.get('latest_run_recommended_action')}"
            )
    backlog_hygiene_warning = (
        payload.get("backlog_hygiene_warning")
        if isinstance(payload.get("backlog_hygiene_warning"), dict)
        else {}
    )
    if backlog_hygiene_warning:
        lines.append(
            "- backlog_hygiene_warning: "
            f"requires_agent_todo={backlog_hygiene_warning.get('requires_agent_todo')} "
            f"evidence_count={backlog_hygiene_warning.get('evidence_count')} "
            f"source_sections={','.join(backlog_hygiene_warning.get('source_sections') or [])}"
        )
        if backlog_hygiene_warning.get("recommended_action"):
            lines.append(f"- backlog_hygiene_action: {backlog_hygiene_warning.get('recommended_action')}")
    projection_gap = (
        payload.get("state_projection_gap")
        if isinstance(payload.get("state_projection_gap"), dict)
        else {}
    )
    if projection_gap:
        lines.append(
            "- state_projection_gap: "
            f"requires_todo_expansion={projection_gap.get('requires_todo_expansion')} "
            f"user_open={projection_gap.get('user_open_count')} "
            f"agent_open={projection_gap.get('agent_open_count')} "
            f"target_roles={','.join(projection_gap.get('target_roles') or [])}"
        )
        if projection_gap.get("recommended_action"):
            lines.append(f"- state_projection_gap_action: {projection_gap.get('recommended_action')}")
    blocked_priority_fallback = (
        payload.get("blocked_priority_fallback")
        if isinstance(payload.get("blocked_priority_fallback"), dict)
        else {}
    )
    if blocked_priority_fallback:
        selected = (
            blocked_priority_fallback.get("selected_executable")
            if isinstance(blocked_priority_fallback.get("selected_executable"), dict)
            else {}
        )
        blocked_items = (
            blocked_priority_fallback.get("blocked_items")
            if isinstance(blocked_priority_fallback.get("blocked_items"), list)
            else []
        )
        lines.append(
            "- blocked_priority_fallback: "
            f"notify_user={blocked_priority_fallback.get('notify_user')} "
            f"blocked_count={len(blocked_items)} "
            f"selected_index={selected.get('index')} "
            f"reason={blocked_priority_fallback.get('reason')}"
        )
        for blocked in blocked_items[:3]:
            if not isinstance(blocked, dict):
                continue
            text = str(blocked.get("text") or "").strip()
            if not text:
                continue
            index = blocked.get("index")
            suffix = f"[{index}]" if index is not None else ""
            lines.append(f"- blocked_priority_item{suffix}: {text}")
        if selected.get("text"):
            lines.append(f"- blocked_priority_selected: {selected.get('text')}")
        if blocked_priority_fallback.get("recommended_action"):
            lines.append(
                f"- blocked_priority_action: {blocked_priority_fallback.get('recommended_action')}"
            )
    scoped_user_gate_fallback = (
        payload.get("scoped_user_gate_fallback")
        if isinstance(payload.get("scoped_user_gate_fallback"), dict)
        else {}
    )
    if scoped_user_gate_fallback:
        selected = (
            scoped_user_gate_fallback.get("selected_executable")
            if isinstance(scoped_user_gate_fallback.get("selected_executable"), dict)
            else {}
        )
        blocked_gate = (
            scoped_user_gate_fallback.get("blocked_user_gate")
            if isinstance(scoped_user_gate_fallback.get("blocked_user_gate"), dict)
            else {}
        )
        blocked_items = (
            scoped_user_gate_fallback.get("blocked_agent_items")
            if isinstance(scoped_user_gate_fallback.get("blocked_agent_items"), list)
            else []
        )
        lines.append(
            "- scoped_user_gate_fallback: "
            f"notify_user={scoped_user_gate_fallback.get('notify_user')} "
            f"blocked_count={len(blocked_items)} "
            f"selected_index={selected.get('index')} "
            f"reason={scoped_user_gate_fallback.get('reason')}"
        )
        if blocked_gate.get("text"):
            lines.append(f"- scoped_user_gate: {blocked_gate.get('text')}")
        for blocked in blocked_items[:3]:
            if not isinstance(blocked, dict):
                continue
            text = str(blocked.get("text") or "").strip()
            if not text:
                continue
            index = blocked.get("index")
            suffix = f"[{index}]" if index is not None else ""
            lines.append(f"- scoped_user_gate_blocked_item{suffix}: {text}")
        if selected.get("text"):
            lines.append(f"- scoped_user_gate_selected: {selected.get('text')}")
        if scoped_user_gate_fallback.get("recommended_action"):
            lines.append(
                f"- scoped_user_gate_action: {scoped_user_gate_fallback.get('recommended_action')}"
            )
    completed_todo_archive_warning = (
        payload.get("completed_todo_archive_warning")
        if isinstance(payload.get("completed_todo_archive_warning"), dict)
        else {}
    )
    if completed_todo_archive_warning:
        lines.append(
            "- completed_todo_archive_warning: "
            f"requires_archive={completed_todo_archive_warning.get('requires_archive')} "
            f"active_done={completed_todo_archive_warning.get('active_done_count')} "
            f"max_active_done={completed_todo_archive_warning.get('max_active_done_count')} "
            f"archive_section={completed_todo_archive_warning.get('archive_section')}"
        )
        if completed_todo_archive_warning.get("recommended_action"):
            lines.append(
                f"- completed_todo_archive_action: {completed_todo_archive_warning.get('recommended_action')}"
            )
    replan_obligation = (
        payload.get("autonomous_replan_obligation")
        if isinstance(payload.get("autonomous_replan_obligation"), dict)
        else {}
    )
    if replan_obligation:
        trigger_kinds = [
            str(trigger.get("kind") or "")
            for trigger in replan_obligation.get("triggers") or []
            if isinstance(trigger, dict) and trigger.get("kind")
        ]
        lines.append(
            "- autonomous_replan_obligation: "
            f"required={replan_obligation.get('required')} "
            f"trigger_count={replan_obligation.get('trigger_count')} "
            f"triggers={','.join(trigger_kinds)}"
        )
        if replan_obligation.get("next_validation_command"):
            lines.append(f"- autonomous_replan_validation: `{replan_obligation.get('next_validation_command')}`")
    work_lane_contract = (
        payload.get("work_lane_contract")
        if isinstance(payload.get("work_lane_contract"), dict)
        else {}
    )
    if work_lane_contract:
        lines.append(
            "- work_lane_contract: "
            f"lane={work_lane_contract.get('lane')} "
            f"next={work_lane_contract.get('next_lane')} "
            f"obligation={work_lane_contract.get('obligation')} "
            f"must_attempt_work={work_lane_contract.get('must_attempt_work')}"
        )
        reason_codes = (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
        if reason_codes:
            lines.append(f"- work_lane_reason_codes: {','.join(str(code) for code in reason_codes)}")
        if work_lane_contract.get("monitor_policy"):
            lines.append(f"- work_lane_monitor_policy: {work_lane_contract.get('monitor_policy')}")
        if work_lane_contract.get("monitor_due_count"):
            lines.append(
                "- work_lane_monitor_due: "
                f"count={work_lane_contract.get('monitor_due_count')} "
                f"selected={work_lane_contract.get('selected_todo_id') or ''} "
                f"next_due_at={work_lane_contract.get('selected_next_due_at') or ''}"
            )
        if work_lane_contract.get("action"):
            lines.append(f"- work_lane_action: {work_lane_contract.get('action')}")
        outcome_followthrough = (
            work_lane_contract.get("outcome_followthrough")
            if isinstance(work_lane_contract.get("outcome_followthrough"), dict)
            else {}
        )
        if outcome_followthrough:
            lines.append(
                "- work_lane_outcome_followthrough: "
                f"latest_outcome={outcome_followthrough.get('latest_delivery_outcome')} "
                f"latest_kind={outcome_followthrough.get('latest_delivery_turn_kind')} "
                f"obligation={outcome_followthrough.get('obligation')}"
            )
    interface_budget_cadence = (
        payload.get("interface_budget_cadence")
        if isinstance(payload.get("interface_budget_cadence"), dict)
        else {}
    )
    if interface_budget_cadence:
        lines.append(
            "- interface_budget_cadence: "
            f"overdue={interface_budget_cadence.get('overdue')} "
            f"within_budget={interface_budget_cadence.get('within_budget')} "
            f"checked_at={interface_budget_cadence.get('checked_at')} "
            f"next_check_due_at={interface_budget_cadence.get('next_check_due_at')} "
            f"tightest={interface_budget_cadence.get('tightest_surface')}/"
            f"{interface_budget_cadence.get('tightest_metric')} "
            f"headroom={interface_budget_cadence.get('headroom_remaining')} "
            f"recommendation={interface_budget_cadence.get('recommendation')}"
        )
    execution_profile = (
        payload.get("execution_profile")
        if isinstance(payload.get("execution_profile"), dict)
        else {}
    )
    if execution_profile:
        lines.append(f"- execution_profile: {execution_profile_summary(execution_profile)}")
    long_task_cadence_hint = (
        payload.get("long_task_cadence_hint")
        if isinstance(payload.get("long_task_cadence_hint"), dict)
        else {}
    )
    if long_task_cadence_hint:
        lines.append(
            f"- long_task_cadence_hint: {long_task_cadence_hint_summary(long_task_cadence_hint)}"
        )
    control_plane = payload.get("control_plane") if isinstance(payload.get("control_plane"), dict) else None
    if control_plane:
        lines.append(f"- control_plane: {control_plane_policy_summary(control_plane)}")

    def append_todo_summary(label: str, summary: dict[str, Any]) -> None:
        summary_parts = [
            f"open={summary.get('open_count')}",
            f"total={summary.get('total_count')}",
        ]
        if summary.get("claimed_open_count"):
            summary_parts.insert(1, f"claimed={summary.get('claimed_open_count')}")
            summary_parts.insert(2, f"unclaimed={summary.get('unclaimed_open_count', 0)}")
        if summary.get("monitor_due_count"):
            summary_parts.append(f"monitor_due={summary.get('monitor_due_count')}")
        lines.append(f"- {label}_summary: {' '.join(summary_parts)}")
        first_open = summary.get("first_open_items") if isinstance(summary.get("first_open_items"), list) else []
        for todo in first_open[:3]:
            if not isinstance(todo, dict):
                continue
            text = str(todo.get("text") or "").strip()
            if not text:
                continue
            index = todo.get("index")
            suffix = f"[{index}]" if index is not None else ""
            claim_suffix = (
                f" claimed_by={todo.get('claimed_by')}"
                if todo.get("claimed_by")
                else ""
            )
            lines.append(f"- {label}_next{suffix}: {text}{claim_suffix}")
        first_keys = {
            (
                str(todo.get("todo_id") or ""),
                todo.get("index"),
                str(todo.get("text") or "").strip(),
            )
            for todo in first_open
            if isinstance(todo, dict)
        }
        backlog = summary.get("backlog_items") if isinstance(summary.get("backlog_items"), list) else []
        extra_count = 0
        for todo in backlog:
            if not isinstance(todo, dict):
                continue
            text = str(todo.get("text") or "").strip()
            if not text:
                continue
            key = (str(todo.get("todo_id") or ""), todo.get("index"), text)
            if key in first_keys:
                continue
            index = todo.get("index")
            suffix = f"[{index}]" if index is not None else ""
            claim_suffix = (
                f" claimed_by={todo.get('claimed_by')}"
                if todo.get("claimed_by")
                else ""
            )
            lines.append(f"- {label}_backlog{suffix}: {text}{claim_suffix}")
            extra_count += 1
            if extra_count >= 5:
                break

    if quota:
        lines.append(
            "- quota: "
            f"compute={quota.get('compute')} "
            f"slot_minutes={quota.get('slot_minutes')} "
            f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')}"
        )
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    handoff_readiness = (
        payload.get("handoff_readiness")
        if isinstance(payload.get("handoff_readiness"), dict)
        else {}
    )
    if handoff_readiness:
        lines.append(
            "- handoff_readiness: "
            f"ready={handoff_readiness.get('ready')} "
            f"codex_ready={handoff_readiness.get('codex_ready')} "
            f"source={handoff_readiness.get('source')} "
            f"quota_state={handoff_readiness.get('quota_state')}"
        )
        interface_budget = (
            handoff_readiness.get("handoff_interface_budget")
            if isinstance(handoff_readiness.get("handoff_interface_budget"), dict)
            else {}
        )
        if interface_budget:
            lines.append(
                "- handoff_interface_budget: "
                f"mode={interface_budget.get('mode')} "
                f"max_lines={interface_budget.get('max_lines')} "
                f"max_chars={interface_budget.get('max_chars')}"
            )
        lines.append(
            "- handoff_state: "
            f"status={handoff_readiness.get('handoff_status')} "
            f"post_handoff_run_seen={handoff_readiness.get('post_handoff_run_seen')} "
            f"ready_at={handoff_readiness.get('handoff_ready_at') or ''}"
        )
        latest_handoff_run = (
            handoff_readiness.get("post_handoff_latest_run")
            if isinstance(handoff_readiness.get("post_handoff_latest_run"), dict)
            else {}
        )
        if latest_handoff_run:
            outcome_suffix = ""
            if latest_handoff_run.get("delivery_outcome"):
                outcome_suffix = f" outcome={latest_handoff_run.get('delivery_outcome')}"
            lines.append(
                "- post_handoff_run: "
                f"classification={latest_handoff_run.get('classification')} "
                f"at={latest_handoff_run.get('generated_at')} "
                f"scale={latest_handoff_run.get('delivery_batch_scale') or ''}"
                f"{outcome_suffix}"
            )
        recent_handoff_runs = (
            handoff_readiness.get("post_handoff_recent_runs")
            if isinstance(handoff_readiness.get("post_handoff_recent_runs"), list)
            else []
        )
        recent_scales = [
            str(run.get("delivery_batch_scale") or "")
            for run in recent_handoff_runs
            if isinstance(run, dict)
        ]
        if recent_scales:
            recent_outcomes = [
                str(run.get("delivery_outcome") or "")
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
                "- post_handoff_recent_scales: "
                f"{','.join(recent_scales)} "
                f"small_streak={handoff_readiness.get('post_handoff_small_scale_streak', 0)}"
                f"{outcome_text}"
                f"{gap_text}"
            )
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    if heartbeat_recommendation:
        lines.append(
            "- heartbeat_recommendation: "
            f"mode={heartbeat_recommendation.get('recommended_mode')} "
            f"notify={heartbeat_recommendation.get('notify')}"
        )
        if heartbeat_recommendation.get("command"):
            lines.append(f"- heartbeat_command: `{heartbeat_recommendation.get('command')}`")
        if heartbeat_recommendation.get("stop_if_unchanged"):
            lines.append("- heartbeat_stop_if_unchanged: `True`")
        if heartbeat_recommendation.get("repeat_notification_required"):
            lines.append("- heartbeat_repeat_notification_required: `True`")
        if heartbeat_recommendation.get("spend_policy"):
            lines.append(f"- heartbeat_spend_policy: {heartbeat_recommendation.get('spend_policy')}")
        if heartbeat_recommendation.get("reason"):
            lines.append(f"- heartbeat_reason: {heartbeat_recommendation.get('reason')}")
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    if execution_obligation:
        lines.append(
            "- execution_obligation: "
            f"must_attempt_work={execution_obligation.get('must_attempt_work')} "
            f"kind={execution_obligation.get('kind')} "
            f"notify_is_execution_gate={execution_obligation.get('notify_is_execution_gate')}"
        )
        if execution_obligation.get("contract_obligation"):
            lines.append(f"- execution_contract_obligation: {execution_obligation.get('contract_obligation')}")
        if execution_obligation.get("reason"):
            lines.append(f"- execution_obligation_reason: {execution_obligation.get('reason')}")
    interaction_contract = (
        payload.get("interaction_contract")
        if isinstance(payload.get("interaction_contract"), dict)
        else {}
    )
    if interaction_contract:
        user_channel = (
            interaction_contract.get("user_channel")
            if isinstance(interaction_contract.get("user_channel"), dict)
            else {}
        )
        agent_channel = (
            interaction_contract.get("agent_channel")
            if isinstance(interaction_contract.get("agent_channel"), dict)
            else {}
        )
        cli_channel = (
            interaction_contract.get("cli_channel")
            if isinstance(interaction_contract.get("cli_channel"), dict)
            else {}
        )
        lines.append(
            "- interaction_contract: "
            f"schema={interaction_contract.get('schema_version')} "
            f"mode={interaction_contract.get('mode')} "
            f"user_required={user_channel.get('action_required')} "
            f"agent_must_attempt={agent_channel.get('must_attempt')} "
            f"quiet_noop_allowed={agent_channel.get('quiet_noop_allowed')} "
            f"spend_after_validation={cli_channel.get('spend_after_validation')}"
        )
        if agent_channel.get("primary_action"):
            lines.append(f"- interaction_agent_action: {agent_channel.get('primary_action')}")
    automation_liveness = (
        payload.get("automation_liveness")
        if isinstance(payload.get("automation_liveness"), dict)
        else {}
    )
    if automation_liveness:
        lines.append(
            "- automation_liveness: "
            f"action={automation_liveness.get('automation_action')} "
            f"keep_active={automation_liveness.get('keep_active')} "
            f"pause_allowed={automation_liveness.get('pause_allowed')}"
        )
        if automation_liveness.get("reason"):
            lines.append(f"- automation_liveness_reason: {automation_liveness.get('reason')}")
        if automation_liveness.get("pause_policy"):
            lines.append(f"- automation_pause_policy: {automation_liveness.get('pause_policy')}")
    scheduler_hint = (
        payload.get("scheduler_hint")
        if isinstance(payload.get("scheduler_hint"), dict)
        else {}
    )
    if scheduler_hint:
        codex_app = (
            scheduler_hint.get("codex_app")
            if isinstance(scheduler_hint.get("codex_app"), dict)
            else {}
        )
        unchanged_poll = (
            scheduler_hint.get("unchanged_poll")
            if isinstance(scheduler_hint.get("unchanged_poll"), dict)
            else {}
        )
        limits = unchanged_poll.get("limits") if isinstance(unchanged_poll.get("limits"), dict) else {}
        codex_cli_tui = (
            scheduler_hint.get("codex_cli_tui")
            if isinstance(scheduler_hint.get("codex_cli_tui"), dict)
            else {}
        )
        claude_code_loop = (
            scheduler_hint.get("claude_code_loop")
            if isinstance(scheduler_hint.get("claude_code_loop"), dict)
            else {}
        )
        cli_unchanged_limit = (
            limits.get("codex_cli_tui")
            if "codex_cli_tui" in limits
            else codex_cli_tui.get("unchanged_poll_limit")
        )
        claude_unchanged_limit = (
            limits.get("claude_code_loop")
            if "claude_code_loop" in limits
            else claude_code_loop.get("unchanged_poll_limit")
        )
        lines.append(
            "- scheduler_hint: "
            f"action={scheduler_hint.get('action')} "
            f"cadence={scheduler_hint.get('cadence_class')} "
            f"codex_app_minutes={codex_app.get('recommended_interval_minutes')} "
            f"codex_app_rrule={codex_app.get('recommended_rrule')} "
            f"codex_app_progression={codex_app.get('example_progression_minutes')} "
            f"cli_unchanged_limit={cli_unchanged_limit} "
            f"claude_unchanged_limit={claude_unchanged_limit}"
        )
        if scheduler_hint.get("reason"):
            lines.append(f"- scheduler_hint_reason: {scheduler_hint.get('reason')}")
        reset_policy = (
            scheduler_hint.get("reset_policy")
            if isinstance(scheduler_hint.get("reset_policy"), dict)
            else {}
        )
        if reset_policy:
            lines.append(
                "- scheduler_reset: "
                f"reset_to={reset_policy.get('reset_to')} "
                f"initial_interval={reset_policy.get('codex_app_initial_interval_minutes')} "
                f"initial_rrule={reset_policy.get('codex_app_initial_rrule')} "
                f"reset_generation={reset_policy.get('reset_token')} "
                f"identity_key_count={reset_policy.get('identity_key_count')} "
                f"identity_signature={reset_policy.get('identity_signature')} "
                f"profile_signature={reset_policy.get('profile_signature')} "
                f"conditions={reset_policy.get('reset_condition_summary')}"
            )
    protocol_action_packet = (
        payload.get("protocol_action_packet")
        if isinstance(payload.get("protocol_action_packet"), dict)
        else {}
    )
    if protocol_action_packet:
        lines.append(
            "- protocol_action_packet: "
            f"schema={protocol_action_packet.get('schema_version')} "
            f"{protocol_action_packet.get('summary') or ''}"
        )
    stall_self_repair = (
        payload.get("stall_self_repair")
        if isinstance(payload.get("stall_self_repair"), dict)
        else {}
    )
    if stall_self_repair:
        lines.append(
            "- stall_self_repair: "
            f"trigger={stall_self_repair.get('trigger')} "
            f"mode={stall_self_repair.get('recommended_mode')} "
            f"action={stall_self_repair.get('effective_action')}"
        )
        if stall_self_repair.get("repair_focus"):
            lines.append(f"- stall_repair_focus: {stall_self_repair.get('repair_focus')}")
        if stall_self_repair.get("missing_write_scopes"):
            lines.append(
                "- boundary_missing_write_scopes: "
                f"{', '.join(str(value) for value in stall_self_repair.get('missing_write_scopes') or [])}"
            )
        blockers = (
            stall_self_repair.get("blocking_health_items")
            if isinstance(stall_self_repair.get("blocking_health_items"), list)
            else []
        )
        for blocker in blockers[:3]:
            if not isinstance(blocker, dict):
                continue
            lines.append(
                "- stall_health_blocker: "
                f"goal={blocker.get('goal_id')} "
                f"status={blocker.get('status')} "
                f"waiting_on={blocker.get('waiting_on')} "
                f"action={blocker.get('recommended_action')}"
            )
    if payload.get("safe_bypass_allowed"):
        lines.append(f"- safe_bypass_allowed: `{payload.get('safe_bypass_allowed')}`")
    if payload.get("safe_bypass_kind"):
        lines.append(f"- safe_bypass_kind: {payload.get('safe_bypass_kind')}")
    if payload.get("blocked_action_scope"):
        lines.append(f"- blocked_action_scope: `{payload.get('blocked_action_scope')}`")
    if payload.get("safe_bypass_policy"):
        lines.append(f"- safe_bypass_policy: {payload.get('safe_bypass_policy')}")
    decision_freshness_warning = (
        payload.get("decision_freshness_warning")
        if isinstance(payload.get("decision_freshness_warning"), dict)
        else {}
    )
    if decision_freshness_warning:
        lines.append(
            "- decision_freshness_warning: "
            f"rebase_required={decision_freshness_warning.get('rebase_required_count')} "
            f"window_days={decision_freshness_warning.get('window_days')} "
            f"source={decision_freshness_warning.get('source')}"
        )
        if decision_freshness_warning.get("message"):
            lines.append(f"- decision_freshness_action: {decision_freshness_warning.get('message')}")
        freshness_items = (
            decision_freshness_warning.get("items")
            if isinstance(decision_freshness_warning.get("items"), list)
            else []
        )
        for item in freshness_items[:DECISION_FRESHNESS_WARNING_ITEM_LIMIT]:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- decision_freshness_item: "
                f"kind={item.get('decision_kind')} "
                f"state={item.get('freshness_state')} "
                f"age_days={item.get('age_days')} "
                f"newer_7d={item.get('newer_event_count_7d')} "
                f"at={item.get('decision_at')}"
            )
    promotion_readiness_warning = (
        payload.get("promotion_readiness_warning")
        if isinstance(payload.get("promotion_readiness_warning"), dict)
        else {}
    )
    if promotion_readiness_warning:
        lines.append(
            "- promotion_readiness_warning: "
            f"status={promotion_readiness_warning.get('freshness_status')} "
            f"requires_readiness_run={promotion_readiness_warning.get('requires_readiness_run')} "
            f"window_hours={promotion_readiness_warning.get('freshness_window_hours')} "
            f"source={promotion_readiness_warning.get('source')}"
        )
        if promotion_readiness_warning.get("message"):
            lines.append(f"- promotion_readiness_action: {promotion_readiness_warning.get('message')}")
        lines.append(
            "- promotion_readiness_evidence: "
            f"goal={promotion_readiness_warning.get('goal_id') or ''} "
            f"generated_at={promotion_readiness_warning.get('generated_at') or ''} "
            f"age_hours={promotion_readiness_warning.get('age_hours')} "
            f"artifacts={promotion_readiness_warning.get('json_exists')}/{promotion_readiness_warning.get('markdown_exists')}"
        )
        if promotion_readiness_warning.get("reason"):
            lines.append(f"- promotion_readiness_reason: {promotion_readiness_warning.get('reason')}")
    reward_lesson_warning = (
        payload.get("reward_lesson_projection_warning")
        if isinstance(payload.get("reward_lesson_projection_warning"), dict)
        else {}
    )
    if reward_lesson_warning:
        lines.append(
            "- reward_lesson_projection_warning: "
            f"matches={reward_lesson_warning.get('match_count')} "
            f"source={reward_lesson_warning.get('source')}"
        )
        if reward_lesson_warning.get("message"):
            lines.append(f"- reward_lesson_action: {reward_lesson_warning.get('message')}")
        for match in (reward_lesson_warning.get("matches") or [])[:3]:
            if not isinstance(match, dict):
                continue
            lines.append(
                "- reward_lesson_match: "
                f"kind={match.get('kind')} "
                f"decision={match.get('decision')} "
                f"avoid={match.get('avoid')} "
                f"summary={match.get('summary')}"
            )
    goal_boundary = payload.get("goal_boundary") if isinstance(payload.get("goal_boundary"), dict) else {}
    if goal_boundary:
        adapter = goal_boundary.get("adapter") if isinstance(goal_boundary.get("adapter"), dict) else {}
        if adapter:
            lines.append(
                "- goal_boundary_adapter: "
                f"{adapter.get('kind') or ''}:{adapter.get('status') or ''}"
            )
        write_scope = goal_boundary.get("write_scope") if isinstance(goal_boundary.get("write_scope"), list) else []
        if write_scope:
            lines.append(f"- goal_boundary_write_scope: {', '.join(str(value) for value in write_scope)}")
        approvals = (
            goal_boundary.get("requires_parent_approval")
            if isinstance(goal_boundary.get("requires_parent_approval"), list)
            else []
        )
        if approvals:
            lines.append(f"- goal_boundary_requires_approval: {', '.join(str(value) for value in approvals)}")
        guards = goal_boundary.get("guards") if isinstance(goal_boundary.get("guards"), list) else []
        for guard in guards[:5]:
            lines.append(f"- goal_boundary_guard: {guard}")
        orchestration = (
            goal_boundary.get("orchestration")
            if isinstance(goal_boundary.get("orchestration"), dict)
            else None
        )
        if orchestration:
            lines.append(f"- goal_boundary_orchestration: {orchestration_policy_summary(orchestration)}")
        run_permission_policy = (
            goal_boundary.get("run_permission_policy")
            if isinstance(goal_boundary.get("run_permission_policy"), dict)
            else None
        )
        if run_permission_policy:
            lines.append(
                "- goal_boundary_run_permission_policy: "
                f"valid={run_permission_policy.get('valid')} "
                f"delivery_allowed={run_permission_policy.get('delivery_allowed')} "
                f"no_upload={run_permission_policy.get('no_upload_required')} "
                f"compact_only={run_permission_policy.get('compact_observation_only')} "
                f"max_minutes={run_permission_policy.get('max_wall_time_minutes')}"
            )
        if goal_boundary.get("stop_condition"):
            lines.append(f"- goal_boundary_stop_condition: {goal_boundary.get('stop_condition')}")
    if payload.get("operator_question"):
        lines.append(f"- operator_question: {payload.get('operator_question')}")
    if payload.get("notify_user_on_gate"):
        lines.append(f"- notify_user_on_gate: `{payload.get('notify_user_on_gate')}`")
    if payload.get("notify_user_on_open_todo"):
        lines.append(f"- notify_user_on_open_todo: `{payload.get('notify_user_on_open_todo')}`")
    if payload.get("open_todo_notify_reason"):
        lines.append(f"- open_todo_notify_reason: {payload.get('open_todo_notify_reason')}")
    if payload.get("open_todo_notification_policy"):
        lines.append(f"- open_todo_notification_policy: {payload.get('open_todo_notification_policy')}")
    if payload.get("gate_prompt"):
        lines.extend(["", "## Gate Prompt", str(payload.get("gate_prompt"))])
    user_todo_summary = (
        payload.get("user_todo_summary") if isinstance(payload.get("user_todo_summary"), dict) else {}
    )
    if user_todo_summary:
        append_todo_summary("user_todo", user_todo_summary)
    agent_todo_summary = (
        payload.get("agent_todo_summary") if isinstance(payload.get("agent_todo_summary"), dict) else {}
    )
    if agent_todo_summary:
        append_todo_summary("agent_todo", agent_todo_summary)
    todo_write_hint = payload.get("todo_write_hint") if isinstance(payload.get("todo_write_hint"), dict) else {}
    if todo_write_hint:
        lines.append(f"- todo_write_hint: {todo_write_hint.get('rule')}")
        lines.append(f"- user_todo_command_template: `{todo_write_hint.get('user_todo_command_template')}`")
        lines.append(f"- agent_todo_command_template: `{todo_write_hint.get('agent_todo_command_template')}`")
    if payload.get("recommended_action"):
        lines.append(f"- recommended_action: {payload.get('recommended_action')}")
    if payload.get("agent_command"):
        lines.append(f"- agent_command: `{payload.get('agent_command')}`")
    if payload.get("next_handoff_condition"):
        lines.append(f"- next_handoff_condition: {payload.get('next_handoff_condition')}")
    summary = payload.get("plan_summary") if isinstance(payload.get("plan_summary"), dict) else {}
    states = summary.get("states") if isinstance(summary.get("states"), dict) else {}
    if summary:
        state_text = ", ".join(f"{state}={states.get(state, 0)}" for state in QUOTA_STATE_ORDER)
        lines.append(
            "- plan_summary: "
            f"next_automatic_turn={summary.get('next_automatic_turn') or 'none'} "
            f"{state_text}"
        )
    return "\n".join(lines)
