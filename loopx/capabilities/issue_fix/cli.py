from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .acceptance_loop import (
    build_issue_fix_acceptance_fixture_packet,
    build_issue_fix_caller_repo_branch_packet,
    build_issue_fix_repo_branch_fixture_packet,
    render_issue_fix_acceptance_loop_markdown,
)
from .workflow_plan import (
    build_issue_fix_workflow_plan_packet,
    render_issue_fix_workflow_plan_markdown,
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
    workflow_parser = issue_fix_sub.add_parser(
        "workflow-plan",
        help=(
            "Plan the full issue-fix workflow from public metadata to ordered "
            "LoopX todos, validation, and PR review packet readiness without writes."
        ),
    )
    add_subcommand_format(workflow_parser)
    workflow_parser.add_argument(
        "--repo",
        default="public_repo_fixture",
        help="Public-safe repository label for the issue metadata.",
    )
    workflow_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata_fixture",
        help="Public-safe issue or PR reference label.",
    )
    workflow_parser.add_argument(
        "--url",
        default=None,
        help="Optional https://github.com/owner/repo/issues/123 or /pull/123 URL.",
    )
    workflow_parser.add_argument(
        "--metadata-json",
        default=None,
        help=(
            "Path to mocked provider JSON metadata, or '-' for stdin. "
            "Body/comment fields stay gated and are not copied."
        ),
    )
    workflow_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help=(
            "Explicitly fetch public GitHub issue/PR metadata with gh api --jq. "
            "Only body-free metadata fields are captured."
        ),
    )
    workflow_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    workflow_parser.add_argument(
        "--repo-path",
        default=None,
        help=(
            "Optional caller-approved local git repository path. Planning keeps "
            "this as a dry-run and never records the path."
        ),
    )
    workflow_parser.add_argument(
        "--base-branch",
        default="main",
        help="Approved local base branch for the eventual issue branch.",
    )
    workflow_parser.add_argument(
        "--issue-branch",
        default=None,
        help="Optional issue branch for the eventual caller-repo execution.",
    )
    workflow_parser.add_argument(
        "--validation-label",
        default="caller-declared validation",
        help="Public-safe validation label stored in the workflow plan.",
    )
    workflow_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the workflow plan.",
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
    caller_branch_parser = issue_fix_sub.add_parser(
        "caller-repo-branch",
        help=(
            "Prepare or execute an explicitly approved local repo issue branch "
            "workflow without external comments, PR creation, or merge."
        ),
    )
    add_subcommand_format(caller_branch_parser)
    caller_branch_parser.add_argument(
        "--repo-path",
        required=True,
        help=(
            "Caller-approved local git repository path. The public artifact records "
            "only a repo label, never this path."
        ),
    )
    caller_branch_parser.add_argument(
        "--repo",
        default="approved_local_repo",
        help="Public-safe repository label when no URL-derived repo is provided.",
    )
    caller_branch_parser.add_argument(
        "--issue-ref",
        default="issue_123_public_metadata",
        help="Public-safe issue or PR reference label.",
    )
    caller_branch_parser.add_argument(
        "--url",
        default=None,
        help="Optional public GitHub issue or PR URL used only for compact metadata.",
    )
    caller_branch_parser.add_argument(
        "--base-branch",
        default="main",
        help="Approved local base branch used when creating a new issue branch.",
    )
    caller_branch_parser.add_argument(
        "--issue-branch",
        default=None,
        help="Optional issue branch to create or claim. Defaults to codex/<issue>-fix.",
    )
    caller_branch_parser.add_argument(
        "--validation-command",
        default=None,
        help="Caller-declared validation command. Required with --execute.",
    )
    caller_branch_parser.add_argument(
        "--validation-label",
        default="caller-declared validation",
        help="Public-safe validation label stored in the artifact instead of raw command text.",
    )
    caller_branch_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Validation timeout in seconds.",
    )
    caller_branch_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually inspect the approved repo, create or claim the issue branch, "
            "and run the caller-declared validation."
        ),
    )
    caller_branch_parser.add_argument(
        "--generated-at",
        default="2026-06-23T00:00:00Z",
        help="Public-safe generated_at timestamp for the artifact.",
    )


def handle_issue_fix_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int:
    try:
        if args.issue_fix_command == "workflow-plan":
            if args.fetch_metadata and args.metadata_json:
                raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
            payload = build_issue_fix_workflow_plan_packet(
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                provider_payload=_load_json_object(args.metadata_json)
                if args.metadata_json
                else None,
                fetch_metadata=args.fetch_metadata,
                fetch_timeout_seconds=args.fetch_timeout_seconds,
                repo_path=args.repo_path,
                base_branch=args.base_branch,
                issue_branch=args.issue_branch,
                validation_label=args.validation_label,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_workflow_plan_markdown
        elif args.issue_fix_command == "acceptance-fixture":
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
        elif args.issue_fix_command == "caller-repo-branch":
            payload = build_issue_fix_caller_repo_branch_packet(
                repo_path=args.repo_path,
                repo=args.repo,
                issue_ref=args.issue_ref,
                url=args.url,
                base_branch=args.base_branch,
                issue_branch=args.issue_branch,
                validation_command=args.validation_command,
                validation_label=args.validation_label,
                execute=args.execute,
                timeout_seconds=args.timeout_seconds,
                generated_at=args.generated_at,
            )
            renderer = render_issue_fix_acceptance_loop_markdown
        else:
            raise ValueError(
                "issue-fix requires `workflow-plan`, `acceptance-fixture`, "
                "`repo-branch-fixture`, or `caller-repo-branch`"
            )
    except Exception as exc:
        payload = {
            "ok": False,
            "mode": "issue-fix",
            "error": str(exc),
        }
        renderer = (
            render_issue_fix_workflow_plan_markdown
            if getattr(args, "issue_fix_command", None) == "workflow-plan"
            else render_issue_fix_acceptance_loop_markdown
        )
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
