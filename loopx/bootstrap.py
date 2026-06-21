from __future__ import annotations

import json
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .execution_profile import (
    build_execution_profile,
    compact_execution_profile,
    execution_profile_summary,
)
from .global_registry import sync_project_registry_to_global
from .onboarding import build_onboarding_scan
from .orchestration import (
    DEFAULT_ORCHESTRATION_MODE,
    MULTI_SUBAGENT_ORCHESTRATION_MODE,
)
from .paths import DEFAULT_RUNTIME_ROOT, rel_or_abs
from .todos import add_todo_to_lines


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


def onboarding_candidates(onboarding_scan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(onboarding_scan, dict):
        return []
    candidates = onboarding_scan.get("agent_todo_candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def render_onboarding_state_markdown(
    *,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
) -> str:
    if not onboarding_scan:
        return ""
    scan_policy = onboarding_scan.get("scan_policy")
    scan_policy = scan_policy if isinstance(scan_policy, dict) else {}
    recent_commits = onboarding_scan.get("recent_commits")
    recent_commits = recent_commits if isinstance(recent_commits, list) else []
    signal_files = onboarding_scan.get("signal_files")
    signal_files = signal_files if isinstance(signal_files, list) else []
    validation_files = onboarding_scan.get("validation_signal_files")
    validation_files = validation_files if isinstance(validation_files, list) else []
    validation_paths = [
        str(item.get("path"))
        for item in validation_files
        if isinstance(item, dict) and item.get("path")
    ]
    acceptance_status = (
        "accepted and written into Agent Todo"
        if accept_onboarding_agent_todos
        else "requires user selection before delivery work"
    )
    autonomous_status = (
        "allowed after accepted agent todos and a fresh quota guard"
        if begin_autonomous_advance
        else "requires an explicit user yes/no choice"
    )
    lines = [
        "## Onboarding Control",
        "",
        "- Fast repository scan: `enabled`.",
        f"- Scan read file bodies: `{bool(scan_policy.get('raw_file_bodies_read'))}`.",
        f"- Git repo detected: `{bool(onboarding_scan.get('is_git_repo'))}`.",
        f"- Local change count from `git status --short`: `{int(onboarding_scan.get('status_path_count') or 0)}`.",
        f"- Recent commits sampled: `{len(recent_commits)}`.",
        f"- Project signal files: `{', '.join(str(item) for item in signal_files) or 'none'}`.",
        f"- Validation signal files: `{', '.join(validation_paths) or 'none'}`.",
        f"- Candidate agent todos: `{acceptance_status}`.",
        f"- Autonomous advancement: `{autonomous_status}`.",
        "",
        "## Proposed Onboarding Candidates",
        "",
    ]
    candidates = onboarding_candidates(onboarding_scan)
    for index, candidate in enumerate(candidates, start=1):
        text = str(candidate.get("text") or "").strip()
        reason = str(candidate.get("reason") or "").strip()
        action_kind = str(candidate.get("action_kind") or "analyze").strip()
        task_class = str(candidate.get("task_class") or "advancement_task").strip()
        lines.append(f"{index}. {text}")
        if reason:
            lines.append(f"   - reason: {reason}")
        lines.append(f"   - metadata: `{task_class}:{action_kind}`")
    if not candidates:
        lines.append("No candidate agent todos were generated.")
    return "\n".join(lines)


def onboarding_user_todo_text(
    *,
    acceptance_required: bool,
    autonomous_choice_required: bool,
) -> str | None:
    if acceptance_required and autonomous_choice_required:
        return (
            "[P1] Choose which proposed onboarding agent todos to accept and whether Codex may "
            "start autonomous advancement; reply with accepted numbers plus autonomous=yes/no."
        )
    if acceptance_required:
        return (
            "[P1] Choose which proposed onboarding agent todos to accept; autonomous advancement "
            "is already allowed after accepted todos are written and quota permits."
        )
    if autonomous_choice_required:
        return (
            "[P1] Decide whether Codex may start autonomous advancement now that onboarding "
            "agent todos were accepted; reply autonomous=yes/no."
        )
    return None


def onboarding_agent_review_todo_text(
    *,
    acceptance_required: bool,
    autonomous_choice_required: bool,
) -> str | None:
    if not acceptance_required and not autonomous_choice_required:
        return None
    if acceptance_required and autonomous_choice_required:
        return (
            "[P1] Present the onboarding scan, ask which candidate agent todos to accept, "
            "and ask whether autonomous advancement may start before delivery work."
        )
    if acceptance_required:
        return (
            "[P1] Present the onboarding scan and ask which candidate agent todos to accept "
            "before starting the pre-authorized autonomous advancement path."
        )
    return (
        "[P1] Ask whether autonomous advancement may start from the accepted onboarding "
        "agent todos before delivery work."
    )


def onboarding_next_action(
    *,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
) -> str:
    if not onboarding_scan:
        return "Run `loopx check` against the project registry and decide the first project-specific adapter signal."
    if not accept_onboarding_agent_todos:
        if begin_autonomous_advance:
            return (
                "Ask the user which proposed onboarding agent todos to accept; once accepted, run the quota guard "
                "and begin the first accepted todo because autonomous advancement was pre-authorized."
            )
        return (
            "Show the proposed onboarding agent todos, ask which to accept, ask whether Codex may start autonomous "
            "advancement, then write accepted todos and refresh state before any delivery work."
        )
    if not begin_autonomous_advance:
        return (
            "Ask whether Codex may start autonomous advancement; if yes, run the quota guard and execute the first "
            "accepted onboarding agent todo, otherwise stop after refresh-state."
        )
    return (
        "Run the quota guard, execute the first accepted onboarding Agent Todo as a bounded segment, write evidence, "
        "complete or update the todo, and refresh state."
    )


def apply_onboarding_todos_to_state(
    text: str,
    *,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
) -> str:
    if not onboarding_scan:
        return text
    lines = text.splitlines()
    if accept_onboarding_agent_todos:
        for candidate in onboarding_candidates(onboarding_scan):
            todo_text = str(candidate.get("text") or "").strip()
            if not todo_text:
                continue
            add_todo_to_lines(
                lines,
                role="agent",
                text=todo_text,
                task_class=str(candidate.get("task_class") or "advancement_task"),
                action_kind=str(candidate.get("action_kind") or "analyze"),
            )

    acceptance_required = not accept_onboarding_agent_todos
    autonomous_choice_required = not begin_autonomous_advance
    user_todo = onboarding_user_todo_text(
        acceptance_required=acceptance_required,
        autonomous_choice_required=autonomous_choice_required,
    )
    if user_todo:
        add_todo_to_lines(
            lines,
            role="user",
            text=user_todo,
            task_class="user_gate",
            action_kind="onboarding_decision",
        )
    agent_todo = onboarding_agent_review_todo_text(
        acceptance_required=acceptance_required,
        autonomous_choice_required=autonomous_choice_required,
    )
    if agent_todo:
        add_todo_to_lines(
            lines,
            role="agent",
            text=agent_todo,
            task_class="advancement_task",
            action_kind="onboarding_todo_review",
        )
    return "\n".join(lines) + "\n"


def render_state_markdown(
    *,
    project: Path,
    goal_id: str,
    objective: str,
    updated_at: str,
    goal_doc: Path | None,
    execution_profile: dict[str, Any] | None,
    onboarding_scan: dict[str, Any] | None = None,
    accept_onboarding_agent_todos: bool = False,
    begin_autonomous_advance: bool = False,
) -> str:
    safe_objective = objective.replace('"', '\\"')
    profile_summary = execution_profile_summary(execution_profile)
    onboarding_markdown = render_onboarding_state_markdown(
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
    )
    onboarding_block = f"\n{onboarding_markdown}\n" if onboarding_markdown else ""
    next_action = onboarding_next_action(
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
    )
    state_text = f"""---
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
{onboarding_block}

## Next Action

- {next_action}

## Recent User Feedback

- Initialized by `loopx bootstrap`.

## Progress Ledger

- Created the initial goal state and registry connection.
"""
    return apply_onboarding_todos_to_state(
        state_text,
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
    )


def relative_state_file(project: Path, state_file: Path) -> str:
    return rel_or_abs(state_file, project)


def todo_add_command(
    *,
    project: Path,
    registry_path: Path,
    goal_id: str,
    candidate: dict[str, Any],
) -> str:
    return (
        f"loopx --registry {shlex.quote(relative_state_file(project, registry_path))} todo add "
        f"--goal-id {shlex.quote(goal_id)} "
        "--role agent "
        f"--text {shlex.quote(str(candidate.get('text') or ''))} "
        f"--task-class {shlex.quote(str(candidate.get('task_class') or 'advancement_task'))} "
        f"--action-kind {shlex.quote(str(candidate.get('action_kind') or 'analyze'))}"
    )


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
        or f"loopx --registry .loopx/registry.json check --scan-root {project}",
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
    onboarding_scan_enabled: bool = True,
    accept_onboarding_agent_todos: bool = False,
    begin_autonomous_advance: bool = False,
    onboarding_max_commits: int = 5,
    onboarding_max_status_paths: int = 12,
    onboarding_max_top_level_files: int = 24,
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
    onboarding_scan = (
        build_onboarding_scan(
            project,
            max_commits=onboarding_max_commits,
            max_status_paths=onboarding_max_status_paths,
            max_top_level_files=onboarding_max_top_level_files,
        )
        if onboarding_scan_enabled
        else None
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
                    onboarding_scan=onboarding_scan,
                    accept_onboarding_agent_todos=accept_onboarding_agent_todos,
                    begin_autonomous_advance=begin_autonomous_advance,
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

    candidates = onboarding_candidates(onboarding_scan)
    accept_candidate_commands = [
        todo_add_command(
            project=project,
            registry_path=registry_path,
            goal_id=goal_id,
            candidate=candidate,
        )
        for candidate in candidates
    ]
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
        "onboarding_scan": onboarding_scan,
        "onboarding_agent_todo_candidates": candidates,
        "accept_onboarding_agent_todos": accept_onboarding_agent_todos,
        "begin_autonomous_advance": begin_autonomous_advance,
        "onboarding_acceptance_required": bool(onboarding_scan and not accept_onboarding_agent_todos),
        "autonomous_advance_choice_required": bool(onboarding_scan and not begin_autonomous_advance),
        "onboarding_todos_written": bool(
            onboarding_scan and state_action in {"created", "replaced"} and not dry_run
        ),
        "accept_candidate_commands": accept_candidate_commands,
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
            f"loopx --registry {relative_state_file(project, registry_path)} registry",
            f"loopx --registry {relative_state_file(project, registry_path)} status",
            f"loopx --registry {relative_state_file(project, registry_path)} check --scan-root {project}",
            f"loopx --format json --registry {runtime_root / 'registry.global.json'} quota should-run --goal-id {goal_id}",
            f"loopx --registry {relative_state_file(project, registry_path)} refresh-state --goal-id {goal_id}",
            f"loopx --registry {runtime_root / 'registry.global.json'} status",
            f"loopx --registry {relative_state_file(project, registry_path)} history --goal-id {goal_id}",
        ],
        "private_boundary_note": "Add .loopx/ and .codex/goals/ to the project .gitignore if the goal state contains private evidence.",
    }


def render_bootstrap_markdown(payload: dict[str, Any]) -> str:
    execution_profile = (
        payload.get("execution_profile")
        if isinstance(payload.get("execution_profile"), dict)
        else None
    )
    execution_profile_text = execution_profile_summary(execution_profile)
    lines = [
        "# LoopX Bootstrap",
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
        f"- onboarding_acceptance_required: `{payload.get('onboarding_acceptance_required')}`",
        f"- autonomous_advance_choice_required: `{payload.get('autonomous_advance_choice_required')}`",
        f"- onboarding_todos_written: `{payload.get('onboarding_todos_written')}`",
        f"- global_sync: `{(payload.get('global_sync') or {}).get('wrote')}`",
        "",
        "## Actions",
    ]
    for action in payload.get("actions") or []:
        lines.append(f"- `{action.get('path')}`: {action.get('action')} ({action.get('goal', '')})")

    onboarding_scan = payload.get("onboarding_scan")
    if isinstance(onboarding_scan, dict):
        recent_commits = onboarding_scan.get("recent_commits")
        recent_commits = recent_commits if isinstance(recent_commits, list) else []
        signal_files = onboarding_scan.get("signal_files")
        signal_files = signal_files if isinstance(signal_files, list) else []
        status_sample = onboarding_scan.get("status_paths_sample")
        status_sample = status_sample if isinstance(status_sample, list) else []
        lines.extend(
            [
                "",
                "## Onboarding Scan",
                f"- schema: `{onboarding_scan.get('schema_version')}`",
                f"- git_repo: `{onboarding_scan.get('is_git_repo')}`",
                f"- status_path_count: `{onboarding_scan.get('status_path_count')}`",
                f"- recent_commits: `{len(recent_commits)}`",
                f"- signal_files: `{', '.join(str(item) for item in signal_files) or 'none'}`",
                "- raw_file_bodies_read: `False`",
            ]
        )
        if status_sample:
            lines.append("- status_sample:")
            for item in status_sample[:5]:
                lines.append(f"  - `{item}`")
        if recent_commits:
            lines.append("- recent_commit_sample:")
            for commit in recent_commits[:5]:
                if isinstance(commit, dict):
                    lines.append(f"  - `{commit.get('hash')}` {commit.get('subject')}")

    candidates = payload.get("onboarding_agent_todo_candidates")
    candidates = candidates if isinstance(candidates, list) else []
    if candidates:
        lines.extend(["", "## Proposed Onboarding Candidates"])
        for index, candidate in enumerate(candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            lines.append(f"{index}. {candidate.get('text')}")
            if candidate.get("reason"):
                lines.append(f"   - reason: {candidate.get('reason')}")
            lines.append(
                "   - metadata: "
                f"`{candidate.get('task_class') or 'advancement_task'}:{candidate.get('action_kind') or 'analyze'}`"
            )

    accept_commands = payload.get("accept_candidate_commands")
    accept_commands = accept_commands if isinstance(accept_commands, list) else []
    if accept_commands:
        lines.extend(
            [
                "",
                "## Accept Candidate Commands",
                "Run only the commands for candidates the user accepts, then refresh state.",
            ]
        )
        for command in accept_commands:
            lines.append(f"- `{command}`")

    if onboarding_scan:
        lines.extend(
            [
                "",
                "## Autonomy Choice",
                (
                    "- Ask the user whether Codex may start autonomous advancement. If yes, run the quota guard "
                    "and execute the first accepted Agent Todo; if no, stop after writing accepted todos and refresh-state."
                ),
            ]
        )

    lines.extend(["", "## Next Commands"])
    for command in payload.get("next_commands") or []:
        lines.append(f"- `{command}`")

    if payload.get("private_boundary_note"):
        lines.extend(["", "## Boundary Note", str(payload.get("private_boundary_note"))])
    return "\n".join(lines)
