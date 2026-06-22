from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..codex_cli_probe import (
    build_codex_cli_bounded_visible_pilot_adapter,
    build_codex_cli_one_message_loop_pilot,
    build_codex_cli_visible_attach_acceptance,
    build_codex_cli_visible_first_response_capture_plan,
    build_codex_cli_visible_local_driver_pilot,
    load_codex_cli_first_response_fixture,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_bounded_visible_pilot_adapter_markdown,
    render_codex_cli_one_message_loop_pilot_markdown,
    render_codex_cli_visible_attach_acceptance_markdown,
    render_codex_cli_visible_first_response_capture_plan_markdown,
    render_codex_cli_visible_local_driver_pilot_markdown,
    run_codex_cli_session_probe,
)
from .starter_runtime_idle import (
    _add_runtime_idle_observation_arguments,
    _load_codex_cli_runtime_idle_payload,
)
from .starter_visible_common import (
    _add_codex_probe_arguments,
    _add_headless_fallback_argument,
    _add_optional_proof_fixture,
    _add_project_arguments,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_visible_pilot_commands(subparsers: argparse._SubParsersAction) -> None:
    codex_cli_one_message_loop_parser = subparsers.add_parser(
        "codex-cli-one-message-loop-pilot",
        help="Compose the first Codex CLI TUI paste message with the safe scheduler/executor bridge.",
    )
    _add_project_arguments(codex_cli_one_message_loop_parser)
    _add_codex_probe_arguments(
        codex_cli_one_message_loop_parser,
        codex_help="Codex CLI executable to probe and reference in bridge commands.",
    )
    _add_optional_proof_fixture(
        codex_cli_one_message_loop_parser,
        help_text=(
            "Optional public-safe visible-session proof fixture. "
            "Without it, same-session automation remains blocked."
        ),
    )
    _add_runtime_idle_observation_arguments(codex_cli_one_message_loop_parser)
    _add_headless_fallback_argument(codex_cli_one_message_loop_parser)

    codex_cli_visible_local_driver_parser = subparsers.add_parser(
        "codex-cli-visible-local-driver-pilot",
        help="Compose the one-message TUI start and later scheduler bridge into a visible local driver pilot packet.",
    )
    _add_project_arguments(codex_cli_visible_local_driver_parser)
    _add_codex_probe_arguments(
        codex_cli_visible_local_driver_parser,
        codex_help="Codex CLI executable to probe and reference in bridge commands.",
    )
    _add_optional_proof_fixture(
        codex_cli_visible_local_driver_parser,
        help_text="Optional public-safe visible-session proof fixture. Without it, later visible turns remain blocked.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--idle-fixture",
        help="Optional public-safe runtime idle fixture. Without it, later visible turn candidates remain blocked.",
    )
    _add_runtime_idle_observation_arguments(
        codex_cli_visible_local_driver_parser,
        include_idle_fixture=False,
    )
    _add_headless_fallback_argument(codex_cli_visible_local_driver_parser)

    codex_cli_bounded_visible_parser = subparsers.add_parser(
        "codex-cli-bounded-visible-pilot-adapter",
        help="Validate public-safe first-response and idle evidence before claiming Codex CLI live TUI bootstrap success.",
    )
    _add_project_arguments(
        codex_cli_bounded_visible_parser,
        agent_help="Registered LoopX agent id to include in adapter commands.",
    )
    codex_cli_bounded_visible_parser.add_argument(
        "--first-response-fixture",
        help="Public-safe JSON fixture proving the first visible TUI response shape.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_bounded_visible_parser)

    codex_cli_first_response_capture_parser = subparsers.add_parser(
        "codex-cli-visible-first-response-capture-plan",
        help="Plan the public-safe manual visible capture of Codex CLI first-response and idle fixtures.",
    )
    _add_project_arguments(
        codex_cli_first_response_capture_parser,
        agent_help="Registered LoopX agent id to include in generated commands.",
    )
    codex_cli_first_response_capture_parser.add_argument(
        "--first-response-path",
        default="public-first-response.json",
        help="Public-safe first-response fixture path used in generated commands.",
    )
    codex_cli_first_response_capture_parser.add_argument(
        "--idle-path",
        default="public-runtime-idle.json",
        help="Public-safe runtime idle fixture path used in generated commands.",
    )

    codex_cli_visible_attach_acceptance_parser = subparsers.add_parser(
        "codex-cli-visible-attach-acceptance",
        help="Accept or block same-TUI Codex CLI visible attach from help-only probe, proof, and idle evidence.",
    )
    _add_project_arguments(
        codex_cli_visible_attach_acceptance_parser,
        agent_help="Registered LoopX agent id to include in acceptance commands.",
    )
    _add_codex_probe_arguments(
        codex_cli_visible_attach_acceptance_parser,
        codex_help="Codex CLI executable to probe and reference in fallback commands.",
    )
    _add_optional_proof_fixture(
        codex_cli_visible_attach_acceptance_parser,
        help_text="Optional public-safe visible-session proof fixture. Without it, same-TUI attach is not accepted.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_visible_attach_acceptance_parser)


def handle_codex_cli_one_message_loop_pilot_command(
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
    idle_payload = _load_codex_cli_runtime_idle_payload(args)
    payload = build_codex_cli_one_message_loop_pilot(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=bool(args.allow_headless_fallback),
    )
    print_payload(payload, args.format, render_codex_cli_one_message_loop_pilot_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_visible_local_driver_pilot_command(
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
    idle_payload = _load_codex_cli_runtime_idle_payload(args)
    payload = build_codex_cli_visible_local_driver_pilot(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=bool(args.allow_headless_fallback),
    )
    print_payload(payload, args.format, render_codex_cli_visible_local_driver_pilot_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_bounded_visible_pilot_adapter_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    first_response_payload = (
        load_codex_cli_first_response_fixture(Path(args.first_response_fixture).expanduser())
        if args.first_response_fixture
        else None
    )
    idle_payload = _load_codex_cli_runtime_idle_payload(args)
    payload = build_codex_cli_bounded_visible_pilot_adapter(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        first_response_payload=first_response_payload,
        idle_payload=idle_payload,
    )
    print_payload(payload, args.format, render_codex_cli_bounded_visible_pilot_adapter_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_visible_first_response_capture_plan_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_visible_first_response_capture_plan(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        first_response_path=args.first_response_path,
        idle_path=args.idle_path,
    )
    print_payload(payload, args.format, render_codex_cli_visible_first_response_capture_plan_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_visible_attach_acceptance_command(
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
    idle_payload = _load_codex_cli_runtime_idle_payload(args)
    payload = build_codex_cli_visible_attach_acceptance(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
    )
    print_payload(payload, args.format, render_codex_cli_visible_attach_acceptance_markdown)
    return 0 if payload.get("ok") else 1


_VISIBLE_PILOT_HANDLERS: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
    "codex-cli-one-message-loop-pilot": handle_codex_cli_one_message_loop_pilot_command,
    "codex-cli-visible-local-driver-pilot": handle_codex_cli_visible_local_driver_pilot_command,
    "codex-cli-bounded-visible-pilot-adapter": handle_codex_cli_bounded_visible_pilot_adapter_command,
    "codex-cli-visible-first-response-capture-plan": handle_codex_cli_visible_first_response_capture_plan_command,
    "codex-cli-visible-attach-acceptance": handle_codex_cli_visible_attach_acceptance_command,
}


def handle_starter_visible_pilot_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    handler = _VISIBLE_PILOT_HANDLERS.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
