from __future__ import annotations

import re
from typing import Any

from ..todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    TODO_TASK_CLASS_MONITOR,
    normalize_todo_claimed_by,
    normalize_todo_id,
)
from ..todos.projection import (
    todo_item_is_actionable_open,
    todo_item_task_class,
    todo_summary_claim_scope_agent_id,
    todo_summary_has_only_future_scoped_monitor_work,
    todo_summary_monitor_due_count,
    todo_summary_monitor_items,
    todo_summary_monitor_schedule_gap_count,
)


EXTERNAL_EVIDENCE_OBSERVATION_SCHEMA_VERSION = "external_evidence_observation_obligation_v0"
PROJECTED_MONITOR_HANDLE_SCHEMA_VERSION = "projected_monitor_handle_v0"

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


def todo_summary_open_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    try:
        return max(0, int(summary.get("open_count") or 0))
    except (TypeError, ValueError):
        return 0


def todo_summary_open_task_counts(summary: dict[str, Any] | None) -> dict[str, int]:
    open_count = todo_summary_open_count(summary)
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
                if todo_item_is_actionable_open(item)
                if todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            ]
        raw_monitor_open = summary.get("monitor_open_items")
        if isinstance(raw_monitor_open, list):
            monitor_open_items = [
                item
                for item in raw_monitor_open
                if isinstance(item, dict)
                if todo_item_is_actionable_open(item)
                if todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
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
            if todo_item_is_actionable_open(item)
            and todo_item_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
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
            if todo_item_is_actionable_open(item)
            and todo_item_task_class(item) == TODO_TASK_CLASS_MONITOR
        )
    hidden_count = max(0, open_count - len(classified_items))
    return {
        "open": open_count,
        "advancement": advancement_count,
        "monitor": monitor_visible_count,
        "monitor_due": todo_summary_monitor_due_count(summary),
        "monitor_schedule_gap": todo_summary_monitor_schedule_gap_count(summary),
        "hidden": hidden_count,
    }


def projected_monitor_handle(summary: dict[str, Any] | None) -> dict[str, Any] | None:
    for item in todo_summary_monitor_items(summary):
        target_key = str(item.get("target_key") or "").strip()
        if not target_key:
            continue
        handle: dict[str, Any] = {
            "schema_version": PROJECTED_MONITOR_HANDLE_SCHEMA_VERSION,
            "target_key": target_key,
        }
        todo_id = normalize_todo_id(item.get("todo_id"))
        if todo_id:
            handle["todo_id"] = todo_id
        claimed_by = normalize_todo_claimed_by(item.get("claimed_by"))
        if claimed_by:
            handle["claimed_by"] = claimed_by
        next_due_at = str(item.get("next_due_at") or "").strip()
        if next_due_at:
            handle["next_due_at"] = next_due_at
        target_text = str(item.get("title") or item.get("text") or "").strip()
        if target_text:
            handle["target_text"] = target_text[:320]
        return handle
    return None


def scoped_monitor_watch_without_advancement(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False
    if not todo_summary_claim_scope_agent_id(summary):
        return False
    if not todo_summary_monitor_items(summary):
        return False
    return todo_summary_open_task_counts(summary).get("advancement", 0) <= 0


def build_external_evidence_poll_signal(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Detect launched external work whose next safe step is observation."""

    if (
        isinstance(agent_todo_summary, dict)
        and todo_summary_claim_scope_agent_id(agent_todo_summary)
        and todo_summary_open_count(agent_todo_summary) <= 0
    ):
        return None

    scoped_monitor_handle = projected_monitor_handle(agent_todo_summary)
    scoped_monitor_watch = scoped_monitor_watch_without_advancement(agent_todo_summary)
    if todo_summary_has_only_future_scoped_monitor_work(agent_todo_summary):
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
    if scoped_monitor_watch and not scoped_monitor_handle:
        return None
    if (
        scoped_monitor_watch
        and todo_summary_monitor_due_count(agent_todo_summary) <= 0
        and todo_summary_monitor_schedule_gap_count(agent_todo_summary) <= 0
    ):
        return None

    scoped_monitor_target = (
        str(scoped_monitor_handle.get("target_text") or "").strip()
        if isinstance(scoped_monitor_handle, dict)
        else ""
    )
    observation_target = scoped_monitor_target or next(
        (text for text in action_texts if text),
        None,
    ) or next((text for text in todo_texts if text), "")
    signal = {
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
    if scoped_monitor_handle:
        signal["monitor_handle"] = scoped_monitor_handle
    return signal


def build_external_evidence_observation_obligation(
    item: dict[str, Any],
    *,
    state: str,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Return the machine contract for a waiting external-evidence monitor."""

    explicit_wait = state == "waiting" and str(item.get("waiting_on") or "") == "external_evidence"
    poll_signal = build_external_evidence_poll_signal(item, agent_todo_summary=agent_todo_summary)
    if not explicit_wait and not poll_signal:
        return None
    if (
        not explicit_wait
        and poll_signal
        and isinstance(agent_todo_summary, dict)
        and todo_summary_claim_scope_agent_id(agent_todo_summary)
        and todo_summary_open_count(agent_todo_summary) <= 0
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

    obligation = {
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
        "observation_target": _compact_protocol_text(observation_target, limit=320),
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
    monitor_handle = poll_signal.get("monitor_handle") if isinstance(poll_signal, dict) else None
    if isinstance(monitor_handle, dict) and monitor_handle:
        obligation["monitor_handle"] = monitor_handle
    return obligation


def _compact_protocol_text(value: Any, *, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
