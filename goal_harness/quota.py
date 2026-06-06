from __future__ import annotations

from copy import deepcopy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .control_plane import (
    compact_control_plane_policy,
    control_plane_policy_summary,
    control_plane_self_repair_allows,
)
from .execution_profile import (
    execution_profile_outcome_floor,
    execution_profile_summary,
    outcome_floor_threshold,
)
from .orchestration import compact_orchestration_policy, orchestration_policy_summary


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
DEFAULT_SLOT_SPEND_SOURCE = "heartbeat"
VALID_SLOT_SPEND_SOURCES = {"heartbeat", "controller", "adapter"}
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
    "handoff_ready_at",
    "handoff_ready_classification",
    "post_handoff_small_scale_streak",
    "post_handoff_outcome_gap_streak",
    "next_probe",
)
POST_HANDOFF_RUN_COMPACT_FIELDS = (
    "generated_at",
    "classification",
    "delivery_batch_scale",
    "delivery_outcome",
    "health_check",
    "json_exists",
    "markdown_exists",
)
SELF_REPAIR_SPEND_ACTIONS = {
    "control_plane_health_repair",
    "control_plane_projection_repair",
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
    if str(run.get("classification") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
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
    spent_slots = 0
    spend_event_count = 0

    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("goal_id") or goal_id) != goal_id:
            continue
        generated_at = _parse_timestamp(run.get("generated_at"))
        if generated_at is None or generated_at < window_start or generated_at > current_time:
            continue
        event = _load_quota_event_from_run(run)
        if not event or str(event.get("event_type") or "") != QUOTA_SLOT_SPENT_CLASSIFICATION:
            continue
        slots = max(0, _int_number(event.get("slots"), default=0))
        if slots <= 0:
            continue
        spent_slots += slots
        spend_event_count += 1

    payload["spent_slots"] = spent_slots
    payload["spend_source"] = "runtime_events"
    payload["spend_event_count"] = spend_event_count
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


def _summarize_user_todos(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    items = value.get("items") if isinstance(value.get("items"), list) else []
    open_items: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("done") is True:
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        open_items.append(
            {
                "index": item.get("index"),
                "text": text,
            }
        )
    return {
        "source_section": value.get("source_section"),
        "total_count": value.get("total_count"),
        "open_count": value.get("open_count", len(open_items)),
        "done_count": value.get("done_count"),
        "first_open_items": open_items[:3],
    }


def _summarize_project_asset_todos(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if isinstance(value.get("items"), list):
        return _summarize_user_todos(value)

    next_text = str(value.get("next") or "").strip()
    first_open_items = [{"index": 1, "text": next_text}] if next_text else []
    open_count = value.get("open", value.get("open_count", len(first_open_items)))
    return {
        "source_section": "project_asset",
        "total_count": value.get("total", value.get("total_count")),
        "open_count": open_count,
        "done_count": value.get("done", value.get("done_count")),
        "first_open_items": first_open_items,
    }


def _todo_write_hint(goal_id: str) -> dict[str, str]:
    return {
        "rule": (
            "If your analysis discovers a concrete user/owner action, write it to the active-state "
            "User Todo section instead of hiding it in Next Action, review docs, or chat."
        ),
        "user_todo_command_template": (
            f"goal-harness todo add --goal-id {goal_id} --role user "
            "--text '<public-safe user/owner action>'"
        ),
        "agent_todo_command_template": (
            f"goal-harness todo add --goal-id {goal_id} --role agent "
            "--text '<public-safe agent action>'"
        ),
        "section": "User Todo / Owner Review Reading Queue",
    }


def _compact_handoff_readiness(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    compact = {field: value[field] for field in HANDOFF_READINESS_COMPACT_FIELDS if field in value}
    checks = value.get("checks") if isinstance(value.get("checks"), dict) else {}
    if checks:
        compact["checks"] = {
            str(key): bool(check)
            for key, check in checks.items()
        }
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
    if write_scope:
        boundary["write_scope"] = [str(value) for value in write_scope if str(value).strip()]
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
    if isinstance(project_asset_source, dict) and project_asset_source.get("project_asset"):
        project_asset = project_asset_source.get("project_asset")
        if isinstance(project_asset, dict):
            if project_asset.get("stop_condition"):
                boundary["stop_condition"] = project_asset.get("stop_condition")
            if isinstance(project_asset.get("execution_profile"), dict):
                boundary["execution_profile"] = project_asset["execution_profile"]
            if isinstance(project_asset.get("orchestration"), dict):
                boundary["orchestration"] = compact_orchestration_policy(project_asset["orchestration"])
    if boundary:
        boundary["rule"] = "Follow this boundary before choosing delivery work; stop if useful work requires an unapproved scope."
        return boundary
    return None


def _build_gate_prompt(item: dict[str, Any]) -> str | None:
    question = str(item.get("operator_question") or "").strip()
    recommended_action = str(item.get("recommended_action") or "").strip()
    next_handoff_condition = str(item.get("next_handoff_condition") or "").strip()
    missing_gates = [
        str(gate).strip()
        for gate in (item.get("missing_gates") if isinstance(item.get("missing_gates"), list) else [])
        if str(gate).strip()
    ]
    user_todo_summary = _summarize_user_todos(item.get("user_todos"))
    first_open = (
        user_todo_summary.get("first_open_items")
        if isinstance(user_todo_summary, dict) and isinstance(user_todo_summary.get("first_open_items"), list)
        else []
    )

    if not any([question, recommended_action, next_handoff_condition, missing_gates, first_open]):
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


def _heartbeat_recommendation(
    item: dict[str, Any],
    *,
    goal_id: str,
    state: str,
    should_run: bool,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    stall_self_repair: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = str(item.get("status") or "")
    waiting_on = str(item.get("waiting_on") or "")
    adapter_kind = str(item.get("adapter_kind") or "")
    lifecycle_phase = item.get("lifecycle_phase")
    lifecycle_flags = item.get("lifecycle_flags")
    quota = item.get("quota") if isinstance(item.get("quota"), dict) else {}
    has_user_todos = _open_todo_count(user_todo_summary) > 0
    has_agent_todos = _open_todo_count(agent_todo_summary) > 0

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
            "spend_policy": "do not append quota spend for the blocker-push turn",
            "reason": _open_todo_notify_reason(state=state, waiting_on=waiting_on),
        }
    if state == "focus_wait" and quota.get("handoff_outcome_floor_block"):
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

    if status == "connected_without_run" and _supports_read_only_project_map(adapter_kind):
        return {
            **base,
            "recommended_mode": "run_first_read_only_map",
            "command": f"goal-harness read-only-map --goal-id {goal_id}",
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

    if item.get("agent_command"):
        return {
            **base,
            "recommended_mode": "run_agent_command",
            "command": str(item.get("agent_command")),
            "notify": "DONT_NOTIFY",
            "spend_policy": "append exactly one heartbeat spend after the command completes and validation/writeback are saved",
            "reason": "current status exposes an approved project-agent command",
        }

    return {
        **base,
        "recommended_mode": "steering_audit_then_one_step",
        "spend_policy": "append exactly one heartbeat spend only after a bounded progress segment is validated and written back",
        "reason": "eligible Codex-ready goal requires the standard steering audit before delivery",
    }


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
    groups: dict[str, list[dict[str, Any]]] = {state: [] for state in QUOTA_STATE_ORDER}
    groups["unknown"] = []

    for goal in run_goals:
        if not isinstance(goal, dict) or not goal.get("registry_member"):
            continue
        goal_id = str(goal.get("id") or "")
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
            "promotion readiness evidence is missing, stale, or unknown; run the "
            "canary promotion-readiness smoke before promoting the local release snapshot"
        ),
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
    stall_self_repair: dict[str, Any] | None,
    state: str,
    quota: dict[str, Any],
) -> str:
    if normal_delivery_allowed:
        return "normal_run"
    if recovery_delivery_allowed:
        return "outcome_floor_recovery"
    if self_repair_allowed:
        repair_action = (
            stall_self_repair.get("effective_action")
            if isinstance(stall_self_repair, dict)
            else None
        )
        return str(repair_action or "control_plane_repair")
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


def build_quota_should_run(status_payload: dict[str, Any], *, goal_id: str) -> dict[str, Any]:
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
        user_todo_summary = _summarize_project_asset_todos(
            project_asset.get("user_todos") if project_asset else None
        ) or _summarize_user_todos(item.get("user_todos"))
        agent_todo_summary = _summarize_project_asset_todos(
            project_asset.get("agent_todos") if project_asset else None
        ) or _summarize_user_todos(item.get("agent_todos"))
        stall_self_repair = _stall_self_repair_hint(
            item,
            state=state,
            plan_ok=bool(plan.get("ok")),
            health_items=health_items,
            user_todo_summary=user_todo_summary,
            agent_todo_summary=agent_todo_summary,
        )
        self_repair_allowed = bool(stall_self_repair and stall_self_repair.get("allowed"))
        should_run = bool(normal_delivery_allowed or recovery_allowed or self_repair_allowed)
        effective_action = _effective_action(
            normal_delivery_allowed=normal_delivery_allowed,
            recovery_delivery_allowed=recovery_allowed,
            self_repair_allowed=self_repair_allowed,
            stall_self_repair=stall_self_repair,
            state=state,
            quota=quota,
        )
        payload = {
            "ok": bool(plan.get("ok")) or self_repair_allowed,
            "status_health_ok": bool(plan.get("ok")),
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": (
                "run"
                if normal_delivery_allowed
                else "safe_bypass_recovery"
                if recovery_allowed
                else "self_repair"
                if self_repair_allowed
                else "skip"
            ),
            "should_run": should_run,
            "normal_delivery_allowed": normal_delivery_allowed,
            "recovery_delivery_allowed": recovery_allowed,
            "self_repair_allowed": self_repair_allowed,
            "effective_action": effective_action,
            "actionable_by_codex": bool(should_run or recovery_allowed),
            "reason": (
                str(stall_self_repair.get("reason"))
                if self_repair_allowed and isinstance(stall_self_repair, dict)
                else reason
            ),
            "quota": quota,
            "state": state,
            "blocked_action_scope": quota.get("blocked_action_scope"),
            "safe_bypass_allowed": bool(quota.get("safe_bypass_allowed")),
            "safe_bypass_kind": quota.get("safe_bypass_kind"),
            "safe_bypass_policy": quota.get("safe_bypass_policy"),
            "waiting_on": item.get("waiting_on"),
            "status": item.get("status"),
            "lifecycle_phase": item.get("lifecycle_phase"),
            "lifecycle_flags": item.get("lifecycle_flags"),
            "source": item.get("source"),
            "project_asset_source": item.get("project_asset_source"),
            "recommended_action": item.get("recommended_action"),
            "execution_profile": project_asset.get("execution_profile") if project_asset else None,
            "handoff_readiness": item.get("handoff_readiness"),
            "heartbeat_recommendation": _heartbeat_recommendation(
                item,
                goal_id=safe_goal_id,
                state=state,
                should_run=should_run,
                user_todo_summary=user_todo_summary,
                agent_todo_summary=agent_todo_summary,
                stall_self_repair=stall_self_repair,
            ),
            "goal_boundary": _goal_boundary(item),
            "plan_summary": plan.get("summary"),
            "todo_write_hint": _todo_write_hint(safe_goal_id),
        }
        control_plane = compact_control_plane_policy(item.get("control_plane"))
        if control_plane:
            payload["control_plane"] = control_plane
        if stall_self_repair:
            payload["stall_self_repair"] = stall_self_repair
        if item.get("operator_question"):
            payload["operator_question"] = item.get("operator_question")
        if item.get("missing_gates"):
            payload["missing_gates"] = item.get("missing_gates")
        if user_todo_summary:
            payload["user_todo_summary"] = user_todo_summary
            if _should_notify_user_on_open_todo(
                state=state,
                waiting_on=str(item.get("waiting_on") or ""),
                user_todo_summary=user_todo_summary,
            ):
                payload["notify_user_on_open_todo"] = True
                payload["open_todo_notify_reason"] = _open_todo_notify_reason(
                    state=state,
                    waiting_on=str(item.get("waiting_on") or ""),
                )
        payload["requires_user_action"] = bool(
            state == "operator_gate" or payload.get("notify_user_on_open_todo") is True
        )
        if agent_todo_summary:
            payload["agent_todo_summary"] = agent_todo_summary
        decision_warning = _decision_freshness_warning(status_payload, goal_id=safe_goal_id)
        if decision_warning:
            payload["decision_freshness_warning"] = decision_warning
        promotion_warning = _promotion_readiness_warning(status_payload)
        if promotion_warning:
            payload["promotion_readiness_warning"] = promotion_warning
        gate_prompt = _build_gate_prompt(item) if state == "operator_gate" else None
        if gate_prompt:
            payload["gate_prompt"] = gate_prompt
            payload["notify_user_on_gate"] = True
        if item.get("next_handoff_condition"):
            payload["next_handoff_condition"] = item.get("next_handoff_condition")
        if should_run and item.get("agent_command"):
            payload["agent_command"] = item.get("agent_command")
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
        "recommended_action": "run `goal-harness registry` and connect or sync the goal before spending compute",
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
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    safe_slots = max(1, _int_number(slots, default=1))
    before = build_quota_should_run(status_payload, goal_id=safe_goal_id)
    safe_bypass_spend = (
        (
            before.get("state") == "operator_gate"
            or before.get("recovery_delivery_allowed") is True
            or before.get("effective_action") == "outcome_floor_recovery"
        )
        and before.get("safe_bypass_allowed") is True
    )
    self_repair_spend = before.get("effective_action") in SELF_REPAIR_SPEND_ACTIONS
    if not before.get("ok") or (not before.get("should_run") and not safe_bypass_spend):
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
    after = build_quota_should_run(after_status, goal_id=safe_goal_id)

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
            f"dry-run preview: spending {safe_slots} slot(s) would move "
            f"{safe_goal_id} from {before.get('state')} to {after.get('state')}"
        ),
        "rolling_window_note": (
            "before -> after is a same-status-payload projection. Later quota status "
            "recomputes spent_slots from quota_slot_spent events still inside window_hours, "
            "so the visible total can stay flat if an older spend expires."
        ),
        "safe_bypass_spend": safe_bypass_spend,
        "self_repair_spend": self_repair_spend,
    }


def _compact_quota_decision(decision: dict[str, Any]) -> dict[str, Any]:
    quota = decision.get("quota") if isinstance(decision.get("quota"), dict) else {}
    return {
        "should_run": bool(decision.get("should_run")),
        "normal_delivery_allowed": bool(decision.get("normal_delivery_allowed")),
        "recovery_delivery_allowed": bool(decision.get("recovery_delivery_allowed")),
        "effective_action": decision.get("effective_action"),
        "self_repair_allowed": bool(decision.get("self_repair_allowed")),
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
    eligible_spend = (
        before_compact["should_run"] is True
        and before_compact["state"] == "eligible"
        and not self_repair_spend
    )
    safe_bypass_spend = (
        (
            before_compact["state"] == "operator_gate"
            or before_compact["recovery_delivery_allowed"] is True
            or before_compact["effective_action"] == "outcome_floor_recovery"
        )
        and before_compact["safe_bypass_allowed"] is True
    )
    if not eligible_spend and not safe_bypass_spend and not self_repair_spend:
        raise ValueError("quota slot spend requires an eligible, safe-bypass, or control-plane self-repair quota should-run decision")

    return {
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
                    else "quota safe-bypass operator gate; quota slot spend event public-safe"
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
                        else f"{slots} automatic agent slot(s) completed as safe-bypass work under an operator gate"
                    )
                )
            ),
            "before": before_compact,
            "after": after_compact,
        },
    }


def spend_quota_slot(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
    execute: bool = False,
    source: str = DEFAULT_SLOT_SPEND_SOURCE,
) -> dict[str, Any]:
    safe_goal_id = _validate_goal_id_path_segment(str(goal_id or ""))
    preview = build_quota_slot_preview(status_payload, goal_id=safe_goal_id, slots=slots)
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

    payload = {
        **preview,
        "dry_run": not execute,
        "appended": execute,
        "registry_mutated": False,
        "source": record["quota_event"]["source"],
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "generated_at": generated_at,
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
        f"# Goal Harness {title}",
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
        "# Goal Harness Quota Slot Preview",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- classification: `{payload.get('classification') or QUOTA_SLOT_SPENT_CLASSIFICATION}`",
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


def render_quota_should_run_markdown(payload: dict[str, Any]) -> str:
    quota = payload.get("quota") if isinstance(payload.get("quota"), dict) else {}
    lines = [
        "# Goal Harness Quota Should Run",
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
    execution_profile = (
        payload.get("execution_profile")
        if isinstance(payload.get("execution_profile"), dict)
        else {}
    )
    if execution_profile:
        lines.append(f"- execution_profile: {execution_profile_summary(execution_profile)}")
    control_plane = payload.get("control_plane") if isinstance(payload.get("control_plane"), dict) else None
    if control_plane:
        lines.append(f"- control_plane: {control_plane_policy_summary(control_plane)}")

    def append_todo_summary(label: str, summary: dict[str, Any]) -> None:
        lines.append(
            f"- {label}_summary: "
            f"open={summary.get('open_count')} "
            f"total={summary.get('total_count')}"
        )
        first_open = summary.get("first_open_items") if isinstance(summary.get("first_open_items"), list) else []
        for todo in first_open[:3]:
            if not isinstance(todo, dict):
                continue
            text = str(todo.get("text") or "").strip()
            if not text:
                continue
            index = todo.get("index")
            suffix = f"[{index}]" if index is not None else ""
            lines.append(f"- {label}_next{suffix}: {text}")

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
        if heartbeat_recommendation.get("spend_policy"):
            lines.append(f"- heartbeat_spend_policy: {heartbeat_recommendation.get('spend_policy')}")
        if heartbeat_recommendation.get("reason"):
            lines.append(f"- heartbeat_reason: {heartbeat_recommendation.get('reason')}")
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
