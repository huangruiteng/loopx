from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

from .file_lock import exclusive_cross_runtime_file_lock
from .registry import atomic_write_json, find_registry_goal
from .control_plane.coordination.legacy_writer_fence import legacy_todo_write_transaction, require_legacy_state_replacement_allowed
from .control_plane.coordination.runtime_shadow_writer_adapter import require_runtime_shadow_capture_prepared, begin_todo_runtime_shadow_capture, settle_todo_runtime_shadow_capture
from typing import Any

from .control_plane.runtime.time import now_local_iso
from .control_plane.runtime.public_safety import public_safe_compact_text
from .control_plane.todos.active_state_editing import (
    TODO_SECTION_HEADINGS,
    atomic_write_state_text,
    insertion_anchor,
    section_bounds,
)
from .control_plane.todos.next_action_runtime import bind_next_action_to_todo
from .control_plane.todos.handoff_mode import (
    HANDOFF_MODE_LEGACY,
    goal_handoff_mode,
)
from .execution_profile import (
    build_execution_profile,
    compact_execution_profile,
    execution_profile_summary,
)
from .global_registry import sync_project_registry_to_global
from .install_contract import (
    ARCHIVE_FALLBACK_INSTALL_COMMAND,
    DEFAULT_INSTALL_REPAIR_COMMAND,
)
from .onboarding import build_onboarding_scan
from .orchestration import (
    DEFAULT_ORCHESTRATION_MODE,
    MULTI_SUBAGENT_ORCHESTRATION_MODE,
)
from .paths import rel_or_abs, resolve_runtime_root
from .registry_writability import probe_registry_write_path
from .todos import add_todo_to_lines


DEFAULT_OBJECTIVE = "Improve this project through bounded, verified goal segments."
DEFAULT_DOMAIN = "project-goal-control-plane"
GENERIC_ONBOARDING_ADAPTER_KINDS = frozenset(
    {"generic_project_goal_v0", "read_only_project_map_v0"}
)
HEARTBEAT_OPT_IN_STATUS_REQUIRED = (
    "requires explicit heartbeat=yes/no before a recurring Codex App automation is installed"
)
HEARTBEAT_OPT_IN_STATUS_PREAUTHORIZED = (
    "explicitly preauthorized; create or update the host loop before claiming recurring automation is active"
)
HEARTBEAT_OPT_IN_STATUS_DECLINED = (
    "explicitly declined; keep the goal manual or on-demand unless the user later opts in"
)
HEARTBEAT_OPT_IN_INSTRUCTION = (
    "Ask the user whether to enable the Codex App heartbeat. heartbeat=yes means create or update a recurring "
    "Codex App automation from an identity-scoped `loopx heartbeat-prompt --thin` task body; heartbeat=no means "
    "keep the goal manual or on-demand."
)
HEARTBEAT_OPT_IN_PREAUTHORIZED_INSTRUCTION = (
    "The user preauthorized the Codex App heartbeat. Create or update the recurring automation from an "
    "identity-scoped `loopx heartbeat-prompt --thin` task body before claiming recurring automation is active."
)
HEARTBEAT_OPT_IN_DECLINED_INSTRUCTION = (
    "The user declined the Codex App heartbeat. Do not install recurring automation; keep the goal manual or "
    "on-demand unless the user later opts in."
)
CODEX_APP_HEARTBEAT_CHOICES = {"ask", "yes", "no"}
ONBOARDING_CONNECTION_VALIDATION_AGENT = "agent"
ONBOARDING_CONNECTION_VALIDATION_PROVIDER_PREVALIDATED = "provider-prevalidated"
ONBOARDING_CONNECTION_VALIDATION_CHOICES = {
    ONBOARDING_CONNECTION_VALIDATION_AGENT,
    ONBOARDING_CONNECTION_VALIDATION_PROVIDER_PREVALIDATED,
}


def slugify_goal_id(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "project-goal"


def default_goal_id(project: Path) -> str:
    return f"{slugify_goal_id(project.name)}-goal"


def derive_goal_display_name(goal_text: str | None) -> str | None:
    """Derive a public-safe display title from user-supplied goal text."""

    return public_safe_compact_text(goal_text, limit=132)


def now_iso() -> str:
    return now_local_iso()


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


def repair_missing_todo_source_sections(state_text: str) -> tuple[str, list[str]]:
    """Add missing durable todo sources without replacing existing state content."""

    lines = state_text.splitlines()
    added_roles: list[str] = []
    for role in ("user", "agent"):
        if section_bounds(lines, role) is not None:
            continue
        anchor = insertion_anchor(lines, role)
        section = [f"## {TODO_SECTION_HEADINGS[role]}", ""]
        if anchor > 0 and lines[anchor - 1].strip():
            section.insert(0, "")
        lines[anchor:anchor] = section
        added_roles.append(role)
    if not added_roles:
        return state_text, []
    trailing_newline = "\n" if state_text.endswith("\n") else ""
    return "\n".join(lines) + trailing_newline, added_roles


def onboarding_candidates(onboarding_scan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(onboarding_scan, dict):
        return []
    candidates = onboarding_scan.get("agent_todo_candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def normalize_codex_app_heartbeat(value: str | None) -> str:
    choice = (value or "ask").strip().lower()
    if choice not in CODEX_APP_HEARTBEAT_CHOICES:
        raise ValueError("codex_app_heartbeat must be one of: ask, yes, no")
    return choice


def normalize_onboarding_connection_validation(value: str | None) -> str:
    choice = (value or ONBOARDING_CONNECTION_VALIDATION_AGENT).strip().lower()
    if choice not in ONBOARDING_CONNECTION_VALIDATION_CHOICES:
        raise ValueError(
            "onboarding_connection_validation must be one of: "
            "agent, provider-prevalidated"
        )
    return choice


def heartbeat_opt_in_required(
    *,
    onboarding_scan: dict[str, Any] | None,
    codex_app_heartbeat: str,
) -> bool:
    return bool(onboarding_scan and codex_app_heartbeat == "ask")


def host_loop_activation_required(
    *,
    onboarding_scan: dict[str, Any] | None,
    codex_app_heartbeat: str,
) -> bool:
    return bool(onboarding_scan and codex_app_heartbeat in {"ask", "yes"})


def heartbeat_status(codex_app_heartbeat: str) -> str:
    if codex_app_heartbeat == "yes":
        return HEARTBEAT_OPT_IN_STATUS_PREAUTHORIZED
    if codex_app_heartbeat == "no":
        return HEARTBEAT_OPT_IN_STATUS_DECLINED
    return HEARTBEAT_OPT_IN_STATUS_REQUIRED


def heartbeat_instruction(codex_app_heartbeat: str) -> str | None:
    if codex_app_heartbeat == "yes":
        return HEARTBEAT_OPT_IN_PREAUTHORIZED_INSTRUCTION
    if codex_app_heartbeat == "no":
        return HEARTBEAT_OPT_IN_DECLINED_INSTRUCTION
    return HEARTBEAT_OPT_IN_INSTRUCTION


def render_onboarding_state_markdown(
    *,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
    codex_app_heartbeat: str,
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
        f"- Codex App heartbeat: `{heartbeat_status(codex_app_heartbeat)}`.",
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
    heartbeat_choice_required: bool,
) -> str | None:
    decisions: list[str] = []
    reply_parts: list[str] = []
    if acceptance_required:
        decisions.append("which proposed onboarding agent todos to accept")
        reply_parts.append("accepted numbers")
    if autonomous_choice_required:
        decisions.append("whether Codex may start autonomous advancement")
        reply_parts.append("autonomous=yes/no")
    if heartbeat_choice_required:
        decisions.append("whether to enable the Codex App heartbeat")
        reply_parts.append("heartbeat=yes/no")
    if not decisions:
        return None
    verb = "Choose" if acceptance_required else "Decide"
    return f"[P1] {verb} {' and '.join(decisions)}; reply with {' plus '.join(reply_parts)}."


def onboarding_agent_review_todo_text(
    *,
    acceptance_required: bool,
    autonomous_choice_required: bool,
    heartbeat_choice_required: bool,
) -> str | None:
    if not acceptance_required and not autonomous_choice_required and not heartbeat_choice_required:
        return None
    prompts: list[str] = []
    if acceptance_required:
        prompts.append("which candidate agent todos to accept")
    if autonomous_choice_required:
        prompts.append("whether autonomous advancement may start")
    if heartbeat_choice_required:
        prompts.append("whether to enable the Codex App heartbeat")
    prefix = "Present the onboarding scan and ask " if acceptance_required else "Ask "
    text = f"[P1] {prefix}{', '.join(prompts)} before delivery work."
    if heartbeat_choice_required:
        text += (
            " If heartbeat=yes, create or update the Codex App heartbeat from an identity-scoped "
            "`loopx heartbeat-prompt --thin` task body before claiming recurring automation is active."
        )
    return text


def onboarding_connection_validation_action(adapter_kind: str) -> dict[str, str] | None:
    if adapter_kind not in GENERIC_ONBOARDING_ADAPTER_KINDS:
        return None
    return {
        "text": (
            "[P1] Run `loopx check` against the project registry and record the first "
            "project-specific adapter signal or an explicit no-follow-up rationale."
        ),
        "task_class": "advancement_task",
        "action_kind": "onboarding_connection_validation",
    }


def onboarding_next_action(
    *,
    adapter_kind: str,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
    codex_app_heartbeat: str,
    include_connection_validation: bool = True,
) -> str:
    if not onboarding_scan:
        validation_action = (
            onboarding_connection_validation_action(adapter_kind)
            if include_connection_validation
            else None
        )
        if validation_action:
            return validation_action["text"]
        return "Initial routing is owned by the connected domain adapter."
    need_heartbeat_choice = codex_app_heartbeat == "ask"
    if not accept_onboarding_agent_todos or not begin_autonomous_advance or need_heartbeat_choice:
        asks: list[str] = []
        if not accept_onboarding_agent_todos:
            asks.append("which proposed onboarding agent todos to accept")
        if not begin_autonomous_advance:
            asks.append("whether Codex may start autonomous advancement")
        if need_heartbeat_choice:
            asks.append("whether to enable the Codex App heartbeat")
        follow_up = "then write accepted choices and refresh state before delivery work."
        heartbeat_follow_up = ""
        if need_heartbeat_choice:
            heartbeat_follow_up = (
                " If heartbeat=yes, create or update the recurring automation from an identity-scoped "
                "`loopx heartbeat-prompt --thin` task body."
            )
        elif codex_app_heartbeat == "yes":
            heartbeat_follow_up = (
                " Create or update the preauthorized recurring automation from an identity-scoped "
                "`loopx heartbeat-prompt --thin` task body."
            )
        autonomous_follow_up = (
            " If autonomous=yes, run the quota guard and execute the first accepted onboarding agent todo."
            if not begin_autonomous_advance
            else " Run the quota guard and execute the first accepted onboarding agent todo once accepted choices permit."
        )
        return f"Ask the user {', '.join(asks)}, {follow_up}{heartbeat_follow_up}{autonomous_follow_up}"
    if codex_app_heartbeat == "yes":
        return (
            "Create or update the Codex App heartbeat from an identity-scoped `loopx heartbeat-prompt --thin` task "
            "body, run the quota guard, execute the first accepted onboarding Agent Todo as a bounded segment, write "
            "evidence, complete or update the todo, and refresh state."
        )
    return (
        "Run the quota guard, execute the first accepted onboarding Agent Todo as a bounded segment, write evidence, "
        "complete or update the todo, and refresh state."
    )


def apply_onboarding_todos_to_state(
    text: str,
    *,
    adapter_kind: str,
    updated_at: str,
    onboarding_scan: dict[str, Any] | None,
    accept_onboarding_agent_todos: bool,
    begin_autonomous_advance: bool,
    codex_app_heartbeat: str,
    include_connection_validation: bool = True,
) -> str:
    if not onboarding_scan:
        lines = text.splitlines()
        action = (
            onboarding_connection_validation_action(adapter_kind)
            if include_connection_validation
            else None
        )
        if action:
            added = add_todo_to_lines(
                lines,
                role="agent",
                text=action["text"],
                task_class=action["task_class"],
                action_kind=action["action_kind"],
                updated_at=updated_at,
            )
            bind_next_action_to_todo(lines, todo_id=str(added["todo_id"]))
        return "\n".join(lines) + "\n"
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
                updated_at=updated_at,
            )

    acceptance_required = not accept_onboarding_agent_todos
    autonomous_choice_required = not begin_autonomous_advance
    heartbeat_choice_required = codex_app_heartbeat == "ask"
    user_todo = onboarding_user_todo_text(
        acceptance_required=acceptance_required,
        autonomous_choice_required=autonomous_choice_required,
        heartbeat_choice_required=heartbeat_choice_required,
    )
    if user_todo:
        add_todo_to_lines(
            lines,
            role="user",
            text=user_todo,
            task_class="user_gate",
            action_kind="onboarding_decision",
            updated_at=updated_at,
        )
    agent_todo = onboarding_agent_review_todo_text(
        acceptance_required=acceptance_required,
        autonomous_choice_required=autonomous_choice_required,
        heartbeat_choice_required=heartbeat_choice_required,
    )
    if agent_todo:
        add_todo_to_lines(
            lines,
            role="agent",
            text=agent_todo,
            task_class="advancement_task",
            action_kind="onboarding_todo_review",
            updated_at=updated_at,
        )
    return "\n".join(lines) + "\n"


def render_objective_markdown(objective: str) -> str:
    """Render objective prose as an isolated Markdown blockquote.

    Generated state grammar owns fences, comments, and headings. Raw
    objective text is quoted line by line so a start-goal-collapsed or
    unclosed fence, comment, or heading example inside the objective can
    never open machine grammar and hide the generated Todo sections below.
    The frontmatter ``objective`` field keeps the raw text; readers of the
    body section strip the quote prefix to recover it.
    """
    lines = str(objective or "").splitlines()
    if not lines:
        return ""
    return "\n".join(f"> {line}" if line.strip() else ">" for line in lines)


def render_state_markdown(
    *,
    project: Path,
    goal_id: str,
    adapter_kind: str,
    objective: str,
    updated_at: str,
    goal_doc: Path | None,
    execution_profile: dict[str, Any] | None,
    onboarding_scan: dict[str, Any] | None = None,
    accept_onboarding_agent_todos: bool = False,
    begin_autonomous_advance: bool = False,
    codex_app_heartbeat: str = "ask",
    include_connection_validation: bool = True,
    handoff_mode: str = HANDOFF_MODE_LEGACY,
) -> str:
    safe_objective = objective.replace('"', '\\"')
    profile_summary = execution_profile_summary(execution_profile)
    onboarding_markdown = render_onboarding_state_markdown(
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
        codex_app_heartbeat=codex_app_heartbeat,
    )
    onboarding_block = f"\n{onboarding_markdown}\n" if onboarding_markdown else ""
    next_action = onboarding_next_action(
        adapter_kind=adapter_kind,
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
        codex_app_heartbeat=codex_app_heartbeat,
        include_connection_validation=include_connection_validation,
    )
    # ``handoff_mode`` travels in the state front matter (RFC shared-goal
    # authority, Appendix B). Legacy is the absent default and is never
    # materialized, so an untouched goal keeps its byte-for-byte shape.
    handoff_mode_line = (
        f"handoff_mode: {handoff_mode}\n" if handoff_mode != HANDOFF_MODE_LEGACY else ""
    )
    state_text = f"""---
status: active
owner_mode: goal
objective: "{safe_objective}"
updated_at: {updated_at}
adapter_id: {goal_id}
{handoff_mode_line}---

# Active Goal State

## Objective

{render_objective_markdown(objective)}

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

## User Todo / Owner Review Reading Queue

## Agent Todo

## Next Action

- {next_action}

## Recent User Feedback

- Initialized by `loopx bootstrap`.

## Progress Ledger

- Created the initial goal state and registry connection.
"""
    return apply_onboarding_todos_to_state(
        state_text,
        adapter_kind=adapter_kind,
        updated_at=updated_at,
        onboarding_scan=onboarding_scan,
        accept_onboarding_agent_todos=accept_onboarding_agent_todos,
        begin_autonomous_advance=begin_autonomous_advance,
        codex_app_heartbeat=codex_app_heartbeat,
        include_connection_validation=include_connection_validation,
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
    onboarding_connection_validation: str,
    next_probe: str | None,
    spawn_allowed: bool,
    max_children: int,
    allowed_domains: list[str],
    write_scope: list[str],
    execution_profile: dict[str, Any] | None,
    display_name: str | None = None,
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
    adapter = {
        "kind": adapter_kind,
        "status": adapter_status,
    }
    if (
        onboarding_connection_validation
        == ONBOARDING_CONNECTION_VALIDATION_PROVIDER_PREVALIDATED
    ):
        adapter["connection_validation"] = {
            "owner": "provider",
            "status": "prevalidated",
            "agent_todo_required": False,
        }
    return {
        "id": goal_id,
        **({"display_name": display_name} if display_name else {}),
        "domain": domain,
        "status": "active",
        "role": role,
        "parent_goal_id": parent_goal_id,
        "repo": str(project),
        "state_file": relative_state_file(project, state_file),
        "authority_sources": authority_sources,
        "adapter": adapter,
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
    execution_minimum_scale: str | None = None,
    execution_must_include: list[str] | None = None,
    execution_small_streak_threshold: int | None = None,
    execution_outcome_markers: list[str] | None = None,
    execution_surface_only_hints: list[str] | None = None,
    execution_surface_streak_threshold: int | None = None,
    execution_outcome_must_advance: list[str] | None = None,
    execution_turn_granularity: str | None = None,
    onboarding_scan_enabled: bool = True,
    onboarding_connection_validation: str = ONBOARDING_CONNECTION_VALIDATION_AGENT,
    accept_onboarding_agent_todos: bool = False,
    begin_autonomous_advance: bool = False,
    codex_app_heartbeat: str = "ask",
    onboarding_max_commits: int = 5,
    onboarding_max_status_paths: int = 12,
    onboarding_max_top_level_files: int = 24,
    preserve_todos: bool = False,
    display_name: str | None = None,
    force: bool,
    dry_run: bool,
    sync_global: bool,
    allow_global_route_replacement: bool = False,
) -> dict[str, Any]:
    project = project.expanduser().resolve()
    codex_app_heartbeat = normalize_codex_app_heartbeat(codex_app_heartbeat)
    onboarding_connection_validation = normalize_onboarding_connection_validation(
        onboarding_connection_validation
    )
    include_connection_validation = (
        onboarding_connection_validation == ONBOARDING_CONNECTION_VALIDATION_AGENT
    )
    registry_path = registry_path.expanduser()
    if not registry_path.is_absolute():
        registry_path = project / registry_path
    goal_id = goal_id or default_goal_id(project)
    state_file = state_file or (project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md")
    state_file = state_file.expanduser()
    if not state_file.is_absolute():
        state_file = project / state_file
    goal_doc = resolve_project_path(project, goal_doc)
    runtime_root = resolve_runtime_root(read_json_if_exists(registry_path), str(runtime_root) if runtime_root else None, registry_path=registry_path)
    updated_at = now_iso()
    execution_profile = build_execution_profile(
        minimum_scale=execution_minimum_scale,
        must_include=execution_must_include,
        small_scale_streak_threshold=execution_small_streak_threshold,
        outcome_markers=execution_outcome_markers,
        surface_only_hints=execution_surface_only_hints,
        surface_streak_threshold=execution_surface_streak_threshold,
        outcome_must_advance=execution_outcome_must_advance,
        turn_granularity=execution_turn_granularity,
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
        onboarding_connection_validation=onboarding_connection_validation,
        next_probe=next_probe,
        spawn_allowed=spawn_allowed,
        max_children=max_children,
        allowed_domains=allowed_domains or [],
        write_scope=write_scope or [],
        execution_profile=execution_profile,
        display_name=display_name,
    )
    registry, registry_goal_action = merge_goal(registry, goal_entry, force=force)

    state_exists = state_file.exists()
    state_action = "created"
    if state_exists and force and preserve_todos:
        state_action = "kept-existing-preserve-todos"
    elif state_exists and not force:
        state_action = "kept-existing"
    elif state_exists and force:
        state_action = "replaced"

    repaired_state_text: str | None = None
    repaired_todo_source_roles: list[str] = []
    if state_exists and state_action in {
        "kept-existing",
        "kept-existing-preserve-todos",
    }:
        repaired_state_text, repaired_todo_source_roles = repair_missing_todo_source_sections(
            state_file.read_text(encoding="utf-8")
        )
    todo_source_migration = (
        {
            "schema_version": "todo_source_section_migration_v0",
            "added_roles": repaired_todo_source_roles,
            "applied": False,
        }
        if repaired_todo_source_roles
        else None
    )

    dry_state_actions = {
        "created": "would-create",
        "kept-existing": "would-keep-existing",
        "kept-existing-preserve-todos": "would-keep-existing-preserve-todos",
        "replaced": "would-replace",
    }
    force_bootstrap_warning = None
    declared_handoff_mode = HANDOFF_MODE_LEGACY
    if state_exists and force:
        # A forced rebuild replaces todos, never the goal's handoff contract:
        # the declared mode is carried into the rewritten front matter, and an
        # invalid declaration fails closed before anything is rewritten.
        declared_handoff_mode = goal_handoff_mode(state_file.read_text(encoding="utf-8"))
        force_bootstrap_warning = {
            "kind": "force_reconnect_existing_active_state",
            "state_file": str(state_file),
            "state_action": state_action,
            "will_replace_active_state": state_action == "replaced",
            "handoff_mode": declared_handoff_mode,
            "preserve_todos_requested": bool(preserve_todos),
            "recommended_scope_migration": (
                "Use configure-goal --write-scope ... --execute to change write scope "
                "without rebuilding the active state."
            ),
            "preserve_todos_option": "--preserve-todos",
        }
    actions = [
        {"path": str(registry_path), "action": "would-write" if dry_run else "wrote", "goal": registry_goal_action},
        {
            "path": str(state_file),
            "action": dry_state_actions.get(state_action, "would-write") if dry_run else state_action,
            **({"todo_source_migration": todo_source_migration} if todo_source_migration else {}),
        },
    ]
    if sync_global:
        actions.append(
            {
                "path": str(runtime_root / "registry.global.json"),
                "action": "would-sync" if dry_run else "synced",
                "goal": goal_id,
            }
        )

    candidates = onboarding_candidates(onboarding_scan)
    heartbeat_required = heartbeat_opt_in_required(
        onboarding_scan=onboarding_scan,
        codex_app_heartbeat=codex_app_heartbeat,
    )
    host_loop_required = host_loop_activation_required(
        onboarding_scan=onboarding_scan,
        codex_app_heartbeat=codex_app_heartbeat,
    )
    accept_candidate_commands = [
        todo_add_command(
            project=project,
            registry_path=registry_path,
            goal_id=goal_id,
            candidate=candidate,
        )
        for candidate in candidates
    ]

    global_sync: dict[str, Any] | None = None
    global_writability: dict[str, Any] | None = None
    if sync_global and not dry_run:
        global_writability = probe_registry_write_path(runtime_root / "registry.global.json", create_parent=True)
        if not global_writability.get("ok"):
            for action in actions:
                if action.get("path") == str(runtime_root / "registry.global.json"):
                    action["action"] = "blocked-write-denied"
            global_sync = {
                "ok": False,
                "enabled": True,
                "dry_run": dry_run,
                "global_registry": str(runtime_root / "registry.global.json"),
                "synced_goal_ids": [],
                "wrote": False,
                "write_denied": True,
                "error_kind": "global_registry_write_denied",
                "global_registry_writability": global_writability,
                "requires_global_registry_repair": True,
                "requires_host_permission": bool(global_writability.get("requires_host_permission")),
                "recommended_action": global_writability.get("recommended_action"),
            }
            return {
                "ok": False,
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
                "todo_source_migration": todo_source_migration,
                "force_bootstrap_warning": force_bootstrap_warning,
                "execution_profile": execution_profile,
                "onboarding_scan": onboarding_scan,
                "onboarding_agent_todo_candidates": candidates,
                "accept_onboarding_agent_todos": accept_onboarding_agent_todos,
                "begin_autonomous_advance": begin_autonomous_advance,
                "codex_app_heartbeat": codex_app_heartbeat,
                "onboarding_connection_validation": onboarding_connection_validation,
                "onboarding_acceptance_required": bool(onboarding_scan and not accept_onboarding_agent_todos),
                "autonomous_advance_choice_required": bool(onboarding_scan and not begin_autonomous_advance),
                "heartbeat_opt_in_required": heartbeat_required,
                "host_loop_activation_required": host_loop_required,
                "heartbeat_opt_in_instruction": (
                    heartbeat_instruction(codex_app_heartbeat) if onboarding_scan else None
                ),
                "onboarding_todos_written": False,
                "accept_candidate_commands": accept_candidate_commands,
                "global_sync": global_sync,
                "actions": actions,
                "next_commands": [
                    "Fix global registry write access, then rerun this command.",
                    "Use --no-global-sync only for an explicit local-only setup.",
                ],
                "install_repair_command": DEFAULT_INSTALL_REPAIR_COMMAND,
                "archive_fallback_install_command": ARCHIVE_FALLBACK_INSTALL_COMMAND,
                "install_repair_note": (
                    "If this local LoopX install is missing or stale, repair the PyPI distribution "
                    "and packaged workflow skills, then confirm with loopx doctor before continuing."
                ),
                "private_boundary_note": "Add .loopx/ and .codex/goals/ to the project .gitignore if the goal state contains private evidence.",
                "error": str(global_writability.get("error") or "global registry is not writable"),
            }
    shadow_capture = None
    shadow_evidence: dict[str, Any] = {}
    if not dry_run:
        with exclusive_cross_runtime_file_lock(registry_path, operation="bootstrap_registry"), legacy_todo_write_transaction(
            registry_path, goal_id, state_file, None, "bootstrap_state", False,
            runtime_root=runtime_root,
        ):
            current_registry = read_json_if_exists(registry_path)
            current_goal = find_registry_goal(current_registry, goal_id)
            previous_root = resolve_runtime_root(current_registry, None, registry_path=registry_path)
            if previous_root != runtime_root:
                for previous_goal in current_registry.get("goals", []):
                    if isinstance(previous_goal, dict) and previous_goal.get("id"):
                        require_legacy_state_replacement_allowed(runtime_root=previous_root,
                            goal_id=str(previous_goal["id"]), goal=previous_goal)
            original = state_file.read_text(encoding="utf-8") if state_file.exists() else ""
            if force or not state_file.exists():
                require_legacy_state_replacement_allowed(runtime_root=runtime_root,
                    goal_id=goal_id, goal=current_goal)
            state_action = ("kept-existing-preserve-todos" if force and preserve_todos else "kept-existing") if state_file.exists() and (not force or preserve_todos) else "replaced" if state_file.exists() else "created"
            planned = original
            if state_action in {"created", "replaced"}:
                declared_handoff_mode = goal_handoff_mode(original) if original and force else HANDOFF_MODE_LEGACY
                planned = render_state_markdown(
                    project=project,
                    goal_id=goal_id,
                    adapter_kind=adapter_kind,
                    objective=objective,
                    updated_at=updated_at,
                    goal_doc=goal_doc,
                    execution_profile=execution_profile,
                    onboarding_scan=onboarding_scan,
                    accept_onboarding_agent_todos=accept_onboarding_agent_todos,
                    begin_autonomous_advance=begin_autonomous_advance,
                    codex_app_heartbeat=codex_app_heartbeat,
                    include_connection_validation=include_connection_validation,
                    handoff_mode=declared_handoff_mode,
                )
            else:
                planned, repaired_todo_source_roles = repair_missing_todo_source_sections(original)
            if planned != original:
                shadow_capture = begin_todo_runtime_shadow_capture(registry_path=registry_path,
                    runtime_root=runtime_root, goal_id=goal_id, state_path=state_file,
                    write_class="bootstrap_state", original_text=original)
                shadow_capture.prepare(planned)
                require_runtime_shadow_capture_prepared(shadow_capture, runtime_root=runtime_root, goal_id=goal_id)
                atomic_write_state_text(state_file, planned)
                shadow_capture.committed()
                if todo_source_migration is not None:
                    todo_source_migration["applied"] = True
            current_registry.setdefault("schema_version", "0.1")
            current_registry["updated_at"] = updated_at.split("T")[0]
            current_registry["common_runtime_root"] = str(runtime_root)
            registry, registry_goal_action = merge_goal(current_registry, goal_entry, force=force)
            atomic_write_json(registry_path, registry)
        if shadow_capture is not None:
            shadow_evidence = settle_todo_runtime_shadow_capture({}, registry_path=registry_path,
                runtime_root=runtime_root, goal_id=goal_id, write_class="bootstrap_state",
                capture=shadow_capture, observe_legacy=False, emit_disabled=False)
        if sync_global:
            global_sync = sync_project_registry_to_global(
                registry_path=registry_path,
                runtime_root_override=str(runtime_root),
                goal_id=goal_id,
                dry_run=False,
                allow_route_replacement=allow_global_route_replacement,
            )

    return {
        **shadow_evidence,
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
        "todo_source_migration": todo_source_migration,
        "force_bootstrap_warning": force_bootstrap_warning,
        "execution_profile": execution_profile,
        "onboarding_scan": onboarding_scan,
        "onboarding_agent_todo_candidates": candidates,
        "accept_onboarding_agent_todos": accept_onboarding_agent_todos,
        "begin_autonomous_advance": begin_autonomous_advance,
        "codex_app_heartbeat": codex_app_heartbeat,
        "onboarding_connection_validation": onboarding_connection_validation,
        "onboarding_acceptance_required": bool(onboarding_scan and not accept_onboarding_agent_todos),
        "autonomous_advance_choice_required": bool(onboarding_scan and not begin_autonomous_advance),
        "heartbeat_opt_in_required": heartbeat_required,
        "host_loop_activation_required": host_loop_required,
        "heartbeat_opt_in_instruction": heartbeat_instruction(codex_app_heartbeat) if onboarding_scan else None,
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
            "route_replacement_allowed": allow_global_route_replacement,
        },
        "actions": actions,
        "next_commands": [
            f"loopx --registry {relative_state_file(project, registry_path)} registry",
            f"loopx --registry {relative_state_file(project, registry_path)} status",
            f"loopx --registry {relative_state_file(project, registry_path)} check --scan-root {project}",
            f"loopx --format json --registry {runtime_root / 'registry.global.json'} quota should-run --goal-id {goal_id} --runtime-profile generic_cli",
            f"loopx --registry {relative_state_file(project, registry_path)} refresh-state --goal-id {goal_id}",
            f"loopx --registry {runtime_root / 'registry.global.json'} status",
            f"loopx --registry {relative_state_file(project, registry_path)} history --goal-id {goal_id}",
        ],
        "install_repair_command": DEFAULT_INSTALL_REPAIR_COMMAND,
        "archive_fallback_install_command": ARCHIVE_FALLBACK_INSTALL_COMMAND,
        "install_repair_note": (
            "If this local LoopX install is missing or stale, repair the PyPI distribution "
            "and packaged workflow skills, then confirm with loopx doctor before continuing."
        ),
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
        f"- codex_app_heartbeat: `{payload.get('codex_app_heartbeat')}`",
        (
            "- onboarding_connection_validation: "
            f"`{payload.get('onboarding_connection_validation')}`"
        ),
        f"- heartbeat_opt_in_required: `{payload.get('heartbeat_opt_in_required')}`",
        f"- host_loop_activation_required: `{payload.get('host_loop_activation_required')}`",
        f"- onboarding_todos_written: `{payload.get('onboarding_todos_written')}`",
        f"- global_sync: `{(payload.get('global_sync') or {}).get('wrote')}`",
        "",
        "## Actions",
    ]
    for action in payload.get("actions") or []:
        lines.append(f"- `{action.get('path')}`: {action.get('action')} ({action.get('goal', '')})")

    force_warning = payload.get("force_bootstrap_warning")
    if isinstance(force_warning, dict):
        lines.extend(
            [
                "",
                "## Force Bootstrap Warning",
                f"- state_file: `{force_warning.get('state_file')}`",
                f"- will_replace_active_state: `{force_warning.get('will_replace_active_state')}`",
                f"- preserve_todos_requested: `{force_warning.get('preserve_todos_requested')}`",
                f"- recommended_scope_migration: {force_warning.get('recommended_scope_migration')}",
                f"- preserve_todos_option: `{force_warning.get('preserve_todos_option')}`",
            ]
        )

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
                "## Autonomy And Heartbeat Choice",
            ]
        )
        instruction = payload.get("heartbeat_opt_in_instruction")
        if instruction:
            lines.append(f"- heartbeat_opt_in_instruction: {instruction}")
        if payload.get("autonomous_advance_choice_required"):
            lines.append(
                "- Ask the user whether Codex may start autonomous advancement. If autonomous=yes, run the quota "
                "guard and execute the first accepted Agent Todo; if autonomous=no, stop after writing accepted todos "
                "and refresh-state."
            )

    lines.extend(["", "## Next Commands"])
    for command in payload.get("next_commands") or []:
        lines.append(f"- `{command}`")

    if payload.get("install_repair_command"):
        lines.extend(
            [
                "",
                "## Install / Update Hint",
                str(payload.get("install_repair_note") or ""),
                "```bash",
                str(payload.get("install_repair_command")),
                "```",
            ]
        )
    if payload.get("archive_fallback_install_command"):
        lines.extend(
            [
                "",
                "### Archive Fallback",
                "Use this only when an appropriate Python package environment is unavailable.",
                "```bash",
                str(payload.get("archive_fallback_install_command")),
                "```",
            ]
        )

    if payload.get("private_boundary_note"):
        lines.extend(["", "## Boundary Note", str(payload.get("private_boundary_note"))])
    return "\n".join(lines)
