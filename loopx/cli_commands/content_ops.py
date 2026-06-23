from __future__ import annotations

import argparse
from collections.abc import Callable

from ..content_ops_surface import (
    build_content_ops_preview_packet,
    build_content_ops_public_handle_observation_packet,
    render_content_ops_preview_markdown,
    render_content_ops_public_handle_observation_markdown,
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
    observe_parser = content_ops_sub.add_parser(
        "observe-public-handle",
        help="Observe a public platform handle as metadata-only source_item_v0.",
    )
    add_subcommand_format(observe_parser)
    observe_parser.add_argument(
        "--url",
        required=True,
        help="Public https handle URL to observe with a HEAD-only metadata check.",
    )
    observe_parser.add_argument(
        "--source-item-id",
        required=True,
        help="Stable source_item_v0 id to assign to the compact observation.",
    )
    observe_parser.add_argument(
        "--surface",
        default="x_public_feed",
        help="Content-ops surface name for this observation.",
    )
    observe_parser.add_argument(
        "--source-kind",
        default="x_public_profile_handle",
        help="source_item_v0 source_kind to write into the compact record.",
    )
    observe_parser.add_argument(
        "--freshness",
        default="fresh",
        choices=("fresh", "stale", "unknown"),
        help="Freshness value for the generated source_item_v0.",
    )
    observe_parser.add_argument(
        "--terms-note",
        default=None,
        help="Optional public-safe terms/source-boundary note.",
    )
    observe_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Timeout for the HEAD-only metadata check.",
    )
    observe_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Build the metadata-only packet without any external read.",
    )


def handle_content_ops_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.content_ops_command == "preview":
            payload = build_content_ops_preview_packet(generated_at=args.generated_at)
            renderer = render_content_ops_preview_markdown
        elif args.content_ops_command == "observe-public-handle":
            payload = build_content_ops_public_handle_observation_packet(
                url=args.url,
                source_item_id=args.source_item_id,
                surface=args.surface,
                source_kind=args.source_kind,
                freshness=args.freshness,
                terms_note=args.terms_note,
                timeout_seconds=args.timeout_seconds,
                fetch=not args.no_fetch,
            )
            renderer = render_content_ops_public_handle_observation_markdown
        else:
            raise ValueError(
                "content-ops requires `preview` or `observe-public-handle`"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "content-ops",
            "error": str(exc),
        }
        renderer = render_content_ops_public_handle_observation_markdown
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
