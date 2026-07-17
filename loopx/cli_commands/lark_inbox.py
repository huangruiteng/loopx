from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from ..capabilities.lark.event_inbox import (
    acknowledge_lark_event_inbox,
    ingest_lark_event_inbox,
    inspect_lark_event_inbox,
)
from ..capabilities.lark.inbox_reply import reply_lark_event_inbox
from ..capabilities.lark.event_collector import (
    inspect_lark_event_collector,
    install_lark_event_collector,
    plan_lark_event_collector,
)
from ..capabilities.lark.event_collector_runtime import run_lark_event_collector
from ..control_plane.runtime.goal_project_route import resolve_goal_project_route


def _goal_inbox_config(goal: dict[str, object]) -> str | None:
    control_plane = (
        goal.get("control_plane") if isinstance(goal.get("control_plane"), dict) else {}
    )
    inbox = (
        control_plane.get("lark_event_inbox")
        if isinstance(control_plane.get("lark_event_inbox"), dict)
        else {}
    )
    if inbox.get("enabled") is not True:
        return None
    return str(inbox.get("config_path") or "").strip() or None


def _inbox_context(
    args: argparse.Namespace, registry_path: Path
) -> tuple[Path, str | None]:
    if getattr(args, "config", None):
        return Path(getattr(args, "project", None) or ".").expanduser(), str(
            args.config
        )
    if getattr(args, "goal_id", None):
        goal, project, _ = resolve_goal_project_route(
            registry_path=registry_path,
            goal_id=str(args.goal_id),
            project_override=getattr(args, "project", None),
        )
        return project, _goal_inbox_config(goal)
    raise ValueError("lark inbox requires --config or --goal-id")


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
    drain.add_argument("--project")
    drain.add_argument("--config")
    drain.add_argument("--goal-id")
    drain.add_argument("--limit", type=int, default=20)
    ack = sub.add_parser(
        "ack",
        help="Acknowledge events only after their actionable feedback is written back.",
    )
    add_subcommand_format(ack)
    ack.add_argument("--project")
    ack.add_argument("--config")
    ack.add_argument("--goal-id")
    ack.add_argument("--message-id", action="append", required=True)
    ack.add_argument("--execute", action="store_true")
    reply = sub.add_parser(
        "reply",
        help=(
            "Reply once in the source thread with the inbox-configured bot profile; "
            "never falls back to the default app."
        ),
    )
    add_subcommand_format(reply)
    reply.add_argument("--project")
    reply.add_argument("--config")
    reply.add_argument("--goal-id")
    reply.add_argument("--message-id", required=True)
    reply.add_argument("--text", required=True)
    reply.add_argument("--execute", action="store_true")
    ingest = sub.add_parser(
        "ingest",
        help=(
            "Persist canonical compact events from stdin JSON/NDJSON for host "
            "collection or bounded history reconciliation."
        ),
    )
    add_subcommand_format(ingest)
    ingest.add_argument("--project")
    ingest.add_argument("--config")
    ingest.add_argument("--goal-id")
    ingest.add_argument("--execute", action="store_true")
    collector_plan = sub.add_parser(
        "collector-plan",
        help="Validate a local-private collector config and preview host setup.",
    )
    add_subcommand_format(collector_plan)
    collector_plan.add_argument("--project", default=".")
    collector_plan.add_argument("--config", required=True)
    collector_install = sub.add_parser(
        "collector-install",
        help="Preview or explicitly install the configured launchd/systemd collector.",
    )
    add_subcommand_format(collector_install)
    collector_install.add_argument("--project", default=".")
    collector_install.add_argument("--config", required=True)
    collector_install.add_argument("--execute", action="store_true")
    collector_status = sub.add_parser(
        "collector-status",
        help="Inspect collector installation, supervisor state, and event evidence.",
    )
    add_subcommand_format(collector_status)
    collector_status.add_argument("--project", default=".")
    collector_status.add_argument("--config", required=True)
    collector_status.add_argument("--probe-event-bus", action="store_true")
    collector_run = sub.add_parser("collector-run", help=argparse.SUPPRESS)
    add_subcommand_format(collector_run)
    collector_run.add_argument("--project", required=True)
    collector_run.add_argument("--config", required=True)
    collector_run.add_argument("--lark-cli-executable", required=True)
    collector_run.add_argument("--node-executable")


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
    registry_path: Path,
    output_format: Callable[..., str],
    print_payload: Callable,
) -> int | None:
    if args.command != "lark-inbox":
        return None
    try:
        if args.lark_inbox_command == "drain":
            project, config_path = _inbox_context(args, registry_path)
            if config_path is None:
                payload = {
                    "ok": True,
                    "schema_version": "lark_event_inbox_projection_v0",
                    "enabled": False,
                    "configured": False,
                    "pending_count": 0,
                    "items": [],
                    "local_private_content_returned": False,
                    "external_reads_performed": False,
                }
                print_payload(payload, output_format(args), _render)
                return 0
            payload = inspect_lark_event_inbox(
                project=project,
                config_path=config_path,
                limit=args.limit,
            )
        elif args.lark_inbox_command == "ack":
            project, config_path = _inbox_context(args, registry_path)
            if config_path is None:
                raise ValueError("goal does not configure a Lark event inbox")
            payload = acknowledge_lark_event_inbox(
                project=project,
                config_path=config_path,
                message_ids=args.message_id,
                execute=args.execute,
            )
        elif args.lark_inbox_command == "reply":
            project, config_path = _inbox_context(args, registry_path)
            if config_path is None:
                raise ValueError("goal does not configure a Lark event inbox")
            payload = reply_lark_event_inbox(
                project=project,
                config_path=config_path,
                message_id=args.message_id,
                text=args.text,
                execute=args.execute,
            )
        elif args.lark_inbox_command == "ingest":
            project, config_path = _inbox_context(args, registry_path)
            if config_path is None:
                raise ValueError("goal does not configure a Lark event inbox")
            payload = ingest_lark_event_inbox(
                project=project,
                config_path=config_path,
                events=_read_stdin_events(),
                execute=args.execute,
            )
        elif args.lark_inbox_command == "collector-plan":
            payload = plan_lark_event_collector(
                project=args.project,
                config_path=args.config,
            )
        elif args.lark_inbox_command == "collector-install":
            payload = install_lark_event_collector(
                project=args.project,
                config_path=args.config,
                execute=args.execute,
            )
        elif args.lark_inbox_command == "collector-run":
            payload = run_lark_event_collector(
                project=args.project,
                config_path=args.config,
                lark_cli_executable=args.lark_cli_executable,
                node_executable=args.node_executable,
            )
        else:
            payload = inspect_lark_event_collector(
                project=args.project,
                config_path=args.config,
                probe_event_bus=args.probe_event_bus,
            )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "ok": False,
            "schema_version": "lark_event_inbox_error_v0",
            "error": str(exc),
        }
    print_payload(payload, output_format(args), _render)
    return 0 if payload.get("ok") else 1
