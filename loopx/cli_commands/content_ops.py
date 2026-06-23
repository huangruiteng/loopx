from __future__ import annotations

import argparse
from collections.abc import Callable

from ..content_ops_surface import (
    build_content_ops_preview_packet,
    render_content_ops_preview_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_content_ops_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    content_ops_parser = subparsers.add_parser(
        "content-ops",
        help="Render public-safe creator/content operations preview packets.",
    )
    content_ops_sub = content_ops_parser.add_subparsers(
        dest="content_ops_command",
        required=True,
    )
    preview_parser = content_ops_sub.add_parser(
        "preview",
        help="Preview metadata-only connector trials and content-ops projection.",
    )
    add_subcommand_format(preview_parser)
    preview_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the synthetic preview fixture.",
    )


def handle_content_ops_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.content_ops_command != "preview":
            raise ValueError("content-ops requires the `preview` subcommand")
        payload = build_content_ops_preview_packet(generated_at=args.generated_at)
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "content-ops",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_content_ops_preview_markdown)
    return 0 if payload.get("ok") else 1
