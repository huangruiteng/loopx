from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .execution_profile import (
    build_execution_profile,
    compact_execution_profile,
    execution_profile_summary,
)
from .global_registry import sync_project_registry_to_global
from .orchestration import (
    DEFAULT_ORCHESTRATION_MODE,
    MULTI_SUBAGENT_ORCHESTRATION_MODE,
)
from .paths import DEFAULT_RUNTIME_ROOT, rel_or_abs


DEFAULT_OBJECTIVE = "Improve this project through bounded, verified goal segments."
DEFAULT_DOMAIN = "project-goal-control-plane"


def slugify_goal_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "project-goal"


def default_goal_id(project: Path) -> str:
    return f"{slugify_goal_id(project.name)}-goal"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_project_path(project: Path, path: Path | None) -> Path | None:
    if path is None:
        return None
    path = path.expanduser()
    return path if path.is_absolute() else project / path


def render_authority_sources(project: Path, goal_doc: Path | None) -> str:
    if not goal_doc:
        return "- No explicit goal document was provided during bootstrap."
    return f"- Primary goal document: `{rel_or_abs(goal_doc, project)}`"


def render_state_markdown(
    *,
    project: Path,
    goal_id: str,
    objective: str,
    updated_at: str,
    goal_doc: Path | None,
    execution_profile: dict[str, Any] | None,
) -> str:
    safe_objective = objective.replace('"', '\\"')
    profile_summary = execution_profile_summary(execution_profile)
    return f"""---
status: active
owner_mode: goal
objective: "{safe_objective}"
updated_at: {updated_at}
adapter_id: {goal_id}
---

# Active Goal State

## Objective

{objective}

## Authority Sources

{render_authority_sources(project, goal_doc)}

## Operating Contract

- Treat this file as the durable goal state for future agent ticks.
- Treat the authority sources above as the first context to inspect before acting.
- Read current project evidence before choosing the next action.
- Run a bounded progress segment when useful; it does not have to be one tiny step.
- Keep private evidence, credentials, local paths, and raw logs out of public commits.
- End each tick with changed files, validation, residual risk, and the next action.

## Execution Profile

- `{profile_summary}`
- Repeated small-scale follow-through should expand the next delivery batch or report a blocker before spending quota.

## Non-Goals

- Do not perform irreversible production operations without explicit approval.
- Do not publish private project evidence.
- Do not optimize for activity if no useful artifact or decision can be produced.

## Next Action

- Run `goal-harness check` against the project registry and decide the first project-specific adapter signal.

## Recent User Feedback

- Initialized by `goal-harness bootstrap`.

## Progress Ledger

- Created the initial goal state and registry connection.
"""


def relative_state_file(project: Path, state_file: Path) -> str:
    return rel_or_abs(state_file, project)


def build_goal_entry(
    *,
    project: Path,
    goal_id: str,
    domain: str,
    role: str,
    parent_goal_id: str | None,
    state_file: Path,
    goal_doc: Path | None,
    adapter_kind: str,
    adapter_status: str,
    next_probe: str | None,
    spawn_allowed: bool,
    max_children: int,
    allowed_domains: list[str],
    write_scope: list[str],
    claim_ttl_minutes: int,
    execution_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    authority_sources = []
    if goal_doc:
        authority_sources.append(
            {
                "kind": "goal_doc",
                "path": rel_or_abs(goal_doc, project),
                "role": "primary_goal_document",
            }
        )
    return {
        "id": goal_id,
        "domain": domain,
        "status": "active",
        "role": role,
        "parent_goal_id": parent_goal_id,
        "repo": str(project),
        "state_file": relative_state_file(project, state_file),
        "authority_sources": authority_sources,
        "adapter": {
            "kind": adapter_kind,
            "status": adapter_status,
        },
        "spawn_policy": {
            "mode": (
                MULTI_SUBAGENT_ORCHESTRATION_MODE
                if spawn_allowed and max(0, max_children) > 0
                else DEFAULT_ORCHESTRATION_MODE
            ),
            "allowed": spawn_allowed,
            "max_children": max(0, max_children),
            "allowed_domains": allowed_domains,
        },
        "coordination": {
            "write_scope": write_scope,
            "claim_ttl_minutes": max(1, claim_ttl_minutes),
            "requires_parent_approval": [
                "write",
                "publish",
                "production-action",
            ],
        },
        "execution_profile": compact_execution_profile(execution_profile),
        "next_probe": next_probe
        or f"goal-harness --registry .goal-harness/registry.json check --scan-root {project}",
        "guards": [
            "read-only by default",
            "do not mutate production systems without explicit user approval",
            "keep private evidence out of public commits",
        ],
    }


def merge_goal(registry: dict[str, Any], goal_entry: dict[str, Any], *, force: bool) -> tuple[dict[str, Any], str]:
    goals = registry.get("goals")
    if not isinstance(goals, list):
        goals = []
    merged: list[Any] = []
    action = "appended"
    replaced = False
    for item in goals:
        if isinstance(item, dict) and item.get("id") == goal_entry["id"]:
            if force:
                merged.append(goal_entry)
                action = "replaced"
            else:
                merged.append(item)
                action = "kept-existing"
            replaced = True
        else:
            merged.append(item)
    if not replaced:
        merged.append(goal_entry)
    registry["goals"] = merged
    return registry, action


def bootstrap_project(
    *,
    project: Path,
    registry_path: Path,
    runtime_root: Path | None,
    goal_id: str | None,
    objective: str,
    domain: str,
    role: str,
    parent_goal_id: str | None,
    state_file: Path | None,
    goal_doc: Path | None,
    adapter_kind: str,
    adapter_status: str,
    next_probe: str | None,
    spawn_allowed: bool,
    max_children: int,
    allowed_domains: list[str] | None,
    write_scope: list[str] | None,
    claim_ttl_minutes: int,
    execution_minimum_scale: str | None = None,
    execution_must_include: list[str] | None = None,
    execution_small_streak_threshold: int | None = None,
    execution_outcome_markers: list[str] | None = None,
    execution_surface_only_hints: list[str] | None = None,
    execution_surface_streak_threshold: int | None = None,
    execution_outcome_must_advance: list[str] | None = None,
    force: bool,
    dry_run: bool,
    sync_global: bool,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    registry_path = registry_path.expanduser()
    if not registry_path.is_absolute():
        registry_path = project / registry_path
    goal_id = goal_id or default_goal_id(project)
    state_file = state_file or (project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md")
    state_file = state_file.expanduser()
    if not state_file.is_absolute():
        state_file = project / state_file
    goal_doc = resolve_project_path(project, goal_doc)
    runtime_root = runtime_root.expanduser() if runtime_root else DEFAULT_RUNTIME_ROOT
    updated_at = now_iso()
    execution_profile = build_execution_profile(
        minimum_scale=execution_minimum_scale,
        must_include=execution_must_include,
        small_scale_streak_threshold=execution_small_streak_threshold,
        outcome_markers=execution_outcome_markers,
        surface_only_hints=execution_surface_only_hints,
        surface_streak_threshold=execution_surface_streak_threshold,
        outcome_must_advance=execution_outcome_must_advance,
    )

    registry = read_json_if_exists(registry_path)
    registry.setdefault("schema_version", "0.1")
    registry["updated_at"] = updated_at.split("T")[0]
    registry.setdefault("common_runtime_root", str(runtime_root))
    if runtime_root:
        registry["common_runtime_root"] = str(runtime_root)

    goal_entry = build_goal_entry(
        project=project,
        goal_id=goal_id,
        domain=domain,
        role=role,
        parent_goal_id=parent_goal_id,
        state_file=state_file,
        goal_doc=goal_doc,
        adapter_kind=adapter_kind,
        adapter_status=adapter_status,
        next_probe=next_probe,
        spawn_allowed=spawn_allowed,
        max_children=max_children,
        allowed_domains=allowed_domains or [],
        write_scope=write_scope or [],
        claim_ttl_minutes=claim_ttl_minutes,
        execution_profile=execution_profile,
    )
    registry, registry_goal_action = merge_goal(registry, goal_entry, force=force)

    state_action = "created"
    if state_file.exists() and not force:
        state_action = "kept-existing"
    elif state_file.exists() and force:
        state_action = "replaced"

    dry_state_actions = {
        "created": "would-create",
        "kept-existing": "would-keep-existing",
        "replaced": "would-replace",
    }
    actions = [
        {"path": str(registry_path), "action": "would-write" if dry_run else "wrote", "goal": registry_goal_action},
        {"path": str(state_file), "action": dry_state_actions.get(state_action, "would-write") if dry_run else state_action},
    ]
    if sync_global:
        actions.append(
            {
                "path": str(runtime_root / "registry.global.json"),
                "action": "would-sync" if dry_run else "synced",
                "goal": goal_id,
            }
        )

    global_sync: dict[str, Any] | None = None
    if not dry_run:
        write_json(registry_path, registry)
        if state_action in {"created", "replaced"}:
            state_file.parent.mkdir(parents=True, exist_ok=True)
            state_file.write_text(
                render_state_markdown(
                    project=project,
                    goal_id=goal_id,
                    objective=objective,
                    updated_at=updated_at,
                    goal_doc=goal_doc,
                    execution_profile=execution_profile,
                ),
                encoding="utf-8",
            )
        if sync_global:
            global_sync = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=str(runtime_root),
                goal_id=goal_id,
                dry_run=False,
            )

    return {
        "ok": True,
        "dry_run": dry_run,
        "project": str(project),
        "goal_id": goal_id,
        "registry": str(registry_path),
        "state_file": str(state_file),
        "goal_doc": str(goal_doc) if goal_doc else None,
        "goal_doc_exists": bool(goal_doc and goal_doc.exists()),
        "runtime_root": str(runtime_root),
        "registry_goal_action": registry_goal_action,
        "state_action": state_action,
        "execution_profile": execution_profile,
        "global_sync": global_sync
        or {
            "enabled": sync_global,
            "dry_run": dry_run,
            "global_registry": str(runtime_root / "registry.global.json"),
            "synced_goal_ids": [goal_id] if sync_global else [],
            "wrote": False,
        },
        "actions": actions,
        "next_commands": [
            f"goal-harness --registry {relative_state_file(project, registry_path)} registry",
            f"goal-harness --registry {relative_state_file(project, registry_path)} check --scan-root {project}",
            f"goal-harness --registry {runtime_root / 'registry.global.json'} status",
            f"goal-harness --registry {relative_state_file(project, registry_path)} history --goal-id {goal_id}",
        ],
        "private_boundary_note": "Add .goal-harness/ and .codex/goals/ to the project .gitignore if the goal state contains private evidence.",
    }


def render_bootstrap_markdown(payload: dict[str, Any]) -> str:
    execution_profile = (
        payload.get("execution_profile")
        if isinstance(payload.get("execution_profile"), dict)
        else None
    )
    execution_profile_text = execution_profile_summary(execution_profile)
    lines = [
        "# Goal Harness Bootstrap",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- project: `{payload.get('project')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- registry: `{payload.get('registry')}`",
        f"- state_file: `{payload.get('state_file')}`",
        f"- goal_doc: `{payload.get('goal_doc')}`",
        f"- goal_doc_exists: `{payload.get('goal_doc_exists')}`",
        f"- runtime_root: `{payload.get('runtime_root')}`",
        f"- registry_goal_action: `{payload.get('registry_goal_action')}`",
        f"- state_action: `{payload.get('state_action')}`",
        f"- execution_profile: `{execution_profile_text}`",
        f"- global_sync: `{(payload.get('global_sync') or {}).get('wrote')}`",
        "",
        "## Actions",
    ]
    for action in payload.get("actions") or []:
        lines.append(f"- `{action.get('path')}`: {action.get('action')} ({action.get('goal', '')})")

    lines.extend(["", "## Next Commands"])
    for command in payload.get("next_commands") or []:
        lines.append(f"- `{command}`")

    if payload.get("private_boundary_note"):
        lines.extend(["", "## Boundary Note", str(payload.get("private_boundary_note"))])
    return "\n".join(lines)
