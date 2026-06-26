from __future__ import annotations

import argparse
from collections.abc import Callable

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


def handle_slash_commands_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "slash-commands":
        return None
    payload = build_slash_command_catalog(
        cli_bin=args.cli_bin,
        include_legacy_aliases=not bool(args.no_legacy_aliases),
    )
    print_payload(payload, output_format(args), render_slash_command_catalog_markdown)
    return 0
