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
    build_codex_cli_tui_bootstrap_smoke_bundle,
    build_new_project_prompt,
    render_codex_cli_bootstrap_message_markdown,
    render_codex_cli_exec_handoff_markdown,
    render_codex_cli_tui_bootstrap_smoke_bundle_markdown,
    render_new_project_prompt_markdown,
)
from ..codex_cli_probe import (
    DEFAULT_CODEX_BIN,
    DEFAULT_EXECUTOR_TIMEOUT_SECONDS,
    DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    build_codex_cli_bounded_visible_pilot_adapter,
    build_codex_cli_one_message_loop_pilot,
    build_codex_cli_visible_local_driver_pilot,
    build_codex_cli_visible_attach_acceptance,
    build_codex_cli_local_scheduler_executor,
    build_codex_cli_local_scheduler_tick,
    build_codex_cli_local_driver_plan,
    build_codex_cli_visible_driver_run_packet,
    build_codex_cli_visible_driver_plan,
    build_codex_cli_visible_session_proof,
    build_codex_cli_runtime_idle_observation_payload,
    build_codex_cli_runtime_idle_detector,
    load_codex_cli_first_response_fixture,
    load_codex_cli_visible_session_proof_fixture,
    load_codex_cli_runtime_idle_fixture,
    render_codex_cli_bounded_visible_pilot_adapter_markdown,
    render_codex_cli_one_message_loop_pilot_markdown,
    render_codex_cli_visible_local_driver_pilot_markdown,
    render_codex_cli_visible_attach_acceptance_markdown,
    render_codex_cli_local_scheduler_executor_markdown,
    render_codex_cli_local_scheduler_tick_markdown,
    render_codex_cli_local_driver_plan_markdown,
    render_codex_cli_session_probe_markdown,
    render_codex_cli_visible_driver_run_packet_markdown,
    render_codex_cli_visible_driver_plan_markdown,
    render_codex_cli_visible_session_proof_markdown,
    render_codex_cli_runtime_idle_detector_markdown,
    probe_human_input_idle_seconds,
    run_codex_cli_session_probe,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]


def _add_runtime_idle_observation_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_idle_fixture: bool = True,
) -> None:
    if include_idle_fixture:
        parser.add_argument(
            "--idle-fixture",
            help="Optional public-safe runtime idle fixture. Without it, later visible turn candidates remain blocked.",
        )
    parser.add_argument(
        "--observe-local-runtime",
        action="store_true",
        help="Build the idle packet from public-safe local observation fields instead of a JSON fixture.",
    )
    parser.add_argument(
        "--observed-surface",
        default="codex_cli_tui_visible_window",
        choices=[
            "codex_cli_tui_visible_window",
            "remote_control_visible_prompt",
            "same_tui_visible_attach",
            "visible_resume_prompt",
        ],
        help="Visible Codex CLI surface observed by the local runtime check.",
    )
    parser.add_argument(
        "--turn-state",
        choices=["idle", "running", "unknown"],
        default="unknown",
        help="Public-safe visible turn state. Unknown or running fails closed.",
    )
    parser.add_argument(
        "--human-input-idle-seconds",
        type=float,
        help="Public-safe observed seconds since last human input. Useful for tests or external sensors.",
    )
    parser.add_argument(
        "--probe-human-input-idle",
        action="store_true",
        help="Probe the local platform for coarse human-input idle seconds when supported.",
    )
    parser.add_argument(
        "--min-human-input-idle-seconds",
        type=float,
        default=DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS,
        help="Minimum idle seconds required to consider human typing inactive.",
    )
    parser.add_argument(
        "--checked-before-prompt",
        action="store_true",
        help="Confirm this idle check ran before any later visible prompt.",
    )
    parser.add_argument(
        "--visible-to-user",
        action="store_true",
        help="Confirm the target turn remains visible to the user.",
    )
    parser.add_argument(
        "--user-can-interrupt",
        action="store_true",
        help="Confirm the user can interrupt the target turn.",
    )
    parser.add_argument(
        "--manual-takeover-available",
        action="store_true",
        help="Confirm manual takeover remains available.",
    )


def _load_codex_cli_runtime_idle_payload(args: argparse.Namespace) -> dict[str, object] | None:
    if args.idle_fixture and args.observe_local_runtime:
        raise ValueError("Use either --idle-fixture or --observe-local-runtime, not both.")
    if args.idle_fixture:
        return load_codex_cli_runtime_idle_fixture(Path(args.idle_fixture).expanduser())
    if not args.observe_local_runtime:
        return None
    probe_result = None
    human_input_idle_seconds = args.human_input_idle_seconds
    if args.probe_human_input_idle:
        probe_result = probe_human_input_idle_seconds()
        if probe_result.get("ok") is True:
            human_input_idle_seconds = float(probe_result["human_input_idle_seconds"])
    return build_codex_cli_runtime_idle_observation_payload(
        observed_surface=args.observed_surface,
        turn_state=args.turn_state,
        human_input_idle_seconds=human_input_idle_seconds,
        min_human_input_idle_seconds=args.min_human_input_idle_seconds,
        checked_before_prompt=bool(args.checked_before_prompt),
        visible_to_user=bool(args.visible_to_user),
        user_can_interrupt=bool(args.user_can_interrupt),
        manual_takeover_available=bool(args.manual_takeover_available),
        probe_result=probe_result,
    )


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
    codex_cli_bootstrap_parser.add_argument(
        "--message-only",
        "--copy-only",
        dest="message_only",
        action="store_true",
        help="Print only the Codex CLI TUI paste message, without the Markdown review packet.",
    )

    codex_cli_tui_bootstrap_smoke_parser = subparsers.add_parser(
        "codex-cli-tui-bootstrap-smoke-bundle",
        help="Generate a transcript-free first-run smoke packet for the Codex CLI TUI bootstrap path.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--project",
        default=".",
        help="Project directory to model as the fresh repo.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--goal-id",
        help="Goal id. Defaults to <project-name>-goal.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_tui_bootstrap_smoke_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )

    codex_cli_one_message_loop_parser = subparsers.add_parser(
        "codex-cli-one-message-loop-pilot",
        help="Compose the first Codex CLI TUI paste message with the safe scheduler/executor bridge.",
    )
    codex_cli_one_message_loop_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_one_message_loop_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_one_message_loop_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_one_message_loop_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_one_message_loop_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in bridge commands.",
    )
    codex_cli_one_message_loop_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_one_message_loop_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_one_message_loop_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-session automation remains blocked.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_one_message_loop_parser)
    codex_cli_one_message_loop_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback candidate.",
    )

    codex_cli_visible_local_driver_parser = subparsers.add_parser(
        "codex-cli-visible-local-driver-pilot",
        help="Compose the one-message TUI start and later scheduler bridge into a visible local driver pilot packet.",
    )
    codex_cli_visible_local_driver_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_local_driver_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_local_driver_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in bridge commands.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, later visible turns remain blocked.",
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--idle-fixture",
        help="Optional public-safe runtime idle fixture. Without it, later visible turn candidates remain blocked.",
    )
    _add_runtime_idle_observation_arguments(
        codex_cli_visible_local_driver_parser,
        include_idle_fixture=False,
    )
    codex_cli_visible_local_driver_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback candidate.",
    )

    codex_cli_bounded_visible_parser = subparsers.add_parser(
        "codex-cli-bounded-visible-pilot-adapter",
        help="Validate public-safe first-response and idle evidence before claiming Codex CLI live TUI bootstrap success.",
    )
    codex_cli_bounded_visible_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_bounded_visible_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_bounded_visible_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in adapter commands.",
    )
    codex_cli_bounded_visible_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_bounded_visible_parser.add_argument(
        "--first-response-fixture",
        help="Public-safe JSON fixture proving the first visible TUI response shape.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_bounded_visible_parser)

    codex_cli_visible_attach_acceptance_parser = subparsers.add_parser(
        "codex-cli-visible-attach-acceptance",
        help="Accept or block same-TUI Codex CLI visible attach from help-only probe, proof, and idle evidence.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_visible_attach_acceptance_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in acceptance commands.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Per-command timeout for help-only Codex CLI probes.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--fixture",
        help="Public-safe JSON fixture with command_outputs, used instead of invoking Codex CLI.",
    )
    codex_cli_visible_attach_acceptance_parser.add_argument(
        "--proof-fixture",
        help="Optional public-safe visible-session proof fixture. Without it, same-TUI attach is not accepted.",
    )
    _add_runtime_idle_observation_arguments(codex_cli_visible_attach_acceptance_parser)

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
    _add_runtime_idle_observation_arguments(codex_cli_local_scheduler_tick_parser)
    codex_cli_local_scheduler_tick_parser.add_argument(
        "--allow-headless-fallback",
        action="store_true",
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback candidate.",
    )

    codex_cli_local_scheduler_exec_parser = subparsers.add_parser(
        "codex-cli-local-scheduler-exec",
        help="Explicit opt-in executor wrapper for codex-cli-local-scheduler-tick results.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_local_scheduler_exec_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in quota/claim instructions.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in generated commands.",
    )
    codex_cli_local_scheduler_exec_parser.add_argument(
        "--codex-bin",
        default=DEFAULT_CODEX_BIN,
        help="Codex CLI executable to probe and reference in fallback commands.",
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
        help="Explicitly mark user/operator opt-in for a headless codex exec fallback candidate.",
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
        help="Execute the precise Goal Harness blocker writeback command after a fresh guard check.",
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

    codex_cli_runtime_idle_parser = subparsers.add_parser(
        "codex-cli-runtime-idle-detector",
        help="Validate public-safe runtime idle evidence before a later visible Codex CLI turn.",
    )
    codex_cli_runtime_idle_parser.add_argument("--project", default=".", help="Project directory to start from.")
    codex_cli_runtime_idle_parser.add_argument("--goal-id", help="Goal id. Defaults to <project-name>-goal.")
    codex_cli_runtime_idle_parser.add_argument(
        "--agent-id",
        help="Registered Goal Harness agent id to include in the idle packet.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--cli-bin",
        default="goal-harness",
        help="Goal Harness CLI binary name embedded in idle detector metadata.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--idle-fixture",
        help="Public-safe JSON idle fixture. Mutually exclusive with --observe-local-runtime.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--observe-local-runtime",
        action="store_true",
        help="Build the idle packet from public-safe local observation fields instead of a JSON fixture.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--observed-surface",
        default="codex_cli_tui_visible_window",
        choices=[
            "codex_cli_tui_visible_window",
            "remote_control_visible_prompt",
            "same_tui_visible_attach",
            "visible_resume_prompt",
        ],
        help="Visible Codex CLI surface observed by the local runtime check.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--turn-state",
        choices=["idle", "running", "unknown"],
        default="unknown",
        help="Public-safe visible turn state. Unknown or running fails closed.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--human-input-idle-seconds",
        type=float,
        help="Public-safe observed seconds since last human input. Useful for tests or external sensors.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--probe-human-input-idle",
        action="store_true",
        help="Probe the local platform for coarse human-input idle seconds when supported.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--min-human-input-idle-seconds",
        type=float,
        default=DEFAULT_MIN_HUMAN_INPUT_IDLE_SECONDS,
        help="Minimum idle seconds required to consider human typing inactive.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--checked-before-prompt",
        action="store_true",
        help="Confirm this idle check ran before any later visible prompt.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--visible-to-user",
        action="store_true",
        help="Confirm the target turn remains visible to the user.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--user-can-interrupt",
        action="store_true",
        help="Confirm the user can interrupt the target turn.",
    )
    codex_cli_runtime_idle_parser.add_argument(
        "--manual-takeover-available",
        action="store_true",
        help="Confirm manual takeover remains available.",
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
    if bool(getattr(args, "message_only", False)):
        print(str(payload.get("message") or ""))
        return 0
    print_payload(payload, args.format, render_codex_cli_bootstrap_message_markdown)
    return 0


def handle_codex_cli_tui_bootstrap_smoke_bundle_command(
    args: argparse.Namespace,
    print_payload: PrintPayload,
) -> int:
    payload = build_codex_cli_tui_bootstrap_smoke_bundle(
        project=Path(args.project),
        goal_id=args.goal_id,
        agent_id=args.agent_id,
        cli_bin=args.cli_bin,
    )
    print_payload(payload, args.format, render_codex_cli_tui_bootstrap_smoke_bundle_markdown)
    return 0


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
