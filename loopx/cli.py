from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .cli_commands import (
    handle_benchmark_command,
    handle_bootstrap_connect_command,
    handle_check_command,
    handle_codex_cli_bounded_visible_pilot_adapter_command,
    handle_codex_cli_bootstrap_message_command,
    handle_codex_cli_exec_handoff_command,
    handle_codex_cli_visible_first_response_capture_plan_command,
    handle_codex_cli_local_driver_plan_command,
    handle_codex_cli_local_scheduler_exec_command,
    handle_codex_cli_local_scheduler_tick_command,
    handle_codex_cli_one_message_loop_pilot_command,
    handle_codex_cli_runtime_idle_detector_command,
    handle_codex_cli_session_probe_command,
    handle_codex_cli_tui_bootstrap_smoke_bundle_command,
    handle_codex_cli_visible_attach_acceptance_command,
    handle_codex_cli_visible_local_driver_pilot_command,
    handle_codex_cli_visible_driver_run_command,
    handle_codex_cli_visible_driver_plan_command,
    handle_codex_cli_visible_session_proof_command,
    handle_diagnose_command,
    handle_demo_command,
    handle_doctor_command,
    handle_dreaming_command,
    handle_history_command,
    handle_ml_experiment_command,
    handle_new_project_prompt_command,
    handle_project_lifecycle_command,
    handle_quota_command,
    handle_registry_admin_command,
    handle_review_packet_command,
    handle_status_command,
    handle_support_control_command,
    handle_todo_command,
    handle_worker_bridge_command,
    register_benchmark_command_group,
    register_bootstrap_connect_command,
    register_doctor_command,
    register_dreaming_commands,
    register_history_command,
    register_ml_experiment_commands,
    register_project_lifecycle_commands,
    register_quota_command,
    register_registry_admin_commands,
    register_starter_commands,
    register_status_commands,
    register_support_control_commands,
    register_todo_command,
    register_worker_bridge_commands,
)
from .cli_rollout import (
    append_benchmark_result_rollout_event,
    append_benchmark_run_rollout_event,
    append_cli_rollout_event,
)
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


def build_version_payload() -> dict[str, object]:
    return {
        "ok": True,
        "schema_version": "loopx_version_v0",
        "name": "loopx",
        "version": __version__,
    }


def render_version_markdown(payload: dict[str, object]) -> str:
    return f"{payload.get('name')} {payload.get('version')}\n"


def add_subcommand_format(arg_parser: argparse.ArgumentParser) -> None:
    arg_parser.add_argument(
        "--format",
        dest="subcommand_format",
        choices=["markdown", "json"],
        help="Output format for this subcommand. Equivalent to global --format before the command.",
    )


def output_format(args: argparse.Namespace, *local_dests: str) -> str:
    for dest in (*local_dests, "subcommand_format"):
        value = getattr(args, dest, None)
        if value:
            return str(value)
    return str(args.format)


def user_supplied_registry(argv: list[str] | None) -> bool:
    values = sys.argv[1:] if argv is None else argv
    return any(value == "--registry" or value.startswith("--registry=") for value in values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LoopX control-plane helper.")
    parser.add_argument("--version", action="version", version=f"loopx {__version__}")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="Print the installed LoopX version.")

    register_bootstrap_connect_command(sub)

    register_starter_commands(sub)

    register_doctor_command(sub)

    register_worker_bridge_commands(sub, add_subcommand_format)

    register_support_control_commands(sub, add_subcommand_format)

    register_ml_experiment_commands(sub, add_subcommand_format)

    register_registry_admin_commands(sub)

    register_history_command(sub)

    register_benchmark_command_group(sub, add_subcommand_format)

    register_project_lifecycle_commands(sub, add_subcommand_format)

    register_status_commands(sub, add_subcommand_format)
    register_dreaming_commands(sub, add_subcommand_format)
    register_todo_command(sub)
    register_quota_command(sub)

    args = parser.parse_args(argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {
            "bootstrap",
            "connect",
            "codex-cli-bootstrap-message",
            "codex-cli-bounded-visible-pilot-adapter",
            "codex-cli-exec-handoff",
            "codex-cli-visible-first-response-capture-plan",
            "codex-cli-local-driver-plan",
            "codex-cli-local-scheduler-exec",
            "codex-cli-local-scheduler-tick",
            "codex-cli-one-message-loop-pilot",
            "codex-cli-runtime-idle-detector",
            "codex-cli-session-probe",
            "codex-cli-visible-attach-acceptance",
            "codex-cli-visible-local-driver-pilot",
            "codex-cli-visible-driver-run",
            "codex-cli-visible-driver-plan",
            "codex-cli-visible-session-proof",
            "demo",
            "doctor",
            "new-project-prompt",
            "heartbeat-prompt",
            "sync-global",
            "version",
        }
        and not user_supplied_registry(argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    if args.command == "version":
        print_payload(build_version_payload(), args.format, render_version_markdown)
        return 0

    bootstrap_connect_result = handle_bootstrap_connect_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
    if bootstrap_connect_result is not None:
        return bootstrap_connect_result

    if args.command == "new-project-prompt":
        return handle_new_project_prompt_command(args, print_payload)

    if args.command == "codex-cli-bootstrap-message":
        return handle_codex_cli_bootstrap_message_command(args, print_payload)

    if args.command == "codex-cli-tui-bootstrap-smoke-bundle":
        return handle_codex_cli_tui_bootstrap_smoke_bundle_command(args, print_payload)

    if args.command == "codex-cli-one-message-loop-pilot":
        return handle_codex_cli_one_message_loop_pilot_command(args, print_payload)

    if args.command == "codex-cli-visible-local-driver-pilot":
        return handle_codex_cli_visible_local_driver_pilot_command(args, print_payload)

    if args.command == "codex-cli-bounded-visible-pilot-adapter":
        return handle_codex_cli_bounded_visible_pilot_adapter_command(args, print_payload)

    if args.command == "codex-cli-visible-first-response-capture-plan":
        return handle_codex_cli_visible_first_response_capture_plan_command(args, print_payload)

    if args.command == "codex-cli-visible-attach-acceptance":
        return handle_codex_cli_visible_attach_acceptance_command(args, print_payload)

    if args.command == "codex-cli-exec-handoff":
        return handle_codex_cli_exec_handoff_command(args, print_payload)

    if args.command == "codex-cli-session-probe":
        return handle_codex_cli_session_probe_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-plan":
        return handle_codex_cli_visible_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-local-driver-plan":
        return handle_codex_cli_local_driver_plan_command(args, print_payload)

    if args.command == "codex-cli-visible-driver-run":
        return handle_codex_cli_visible_driver_run_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-tick":
        return handle_codex_cli_local_scheduler_tick_command(args, print_payload)

    if args.command == "codex-cli-local-scheduler-exec":
        return handle_codex_cli_local_scheduler_exec_command(args, print_payload)

    if args.command == "codex-cli-visible-session-proof":
        return handle_codex_cli_visible_session_proof_command(args, print_payload)

    if args.command == "codex-cli-runtime-idle-detector":
        return handle_codex_cli_runtime_idle_detector_command(args, print_payload)

    if args.command == "demo":
        return handle_demo_command(args, print_payload)

    if args.command == "doctor":
        return handle_doctor_command(args, print_payload)

    worker_bridge_result = handle_worker_bridge_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if worker_bridge_result is not None:
        return worker_bridge_result

    support_control_result = handle_support_control_command(
        args,
        registry_path=registry_path,
        registry_was_supplied=user_supplied_registry(argv),
        print_payload=print_payload,
        output_format=output_format,
    )
    if support_control_result is not None:
        return support_control_result

    if args.command == "ml-experiment":
        return handle_ml_experiment_command(args, output_format=output_format, print_payload=print_payload)

    registry_admin_result = handle_registry_admin_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
    if registry_admin_result is not None:
        return registry_admin_result

    benchmark_result = handle_benchmark_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
        append_benchmark_run_rollout_event=append_benchmark_run_rollout_event,
    )
    if benchmark_result is not None:
        return benchmark_result
    if args.command == "history":
        return handle_history_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_benchmark_run_rollout_event=append_benchmark_run_rollout_event,
            append_benchmark_result_rollout_event=append_benchmark_result_rollout_event,
        )

    project_lifecycle_result = handle_project_lifecycle_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
        append_cli_rollout_event=append_cli_rollout_event,
    )
    if project_lifecycle_result is not None:
        return project_lifecycle_result

    if args.command == "check":
        return handle_check_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            allow_missing_registry=not user_supplied_registry(argv),
            print_payload=print_payload,
        )

    if args.command == "status":
        return handle_status_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "diagnose":
        return handle_diagnose_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "review-packet":
        return handle_review_packet_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "dreaming":
        return handle_dreaming_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    if args.command == "todo":
        return handle_todo_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_cli_rollout_event=append_cli_rollout_event,
        )

    if args.command == "quota":
        return handle_quota_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_cli_rollout_event=append_cli_rollout_event,
        )

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
