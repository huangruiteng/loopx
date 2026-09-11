"""Argument-parser registration for the governed Turn command surface."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from ..paths import default_public_scan_root


AddFormat = Callable[[argparse.ArgumentParser], None]


def register_turn_commands(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddFormat,
) -> None:
    parser = subparsers.add_parser(
        "turn",
        help="Plan, run, or inspect one governed external-host Turn.",
    )
    command_sub = parser.add_subparsers(dest="turn_command", required=True)
    inspect_journal = command_sub.add_parser(
        "inspect-journal",
        help="Inspect one canonical fenced Turn journal without executing effects.",
    )
    add_subcommand_format(inspect_journal)
    inspect_journal.add_argument("--goal-id", required=True)
    inspect_journal.add_argument("--agent-id", required=True)
    inspect_journal.add_argument("--turn-key", required=True)
    inspect_journal.add_argument(
        "--retry-failed-turn",
        action="store_true",
        help=(
            "Evaluate an explicit failed-Turn retry, including any current "
            "Host Session binding check."
        ),
    )

    plan = command_sub.add_parser(
        "plan",
        help="Build one typed read-only host decision without launching or writing.",
    )
    add_subcommand_format(plan)
    _add_turn_decision_arguments(plan, default_host="codex-cli")
    plan.add_argument(
        "--include-transaction-detail",
        action="store_true",
        help="Include session binding and transaction receipt planning detail.",
    )
    plan.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material.",
    )
    plan.add_argument(
        "--scan-path",
        action="append",
        default=[],
        help="Specific public file or directory to scan. Repeatable.",
    )
    plan.add_argument("--limit", type=int, default=5)

    run_once = command_sub.add_parser(
        "run-once",
        help=(
            "Run one explicit isolated generic host command and commit only a "
            "validated public-safe result."
        ),
        description=(
            "Run one governed Turn: LoopX decides, a host adapter invokes an "
            "agent CLI, an independent validator proves the postcondition, and "
            "LoopX commits only a passing result."
        ),
        epilog=(
            "A Trae, Codex, or other conversational CLI normally needs a thin "
            "adapter: read one typed request from stdin and emit one typed result "
            "to stdout. The validation command receives that normalized result "
            "on stdin and must independently check the real postcondition. Only "
            "eligible interrupted sessions resume; terminal startup or missing-session "
            "failures start a fresh host session on the next Turn."
        ),
    )
    add_subcommand_format(run_once)
    _add_turn_decision_arguments(
        run_once,
        default_host="generic-cli",
        host_choices=["codex-cli", "dsh", "generic-cli"],
        execution_mode_choices=["isolated-headless"],
        default_execution_mode="isolated-headless",
    )
    run_once.add_argument("--project", required=True)
    run_once.add_argument(
        "--host-command-json",
        "--host-adapter-command-json",
        dest="host_command_json",
        help=(
            "JSON argv array for a typed generic host adapter. The adapter reads "
            "the Turn request from stdin and emits one result JSON object; shell "
            "parsing is never used."
        ),
    )
    run_once.add_argument(
        "--validation-command-json",
        help=(
            "Trusted JSON argv array for independent task/postcondition validation. "
            "The normalized host result is provided on stdin; shell parsing is never used."
        ),
    )
    run_once.add_argument(
        "--validation-timeout-seconds",
        type=float,
        default=30.0,
        help="Timeout for the independent validation command.",
    )
    run_once.add_argument(
        "--validation-failure-kind",
        choices=["repair_required", "replan_required"],
        default="repair_required",
        help="Typed recovery disposition when the independent validator rejects the result.",
    )
    run_once.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable used by the built-in codex-cli host.",
    )
    run_once.add_argument("--codex-model")
    run_once.add_argument(
        "--codex-sandbox",
        choices=["read-only", "workspace-write"],
        default="read-only",
        help="Sandbox for a new Codex CLI session; resume preserves its original session policy.",
    )
    run_once.add_argument(
        "--dsh-provider",
        help="Provider for the built-in dsh host; defaults to DSH_PROVIDER.",
    )
    run_once.add_argument(
        "--dsh-model",
        help="Model for the built-in dsh host; defaults to DSH_MODEL.",
    )
    run_once.add_argument("--dsh-max-tokens", type=int)
    run_once.add_argument(
        "--dsh-home",
        help=(
            "Explicit DeepSeek Harness home; defaults to DSH_HOME or "
            "<project>/.local/.dsh-sessions."
        ),
    )
    run_once.add_argument(
        "--dsh-cordis",
        help="cordis.yml used by the built-in dsh host runtime.",
    )
    run_once.add_argument("--dsh-runtime-bin")
    run_once.add_argument(
        "--dsh-runner",
        help=(
            "Explicit runner hook intended for hermetic tests; this is not a "
            "permission boundary. Path to a Python module exposing "
            "run_dsh_turn(...) used instead of the DeepSeek Harness SDK."
        ),
    )
    run_once.add_argument("--timeout-seconds", type=float, default=120.0)
    run_once.add_argument(
        "--retry-failed-turn",
        action="store_true",
        help="Retry a failed transaction from its last side-effect-safe phase.",
    )
    run_once.add_argument(
        "--resume-turn-key",
        help="Resume the exact journaled transaction without recomputing its plan.",
    )
    run_once.add_argument(
        "--no-global-sync",
        action="store_true",
        help="Keep disposable fixture writeback out of the shared global registry.",
    )
    run_once.add_argument(
        "--execute",
        action="store_true",
        help="Invoke the host and commit validated writeback/quota effects.",
    )
    run_once.add_argument(
        "--scan-root",
        default=default_public_scan_root(),
        help="Public files to scan for obvious private material.",
    )
    run_once.add_argument("--scan-path", action="append", default=[])
    run_once.add_argument("--limit", type=int, default=5)


def _add_turn_decision_arguments(
    parser: argparse.ArgumentParser,
    *,
    default_host: str,
    host_choices: list[str] | None = None,
    execution_mode_choices: list[str] | None = None,
    default_execution_mode: str = "interactive-visible",
) -> None:
    parser.add_argument("--goal-id", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--host",
        choices=host_choices or ["codex-cli", "claude-code", "generic-cli"],
        default=default_host,
    )
    parser.add_argument(
        "--execution-mode",
        choices=execution_mode_choices or ["interactive-visible", "isolated-headless"],
        default=default_execution_mode,
    )
    parser.add_argument(
        "--scheduler-owner",
        choices=["host_automation", "agent_cli_loop", "outer_controller", "none"],
        help=(
            "Cadence owner; defaults to outer_controller for generic-cli and "
            "agent_cli_loop otherwise."
        ),
    )
    parser.add_argument(
        "--turn-instance-id",
        help=(
            "Caller-stable public-safe identity for one logical Turn. Reusing the "
            "same id replays idempotently; use a new id for a new Turn with the "
            "same semantic action."
        ),
    )
    parser.add_argument(
        "--iteration-context",
        choices=["fresh", "resume-if-available"],
        default="resume-if-available",
        help=(
            "Host context policy for this iteration. fresh starts a clean "
            "session even when a compatible prior session exists; "
            "resume-if-available preserves the existing continuation behavior."
        ),
    )
    parser.add_argument(
        "--resume-goal-id",
        help="Goal identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--resume-agent-id",
        help="Agent identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--resume-todo-id",
        help="Todo identity bound to an available opaque host session.",
    )
    parser.add_argument(
        "--available-capability",
        dest="available_capabilities",
        action="append",
    )
