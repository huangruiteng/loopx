from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .pr_gate_reconcile import (
    reconcile_acknowledged_issue_fix_pr_reviews,
    reconcile_issue_fix_pr_gate,
    reconcile_issue_fix_pr_review,
    render_issue_fix_pr_gate_reconciliation_markdown,
    render_issue_fix_pr_review_reconciliation_markdown,
)
from .pr_review_ack import (
    find_issue_fix_pr_review_ack_receipt,
    record_issue_fix_pr_review_ack,
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
    review_parser = issue_fix_sub.add_parser(
        "pr-review-reconcile",
        help=(
            "Complete one exact nonblocking PR review user_action only after "
            "owner acknowledgement and a compact terminal PR observation."
        ),
    )
    review_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand.",
    )
    review_parser.add_argument(
        "--url",
        required=True,
        help="Public https://github.com/owner/repo/pull/123 URL.",
    )
    review_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal containing the nonblocking PR review action.",
    )
    review_parser.add_argument(
        "--todo-id",
        required=True,
        help="Exact task_class=user_action todo id acknowledged by the owner.",
    )
    review_parser.add_argument(
        "--agent-id",
        required=True,
        help=(
            "Registered lifecycle actor; must match bound_agent when the "
            "user_action is agent-bound."
        ),
    )
    review_parser.add_argument(
        "--project",
        default=".",
        help="Project root containing the goal state.",
    )
    review_parser.add_argument(
        "--metadata-json",
        default=None,
        help="Path to mocked compact gh pr view JSON metadata, or '-' for stdin.",
    )
    review_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help="Explicitly fetch compact public PR state with gh pr view.",
    )
    review_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for --fetch-metadata.",
    )
    review_parser.add_argument(
        "--owner-acknowledged",
        action="store_true",
        help=(
            "Assert that the owner explicitly acknowledged this exact review "
            "action as complete. Terminal PR state alone is insufficient."
        ),
    )
    review_parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Complete the exact user_action only when owner acknowledgement and "
            "terminal PR state are both present."
        ),
    )
    review_parser.add_argument(
        "--generated-at",
        default=None,
        help="Public-safe reconciliation timestamp; defaults to current UTC.",
    )
    acked_parser = issue_fix_sub.add_parser(
        "pr-review-reconcile-acked",
        help=(
            "Reconcile current PR review user_actions from persisted exact "
            "owner acknowledgement bindings."
        ),
    )
    acked_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand.",
    )
    acked_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal whose persisted review acknowledgement receipts are read.",
    )
    acked_parser.add_argument(
        "--agent-id",
        required=True,
        help="Registered lifecycle actor bound by each acknowledgement receipt.",
    )
    acked_parser.add_argument(
        "--project",
        default=None,
        help="Optional project root; defaults to the registry-declared project.",
    )
    acked_parser.add_argument(
        "--fetch-metadata",
        action="store_true",
        help="Fetch compact public PR state for each current matching receipt.",
    )
    acked_parser.add_argument(
        "--fetch-timeout-seconds",
        type=int,
        default=10,
        help="Timeout for each compact public PR metadata fetch.",
    )
    acked_parser.add_argument(
        "--execute",
        action="store_true",
        help="Complete exact acknowledged review actions whose PR is terminal.",
    )
    acked_parser.add_argument(
        "--generated-at",
        default=None,
        help="Public-safe reconciliation timestamp; defaults to current UTC.",
    )
    ack_parser = issue_fix_sub.add_parser(
        "pr-review-ack",
        help=(
            "Persist one typed owner acknowledgement receipt with an exact "
            "goal/todo/agent/GitHub PR binding for later reconciliation."
        ),
    )
    ack_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand.",
    )
    ack_parser.add_argument(
        "--url",
        required=True,
        help="Public https://github.com/owner/repo/pull/123 URL.",
    )
    ack_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal containing the nonblocking PR review action.",
    )
    ack_parser.add_argument(
        "--todo-id",
        required=True,
        help="Exact task_class=user_action todo id acknowledged by the owner.",
    )
    ack_parser.add_argument(
        "--agent-id",
        required=True,
        help="Registered lifecycle actor matching the user_action bound_agent.",
    )
    ack_parser.add_argument(
        "--project",
        default=".",
        help="Project root containing the goal state.",
    )
    ack_parser.add_argument(
        "--owner-acknowledged",
        action="store_true",
        help="Assert that the owner explicitly acknowledged this exact review.",
    )
    ack_parser.add_argument(
        "--generated-at",
        default=None,
        help="Public-safe acknowledgement timestamp; defaults to current UTC.",
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


def build_pr_review_reconciliation_from_args(
    args: argparse.Namespace,
    registry_path: Path | None,
    runtime_root_arg: str | None,
    generated_at: str,
) -> dict[str, Any]:
    if registry_path is None:
        raise ValueError("pr-review-reconcile requires a LoopX registry")
    if args.fetch_metadata and args.metadata_json:
        raise ValueError("--fetch-metadata cannot be combined with --metadata-json")
    ack_receipt = None
    if args.owner_acknowledged:
        acknowledgement = record_issue_fix_pr_review_ack(
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            goal_id=args.goal_id,
            todo_id=args.todo_id,
            agent_id=args.agent_id,
            project=Path(args.project).expanduser(),
            url=args.url,
            owner_acknowledged=True,
            generated_at=generated_at,
        )
        ack_receipt = acknowledgement["ack_receipt"]
    else:
        ack_receipt = find_issue_fix_pr_review_ack_receipt(
            registry_path=registry_path,
            runtime_root_arg=runtime_root_arg,
            goal_id=args.goal_id,
            todo_id=args.todo_id,
            agent_id=args.agent_id,
            url=args.url,
        )
    return reconcile_issue_fix_pr_review(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=args.goal_id,
        todo_id=args.todo_id,
        agent_id=args.agent_id,
        project=Path(args.project).expanduser(),
        url=args.url,
        ack_receipt=ack_receipt,
        provider_payload=(
            _load_json_object(args.metadata_json) if args.metadata_json else None
        ),
        fetch_metadata=args.fetch_metadata,
        fetch_timeout_seconds=args.fetch_timeout_seconds,
        execute=args.execute,
        generated_at=generated_at,
    )


def build_acked_pr_review_reconciliation_from_args(
    args: argparse.Namespace,
    registry_path: Path | None,
    runtime_root_arg: str | None,
    generated_at: str,
) -> dict[str, Any]:
    if registry_path is None:
        raise ValueError("pr-review-reconcile-acked requires a LoopX registry")
    return reconcile_acknowledged_issue_fix_pr_reviews(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        project=Path(args.project).expanduser() if args.project else None,
        fetch_metadata=args.fetch_metadata,
        fetch_timeout_seconds=args.fetch_timeout_seconds,
        execute=args.execute,
        generated_at=generated_at,
    )


def build_pr_review_ack_from_args(
    args: argparse.Namespace,
    registry_path: Path | None,
    runtime_root_arg: str | None,
    generated_at: str,
) -> dict[str, Any]:
    if registry_path is None:
        raise ValueError("pr-review-ack requires a LoopX registry")
    return record_issue_fix_pr_review_ack(
        registry_path=registry_path,
        runtime_root_arg=runtime_root_arg,
        goal_id=args.goal_id,
        todo_id=args.todo_id,
        agent_id=args.agent_id,
        project=Path(args.project).expanduser(),
        url=args.url,
        owner_acknowledged=args.owner_acknowledged,
        generated_at=generated_at,
    )


def render_issue_fix_pr_review_ack_markdown(payload: dict[str, Any]) -> str:
    binding = (
        payload.get("binding")
        if isinstance(payload.get("binding"), dict)
        else {}
    )
    receipt = (
        payload.get("ack_receipt")
        if isinstance(payload.get("ack_receipt"), dict)
        else {}
    )
    return "\n".join(
        [
            "# LoopX Issue Fix PR Review Acknowledgement",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- todo_id: `{payload.get('todo_id')}`",
            f"- pr: `{binding.get('pr_ref')}`",
            f"- receipt_id: `{receipt.get('receipt_id')}`",
            f"- write_performed: `{payload.get('write_performed')}`",
            f"- replayed: `{payload.get('replayed')}`",
        ]
    )


def render_issue_fix_acked_pr_review_reconciliation_markdown(
    payload: dict[str, Any],
) -> str:
    return "\n".join(
        [
            "# LoopX Acknowledged PR Review Reconciliation",
            "",
            f"- ok: `{payload.get('ok')}`",
            f"- degraded: `{payload.get('degraded')}`",
            f"- ack_receipt_count: `{payload.get('ack_receipt_count')}`",
            f"- result_count: `{payload.get('result_count')}`",
            f"- terminal_count: `{payload.get('terminal_count')}`",
            f"- reconciled_count: `{payload.get('reconciled_count')}`",
            f"- already_reconciled_count: `{payload.get('already_reconciled_count')}`",
            f"- external_read_count: `{payload.get('external_read_count')}`",
            f"- failure_count: `{payload.get('failure_count')}`",
            "- quota_spend_required: `False`",
        ]
    )


__all__ = [
    "build_acked_pr_review_reconciliation_from_args",
    "build_pr_gate_reconciliation_from_args",
    "build_pr_review_ack_from_args",
    "build_pr_review_reconciliation_from_args",
    "register_pr_gate_reconciliation_command",
    "render_issue_fix_acked_pr_review_reconciliation_markdown",
    "render_issue_fix_pr_gate_reconciliation_markdown",
    "render_issue_fix_pr_review_ack_markdown",
    "render_issue_fix_pr_review_reconciliation_markdown",
]
