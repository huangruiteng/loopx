from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


MULTI_AGENT_COLLECTIVE_ROUND_LEDGER_SCHEMA_VERSION = (
    "multi_agent_collective_round_ledger_v0"
)


def _string(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _dicts(values: Iterable[object] | None) -> list[dict[str, Any]]:
    return [dict(item) for item in values or [] if isinstance(item, Mapping)]


def _lane_key(lane: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        _string(lane.get("agent_id")),
        _string(lane.get("lane_id")),
        _string(lane.get("role_id")),
    )


def _normalize_lane(lane: Mapping[str, object]) -> dict[str, object]:
    return {
        "agent_id": _string(lane.get("agent_id")),
        "lane_id": _string(lane.get("lane_id")),
        "role_id": _string(lane.get("role_id")),
    }


def _normalize_outcome(outcome: Mapping[str, object]) -> dict[str, object]:
    completion_status = _string(outcome.get("completion_status"))
    executed = _bool_or_none(outcome.get("executed"))
    return {
        "round": _int_or_none(outcome.get("round")),
        "agent_id": _string(outcome.get("agent_id")),
        "lane_id": _string(outcome.get("lane_id")),
        "role_id": _string(outcome.get("role_id")),
        "selected_todo_id": _string(outcome.get("selected_todo_id")),
        "selected_action": _string(outcome.get("selected_action")),
        "executed": executed,
        "completion_status": completion_status or None,
        "completed": executed is True or completion_status == "done",
        "dev_metric": _number_or_none(outcome.get("dev_metric")),
        "holdout_metric": _number_or_none(outcome.get("holdout_metric")),
        "appended_count": _int_or_none(outcome.get("appended_count")),
        "successor_todo_declared": bool(outcome.get("successor_todo_declared")),
    }


def _derive_lanes(outcomes: list[dict[str, object]]) -> list[dict[str, object]]:
    lanes: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for outcome in outcomes:
        lane = _normalize_lane(outcome)
        key = _lane_key(lane)
        if key == ("", "", "") or key in seen:
            continue
        seen.add(key)
        lanes.append(lane)
    return lanes


def _normalize_successor(todo: Mapping[str, object]) -> dict[str, object]:
    return {
        "todo_id": _string(todo.get("todo_id")),
        "target_agent_id": _string(todo.get("target_agent_id") or todo.get("claimed_by")),
        "target_role_id": _string(todo.get("target_role_id")),
        "source_todo_id": _string(todo.get("source_todo_id") or todo.get("unblocks_todo_id")),
        "action_kind": _string(todo.get("action_kind")),
    }


def build_multi_agent_collective_round_ledger(
    *,
    source: str,
    expected_lanes: Iterable[object] | None = None,
    lane_outcomes: Iterable[object] | None = None,
    integrated_evidence: Mapping[str, object] | None = None,
    role_declared_successor_todos: Iterable[object] | None = None,
) -> dict[str, object]:
    """Build a domain-neutral ledger for decentralized multi-agent rounds.

    A collective round is only an observation over normal LoopX state: each lane
    gets a chance to read its own quota/frontier and run one bounded turn. This
    helper deliberately does not select work, wake panes, write todos, or decide
    promotion. Product presets may wrap the ledger with domain-specific metrics.
    """

    outcomes = [_normalize_outcome(item) for item in _dicts(lane_outcomes)]
    lanes = [_normalize_lane(item) for item in _dicts(expected_lanes)]
    if not lanes:
        lanes = _derive_lanes(outcomes)
    evidence = dict(integrated_evidence or {})
    successors = [
        _normalize_successor(item) for item in _dicts(role_declared_successor_todos)
    ]
    round_indexes = sorted(
        {
            int(outcome["round"])
            for outcome in outcomes
            if isinstance(outcome.get("round"), int) and outcome.get("executed") is True
        }
    )
    completed_outcomes = [
        outcome for outcome in outcomes if outcome.get("completed") is True
    ]
    evidence_event_count = _int_or_none(evidence.get("evidence_event_count"))
    if evidence_event_count is None:
        evidence_events = evidence.get("events")
        evidence_event_count = len(evidence_events) if isinstance(evidence_events, list) else 0
    return {
        "schema_version": MULTI_AGENT_COLLECTIVE_ROUND_LEDGER_SCHEMA_VERSION,
        "source": _string(source, default="unknown"),
        "coordination_model": "decentralized_state_a2a",
        "round_unit": "collective_agent_pass",
        "definition": (
            "one collective round means each expected lane has one normal "
            "LoopX quota/frontier/turn opportunity; pane-local tick loops are "
            "evidence, not a central workflow"
        ),
        "expected_lanes": lanes,
        "expected_lane_count": len(lanes),
        "lane_outcomes": outcomes,
        "lane_outcome_count": len(outcomes),
        "completed_lane_turn_count": len(completed_outcomes),
        "collective_round_indexes": round_indexes,
        "collective_round_count": len(round_indexes),
        "multi_round_interaction_verified": len(round_indexes) >= 2,
        "integrated_evidence": {
            "loaded": bool(evidence),
            "evidence_event_count": evidence_event_count,
            "dev_metric": _number_or_none(evidence.get("dev_metric")),
            "holdout_metric": _number_or_none(evidence.get("holdout_metric")),
            "result_status": _string(evidence.get("result_status")),
            "protected_scope_clean": _bool_or_none(evidence.get("protected_scope_clean")),
        },
        "role_declared_successor_todos": successors,
        "successor_todo_count": len(successors),
        "source_of_truth": [
            "loopx_quota_should_run",
            "agent_scoped_frontier",
            "todo_claims",
            "public_safe_evidence",
        ],
        "owner_layer": "generic_multi_agent_kernel",
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
        },
    }
