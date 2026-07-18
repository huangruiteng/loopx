from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .capabilities.content_ops.cli import (
    handle_content_ops_command,
    register_content_ops_commands,
)
from .capabilities.issue_fix.cli import (
    handle_issue_fix_command,
    register_issue_fix_commands,
)
from .capabilities.reward_memory.cli import (
    handle_reward_memory_command,
    register_reward_memory_commands,
)
from .capabilities.review_batch.cli import (
    handle_review_batch_command,
    register_review_batch_commands,
)
from .capabilities.semantic_preference.cli import (
    handle_semantic_preference_command,
    register_semantic_preference_commands,
)
from .capabilities.auto_research.cli import (
    handle_auto_research_command,
    register_auto_research_commands,
    rewrite_auto_research_question_argv,
)
from .capabilities.value_connectors.cli import (
    handle_value_connector_command,
    register_value_connector_commands,
)
from .cli_commands import (
    handle_turn_command,
    handle_benchmark_command,
    handle_bootstrap_connect_command,
    handle_canary_command,
    handle_capability_command,
    handle_check_command,
    handle_diagnose_command,
    handle_doctor_command,
    handle_dreaming_command,
    handle_evidence_log_command,
    handle_extension_command,
    handle_explore_command,
    handle_history_command,
    handle_lark_inbox_command,
    handle_lark_kanban_command,
    handle_ml_experiment_command,
    handle_multi_agent_command,
    handle_preset_command,
    handle_presentation_command,
    handle_project_lifecycle_command,
    handle_pr_review_command,
    handle_quota_command,
    handle_ready_score_command,
    handle_registry_admin_command,
    handle_review_packet_command,
    handle_slash_commands_command,
    handle_status_command,
    handle_starter_command,
    handle_summary_all_command,
    handle_support_control_command,
    handle_task_lease_command,
    handle_todo_command,
    handle_version_command,
    handle_worker_bridge_command,
    register_benchmark_command_group,
    register_turn_commands,
    register_bootstrap_connect_command,
    register_canary_commands,
    register_capability_commands,
    register_doctor_command,
    register_dreaming_commands,
    register_evidence_log_command,
    register_extension_commands,
    register_explore_commands,
    register_history_command,
    register_lark_inbox_commands,
    register_lark_kanban_commands,
    register_ml_experiment_commands,
    register_multi_agent_commands,
    register_preset_commands,
    register_presentation_commands,
    register_project_lifecycle_commands,
    register_pr_review_command,
    register_quota_command,
    register_ready_score_command,
    register_registry_admin_commands,
    register_slash_commands_command,
    register_starter_commands,
    register_status_commands,
    register_summary_all_command,
    register_support_control_commands,
    register_task_lease_command,
    register_todo_command,
    register_version_command,
    register_worker_bridge_commands,
)
from .cli_rollout import (
    append_benchmark_result_rollout_event,
    append_benchmark_run_rollout_event,
    append_cli_rollout_event,
)
from .help_surface import (
    build_command_reference_payload,
    render_command_reference_markdown,
    render_concise_help,
    top_level_help_requested,
)
from .paths import DEFAULT_RUNTIME_ROOT, default_registry_path, global_registry_path


class LoopXArgumentParser(argparse.ArgumentParser):
    """Require complete option names across the automation-facing CLI."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def print_payload(payload: dict[str, object], fmt: str, markdown_renderer) -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(markdown_renderer(payload))


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
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    if top_level_help_requested(raw_argv):
        print(render_concise_help(sys.argv[0] if argv is None else "loopx"), end="")
        return 0
    raw_argv = rewrite_auto_research_question_argv(raw_argv)

    parser = LoopXArgumentParser(description="LoopX control-plane helper.")
    parser.add_argument("--version", action="version", version=f"loopx {__version__}")
    parser.add_argument("--registry", default=str(default_registry_path()), help="Path to a project-local registry.")
    parser.add_argument("--runtime-root", help="Override registry common_runtime_root.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sub = parser.add_subparsers(dest="command", required=True)

    register_version_command(sub, add_subcommand_format)

    commands_parser = sub.add_parser(
        "commands",
        help="Show grouped LoopX command reference for operators and contributors.",
    )
    add_subcommand_format(commands_parser)

    register_bootstrap_connect_command(sub)

    register_starter_commands(sub)

    register_doctor_command(sub)

    register_worker_bridge_commands(sub, add_subcommand_format)

    register_support_control_commands(sub, add_subcommand_format)

    register_canary_commands(sub, add_subcommand_format)

    register_capability_commands(sub, add_subcommand_format)

    register_extension_commands(sub, add_subcommand_format)

    register_content_ops_commands(sub, add_subcommand_format)

    register_issue_fix_commands(sub, add_subcommand_format)

    register_reward_memory_commands(sub, add_subcommand_format)

    register_review_batch_commands(sub, add_subcommand_format)

    register_semantic_preference_commands(sub, add_subcommand_format)

    register_value_connector_commands(sub, add_subcommand_format)

    register_ml_experiment_commands(sub, add_subcommand_format)

    register_auto_research_commands(sub, add_subcommand_format)

    register_multi_agent_commands(sub, add_subcommand_format)
    register_turn_commands(sub, add_subcommand_format)
    register_preset_commands(sub, add_subcommand_format)
    register_presentation_commands(sub, add_subcommand_format)
    register_ready_score_command(sub, add_subcommand_format)

    register_registry_admin_commands(sub)

    register_history_command(sub)

    register_benchmark_command_group(sub, add_subcommand_format)

    register_project_lifecycle_commands(sub, add_subcommand_format)
    register_lark_inbox_commands(sub, add_subcommand_format)
    register_lark_kanban_commands(sub, add_subcommand_format)

    register_status_commands(sub, add_subcommand_format)
    register_summary_all_command(sub, add_subcommand_format)
    register_pr_review_command(sub, add_subcommand_format)
    register_slash_commands_command(sub, add_subcommand_format)
    register_dreaming_commands(sub, add_subcommand_format)
    register_evidence_log_command(sub, add_subcommand_format)
    register_explore_commands(sub, add_subcommand_format)
    register_todo_command(sub)
    register_task_lease_command(sub, add_subcommand_format)
    register_quota_command(sub)

    args = parser.parse_args(raw_argv)
    registry_path = Path(args.registry).expanduser()
    if (
        args.command
        not in {
            "bootstrap",
            "bootstrap-command-pack",
            "agent-onboard",
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
            "canary",
            "demo",
            "doctor",
            "new-project-prompt",
            "start-goal",
            "slash-commands",
            "heartbeat-prompt",
            "supervisor-event",
            "supervisor-observe",
            "supervisor-prompt",
            "sync-global",
            "uninstall-project",
            "version",
        }
        and not user_supplied_registry(raw_argv)
        and not registry_path.exists()
    ):
        runtime_root = Path(args.runtime_root).expanduser() if args.runtime_root else DEFAULT_RUNTIME_ROOT
        fallback_registry = global_registry_path(runtime_root)
        if fallback_registry.exists():
            registry_path = fallback_registry

    version_result = handle_version_command(args, output_format=output_format, print_payload=print_payload)
    if version_result is not None:
        return version_result

    if args.command == "commands":
        print_payload(
            build_command_reference_payload(),
            output_format(args),
            render_command_reference_markdown,
        )
        return 0

    bootstrap_connect_result = handle_bootstrap_connect_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
    if bootstrap_connect_result is not None:
        return bootstrap_connect_result

    starter_result = handle_starter_command(args, print_payload)
    if starter_result is not None:
        return starter_result

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
        registry_was_supplied=user_supplied_registry(raw_argv),
        print_payload=print_payload,
        output_format=output_format,
    )
    if support_control_result is not None:
        return support_control_result

    canary_result = handle_canary_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if canary_result is not None:
        return canary_result

    capability_result = handle_capability_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if capability_result is not None:
        return capability_result

    extension_result = handle_extension_command(
        args,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if extension_result is not None:
        return extension_result

    if args.command == "ml-experiment":
        return handle_ml_experiment_command(args, output_format=output_format, print_payload=print_payload)

    if args.command == "auto-research":
        return handle_auto_research_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    multi_agent_result = handle_multi_agent_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if multi_agent_result is not None:
        return multi_agent_result

    turn_result = handle_turn_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if turn_result is not None:
        return turn_result

    preset_result = handle_preset_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if preset_result is not None:
        return preset_result

    presentation_result = handle_presentation_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if presentation_result is not None:
        return presentation_result

    ready_score_result = handle_ready_score_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if ready_score_result is not None:
        return ready_score_result

    if args.command == "content-ops":
        return handle_content_ops_command(args, output_format=output_format, print_payload=print_payload)

    if args.command == "issue-fix":
        return handle_issue_fix_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    reward_memory_result = handle_reward_memory_command(
        args,
        registry_path=registry_path,
        output_format=output_format,
        print_payload=print_payload,
    )
    if reward_memory_result is not None:
        return reward_memory_result

    review_batch_result = handle_review_batch_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if review_batch_result is not None:
        return review_batch_result

    semantic_preference_result = handle_semantic_preference_command(
        args,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if semantic_preference_result is not None:
        return semantic_preference_result

    if args.command == "value-connectors":
        return handle_value_connector_command(args, output_format=output_format, print_payload=print_payload)

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

    lark_kanban_result = handle_lark_kanban_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
    )
    if lark_kanban_result is not None:
        return lark_kanban_result

    lark_inbox_result = handle_lark_inbox_command(
        args,
        registry_path=registry_path,
        output_format=output_format,
        print_payload=print_payload,
    )
    if lark_inbox_result is not None:
        return lark_inbox_result

    if args.command == "check":
        return handle_check_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            allow_missing_registry=not user_supplied_registry(raw_argv),
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

    summary_all_result = handle_summary_all_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if summary_all_result is not None:
        return summary_all_result

    pr_review_result = handle_pr_review_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if pr_review_result is not None:
        return pr_review_result

    slash_commands_result = handle_slash_commands_command(
        args,
        output_format=output_format,
        print_payload=print_payload,
    )
    if slash_commands_result is not None:
        return slash_commands_result

    if args.command == "dreaming":
        return handle_dreaming_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            output_format=output_format,
            print_payload=print_payload,
        )

    evidence_log_result = handle_evidence_log_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if evidence_log_result is not None:
        return evidence_log_result

    explore_result = handle_explore_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        print_payload=print_payload,
        output_format=output_format,
    )
    if explore_result is not None:
        return explore_result

    if args.command == "todo":
        return handle_todo_command(
            args,
            registry_path=registry_path,
            runtime_root_arg=args.runtime_root,
            print_payload=print_payload,
            append_cli_rollout_event=append_cli_rollout_event,
        )

    task_lease_result = handle_task_lease_command(
        args,
        registry_path=registry_path,
        runtime_root_arg=args.runtime_root,
        output_format=output_format,
        print_payload=print_payload,
    )
    if task_lease_result is not None:
        return task_lease_result

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
