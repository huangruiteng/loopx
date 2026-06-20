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
from ..project_prompt import (
    DEFAULT_HANDOFF_ADAPTER_KIND,
    DEFAULT_HANDOFF_ADAPTER_STATUS,
    build_codex_cli_bootstrap_message,
    build_codex_cli_exec_handoff,
    build_new_project_prompt,
    render_codex_cli_bootstrap_message_markdown,
    render_codex_cli_exec_handoff_markdown,
    render_new_project_prompt_markdown,
)
from ..codex_cli_probe import (
    DEFAULT_CODEX_BIN,
    DEFAULT_TIMEOUT_SECONDS,
    build_codex_cli_local_scheduler_tick,
    build_codex_cli_local_driver_plan,
    build_codex_cli_visible_driver_run_packet,
    build_codex_cli_visible_driver_plan,
    build_codex_cli_visible_session_proof,
    load_codex_cli_visible_session_proof_fixture,
    render_codex_cli_local_scheduler_tick_markdown,
    render_codex_cli_local_driver_plan_markdown,
    render_codex_cli_session_probe_markdown,
    render_codex_cli_visible_driver_run_packet_markdown,
    render_codex_cli_visible_driver_plan_markdown,
    render_codex_cli_visible_session_proof_markdown,
    run_codex_cli_session_probe,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def register_starter_commands(subparsers: argparse._SubParsersAction) -> None:
    prompt_parser = subparsers.add_parser(
        "new-project-prompt",
        help="Generate a copy-paste Codex prompt for connecting a project from a goal document.",
    )
    prompt_parser.add_argument("--project", required=True, help="Project directory the target Codex session can access.")
    prompt_parser.add_argument("--goal-doc", required=True, help="Goal document path for the target project.")
    prompt_parser.add_argument("--goal-id", help="Initial stable goal id. Defaults to <project-name>-goal.")
    prompt_parser.add_argument("--objective", help="Initial objective. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--domain", help="Initial domain label. Defaults to an extraction placeholder.")
    prompt_parser.add_argument("--adapter-kind", default=DEFAULT_HANDOFF_ADAPTER_KIND)
    prompt_parser.add_argument("--adapter-status", default=DEFAULT_HANDOFF_ADAPTER_STATUS)
    prompt_parser.add_argument("--next-probe", help="Optional read-only pre-tick command for the target project.")
    prompt_parser.add_argument("--spawn-allowed", action="store_true", help="Include controller/sub-agent flags.")
    prompt_parser.add_argument("--allowed-domain", action="append", default=[], help="Allowed child work domain. Repeatable.")
    prompt_parser.add_argument("--write-scope", action="append", default=[], help="Allowed write scope such as docs/**. Repeatable.")

    codex_cli_bootstrap_parser = subparsers.add_parser(
        "codex-cli-bootstrap-message",
        help="Generate a one-message Codex CLI TUI bootstrap prompt for a Goal Harness loop.",
    )
    codex_cli_bootstrap_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_bootstrap_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_bootstrap_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_bootstrap_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )

    codex_cli_probe_parser = subparsers.add_parser(
        "codex-cli-session-probe",
        help="Probe Codex CLI help surfaces for same-session Goal Harness automation support.",
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

    codex_cli_visible_driver_parser = subparsers.add_parser(
        "codex-cli-visible-driver-plan",
        help="Plan a public-safe visible Codex CLI driver path from session-probe evidence.",
    )
    codex_cli_visible_driver_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_driver_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_driver_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_visible_driver_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_visible_driver_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
    )
    codex_cli_visible_driver_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_visible_driver_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )

    codex_cli_local_driver_parser = subparsers.add_parser(
        "codex-cli-local-driver-plan",
        help="Compose a dry-run-first local Codex CLI driver plan from quota, TUI bootstrap, visible-driver, and exec fallback commands.",
    )
    codex_cli_local_driver_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_local_driver_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_local_driver_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_local_driver_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_local_driver_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
    )
    codex_cli_local_driver_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_local_driver_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )

    codex_cli_visible_driver_run_parser = subparsers.add_parser(
        "codex-cli-visible-driver-run",
        help="Build a no-execution visible Codex CLI driver run packet from quota-safe driver planning inputs.",
    )
    codex_cli_visible_driver_run_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_driver_run_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_driver_run_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-session automation remains blocked.",
    )
    codex_cli_visible_driver_run_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback packet.",
    )

    codex_cli_local_scheduler_tick_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-tick",
        help="Build a no-execution local scheduler tick around codex-cli-visible-driver-run.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_local_scheduler_tick_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
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
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback candidate.",
    )

    codex_cli_visible_session_proof_parser = subparsers.add_parser(
        "codex-cli-visible-session-proof",
        help="Validate a public-safe proof fixture before treating Codex CLI resume or remote-control as same-session automation.",
    )
    codex_cli_visible_session_proof_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_session_proof_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_session_proof_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in the proof packet.",
    )
    codex_cli_visible_session_proof_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in proof metadata.",
    )
    codex_cli_visible_session_proof_parser.add_argument(
        "--proof-fixture",
        help="Public-safe JSON proof fixture. When omitted, prints the required fixture shape.",
    )

    codex_cli_exec_parser = subparsers.add_parser(
        "codex-cli-exec-handoff",
        help="Generate an explicit one-shot codex exec fallback for Goal Harness onboarding.",
    )
    codex_cli_exec_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_exec_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_exec_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_exec_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_exec_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable name embedded in the generated handoff command.",
    )

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


def handle_new_project_prompt_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_new_project_prompt(
        project=Path(args.project),
        goal_doc=Path(args.goal_doc),
        goal_id=args.goal_id,
        objective=args.objective,
        domain=args.domain,
        adapter_kind=args.adapter_kind,
        adapter_status=args.adapter_status,
        next_probe=args.next_probe,
        spawn_allowed=bool(args.spawn_allowed),
        allowed_domains=args.allowed_domain,
        write_scope=args.write_scope,
    )
    print_payload(payload, args.format, render_new_project_prompt_markdown)
    return 0


def handle_codex_cli_bootstrap_message_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_bootstrap_message(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
    )
    print_payload(payload, args.format, render_codex_cli_bootstrap_message_markdown)
    return 0


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
    payload = build_codex_cli_local_scheduler_tick(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
        probe_payload=probe_payload,
        proof_payload=proof_payload,
        allow_headless_fallback=bool(args.allow_headless_fallback),
    )
    print_payload(payload, args.format, render_codex_cli_local_scheduler_tick_markdown)
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


def handle_codex_cli_exec_handoff_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_exec_handoff(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
        codex_bin=args.codex_bin,
    )
    print_payload(payload, args.format, render_codex_cli_exec_handoff_markdown)
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
