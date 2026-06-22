from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..codex_cli_probe import (
    DEFAULT_CODEX_BIN,
    DEFAULT_TIMEOUT_SECONDS,
    build_codex_cli_runtime_idle_detector,
    build_codex_cli_visible_session_proof,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_runtime_idle_detector_markdown,
    render_codex_cli_session_probe_markdown,
    render_codex_cli_visible_session_proof_markdown,
    run_codex_cli_session_probe,
)
from .starter_runtime_idle import (
    _add_runtime_idle_observation_arguments,
    _load_codex_cli_runtime_idle_payload,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_session_runtime_commands(subparsers: argparse._SubParsersAction) -> None:
    codex_cli_probe_parser = subparsers.add_parser(
        "codex-cli-session-probe",
        help="Probe Codex CLI help surfaces for same-session LoopX automation support.",
    )
    codex_cli_probe_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe with help-only commands.",
    )
    codex_cli_probe_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_probe_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )

    codex_cli_visible_session_proof_parser = subparsers.add_parser(
        "codex-cli-visible-session-proof",
        help="Validate a public-safe proof fixture before treating Codex CLI resume or remote-control as same-session automation.",
    )
    codex_cli_visible_session_proof_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_session_proof_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_session_proof_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in the proof packet.",
    )
    codex_cli_visible_session_proof_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in proof metadata.",
    )
    codex_cli_visible_session_proof_parser.add_argument(
        "--proof-fixture",
        help="Public-safe JSON proof fixture. When omitted, prints the required fixture shape.",
    )

    codex_cli_runtime_idle_parser = subparsers.add_parser(
        "codex-cli-runtime-idle-detector",
        help="Validate public-safe runtime idle evidence before a later visible Codex CLI turn.",
    )
    codex_cli_runtime_idle_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_runtime_idle_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_runtime_idle_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in the idle packet.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in idle detector metadata.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_runtime_idle_parser)


def handle_codex_cli_session_probe_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = run_codex_cli_session_probe(
        codex_bin=args.codex_bin,
        timeout_seconds=args.timeout_seconds,
        fixture=Path(args.fixture).expanduser() if args.fixture else None,
    )
    print_payload(payload, args.format, render_codex_cli_session_probe_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_visible_session_proof_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    proof_payload = (
        load_codex_cli_visible_session_proof_fixture(Path(args.proof_fixture).expanduser())
        if args.proof_fixture
        else None
    )
    payload = build_codex_cli_visible_session_proof(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        proof_payload=proof_payload,
    )
    print_payload(payload, args.format, render_codex_cli_visible_session_proof_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_runtime_idle_detector_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    idle_payload = _load_codex_cli_runtime_idle_payload(args)
    payload = build_codex_cli_runtime_idle_detector(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        idle_payload=idle_payload,
    )
    print_payload(payload, args.format, render_codex_cli_runtime_idle_detector_markdown)
    return 0 if payload.get("ok") else 1


_SESSION_RUNTIME_HANDLERS: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
    "codex-cli-session-probe": handle_codex_cli_session_probe_command,
    "codex-cli-visible-session-proof": handle_codex_cli_visible_session_proof_command,
    "codex-cli-runtime-idle-detector": handle_codex_cli_runtime_idle_detector_command,
}


def handle_starter_session_runtime_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    handler = _SESSION_RUNTIME_HANDLERS.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
