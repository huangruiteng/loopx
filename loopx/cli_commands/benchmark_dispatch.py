from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from .agents_last_exam import (
    handle_agents_last_exam_command,
    register_agents_last_exam_commands,
)
from .agentissue_runner_flow import (
    handle_agentissue_runner_flow_command,
    register_agentissue_runner_flow_commands,
)
from .benchmark_boundary import (
    handle_benchmark_boundary_command,
    register_benchmark_boundary_commands,
)
from .benchmark_release_outcome import (
    handle_benchmark_release_outcome_command,
    register_benchmark_release_outcome_commands,
)
from .benchmark_review_lifecycle import (
    handle_benchmark_review_lifecycle_command,
    register_benchmark_review_lifecycle_commands,
)
from .benchmark_run_ledger import (
    handle_benchmark_run_ledger_command,
    register_benchmark_run_ledger_commands,
)
from .terminal_bench_adapter import (
    handle_terminal_bench_adapter_command,
    register_terminal_bench_adapter_commands,
)
from .terminal_bench_environment_result import (
    handle_terminal_bench_environment_result_command,
    register_terminal_bench_environment_result_commands,
)


AddSubcommandFormat = Callable[[argparse.ArgumentParser], None]
OutputFormat = Callable[..., str]
PrintPayload = Callable[..., None]
BenchmarkRunRolloutEventAppender = Callable[..., dict[str, object]]


def register_benchmark_command_group(
    subparsers: argparse._SubParsersAction,
    add_subcommand_format: AddSubcommandFormat,
) -> None:
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Benchmark runner skeletons. Current public surface is fixture-only and no-run by default.",
    )
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    register_benchmark_run_ledger_commands(benchmark_sub, add_subcommand_format)

    register_agentissue_runner_flow_commands(benchmark_sub, add_subcommand_format)
    register_benchmark_boundary_commands(benchmark_sub, add_subcommand_format)
    register_benchmark_release_outcome_commands(benchmark_sub, add_subcommand_format)
    register_terminal_bench_adapter_commands(benchmark_sub, add_subcommand_format)

    register_agents_last_exam_commands(benchmark_sub, add_subcommand_format)

    register_benchmark_review_lifecycle_commands(benchmark_sub, add_subcommand_format)
    register_terminal_bench_environment_result_commands(benchmark_sub, add_subcommand_format)


def handle_benchmark_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
    output_format: OutputFormat,
    append_benchmark_run_rollout_event: BenchmarkRunRolloutEventAppender,
) -> int | None:
    if args.command != "benchmark":
        return None

    agentissue_runner_flow_result = handle_agentissue_runner_flow_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
    )
    if agentissue_runner_flow_result is not None:
        return agentissue_runner_flow_result

    benchmark_boundary_result = handle_benchmark_boundary_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if benchmark_boundary_result is not None:
        return benchmark_boundary_result

    release_outcome_result = handle_benchmark_release_outcome_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if release_outcome_result is not None:
        return release_outcome_result

    terminal_bench_adapter_result = handle_terminal_bench_adapter_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if terminal_bench_adapter_result is not None:
        return terminal_bench_adapter_result

    agents_last_exam_result = handle_agents_last_exam_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if agents_last_exam_result is not None:
        return agents_last_exam_result

    benchmark_review_lifecycle_result = handle_benchmark_review_lifecycle_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
    )
    if benchmark_review_lifecycle_result is not None:
        return benchmark_review_lifecycle_result

    terminal_bench_environment_result = handle_terminal_bench_environment_result_command(
        args,
        print_payload=print_payload,
        output_format=output_format,
    )
    if terminal_bench_environment_result is not None:
        return terminal_bench_environment_result

    benchmark_run_ledger_result = handle_benchmark_run_ledger_command(
        args,
        registry_path=registry_path,
        print_payload=print_payload,
        output_format=output_format,
        append_benchmark_run_rollout_event=append_benchmark_run_rollout_event,
    )
    if benchmark_run_ledger_result is not None:
        return benchmark_run_ledger_result

    return None
