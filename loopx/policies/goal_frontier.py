from __future__ import annotations

from typing import Any


GOAL_FRONTIER_PROJECTION_SCHEMA_VERSION = "goal_frontier_projection_v0"
AUTONOMOUS_REPLAN_DECISION_SCHEMA_VERSION = "autonomous_replan_decision_v0"
AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION = "autonomous_replan_obligation_v0"
AUTONOMOUS_REPLAN_REQUIRED_MODE = "autonomous_replan_required"
FRONTIER_EXHAUSTED_MONITOR_TRIGGER = "frontier_exhausted_monitor_lane"
TODO_TASK_CLASS_ADVANCEMENT = "advancement_task"
TODO_TASK_CLASS_MONITOR = "continuous_monitor"
FRONTIER_REPLAN_ACK_DELTA_KINDS = {
    "active_state_next_action",
    "blocker",
    "goal_vision_patch",
    "no_followup",
    "runnable_todo_set",
    "successor_or_supersede",
    "watch_lane_continuation",
}


def safe_non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def select_autonomous_replan_obligation(
    item: dict[str, Any],
    project_asset: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    project_asset = project_asset if isinstance(project_asset, dict) else {}
    value = item.get("autonomous_replan_obligation")
    if isinstance(value, dict):
        return value
    value = project_asset.get("autonomous_replan_obligation")
    if isinstance(value, dict):
        return value
    return None


def autonomous_replan_is_required(replan_obligation: dict[str, Any] | None) -> bool:
    return bool(replan_obligation and replan_obligation.get("required"))


def autonomous_replan_ack_has_frontier_delta(ack: dict[str, Any] | None) -> bool:
    if not isinstance(ack, dict) or ack.get("recorded") is not True:
        return False
    delta_contract = ack.get("delta_contract")
    if not isinstance(delta_contract, dict) or delta_contract.get("delta_present") is not True:
        return False
    delta_kinds = {
        str(item or "").strip()
        for item in (delta_contract.get("delta_kinds") or [])
        if str(item or "").strip()
    }
    return bool(delta_kinds & FRONTIER_REPLAN_ACK_DELTA_KINDS)


def autonomous_replan_decision_allowed(
    *,
    replan_obligation: dict[str, Any] | None,
    plan_ok: bool,
    workspace_blocked: bool,
    automation_prompt_upgrade_required: bool,
) -> bool:
    return bool(
        autonomous_replan_is_required(replan_obligation)
        and plan_ok
        and not workspace_blocked
        and not automation_prompt_upgrade_required
    )


def _open_todo_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    return safe_non_negative_int(summary.get("open_count"))


def _todo_item_is_actionable_open(item: dict[str, Any]) -> bool:
    if item.get("done") is True:
        return False
    status = str(item.get("status") or "open").strip().lower()
    return status in {"", "open", "todo", "active", "pending"}


def _todo_task_class(item: dict[str, Any]) -> str:
    return str(item.get("task_class") or "").strip()


def _count_advancement_items(items: Any, *, claimed_by: str | None = None) -> int:
    if not isinstance(items, list):
        return 0
    count = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if not _todo_item_is_actionable_open(item):
            continue
        if _todo_task_class(item) != TODO_TASK_CLASS_ADVANCEMENT:
            continue
        item_claimed_by = str(item.get("claimed_by") or "").strip()
        if claimed_by == "__unclaimed__":
            if item_claimed_by:
                continue
        elif claimed_by is not None and item_claimed_by != claimed_by:
            continue
        count += 1
    return count


def _summary_task_counts(summary: dict[str, Any] | None) -> dict[str, int]:
    open_count = _open_todo_count(summary)
    if not isinstance(summary, dict):
        return {"open": open_count, "advancement": 0, "monitor": 0, "monitor_due": 0}
    executable = summary.get("executable_backlog_items")
    monitor_open = summary.get("monitor_open_items")
    advancement_count = (
        _count_advancement_items(executable)
        if isinstance(executable, list)
        else safe_non_negative_int(summary.get("claimed_advancement_open_count"))
        + len(
            [
                item
                for item in (summary.get("unclaimed_priority_open_items") or [])
                if isinstance(item, dict)
                and _todo_task_class(item) == TODO_TASK_CLASS_ADVANCEMENT
            ]
        )
    )
    monitor_count = (
        len(
            [
                item
                for item in monitor_open
                if isinstance(item, dict)
                and _todo_item_is_actionable_open(item)
                and _todo_task_class(item) == TODO_TASK_CLASS_MONITOR
            ]
        )
        if isinstance(monitor_open, list)
        else safe_non_negative_int(summary.get("claimed_monitor_open_count"))
    )
    return {
        "open": open_count,
        "advancement": advancement_count,
        "monitor": monitor_count,
        "monitor_due": safe_non_negative_int(summary.get("monitor_due_count")),
    }


def _frontier_advancement_counts(
    *,
    agent_todo_summary: dict[str, Any] | None,
    agent_id: str | None,
) -> dict[str, int]:
    current_agent_advancement_count = (
        safe_non_negative_int(agent_todo_summary.get("current_agent_claimed_advancement_count"))
        if isinstance(agent_todo_summary, dict)
        else 0
    )
    unclaimed_advancement_count = (
        _count_advancement_items(
            agent_todo_summary.get("unclaimed_priority_open_items"),
            claimed_by="__unclaimed__",
        )
        if isinstance(agent_todo_summary, dict)
        else 0
    )
    other_agent_claimed_items: Any = None
    if isinstance(agent_todo_summary, dict):
        executable_items = agent_todo_summary.get("executable_backlog_items")
        if isinstance(executable_items, list):
            if agent_id:
                current_agent_advancement_count = max(
                    current_agent_advancement_count,
                    _count_advancement_items(executable_items, claimed_by=agent_id),
                )
            unclaimed_advancement_count = max(
                unclaimed_advancement_count,
                _count_advancement_items(executable_items, claimed_by="__unclaimed__"),
            )
        claim_scope = (
            agent_todo_summary.get("claim_scope")
            if isinstance(agent_todo_summary.get("claim_scope"), dict)
            else {}
        )
        other_agent_claimed_items = claim_scope.get("other_agent_claimed_items")
    return {
        "current_agent_claimed_advancement_count": current_agent_advancement_count,
        "unclaimed_advancement_count": unclaimed_advancement_count,
        "other_agent_claimed_advancement_count": _count_advancement_items(
            other_agent_claimed_items
        ),
    }


def _is_monitor_only_lane(
    work_lane_contract: dict[str, Any] | None,
) -> bool:
    return bool(
        work_lane_contract
        and work_lane_contract.get("lane") == TODO_TASK_CLASS_MONITOR
        and work_lane_contract.get("must_attempt_work") is False
    )


def derive_goal_frontier_replan_obligation_from_summaries(
    *,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    agent_id: str | None,
    existing_replan_obligation: dict[str, Any] | None,
    latest_replan_ack: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a compact replan obligation when the goal frontier has no advancement.

    This keeps the per-goal completion/replan rule in the goal-frontier policy
    seam. Quota should consume the resulting obligation instead of embedding
    monitor/vision semantics in its scheduler path.
    """

    if autonomous_replan_is_required(existing_replan_obligation):
        return None
    if autonomous_replan_ack_has_frontier_delta(latest_replan_ack):
        return None

    user_counts = _summary_task_counts(user_todo_summary)
    agent_counts = _summary_task_counts(agent_todo_summary)
    frontier_counts = _frontier_advancement_counts(
        agent_todo_summary=agent_todo_summary,
        agent_id=agent_id,
    )
    total_frontier_advancement = sum(frontier_counts.values())
    if user_counts.get("open", 0) > 0:
        return None
    if not _is_monitor_only_lane(work_lane_contract):
        return None
    if agent_counts.get("monitor", 0) <= 0:
        return None
    if agent_counts.get("advancement", 0) > 0 or total_frontier_advancement > 0:
        return None

    return {
        "schema_version": AUTONOMOUS_REPLAN_OBLIGATION_SCHEMA_VERSION,
        "required": True,
        "stall_threshold": 1,
        "trigger_count": 1,
        "triggers": [
            {
                "kind": FRONTIER_EXHAUSTED_MONITOR_TRIGGER,
                "section": "goal_frontier_projection",
                "text": (
                    "current goal frontier has no current, unclaimed, or other-agent "
                    "advancement todo while only monitor work remains"
                ),
                "agent_id": agent_id,
                "agent_open_count": agent_counts.get("open", 0),
                "agent_monitor_open_count": agent_counts.get("monitor", 0),
            }
        ],
        "guidance_actions": [
            "create_successor",
            "supersede_monitor",
            "set_watch_expiry",
            "record_no_followup",
        ],
        "todo_actions": [
            {
                "action": "add",
                "role": "agent",
                "priority": "P1",
                "text": (
                    "run a compact goal-frontier replan: create a successor runnable "
                    "todo, supersede stale monitor work, set watch-lane expiry, or "
                    "record an explicit no-follow-up rationale"
                ),
            }
        ],
        "next_validation_command": "python3 examples/quota-replan-decision-plane-smoke.py",
        "stop_condition": (
            "stop if the replan requires private material, credentials, destructive git, "
            "production actions, or owner-only decisions"
        ),
        "recommended_action": (
            "run a bounded goal-frontier replan before another monitor-only quiet "
            "poll: create successor work, supersede the monitor lane, set an expiry, "
            "or record no-follow-up"
        ),
    }


def build_goal_frontier_projection_from_summaries(
    *,
    goal_id: str,
    agent_id: str | None,
    user_todo_summary: dict[str, Any] | None,
    agent_todo_summary: dict[str, Any] | None,
    work_lane_contract: dict[str, Any] | None,
    replan_obligation: dict[str, Any] | None,
) -> dict[str, Any]:
    user_counts = _summary_task_counts(user_todo_summary)
    agent_counts = _summary_task_counts(agent_todo_summary)
    frontier_counts = _frontier_advancement_counts(
        agent_todo_summary=agent_todo_summary,
        agent_id=agent_id,
    )
    monitor_only_lane = _is_monitor_only_lane(work_lane_contract)
    return build_goal_frontier_projection(
        goal_id=goal_id,
        agent_id=agent_id,
        user_counts=user_counts,
        agent_counts=agent_counts,
        current_agent_claimed_advancement_count=frontier_counts[
            "current_agent_claimed_advancement_count"
        ],
        unclaimed_advancement_count=frontier_counts["unclaimed_advancement_count"],
        other_agent_claimed_advancement_count=frontier_counts[
            "other_agent_claimed_advancement_count"
        ],
        monitor_only_lane=monitor_only_lane,
        replan_obligation=replan_obligation,
    )


def compact_replan_obligation(replan_obligation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": replan_obligation.get("schema_version"),
        "stall_threshold": replan_obligation.get("stall_threshold"),
        "trigger_count": replan_obligation.get("trigger_count"),
        "triggers": replan_obligation.get("triggers") or [],
        "next_validation_command": replan_obligation.get("next_validation_command"),
        "stop_condition": replan_obligation.get("stop_condition"),
    }


def build_autonomous_replan_recommendation(
    replan_obligation: dict[str, Any],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "recommended_mode": AUTONOMOUS_REPLAN_REQUIRED_MODE,
        "notify": "DONT_NOTIFY",
        "replan_obligation": compact_replan_obligation(replan_obligation),
        "spend_policy": (
            "append exactly one heartbeat spend only after executing the selected "
            "replan slice, validating it, and writing back todo split/add/retire state"
        ),
        "reason": reason
        or (
            "status exposes an autonomous replan obligation; advance the goal-level "
            "planning-trigger slice before monitor-only or agent-scope wait classification"
        ),
    }


def build_autonomous_replan_decision(replan_obligation: dict[str, Any]) -> dict[str, Any]:
    triggers = (
        replan_obligation.get("triggers")
        if isinstance(replan_obligation.get("triggers"), list)
        else []
    )
    return {
        "schema_version": AUTONOMOUS_REPLAN_DECISION_SCHEMA_VERSION,
        "required": True,
        "decision": AUTONOMOUS_REPLAN_REQUIRED_MODE,
        "decision_plane": "goal_frontier_before_lane_quiet_or_agent_scope_wait",
        "not_disturbed_by": [
            "monitor_quiet_skip",
            "agent_scope_wait",
            "agent_scope_exhausted",
        ],
        "trigger_count": safe_non_negative_int(replan_obligation.get("trigger_count")),
        "triggers": [
            trigger.get("kind")
            for trigger in triggers
            if isinstance(trigger, dict) and trigger.get("kind")
        ],
    }


def build_goal_frontier_projection(
    *,
    goal_id: str,
    agent_id: str | None,
    user_counts: dict[str, int],
    agent_counts: dict[str, int],
    current_agent_claimed_advancement_count: int,
    unclaimed_advancement_count: int,
    other_agent_claimed_advancement_count: int,
    monitor_only_lane: bool,
    replan_obligation: dict[str, Any] | None,
) -> dict[str, Any]:
    replan_required = autonomous_replan_is_required(replan_obligation)
    blockers: list[str] = []
    if monitor_only_lane:
        blockers.append("monitor_only_lane")
    if (
        current_agent_claimed_advancement_count == 0
        and unclaimed_advancement_count == 0
        and other_agent_claimed_advancement_count > 0
    ):
        blockers.append("other_agent_claimed_advancement")
    if replan_required:
        blockers.append("autonomous_replan_obligation")

    projection: dict[str, Any] = {
        "schema_version": GOAL_FRONTIER_PROJECTION_SCHEMA_VERSION,
        "goal_id": goal_id,
        "agent_id": agent_id,
        "source": "quota_should_run",
        "normalized_progress": {
            "user_open_count": user_counts.get("open", 0),
            "agent_open_count": agent_counts.get("open", 0),
            "agent_advancement_open_count": agent_counts.get("advancement", 0),
            "agent_monitor_open_count": agent_counts.get("monitor", 0),
            "agent_monitor_due_count": agent_counts.get("monitor_due", 0),
        },
        "remaining_advancement_frontier": {
            "current_agent_claimed_advancement_count": current_agent_claimed_advancement_count,
            "unclaimed_advancement_count": unclaimed_advancement_count,
            "other_agent_claimed_advancement_count": other_agent_claimed_advancement_count,
        },
        "monitor_only_lanes": {
            "present": monitor_only_lane,
            "quiet_until_material_transition": monitor_only_lane,
        },
        "autonomy_blockers": blockers,
        "replan_required": replan_required,
    }
    if replan_required and isinstance(replan_obligation, dict):
        projection["autonomous_replan_decision"] = build_autonomous_replan_decision(
            replan_obligation
        )
    return projection
