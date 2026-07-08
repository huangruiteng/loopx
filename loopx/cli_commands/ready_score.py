from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..doctor import collect_doctor
from ..quota import build_quota_should_run
from ..ready_score import (
    build_ready_score_report,
    render_ready_score_markdown,
    select_ready_score_goal_id,
)
from ..status import collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def _scan_roots(args: argparse.Namespace) -> list[Path]:
    scan_roots = [Path(item).expanduser() for item in args.scan_path]
    return scan_roots or [Path(args.scan_root).expanduser()]


def register_ready_score_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "ready-score",
        help="Render a read-only LoopX readiness score from doctor/status/quota signals.",
        description=(
            "Render a read-only LoopX readiness score from doctor/status/quota "
            "signals without writing state, README files, or badges."
        ),
    )
    add_subcommand_format(parser)
    parser.add_argument("--goal-id", help="Goal id to score. Defaults to the first attention item.")
    parser.add_argument(
        "--agent-id",
        help="Registered agent id for identity-scoped quota and scheduler readiness.",
    )
    parser.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan through the status contract. Defaults to the LoopX install root.",
    )
    parser.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan through the status contract. Repeatable.",
    )
    parser.add_argument("--limit", type=int, default=5)


def handle_ready_score_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "ready-score":
        return None
    doctor_payload = collect_doctor()
    status_payload = collect_status(
        registry_path=registry_path,
        runtime_root_override=runtime_root_arg,
        scan_roots=_scan_roots(args),
        limit=max(0, args.limit),
        goal_id=args.goal_id,
    )
    selected_goal_id = select_ready_score_goal_id(status_payload, args.goal_id)
    quota_payload = None
    if selected_goal_id:
        quota_payload = build_quota_should_run(
            status_payload,
            goal_id=selected_goal_id,
            agent_id=args.agent_id,
        )
    payload = build_ready_score_report(
        doctor_payload=doctor_payload,
        status_payload=status_payload,
        quota_payload=quota_payload,
        goal_id=selected_goal_id,
        agent_id=args.agent_id,
    )
    print_payload(payload, output_format(args), render_ready_score_markdown)
    return 0 if payload.get("ok") else 1
