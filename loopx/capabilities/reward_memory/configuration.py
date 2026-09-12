from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import Any

from ...control_plane.operator_inbox_binding import local_private_config_digest
from ...control_plane.reward_memory import reward_memory_goal_policy
from .experiment import (
    load_reward_memory_experiment_config,
    preflight_reward_memory_experiment_config,
)


def plan_reward_memory_goal_configuration(
    *,
    goal: Mapping[str, Any],
    goal_id: str,
    registered_agents: Sequence[str],
    requested_config_path: str | None,
    requested_agents: Sequence[str] | None,
    clear: bool,
    observed_at: str,
    execute: bool,
) -> dict[str, Any]:
    """Validate one Goal-local Reward Memory change before registry mutation."""

    existing = reward_memory_goal_policy(goal)
    agents = list(
        requested_agents if requested_agents is not None else existing["enabled_agents"]
    )
    change_requested = requested_config_path is not None or requested_agents is not None
    config_path = requested_config_path or existing["config_path"]
    if change_requested and not config_path:
        raise ValueError(
            "--reward-memory-agent requires an existing or supplied "
            "--reward-memory-config"
        )
    if change_requested and not agents:
        raise ValueError(
            "enabling Reward Memory requires at least one --reward-memory-agent"
        )
    remains_enabled = not clear and (existing["enabled"] or change_requested)
    unknown_agents = sorted(set(agents) - set(registered_agents))
    if remains_enabled and unknown_agents:
        raise ValueError(
            "Reward Memory agents must already be registered for this goal: "
            + ", ".join(unknown_agents)
        )

    preflight: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    if change_requested and not clear:
        project = Path(str(goal.get("repo") or "")).expanduser()
        config = load_reward_memory_experiment_config(
            project=project,
            config_path=config_path,
        )
        preflight = preflight_reward_memory_experiment_config(
            config,
            goal_id=goal_id,
            agent_ids=agents,
            observed_at=observed_at,
            execute=execute,
        )
        if execute and not preflight["ok"]:
            reason_codes = sorted(
                {
                    reason
                    for receipt in preflight["agent_receipts"].values()
                    for reason in receipt.get("reason_codes") or []
                }
            )
            detail = ", ".join(reason_codes) or "provider_write_preflight_failed"
            raise ValueError(
                "Reward Memory enablement requires a verified provider write and "
                f"exact readback: {detail}"
            )
        policy = {
            "enabled": True,
            "experimental": True,
            "config_path": config_path,
            "enabled_agents": agents,
        }
        if execute:
            config_digest = local_private_config_digest(
                project=project,
                config_path=config_path,
            )
            if not config_digest:
                raise ValueError(
                    "Reward Memory config must remain readable through its exact "
                    "repo-relative pointer during enablement"
                )
            for receipt in preflight["agent_receipts"].values():
                receipt["config_digest"] = config_digest
            policy.update(
                {
                    "config_digest": config_digest,
                    "enablement_receipts": deepcopy(preflight["agent_receipts"]),
                }
            )
    return {
        "change_requested": change_requested or clear,
        "clear": clear,
        "enabled_agents": agents,
        "preflight": preflight,
        "policy": policy,
    }


def apply_reward_memory_goal_configuration(
    goal: dict[str, Any], plan: Mapping[str, Any]
) -> None:
    """Apply a prevalidated plan to the in-memory Goal projection."""

    if not plan.get("change_requested"):
        return
    current = goal.get("control_plane")
    control_plane = dict(current) if isinstance(current, Mapping) else {}
    if plan.get("clear"):
        control_plane.pop("reward_memory", None)
    else:
        control_plane["reward_memory"] = deepcopy(plan["policy"])
    goal["control_plane"] = control_plane


def reward_memory_preflight_markdown_lines(value: object) -> list[str]:
    """Render compact shared CLI/Lark-safe enablement feedback."""

    if not isinstance(value, Mapping):
        return []
    verified = value.get("status") == "verified"
    return [
        f"- reward_memory_preflight: `{value.get('status')}`",
        f"- reward_memory_agent_count: `{value.get('agent_count')}`",
        "- reward_memory_writability: `verified`"
        if verified
        else "- reward_memory_writability: `not_yet_verified`",
    ]
