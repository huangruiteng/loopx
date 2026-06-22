from __future__ import annotations

import argparse
from collections.abc import Callable

from .agents_last_exam_baked_input import (
    AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS,
    handle_agents_last_exam_baked_input_command,
    register_agents_last_exam_baked_input_commands,
)
from .agents_last_exam_host_codex import (
    AGENTS_LAST_EXAM_HOST_CODEX_COMMANDS,
    handle_agents_last_exam_host_codex_command,
    register_agents_last_exam_host_codex_commands,
)
from .agents_last_exam_local_plan import (
    AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS,
    handle_agents_last_exam_local_plan_command,
    register_agents_last_exam_local_plan_commands,
)
from .agents_last_exam_launch_dry_run import (
    AGENTS_LAST_EXAM_LAUNCH_DRY_RUN_COMMANDS,
    handle_agents_last_exam_launch_dry_run_command,
    register_agents_last_exam_launch_dry_run_commands,
)
from .agents_last_exam_runner_source import (
    AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS,
    handle_agents_last_exam_runner_source_command,
    register_agents_last_exam_runner_source_commands,
)
from .agents_last_exam_task_material import (
    AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS,
    handle_agents_last_exam_task_material_command,
    register_agents_last_exam_task_material_commands,
)
from .agents_last_exam_validation_gate import (
    AGENTS_LAST_EXAM_VALIDATION_GATE_COMMANDS,
    handle_agents_last_exam_validation_gate_command,
    register_agents_last_exam_validation_gate_commands,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_COMMANDS = (
    AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS
    | AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS
    | AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS
    | AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS
    | AGENTS_LAST_EXAM_LAUNCH_DRY_RUN_COMMANDS
    | AGENTS_LAST_EXAM_HOST_CODEX_COMMANDS
    | AGENTS_LAST_EXAM_VALIDATION_GATE_COMMANDS
)


def register_agents_last_exam_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    register_agents_last_exam_local_plan_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_runner_source_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_baked_input_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_task_material_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_launch_dry_run_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_host_codex_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )
    register_agents_last_exam_validation_gate_commands(
        benchmark_subparsers,
        add_subcommand_format,
    )



def handle_agents_last_exam_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_COMMANDS:
        return None

    local_plan_result = handle_agents_last_exam_local_plan_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if local_plan_result is not None:
        return local_plan_result

    runner_source_result = handle_agents_last_exam_runner_source_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if runner_source_result is not None:
        return runner_source_result

    baked_input_result = handle_agents_last_exam_baked_input_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if baked_input_result is not None:
        return baked_input_result

    task_material_result = handle_agents_last_exam_task_material_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if task_material_result is not None:
        return task_material_result

    launch_dry_run_result = handle_agents_last_exam_launch_dry_run_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if launch_dry_run_result is not None:
        return launch_dry_run_result

    host_codex_result = handle_agents_last_exam_host_codex_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if host_codex_result is not None:
        return host_codex_result

    validation_gate_result = handle_agents_last_exam_validation_gate_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if validation_gate_result is not None:
        return validation_gate_result

    return None
