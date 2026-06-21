from __future__ import annotations

from typing import Any, Mapping, Sequence


SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION = (
    "session_runtime_readonly_projection_v0"
)

RAW_MATERIAL_KEY_HINTS = (
    "credential",
    "local_path",
    "log",
    "raw",
    "secret",
    "stderr",
    "stdout",
    "token",
    "trace",
    "transcript",
)

SOURCE_ID_KEYS = (
    "session_id",
    "event_id",
    "outcome_id",
    "gate_id",
    "approval_id",
    "artifact_id",
    "tool_call_id",
    "run_id",
    "ref_id",
)

OPEN_GATE_STATUSES = {
    "blocked",
    "needs_decision",
    "open",
    "pending",
    "requested",
    "requires_decision",
    "waiting",
}

HUMAN_GATE_ACTORS = {"controller", "human", "operator", "owner", "user"}
BLOCKED_STATUSES = {"blocked", "error", "failed", "timed_out"}
VALIDATED_STATUSES = {"ok", "passed", "success", "validated"}


def _as_mappings(values: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    if not values:
        return []
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _text(value: Any, *, limit: int = 180) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _first_text(item: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    for key in keys:
        text = _text(item.get(key))
        if text:
            return text
    return None


def _status(item: Mapping[str, Any]) -> str:
    return str(item.get("status") or item.get("state") or "").strip().lower()


def _actor(item: Mapping[str, Any]) -> str:
    return str(
        item.get("actor")
        or item.get("required_actor")
        or item.get("decision_actor")
        or item.get("channel")
        or ""
    ).strip().lower()


def _is_human_gate(item: Mapping[str, Any]) -> bool:
    status = _status(item)
    actor = _actor(item)
    return status in OPEN_GATE_STATUSES and (
        actor in HUMAN_GATE_ACTORS
        or bool(item.get("requires_human_decision"))
        or bool(item.get("action_required"))
    )


def _is_blocking_gate(item: Mapping[str, Any]) -> bool:
    if not _is_human_gate(item):
        return False
    if item.get("advisory") is True:
        return False
    return item.get("blocking", True) is not False


def _is_blocker(item: Mapping[str, Any]) -> bool:
    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
    return kind == "blocker" or _status(item) in BLOCKED_STATUSES


def _is_validation(item: Mapping[str, Any]) -> bool:
    kind = str(item.get("kind") or item.get("type") or "").strip().lower()
    return kind in {"validation", "outcome"} and _status(item) in VALIDATED_STATUSES


def _latest(items: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return max(
        (dict(item) for item in items),
        key=lambda item: str(
            item.get("created_at")
            or item.get("event_at")
            or item.get("updated_at")
            or item.get("timestamp")
            or ""
        ),
    )


def _source_ref(item: Mapping[str, Any], *, default_kind: str) -> dict[str, Any]:
    ref: dict[str, Any] = {
        "kind": _text(item.get("kind") or item.get("type") or default_kind, limit=60)
        or default_kind
    }
    for key in SOURCE_ID_KEYS:
        value = _text(item.get(key), limit=120)
        if value:
            ref[key] = value
    return ref


def _source_refs(
    *,
    sessions: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
    gates: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, Any]],
    decision_results: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "sessions": [_source_ref(item, default_kind="session") for item in sessions],
        "events": [_source_ref(item, default_kind="event") for item in events],
        "outcomes": [_source_ref(item, default_kind="outcome") for item in outcomes],
        "gates": [_source_ref(item, default_kind="gate") for item in gates],
        "artifacts": [_source_ref(item, default_kind="artifact") for item in artifacts],
        "decision_results": [
            _source_ref(item, default_kind="decision_result")
            for item in decision_results
        ],
    }


def _raw_material_keys(*groups: Sequence[Mapping[str, Any]]) -> list[str]:
    keys: set[str] = set()
    for group in groups:
        for item in group:
            for key in item:
                lowered = str(key).lower()
                if any(hint in lowered for hint in RAW_MATERIAL_KEY_HINTS):
                    keys.add(str(key))
    return sorted(keys)


def _first_user_todo(gate: Mapping[str, Any] | None) -> str | None:
    if gate is None:
        return None
    return _first_text(
        gate,
        (
            "question",
            "requested_decision",
            "title",
            "summary",
            "message",
            "next_action",
        ),
    )


def _first_agent_todo(
    *,
    decision_results: Sequence[Mapping[str, Any]],
    sessions: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> str | None:
    for group in (decision_results, sessions, events, outcomes):
        for item in group:
            text = _first_text(
                item,
                (
                    "recommended_action",
                    "agent_next_action",
                    "next_action",
                    "handoff",
                    "summary",
                ),
            )
            if text:
                return text
    return None


def _latest_validation(
    outcomes: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]]
) -> str | None:
    candidates = [
        item
        for item in [*outcomes, *events]
        if _is_validation(item)
        or _first_text(item, ("validation_summary", "validated", "result"))
    ]
    latest = _latest(candidates)
    if latest is None:
        return None
    return _first_text(
        latest,
        ("validation_summary", "validated", "result", "summary", "message"),
    )


def _latest_blocker(
    gates: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
) -> str | None:
    candidates = [
        item
        for item in [*gates, *outcomes, *events]
        if _is_blocker(item) or _first_text(item, ("blocker", "blocker_summary"))
    ]
    latest = _latest(candidates)
    if latest is None:
        return None
    return _first_text(
        latest,
        ("blocker", "blocker_summary", "summary", "message", "title"),
    )


def _waiting_on(
    *,
    blocking_gate: Mapping[str, Any] | None,
    blocker: str | None,
    first_agent_todo: str | None,
) -> str:
    if blocking_gate is not None:
        actor = _actor(blocking_gate)
        return actor if actor in HUMAN_GATE_ACTORS else "operator"
    if blocker and not first_agent_todo:
        return "runtime"
    if first_agent_todo:
        return "agent"
    return "none"


def _lane(
    *,
    blocking_gate: Mapping[str, Any] | None,
    blocker: str | None,
    first_agent_todo: str | None,
) -> str:
    if blocking_gate is not None:
        return "user_gate"
    if blocker and not first_agent_todo:
        return "blocker"
    if first_agent_todo:
        return "advancement_task"
    return "monitor"


def build_session_runtime_readonly_projection(
    *,
    goal_id: str,
    sessions: Sequence[Mapping[str, Any]] | None = None,
    events: Sequence[Mapping[str, Any]] | None = None,
    outcomes: Sequence[Mapping[str, Any]] | None = None,
    gates: Sequence[Mapping[str, Any]] | None = None,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    decision_results: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Project compact session-runtime facts into a LoopX first screen.

    This adapter is intentionally read-only. It consumes only compact summaries
    and source pointers, never raw transcripts, logs, credentials, or local
    paths. If raw-looking keys are present, the projection records a boundary
    violation without copying their values.
    """

    session_items = _as_mappings(sessions)
    event_items = _as_mappings(events)
    outcome_items = _as_mappings(outcomes)
    gate_items = _as_mappings(gates)
    artifact_items = _as_mappings(artifacts)
    decision_items = _as_mappings(decision_results)

    blocking_gate = next((gate for gate in gate_items if _is_blocking_gate(gate)), None)
    user_todo = _first_user_todo(blocking_gate)
    agent_todo = _first_agent_todo(
        decision_results=decision_items,
        sessions=session_items,
        events=event_items,
        outcomes=outcome_items,
    )
    validation = _latest_validation(outcome_items, event_items)
    blocker = _latest_blocker(gate_items, outcome_items, event_items)
    waiting = _waiting_on(
        blocking_gate=blocking_gate,
        blocker=blocker,
        first_agent_todo=agent_todo,
    )
    lane = _lane(
        blocking_gate=blocking_gate,
        blocker=blocker,
        first_agent_todo=agent_todo,
    )
    raw_keys = _raw_material_keys(
        session_items,
        event_items,
        outcome_items,
        gate_items,
        artifact_items,
        decision_items,
    )
    latest_event = _latest([*session_items, *event_items, *outcome_items])
    source_refs = _source_refs(
        sessions=session_items,
        events=event_items,
        outcomes=outcome_items,
        gates=gate_items,
        artifacts=artifact_items,
        decision_results=decision_items,
    )

    can_continue = bool(agent_todo and blocking_gate is None and not raw_keys)
    recommended_action = (
        "provide compact summaries without raw material before projection"
        if raw_keys
        else user_todo
        if blocking_gate is not None
        else agent_todo
        if agent_todo
        else "monitor for a material transition"
    )

    return {
        "schema_version": SESSION_RUNTIME_READONLY_PROJECTION_SCHEMA_VERSION,
        "goal_id": str(goal_id),
        "mode": "read_only",
        "source": {
            "host_kind": "session_runtime",
            "source_refs": source_refs,
            "latest_fact_at": _text(
                latest_event.get("created_at")
                or latest_event.get("event_at")
                or latest_event.get("updated_at")
                or latest_event.get("timestamp"),
                limit=80,
            )
            if latest_event
            else None,
        },
        "boundary": {
            "raw_transcript_copied": False,
            "raw_logs_copied": False,
            "credentials_copied": False,
            "runtime_writeback_allowed": False,
            "runtime_mutation_allowed": False,
            "raw_material_detected": bool(raw_keys),
            "raw_material_key_names": raw_keys,
        },
        "first_screen": {
            "waiting_on": waiting,
            "user_action_required": blocking_gate is not None,
            "agent_can_continue": can_continue,
            "first_user_todo": user_todo,
            "first_agent_todo": agent_todo if blocking_gate is None else None,
            "latest_validation": validation,
            "latest_blocker": blocker,
            "gate_state": _status(blocking_gate) if blocking_gate else "none",
            "recommended_action": recommended_action,
        },
        "work_lane_contract": {
            "lane": lane,
            "must_attempt_work": can_continue,
            "user_gate_blocks_delivery": blocking_gate is not None,
            "monitor_only": lane == "monitor",
        },
        "attention_item": {
            "kind": lane,
            "priority": "P0" if lane in {"user_gate", "blocker"} else "P1",
            "title": recommended_action,
            "waiting_on": waiting,
            "evidence_refs": source_refs,
        },
        "reconcile_rule": {
            "raw_fact_source": "host_session_log",
            "compact_projection_source": "loopx_run_projection",
            "conflict_policy": (
                "recompute projection from compact source refs; do not copy raw "
                "transcripts, raw logs, credentials, billing records, or sandbox "
                "internals into LoopX state"
            ),
        },
    }
