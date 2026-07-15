from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..control_plane.turn_driver import build_loopx_turn_plan
from ..control_plane.quota.live_decision import build_live_quota_should_run_decision
from ..control_plane.quota.turn_envelope import build_turn_envelope
from ..control_plane.runtime.status_projection_cache import (
    resolve_status_projection_cache_runtime_root,
)
from ..status import AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK, collect_status


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def _default_public_scan_root() -> str:
    return str(Path(__file__).resolve().parents[2])


def register_turn_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "turn",
        help="Plan one governed external-host turn from a live LoopX decision.",
    )
    command_sub = parser.add_subparsers(dest="turn_command", required=True)
    plan = command_sub.add_parser(
        "plan",
        help="Build one typed read-only host decision without launching or writing.",
    )
    add_subcommand_format(plan)
    plan.add_argument("--goal-id", required=True)
    plan.add_argument("--agent-id", required=True)
    plan.add_argument(
        "--host",
        choices=["codex-cli", "claude-code", "generic-cli"],
        default="codex-cli",
    )
    plan.add_argument(
        "--execution-mode",
        choices=["interactive-visible", "isolated-headless"],
        default="interactive-visible",
    )
    plan.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
    )
    plan.add_argument(
        "--scan-root",
        default=_default_public_scan_root(),
        help="Public files to scan for obvious private material.",
    )
    plan.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable.",
    )
    plan.add_argument("--limit", type=int, default=5)


def _render_loopx_turn_plan_markdown(payload: dict[str, object]) -> str:
    if not payload.get("ok"):
        error = payload.get("error") or "invalid TurnEnvelope contract"
        return f"LoopX Turn plan failed: {error}"
    host = payload.get("host") if isinstance(payload.get("host"), dict) else {}
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    return "\n".join(
        [
            "# LoopX Turn Plan",
            f"- host: {host.get('kind')}",
            f"- execution_mode: {host.get('execution_mode')}",
            f"- route: {route.get('kind')}",
            f"- would_invoke_host: {route.get('would_invoke_host')}",
            "- side_effects: none",
        ]
    )


def handle_turn_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    runtime_root_arg: str | None,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "turn":
        return None
    try:
        if args.turn_command != "plan":
            raise ValueError("turn requires the `plan` subcommand")
        scan_roots = [Path(item).expanduser() for item in args.scan_path]
        if not scan_roots:
            scan_roots = [Path(args.scan_root).expanduser()]
        runtime_root = resolve_status_projection_cache_runtime_root(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
        )
        status_payload = collect_status(
            registry_path=registry_path,
            runtime_root_override=runtime_root_arg,
            scan_roots=scan_roots,
            limit=max(max(0, args.limit), AUTONOMOUS_REPLAN_PERIODIC_LOOKBACK),
        )
        decision = build_live_quota_should_run_decision(
            status_payload,
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            available_capabilities=args.available_capabilities,
            include_scheduler_detail=False,
            codex_app_current_rrule=None,
            registry_path=registry_path,
            runtime_root=runtime_root,
            route_source="loopx_turn_plan",
        )
        payload = build_loopx_turn_plan(
            build_turn_envelope(decision),
            host=args.host,
            execution_mode=args.execution_mode,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "schema_version": "loopx_turn_plan_v0",
            "mode": "plan",
            "error": str(exc),
            "effects": {
                "host_invoked": False,
                "state_written": False,
                "scheduler_acknowledged": False,
                "quota_spent": False,
            },
        }
    print_payload(payload, output_format(args), _render_loopx_turn_plan_markdown)
    return 0 if payload.get("ok") else 1
