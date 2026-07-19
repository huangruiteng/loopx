from __future__ import annotations

import argparse
from collections.abc import Callable

from ..capabilities.catalog import (
    build_capability_catalog_packet,
    build_capability_detail_packet,
    render_capability_catalog_markdown,
    render_capability_detail_markdown,
)
from ..extensions.runtime import default_extension_state_file


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _add_extension_manifest_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--extension-manifest",
        action="append",
        default=[],
        help=(
            "Declare one extension manifest for this catalog read without "
            "installing or enabling it. Repeat for multiple manifests."
        ),
    )
    parser.set_defaults(capability_operation_parser=parser)


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
    _add_extension_manifest_argument(list_parser)
    show_parser = capability_sub.add_parser(
        "show",
        help="Show CLI, protocol, smoke, and boundary details for a capability.",
    )
    add_subcommand_format(show_parser)
    show_parser.add_argument(
        "capability_id",
        help="Capability id to inspect.",
    )
    _add_extension_manifest_argument(show_parser)


def handle_capability_command(
    args: argparse.Namespace,
    *,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "capability":
        return None
    manifest_paths = tuple(args.extension_manifest)
    state_file = default_extension_state_file(runtime_root_arg)
    try:
        if args.capability_command == "list":
            payload = build_capability_catalog_packet(
                manifest_paths,
                extension_state_file=state_file,
            )
            renderer = render_capability_catalog_markdown
        elif args.capability_command == "show":
            payload = build_capability_detail_packet(
                args.capability_id,
                manifest_paths,
                extension_state_file=state_file,
            )
            renderer = render_capability_detail_markdown
        else:
            raise ValueError("capability requires `list` or `show`")
    except ValueError as exc:
        args.capability_operation_parser.error(str(exc))
    print_payload(payload, output_format(args), renderer)
    return 0
