from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..summary_all import build_summary_all, render_summary_all_markdown


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _scan_roots(args: argparse.Namespace) -> list[Path]:
    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    return scan_roots or [Path(args.scan_root).expanduser()]


def register_summary_all_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "global-summary",
        help="Read a public-safe /loopx-global-summary progress digest across visible LoopX goals.",
    )
    add_subcommand_format(parser)
    parser.add_argument("--agent-id", help="Registered agent id for agent-lane quota projection.")
    parser.add_argument("--time-range", default="24h", help="Recent progress window, e.g. 24h or 7d.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum items per digest section.")
    parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )


def handle_summary_all_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "global-summary":
        return None
    try:
        payload = build_summary_all(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            agent_id=args.agent_id,
            time_range=args.time_range,
            limit=max(1, args.limit),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "global_manager_command_response_v0",
            "request": {
                "schema_version": "global_manager_command_request_v0",
                "command": "/loopx-global-summary",
                "legacy_aliases": ["/loop-global-summary"],
                "privacy_mode": "public_safe_summary",
                "dry_run": True,
            },
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_summary_all_markdown)
    return 0 if payload.get("ok") else 1
