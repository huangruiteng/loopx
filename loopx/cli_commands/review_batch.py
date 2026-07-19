from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..control_plane.handoff.review_batch import (
    bind_review_batch_decisions,
    build_review_batch,
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


def register_review_batch_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "review-batch",
        help="Compose provider-neutral bounded review batches and bind exact decisions.",
    )
    commands = parser.add_subparsers(dest="review_batch_command", required=True)
    compose = commands.add_parser(
        "compose",
        help="Compose a deterministic review_batch_v0 packet from typed candidate sources.",
    )
    add_subcommand_format(compose)
    compose.add_argument(
        "--request-json",
        required=True,
        help="Path to a review_batch_request_v0 object; use '-' for stdin.",
    )
    bind = commands.add_parser(
        "bind-decisions",
        help="Bind maintainer decisions to exact batch and candidate digests without effects.",
    )
    add_subcommand_format(bind)
    bind.add_argument("--batch-json", required=True, help="Path to review_batch_v0 JSON.")
    bind.add_argument(
        "--decisions-json",
        required=True,
        help="Path to review_batch_decisions_v0 JSON.",
    )


def _render_candidate(candidate: dict[str, Any]) -> list[str]:
    reasons = candidate.get("priority_reasons")
    reason_text = ", ".join(
        str(item.get("code")) for item in reasons or [] if isinstance(item, dict)
    )
    proposal = candidate.get("proposal") if isinstance(candidate.get("proposal"), dict) else {}
    action = proposal.get("action") or proposal.get("draft") or "n/a"
    return [
        f"### {candidate.get('candidate_id')}: {candidate.get('title')}",
        "",
        f"- priority: tier {candidate.get('priority_tier')} ({reason_text})",
        f"- evidence: `{candidate.get('evidence_status')}`",
        f"- proposed: {action}",
        f"- decision_digest: `{candidate.get('decision_digest')}`",
        "",
    ]


def render_review_batch_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# Review Batch Error\n\n- error: {payload.get('error')}\n"
    lines = [
        f"# Review Batch `{payload.get('batch_id')}`",
        "",
        f"- schema: `{payload.get('schema_version')}`",
        f"- decision_digest: `{payload.get('decision_digest')}`",
        f"- candidate_counts: `{json.dumps(payload.get('candidate_counts'), ensure_ascii=False, sort_keys=True)}`",
        "",
    ]
    for candidate in payload.get("candidates") or []:
        if isinstance(candidate, dict):
            lines.extend(_render_candidate(candidate))
    return "\n".join(lines).rstrip() + "\n"


def render_review_batch_decision_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        return f"# Review Batch Decision Error\n\n- error: {payload.get('error')}\n"
    lines = [
        f"# Review Batch Decisions `{payload.get('batch_id')}`",
        "",
        f"- receipt_id: `{payload.get('receipt_id')}`",
        f"- decision_digest: `{payload.get('decision_digest')}`",
        "",
    ]
    for decision in payload.get("decisions") or []:
        if isinstance(decision, dict):
            lines.append(
                f"- `{decision.get('candidate_id')}`: `{decision.get('decision')}` "
                f"(`{decision.get('candidate_decision_digest')}`)"
            )
    return "\n".join(lines).rstrip() + "\n"


def handle_review_batch_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "review-batch":
        return None
    renderer = render_review_batch_markdown
    try:
        if args.review_batch_command == "compose":
            payload = build_review_batch(_load_json_object(args.request_json))
        else:
            payload = bind_review_batch_decisions(
                _load_json_object(args.batch_json),
                _load_json_object(args.decisions_json),
            )
            renderer = render_review_batch_decision_markdown
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "review_batch_error_v0",
            "command": args.review_batch_command,
            "error": str(exc),
        }
    print_payload(payload, output_format(args), renderer)
    return 0 if payload.get("ok") else 1
