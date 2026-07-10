from __future__ import annotations

import json
import os
import shlex
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .boundary_authority import (
    build_checkpointed_boundary_authority_entry,
    checkpointed_boundary_authority_summary,
)
from .agent_registry import normalize_registered_agents
from .control_plane import compact_control_plane_policy, control_plane_policy_summary
from .orchestration import (
    DEFAULT_ORCHESTRATION_MODE,
    EXPLORE_HARNESS_PROFILES,
    MULTI_SUBAGENT_ORCHESTRATION_MODE,
    compact_orchestration_policy,
    orchestration_policy_summary,
)
from .quota import goal_quota_config
from .registry import read_json, registry_goals
from .control_plane.todos.contract import normalize_todo_claimed_by
from .control_plane.agents.runtime_model import (
    AgentRuntimeModel,
    PEER_AGENT_RUNTIME_MIGRATION,
    agent_runtime_model_for_goal,
    completed_peer_agent_runtime_migration,
    legacy_agent_hierarchy_present,
    migrate_agent_profiles_to_peer_v1,
    normalized_peer_agent_ids,
    peer_agent_runtime_migration_completed,
    peer_agent_runtime_migration_id,
)


WAITING_ON_CHOICES = (
    "codex",
    "user_or_controller",
    "controller",
    "external_evidence",
)

MULTI_SUBAGENT_FEATURE_CHOICES = ("off", "enabled")
DEFAULT_MULTI_SUBAGENT_MAX_CHILDREN = 2
AGENT_MODEL_CHOICES = tuple(model.value for model in AgentRuntimeModel)


def _now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _positive_number(value: float | None, *, field: str) -> float | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return float(value)


def _non_negative_int(value: int | None, *, field: str) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError(f"{field} must be greater than or equal to 0")
    return int(value)


def _clean_domains(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    domains: list[str] = []
    for value in values:
        for part in str(value).split(","):
            domain = part.strip()
            if domain and domain not in domains:
                domains.append(domain)
    return domains


def _clean_registered_agents(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    agents: list[str] = []
    for value in values:
        for part in str(value).split(","):
            raw_agent = part.strip()
            if not raw_agent:
                continue
            agent = normalize_todo_claimed_by(raw_agent)
            if not agent:
                raise ValueError("registered agents must be public-safe tokens such as codex-main-control")
            if agent not in agents:
                agents.append(agent)
    return agents


def _clean_write_scope(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    scopes: list[str] = []
    for value in values:
        for part in str(value).split(","):
            scope = part.strip()
            if scope and scope not in scopes:
                scopes.append(scope)
    return scopes


def _settings_summary(goal: dict[str, Any]) -> dict[str, Any]:
    quota = goal_quota_config(goal)
    control_plane = compact_control_plane_policy(goal.get("control_plane"))
    orchestration = compact_orchestration_policy(goal.get("spawn_policy"))
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    agent_model = agent_runtime_model_for_goal(goal)
    summary = {
        "quota": {
            "compute": quota.get("compute"),
            "window_hours": quota.get("window_hours"),
        },
        "control_plane": control_plane,
        "orchestration": orchestration,
        "waiting_on": goal.get("waiting_on"),
        "write_scope": _clean_write_scope(coordination.get("write_scope") or []) or [],
        "checkpointed_boundary_authority": checkpointed_boundary_authority_summary(coordination),
        "registered_agents": normalize_registered_agents(coordination.get("registered_agents")),
        "agent_model": agent_model.value,
        "configured_agent_model": coordination.get("agent_model"),
        "legacy_hierarchy_present": legacy_agent_hierarchy_present(goal),
        "peer_runtime_migration": deepcopy(
            completed_peer_agent_runtime_migration(goal)
        ),
    }
    return summary


def _multi_subagent_feature_status(orchestration: dict[str, Any]) -> str:
    if (
        orchestration.get("mode") == MULTI_SUBAGENT_ORCHESTRATION_MODE
        and orchestration.get("spawn_allowed") is True
        and int(orchestration.get("max_children") or 0) > 0
    ):
        return "enabled"
    return "off"


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for group, before_value in before.items():
        after_value = after.get(group)
        if before_value != after_value:
            changed.append(group)
    return changed


def _heartbeat_scope_hint(
    agent_id: str,
) -> str:
    del agent_id
    return "peer task claims, leases, evidence, and bounded delivery"


def _build_heartbeat_prompt_migration(
    *,
    goal_id: str,
    changed_fields: list[str],
    after: dict[str, Any],
    migration_id: str | None = None,
    migration_acknowledged: bool = False,
) -> dict[str, Any] | None:
    if not migration_id and not any(
        field in changed_fields
        for field in (
            "registered_agents",
            "configured_agent_model",
            "legacy_hierarchy_present",
        )
    ):
        return None
    registered_agents = [
        str(agent).strip()
        for agent in after.get("registered_agents") or []
        if str(agent).strip()
    ]
    if not registered_agents:
        return None
    agent_model = AgentRuntimeModel.PEER_V1.value
    ordered_agents = list(registered_agents)
    commands = []
    for agent in ordered_agents:
        scope = _heartbeat_scope_hint(agent)
        command = {
            "agent_id": agent,
            "command": (
                "loopx heartbeat-prompt --thin "
                f"--goal-id {shlex.quote(goal_id)} "
                f"--agent-id {shlex.quote(agent)} "
                f"--agent-scope {shlex.quote(scope)}"
            ),
        }
        commands.append(command)
    payload = {
        "schema_version": "heartbeat_prompt_migration_v1",
        "agent_model": agent_model,
        "migration_id": migration_id,
        "host_update_idempotency_key": migration_id,
        "status": "completed" if migration_acknowledged else "required",
        "reason": (
            "the host automation update was acknowledged and the registry hard cut completed"
            if migration_acknowledged
            else "coordination agent identity changed; installed heartbeats should be "
            "regenerated with identity-aware prompt args"
        ),
        "action": (
            "none; this migration id is complete and will not be projected again"
            if migration_acknowledged
            else "update each installed host automation once using migration_id as the "
            "idempotency key, then run completion_command"
        ),
        "commands": [] if migration_acknowledged else commands,
    }
    if migration_id and not migration_acknowledged:
        payload["completion_command"] = (
            "loopx configure-goal "
            f"--goal-id {shlex.quote(goal_id)} "
            f"--ack-automation-prompt-migration {shlex.quote(migration_id)} --execute"
        )
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def configure_goal(
    *,
    registry_path: Path,
    goal_id: str,
    quota_compute: float | None = None,
    quota_window_hours: float | None = None,
    self_repair_enabled: bool | None = None,
    self_repair_health: bool | None = None,
    self_repair_waiting_projection: bool | None = None,
    multi_subagent_feature: str | None = None,
    orchestration_mode: str | None = None,
    spawn_allowed: bool | None = None,
    max_children: int | None = None,
    allowed_domains: list[str] | None = None,
    clear_allowed_domains: bool = False,
    explore_harness_enabled: bool | None = None,
    explore_harness_profile: str | None = None,
    clear_explore_harness_profile: bool = False,
    registered_agents: list[str] | None = None,
    clear_registered_agents: bool = False,
    agent_model: str | None = None,
    automation_prompt_migration_ack: str | None = None,
    write_scope: list[str] | None = None,
    replace_write_scope: bool = False,
    clear_write_scope: bool = False,
    waiting_on: str | None = None,
    clear_waiting_on: bool = False,
    boundary_authority_scopes: list[str] | None = None,
    boundary_authority_source: str | None = None,
    boundary_authority_decision_id: str | None = None,
    boundary_authority_recorded_at: str | None = None,
    boundary_authority_expires_at: str | None = None,
    clear_boundary_authority: bool = False,
    execute: bool = False,
) -> dict[str, Any]:
    if not registry_path.exists():
        raise FileNotFoundError(f"registry file does not exist: {registry_path}")
    if clear_allowed_domains and allowed_domains:
        raise ValueError("--clear-allowed-domains cannot be combined with --allowed-domain")
    if clear_explore_harness_profile and explore_harness_profile:
        raise ValueError(
            "--clear-explore-harness-profile cannot be combined with --explore-harness-profile"
        )
    if clear_registered_agents and registered_agents:
        raise ValueError("--clear-registered-agents cannot be combined with --registered-agent")
    if agent_model is not None:
        agent_model = str(agent_model).strip().lower()
        if agent_model not in AGENT_MODEL_CHOICES:
            raise ValueError("--agent-model must be one of: " + ", ".join(AGENT_MODEL_CHOICES))
    if automation_prompt_migration_ack is not None:
        automation_prompt_migration_ack = str(
            automation_prompt_migration_ack
        ).strip()
        if not automation_prompt_migration_ack:
            raise ValueError("--ack-automation-prompt-migration requires a migration id")
        if registered_agents is not None or clear_registered_agents:
            raise ValueError(
                "--ack-automation-prompt-migration cannot change registered agents; "
                "complete the runtime cutover first, then update the peer set separately"
            )
    if clear_write_scope and write_scope:
        raise ValueError("--clear-write-scope cannot be combined with --write-scope")
    if replace_write_scope and not write_scope:
        raise ValueError("--replace-write-scope requires --write-scope")
    if clear_write_scope and replace_write_scope:
        raise ValueError("--clear-write-scope cannot be combined with --replace-write-scope")
    if clear_waiting_on and waiting_on:
        raise ValueError("--clear-waiting-on cannot be combined with --waiting-on")
    adding_boundary_authority = any(
        value
        for value in (
            boundary_authority_scopes,
            boundary_authority_source,
            boundary_authority_decision_id,
            boundary_authority_recorded_at,
            boundary_authority_expires_at,
        )
    )
    if clear_boundary_authority and adding_boundary_authority:
        raise ValueError("--clear-boundary-authority cannot be combined with boundary authority fields")
    if waiting_on and waiting_on not in WAITING_ON_CHOICES:
        raise ValueError("--waiting-on must be one of: " + ", ".join(WAITING_ON_CHOICES))
    if multi_subagent_feature is not None and multi_subagent_feature not in MULTI_SUBAGENT_FEATURE_CHOICES:
        raise ValueError("--multi-subagent-feature must be one of: " + ", ".join(MULTI_SUBAGENT_FEATURE_CHOICES))
    if multi_subagent_feature is not None and (orchestration_mode is not None or spawn_allowed is not None):
        raise ValueError(
            "--multi-subagent-feature cannot be combined with --orchestration-mode or --spawn-allowed; "
            "use --max-children/--allowed-domain for bounded feature settings"
        )
    if explore_harness_profile is not None:
        explore_harness_profile = str(explore_harness_profile).strip().lower().replace("_", "-")
        if explore_harness_profile not in EXPLORE_HARNESS_PROFILES:
            raise ValueError(
                "--explore-harness-profile must be one of: "
                + ", ".join(EXPLORE_HARNESS_PROFILES)
            )

    quota_compute = _positive_number(quota_compute, field="quota_compute")
    quota_window_hours = _positive_number(quota_window_hours, field="quota_window_hours")
    max_children = _non_negative_int(max_children, field="max_children")
    allowed_domains = _clean_domains(allowed_domains)
    if multi_subagent_feature == "off":
        if max_children not in (None, 0):
            raise ValueError("--multi-subagent-feature off cannot be combined with --max-children greater than 0")
        if allowed_domains:
            raise ValueError("--multi-subagent-feature off cannot be combined with --allowed-domain")
    registered_agents = _clean_registered_agents(registered_agents)
    write_scope = _clean_write_scope(write_scope)

    payload = read_json(registry_path)
    goals = registry_goals(payload)
    goal = next((item for item in goals if str(item.get("id")) == goal_id), None)
    if goal is None:
        raise ValueError(f"goal_id not found in registry: {goal_id}")

    before_goal = deepcopy(goal)
    before = _settings_summary(before_goal)
    legacy_hierarchy_before = legacy_agent_hierarchy_present(before_goal)
    expected_migration_id = peer_agent_runtime_migration_id(goal_id, before_goal)
    completed_migration_before = completed_peer_agent_runtime_migration(before_goal)
    migration_completed_before = peer_agent_runtime_migration_completed(before_goal)
    migration_already_completed = bool(
        completed_migration_before
        and completed_migration_before.get("migration_id")
        == automation_prompt_migration_ack
        and migration_completed_before
    )
    if automation_prompt_migration_ack is not None:
        if migration_already_completed:
            pass
        elif not legacy_hierarchy_before:
            raise ValueError(
                "no pending peer runtime automation migration matches this goal"
            )
        elif automation_prompt_migration_ack != expected_migration_id:
            raise ValueError(
                "automation prompt migration id does not match the current goal state; "
                f"expected {expected_migration_id}"
            )
    elif execute and legacy_hierarchy_before and not migration_completed_before and (
        agent_model is not None
        or registered_agents is not None
        or clear_registered_agents
    ):
        raise ValueError(
            "legacy agent hierarchy requires the one-time host automation migration first; "
            "regenerate/update the installed peer heartbeat, then run "
            f"`loopx configure-goal --goal-id {goal_id} "
            f"--ack-automation-prompt-migration {expected_migration_id} --execute`"
        )

    if quota_compute is not None or quota_window_hours is not None:
        quota = goal.get("quota") if isinstance(goal.get("quota"), dict) else {}
        if quota_compute is not None:
            quota["compute"] = quota_compute
        if quota_window_hours is not None:
            quota["window_hours"] = quota_window_hours
        goal["quota"] = quota

    if (
        self_repair_enabled is not None
        or self_repair_health is not None
        or self_repair_waiting_projection is not None
    ):
        control_plane = goal.get("control_plane") if isinstance(goal.get("control_plane"), dict) else {}
        self_repair = control_plane.get("self_repair") if isinstance(control_plane.get("self_repair"), dict) else {}
        if self_repair_enabled is not None:
            self_repair["enabled"] = self_repair_enabled
        if self_repair_health is not None:
            self_repair["allow_health_blocker_repair"] = self_repair_health
        if self_repair_waiting_projection is not None:
            self_repair["allow_waiting_projection_repair"] = self_repair_waiting_projection
        control_plane["self_repair"] = self_repair
        goal["control_plane"] = control_plane

    if (
        multi_subagent_feature is not None
        or
        orchestration_mode is not None
        or spawn_allowed is not None
        or max_children is not None
        or allowed_domains is not None
        or clear_allowed_domains
        or explore_harness_enabled is not None
        or explore_harness_profile is not None
        or clear_explore_harness_profile
    ):
        spawn_policy = goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else {}
        if multi_subagent_feature == "enabled":
            spawn_policy["mode"] = MULTI_SUBAGENT_ORCHESTRATION_MODE
            spawn_policy["allowed"] = True
            if max_children is None:
                existing_children = int(compact_orchestration_policy(spawn_policy).get("max_children") or 0)
                spawn_policy["max_children"] = (
                    existing_children
                    if existing_children > 0
                    else DEFAULT_MULTI_SUBAGENT_MAX_CHILDREN
                )
        elif multi_subagent_feature == "off":
            spawn_policy["mode"] = DEFAULT_ORCHESTRATION_MODE
            spawn_policy["allowed"] = False
            spawn_policy["max_children"] = 0
            spawn_policy["allowed_domains"] = []
        elif orchestration_mode is not None:
            spawn_policy["mode"] = orchestration_mode
        if spawn_allowed is not None:
            spawn_policy["allowed"] = spawn_allowed
        if max_children is not None:
            spawn_policy["max_children"] = max_children
        if clear_allowed_domains:
            spawn_policy["allowed_domains"] = []
        elif allowed_domains is not None:
            spawn_policy["allowed_domains"] = allowed_domains
        if (
            explore_harness_enabled is not None
            or explore_harness_profile is not None
            or clear_explore_harness_profile
        ):
            explore_harness = (
                spawn_policy.get("explore_harness")
                if isinstance(spawn_policy.get("explore_harness"), dict)
                else {}
            )
            if explore_harness_enabled is not None:
                explore_harness["enabled"] = explore_harness_enabled
            if clear_explore_harness_profile:
                explore_harness.pop("profile", None)
            elif explore_harness_profile is not None:
                explore_harness["profile"] = explore_harness_profile
            if explore_harness:
                spawn_policy["explore_harness"] = explore_harness
            else:
                spawn_policy.pop("explore_harness", None)
        goal["spawn_policy"] = spawn_policy

    if waiting_on is not None:
        goal["waiting_on"] = waiting_on
    elif clear_waiting_on:
        goal.pop("waiting_on", None)

    if (
        clear_registered_agents
        or registered_agents is not None
        or agent_model is not None
        or automation_prompt_migration_ack is not None
        or write_scope is not None
        or clear_write_scope
        or clear_boundary_authority
        or adding_boundary_authority
    ):
        coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
        effective_agent_model = AgentRuntimeModel.PEER_V1.value
        if clear_registered_agents:
            coordination.pop("registered_agents", None)
            coordination.pop("agent_model", None)
        elif registered_agents is not None:
            coordination["registered_agents"] = registered_agents
        if not clear_registered_agents:
            coordination["agent_model"] = effective_agent_model
        if automation_prompt_migration_ack is not None and not migration_already_completed:
            coordination.pop("primary_agent", None)
            coordination.pop("side_agent_handoff_agent", None)
            coordination["registered_agents"] = normalized_peer_agent_ids(
                coordination.get("registered_agents") or []
            )
            migrated_profiles = migrate_agent_profiles_to_peer_v1(
                coordination.get("agent_profiles")
            )
            if migrated_profiles:
                coordination["agent_profiles"] = migrated_profiles
            else:
                coordination.pop("agent_profiles", None)
            completed_migrations = (
                coordination.get("completed_migrations")
                if isinstance(coordination.get("completed_migrations"), dict)
                else {}
            )
            completed_migrations[PEER_AGENT_RUNTIME_MIGRATION] = {
                "migration_id": automation_prompt_migration_ack,
                "status": "completed",
                "completed_at": _now_iso() if execute else None,
            }
            coordination["completed_migrations"] = completed_migrations
        if clear_write_scope:
            coordination["write_scope"] = []
        elif write_scope is not None:
            if replace_write_scope:
                coordination["write_scope"] = write_scope
            else:
                existing_write_scope = _clean_write_scope(coordination.get("write_scope") or []) or []
                coordination["write_scope"] = _clean_write_scope([*existing_write_scope, *write_scope]) or []
        if clear_boundary_authority:
            coordination.pop("checkpointed_boundary_authority", None)
        if adding_boundary_authority:
            entry = build_checkpointed_boundary_authority_entry(
                write_scopes=boundary_authority_scopes or [],
                source=boundary_authority_source or "",
                decision_id=boundary_authority_decision_id,
                recorded_at=boundary_authority_recorded_at,
                expires_at=boundary_authority_expires_at,
            )
            entries = (
                coordination.get("checkpointed_boundary_authority")
                if isinstance(coordination.get("checkpointed_boundary_authority"), list)
                else []
            )
            coordination["checkpointed_boundary_authority"] = [*entries, entry]
        goal["coordination"] = coordination

    after = _settings_summary(goal)
    changed_fields = _changed_fields(before, after)
    dry_run = not execute
    model_changed = bool(
        before.get("legacy_hierarchy_present")
        or before.get("agent_model") != after.get("agent_model")
        or automation_prompt_migration_ack is not None
    )
    backup_path = None

    if execute and changed_fields:
        payload["updated_at"] = _now_iso()
        if model_changed:
            stamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z")
            backup_path = registry_path.with_name(
                f"{registry_path.name}.before-agent-model-{stamp}.bak"
            )
            shutil.copy2(registry_path, backup_path)
        _atomic_write_json(registry_path, payload)

    return {
        "ok": True,
        "dry_run": dry_run,
        "execute": execute,
        "registry": str(registry_path),
        "goal_id": goal_id,
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "backup_path": str(backup_path) if backup_path else None,
        "before": before,
        "after": after,
        "written": bool(execute and changed_fields),
        "automation_prompt_migration": {
            "migration_id": automation_prompt_migration_ack,
            "status": (
                "already_completed"
                if migration_already_completed
                else "completed"
                if automation_prompt_migration_ack is not None
                else "pending"
                if legacy_hierarchy_before
                else "not_required"
            ),
            "exactly_once_effect": True,
        },
        "control_plane_summary": control_plane_policy_summary(after.get("control_plane")),
        "orchestration_summary": orchestration_policy_summary(after.get("orchestration")),
        "feature_summary": {
            "multi_subagent": _multi_subagent_feature_status(after.get("orchestration") or {}),
            "explore_harness": deepcopy(
                (after.get("orchestration") or {}).get("explore_harness")
                or {"enabled": False}
            ),
            "default": "off",
            "configuration_entry": "multi_subagent_feature",
        },
        "heartbeat_prompt_migration": _build_heartbeat_prompt_migration(
            goal_id=goal_id,
            changed_fields=changed_fields,
            after=after,
            migration_id=(
                automation_prompt_migration_ack
                if automation_prompt_migration_ack is not None
                else expected_migration_id
                if legacy_hierarchy_before and not migration_completed_before
                else None
            ),
            migration_acknowledged=automation_prompt_migration_ack is not None,
        ),
    }


def render_configure_goal_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# LoopX Goal Configuration",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- changed: `{payload.get('changed')}`",
        f"- written: `{payload.get('written')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
        return "\n".join(lines)
    fields = payload.get("changed_fields") or []
    lines.append(f"- changed_fields: `{', '.join(fields) if fields else 'none'}`")
    if payload.get("control_plane_summary"):
        lines.append(f"- control_plane: {payload.get('control_plane_summary')}")
    if payload.get("orchestration_summary"):
        lines.append(f"- orchestration: {payload.get('orchestration_summary')}")
    feature_summary = payload.get("feature_summary")
    if isinstance(feature_summary, dict):
        lines.append(f"- feature_multi_subagent: `{feature_summary.get('multi_subagent')}`")
        harness = feature_summary.get("explore_harness")
        if isinstance(harness, dict):
            harness_state = "on" if harness.get("enabled") else "off"
            if harness.get("profile"):
                harness_state += f"({harness.get('profile')})"
            lines.append(f"- feature_explore_harness: `{harness_state}`")
    migration = payload.get("heartbeat_prompt_migration")
    if isinstance(migration, dict):
        lines.append(f"- heartbeat_prompt_migration: {migration.get('action')}")
        for command in migration.get("commands") or []:
            if not isinstance(command, dict):
                continue
            lines.append(
                f"  - {command.get('agent_id')}: `{command.get('command')}`"
            )
    activation = payload.get("host_loop_activation")
    if isinstance(activation, dict):
        lines.append(
            f"- host_loop_activation: `{activation.get('host_surface')}` "
            f"status=`{activation.get('status')}` "
            f"activated=`{activation.get('activated')}`"
        )
        if activation.get("activated") is not True:
            lines.append(f"- host_loop_action: {activation.get('recommended_action')}")
    lines.extend(
        [
            "",
            "## Before",
            "",
            "```json",
            json.dumps(payload.get("before") or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## After",
            "",
            "```json",
            json.dumps(payload.get("after") or {}, ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines)
