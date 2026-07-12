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
    project_lark_event_inbox_reward,
)
from ..feedback import LESSON_KINDS, compact_reward


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
    project_reward = sub.add_parser(
        "project-reward",
        help="Atomically project one inbox event into reward state, then acknowledge it.",
    )
    add_subcommand_format(project_reward)
    project_reward.add_argument("--project", default=".")
    project_reward.add_argument("--config", required=True)
    project_reward.add_argument("--goal-id", required=True)
    project_reward.add_argument("--message-id", required=True)
    project_reward.add_argument("--run-generated-at")
    project_reward.add_argument("--recorded-at")
    project_reward.add_argument("--decision", required=True)
    project_reward.add_argument(
        "--reward", required=True, choices=["positive", "negative", "mixed", "neutral"]
    )
    project_reward.add_argument("--reason-summary", required=True)
    project_reward.add_argument("--follow-up")
    project_reward.add_argument("--lesson-kind", choices=sorted(LESSON_KINDS), required=True)
    project_reward.add_argument("--lesson-summary", required=True)
    project_reward.add_argument("--lesson-avoid", action="append", default=[])
    project_reward.add_argument("--lesson-prefer", action="append", default=[])
    project_reward.add_argument(
        "--lesson-strength", choices=["advisory", "required"], default="advisory"
    )
    project_reward.add_argument(
        "--lesson-scope",
        choices=["goal", "workspace", "repository", "delivery_surface"],
        default="goal",
    )
    project_reward.add_argument("--lesson-scope-key")
    project_reward.add_argument("--lesson-supersedes", action="append", default=[])
    project_reward.add_argument("--state-file")
    project_reward.add_argument("--execute", action="store_true")


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
    if payload.get("schema_version") == "lark_event_reward_projection_v0":
        return "\n".join(
            [
                "# Lark Event Reward Projection",
                "",
                f"- ok: {payload.get('ok')}",
                f"- execute: {payload.get('execute')}",
                f"- goal_id: {payload.get('goal_id')}",
                f"- reward_id: {payload.get('reward_id')}",
                f"- reward_event_appended: {payload.get('reward_event_appended')}",
                f"- reward_event_already_exists: {payload.get('reward_event_already_exists')}",
                f"- active_state_written: {payload.get('active_state_written')}",
                f"- acknowledged: {payload.get('acknowledged')}",
            ]
        ).rstrip() + "\n"
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
    runtime_root_arg: str | None,
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
        elif args.lark_inbox_command == "ingest":
            payload = ingest_lark_event_inbox(
                project=args.project,
                config_path=args.config,
                events=_read_stdin_events(),
                execute=args.execute,
            )
        else:
            reward = compact_reward(
                recorded_at=args.recorded_at,
                decision=args.decision,
                reward=args.reward,
                reason_summary=args.reason_summary,
                follow_up=args.follow_up,
                lesson={
                    "kind": args.lesson_kind,
                    "summary": args.lesson_summary,
                    "avoid": args.lesson_avoid,
                    "prefer": args.lesson_prefer,
                    "strength": args.lesson_strength,
                    "scope": args.lesson_scope,
                    "scope_key": args.lesson_scope_key,
                    "supersedes": args.lesson_supersedes,
                },
            )
            payload = project_lark_event_inbox_reward(
                project=args.project,
                config_path=args.config,
                registry_path=registry_path,
                runtime_root_override=runtime_root_arg,
                goal_id=args.goal_id,
                message_id=args.message_id,
                reward=reward,
                run_generated_at=args.run_generated_at,
                state_file_override=Path(args.state_file).expanduser() if args.state_file else None,
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
