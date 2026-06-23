from __future__ import annotations

import argparse
from collections.abc import Callable

from ..issue_fix_acceptance_loop import (
    build_issue_fix_acceptance_fixture_packet,
    build_issue_fix_repo_branch_fixture_packet,
    render_issue_fix_acceptance_loop_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_issue_fix_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    issue_fix_parser = subparsers.add_parser(
        "issue-fix",
        help="Run public-safe issue fix acceptance loops.",
    )
    issue_fix_sub = issue_fix_parser.add_subparsers(
        dest="issue_fix_command",
        required=True,
    )
    acceptance_parser = issue_fix_sub.add_parser(
        "acceptance-fixture",
        help=(
            "Run a deterministic fix loop: failing repro, minimal patch, "
            "focused validation, and PR-review-ready artifact."
        ),
    )
    add_subcommand_format(acceptance_parser)
    acceptance_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata fixture.",
    )
    acceptance_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the fixture.",
    )
    acceptance_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL for metadata parsing.",
    )
    acceptance_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the fixture artifact.",
    )
    branch_parser = issue_fix_sub.add_parser(
        "repo-branch-fixture",
        help=(
            "Run the fix loop through a temporary git repo issue branch: "
            "branch, repro, patch, validation, and PR evidence."
        ),
    )
    add_subcommand_format(branch_parser)
    branch_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata fixture.",
    )
    branch_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label for the fixture.",
    )
    branch_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL for metadata parsing.",
    )
    branch_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the fixture artifact.",
    )


def handle_issue_fix_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.issue_fix_command == "acceptance-fixture":
            payload = build_issue_fix_acceptance_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        elif args.issue_fix_command == "repo-branch-fixture":
            payload = build_issue_fix_repo_branch_fixture_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        else:
            raise ValueError("issue-fix requires `acceptance-fixture` or `repo-branch-fixture`")
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "issue-fix",
            "error": str(exc),
        }
        renderer = render_issue_fix_acceptance_loop_markdown
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
