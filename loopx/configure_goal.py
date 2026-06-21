from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .boundary_authority import (
    build_checkpointed_boundary_authority_entry,
    checkpointed_boundary_authority_summary,
)
from .agent_registry import normalize_registered_agents, primary_agent_id_for_goal
from .control_plane import compact_control_plane_policy, control_plane_policy_summary
from .orchestration import compact_orchestration_policy, orchestration_policy_summary
from .quota import goal_quota_config
from .registry import read_json, registry_goals
from .todo_contract import normalize_todo_claimed_by


WAITING_ON_CHOICES = (
    "codex",
    "user_or_controller",
    "controller",
    "external_evidence",
)


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


def _settings_summary(goal: dict[str, Any]) -> dict[str, Any]:
    quota = goal_quota_config(goal)
    control_plane = compact_control_plane_policy(goal.get("control_plane"))
    orchestration = compact_orchestration_policy(goal.get("spawn_policy"))
    coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
    return {
        "quota": {
            "compute": quota.get("compute"),
            "window_hours": quota.get("window_hours"),
        },
        "control_plane": control_plane,
        "orchestration": orchestration,
        "waiting_on": goal.get("waiting_on"),
        "checkpointed_boundary_authority": checkpointed_boundary_authority_summary(coordination),
        "registered_agents": normalize_registered_agents(coordination.get("registered_agents")),
        "primary_agent": primary_agent_id_for_goal(goal),
    }


def _changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    for group, before_value in before.items():
        after_value = after.get(group)
        if before_value != after_value:
            changed.append(group)
    return changed


def configure_goal(
    *,
    registry_path: Path,
    goal_id: str,
    quota_compute: float | None = None,
    quota_window_hours: float | None = None,
    self_repair_enabled: bool | None = None,
    self_repair_health: bool | None = None,
    self_repair_waiting_projection: bool | None = None,
    orchestration_mode: str | None = None,
    spawn_allowed: bool | None = None,
    max_children: int | None = None,
    allowed_domains: list[str] | None = None,
    clear_allowed_domains: bool = False,
    registered_agents: list[str] | None = None,
    clear_registered_agents: bool = False,
    primary_agent: str | None = None,
    clear_primary_agent: bool = False,
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
    if clear_registered_agents and registered_agents:
        raise ValueError("--clear-registered-agents cannot be combined with --registered-agent")
    if clear_primary_agent and primary_agent:
        raise ValueError("--clear-primary-agent cannot be combined with --primary-agent")
    if clear_registered_agents and primary_agent:
        raise ValueError("--clear-registered-agents cannot be combined with --primary-agent")
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

    quota_compute = _positive_number(quota_compute, field="quota_compute")
    quota_window_hours = _positive_number(quota_window_hours, field="quota_window_hours")
    max_children = _non_negative_int(max_children, field="max_children")
    allowed_domains = _clean_domains(allowed_domains)
    registered_agents = _clean_registered_agents(registered_agents)
    normalized_primary_agent = normalize_todo_claimed_by(primary_agent) if primary_agent else None
    if primary_agent and not normalized_primary_agent:
        raise ValueError("--primary-agent must be a public-safe registered agent id")

    payload = read_json(registry_path)
    goals = registry_goals(payload)
    goal = next((item for item in goals if str(item.get("id")) == goal_id), None)
    if goal is None:
        raise ValueError(f"goal_id not found in registry: {goal_id}")

    before_goal = deepcopy(goal)
    before = _settings_summary(before_goal)

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
        orchestration_mode is not None
        or spawn_allowed is not None
        or max_children is not None
        or allowed_domains is not None
        or clear_allowed_domains
    ):
        spawn_policy = goal.get("spawn_policy") if isinstance(goal.get("spawn_policy"), dict) else {}
        if orchestration_mode is not None:
            spawn_policy["mode"] = orchestration_mode
        if spawn_allowed is not None:
            spawn_policy["allowed"] = spawn_allowed
        if max_children is not None:
            spawn_policy["max_children"] = max_children
        if clear_allowed_domains:
            spawn_policy["allowed_domains"] = []
        elif allowed_domains is not None:
            spawn_policy["allowed_domains"] = allowed_domains
        goal["spawn_policy"] = spawn_policy

    if waiting_on is not None:
        goal["waiting_on"] = waiting_on
    elif clear_waiting_on:
        goal.pop("waiting_on", None)

    if (
        clear_registered_agents
        or registered_agents is not None
        or normalized_primary_agent is not None
        or clear_primary_agent
        or clear_boundary_authority
        or adding_boundary_authority
    ):
        coordination = goal.get("coordination") if isinstance(goal.get("coordination"), dict) else {}
        existing_registered_agents = normalize_registered_agents(coordination.get("registered_agents"))
        effective_registered_agents = registered_agents if registered_agents is not None else existing_registered_agents
        if normalized_primary_agent and normalized_primary_agent not in effective_registered_agents:
            raise ValueError(
                f"--primary-agent {normalized_primary_agent!r} must also be listed in coordination.registered_agents; "
                "pass --registered-agent for it in the same command or register it first"
            )
        if clear_registered_agents:
            coordination.pop("registered_agents", None)
            coordination.pop("primary_agent", None)
        elif registered_agents is not None:
            coordination["registered_agents"] = registered_agents
        if clear_primary_agent:
            coordination.pop("primary_agent", None)
        elif normalized_primary_agent is not None:
            coordination["primary_agent"] = normalized_primary_agent
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

    if execute and changed_fields:
        payload["updated_at"] = _now_iso()
        registry_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    return {
        "ok": True,
        "dry_run": dry_run,
        "execute": execute,
        "registry": str(registry_path),
        "goal_id": goal_id,
        "changed": bool(changed_fields),
        "changed_fields": changed_fields,
        "before": before,
        "after": after,
        "written": bool(execute and changed_fields),
        "control_plane_summary": control_plane_policy_summary(after.get("control_plane")),
        "orchestration_summary": orchestration_policy_summary(after.get("orchestration")),
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
