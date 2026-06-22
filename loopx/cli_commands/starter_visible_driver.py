from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..codex_cli_probe import (
    build_codex_cli_local_driver_plan,
    build_codex_cli_visible_driver_plan,
    build_codex_cli_visible_driver_run_packet,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_local_driver_plan_markdown,
    render_codex_cli_visible_driver_plan_markdown,
    render_codex_cli_visible_driver_run_packet_markdown,
    run_codex_cli_session_probe,
)
from .starter_visible_common import (
    _add_codex_probe_arguments,
    _add_headless_fallback_argument,
    _add_optional_proof_fixture,
    _add_project_arguments,
)
from .starter_visible_pilot import (
    handle_starter_visible_pilot_command,
    register_starter_visible_pilot_commands,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_visible_driver_commands(subparsers: argparse._SubParsersAction) -> None:
    register_starter_visible_pilot_commands(subparsers)

    codex_cli_visible_driver_parser = subparsers.add_parser(
        "codex-cli-visible-driver-plan",
        help="Plan a public-safe visible Codex CLI driver path from session-probe evidence.",
    )
    _add_project_arguments(codex_cli_visible_driver_parser)
    _add_codex_probe_arguments(codex_cli_visible_driver_parser)

    codex_cli_local_driver_parser = subparsers.add_parser(
        "codex-cli-local-driver-plan",
        help=(
            "Compose a dry-run-first local Codex CLI driver plan from quota, "
            "TUI bootstrap, visible-driver, and exec fallback commands."
        ),
    )
    _add_project_arguments(codex_cli_local_driver_parser)
    _add_codex_probe_arguments(codex_cli_local_driver_parser)

    codex_cli_visible_driver_run_parser = subparsers.add_parser(
        "codex-cli-visible-driver-run",
        help="Build a no-execution visible Codex CLI driver run packet from quota-safe driver planning inputs.",
    )
    _add_project_arguments(codex_cli_visible_driver_run_parser)
    _add_codex_probe_arguments(
        codex_cli_visible_driver_run_parser,
        codex_help="Codex CLI executable to probe for visible-session capabilities.",
    )
    _add_optional_proof_fixture(
        codex_cli_visible_driver_run_parser,
        help_text=(
            "Optional public-safe visible-session proof fixture. "
            "Without it, same-session automation remains blocked."
        ),
    )
    _add_headless_fallback_argument(codex_cli_visible_driver_run_parser)


def handle_codex_cli_visible_driver_plan_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    probe_payload = run_codex_cli_session_probe(
        codex_bin=args.codex_bin,
        timeout_seconds=args.timeout_seconds,
        fixture=Path(args.fixture).expanduser() if args.fixture else None,
    )
    payload = build_codex_cli_visible_driver_plan(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
    )
    print_payload(payload, args.format, render_codex_cli_visible_driver_plan_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_local_driver_plan_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    probe_payload = run_codex_cli_session_probe(
        codex_bin=args.codex_bin,
        timeout_seconds=args.timeout_seconds,
        fixture=Path(args.fixture).expanduser() if args.fixture else None,
    )
    payload = build_codex_cli_local_driver_plan(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
    )
    print_payload(payload, args.format, render_codex_cli_local_driver_plan_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_visible_driver_run_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    probe_payload = run_codex_cli_session_probe(
        codex_bin=args.codex_bin,
        timeout_seconds=args.timeout_seconds,
        fixture=Path(args.fixture).expanduser() if args.fixture else None,
    )
    proof_payload = (
        load_codex_cli_visible_session_proof_fixture(Path(args.proof_fixture).expanduser())
        if args.proof_fixture
        else None
    )
    payload = build_codex_cli_visible_driver_run_packet(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        allow_headless_fallback=bool(args.allow_headless_fallback),
    )
    print_payload(payload, args.format, render_codex_cli_visible_driver_run_packet_markdown)
    return 0 if payload.get("ok") else 1


_VISIBLE_DRIVER_HANDLERS: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
    "codex-cli-visible-driver-plan": handle_codex_cli_visible_driver_plan_command,
    "codex-cli-local-driver-plan": handle_codex_cli_local_driver_plan_command,
    "codex-cli-visible-driver-run": handle_codex_cli_visible_driver_run_command,
}


def handle_starter_visible_driver_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    pilot_result = handle_starter_visible_pilot_command(args, print_payload)
    if pilot_result is not None:
        return pilot_result
    handler = _VISIBLE_DRIVER_HANDLERS.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
