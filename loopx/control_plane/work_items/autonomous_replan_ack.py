from __future__ import annotations

from typing import Any


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
    return {
        "schema_version": ack.get("schema_version"),
        "recorded": True,
        "source": ack.get("source"),
        "delta_contract": compact_delta,
    }


def latest_autonomous_replan_ack_for_projection(
    latest_runs: list[dict[str, Any]] | None,
    *,
    neutral_classifications: set[str],
) -> dict[str, Any] | None:
    """Return the newest durable replan ACK, skipping neutral accounting runs."""

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
        return None
    return None
