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
from ..codex_cli_probe import (
    DEFAULT_CODEX_BIN,
    DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    build_codex_cli_local_scheduler_executor,
    build_codex_cli_local_scheduler_tick,
    build_codex_cli_runtime_idle_detector,
    build_codex_cli_visible_session_proof,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_local_scheduler_executor_markdown,
    render_codex_cli_local_scheduler_tick_markdown,
    render_codex_cli_session_probe_markdown,
    render_codex_cli_runtime_idle_detector_markdown,
    render_codex_cli_visible_session_proof_markdown,
    run_codex_cli_session_probe,
)
from .starter_bootstrap import (
    handle_starter_bootstrap_command,
    register_starter_bootstrap_commands,
)
from .starter_runtime_idle import (
    _add_runtime_idle_observation_arguments,
    _load_codex_cli_runtime_idle_payload,
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

    codex_cli_local_scheduler_tick_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-tick",
        help="Build a no-execution local scheduler tick around codex-cli-visible-driver-run.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_local_scheduler_tick_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe for visible-session capabilities.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-session automation remains blocked.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_local_scheduler_tick_parser)
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Deprecated and ignored; headless codex exec is disabled for this default /goal path.",
    )

    codex_cli_local_scheduler_exec_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-exec",
        help="Explicit opt-in executor wrapper for codex-cli-local-scheduler-tick results.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_local_scheduler_exec_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--agent-id",
        help="Registered LoopX agent id to include in quota/claim instructions.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--cli-bin",
        default="loopx",
        help="LoopX CLI binary name embedded in generated commands.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe for visible-session capabilities.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--executor-timeout-seconds",
        type=float,
        default=DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
        help="Timeout for the explicitly executed scheduler result command.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-session automation remains blocked.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_local_scheduler_exec_parser)
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Deprecated and ignored; headless codex exec is disabled for this default /goal path.",
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
    handlers: dict[str, Callable[[argparse.Namespace, PrintPayload], int]] = {
        "codex-cli-session-probe": handle_codex_cli_session_probe_command,
        "codex-cli-local-scheduler-tick": handle_codex_cli_local_scheduler_tick_command,
        "codex-cli-local-scheduler-exec": handle_codex_cli_local_scheduler_exec_command,
        "codex-cli-visible-session-proof": handle_codex_cli_visible_session_proof_command,
        "codex-cli-runtime-idle-detector": handle_codex_cli_runtime_idle_detector_command,
        "demo": handle_demo_command,
    }
    handler = handlers.get(str(getattr(args, "command", "")))
    if handler is None:
        return None
    return handler(args, print_payload)
