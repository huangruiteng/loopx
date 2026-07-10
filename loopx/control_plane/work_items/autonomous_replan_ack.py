from __future__ import annotations

from typing import Any


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
    return result


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
