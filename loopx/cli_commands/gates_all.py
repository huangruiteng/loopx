from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..global_gates import build_global_gates, render_global_gates_markdown

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


def register_gates_all_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    parser = subparsers.add_parser(
        "global-gates",
        help="Read open /loopx-global-gates decisions and blocked work; see `loopx slash-commands` for slash help.",
    )
    add_subcommand_format(parser)
    parser.add_argument("--agent-id", help="Registered agent id for agent-lane quota projection.")
    parser.add_argument("--limit", type=int, default=8, help="Maximum gates to return.")
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


def handle_gates_all_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "global-gates":
        return None
    try:
        payload = build_global_gates(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            agent_id=args.agent_id,
            limit=max(1, args.limit),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "global_manager_command_response_v0",
            "request": {
                "schema_version": "global_manager_command_request_v0",
                "command": "/loopx-global-gates",
                "legacy_aliases": ["/loop-global-gates"],
                "privacy_mode": "public_safe_summary",
                "dry_run": True,
            },
            "error": str(exc),
        }
    print_payload(payload, output_format(args), render_global_gates_markdown)
    return 0 if payload.get("ok") else 1
