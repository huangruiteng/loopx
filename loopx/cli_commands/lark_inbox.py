from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

from ..capabilities.lark.event_inbox import (
    acknowledge_lark_event_inbox,
    ingest_lark_event_inbox,
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
    ingest = sub.add_parser(
        "ingest",
        help=(
            "Persist canonical compact events from stdin JSON/NDJSON for host "
            "collection or bounded history reconciliation."
        ),
    )
    add_subcommand_format(ingest)
    ingest.add_argument("--project", default=".")
    ingest.add_argument("--config", required=True)
    ingest.add_argument("--execute", action="store_true")


def _read_stdin_events() -> list[object]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError("lark inbox ingest requires JSON or NDJSON on stdin")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("lark inbox ingest input must be an event object or event array")


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
        elif args.lark_inbox_command == "ack":
            payload = acknowledge_lark_event_inbox(
                project=args.project,
                config_path=args.config,
                message_ids=args.message_id,
                execute=args.execute,
            )
        else:
            payload = ingest_lark_event_inbox(
                project=args.project,
                config_path=args.config,
                events=_read_stdin_events(),
                execute=args.execute,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "ok": False,
            "schema_version": "lark_event_inbox_error_v0",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), _render)
    return 0 if payload.get("ok") else 1
