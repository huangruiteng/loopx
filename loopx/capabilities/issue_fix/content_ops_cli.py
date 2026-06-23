from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .intake_surface import (
    build_content_ops_issue_fix_intake_packet,
    build_content_ops_issue_fix_metadata_preview_packet,
    render_content_ops_issue_fix_intake_markdown,
    render_content_ops_issue_fix_metadata_preview_markdown,
)


Renderer = Callable[[dict[str, object]], str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _load_json_object(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        payload = json.loads(sys.stdin.read())
    else:
        payload = json.loads(Path(path_text).expanduser().read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path_text} must contain a JSON object")
    return payload


def register_content_ops_issue_fix_commands(
    content_ops_subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    issue_fix_parser = content_ops_subparsers.add_parser(
        "issue-fix-intake",
        help=(
            "Build a fixture-only issue_fix_intake_v0 packet from public "
            "GitHub issue/PR metadata."
        ),
    )
    add_subcommand_format(issue_fix_parser)
    issue_fix_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the metadata fixture.",
    )
    issue_fix_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the metadata fixture.",
    )
    issue_fix_parser.add_argument(
        "--issue-state",
        default="open",
        choices=("open", "closed", "unknown"),
        help="Public issue state to project into the fixture.",
    )
    issue_fix_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the issue-fix intake.",
    )

    issue_fix_metadata_parser = content_ops_subparsers.add_parser(
        "issue-fix-metadata-preview",
        help=(
            "Preview public GitHub issue/PR metadata intake with mocked provider "
            "data and gated body/comment fields."
        ),
    )
    add_subcommand_format(issue_fix_metadata_parser)
    issue_fix_metadata_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the metadata preview.",
    )
    issue_fix_metadata_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the metadata preview.",
    )
    issue_fix_metadata_parser.add_argument(
        "--url",
        default=None,
        help="Optional https://github.com/owner/repo/issues/123 or /pull/123 URL.",
    )
    issue_fix_metadata_parser.add_argument(
        "--metadata-json",
        default=None,
        help=(
            "Path to mocked provider JSON metadata, or '-' for stdin. "
            "Body/comment fields stay gated and are not copied."
        ),
    )
    issue_fix_metadata_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help=(
            "Explicitly fetch public GitHub issue/PR metadata with gh api --jq. "
            "Only body-free metadata fields are captured."
        ),
    )
    issue_fix_metadata_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    issue_fix_metadata_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the metadata preview.",
    )


def handle_content_ops_issue_fix_command(
    args: argparse.Namespace,
) -> tuple[dict[str, object], Renderer] | None:
    if args.content_ops_command == "issue-fix-intake":
        return (
            build_content_ops_issue_fix_intake_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                issue_state=args.issue_state,
                generated_at=args.generated_at,
            ),
            render_content_ops_issue_fix_intake_markdown,
        )
    if args.content_ops_command == "issue-fix-metadata-preview":
        if args.fetch_metadata and args.metadata_json:
            raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
        return (
            build_content_ops_issue_fix_metadata_preview_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                provider_payload=_load_json_object(args.metadata_json)
                if args.metadata_json
                else None,
                fetch_metadata=args.fetch_metadata,
                fetch_timeout_seconds=args.fetch_timeout_seconds,
                generated_at=args.generated_at,
            ),
            render_content_ops_issue_fix_metadata_preview_markdown,
        )
    return None
