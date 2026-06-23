from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..content_ops_surface import (
    build_content_ops_chatview_report_packet,
    build_content_ops_packet_aggregation_packet,
    build_content_ops_preview_packet,
    build_content_ops_private_connector_gate_packet,
    build_content_ops_public_handle_observation_packet,
    render_content_ops_chatview_report_markdown,
    render_content_ops_packet_aggregation_markdown,
    render_content_ops_preview_markdown,
    render_content_ops_private_connector_gate_markdown,
    render_content_ops_public_handle_observation_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _load_json_object(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path_text} must contain a JSON object")
    return payload


def _parse_path_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--api-path-count must use PATH=COUNT")
        path, raw_count = value.split("=", 1)
        counts[path.strip()] = int(raw_count.strip())
    return counts


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
    private_gate_parser = content_ops_sub.add_parser(
        "project-private-connector-gate",
        help="Project an owner gate before private connector metadata intake.",
    )
    add_subcommand_format(private_gate_parser)
    private_gate_parser.add_argument(
        "--connector-id",
        default="chatlog_alpha_chatview",
        help="Stable connector id for the private metadata-only gate.",
    )
    private_gate_parser.add_argument(
        "--connector-name",
        default="chatlog-alpha/chatview",
        help="Human-readable connector name for the owner gate.",
    )
    private_gate_parser.add_argument(
        "--surface",
        default="wechat_private_archive",
        help="Content-ops surface name for this private connector.",
    )
    private_gate_parser.add_argument(
        "--proposed-source-item-id",
        default="source_wechat_metadata_signal_001",
        help="source_item_v0 id to reserve after owner approval.",
    )
    private_gate_parser.add_argument(
        "--source-kind",
        default="wechat_private_connector_metadata",
        help="source_item_v0 source_kind for the metadata-only placeholder.",
    )
    private_gate_parser.add_argument(
        "--owner-label",
        default="WeChat archive owner",
        help="Public-safe owner label to show in the gate packet.",
    )
    private_gate_parser.add_argument(
        "--freshness",
        default="unknown",
        choices=("fresh", "stale", "unknown"),
        help="Freshness value for the metadata-only placeholder.",
    )
    aggregate_parser = content_ops_sub.add_parser(
        "aggregate-packets",
        help=(
            "Aggregate public source_item packets and private owner_gate packets "
            "into a compact content_ops_surface_v0 projection."
        ),
    )
    add_subcommand_format(aggregate_parser)
    aggregate_parser.add_argument(
        "--public-packet-json",
        action="append",
        default=[],
        help=(
            "Path to a content_ops_public_handle_observation_packet_v0 JSON object. "
            "Repeat for multiple public source packets. Use '-' to read stdin."
        ),
    )
    aggregate_parser.add_argument(
        "--private-gate-packet-json",
        action="append",
        default=[],
        help=(
            "Path to a content_ops_private_connector_gate_packet_v0 JSON object. "
            "Repeat for multiple private connector gates."
        ),
    )
    aggregate_parser.add_argument(
        "--surface-id",
        default="content_ops_connector_packet_aggregation",
        help="Stable surface_id for the generated content_ops_surface_v0.",
    )
    aggregate_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the aggregate surface.",
    )
    chatview_parser = content_ops_sub.add_parser(
        "project-chatview-report",
        help=(
            "Project a public-safe ChatView operator card as an "
            "aggregation-compatible private connector gate packet."
        ),
    )
    add_subcommand_format(chatview_parser)
    chatview_parser.add_argument(
        "--channel-count",
        type=int,
        required=True,
        help="Compact channel collection count from the approved ChatView trial.",
    )
    chatview_parser.add_argument(
        "--recent-record-count",
        type=int,
        required=True,
        help="Compact recent record count from the approved ChatView trial.",
    )
    chatview_parser.add_argument(
        "--report-count",
        type=int,
        required=True,
        help="Compact report collection count from the approved ChatView trial.",
    )
    chatview_parser.add_argument(
        "--api-request-count",
        type=int,
        required=True,
        help="Total API request count observed during the approved ChatView trial.",
    )
    chatview_parser.add_argument(
        "--api-path-count",
        action="append",
        default=[],
        help="Normalized ChatView API path class count as PATH=COUNT. Repeatable.",
    )
    chatview_parser.add_argument(
        "--connector-url",
        default="https://chatview.zaynjarvis.com/",
        help="Approved ChatView connector URL; must be public https.",
    )
    chatview_parser.add_argument(
        "--source-item-id",
        default="source_chatview_metadata_signal_001",
        help="source_item_v0 id to reserve for the compact ChatView signal.",
    )
    chatview_parser.add_argument(
        "--owner-label",
        default="ChatView owner",
        help="Public-safe owner label to show in the gate packet.",
    )
    chatview_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the ChatView report.",
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
        elif args.content_ops_command == "project-private-connector-gate":
            payload = build_content_ops_private_connector_gate_packet(
                connector_id=args.connector_id,
                connector_name=args.connector_name,
                surface=args.surface,
                proposed_source_item_id=args.proposed_source_item_id,
                source_kind=args.source_kind,
                owner_label=args.owner_label,
                freshness=args.freshness,
            )
            renderer = render_content_ops_private_connector_gate_markdown
        elif args.content_ops_command == "aggregate-packets":
            payload = build_content_ops_packet_aggregation_packet(
                public_handle_packets=[
                    _load_json_object(path) for path in args.public_packet_json
                ],
                private_connector_gate_packets=[
                    _load_json_object(path) for path in args.private_gate_packet_json
                ],
                surface_id=args.surface_id,
                generated_at=args.generated_at,
            )
            renderer = render_content_ops_packet_aggregation_markdown
        elif args.content_ops_command == "project-chatview-report":
            payload = build_content_ops_chatview_report_packet(
                channel_count=args.channel_count,
                recent_record_count=args.recent_record_count,
                report_count=args.report_count,
                api_request_count=args.api_request_count,
                api_path_counts=_parse_path_counts(args.api_path_count),
                connector_url=args.connector_url,
                source_item_id=args.source_item_id,
                owner_label=args.owner_label,
                generated_at=args.generated_at,
            )
            renderer = render_content_ops_chatview_report_markdown
        else:
            raise ValueError(
                "content-ops requires `preview`, `observe-public-handle`, "
                "`project-private-connector-gate`, `aggregate-packets`, or "
                "`project-chatview-report`"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "content-ops",
            "error": str(exc),
        }
        renderer = render_content_ops_private_connector_gate_markdown
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
