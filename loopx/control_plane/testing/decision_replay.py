from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..scheduler.scheduler_hint import build_scheduler_hint
from ..todos.decision_scope import build_required_decision_scope_consistency


PUBLIC_SAFE_DECISION_REPLAY_SCHEMA_VERSION = "public_safe_decision_replay_v0"
PUBLIC_SAFE_DECISION_CASE_SCHEMA_VERSION = "public_safe_decision_case_v0"
_SUMMARY_KEYS = (
    "current_agent_claimed_open_items",
    "first_executable_items",
    "deferred_resume_candidates",
    "gate_open_items",
    "user_action_items",
    "other_agent_scoped_items",
    "first_open_items",
    "backlog_items",
)
_TODO_FIELDS = (
    "todo_id",
    "status",
    "task_class",
    "action_kind",
    "claimed_by",
    "blocks_agent",
    "global_gate",
    "decision_scope",
    "required_decision_scopes",
    "resume_when",
    "resume_ready",
)
_BANNED_KEYS = frozenset(
    {
        "credential",
        "credentials",
        "raw_log",
        "raw_logs",
        "raw_state",
        "trajectory",
        "trajectories",
        "verifier_output",
    }
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _compact_todo(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: item[field]
        for field in _TODO_FIELDS
        if item.get(field) is not None
    }


def _compact_summary(summary: Any) -> list[dict[str, Any]]:
    source = _mapping(summary)
    items: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for key in _SUMMARY_KEYS:
        values = source.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, Mapping):
                continue
            identity = (value.get("todo_id"), value.get("task_class"), value.get("status"))
            if identity in seen:
                continue
            seen.add(identity)
            compact = _compact_todo(value)
            if compact:
                items.append(compact)
    return items


def reduce_public_safe_decision(
    payload: Mapping[str, Any],
    *,
    case_id: str,
) -> dict[str, Any]:
    interaction = _mapping(payload.get("interaction_contract"))
    user_channel = _mapping(interaction.get("user_channel"))
    agent_channel = _mapping(interaction.get("agent_channel"))
    scheduler = _mapping(payload.get("scheduler_hint"))
    codex_app = _mapping(scheduler.get("codex_app"))
    selected_todo = _mapping(payload.get("selected_todo"))
    reduced = {
        "schema_version": PUBLIC_SAFE_DECISION_CASE_SCHEMA_VERSION,
        "case_id": str(case_id),
        "agent_id": str(_mapping(payload.get("agent_identity")).get("agent_id") or "replay-agent"),
        "decision": {
            "should_run": payload.get("should_run") is True,
            "effective_action": payload.get("effective_action"),
            "normal_delivery_allowed": payload.get("normal_delivery_allowed") is True,
            "recovery_delivery_allowed": payload.get("recovery_delivery_allowed") is True,
            "self_repair_allowed": payload.get("self_repair_allowed") is True,
        },
        "selected_todo": _compact_todo(selected_todo),
        "agent_todos": _compact_summary(payload.get("agent_todo_summary")),
        "user_todos": _compact_summary(payload.get("user_todo_summary")),
        "interaction_contract": {
            "schema_version": interaction.get("schema_version"),
            "mode": interaction.get("mode"),
            "user_channel": {
                field: user_channel[field]
                for field in ("action_required", "notify", "non_blocking")
                if user_channel.get(field) is not None
            },
            "agent_channel": {
                field: agent_channel[field]
                for field in ("must_attempt", "delivery_allowed", "quiet_noop_allowed")
                if agent_channel.get(field) is not None
            },
        },
        "expected": {
            "scheduler_action": scheduler.get("action"),
            "scheduler_cadence_class": scheduler.get("cadence_class"),
            "scheduler_reason_code": scheduler.get("reason_code"),
            "scheduler_interval_minutes": codex_app.get("recommended_interval_minutes"),
            "decision_scope_status": (
                _mapping(payload.get("todo_decision_scope_consistency")).get("status")
                or "consistent"
            ),
        },
    }
    validate_public_safe_decision_case(reduced)
    return reduced


def _walk(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key), child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def validate_public_safe_decision_case(case: Mapping[str, Any]) -> None:
    if case.get("schema_version") != PUBLIC_SAFE_DECISION_CASE_SCHEMA_VERSION:
        raise ValueError("decision replay case schema_version mismatch")
    for key, value in _walk(case):
        if key.lower() in _BANNED_KEYS:
            raise ValueError(f"decision replay contains banned key: {key}")
        if isinstance(value, str) and (value.startswith("/") or "file://" in value):
            raise ValueError(f"decision replay contains a local path in {key}")


def load_public_safe_decision_replay(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != PUBLIC_SAFE_DECISION_REPLAY_SCHEMA_VERSION:
        raise ValueError("decision replay schema_version mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("decision replay requires at least one case")
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("decision replay cases must be objects")
        validate_public_safe_decision_case(case)
    return payload


def replay_public_safe_decision_case(case: Mapping[str, Any]) -> dict[str, Any]:
    validate_public_safe_decision_case(case)
    decision = _mapping(case.get("decision"))
    interaction = _mapping(case.get("interaction_contract"))
    agent_id = str(case.get("agent_id") or "replay-agent")
    payload = {
        "goal_id": str(case.get("case_id") or "decision-replay"),
        "agent_identity": {"agent_id": agent_id},
        "should_run": decision.get("should_run") is True,
        "effective_action": decision.get("effective_action"),
        "recommended_action": "Replay the compact public-safe decision.",
        "heartbeat_recommendation": {
            "recommended_mode": interaction.get("mode"),
            "notify": _mapping(interaction.get("user_channel")).get("notify", "DONT_NOTIFY"),
            "spend_policy": "spend only after validated writeback",
        },
        "execution_obligation": {
            "must_attempt_work": _mapping(interaction.get("agent_channel")).get("must_attempt")
            is True,
            "spend_policy": "spend only after validated writeback",
        },
        "automation_liveness": {
            "automation_action": "",
            "spend_policy": "spend only after validated writeback",
        },
        "interaction_contract": interaction,
    }
    scheduler = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions={
            "agent_scope_exhausted",
            "agent_scope_wait",
            "reassignment_required",
            "successor_replan_required",
        },
    )
    scope_consistency = build_required_decision_scope_consistency(
        {"first_open_items": list(case.get("agent_todos") or [])},
        {"first_open_items": list(case.get("user_todos") or [])},
        agent_id=agent_id,
    )
    return {
        "scheduler_action": scheduler.get("action"),
        "scheduler_cadence_class": scheduler.get("cadence_class"),
        "scheduler_reason_code": scheduler.get("reason_code"),
        "scheduler_interval_minutes": _mapping(scheduler.get("codex_app")).get(
            "recommended_interval_minutes"
        ),
        "decision_scope_status": scope_consistency.get("status"),
    }
