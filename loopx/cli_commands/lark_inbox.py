from __future__ import annotations

import argparse
from typing import Callable

from ..capabilities.lark.event_inbox import (
    acknowledge_lark_event_inbox,
    inspect_lark_event_inbox,
)


def register_lark_inbox_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "lark-inbox",
        help="Inspect and acknowledge a host-collected local Lark event inbox.",
    )
    sub = parser.add_subparsers(dest="lark_inbox_command", required=True)
    drain = sub.add_parser(
        "drain",
        help="Return bounded unprocessed local-private events without acknowledging them.",
    )
    add_subcommand_format(drain)
    drain.add_argument("--project", default=".")
    drain.add_argument("--config", required=True)
    drain.add_argument("--limit", type=int, default=20)
    ack = sub.add_parser(
        "ack",
        help="Acknowledge events only after their actionable feedback is written back.",
    )
    add_subcommand_format(ack)
    ack.add_argument("--project", default=".")
    ack.add_argument("--config", required=True)
    ack.add_argument("--message-id", action="append", required=True)
    ack.add_argument("--execute", action="store_true")


def _render(payload: dict[str, object]) -> str:
    lines = [
        "# Lark Event Inbox",
        "",
        f"- ok: {payload.get('ok')}",
        f"- enabled: {payload.get('enabled')}",
        f"- pending_count: {payload.get('pending_count')}",
        f"- write_performed: {payload.get('write_performed')}",
    ]
    for item in payload.get("items") or []:
        if isinstance(item, dict):
            lines.append(f"- {item.get('message_id')}: {item.get('content')}")
    return "\n".join(lines).rstrip() + "\n"


def handle_lark_inbox_command(
    args: argparse.Namespace,
    *,
    output_format: Callable[..., str],
    print_payload: Callable,
) -> int | None:
    if args.command != "lark-inbox":
        return None
    try:
        if args.lark_inbox_command == "drain":
            payload = inspect_lark_event_inbox(
                project=args.project,
                config_path=args.config,
                limit=args.limit,
            )
        else:
            payload = acknowledge_lark_event_inbox(
                project=args.project,
                config_path=args.config,
                message_ids=args.message_id,
                execute=args.execute,
            )
    except (OSError, ValueError) as exc:
        payload = {
            "ok": False,
            "schema_version": "lark_event_inbox_error_v0",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), _render)
    return 0 if payload.get("ok") else 1
