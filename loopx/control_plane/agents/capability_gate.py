from __future__ import annotations

from typing import Any

from ...todo_contract import (
    normalize_required_capabilities,
    normalize_target_capabilities,
    normalize_todo_blocks_agent,
    normalize_todo_claimed_by,
)
from ..todos.projection import todo_index_rank, todo_priority_rank
from .agent_scope import _compact_todo_summary_item


CAPABILITY_REPAIR_BRIDGE_HINTS = {
    "benchmark_runner",
    "external_evidence_poll",
    "worker_bridge",
    "cli_bridge",
}
CAPABILITY_OWNER_GATE_HINTS = {
    "network",
    "credentials",
    "production_access",
}


def _capability_missing_action(missing: list[str]) -> str:
    missing_set = set(missing)
    if not missing_set:
        return "run"
    if missing_set & CAPABILITY_REPAIR_BRIDGE_HINTS:
        return "repair_bridge"
    if missing_set & CAPABILITY_OWNER_GATE_HINTS:
        return "ask_owner"
    return "skip"


def _capability_candidate_item(
    item: dict[str, Any],
    *,
    missing: list[str],
    missing_target_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    text = str(item.get("text") or "").strip()
    payload = _compact_todo_summary_item(item, text=text)
    required = normalize_required_capabilities(item.get("required_capabilities"))
    targets = normalize_target_capabilities(item.get("target_capabilities"))
    payload["required_capabilities"] = required
    if targets:
        payload["target_capabilities"] = targets
    payload["missing_capabilities"] = missing
    payload["capability_action"] = _capability_missing_action(missing)
    missing_targets = normalize_target_capabilities(missing_target_capabilities)
    if missing_targets:
        payload["missing_target_capabilities"] = missing_targets
    if missing_targets and set(missing_targets) & CAPABILITY_REPAIR_BRIDGE_HINTS:
        payload["capability_repair_mode"] = True
        payload["capability_action"] = "repair_bridge"
    return payload


def _unblock_handoff_rank(
    raw_item: dict[str, Any],
    *,
    agent_id: str | None,
) -> int:
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    blocks_agent = normalize_todo_blocks_agent(raw_item.get("blocks_agent"))
    return (
        0
        if agent_id
        and claimed_by == agent_id
        and blocks_agent
        and blocks_agent != agent_id
        else 1
    )


def _primary_review_rank(raw_item: dict[str, Any], *, agent_id: str | None) -> int:
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    action_kind = str(raw_item.get("action_kind") or "").strip()
    return (
        0
        if agent_id
        and claimed_by == agent_id
        and (action_kind == "primary_review" or action_kind.startswith("primary_review_"))
        else 1
    )


def _agent_lane_candidate_sort_key(
    raw_item: dict[str, Any],
    *,
    agent_id: str | None,
    primary_agent: str | None,
    preferred_todo_ids: set[str] | None = None,
) -> tuple[int, int, int, int, int, int, int]:
    del primary_agent
    preferred_todo_ids = preferred_todo_ids or set()
    todo_id = str(raw_item.get("todo_id") or "").strip()
    active_next_rank = 0 if todo_id and todo_id in preferred_todo_ids else 1
    claimed_by = normalize_todo_claimed_by(raw_item.get("claimed_by"))
    claim_rank = 0 if agent_id and claimed_by == agent_id else 1
    repair_rank = 0 if raw_item.get("capability_repair_mode") is True else 1
    return (
        active_next_rank,
        claim_rank,
        _unblock_handoff_rank(raw_item, agent_id=agent_id),
        todo_priority_rank(raw_item),
        _primary_review_rank(raw_item, agent_id=agent_id),
        repair_rank,
        todo_index_rank(raw_item),
    )


def _sort_capability_runnable_candidates(
    runnable: list[dict[str, Any]],
    *,
    agent_identity: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(agent_identity, dict):
        return runnable, None
    agent_id = normalize_todo_claimed_by(agent_identity.get("agent_id"))
    if not agent_id:
        return runnable, None
    primary_agent = normalize_todo_claimed_by(agent_identity.get("primary_agent"))
    policy = "active_next_then_claim_then_unblock_handoff_then_priority_then_repair"
    return (
        sorted(
            runnable,
            key=lambda item: _agent_lane_candidate_sort_key(
                item,
                agent_id=agent_id,
                primary_agent=primary_agent,
            ),
        ),
        policy,
    )
