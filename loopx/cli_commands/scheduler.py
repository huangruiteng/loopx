from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..scheduler import (
    DEFAULT_MAX_PARALLEL,
    build_scheduler_plan,
    render_scheduler_plan_markdown,
)
from ..status import collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[..., str]


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def register_scheduler_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    scheduler_parser = subparsers.add_parser(
        "scheduler",
        help="Preview safe parallel LoopX todo scheduling without starting workers.",
    )
    scheduler_sub = scheduler_parser.add_subparsers(dest="scheduler_command", required=True)
    plan_parser = scheduler_sub.add_parser(
        "plan",
        help="Build a read-only safe parallel scheduling plan from current status.",
    )
    add_subcommand_format(plan_parser)
    plan_parser.add_argument("--goal-id", help="Only plan candidates for one goal.")
    plan_parser.add_argument("--agent-id", help="Limit the plan to one registered agent lane.")
    plan_parser.add_argument(
        "--max-parallel",
        type=int,
        default=DEFAULT_MAX_PARALLEL,
        help=f"Maximum candidates in the runnable batch. Defaults to {DEFAULT_MAX_PARALLEL}.",
    )
    plan_parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material. Defaults to the LoopX install root.",
    )
    plan_parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable. Overrides --scan-root when set.",
    )
    plan_parser.add_argument("--limit", type=int, default=5)


def _scan_roots(args: argparse.Namespace) -> list[Path]:
    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    return scan_roots or [Path(args.scan_root).expanduser()]


def handle_scheduler_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: OutputFormat,
    print_payload: PrintPayload,
) -> int | None:
    if getattr(args, "command", None) != "scheduler":
        return None
    selected_format = output_format(args)
    try:
        if args.scheduler_command != "plan":
            raise ValueError(f"unsupported scheduler command: {args.scheduler_command}")
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=_scan_roots(args),
            limit=max(0, int(args.limit)),
        )
        payload = build_scheduler_plan(
            status_payload,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            max_parallel=max(1, int(args.max_parallel)),
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "scheduler_plan_v0",
            "mode": "plan",
            "goal_id": getattr(args, "goal_id", None),
            "agent_id": getattr(args, "agent_id", None),
            "error": str(exc),
        }
    print_payload(payload, selected_format, render_scheduler_plan_markdown)
    return 0 if payload.get("ok") else 1
