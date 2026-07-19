from __future__ import annotations

import argparse
from collections.abc import Callable

from ..slash_command_install import (
    install_slash_commands,
    render_slash_command_install_markdown,
)
from ..slash_commands import build_slash_command_catalog, render_slash_command_catalog_markdown


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def register_slash_commands_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "slash-commands",
        help="List LoopX chat slash commands, onboarding hints, and CLI references.",
    )
    add_subcommand_format(parser)
    parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name to show in command references.",
    )
    parser.add_argument(
        "--no-legacy-aliases",
        action="store_true",
        help="Hide legacy /loop-global-* aliases from the command catalog.",
    )
    install_group = parser.add_mutually_exclusive_group()
    install_group.add_argument(
        "--install",
        action="store_true",
        help="Install LoopX command skill files for supported hosts.",
    )
    install_group.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove LoopX-managed command skill files for supported hosts while preserving user-owned files.",
    )
    parser.add_argument(
        "--surface",
        action="append",
        choices=["all", "codex", "codex-cli", "codex-app", "codex-ide-plugin", "codex-ide", "claude-code", "opencode"],
        help=(
            "Host surface to install. Repeatable. Defaults to static command facades "
            "for Codex, Claude Code, and OpenCode."
        ),
    )
    parser.add_argument(
        "--with-goal-bridge",
        action="store_true",
        help=(
            "Also install or uninstall the executable OpenCode goal bridge. Requires "
            "an effective OpenCode surface and explicit opt-in."
        ),
    )
    parser.add_argument(
        "--codex-home",
        help="Codex home for skill installation. Defaults to CODEX_HOME or ~/.codex.",
    )
    parser.add_argument(
        "--claude-home",
        help="Claude Code home for skill installation. Defaults to CLAUDE_HOME or ~/.claude.",
    )
    parser.add_argument(
        "--opencode-home",
        help="OpenCode config directory. Defaults to OPENCODE_CONFIG_DIR or ~/.config/opencode.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what slash-command files would be installed without writing them.",
    )


def handle_slash_commands_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "slash-commands":
        return None
    if args.install or args.uninstall or args.dry_run:
        payload = install_slash_commands(
            execute=bool((args.install or args.uninstall) and not args.dry_run),
            uninstall=bool(args.uninstall),
            with_goal_bridge=bool(args.with_goal_bridge),
            surfaces=args.surface,
            cli_bin=args.cli_bin,
            include_legacy_aliases=not bool(args.no_legacy_aliases),
            codex_home=args.codex_home,
            claude_home=args.claude_home,
            opencode_home=args.opencode_home,
        )
        print_payload(payload, output_format(args), render_slash_command_install_markdown)
        return 0 if payload.get("ok") is True else 1
    payload = build_slash_command_catalog(
        cli_bin=args.cli_bin,
        include_legacy_aliases=not bool(args.no_legacy_aliases),
    )
    print_payload(payload, output_format(args), render_slash_command_catalog_markdown)
    return 0
