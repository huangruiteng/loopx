from __future__ import annotations

from copy import deepcopy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_COMPUTE_QUOTA = 1.0
DEFAULT_WINDOW_HOURS = 24
QUOTA_STATE_ORDER = (
    "blocked_health",
    "operator_gate",
    "eligible",
    "waiting",
    "throttled",
    "paused",
)
QUOTA_SLOT_SPENT_CLASSIFICATION = "quota_slot_spent"
DEFAULT_SLOT_SPEND_SOURCE = "heartbeat"
VALID_SLOT_SPEND_SOURCES = {"heartbeat", "controller", "adapter"}


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


def goal_quota_config(goal: dict[str, Any] | None) -> dict[str, Any]:
    raw = goal.get("quota") if goal and isinstance(goal.get("quota"), dict) else {}
    if goal and "compute_quota" in goal and "compute" not in raw:
        raw = {**raw, "compute": goal.get("compute_quota")}
    compute = _clamp_compute(_number(raw.get("compute"), default=DEFAULT_COMPUTE_QUOTA))
    window_hours = max(1, _int_number(raw.get("window_hours"), default=DEFAULT_WINDOW_HOURS))
    spent_slots = max(0, _int_number(raw.get("spent_slots"), default=0))
    allowed_slots = max(0, _int_number(raw.get("allowed_slots"), default=round(window_hours * compute)))
    payload: dict[str, Any] = {
        "compute": compute,
        "window_hours": window_hours,
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
        reason = "human or target-controller gate must clear before spending compute"
    elif waiting_on == "external_evidence":
        state = "waiting"
        reason = "external evidence is still pending; do not spend delivery compute yet"
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
        latest = _latest_run(goal)
        quota = attention.get("quota") if isinstance(attention.get("quota"), dict) else goal.get("quota")
        quota = quota if isinstance(quota, dict) else quota_status(goal)
        state = str(quota.get("state") or "waiting")
        item: dict[str, Any] = {
            "goal_id": goal_id,
            "status": attention.get("status") or goal.get("status"),
            "lifecycle_phase": attention.get("lifecycle_phase") or goal.get("lifecycle_phase"),
            "waiting_on": attention.get("waiting_on") or "none",
            "severity": attention.get("severity") or "info",
            "source": attention.get("source") or "run_history",
            "recommended_action": attention.get("recommended_action") or latest.get("recommended_action"),
            "adapter_kind": goal.get("adapter_kind"),
            "adapter_status": goal.get("adapter_status"),
            "latest_run_generated_at": latest.get("generated_at"),
            "quota": quota,
        }
        for optional_field in (
            "operator_question",
            "agent_command",
            "controller_stage",
            "missing_gates",
            "next_handoff_condition",
        ):
            if optional_field in attention:
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
        should_run = bool(plan.get("ok")) and state == "eligible"
        reason = str(quota.get("reason") or "quota state is not eligible")
        if not plan.get("ok"):
            reason = "status or contract health is not ok; skip automatic compute"
        payload = {
            "ok": bool(plan.get("ok")),
            "mode": "should-run",
            "goal_id": safe_goal_id,
            "decision": "run" if should_run else "skip",
            "should_run": should_run,
            "reason": reason,
            "quota": quota,
            "state": state,
            "waiting_on": item.get("waiting_on"),
            "status": item.get("status"),
            "source": item.get("source"),
            "recommended_action": item.get("recommended_action"),
            "plan_summary": plan.get("summary"),
        }
        if item.get("next_handoff_condition"):
            payload["next_handoff_condition"] = item.get("next_handoff_condition")
        if item.get("agent_command"):
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


def build_quota_slot_preview(
    status_payload: dict[str, Any],
    *,
    goal_id: str,
    slots: int = 1,
) -> dict[str, Any]:
    safe_goal_id = str(goal_id or "").strip()
    safe_slots = max(1, _int_number(slots, default=1))
    before = build_quota_should_run(status_payload, goal_id=safe_goal_id)
    if not before.get("ok") or not before.get("should_run"):
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
    }


def _compact_quota_decision(decision: dict[str, Any]) -> dict[str, Any]:
    quota = decision.get("quota") if isinstance(decision.get("quota"), dict) else {}
    return {
        "should_run": bool(decision.get("should_run")),
        "state": str(decision.get("state") or ""),
        "compute": quota.get("compute"),
        "window_hours": quota.get("window_hours"),
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
    if before_compact["should_run"] is not True or before_compact["state"] != "eligible":
        raise ValueError("quota slot spend requires a fresh eligible quota should-run decision")
    if _int_number(after_compact.get("spent_slots"), default=0) != _int_number(
        before_compact.get("spent_slots"), default=0
    ) + slots:
        raise ValueError("after.spent_slots must equal before.spent_slots + slots")

    return {
        "generated_at": generated_at or _now_local(),
        "goal_id": preview.get("goal_id"),
        "classification": QUOTA_SLOT_SPENT_CLASSIFICATION,
        "recommended_action": after.get("recommended_action") or "inspect next quota should-run decision",
        "health_check": "quota should-run eligible; quota slot spend event public-safe",
        "quota_event": {
            "event_type": QUOTA_SLOT_SPENT_CLASSIFICATION,
            "source": safe_source,
            "slots": slots,
            "reason_summary": f"{slots} automatic agent slot(s) completed under an eligible quota guard",
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
    json_path = runs_dir / f"{stem}.json"
    markdown_path = runs_dir / f"{stem}.md"
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
        f"- state: `{payload.get('state')}`",
        f"- waiting_on: `{payload.get('waiting_on')}`",
        f"- status: `{payload.get('status')}`",
    ]
    if quota:
        lines.append(
            "- quota: "
            f"compute={quota.get('compute')} "
            f"slots={quota.get('spent_slots')}/{quota.get('allowed_slots')}"
        )
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
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
