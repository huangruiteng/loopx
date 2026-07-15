from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ...agent_registry import normalize_registered_agents
from ...control_plane.reward_memory import reward_memory_goal_policy
from ...control_plane.todos.contract import normalize_todo_claimed_by
from .application import normalize_reward_memory_provider_binding
from .ingestion import normalize_reward_memory_standing_policy
from .registry import normalize_reward_memory_corpus


REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION = "reward_memory_experiment_config_v0"
ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER = "issue_fix_maintainer_feedback"

_CONFIG_FIELDS = {
    "schema_version",
    "adapter",
    "corpus",
    "standing_policy",
    "provider_binding",
}


def _read_json_object(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def load_reward_memory_experiment_config(
    *, project: Path, config_path: str
) -> dict[str, Any]:
    path = project / config_path
    try:
        raw = _read_json_object(path)
    except (OSError, ValueError) as exc:
        raise ValueError("reward-memory experiment config is unavailable") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("reward-memory experiment config must be an object")
    unexpected = sorted(set(raw) - _CONFIG_FIELDS)
    if unexpected:
        raise ValueError(
            "reward-memory experiment config contains unsupported fields: "
            + ", ".join(unexpected)
        )
    if raw.get("schema_version") != REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION:
        raise ValueError(
            "reward-memory experiment config must use "
            f"{REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION}"
        )
    if raw.get("adapter") != ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER:
        raise ValueError(
            "reward-memory experiment adapter must be "
            f"{ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER}"
        )
    for key in ("corpus", "standing_policy", "provider_binding"):
        if not isinstance(raw.get(key), Mapping):
            raise ValueError(f"reward-memory experiment {key} must be an object")
    corpus = normalize_reward_memory_corpus(raw["corpus"])
    policy = normalize_reward_memory_standing_policy(raw["standing_policy"])
    binding = normalize_reward_memory_provider_binding(raw["provider_binding"], corpus)
    return {
        "schema_version": REWARD_MEMORY_EXPERIMENT_SCHEMA_VERSION,
        "adapter": ISSUE_FIX_MAINTAINER_FEEDBACK_ADAPTER,
        "corpus": corpus,
        "standing_policy": policy,
        "provider_binding": binding,
    }


def resolve_reward_memory_experiment(
    *, registry_path: Path, goal_id: str, agent_id: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve an agent-scoped experiment without exposing local config details."""

    normalized_agent = normalize_todo_claimed_by(agent_id)
    if not normalized_agent:
        raise ValueError("agent_id must be a public-safe registered agent id")
    registry = _read_json_object(registry_path)
    goals = registry.get("goals") if isinstance(registry.get("goals"), list) else []
    goal = next(
        (
            item
            for item in goals
            if isinstance(item, Mapping) and str(item.get("id")) == goal_id
        ),
        None,
    )
    if goal is None:
        raise ValueError(f"goal_id not found in registry: {goal_id}")
    registered_agents = normalize_registered_agents(
        (goal.get("coordination") or {}).get("registered_agents")
        if isinstance(goal.get("coordination"), Mapping)
        else None
    )
    if normalized_agent not in registered_agents:
        raise ValueError(f"agent_id is not registered for goal {goal_id}")
    policy = reward_memory_goal_policy(goal)
    base = {
        "ok": True,
        "schema_version": "reward_memory_experiment_status_v0",
        "goal_id": goal_id,
        "agent_id": normalized_agent,
        "experimental": policy["experimental"],
        "enabled": policy["enabled"],
        "configured_for_agent": normalized_agent in policy["enabled_agents"],
        "config_pointer_registered": bool(policy["config_path"]),
        "automatic_ingest": False,
        "automatic_recall": False,
        "external_writes_performed": False,
    }
    if not policy["enabled"]:
        return base | {"status": "disabled", "available": False}, None
    if normalized_agent not in policy["enabled_agents"]:
        return base | {"status": "agent_not_enabled", "available": False}, None
    if not policy["config_path"]:
        return base | {"status": "config_missing", "available": False}, None
    project = Path(str(goal.get("repo") or "")).expanduser()
    try:
        config = load_reward_memory_experiment_config(
            project=project,
            config_path=policy["config_path"],
        )
    except ValueError:
        return base | {
            "status": "config_invalid",
            "available": False,
            "reason_code": "config_unavailable_or_invalid",
        }, None
    corpus = config["corpus"]
    binding = config["provider_binding"]
    return base | {
        "status": "available",
        "available": True,
        "adapter": config["adapter"],
        "corpus_id": corpus["corpus_id"],
        "provider_id": binding["provider_id"],
        "surface_ids": list(corpus["scope"]["surface_ids"]),
        "raw_content_captured": False,
    }, config
