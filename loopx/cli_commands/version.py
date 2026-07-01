from __future__ import annotations

import argparse
from collections.abc import Callable

from .. import __version__


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def build_version_payload() -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "loopx_version_v0",
        "name": "loopx",
        "version": __version__,
    }


def render_version_markdown(payload: dict[str, object]) -> str:
    return f"{payload.get('name')} {payload.get('version')}\n"


def register_version_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser("version", help="Print the installed LoopX version.")
    add_subcommand_format(parser)


def handle_version_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "version":
        return None
    print_payload(build_version_payload(), output_format(args), render_version_markdown)
    return 0
