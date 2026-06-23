from __future__ import annotations

import argparse
from collections.abc import Callable

from ..capabilities.catalog import (
    build_capability_catalog_packet,
    build_capability_detail_packet,
    capability_ids,
    render_capability_catalog_markdown,
    render_capability_detail_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_capability_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    capability_parser = subparsers.add_parser(
        "capability",
        help="Inspect real LoopX product capability paths.",
    )
    capability_sub = capability_parser.add_subparsers(
        dest="capability_command",
        required=True,
    )
    list_parser = capability_sub.add_parser(
        "list",
        help="List implemented product capability paths.",
    )
    add_subcommand_format(list_parser)
    show_parser = capability_sub.add_parser(
        "show",
        help="Show CLI, protocol, smoke, and boundary details for a capability.",
    )
    add_subcommand_format(show_parser)
    show_parser.add_argument(
        "capability_id",
        choices=capability_ids(),
        help="Capability id to inspect.",
    )


def handle_capability_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "capability":
        return None
    if args.capability_command == "list":
        payload = build_capability_catalog_packet()
        renderer = render_capability_catalog_markdown
    elif args.capability_command == "show":
        payload = build_capability_detail_packet(args.capability_id)
        renderer = render_capability_detail_markdown
    else:
        raise ValueError("capability requires `list` or `show`")
    print_payload(payload, output_format(args), renderer)
    return 0
