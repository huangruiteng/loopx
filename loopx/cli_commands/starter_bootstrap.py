from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..codex_cli_probe import DEFAULT_CODEX_BIN
from ..agent_onboarding import (
    AgentTypeError,
    build_agent_onboarding_packet,
    build_agent_type_catalog,
    render_agent_onboarding_markdown,
    render_agent_type_catalog_markdown,
)
from ..bootstrap_command_pack import (
    build_loopx_bootstrap_command_pack,
    render_loopx_bootstrap_command_pack_markdown,
)
from ..project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    build_codex_cli_bootstrap_message,
    build_codex_cli_exec_handoff,
    build_codex_cli_tui_bootstrap_smoke_bundle,
    build_new_project_prompt,
    render_codex_cli_bootstrap_message_markdown,
    render_codex_cli_exec_handoff_markdown,
    render_codex_cli_tui_bootstrap_smoke_bundle_markdown,
    render_new_project_prompt_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_bootstrap_commands(subparsers: argparse._SubParsersAction) -> None:
    agent_onboard_parser = subparsers.add_parser(
        "agent-onboard",
        help=(
            "Generate a deterministic LoopX setup and host-loop activation packet "
            "for one agent runtime."
        ),
    )
    agent_onboard_parser.add_argument(
        "--agent-type",
        help="Agent runtime type: codex-app, codex-cli, claude-code, manual, or other-agent.",
    )
    agent_onboard_parser.add_argument(
        "--list-agent-types",
        action="store_true",
        help="List canonical agent_type values, accepted aliases, and ambiguous inputs.",
    )
    agent_onboard_parser.add_argument("--project", default=".", help="Project directory to inspect.")
    agent_onboard_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    agent_onboard_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/heartbeat commands.",
    )
    agent_onboard_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    agent_onboard_parser.add_argument(
        "--task-text",
        help="Optional first task text to include in the bootstrap command pack.",
    )

    bootstrap_command_pack_parser = subparsers.add_parser(
        "bootstrap-command-pack",
        help="Preview the /loopx project bootstrap command pack without mutating state.",
    )
    bootstrap_command_pack_parser.add_argument("--project", default=".", help="Project directory to inspect.")
    bootstrap_command_pack_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    bootstrap_command_pack_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/heartbeat commands.",
    )
    bootstrap_command_pack_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    bootstrap_command_pack_parser.add_argument(
        "--host-surface",
        default="chat-box",
        choices=["chat-box", "codex-app", "codex-cli-tui", "claude-code", "shell", "http", "worker-bridge"],
        help="Host surface where the slash command pack will be exposed.",
    )
    bootstrap_command_pack_parser.add_argument(
        "--goal-text",
        help=(
            "Optional text after /loopx. When present, preview the explicit goal-start flow: "
            "connect if needed, plan ranked todos, write them in order, then enter quota-gated automation."
        ),
    )
    bootstrap_command_pack_parser.add_argument(
        "--message-only",
        "--copy-only",
        dest="message_only",
        action="store_true",
        help="Print only the pasteable /loopx handling message.",
    )

    prompt_parser = subparsers.add_parser(
        "new-project-prompt",
        help="Generate a copy-paste Codex prompt for connecting a project from a goal document.",
    )
    prompt_parser.add_argument("--project", required=True, help="Project directory the target Codex session can access.")
    prompt_parser.add_argument("--goal-doc", required=True, help="Goal document path for the target project.")
    prompt_parser.add_argument("--goal-id", help="Initial stable goal id. Defaults to <project-name>-goal.")
    prompt_parser.add_argument("--objective", help="Initial objective. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--domain", help="Initial domain label. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--adapter-kind", default=DEFAULT_HANDOFF_ADAPTER_KIND)
    prompt_parser.add_argument("--adapter-status", default=DEFAULT_HANDOFF_ADAPTER_STATUS)
    prompt_parser.add_argument("--next-probe", help="Optional read-only pre-tick command for the target project.")
    prompt_parser.add_argument("--spawn-allowed", action="store_true", help="Include controller/sub-agent flags.")
    prompt_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    prompt_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")

    codex_cli_bootstrap_parser = subparsers.add_parser(
        "codex-cli-bootstrap-message",
        help="Generate a one-message Codex CLI TUI setup prompt that installs/connects LoopX, then sets the thin /goal loop.",
    )
    codex_cli_bootstrap_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_bootstrap_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_bootstrap_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    codex_cli_bootstrap_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    codex_cli_bootstrap_parser.add_argument(
        "--message-only",
        "--copy-only",
        dest="message_only",
        action="store_true",
        help="Print only the Codex CLI TUI paste message, without the Markdown review packet.",
    )

    codex_cli_tui_bootstrap_smoke_parser = subparsers.add_parser(
        "codex-cli-tui-bootstrap-smoke-bundle",
        help="Generate a transcript-free first-run smoke packet for the Codex CLI TUI bootstrap path.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--project",
        default=".",
        help="Project directory to model as the fresh repo.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--goal-id",
        help="Goal id. Defaults to <project-name>-goal.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )

    codex_cli_exec_parser = subparsers.add_parser(
        "codex-cli-exec-handoff",
        help="Show the disabled headless handoff boundary and the TUI message-only bootstrap command.",
    )
    codex_cli_exec_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_exec_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_exec_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    codex_cli_exec_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    codex_cli_exec_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable name embedded in the generated handoff command.",
    )


def handle_new_project_prompt_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_new_project_prompt(
        project=Path(args.project),
        goal_doc=Path(args.goal_doc),
        goal_id=args.goal_id,
        objective=args.objective,
        domain=args.domain,
        adapter_kind=args.adapter_kind,
        adapter_status=args.adapter_status,
        next_probe=args.next_probe,
        spawn_allowed=bool(args.spawn_allowed),
        allowed_domains=args.allowed_domain,
        write_scope=args.write_scope,
    )
    print_payload(payload, args.format, render_new_project_prompt_markdown)
    return 0


def handle_agent_onboard_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    if bool(getattr(args, "list_agent_types", False)):
        print_payload(build_agent_type_catalog(), args.format, render_agent_type_catalog_markdown)
        return 0
    if not args.agent_type:
        exc = AgentTypeError(
            value=None,
            reason="--agent-type is required unless --list-agent-types is used",
            suggestions=["codex-app", "codex-cli", "claude-code", "manual", "other-agent"],
        )
        print_payload(exc.to_payload(), args.format, render_agent_onboarding_markdown)
        return 2
    try:
        payload = build_agent_onboarding_packet(
            project=Path(args.project),
            agent_type=args.agent_type,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            cli_bin=args.cli_bin,
            task_text=args.task_text,
        )
    except AgentTypeError as exc:
        print_payload(exc.to_payload(), args.format, render_agent_onboarding_markdown)
        return 2
    print_payload(payload, args.format, render_agent_onboarding_markdown)
    return 0


def handle_loopx_bootstrap_command_pack_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_loopx_bootstrap_command_pack(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        host_surface=args.host_surface,
        goal_text=args.goal_text,
    )
    if bool(getattr(args, "message_only", False)):
        print(str(payload.get("message") or ""))
        return 0
    print_payload(payload, args.format, render_loopx_bootstrap_command_pack_markdown)
    return 0


def handle_codex_cli_bootstrap_message_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_bootstrap_message(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
    )
    if bool(getattr(args, "message_only", False)):
        print(str(payload.get("message") or ""))
        return 0
    print_payload(payload, args.format, render_codex_cli_bootstrap_message_markdown)
    return 0


def handle_codex_cli_tui_bootstrap_smoke_bundle_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_tui_bootstrap_smoke_bundle(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
    )
    print_payload(payload, args.format, render_codex_cli_tui_bootstrap_smoke_bundle_markdown)
    return 0


def handle_codex_cli_exec_handoff_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_exec_handoff(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
    )
    print_payload(payload, args.format, render_codex_cli_exec_handoff_markdown)
    return 0 if payload.get("ok") else 1


def handle_starter_bootstrap_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    handlers: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
        "agent-onboard": handle_agent_onboard_command,
        "bootstrap-command-pack": handle_loopx_bootstrap_command_pack_command,
        "new-project-prompt": handle_new_project_prompt_command,
        "codex-cli-bootstrap-message": handle_codex_cli_bootstrap_message_command,
        "codex-cli-tui-bootstrap-smoke-bundle": handle_codex_cli_tui_bootstrap_smoke_bundle_command,
        "codex-cli-exec-handoff": handle_codex_cli_exec_handoff_command,
    }
    handler = handlers.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
