from __future__ import annotations

import re
from typing import Any, Callable, Optional

from ..todos.contract import (
    TODO_TASK_CLASS_ADVANCEMENT,
    normalize_todo_claimed_by,
    normalize_todo_id,
)
from ..todos.summary_item import compact_todo_summary_item
from ..work_items.interaction_contract import protocol_action_text
from ..work_items.work_lane import work_lane_contract_is_due_monitor_attempt
from .agent_scope import (
    _todo_item_is_actionable_open,
    _todo_task_class,
    agent_scope_item_blocks_agent,
    agent_scope_item_claimed_by,
    agent_scope_item_claimed_by_agent_or_unclaimed,
)
from .capability_gate import _agent_lane_candidate_sort_key


PublicSafeText = Callable[..., Optional[str]]
ActionAlignment = Callable[[Any, Any], bool]
TimestampParser = Callable[[Any], Any]
AGENT_LANE_NEXT_ACTION_SCHEMA_VERSION = "agent_lane_next_action_v0"


def is_status_neutral_run(
    run: dict[str, Any],
    *,
    status_neutral_classifications: set[str],
    agent_lane_progress_scope: str,
) -> bool:
    return (
        str(run.get("classification") or "") in status_neutral_classifications
        or str(run.get("progress_scope") or "") == agent_lane_progress_scope
    )


def latest_agent_lane_run(
    goal: dict[str, Any],
    *,
    agent_lane_progress_scope: str,
) -> dict[str, Any] | None:
    runs = goal.get("latest_runs")
    if not isinstance(runs, list):
        return None
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("progress_scope") or "") == agent_lane_progress_scope:
            return run
    return None


def compact_agent_lane_recommendation(
    run: dict[str, Any] | None,
    *,
    agent_lane_progress_scope: str,
    public_safe_compact_text: PublicSafeText,
) -> dict[str, Any] | None:
    if not isinstance(run, dict):
        return None
    action = public_safe_compact_text(run.get("recommended_action"), limit=220)
    if not action:
        return None
    compact: dict[str, Any] = {
        "schema_version": "agent_lane_recommendation_v0",
        "progress_scope": agent_lane_progress_scope,
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
    preferred_agent_id: str | None = None,
    limit: int = 320,
    public_safe_compact_text: PublicSafeText,
    actions_are_projection_aligned: ActionAlignment,
    parse_timestamp: TimestampParser,
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
    lane_dt = parse_timestamp(agent_lane_recommendation.get("generated_at"))
    latest_dt = parse_timestamp(
        current_status_run.get("generated_at")
        if isinstance(current_status_run, dict)
        else None
    )
    lane_agent_id = str(agent_lane_recommendation.get("agent_id") or "").strip()
    preferred_agent = str(preferred_agent_id or "").strip()
    lane_matches_preferred_agent = bool(
        preferred_agent and lane_agent_id and lane_agent_id == preferred_agent
    )
    lane_is_newer = bool(lane_dt and latest_dt and lane_dt >= latest_dt)
    if lane_is_newer and lane_matches_preferred_agent:
        return lane_action, "agent_lane_recommendation"
    if not active_state_next_action or not actions_are_projection_aligned(
        active_state_next_action,
        lane_action,
    ):
        return latest_action, "latest_status_run" if latest_action else None

    latest_aligned = bool(
        latest_action
        and actions_are_projection_aligned(active_state_next_action, latest_action)
    )
    if not latest_action or not latest_aligned:
        return lane_action, "agent_lane_recommendation"
    return latest_action, "latest_status_run"


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
        text = protocol_action_text(item.get("text"), limit=320)
        if text:
            return text
    return None


def _todo_ids_from_action(value: Any) -> set[str]:
    text = str(value or "")
    if not text:
        return set()
    return set(re.findall(r"\btodo_[A-Za-z0-9_]+\b", text))


def selected_recommended_action_from_work_lane(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
) -> Any:
    raw_action = item.get("recommended_action")
    if work_lane_contract_is_due_monitor_attempt(work_lane_contract):
        due_items = (
            work_lane_contract.get("monitor_due_items")
            if isinstance(work_lane_contract.get("monitor_due_items"), list)
            else []
        )
        for due_item in due_items:
            if not isinstance(due_item, dict):
                continue
            text = protocol_action_text(due_item.get("text"), limit=320)
            if text:
                return text
        return raw_action
    if (
        isinstance(work_lane_contract, dict)
        and work_lane_contract.get("lane") == "advancement_task"
        and "open_agent_todo"
        in (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
    ):
        return _first_executable_todo_text(agent_todo_summary) or raw_action
    return raw_action


def build_agent_lane_next_action(
    *,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    capability_gate: dict[str, Any] | None,
    active_next_action: Any = None,
    scoped_user_gate_fallback: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id or not isinstance(agent_todo_summary, dict):
        return None

    if isinstance(scoped_user_gate_fallback, dict):
        selected = scoped_user_gate_fallback.get("selected_executable")
        if isinstance(selected, dict):
            text = protocol_action_text(selected.get("text"), limit=500)
            claimed_by = agent_scope_item_claimed_by(selected)
            if (
                text
                and _todo_item_is_actionable_open(selected)
                and _todo_task_class(selected) == TODO_TASK_CLASS_ADVANCEMENT
                and agent_scope_item_claimed_by_agent_or_unclaimed(
                    selected,
                    agent_id=agent_id,
                )
            ):
                payload = dict(selected)
                payload.update(
                    {
                        "schema_version": AGENT_LANE_NEXT_ACTION_SCHEMA_VERSION,
                        "agent_id": agent_id,
                        "primary_agent": normalize_todo_claimed_by(
                            agent_identity.get("primary_agent")
                        ),
                        "source": "scoped_user_gate_fallback.selected_executable",
                        "selected_by": "scoped_user_gate_fallback",
                        "confidence": "selected",
                        "preserves_goal_next_action": False,
                        "replaces_gated_goal_next_action": True,
                    }
                )
                if not claimed_by:
                    payload["claim_required_before_work"] = True
                return payload

    candidate_sources: list[tuple[str, list[Any]]] = []
    if isinstance(capability_gate, dict) and capability_gate.get("action") == "run":
        candidate_sources.append(
            (
                "capability_gate.runnable_candidates",
                capability_gate.get("runnable_candidates")
                if isinstance(capability_gate.get("runnable_candidates"), list)
                else [],
            )
        )
    else:
        candidate_sources.append(
            (
                "agent_todo_summary.active_next_action_executable_items",
                agent_todo_summary.get("active_next_action_executable_items")
                if isinstance(
                    agent_todo_summary.get("active_next_action_executable_items"), list
                )
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
    active_next_action_items = (
        agent_todo_summary.get("active_next_action_executable_items")
        if isinstance(agent_todo_summary.get("active_next_action_executable_items"), list)
        else []
    )
    active_next_action_todo_ids = {
        normalize_todo_id(item.get("todo_id"))
        for item in active_next_action_items
        if isinstance(item, dict)
    }

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
            text = protocol_action_text(raw_item.get("text"), limit=500)
            if not text:
                continue
            identity = (str(raw_item.get("todo_id") or ""), text)
            if identity in seen:
                continue
            if not agent_scope_item_claimed_by_agent_or_unclaimed(
                raw_item,
                agent_id=agent_id,
            ):
                continue
            seen.add(identity)
            source_candidates.append(raw_item)
        for raw_item in sorted(
            source_candidates,
            key=lambda candidate: _agent_lane_candidate_sort_key(
                candidate,
                agent_id=agent_id,
                primary_agent=primary_agent,
                preferred_todo_ids=preferred_todo_ids,
            ),
        ):
            text = protocol_action_text(raw_item.get("text"), limit=500)
            claimed_by = agent_scope_item_claimed_by(raw_item)
            todo_id = str(raw_item.get("todo_id") or "").strip()
            selected_by = (
                "active_next_action_todo"
                if todo_id and todo_id in preferred_todo_ids
                else "current_agent_claimed_todo"
                if claimed_by == agent_id
                else "unclaimed_todo"
            )
            payload = compact_todo_summary_item(raw_item, text=text)
            if selected_by == "unclaimed_todo":
                payload["claim_required_before_work"] = True
            lineage_source = source
            if (
                source == "capability_gate.runnable_candidates"
                and selected_by == "active_next_action_todo"
                and normalize_todo_id(todo_id) in active_next_action_todo_ids
            ):
                lineage_source = "agent_todo_summary.active_next_action_executable_items"
            blocks_agent = agent_scope_item_blocks_agent(raw_item)
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
                    "source": lineage_source,
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


def selected_action_with_agent_lane(
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
    if selected_by not in {
        "active_next_action_todo",
        "current_agent_claimed_todo",
        "unclaimed_todo",
    }:
        return selected_action
    if confidence not in {"selected", "candidate"}:
        return selected_action
    lane_text = str(agent_lane_next_action.get("text") or "").strip()
    return lane_text or selected_action
