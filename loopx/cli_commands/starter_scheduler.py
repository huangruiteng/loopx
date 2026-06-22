from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..codex_cli_probe import (
    DEFAULT_CODEX_BIN,
    DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    build_codex_cli_local_scheduler_executor,
    build_codex_cli_local_scheduler_tick,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_local_scheduler_executor_markdown,
    render_codex_cli_local_scheduler_tick_markdown,
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


def _add_scheduler_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=".", help="Project directory to start from.")
    parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe for visible-session capabilities.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-session automation remains blocked.",
    )
    _add_runtime_idle_observation_arguments(parser)
    parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Deprecated and ignored; headless codex exec is disabled for this default /goal path.",
    )


def register_starter_scheduler_commands(subparsers: argparse._SubParsersAction) -> None:
    codex_cli_local_scheduler_tick_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-tick",
        help="Build a no-execution local scheduler tick around codex-cli-visible-driver-run.",
    )
    _add_scheduler_common_arguments(codex_cli_local_scheduler_tick_parser)

    codex_cli_local_scheduler_exec_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-exec",
        help="Explicit opt-in executor wrapper for codex-cli-local-scheduler-tick results.",
    )
    _add_scheduler_common_arguments(codex_cli_local_scheduler_exec_parser)
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--executor-timeout-seconds",
        type=float,
        default=DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
        help="Timeout for the explicitly executed scheduler result command.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--guard-checked",
        action="store_true",
        help="Confirm a fresh quota/user-gate guard was checked before executing a candidate or blocker writeback.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--execute-candidate",
        action="store_true",
        help="Execute the scheduler candidate command after guard and prefix checks.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--execute-blocker-writeback",
        action="store_true",
        help="Execute the precise LoopX blocker writeback command after a fresh guard check.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--candidate-command-prefix",
        action="append",
        default=[],
        help="Allowed command prefix for --execute-candidate. Repeatable; required before candidate execution.",
    )


def handle_codex_cli_local_scheduler_tick_command(
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
    payload = build_codex_cli_local_scheduler_tick(
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
    print_payload(payload, args.format, render_codex_cli_local_scheduler_tick_markdown)
    return 0 if payload.get("ok") else 1


def handle_codex_cli_local_scheduler_exec_command(
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
    payload = build_codex_cli_local_scheduler_executor(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        idle_payload=idle_payload,
        allow_headless_fallback=bool(args.allow_headless_fallback),
        execute_candidate=bool(args.execute_candidate),
        execute_blocker_writeback=bool(args.execute_blocker_writeback),
        guard_checked=bool(args.guard_checked),
        candidate_command_prefixes=list(args.candidate_command_prefix or []),
        executor_timeout_seconds=args.executor_timeout_seconds,
    )
    print_payload(payload, args.format, render_codex_cli_local_scheduler_executor_markdown)
    return 0 if payload.get("ok") else 1


_SCHEDULER_HANDLERS: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
    "codex-cli-local-scheduler-tick": handle_codex_cli_local_scheduler_tick_command,
    "codex-cli-local-scheduler-exec": handle_codex_cli_local_scheduler_exec_command,
}


def handle_starter_scheduler_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int | None:
    handler = _SCHEDULER_HANDLERS.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
