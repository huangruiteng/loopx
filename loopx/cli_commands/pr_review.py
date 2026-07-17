from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..pr_review import (
    build_pr_review_packet,
    scan_github_pull_requests,
    load_pr_fixture,
    normalize_pr_state_filter,
    render_pr_review_markdown,
    resolve_current_github_repository,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def register_pr_review_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "pr-review",
        help="Build a public-safe /loopx-pr-review queue for the current project's open and merged pull requests.",
    )
    add_subcommand_format(parser)
    parser.add_argument(
        "--repo",
        help="GitHub owner/repo to review. Defaults to the current project's gh repository context.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum PRs to include per selected lifecycle group.",
    )
    parser.add_argument(
        "--state",
        choices=("open", "merged", "all"),
        default="all",
        help="PR lifecycle state to include. Defaults to all so merged PRs remain reviewable.",
    )
    parser.add_argument(
        "--since",
        help="Only include PRs active since this ISO timestamp or YYYY-MM-DD date.",
    )
    parser.add_argument(
        "--fixture",
        help="Read public-safe PR metadata from a JSON fixture instead of live gh output.",
    )


def handle_pr_review_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "pr-review":
        return None
    try:
        repository = args.repo
        source = "github_cli"
        if args.fixture:
            repository_from_fixture, pull_requests = load_pr_fixture(Path(args.fixture).expanduser())
            repository = repository or repository_from_fixture
            source = "fixture"
            source_scan = None
        else:
            repository = repository or resolve_current_github_repository()
            source_scan = scan_github_pull_requests(
                repo=repository,
                limit=max(1, args.limit) + 1,
                state_filter=normalize_pr_state_filter(args.state),
                since=args.since,
            )
            pull_requests = source_scan["pull_requests"]
        payload = build_pr_review_packet(
            pull_requests=pull_requests,
            repository=repository,
            limit=max(1, args.limit),
            source=source,
            state_filter=normalize_pr_state_filter(args.state),
            since=args.since,
            source_scan=source_scan,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_pr_review_command_response_v0",
            "request": {
                "schema_version": "loopx_pr_review_command_request_v0",
                "command": "/loopx-pr-review",
                "cli_command": "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]",
                "repository": args.repo,
                "limit": max(1, args.limit),
                "state_filter": normalize_pr_state_filter(args.state),
                "since": args.since,
                "source": "fixture" if args.fixture else "github_cli",
                "privacy_mode": "public_safe_github_metadata",
                "dry_run": True,
            },
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_pr_review_markdown)
    return 0 if payload.get("ok") else 1
