from __future__ import annotations

import argparse
from collections.abc import Callable

from ..host_mode_planner import (
    SUPPORTED_HOST_CAPABILITIES,
    SUPPORTED_INTENTS,
    SUPPORTED_TURN_HOST_IDENTITIES,
    HostModePlanError,
    build_host_mode_plan,
    render_host_mode_plan_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
FormatSelector = Callable[..., str]
AddFormat = Callable[[argparse.ArgumentParser], None]


def register_host_mode_plan_command(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "host-mode-plan",
        help="Select a read-only LoopX Turn/connector host mode from intent and host capabilities.",
        description=(
            "Build a public-safe host-mode selector plan on top of the shipped "
            "LoopX Turn and runtime connector contracts. It maps visible TUI, "
            "isolated headless Turn, IM/gateway intake, shell/service timer, "
            "and hybrid handoff modes to preview commands without launching a "
            "host, writing state, or spending quota."
        ),
    )
    add_subcommand_format(parser)
    parser.add_argument("--goal-id", required=True, help="Goal id the host-mode plan is scoped to.")
    parser.add_argument(
        "--intent",
        dest="user_intent",
        action="append",
        default=[],
        help="User intent signal. Repeatable. One of: " + ", ".join(SUPPORTED_INTENTS) + ".",
    )
    parser.add_argument(
        "--host-capability",
        dest="host_capabilities",
        action="append",
        default=[],
        help=(
            "Advertised host capability. Repeatable. One of: "
            + ", ".join(SUPPORTED_HOST_CAPABILITIES)
            + "."
        ),
    )
    parser.add_argument("--agent-id", help="Registered agent id to scope Turn and quota preview commands.")
    parser.add_argument(
        "--host-identity",
        choices=SUPPORTED_TURN_HOST_IDENTITIES,
        help=(
            "Explicit visible host identity. Required to keep visible_tui mapped to the "
            "actual host instead of assuming Codex CLI. One of: "
            + ", ".join(SUPPORTED_TURN_HOST_IDENTITIES)
            + "."
        ),
    )
    parser.add_argument(
        "--registered-agent",
        dest="registered_agents",
        action="append",
        default=[],
        help="Registered agent id for identity resolution. Repeatable.",
    )
    parser.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
        default=[],
        help="Capability passed into generated Turn/quota preview commands. Repeatable.",
    )
    parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated preview commands.",
    )


def handle_host_mode_plan_command(
    args: argparse.Namespace,
    *,
    output_format: FormatSelector,
    print_payload: PrintPayload,
) -> int | None:
    if args.command != "host-mode-plan":
        return None
    try:
        payload = build_host_mode_plan(
            goal_id=args.goal_id,
            user_intent=args.user_intent,
            host_capabilities=args.host_capabilities,
            agent_id=args.agent_id,
            registered_agents=args.registered_agents or None,
            cli_bin=args.cli_bin,
            available_capabilities=args.available_capabilities or None,
            host_identity=args.host_identity,
        )
    except HostModePlanError as exc:
        payload = exc.to_payload()
    print_payload(payload, output_format(args), render_host_mode_plan_markdown)
    return 0 if payload.get("ok") else 1
