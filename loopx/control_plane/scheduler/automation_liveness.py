from __future__ import annotations

from typing import Any

from ..agents.agent_scope_frontier import (
    AgentScopeFrontierAction,
    agent_scope_frontier_action as _agent_scope_frontier_action,
)
from ..goals.goal_frontier import AUTONOMOUS_REPLAN_REQUIRED_MODE


AUTOMATION_LIVENESS_SCHEMA_VERSION = "automation_liveness_v0"


def build_automation_liveness(payload: dict[str, Any]) -> dict[str, Any]:
    heartbeat_recommendation = (
        payload.get("heartbeat_recommendation")
        if isinstance(payload.get("heartbeat_recommendation"), dict)
        else {}
    )
    execution_obligation = (
        payload.get("execution_obligation")
        if isinstance(payload.get("execution_obligation"), dict)
        else {}
    )
    effective_action = str(payload.get("effective_action") or "")
    recommended_mode = str(heartbeat_recommendation.get("recommended_mode") or "")
    must_attempt_work = bool(execution_obligation.get("must_attempt_work"))

    base = {
        "schema_version": AUTOMATION_LIVENESS_SCHEMA_VERSION,
        "keep_active": True,
        "pause_allowed": False,
        "pause_policy": (
            "pause/delete only after a bounded self-repair or replan path is itself "
            "stuck for two more eligible turns"
        ),
    }
    if effective_action == "terminal_no_followup":
        return {
            **base,
            "keep_active": False,
            "pause_allowed": True,
            "pause_policy": (
                "pause or delete the recurring automation now; only an explicit "
                "goal resume or new projected work should recreate it"
            ),
            "automation_action": "stop_terminal_no_followup",
            "reason": (
                "validated closure evidence derives no-follow-up from complete todo "
                "sources and an empty normalized frontier"
            ),
            "next_trigger": "explicit goal resume or newly projected work",
            "spend_policy": "no quota spend for terminal automation shutdown",
        }
    if (
        effective_action == "monitor_quiet_skip"
        or recommended_mode == "monitor_quiet_until_material_transition"
    ):
        return {
            **base,
            "automation_action": "keep_active_quiet",
            "reason": (
                "monitor-only quiet skip is a liveness-preserving no-op, not a "
                "self-stop signal"
            ),
            "next_trigger": (
                "material monitor transition, regression, concrete blocker, or "
                f"{AUTONOMOUS_REPLAN_REQUIRED_MODE}"
            ),
            "spend_policy": "no quota spend for unchanged monitor-only polls",
        }
    if effective_action == "automation_prompt_upgrade_required":
        return {
            **base,
            "automation_action": "repair_automation_prompt_identity",
            "reason": (
                "the installed automation is stale or unscoped; keep the automation "
                "active but block delivery until it reruns with a registered agent id"
            ),
            "spend_policy": "no quota spend for identity prompt upgrade preflight",
        }
    if effective_action == AgentScopeFrontierAction.SUCCESSOR_REPLAN_REQUIRED.value:
        agent_scope_frontier = (
            payload.get("agent_scope_frontier")
            if isinstance(payload.get("agent_scope_frontier"), dict)
            else {}
        )
        if agent_scope_frontier.get("monitor_blocked_resume_candidates"):
            return {
                **base,
                "automation_action": "execute_bounded_work",
                "reason": (
                    "a current-agent advancement todo is gated by an open standing "
                    "monitor; repair the gate model before another quiet no-op"
                ),
                "next_trigger": "standing monitor gate repair writeback or fresh quota guard",
                "spend_policy": "spend once only after validated gate repair/todo writeback",
            }
        return {
            **base,
            "automation_action": "execute_bounded_work",
            "reason": (
                "a ready deferred successor is visible to this agent; run a bounded "
                "successor replan or write a no-follow-up rationale before another quiet no-op"
            ),
            "next_trigger": "deferred successor replan writeback or fresh quota guard",
            "spend_policy": "spend once only after validated successor replan/todo writeback",
        }
    if _agent_scope_frontier_action(effective_action) is not None:
        return {
            **base,
            "automation_action": "keep_active_quiet",
            "reason": (
                "the current agent has no in-scope runnable candidate; this is a "
                "liveness-preserving no-op until work is reassigned or projected"
            ),
            "next_trigger": (
                "handoff owner progress, reassignment, or a current-agent/unclaimed "
                "advancement todo"
            ),
            "spend_policy": "no quota spend for agent-scoped no-candidate checks",
        }
    if must_attempt_work or recommended_mode == AUTONOMOUS_REPLAN_REQUIRED_MODE:
        return {
            **base,
            "automation_action": "execute_bounded_work",
            "reason": (
                "execution_obligation requires a bounded progress or replan segment "
                "before another quiet no-op"
            ),
            "spend_policy": "spend once only after validation and durable writeback",
        }
    if recommended_mode == "mapped_noop_if_unchanged":
        return {
            **base,
            "automation_action": "keep_active_noop_if_unchanged",
            "reason": (
                "unchanged mapped state should stay quiet and active until new evidence "
                "or a concrete safe handoff appears"
            ),
            "spend_policy": "no quota spend for unchanged mapped no-op checks",
        }
    return {
        **base,
        "automation_action": "keep_active",
        "reason": "heartbeat liveness should be preserved unless the repair path is stuck",
        "spend_policy": (
            "follow heartbeat_recommendation; spend only after validated delivery or "
            "safe-bypass writeback"
        ),
    }
