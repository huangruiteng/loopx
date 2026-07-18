from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .pr_gate_reconcile import (
    reconcile_issue_fix_pr_gate,
    render_issue_fix_pr_gate_reconciliation_markdown,
)


def register_pr_gate_reconciliation_command(
    issue_fix_sub: argparse._SubParsersAction,
) -> None:
    parser = issue_fix_sub.add_parser(
        "pr-gate-reconcile",
        help=(
            "Reconcile a merge-scoped user gate against compact public PR "
            "lifecycle state before notifying the owner."
        ),
    )
    parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Public https://github.com/owner/repo/pull/123 URL.",
    )
    parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal containing the merge-scoped user gate.",
    )
    parser.add_argument(
        "--todo-id",
        required=True,
        help="User gate todo id whose decision_scope is merge_pr_<number>.",
    )
    parser.add_argument(
        "--agent-id",
        default=None,
        help=(
            "Registered lifecycle actor completing an unlinked merge gate in "
            "a multi-agent goal. Exactly linked user gates retain the typed "
            "controller override."
        ),
    )
    parser.add_argument(
        "--project",
        default=".",
        help="Project root containing the goal state.",
    )
    parser.add_argument(
        "--metadata-json",
        default=None,
        help="Path to mocked compact gh pr view JSON metadata, or '-' for stdin.",
    )
    parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help="Explicitly fetch compact public PR state with gh pr view.",
    )
    parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Complete the obsolete gate only when the observed PR is terminal.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Public-safe reconciliation timestamp; defaults to current UTC.",
    )


def _load_json_object(input_text: str) -> dict[str, Any]:
    if input_text == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(input_text).expanduser().read_text(encoding="utf-8")
    if len(raw) > 1_048_576:
        raise ValueError("PR metadata JSON exceeds the 1 MiB limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("PR metadata JSON is invalid") from None
    if not isinstance(payload, dict):
        raise ValueError("PR metadata JSON must contain an object")
    return payload


def build_pr_gate_reconciliation_from_args(
    args: argparse.Namespace,
    registry_path: Path | None,
    runtime_root_arg: str | None,
    generated_at: str,
) -> dict[str, Any]:
    if registry_path is None:
        raise ValueError("pr-gate-reconcile requires a LoopX registry")
    if args.fetch_metadata and args.metadata_json:
        raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
    return reconcile_issue_fix_pr_gate(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=args.goal_id,
        todo_id=args.todo_id,
        agent_id=args.agent_id,
        project=Path(args.project).expanduser(),
        url=args.url,
        provider_payload=(
            _load_json_object(args.metadata_json) if args.metadata_json else None
        ),
        fetch_metadata=args.fetch_metadata,
        fetch_timeout_seconds=args.fetch_timeout_seconds,
        execute=args.execute,
        generated_at=generated_at,
    )


__all__ = [
    "build_pr_gate_reconciliation_from_args",
    "register_pr_gate_reconciliation_command",
    "render_issue_fix_pr_gate_reconciliation_markdown",
]
