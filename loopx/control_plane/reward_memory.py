from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .todos.contract import normalize_todo_claimed_by


def reward_memory_goal_policy(goal: Mapping[str, Any]) -> dict[str, Any]:
    """Return the provider-neutral opt-in policy for one goal."""

    control_plane = (
        goal.get("control_plane")
        if isinstance(goal.get("control_plane"), Mapping)
        else {}
    )
    raw = (
        control_plane.get("reward_memory")
        if isinstance(control_plane.get("reward_memory"), Mapping)
        else {}
    )
    enabled_agents: list[str] = []
    for value in raw.get("enabled_agents") or []:
        agent_id = normalize_todo_claimed_by(value)
        if agent_id and agent_id not in enabled_agents:
            enabled_agents.append(agent_id)
    experimental = raw.get("experimental") is True
    enablement_receipts: dict[str, dict[str, Any]] = {}
    raw_receipts = raw.get("enablement_receipts")
    if isinstance(raw_receipts, Mapping):
        for agent_id in enabled_agents:
            receipt = raw_receipts.get(agent_id)
            if not isinstance(receipt, Mapping):
                continue
            enablement_receipts[agent_id] = {
                key: receipt[key]
                for key in (
                    "schema_version",
                    "status",
                    "goal_id",
                    "agent_id",
                    "config_digest",
                    "provider_id",
                    "isolation_mode",
                    "actor_binding_verified",
                    "writability_verified",
                    "exact_readback_verified",
                    "probe_count",
                    "write_count",
                    "external_writes_performed",
                    "observed_at",
                    "provider_preflight_performed",
                    "reason_codes",
                )
                if key in receipt
            }
    return {
        "enabled": raw.get("enabled") is True and experimental,
        "experimental": experimental,
        "config_path": str(raw.get("config_path") or "").strip(),
        "config_digest": str(raw.get("config_digest") or "").strip(),
        "enabled_agents": enabled_agents,
        "enablement_receipts": enablement_receipts,
    }


def reward_memory_goal_policy_summary(goal: Mapping[str, Any]) -> dict[str, Any]:
    policy = reward_memory_goal_policy(goal)
    return {
        "enabled": policy["enabled"],
        "experimental": policy["experimental"],
        "config_pointer_registered": bool(policy["config_path"]),
        "enabled_agents": list(policy["enabled_agents"]),
        "enablement_verified_agents": sorted(
            agent_id
            for agent_id, receipt in policy["enablement_receipts"].items()
            if receipt.get("status") == "verified"
            and receipt.get("writability_verified") is True
            and receipt.get("exact_readback_verified") is True
        ),
    }
