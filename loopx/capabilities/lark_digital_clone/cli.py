from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from .scan import (
    DEFAULT_CLI_BIN,
    DEFAULT_OUT_DIR,
    DEFAULT_STYLE,
    render_lark_digital_clone_scan_markdown,
    run_lark_digital_clone_scan,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_lark_digital_clone_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "lark-digital-clone",
        help="Scan Lark messages into reviewed reply drafts and LoopX-style artifacts.",
    )
    sub = parser.add_subparsers(dest="lark_digital_clone_command", required=True)

    scan = sub.add_parser(
        "scan",
        help="Read or preview Lark message sources and generate local digital-clone artifacts.",
    )
    add_subcommand_format(scan)
    scan.add_argument("--at-me", action="store_true", help="Scan messages that mention the current user.")
    scan.add_argument("--since", default="24h", help="Lookback window such as 24h or 7d.")
    scan.add_argument("--chat-keyword", action="append", default=[], help="Resolve a group by keyword. Repeatable.")
    scan.add_argument("--chat-id", action="append", default=[], help="Scan a known oc_ chat id. Repeatable.")
    scan.add_argument("--page-limit", type=int, default=2, help="Max pages per lark-cli message search.")
    scan.add_argument("--page-size", type=int, default=20, help="Page size per lark-cli message search.")
    scan.add_argument("--style", default=DEFAULT_STYLE, help="Reply draft style hint.")
    scan.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Local artifact directory.")
    scan.add_argument(
        "--fixture-json",
        action="append",
        default=[],
        help="Synthetic or exported message JSON to process without Lark reads. Repeatable.",
    )
    scan.add_argument(
        "--execute-read",
        action="store_true",
        help="Actually read Lark messages. Without this, Lark calls are dry-run previews.",
    )
    scan.add_argument("--skip-auth-check", action="store_true", help="Skip lark-cli auth status check.")
    scan.add_argument("--cli-bin", default=DEFAULT_CLI_BIN, help="lark-cli executable path.")


def handle_lark_digital_clone_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: FormatSelector,
) -> int | None:
    if args.command != "lark-digital-clone":
        return None
    fmt = output_format(args)
    try:
        if args.lark_digital_clone_command == "scan":
            payload = run_lark_digital_clone_scan(
                at_me=bool(args.at_me),
                since=args.since,
                out_dir=Path(args.out_dir).expanduser(),
                chat_keywords=args.chat_keyword,
                chat_ids=args.chat_id,
                page_limit=args.page_limit,
                page_size=args.page_size,
                style=args.style,
                fixture_json=args.fixture_json,
                execute_read=bool(args.execute_read),
                skip_auth_check=bool(args.skip_auth_check),
                cli_bin=args.cli_bin,
            )
        else:
            raise ValueError(f"unknown lark-digital-clone command: {args.lark_digital_clone_command}")
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_lark_digital_clone_error_v0",
            "error": str(exc),
        }
    print_payload(payload, fmt, render_lark_digital_clone_scan_markdown)
    return 0 if payload.get("ok") else 1
