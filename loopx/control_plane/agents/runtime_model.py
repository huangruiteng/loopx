from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Iterable, Mapping

from ..todos.contract import normalize_todo_claimed_by


PEER_AGENT_IDENTITY_SCHEMA_VERSION = "peer_agent_identity_v1"
PEER_AGENT_RUNTIME_MIGRATION = "peer_agent_runtime_v1"
PEER_AGENT_PROFILE_SCHEMA_VERSION = "agent_profile_v1"
LEGACY_AGENT_PROFILE_SCHEMA_VERSION = "agent_profile_v0"
LEGACY_HIERARCHY_ROLES = {"primary-agent", "side-agent"}


class AgentRuntimeModel(str, Enum):
    PEER_V1 = "peer_v1"


def agent_runtime_model_for_goal(goal: Mapping[str, Any] | None) -> AgentRuntimeModel:
    """Return the only live agent runtime model.

    v0.1 hierarchy fields may still exist in registry snapshots until the
    explicit migration writes them out. They never select hierarchy behavior.
    """

    if isinstance(goal, Mapping):
        coordination = goal.get("coordination")
        raw = coordination.get("agent_model") if isinstance(coordination, Mapping) else None
        raw = raw or goal.get("agent_model")
        if raw not in {None, "", AgentRuntimeModel.PEER_V1.value, "legacy_hierarchy"}:
            raise ValueError("coordination.agent_model must be peer_v1")
    return AgentRuntimeModel.PEER_V1


def legacy_agent_hierarchy_present(goal: Mapping[str, Any] | None) -> bool:
    """Detect v0.1 registry input for migration/status warnings only."""

    if not isinstance(goal, Mapping):
        return False
    coordination = goal.get("coordination")
    if not isinstance(coordination, Mapping):
        return False
    profiles = coordination.get("agent_profiles")
    profile_items = (
        profiles.values()
        if isinstance(profiles, Mapping)
        else profiles
        if isinstance(profiles, list)
        else []
    )
    legacy_profile_present = any(
        isinstance(profile, Mapping)
        and (
            profile.get("schema_version") == LEGACY_AGENT_PROFILE_SCHEMA_VERSION
            or profile.get("role") in LEGACY_HIERARCHY_ROLES
            or profile.get("primary_agent")
            or (
                isinstance(profile.get("review_policy"), Mapping)
                and (
                    profile["review_policy"].get("handoff_agent")
                    or profile["review_policy"].get("reviews_side_agent_work")
                )
            )
        )
        for profile in profile_items
    )
    return bool(
        coordination.get("primary_agent")
        or coordination.get("side_agent_handoff_agent")
        or coordination.get("agent_model") == "legacy_hierarchy"
        or legacy_profile_present
    )


def peer_agent_runtime_migration_id(
    goal_id: str,
    goal: Mapping[str, Any] | None,
) -> str:
    """Return the stable idempotency key for the v0.1 -> peer_v1 cutover."""

    coordination = goal.get("coordination") if isinstance(goal, Mapping) else None
    registered_agents = (
        normalized_peer_agent_ids(coordination.get("registered_agents") or [])
        if isinstance(coordination, Mapping)
        else []
    )
    encoded = json.dumps(
        {
            "goal_id": str(goal_id),
            "migration": PEER_AGENT_RUNTIME_MIGRATION,
            "registered_agents": registered_agents,
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]
    return f"peer_runtime_v1_{digest}"


def completed_peer_agent_runtime_migration(
    goal: Mapping[str, Any] | None,
) -> Mapping[str, Any] | None:
    if not isinstance(goal, Mapping):
        return None
    coordination = goal.get("coordination")
    if not isinstance(coordination, Mapping):
        return None
    completed = coordination.get("completed_migrations")
    if not isinstance(completed, Mapping):
        return None
    migration = completed.get(PEER_AGENT_RUNTIME_MIGRATION)
    return migration if isinstance(migration, Mapping) else None


def agent_identity_is_peer(agent_identity: Mapping[str, Any] | None) -> bool:
    return bool(
        isinstance(agent_identity, Mapping)
        and agent_identity.get("agent_model") == AgentRuntimeModel.PEER_V1.value
    )


def normalized_peer_agent_ids(values: Iterable[Any]) -> list[str]:
    agents = sorted(
        {
            agent
            for value in values
            for agent in [
                normalize_todo_claimed_by(
                    value.get("id") or value.get("agent_id") or value.get("name")
                    if isinstance(value, Mapping)
                    else value
                )
            ]
            if agent
        }
    )
    return agents


def migrate_agent_profiles_to_peer_v1(raw_profiles: Any) -> dict[str, dict[str, Any]]:
    """Normalize advisory profiles while deleting v0.1 hierarchy policy."""

    if isinstance(raw_profiles, Mapping):
        candidates = [(key, value) for key, value in raw_profiles.items()]
    elif isinstance(raw_profiles, list):
        candidates = [
            (
                value.get("agent_id") or value.get("id") or value.get("name"),
                value,
            )
            for value in raw_profiles
            if isinstance(value, Mapping)
        ]
    else:
        return {}
    migrated: dict[str, dict[str, Any]] = {}
    for raw_agent_id, raw_profile in candidates:
        agent_id = normalize_todo_claimed_by(raw_agent_id)
        if not agent_id or not isinstance(raw_profile, Mapping):
            continue
        profile = dict(raw_profile)
        legacy_role = str(profile.pop("role", "") or "").strip()
        profile.pop("primary_agent", None)
        profile["schema_version"] = PEER_AGENT_PROFILE_SCHEMA_VERSION
        profile["agent_id"] = agent_id
        if legacy_role and legacy_role not in LEGACY_HIERARCHY_ROLES:
            profile.setdefault("profile_role", legacy_role)
        # Workspace isolation, merge eligibility, and review routing are task
        # and repository policy. Carrying them in identity profiles recreates
        # rank by another name.
        profile.pop("worktree_policy", None)
        profile.pop("review_policy", None)
        migrated[agent_id] = profile
    return migrated


def peer_work_key(value: Mapping[str, Any] | None, *, fallback: str) -> str:
    if not isinstance(value, Mapping):
        return fallback
    encoded = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def select_peer_for_work(
    registered_agents: Iterable[Any],
    *,
    work_key: str,
) -> str | None:
    agents = normalized_peer_agent_ids(registered_agents)
    if not agents:
        return None
    digest = hashlib.sha256(str(work_key).encode("utf-8")).digest()
    index = int.from_bytes(digest[:8], "big") % len(agents)
    return agents[index]
