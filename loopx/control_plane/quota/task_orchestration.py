from __future__ import annotations

from typing import Any

from ..agents.agent_scope_frontier import AgentScopeFrontierAction
from ..agents.runtime_model import peer_work_key, select_peer_for_work
from ..todos.todo_summary import normalize_todo_claimed_by
from ..work_items.work_lane import WORK_LANE_CONTRACT_SCHEMA_VERSION
from ..work_items.work_lane_context import build_work_lane_context_contract


AGENT_SCOPE_NON_EXECUTION_ACTIONS = {
    AgentScopeFrontierAction.AGENT_SCOPE_EXHAUSTED.value,
    AgentScopeFrontierAction.AGENT_SCOPE_WAIT.value,
    AgentScopeFrontierAction.REASSIGNMENT_REQUIRED.value,
}


def build_quota_work_lane_contract(
    item: dict[str, Any],
    *,
    agent_todo_summary: dict[str, Any] | None,
    monitor_due_item_limit: int,
) -> dict[str, Any] | None:
    return build_work_lane_context_contract(
        item,
        agent_todo_summary=agent_todo_summary,
        monitor_due_item_limit=monitor_due_item_limit,
    )


def payload_work_lane_contract(
    work_lane_contract: dict[str, Any] | None,
    *,
    effective_action: str,
    recovery_allowed: bool,
    agent_scope_frontier: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if recovery_allowed and effective_action == "outcome_floor_recovery":
        return None
    if not isinstance(work_lane_contract, dict):
        return work_lane_contract
    if (
        effective_action in AGENT_SCOPE_NON_EXECUTION_ACTIONS
        and work_lane_contract.get("must_attempt_work") is True
        and isinstance(agent_scope_frontier, dict)
    ):
        return _agent_scope_payload_work_lane_contract(
            work_lane_contract,
            effective_action=effective_action,
            agent_scope_frontier=agent_scope_frontier,
        )
    return work_lane_contract


def apply_task_orchestration_contract(
    *,
    fallback_work_lane_contract: dict[str, Any] | None,
    goal_boundary: dict[str, Any] | None,
    agent_identity: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any],
    raw_agent_todo_summary: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    del agent_todo_summary
    contract = _task_orchestration_contract(
        goal_boundary=goal_boundary,
        agent_identity=agent_identity,
        raw_agent_todo_summary=raw_agent_todo_summary,
    )
    if not contract:
        return None, fallback_work_lane_contract
    return contract, _task_orchestration_work_lane_contract(contract)


def task_orchestration_effective_action(
    contract: dict[str, Any] | None,
    *,
    should_run: bool,
    normal_delivery_allowed: bool,
    effective_action: str,
    reason: str,
) -> tuple[str, str]:
    if (
        contract
        and should_run
        and normal_delivery_allowed
        and effective_action == "normal_run"
    ):
        return (
            "coordinate_task_bundle",
            "the deterministic task coordinator must activate or resume eligible "
            "peer lanes before doing its own worker-lane delivery",
        )
    return effective_action, reason


def task_selected_recommended_action(
    contract: dict[str, Any] | None,
    fallback: str | None,
) -> str | None:
    if not contract:
        return fallback
    return str(contract.get("coordinator_obligation") or fallback or "")


def task_goal_route_hint(
    goal_route_hint: dict[str, Any] | None,
    contract: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not contract or not isinstance(goal_route_hint, dict):
        return goal_route_hint
    peer_lanes = contract.get("eligible_peer_lanes")
    return {
        **{
            key: value
            for key, value in goal_route_hint.items()
            if key != "current_agent_next_action"
        },
        "kind": "task_orchestration",
        "route_decision": "coordinate_task_bundle",
        "reason": "task-scoped coordinator must activate/resume eligible peer lanes",
        "peer_lane_count": len(peer_lanes) if isinstance(peer_lanes, list) else 0,
    }


def attach_task_orchestration_payload(
    payload: dict[str, Any],
    contract: dict[str, Any] | None,
) -> dict[str, Any]:
    if contract:
        payload["task_orchestration_contract"] = contract
    return payload


def _agent_scope_payload_work_lane_contract(
    work_lane_contract: dict[str, Any],
    *,
    effective_action: str,
    agent_scope_frontier: dict[str, Any],
) -> dict[str, Any]:
    reason_codes = [
        str(value)
        for value in (
            work_lane_contract.get("reason_codes")
            if isinstance(work_lane_contract.get("reason_codes"), list)
            else []
        )
        if str(value).strip()
    ]
    for code in ("agent_scope_no_current_runnable_candidate", effective_action):
        if code not in reason_codes:
            reason_codes.append(code)
    deferred_work_lane = {
        key: work_lane_contract.get(key)
        for key in ("lane", "next_lane", "obligation", "monitor_policy")
        if work_lane_contract.get(key) is not None
    }
    if work_lane_contract.get("reason_codes") is not None:
        deferred_work_lane["reason_codes"] = work_lane_contract.get("reason_codes")
    return {
        "schema_version": str(
            work_lane_contract.get("schema_version")
            or WORK_LANE_CONTRACT_SCHEMA_VERSION
        ),
        "lane": effective_action,
        "next_lane": str(work_lane_contract.get("lane") or "advancement_task"),
        "obligation": "wait_for_current_agent_or_unclaimed_advancement",
        "must_attempt_work": False,
        "reason_codes": reason_codes,
        "monitor_policy": "no_delivery_until_current_agent_frontier_exists",
        "blocked_by_agent_scope": True,
        "agent_scope_action": effective_action,
        "deferred_work_lane": deferred_work_lane,
        "action": (
            agent_scope_frontier.get("recommended_action")
            or agent_scope_frontier.get("reason")
            or "wait for a current-agent or unclaimed advancement todo before delivery"
        ),
    }


def _task_orchestration_contract(
    *,
    goal_boundary: dict[str, Any] | None,
    agent_identity: dict[str, Any] | None,
    raw_agent_todo_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(agent_identity, dict):
        return None
    if not isinstance(goal_boundary, dict):
        return None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return None
    orchestration = (
        goal_boundary.get("orchestration")
        if isinstance(goal_boundary.get("orchestration"), dict)
        else {}
    )
    if orchestration.get("mode") != "multi_subagent":
        return None
    if orchestration.get("spawn_allowed") is not True:
        return None
    max_peers = orchestration.get("max_children")
    if not isinstance(max_peers, int) or max_peers <= 0:
        return None
    source_items = (
        raw_agent_todo_summary.get("items")
        if isinstance(raw_agent_todo_summary, dict)
        and isinstance(raw_agent_todo_summary.get("items"), list)
        else []
    )
    candidate_lanes: list[dict[str, Any]] = []
    seen_agents: set[str] = set()
    registered_agents = set(agent_identity.get("registered_agents") or [])
    for item in source_items:
        if not isinstance(item, dict):
            continue
        if str(item.get("task_class") or "") != "advancement_task":
            continue
        peer_agent = normalize_todo_claimed_by(item.get("claimed_by"))
        if (
            not peer_agent
            or peer_agent in seen_agents
            or peer_agent not in registered_agents
        ):
            continue
        candidate_lanes.append(
            {
                "agent_id": peer_agent,
                "todo_id": str(item.get("todo_id") or "").strip() or None,
                "priority": item.get("priority"),
                "task_class": item.get("task_class"),
                "action_kind": item.get("action_kind"),
                "title": str(item.get("title") or item.get("text") or "").strip(),
            }
        )
        seen_agents.add(peer_agent)
    if not candidate_lanes:
        return None
    assignment_key = peer_work_key(
        {
            "mode": "task_scoped_peer",
            "lanes": [
                {"agent_id": lane["agent_id"], "todo_id": lane["todo_id"]}
                for lane in candidate_lanes
            ],
        },
        fallback="task_orchestration",
    )
    coordinator = select_peer_for_work(
        agent_identity.get("registered_agents") or [],
        work_key=assignment_key,
    )
    if not coordinator or agent_id != coordinator:
        return None
    peer_lanes = [
        lane for lane in candidate_lanes if lane["agent_id"] != coordinator
    ][:max_peers]
    if not peer_lanes:
        return None
    return {
        "schema_version": "task_orchestration_contract_v1",
        "mode": "task_scoped_peer",
        "coordinator_agent_id": coordinator,
        "assignment_key": assignment_key,
        "activation_required": True,
        "activation_allowed": True,
        "max_peer_lanes": max_peers,
        "eligible_peer_lanes": peer_lanes,
        "blocked_peer_lanes": [],
        "writeback_owner": "task_coordinator",
        "coordinator_obligation": (
            "activate or resume eligible peer lanes, review returned evidence, "
            "then write accepted state/todos for this task bundle"
        ),
    }


def _task_orchestration_work_lane_contract(
    contract: dict[str, Any],
) -> dict[str, Any]:
    peer_lanes = contract.get("eligible_peer_lanes")
    return {
        "schema_version": "work_lane_contract_v1",
        "lane": "task_orchestration",
        "next_lane": "peer_evidence_review",
        "obligation": "coordinate_task_bundle",
        "must_attempt_work": True,
        "reason_codes": ["eligible_peer_lanes"],
        "monitor_policy": "material_transition_only",
        "action": contract["coordinator_obligation"],
        "eligible_peer_lane_count": (
            len(peer_lanes) if isinstance(peer_lanes, list) else 0
        ),
    }
