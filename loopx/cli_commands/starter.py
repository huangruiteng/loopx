from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..demo import (
    DEFAULT_DEMO_AGENT_TODO,
    DEFAULT_DEMO_GOAL_ID,
    DEFAULT_DEMO_OBJECTIVE,
    DEFAULT_DEMO_PROJECT,
    DEFAULT_DEMO_USER_TODO,
    render_demo_markdown,
    run_demo,
)
from .starter_bootstrap import (
    handle_starter_bootstrap_command,
    register_starter_bootstrap_commands,
)
from .starter_scheduler import (
    handle_starter_scheduler_command,
    register_starter_scheduler_commands,
)
from .starter_session_runtime import (
    handle_starter_session_runtime_command,
    register_starter_session_runtime_commands,
)
from .starter_visible_driver import (
    handle_starter_visible_driver_command,
    register_starter_visible_driver_commands,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_commands(subparsers: argparse._SubParsersAction) -> None:
    register_starter_bootstrap_commands(subparsers)
    register_starter_visible_driver_commands(subparsers)
    register_starter_session_runtime_commands(subparsers)
    register_starter_scheduler_commands(subparsers)

    demo_parser = subparsers.add_parser(
        "demo",
        help="Create a disposable local demo goal and show status/quota output.",
    )
    demo_parser.add_argument(
        "--project",
        default=str(DEFAULT_DEMO_PROJECT),
        help=f"Disposable demo project directory. Defaults to {DEFAULT_DEMO_PROJECT}.",
    )
    demo_parser.add_argument("--goal-id", default=DEFAULT_DEMO_GOAL_ID)
    demo_parser.add_argument("--objective", default=DEFAULT_DEMO_OBJECTIVE)
    demo_parser.add_argument("--user-todo", default=DEFAULT_DEMO_USER_TODO)
    demo_parser.add_argument("--agent-todo", default=DEFAULT_DEMO_AGENT_TODO)


def handle_demo_command(args: argparse.Namespace, print_payload: PrintPayload) -> int:
    try:
        payload = run_demo(
            project=Path(args.project).expanduser(),
            runtime_root=Path(args.runtime_root).expanduser() if args.runtime_root else None,
            goal_id=args.goal_id,
            objective=args.objective,
            user_todo=args.user_todo,
            agent_todo=args.agent_todo,
        )
    except Exception as exc:
        payload = {
            "ok": False,
            "project": args.project,
            "goal_id": args.goal_id,
            "error": str(exc),
        }
    print_payload(payload, args.format, render_demo_markdown)
    return 0 if payload.get("ok") else 1


def handle_starter_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    bootstrap_result = handle_starter_bootstrap_command(args, print_payload)
    if bootstrap_result is not None:
        return bootstrap_result
    visible_driver_result = handle_starter_visible_driver_command(args, print_payload)
    if visible_driver_result is not None:
        return visible_driver_result
    session_runtime_result = handle_starter_session_runtime_command(args, print_payload)
    if session_runtime_result is not None:
        return session_runtime_result
    scheduler_result = handle_starter_scheduler_command(args, print_payload)
    if scheduler_result is not None:
        return scheduler_result
    if str(getattr(args, "command", "")) == "demo":
        return handle_demo_command(args, print_payload)
    return None
