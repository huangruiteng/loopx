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


def _number_list(values: object) -> list[float]:
    if not isinstance(values, list):
        return []
    numbers: list[float] = []
    for value in values:
        number = _number_or_none(value)
        if number is not None:
            numbers.append(number)
    return numbers


def _improvement_count(metrics: list[float], *, baseline: float) -> int:
    previous = baseline
    count = 0
    for metric in metrics:
        if metric > previous:
            count += 1
        previous = metric
    return count


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
    round_index = _int_or_none(outcome.get("round"))
    if round_index is None:
        round_index = _int_or_none(outcome.get("round_index"))
    selected_todo_id = _string(outcome.get("selected_todo_id"))
    selected_action = _string(outcome.get("selected_action"))
    productive_turn = bool(selected_todo_id or selected_action)
    return {
        "round": round_index,
        "agent_id": _string(outcome.get("agent_id")),
        "lane_id": _string(outcome.get("lane_id")),
        "role_id": _string(outcome.get("role_id")),
        "selected_todo_id": selected_todo_id,
        "selected_action": selected_action,
        "executed": executed,
        "completion_status": completion_status or None,
        "completed": productive_turn and (executed is True or completion_status == "done"),
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


def summarize_multi_agent_pane_tick_artifacts(
    artifacts: Iterable[object],
) -> dict[str, object]:
    """Compact pane-local tick artifacts into generic ledger inputs."""

    lanes: list[dict[str, object]] = []
    lane_outcomes: list[dict[str, object]] = []
    for artifact in _dicts(artifacts):
        rounds = _dicts(artifact.get("rounds") if isinstance(artifact.get("rounds"), list) else [])
        completed = _int_or_none(artifact.get("rounds_completed")) or 0
        requested = _int_or_none(artifact.get("rounds_requested")) or 0
        agent_id = _string(artifact.get("agent_id"))
        role_id = _string(artifact.get("role_id"))
        lane_id = _string(artifact.get("lane_id"), default=agent_id)
        compact_rounds: list[dict[str, object]] = []
        for item in rounds:
            executed = item.get("worker_executed") is True
            completed_round = (
                executed
                and item.get("worker_status") in (0, None)
                and item.get("quota_status") == 0
            )
            compact_round = {
                "round": item.get("round_index"),
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": _string(item.get("role_id"), default=role_id),
                "selected_todo_id": item.get("selected_todo_id"),
                "selected_action": item.get("selected_action"),
                "executed": executed,
                "completion_status": "done" if completed_round else None,
                "dev_metric": item.get("dev_metric"),
                "holdout_metric": item.get("holdout_metric"),
                "appended_count": item.get("appended_count"),
                "successor_todo_declared": bool(item.get("successor_todo_declared")),
            }
            compact_rounds.append(compact_round)
            lane_outcomes.append(compact_round)
        lanes.append(
            {
                "agent_id": agent_id,
                "lane_id": lane_id,
                "role_id": role_id,
                "status": artifact.get("status"),
                "rounds_requested": requested,
                "rounds_completed": completed,
                "worker_label": artifact.get("worker_label"),
                "worker_configured": bool(artifact.get("worker_configured")),
                "round_count": len(rounds),
                "rounds": compact_rounds,
            }
        )
    max_completed = max(
        (_int_or_none(lane.get("rounds_completed")) or 0 for lane in lanes),
        default=0,
    )
    max_requested = max(
        (_int_or_none(lane.get("rounds_requested")) or 0 for lane in lanes),
        default=0,
    )
    total_completed = sum(_int_or_none(lane.get("rounds_completed")) or 0 for lane in lanes)
    all_requested_rounds_completed = bool(lanes) and all(
        (_int_or_none(lane.get("rounds_requested")) or 0) > 0
        and (_int_or_none(lane.get("rounds_completed")) or 0)
        >= (_int_or_none(lane.get("rounds_requested")) or 0)
        for lane in lanes
    )
    return {
        "schema_version": "multi_agent_pane_tick_artifact_summary_v0",
        "loaded": bool(lanes),
        "source": "visible_launcher_artifact",
        "coordination_model": "decentralized_state_a2a",
        "workflow_driver": False,
        "round_unit": "pane_local_tick",
        "research_round_unit": "collective_agent_pass",
        "counts_as_collective_research_round": False,
        "lane_count": len(lanes),
        "rounds_completed_total": total_completed,
        "max_rounds_requested": max_requested,
        "max_rounds_completed": max_completed,
        "all_requested_rounds_completed": all_requested_rounds_completed,
        "multi_round_verified": max_completed >= 2,
        "pane_local_multi_tick_verified": max_completed >= 2,
        "lanes": lanes,
        "lane_outcomes": lane_outcomes,
        "public_boundary": {
            "raw_logs_recorded": False,
            "private_artifacts_recorded": False,
            "absolute_paths_recorded": False,
            "credentials_recorded": False,
            "local_workspace_path_redacted": True,
        },
    }


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
    baseline_metric: float | None = None,
    required_full_participation_round_count: int | None = None,
    required_holdout_improvement_count: int | None = None,
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
    expected_agent_ids = {
        str(lane.get("agent_id") or "")
        for lane in lanes
        if str(lane.get("agent_id") or "").strip()
    }
    completed_agents_by_round: dict[int, set[str]] = {}
    completed_turn_count_by_agent: dict[str, int] = {}
    for outcome in completed_outcomes:
        round_index = outcome.get("round")
        agent_id = str(outcome.get("agent_id") or "").strip()
        if agent_id:
            completed_turn_count_by_agent[agent_id] = (
                completed_turn_count_by_agent.get(agent_id, 0) + 1
            )
        if isinstance(round_index, int) and agent_id:
            completed_agents_by_round.setdefault(round_index, set()).add(agent_id)
    full_participation_round_indexes = [
        round_index
        for round_index in round_indexes
        if expected_agent_ids
        and expected_agent_ids <= completed_agents_by_round.get(round_index, set())
    ]
    asynchronous_full_participation_round_count = (
        min(completed_turn_count_by_agent.get(agent_id, 0) for agent_id in expected_agent_ids)
        if expected_agent_ids
        else 0
    )
    effective_full_participation_round_count = max(
        len(full_participation_round_indexes),
        asynchronous_full_participation_round_count,
    )
    evidence_event_count = _int_or_none(evidence.get("evidence_event_count"))
    if evidence_event_count is None:
        evidence_events = evidence.get("events")
        evidence_event_count = len(evidence_events) if isinstance(evidence_events, list) else 0
    dev_metric = _number_or_none(evidence.get("dev_metric"))
    holdout_metric = _number_or_none(evidence.get("holdout_metric"))
    dev_metric_sequence = _number_list(evidence.get("dev_metric_sequence"))
    holdout_metric_sequence = _number_list(evidence.get("holdout_metric_sequence"))
    if not dev_metric_sequence:
        dev_metric_sequence = [
            metric
            for outcome in outcomes
            for metric in [_number_or_none(outcome.get("dev_metric"))]
            if metric is not None
        ]
    if not holdout_metric_sequence:
        holdout_metric_sequence = [
            metric
            for outcome in outcomes
            for metric in [_number_or_none(outcome.get("holdout_metric"))]
            if metric is not None
        ]
    if dev_metric is None and dev_metric_sequence:
        dev_metric = dev_metric_sequence[-1]
    if holdout_metric is None and holdout_metric_sequence:
        holdout_metric = holdout_metric_sequence[-1]
    if not dev_metric_sequence and dev_metric is not None:
        dev_metric_sequence = [dev_metric]
    if not holdout_metric_sequence and holdout_metric is not None:
        holdout_metric_sequence = [holdout_metric]
    holdout_improvement_count = _int_or_none(evidence.get("holdout_improvement_count"))
    baseline = _number_or_none(baseline_metric)
    if holdout_improvement_count is None and baseline is not None:
        holdout_improvement_count = _improvement_count(
            holdout_metric_sequence,
            baseline=baseline,
        )
    full_rounds_required = _int_or_none(required_full_participation_round_count)
    holdout_improvements_required = _int_or_none(required_holdout_improvement_count)
    full_round_requirement_met = (
        None
        if full_rounds_required is None
        else effective_full_participation_round_count >= full_rounds_required
    )
    holdout_improvement_requirement_met = (
        None
        if holdout_improvements_required is None
        else (holdout_improvement_count or 0) >= holdout_improvements_required
    )
    verification_checks = [
        check
        for check in (
            full_round_requirement_met,
            holdout_improvement_requirement_met,
        )
        if check is not None
    ]
    collective_research_verified = bool(verification_checks) and all(verification_checks)
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
        "full_participation_round_indexes": full_participation_round_indexes,
        "synchronous_full_participation_round_count": len(full_participation_round_indexes),
        "asynchronous_full_participation_round_count": (
            asynchronous_full_participation_round_count
        ),
        "full_participation_round_count": effective_full_participation_round_count,
        "full_participation_verified": (
            bool(round_indexes)
            and len(full_participation_round_indexes) == len(round_indexes)
        ),
        "multi_round_interaction_verified": (
            len(round_indexes) >= 2 or effective_full_participation_round_count >= 2
        ),
        "integrated_evidence": {
            "loaded": bool(evidence),
            "evidence_event_count": evidence_event_count,
            "dev_metric": dev_metric,
            "holdout_metric": holdout_metric,
            "dev_metric_sequence": dev_metric_sequence,
            "holdout_metric_sequence": holdout_metric_sequence,
            "holdout_improvement_count": holdout_improvement_count,
            "result_status": _string(evidence.get("result_status")),
            "protected_scope_clean": _bool_or_none(evidence.get("protected_scope_clean")),
        },
        "collective_research_verification": {
            "schema_version": "multi_agent_collective_research_verification_v0",
            "baseline_metric": baseline,
            "required_full_participation_round_count": full_rounds_required,
            "required_holdout_improvement_count": holdout_improvements_required,
            "full_participation_round_count": effective_full_participation_round_count,
            "synchronous_full_participation_round_count": len(full_participation_round_indexes),
            "asynchronous_full_participation_round_count": (
                asynchronous_full_participation_round_count
            ),
            "full_participation_requirement_met": full_round_requirement_met,
            "dev_metric_over_baseline": (
                None
                if baseline is None or dev_metric is None
                else dev_metric > baseline
            ),
            "holdout_metric_over_baseline": (
                None
                if baseline is None or holdout_metric is None
                else holdout_metric > baseline
            ),
            "holdout_improvement_count": holdout_improvement_count,
            "holdout_improvement_requirement_met": holdout_improvement_requirement_met,
            "verified": collective_research_verified,
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
