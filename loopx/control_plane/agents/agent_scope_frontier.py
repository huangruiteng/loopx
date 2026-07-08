from __future__ import annotations

from enum import Enum
from typing import Any


AGENT_SCOPE_FRONTIER_SCHEMA_VERSION = "agent_scope_frontier_v0"
AGENT_LANE_FRONTIER_HINT_SCHEMA_VERSION = "agent_lane_frontier_hint_v0"


class AgentScopeFrontierAction(str, Enum):
    AGENT_SCOPE_EXHAUSTED = "agent_scope_exhausted"
    AGENT_SCOPE_WAIT = "agent_scope_wait"
    REASSIGNMENT_REQUIRED = "reassignment_required"
    SUCCESSOR_REPLAN_REQUIRED = "successor_replan_required"


class AgentLaneFrontierHintDecision(str, Enum):
    CLAIM_UNOWNED_IN_SCOPE = "claim_unowned_in_scope"
    ADD_NEXT_ADVANCEMENT = "add_next_advancement"
    RECORD_NO_FOLLOWUP = "record_no_followup"
    QUIET_NOOP_BLOCKER = "quiet_noop_blocker"


def agent_scope_frontier_action(value: Any) -> AgentScopeFrontierAction | None:
    try:
        return AgentScopeFrontierAction(str(value or ""))
    except ValueError:
        return None


def build_agent_scope_frontier_payload(
    *,
    agent_id: str,
    primary_agent: str | None,
    action: AgentScopeFrontierAction,
    quiet_noop_allowed: bool,
    spend_policy: str,
    reason: str,
    recommended_action: str,
    candidate_counts: dict[str, Any],
    requires_replan: bool = False,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": AGENT_SCOPE_FRONTIER_SCHEMA_VERSION,
        "agent_id": agent_id,
        "primary_agent": primary_agent,
        "action": action.value,
        "effective_action": action.value,
        "blocks_delivery": True,
        "quiet_noop_allowed": quiet_noop_allowed,
        "spend_policy": spend_policy,
        "reason": reason,
        "recommended_action": recommended_action,
        "candidate_counts": candidate_counts,
    }
    if requires_replan:
        payload["requires_replan"] = True
    if extra_fields:
        payload.update(extra_fields)
    return payload
