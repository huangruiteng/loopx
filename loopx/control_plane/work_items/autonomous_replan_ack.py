from __future__ import annotations

from typing import Any

from ..runtime.time import parse_timestamp


AUTONOMOUS_REPLAN_ACK_MATERIAL_RUN_WINDOW = 20


def autonomous_replan_ack_recorded(run: dict[str, Any]) -> bool:
    ack = run.get("autonomous_replan_ack")
    if not isinstance(ack, dict) or ack.get("recorded") is not True:
        return False
    delta_contract = ack.get("delta_contract")
    if not isinstance(delta_contract, dict):
        return False
    return delta_contract.get("delta_present") is True


def compact_autonomous_replan_ack(run: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run, dict) or not autonomous_replan_ack_recorded(run):
        return None
    ack = run.get("autonomous_replan_ack")
    delta_contract = ack.get("delta_contract") if isinstance(ack, dict) else {}
    if not isinstance(delta_contract, dict):
        return None
    compact_delta = {
        "schema_version": delta_contract.get("schema_version"),
        "delta_present": bool(delta_contract.get("delta_present")),
        "delta_kinds": [
            str(item)
            for item in (delta_contract.get("delta_kinds") or [])
            if str(item or "").strip()
        ],
    }
    result = {
        "schema_version": ack.get("schema_version"),
        "recorded": True,
        "source": ack.get("source"),
        "delta_contract": compact_delta,
    }
    agent_id = str(run.get("agent_id") or "").strip()
    if agent_id:
        result["agent_id"] = agent_id
    frontier_identity = str(ack.get("frontier_identity") or "").strip()
    if frontier_identity:
        result["frontier_identity"] = frontier_identity
    generated_at = str(run.get("generated_at") or "").strip()
    if generated_at:
        result["generated_at"] = generated_at
    return result


def latest_blocked_successor_frontier_identity(
    latest_runs: list[dict[str, Any]] | None,
    *,
    agent_id: str | None = None,
) -> str | None:
    normalized_agent_id = str(agent_id or "").strip()
    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        target = (
            run.get("monitor_target")
            if isinstance(run.get("monitor_target"), dict)
            else {}
        )
        if normalized_agent_id:
            run_agent_id = str(run.get("agent_id") or "").strip()
            target_agent_id = str(target.get("agent_id") or "").strip()
            if run_agent_id and target_agent_id and run_agent_id != target_agent_id:
                if normalized_agent_id in {run_agent_id, target_agent_id}:
                    return None
                continue
            attributed_agent_id = run_agent_id or target_agent_id
            if not attributed_agent_id:
                return None
            if attributed_agent_id != normalized_agent_id:
                continue
        classification = str(run.get("classification") or "").strip()
        if classification != "quota_monitor_poll":
            return None
        if target.get("monitor_mode") != (
            "blocked_successor_wait_without_material_transition"
        ):
            continue
        frontier_identity = str(target.get("frontier_identity") or "").strip()
        return frontier_identity or None
    return None


def autonomous_replan_ack_matches_frontier(
    ack: dict[str, Any] | None,
    obligation: dict[str, Any] | None,
) -> bool:
    if not isinstance(obligation, dict):
        return True
    frontier_identity = str(obligation.get("frontier_identity") or "").strip()
    if not frontier_identity:
        return True
    if not isinstance(ack, dict):
        return False
    if str(ack.get("frontier_identity") or "").strip() != frontier_identity:
        return False

    ack_generated_at = parse_timestamp(
        ack.get("generated_at") or ack.get("recorded_at")
    )
    trigger_times = [
        parsed
        for trigger in obligation.get("triggers") or []
        if isinstance(trigger, dict)
        if (
            parsed := parse_timestamp(
                trigger.get("latest_generated_at") or trigger.get("generated_at")
            )
        )
        is not None
    ]
    if ack_generated_at is not None and trigger_times:
        return ack_generated_at >= max(trigger_times)
    return True


def autonomous_replan_ack_matches_agent(
    ack: dict[str, Any] | None,
    *,
    agent_id: str | None,
) -> bool:
    if not isinstance(ack, dict):
        return False
    normalized_agent_id = str(agent_id or "").strip()
    if not normalized_agent_id:
        return True
    ack_agent_id = str(ack.get("agent_id") or "").strip()
    return bool(ack_agent_id and ack_agent_id == normalized_agent_id)


def latest_autonomous_replan_ack_for_projection(
    latest_runs: list[dict[str, Any]] | None,
    *,
    neutral_classifications: set[str],
) -> dict[str, Any] | None:
    """Return a recent durable replan ACK within the material review window."""

    material_run_count = 0
    for run in latest_runs or []:
        if not isinstance(run, dict):
            continue
        replan_ack = compact_autonomous_replan_ack(run)
        if replan_ack:
            return replan_ack
        classification = str(run.get("classification") or "").strip()
        if not classification:
            continue
        if classification in neutral_classifications:
            continue
        if classification == "quota_monitor_poll":
            continue
        material_run_count += 1
        if material_run_count >= AUTONOMOUS_REPLAN_ACK_MATERIAL_RUN_WINDOW:
            return None
    return None
