from __future__ import annotations

from pathlib import Path
from typing import Any

from .agent_registry import registered_agent_ids_from_registry
from .bootstrap_command_pack import inspect_bootstrap_connection
from .host_loop_activation import (
    build_host_loop_activation_packet,
    normalize_agent_type,
    render_agent_type_catalog_markdown,
    scheduler_command_binding_for_agent_type,
)
from .project_prompt import (
    render_available_capability_args,
    render_codex_cli_no_clone_preflight,
    render_quota_guard_command,
    shell_arg,
)


SCHEMA_VERSION = "loopx_agent_onboarding_v0"


def _surface_install_command(agent_type: str, cli_bin: str) -> str | None:
    if agent_type in {"codex-app", "codex-ide-plugin", "codex-cli"}:
        return f"{shell_arg(cli_bin)} slash-commands --install --surface codex"
    if agent_type == "claude-code":
        return f"{shell_arg(cli_bin)} slash-commands --install --surface claude-code"
    if agent_type == "opencode":
        return (
            f"{shell_arg(cli_bin)} slash-commands --install --surface opencode "
            "--with-goal-bridge"
        )
    return None


def _bootstrap_pack_command(
    *,
    project: str,
    goal_id: str,
    agent_id: str | None,
    agent_type: str,
    cli_bin: str,
    task_text: str | None,
    available_capabilities: list[str] | None,
) -> str:
    surface_by_type = {
        "codex-app": "codex-app",
        "codex-ide-plugin": "codex-ide-plugin",
        "codex-cli": "codex-cli-tui",
        "claude-code": "claude-code",
        "opencode": "opencode",
        "manual": "shell",
        "other-agent": "worker-bridge",
    }
    parts = [
        shell_arg(cli_bin),
        "bootstrap-command-pack",
        "--project",
        shell_arg(project),
        "--goal-id",
        shell_arg(goal_id),
        "--host-surface",
        shell_arg(surface_by_type.get(agent_type, "worker-bridge")),
    ]
    if agent_id:
        parts.extend(["--agent-id", shell_arg(agent_id)])
    if task_text:
        parts.extend(["--goal-text", shell_arg(task_text)])
    for capability in available_capabilities or []:
        parts.extend(["--available-capability", shell_arg(capability)])
    return " ".join(parts)


def _start_instruction(agent_type: str) -> str:
    if agent_type == "codex-app":
        return "Use `$loopx <task>` or select the LoopX skill from `/skills`; Codex App should then create/update the heartbeat automation."
    if agent_type == "codex-ide-plugin":
        return "Use `$loopx <task>` or select the LoopX skill from `/skills`; after todos are written, set `/goal <task_body>` in the visible IDE plugin."
    if agent_type == "codex-cli":
        return "Use `$loopx <task>` or select the LoopX skill from `/skills`; after todos are written, set `/goal <task_body>` in the visible TUI."
    if agent_type == "claude-code":
        return "Run `/loopx <task>` to arm LoopX, then run native `/loop`."
    if agent_type == "opencode":
        return "Run `/loopx <task>`; after todo writeback, call `loopx_goal_activate` with the generated heartbeat task body."
    if agent_type == "manual":
        return "Use the CLI packet and wire an external scheduler, or run quota/status/todo commands manually."
    return "Use the host's explicit LoopX command facade such as `@loopx <task>` or `$loopx <task>`, then wire its scheduler through this packet."


def build_agent_onboarding_packet(
    *,
    project: Path,
    agent_type: str,
    goal_id: str | None = None,
    agent_id: str | None = None,
    cli_bin: str = "loopx",
    task_text: str | None = None,
    available_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    canonical_agent_type = normalize_agent_type(agent_type)
    inspection = inspect_bootstrap_connection(project, goal_id=goal_id)
    resolved_project = str(inspection["project"])
    resolved_goal_id = str(inspection["goal_id"])
    registry_path = Path(str(inspection["registry"]))
    registered_agents = registered_agent_ids_from_registry(
        registry_path,
        resolved_goal_id,
    )
    host_loop_activation = build_host_loop_activation_packet(
        agent_type=canonical_agent_type,
        goal_id=resolved_goal_id,
        cli_bin=cli_bin,
        agent_id=agent_id,
        registered_agents=registered_agents,
        available_capabilities=available_capabilities,
    )
    selected_agent_id = host_loop_activation.get("agent_id")
    activation_allowed = bool(host_loop_activation.get("activation_allowed"))
    normalized_available_capabilities = list(
        host_loop_activation.get("available_capabilities") or []
    )
    install_command = _surface_install_command(canonical_agent_type, cli_bin)
    bootstrap_pack_command = _bootstrap_pack_command(
        project=resolved_project,
        goal_id=resolved_goal_id,
        agent_id=str(selected_agent_id) if selected_agent_id else None,
        agent_type=canonical_agent_type,
        cli_bin=cli_bin,
        task_text=task_text,
        available_capabilities=normalized_available_capabilities,
    )
    commands: dict[str, Any] = {
        "doctor_or_install": render_codex_cli_no_clone_preflight(cli_bin=cli_bin),
        "bootstrap_command_pack": bootstrap_pack_command,
        "quota_guard": (
            render_quota_guard_command(
                resolved_goal_id,
                cli_bin=cli_bin,
                agent_id=str(selected_agent_id) if selected_agent_id else None,
                available_capabilities=normalized_available_capabilities,
                **scheduler_command_binding_for_agent_type(canonical_agent_type),
            )
            if activation_allowed
            else None
        ),
        "agent_onboard_recheck": (
            f"{shell_arg(cli_bin)} agent-onboard "
            f"--agent-type {shell_arg(canonical_agent_type)} "
            f"--project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(resolved_goal_id)}"
            + (
                f" --agent-id {shell_arg(str(selected_agent_id))}"
                if selected_agent_id
                else ""
            )
            + render_available_capability_args(normalized_available_capabilities)
        ),
    }
    if install_command:
        commands["install_command_facade"] = install_command
    if canonical_agent_type == "codex-cli":
        commands["codex_cli_bootstrap_message"] = (
            f"{shell_arg(cli_bin)} codex-cli-bootstrap-message "
            f"--project {shell_arg(resolved_project)} "
            f"--goal-id {shell_arg(resolved_goal_id)}"
            + (
                f" --agent-id {shell_arg(str(selected_agent_id))}"
                if selected_agent_id
                else ""
            )
        )
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "agent_type": canonical_agent_type,
        "project": resolved_project,
        "goal_id": resolved_goal_id,
        "agent_id": selected_agent_id,
        "requested_agent_id": agent_id,
        "available_capabilities": normalized_available_capabilities,
        "identity_selection_gate": host_loop_activation.get("identity_selection_gate"),
        "task_text": task_text,
        "project_connection": inspection,
        "host_loop_activation": host_loop_activation,
        "recommended_start": (
            "Select one registered agent lane from identity_selection_gate, then rerun onboarding."
            if not activation_allowed
            else _start_instruction(canonical_agent_type)
        ),
        "commands": commands,
        "cost_model": {
            "onboarding": "run once during install/connect or when the active host loop is missing/stale",
            "loopx_task_start": (
                "`/loopx <task>` or the explicit skill should call this packet only when "
                "host_loop_activation is missing, unknown, stale, or the agent type changed"
            ),
            "normal_ticks": "read quota/status/state directly; do not recompute onboarding every turn",
        },
        "slash_command_contract": {
            "after_todo_writeback": (
                "refresh state, activate the host loop through host_loop_activation, "
                "or report the concrete host-tool gate; then run quota should-run"
            ),
            "connected_registry_is_not_enough": True,
            "setup_complete_requires": [
                "project-local LoopX state exists or was intentionally previewed",
                "ordered todos are written when task text was supplied",
                "host_loop_activation success criteria are satisfied or a concrete gate is reported",
            ],
        },
    }


def render_agent_onboarding_markdown(payload: dict[str, Any]) -> str:
    if not payload.get("ok"):
        return render_agent_type_catalog_markdown(payload)
    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    activation = (
        payload.get("host_loop_activation")
        if isinstance(payload.get("host_loop_activation"), dict)
        else {}
    )
    steps = activation.get("activation_steps") if isinstance(activation.get("activation_steps"), list) else []
    criteria = (
        activation.get("success_criteria")
        if isinstance(activation.get("success_criteria"), list)
        else []
    )
    identity_gate = payload.get("identity_selection_gate")
    identity_gate = identity_gate if isinstance(identity_gate, dict) else {}
    lines = [
        "# LoopX Agent Onboarding",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- agent_type: `{payload.get('agent_type')}`",
        f"- project: `{payload.get('project')}`",
        f"- goal_id: `{payload.get('goal_id')}`",
        f"- recommended_start: {payload.get('recommended_start')}",
        "",
        "## Commands",
        "",
        "```bash",
        str(commands.get("doctor_or_install") or ""),
        "```",
    ]
    if commands.get("install_command_facade"):
        lines.extend(["", "```bash", str(commands.get("install_command_facade")), "```"])
    lines.extend(["", "```bash", str(commands.get("bootstrap_command_pack") or ""), "```"])
    if commands.get("codex_cli_bootstrap_message"):
        lines.extend(["", "```bash", str(commands.get("codex_cli_bootstrap_message")), "```"])
    lines.extend(
        [
            "",
            "## Host Loop Activation",
            "",
            f"- host_surface: `{activation.get('host_surface')}`",
            f"- activation_method: `{activation.get('activation_method')}`",
            f"- activation_input_command: `{activation.get('activation_input_command')}`",
            "",
            "Steps:",
        ]
    )
    lines.extend(f"- {step}" for step in steps)
    lines.append("")
    lines.append("Success criteria:")
    lines.extend(f"- {item}" for item in criteria)
    if identity_gate:
        lines.extend(["", "## Agent Identity Gate", ""])
        lines.append(f"- reason: {identity_gate.get('reason')}")
        for choice in identity_gate.get("choices") or []:
            if isinstance(choice, dict):
                lines.append(
                    f"- `{choice.get('agent_id')}` ({choice.get('role')}): "
                    f"`{choice.get('heartbeat_prompt_json')}`"
                )
    lines.extend(
        [
            "",
            "## Recheck Policy",
            "",
            f"- {payload.get('cost_model', {}).get('loopx_task_start') if isinstance(payload.get('cost_model'), dict) else ''}",
        ]
    )
    return "\n".join(lines)
