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


def build_loopx_bootstrap_command_pack(
    *,
    project: Path,
    goal_id: str | None,
    agent_id: str | None,
    cli_bin: str,
    host_surface: str,
) -> dict[str, Any]:
    inspection = inspect_bootstrap_connection(project, goal_id=goal_id)
    resolved_project = str(inspection["project"])
    resolved_goal_id = str(inspection["goal_id"])
    connected = inspection.get("connection_state") == "connected"
    mutation_confirmation_required = bool(inspection.get("mutation_confirmation_required"))

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
        "canonical_cli_command": (
            f"{shell_arg(cli_bin)} bootstrap-command-pack --project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(resolved_goal_id)}"
        ),
        "read_only": True,
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": agent_id,
        "host_surface": host_surface,
        "project_connection": inspection,
        "recommended_next_step": recommended_next_step,
        "commands": {
            "doctor": f"{shell_arg(cli_bin)} doctor",
            "status": status_command,
            "quota_guard": quota_guard_command,
            "heartbeat_prompt": heartbeat_prompt_command,
            "bootstrap_dry_run_preview": bootstrap_preview_command,
            "bootstrap_after_user_confirmation": bootstrap_after_confirmation_command,
        },
        "safety_contract": {
            "runs_bootstrap": False,
            "writes_registry": False,
            "writes_state_file": False,
            "creates_heartbeat": False,
            "spends_quota": False,
            "mutation_requires_user_confirmation": mutation_confirmation_required,
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
    state = connection.get("connection_state")
    reason = connection.get("reason")

    if requires_confirmation:
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

    return f"""Handle `{CANONICAL_SLASH_COMMAND}` for this project without hidden mutation.

Project: `{project}`
Goal id: `{goal_id}`
Detected state: `{state}` ({reason})

Rules:
- This command pack is read-only. Do not run bootstrap/connect, create heartbeat automation, or spend quota while interpreting it.
- If the project is not fully connected, ask for explicit user confirmation before any command that writes `.loopx/` or `.codex/goals/`.
- If the project is connected, reuse the existing state and show the status/gate/todo snapshot.

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
    return f"""# /loopx Bootstrap Command Pack

Canonical slash command: `{payload.get("slash_command")}`

## Detected Project State

- project: `{payload.get("project")}`
- goal_id: `{payload.get("goal_id")}`
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

## Key Commands

```bash
{commands.get("status", "")}
```

```bash
{commands.get("bootstrap_dry_run_preview", "")}
```

## Safety Contract

- read_only: `{payload.get("read_only")}`
- writes_registry: `{safety.get("writes_registry")}`
- writes_state_file: `{safety.get("writes_state_file")}`
- creates_heartbeat: `{safety.get("creates_heartbeat")}`
- spends_quota: `{safety.get("spends_quota")}`
"""
