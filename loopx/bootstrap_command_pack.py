from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bootstrap import default_goal_id
from .project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    render_heartbeat_prompt_command,
    render_quota_guard_command,
    shell_arg,
)
from .registry import registry_goals, resolve_state_file


SCHEMA_VERSION = "loopx_bootstrap_command_pack_v0"
CANONICAL_SLASH_COMMAND = "/loopx"
GOAL_START_SCHEMA_VERSION = "loopx_goal_start_command_v0"


def _resolve_project(project: Path) -> Path:
    project = project.expanduser()
    try:
        return project.resolve()
    except OSError:
        return project.absolute()


def _read_registry(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        return None, None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "registry root must be a JSON object"
    return payload, None


def _select_goal(goals: list[dict[str, Any]], goal_id: str | None) -> tuple[str, dict[str, Any] | None]:
    if goal_id:
        for goal in goals:
            if goal.get("id") == goal_id:
                return goal_id, goal
        return goal_id, None
    if goals:
        first_goal_id = str(goals[0].get("id"))
        return first_goal_id, goals[0]
    return "", None


def inspect_bootstrap_connection(project: Path, *, goal_id: str | None = None) -> dict[str, Any]:
    resolved_project = _resolve_project(project)
    registry_path = resolved_project / ".loopx" / "registry.json"
    registry_exists = registry_path.exists()
    registry, registry_error = _read_registry(registry_path) if registry_exists else (None, None)
    inferred_goal_id = goal_id or default_goal_id(resolved_project)
    state_file = resolved_project / ".codex" / "goals" / inferred_goal_id / "ACTIVE_GOAL_STATE.md"

    if registry_error:
        return {
            "project": str(resolved_project),
            "registry": str(registry_path),
            "registry_exists": registry_exists,
            "goal_id": inferred_goal_id,
            "goal_found": False,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_invalid",
            "mutation_confirmation_required": True,
            "reason": registry_error,
        }

    if not registry:
        return {
            "project": str(resolved_project),
            "registry": str(registry_path),
            "registry_exists": False,
            "goal_id": inferred_goal_id,
            "goal_found": False,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "not_connected",
            "mutation_confirmation_required": True,
            "reason": "project-local .loopx/registry.json is missing",
        }

    goals = registry_goals(registry)
    selected_goal_id, selected_goal = _select_goal(goals, goal_id)
    resolved_goal_id = selected_goal_id or inferred_goal_id
    fallback_state_file = resolved_project / ".codex" / "goals" / resolved_goal_id / "ACTIVE_GOAL_STATE.md"
    goal_state_file = (
        resolve_state_file(resolved_project, str(selected_goal.get("state_file")))
        if selected_goal and selected_goal.get("state_file")
        else None
    )
    state_file = goal_state_file or fallback_state_file

    if selected_goal is None:
        return {
            "project": str(resolved_project),
            "registry": str(registry_path),
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": False,
            "known_goal_ids": [str(goal.get("id")) for goal in goals],
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_without_goal",
            "mutation_confirmation_required": True,
            "reason": "registry exists but no matching goal entry was found",
        }

    if not selected_goal.get("state_file"):
        return {
            "project": str(resolved_project),
            "registry": str(registry_path),
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": True,
            "state_file": str(state_file),
            "state_file_exists": state_file.exists(),
            "connection_state": "registry_goal_missing_state_file",
            "mutation_confirmation_required": True,
            "reason": "goal entry does not declare state_file",
        }

    if not state_file.exists():
        return {
            "project": str(resolved_project),
            "registry": str(registry_path),
            "registry_exists": True,
            "goal_id": resolved_goal_id,
            "goal_found": True,
            "state_file": str(state_file),
            "state_file_exists": False,
            "connection_state": "state_file_missing",
            "mutation_confirmation_required": True,
            "reason": "registry goal points at a state_file that is missing",
        }

    return {
        "project": str(resolved_project),
        "registry": str(registry_path),
        "registry_exists": True,
        "goal_id": resolved_goal_id,
        "goal_found": True,
        "state_file": str(state_file),
        "state_file_exists": True,
        "connection_state": "connected",
        "mutation_confirmation_required": False,
        "reason": "registry goal and active state_file are present",
    }


def _bootstrap_command(
    *,
    project: str,
    goal_id: str,
    cli_bin: str,
    dry_run: bool,
) -> str:
    lines = [
        f"cd {shell_arg(project)}",
        f"{shell_arg(cli_bin)} bootstrap \\",
        "  --project . \\",
        f"  --goal-id {shell_arg(goal_id)} \\",
        f"  --adapter-kind {shell_arg(DEFAULT_HANDOFF_ADAPTER_KIND)} \\",
        f"  --adapter-status {shell_arg(DEFAULT_HANDOFF_ADAPTER_STATUS)} \\",
        "  --codex-app-heartbeat ask",
    ]
    if dry_run:
        lines[-1] += " \\"
        lines.append("  --dry-run")
    return "\n".join(lines)


def _project_command(project: str, command: str) -> str:
    return "\n".join([f"cd {shell_arg(project)}", command])


def _goal_start_bootstrap_command(
    *,
    project: str,
    goal_id: str,
    goal_text: str | None,
    cli_bin: str,
) -> str:
    objective = goal_text or "<exact /loopx goal text>"
    lines = [
        f"cd {shell_arg(project)}",
        f"{shell_arg(cli_bin)} bootstrap \\",
        "  --project . \\",
        f"  --goal-id {shell_arg(goal_id)} \\",
        f"  --objective {shell_arg(objective)} \\",
        f"  --adapter-kind {shell_arg(DEFAULT_HANDOFF_ADAPTER_KIND)} \\",
        f"  --adapter-status {shell_arg(DEFAULT_HANDOFF_ADAPTER_STATUS)} \\",
        "  --no-onboarding-scan \\",
        "  --codex-app-heartbeat ask",
    ]
    return "\n".join(lines)


def _goal_start_contract(*, goal_text: str | None, connected: bool) -> dict[str, Any]:
    return {
        "schema_version": GOAL_START_SCHEMA_VERSION,
        "slash_syntax": "/loopx <goal text>",
        "goal_text": goal_text,
        "explicit_invocation_confirms_project_local_state_writes": True,
        "connect_if_needed": True,
        "bootstrap_policy": "create project-local LoopX state only when no matching registry goal exists",
        "planner": {
            "required_before_todo_write": True,
            "default_profile": "open_ended_product_direction",
            "profile_selection": (
                "Use open_ended_product_direction when the user's goal is a broad, "
                "fuzzy product direction or new initiative. Use clear_bounded_problem "
                "when the target is a concrete task with a clear success condition. "
                "In both cases, let the model produce a real ordered plan before writes."
            ),
            "profiles": {
                "open_ended_product_direction": {
                    "suggested_items_min": 2,
                    "suggested_items_max": 5,
                    "intent": (
                        "turn an ambiguous product direction into public-safe, ranked "
                        "todo options before execution"
                    ),
                },
                "clear_bounded_problem": {
                    "item_count_policy": "planner_sized",
                    "may_reuse_current_todo_when_it_already_represents_the_plan": True,
                    "intent": (
                        "make the approach explicit with enough concise ordered todos, "
                        "without arbitrary caps or management-only filler"
                    ),
                },
            },
            "allowed_priorities": ["P0", "P1", "P2"],
            "default_role": "agent",
            "default_task_class": "advancement_task",
            "required_fields": ["priority", "text", "task_class", "action_kind"],
            "public_safe_only": True,
            "budget_policy": (
                "For clear bounded problems, planning should sharpen action selection "
                "rather than crowd out task work; prefer the minimum sufficient ordered "
                "todo plan over fixed-count filler."
            ),
        },
        "priority_ordering": {
            "bucket_order": ["P0", "P1", "P2"],
            "same_priority_tie_breaker": "planner_order_then_todo_write_order",
            "prompt_constraint": (
                "Sort planned todos by priority bucket and relative rank before writing. "
                "For multiple P0/P1/P2 items, earlier items are higher rank; preserve that "
                "exact order when running todo add commands."
            ),
            "storage_contract": (
                "LoopX status/quota already use todo index as the same-priority tie-breaker, "
                "so host integrations must write todos in planner order instead of adding "
                "a separate rank field."
            ),
        },
        "activation": {
            "after_write": ["refresh-state", "quota should-run"],
            "begin_automation_when_quota_allows": True,
            "spend_quota_after_writeback": True,
        },
        "connected_at_preview_time": connected,
        "stop_conditions": [
            "private material requested before a public-safe todo can be written",
            "credentials or secrets are required",
            "destructive git or production operation would be needed",
            "the host cannot execute shell/CLI/tool calls or persist LoopX state",
        ],
    }


def _goal_start_prompt(*, goal_text: str | None, goal_id: str, agent_id: str | None) -> str:
    goal_clause = (
        f"Goal text: {goal_text}"
        if goal_text
        else "Goal text: use the text after `/loopx`; if it is empty, handle bare `/loopx` instead."
    )
    agent_clause = f" Use agent id `{agent_id}` for quota/claim commands." if agent_id else ""
    return f"""Plan before writing todos for `/loopx <goal text>`.

{goal_clause}
Goal id: {goal_id}.{agent_clause}

Planning rules:
1. Choose the planning profile: broad or fuzzy product direction uses 2-5 public-safe todos; clear bounded problems use a planner-sized ordered todo plan with enough steps to make the approach explicit.
2. Plan before any `loopx todo add`; keep each item concise and avoid management-only filler.
3. Every new todo starts with `[P0]`, `[P1]`, or `[P2]`; include at least one `[P0]` unless the first useful step is blocked by a user gate.
4. If several todos share the same priority, their listed order is their relative priority. Preserve that exact order when writing them.
5. Prefer executable Agent Todo items with `task_class=advancement_task`; use User Todo only for concrete owner decisions or private-material gates.
6. After writing todos, run `loopx refresh-state --goal-id {goal_id}`, then `loopx quota should-run --goal-id {goal_id}` and begin the first allowed bounded segment.
"""


def build_loopx_bootstrap_command_pack(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
    goal_text: str | None = None,
) -> dict[str, Any]:
    inspection = inspect_bootstrap_connection(project, goal_id=goal_id)
    resolved_project = str(inspection["project"])
    resolved_goal_id = str(inspection["goal_id"])
    connected = inspection.get("connection_state") == "connected"
    mutation_confirmation_required = bool(inspection.get("mutation_confirmation_required"))
    normalized_goal_text = " ".join(goal_text.split()) if goal_text else None
    explicit_goal_start = bool(normalized_goal_text)

    bootstrap_preview_command = _bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        dry_run=True,
    )
    bootstrap_after_confirmation_command = _bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        dry_run=False,
    )
    heartbeat_prompt_command = render_heartbeat_prompt_command(
        resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
        agent_scope=f"{host_surface} LoopX command pack",
    )
    quota_guard_command = render_quota_guard_command(resolved_goal_id, cli_bin=cli_bin, agent_id=agent_id)
    status_command = _project_command(resolved_project, f"{shell_arg(cli_bin)} status")
    goal_start_bootstrap_command = _goal_start_bootstrap_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        goal_text=normalized_goal_text,
        cli_bin=cli_bin,
    )
    goal_start_plan_prompt = _goal_start_prompt(
        goal_text=normalized_goal_text,
        goal_id=resolved_goal_id,
        agent_id=agent_id,
    )

    if explicit_goal_start:
        recommended_next_step = {
            "kind": "goal_plan_write_and_activate",
            "requires_user_confirmation": False,
            "confirmation_source": "/loopx <goal text>",
            "summary": (
                "The slash command includes an explicit goal. Connect the project if needed, plan ranked todos, "
                "write them in exact plan order, refresh state, and enter the quota-gated automation flow."
            ),
            "connect_command_if_needed": goal_start_bootstrap_command,
            "plan_prompt": goal_start_plan_prompt,
        }
    else:
        recommended_next_step = {
            "kind": "status_and_loop_activation" if connected else "confirm_before_bootstrap_mutation",
            "requires_user_confirmation": mutation_confirmation_required,
            "summary": (
                "Project is connected; show status, then generate the heartbeat prompt only if the user wants a loop surface."
                if connected
                else "Project is not fully connected; show the dry-run preview and ask before running bootstrap/connect."
            ),
        }
        if mutation_confirmation_required:
            recommended_next_step["dry_run_command"] = bootstrap_preview_command
            recommended_next_step["after_confirmation_command"] = bootstrap_after_confirmation_command

    payload: dict[str, Any] = {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "slash_command": CANONICAL_SLASH_COMMAND,
        "slash_forms": [
            {"form": "/loopx", "mode": "inspect_or_connect_preview"},
            {"form": "/loopx <goal text>", "mode": "goal_plan_write_and_activate"},
        ],
        "canonical_cli_command": (
            f"{shell_arg(cli_bin)} bootstrap-command-pack --project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(resolved_goal_id)}"
        ),
        "read_only": True,
        "goal_text": normalized_goal_text,
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "host_surface": host_surface,
        "project_connection": inspection,
        "recommended_next_step": recommended_next_step,
        "goal_start_contract": _goal_start_contract(goal_text=normalized_goal_text, connected=connected),
        "commands": {
            "doctor": f"{shell_arg(cli_bin)} doctor",
            "status": status_command,
            "quota_guard": quota_guard_command,
            "heartbeat_prompt": heartbeat_prompt_command,
            "bootstrap_dry_run_preview": bootstrap_preview_command,
            "bootstrap_after_user_confirmation": bootstrap_after_confirmation_command,
            "goal_start_connect_if_needed": goal_start_bootstrap_command,
            "goal_start_plan_prompt": goal_start_plan_prompt,
            "goal_start_refresh_state": f"{shell_arg(cli_bin)} refresh-state --goal-id {shell_arg(resolved_goal_id)}",
            "goal_start_quota_should_run": (
                f"{shell_arg(cli_bin)} quota should-run --goal-id {shell_arg(resolved_goal_id)}"
                + (f" --agent-id {shell_arg(agent_id)}" if agent_id else "")
            ),
        },
        "safety_contract": {
            "runs_bootstrap": False,
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_requires_user_confirmation": mutation_confirmation_required and not explicit_goal_start,
            "bare_command_mutation_requires_user_confirmation": mutation_confirmation_required,
            "explicit_goal_start_may_write_project_local_state": explicit_goal_start,
        },
    }
    payload["message"] = render_loopx_bootstrap_command_pack_message(payload)
    return payload


def render_loopx_bootstrap_command_pack_message(payload: dict[str, Any]) -> str:
    connection = payload.get("project_connection")
    connection = connection if isinstance(connection, dict) else {}
    commands = payload.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    next_step = payload.get("recommended_next_step")
    next_step = next_step if isinstance(next_step, dict) else {}
    requires_confirmation = bool(next_step.get("requires_user_confirmation"))
    project = payload.get("project")
    goal_id = payload.get("goal_id")
    goal_text = payload.get("goal_text")
    state = connection.get("connection_state")
    reason = connection.get("reason")
    goal_start_contract = payload.get("goal_start_contract")
    goal_start_contract = goal_start_contract if isinstance(goal_start_contract, dict) else {}

    if goal_text:
        action = f"""This is an explicit goal-start invocation. Connect project-local LoopX state if needed:

```bash
{commands.get("goal_start_connect_if_needed", "")}
```

Then plan before writing todos. Preserve relative priority by write order:

````text
{commands.get("goal_start_plan_prompt", "")}
````

Write the planned todos with `loopx todo add` in the exact planned order. Same-priority items use that write order as the tie-breaker.

After todo writeback:

```bash
{commands.get("goal_start_refresh_state", "")}
{commands.get("goal_start_quota_should_run", "")}
```"""
    elif requires_confirmation:
        action = f"""First show this dry-run preview, then ask me before running the mutation:

```bash
{commands.get("bootstrap_dry_run_preview", "")}
```

If I confirm, run:

```bash
{commands.get("bootstrap_after_user_confirmation", "")}
```"""
    else:
        action = f"""Start with the current LoopX status and do not reconnect:

```bash
{commands.get("status", "")}
```

Only after I ask for a recurring loop surface, generate the heartbeat body:

```bash
{commands.get("heartbeat_prompt", "")}
```"""

    return f"""Handle `{CANONICAL_SLASH_COMMAND}` for this project with explicit mutation boundaries.

Project: `{project}`
Goal id: `{goal_id}`
Goal text: `{goal_text or ""}`
Detected state: `{state}` ({reason})

Rules:
- This command pack preview is read-only. Do not run bootstrap/connect, create heartbeat automation, or spend quota while only previewing it.
- Bare `/loopx` is read/status-first: if the project is not fully connected, ask for explicit user confirmation before any command that writes `.loopx/` or `.codex/goals/`.
- `/loopx <goal text>` is explicit goal-start intent: it may create project-local LoopX state, but it must run the profile-appropriate planning checkpoint before writing todos.
- Same-priority todos are ranked by planner order, then by `todo add` write order; preserve the order exactly.
- If the project is connected, reuse the existing state and show the status/gate/todo snapshot.

Goal-start contract: `{goal_start_contract.get("schema_version")}`

{action}

For ongoing work after the project is connected, use the quota guard:

```bash
{commands.get("quota_guard", "")}
```
"""


def render_loopx_bootstrap_command_pack_markdown(payload: dict[str, Any]) -> str:
    connection = payload.get("project_connection")
    connection = connection if isinstance(connection, dict) else {}
    next_step = payload.get("recommended_next_step")
    next_step = next_step if isinstance(next_step, dict) else {}
    safety = payload.get("safety_contract")
    safety = safety if isinstance(safety, dict) else {}
    commands = payload.get("commands")
    commands = commands if isinstance(commands, dict) else {}
    goal_start = payload.get("goal_start_contract")
    goal_start = goal_start if isinstance(goal_start, dict) else {}
    ordering = goal_start.get("priority_ordering")
    ordering = ordering if isinstance(ordering, dict) else {}
    return f"""# /loopx Bootstrap Command Pack

Canonical slash command: `{payload.get("slash_command")}`
Supported forms: `/loopx`, `/loopx <goal text>`

## Detected Project State

- project: `{payload.get("project")}`
- goal_id: `{payload.get("goal_id")}`
- goal_text: `{payload.get("goal_text") or ""}`
- connection_state: `{connection.get("connection_state")}`
- reason: `{connection.get("reason")}`
- registry: `{connection.get("registry")}`
- state_file: `{connection.get("state_file")}`

## Recommended Next Step

- kind: `{next_step.get("kind")}`
- requires_user_confirmation: `{next_step.get("requires_user_confirmation")}`
- summary: {next_step.get("summary")}

## Paste Message

````text
{payload.get("message", "")}
````

## Goal Start Contract

- schema: `{goal_start.get("schema_version")}`
- planner_required_before_todo_write: `{(goal_start.get("planner") or {}).get("required_before_todo_write") if isinstance(goal_start.get("planner"), dict) else None}`
- same_priority_tie_breaker: `{ordering.get("same_priority_tie_breaker")}`
- prompt_constraint: {ordering.get("prompt_constraint")}

## Key Commands

```bash
{commands.get("status", "")}
```

```bash
{commands.get("bootstrap_dry_run_preview", "")}
```

```bash
{commands.get("goal_start_connect_if_needed", "")}
```

## Safety Contract

- read_only: `{payload.get("read_only")}`
- writes_registry: `{safety.get("writes_registry")}`
- writes_state_file: `{safety.get("writes_state_file")}`
- creates_heartbeat: `{safety.get("creates_heartbeat")}`
- spends_quota: `{safety.get("spends_quota")}`
- explicit_goal_start_may_write_project_local_state: `{safety.get("explicit_goal_start_may_write_project_local_state")}`
"""
