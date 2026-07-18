from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from ..scheduler.execution_context import (
    scheduler_execution_context_for_runtime_profile,
)
from ...quota import build_quota_should_run
from .quota_fixtures import quota_status_payload, quota_todo_item, quota_todo_summary


PUBLIC_SAFE_DECISION_REPLAY_SCHEMA_VERSION = "public_safe_decision_replay_v0"
PUBLIC_SAFE_DECISION_CASE_SCHEMA_VERSION = "public_safe_decision_case_v0"
_SUMMARY_KEYS = (
    "current_agent_claimed_open_items",
    "first_executable_items",
    "deferred_resume_candidates",
    "gate_open_items",
    "user_action_items",
    "other_agent_bound_user_action_items",
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
    "bound_agent",
    "goal_bound",
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


def _walk(value: Any) -> Iterator[tuple[str, Any]]:
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
    if case.get("scenario") is not None:
        if not str(case.get("invariant_id") or "").strip():
            raise ValueError("decision replay case requires invariant_id")
        if not str(case.get("rationale") or "").strip():
            raise ValueError("decision replay case requires rationale")
    for key, value in _walk(case):
        if key.lower() in _BANNED_KEYS:
            raise ValueError(f"decision replay contains banned key: {key}")
        if isinstance(value, str) and (value.startswith("/") or "file://" in value):
            raise ValueError(f"decision replay contains a local path in {key}")


def load_public_safe_decision_replay(path: Path) -> dict[str, Any]:
    payload_raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, dict):
        raise ValueError("decision replay root must be an object")
    payload: dict[str, Any] = payload_raw
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


def _source_todo_item(
    value: Mapping[str, Any],
    *,
    role: str,
    index: int,
) -> dict[str, Any]:
    metadata = dict(value)
    todo_id = str(metadata.pop("todo_id", "") or f"todo_{role}_{index}")
    status = str(metadata.pop("status", "open") or "open")
    task_class = str(
        metadata.pop(
            "task_class",
            "user_action" if role == "user" else "advancement_task",
        )
    )
    claimed_by = metadata.pop("claimed_by", None)
    blocks_agent = metadata.pop("blocks_agent", None)
    action_kind = metadata.pop("action_kind", None)
    return cast(
        dict[str, Any],
        quota_todo_item(
            todo_id=todo_id,
            index=index,
            role=role,
            status=status,
            task_class=task_class,
            text=f"[P1] Public-safe replay item {todo_id}.",
            claimed_by=str(claimed_by) if claimed_by else None,
            blocks_agent=str(blocks_agent) if blocks_agent else None,
            action_kind=str(action_kind) if action_kind else None,
            **metadata,
        ),
    )


def replay_public_safe_decision_case(case: Mapping[str, Any]) -> dict[str, Any]:
    validate_public_safe_decision_case(case)
    agent_id = str(case.get("agent_id") or "replay-agent")
    goal_id = str(case.get("case_id") or "decision-replay")
    scenario = _mapping(case.get("scenario"))
    agent_items = [
        _source_todo_item(item, role="agent", index=index)
        for index, item in enumerate(case.get("agent_todos") or [], start=1)
        if isinstance(item, Mapping)
    ]
    user_items = [
        _source_todo_item(item, role="user", index=index)
        for index, item in enumerate(case.get("user_todos") or [], start=1)
        if isinstance(item, Mapping)
    ]
    status = quota_status_payload(
        goal_id=goal_id,
        status="active",
        recommended_action="Replay the reviewed public-safe decision invariant.",
        agent_todos=quota_todo_summary(
            agent_items,
            role="agent",
            claim_scope_agent_id=agent_id,
        ),
        user_todos=quota_todo_summary(user_items, role="user"),
        quota_state=str(scenario.get("quota_state") or "eligible"),
        safe_bypass=scenario.get("safe_bypass") is True,
        coordination={"agent_model": "peer_v1", "registered_agents": [agent_id]},
    )
    runtime_profile = str(scenario.get("scheduler_runtime_profile") or "").strip()
    scheduler_execution_context = (
        scheduler_execution_context_for_runtime_profile(runtime_profile)
        if runtime_profile
        else None
    )
    payload = build_quota_should_run(
        status,
        goal_id=goal_id,
        agent_id=agent_id,
        scheduler_execution_context=scheduler_execution_context,
    )
    reduced = reduce_public_safe_decision(payload, case_id=goal_id)
    return {
        "decision": reduced["decision"],
        "selected_todo": reduced["selected_todo"],
        "interaction_contract": reduced["interaction_contract"],
        "expected": reduced["expected"],
    }
