from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_core import (
    build_benchmark_candidate_source_boundary,
    build_split_control_remote_executor_execution_seam,
    build_split_control_remote_executor_launch_plan,
    build_split_control_remote_executor_runner_batch,
    filter_public_benchmark_artifact_paths,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_BOUNDARY_COMMANDS = {
    "classify-artifacts",
    "candidate-source-boundary",
    "split-control-execution-seam",
}


def render_benchmark_artifact_path_filter_markdown(payload: dict[str, object]) -> str:
    artifact_policy = (
        payload.get("artifact_policy")
        if isinstance(payload.get("artifact_policy"), dict)
        else {}
    )
    lines = [
        "# Benchmark Artifact Path Filter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Adapter policy: `{artifact_policy.get('adapter_kind')}`",
        f"- Allowed to read: `{payload.get('allowed_to_read_count')}`",
        f"- Blocked: `{payload.get('blocked_count')}`",
        f"- Full paths recorded: `{payload.get('path_recorded')}`",
    ]
    allowed = payload.get("allowed_artifact_basenames")
    if isinstance(allowed, list) and allowed:
        lines.append("- Allowed basenames: " + ", ".join(f"`{item}`" for item in allowed))
    blocked = payload.get("blocked_reasons")
    if isinstance(blocked, dict) and blocked:
        reasons = ", ".join(f"`{key}`={value}" for key, value in blocked.items())
        lines.append("- Blocked reasons: " + reasons)
    return "\n".join(lines) + "\n"


def render_benchmark_candidate_source_boundary_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Benchmark Candidate Source Boundary",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Clean: `{payload.get('clean')}`",
        f"- Allowed: `{payload.get('allowed_source_count')}`",
        f"- Blocked: `{payload.get('blocked_source_count')}`",
        f"- Paths recorded: `{payload.get('path_recorded')}`",
    ]
    blocked = payload.get("blocked_reasons")
    if isinstance(blocked, dict) and blocked:
        reasons = ", ".join(f"`{key}`={value}" for key, value in blocked.items())
        lines.append("- Blocked reasons: " + reasons)
    if payload.get("next_action"):
        lines.append(f"- Next action: {payload.get('next_action')}")
    return "\n".join(lines) + "\n"


def render_split_control_execution_seam_markdown(payload: dict[str, object]) -> str:
    cases = payload.get("execution_cases") if isinstance(payload.get("execution_cases"), list) else []
    lines = [
        "# Benchmark Split-Control Execution Seam",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready to execute: `{payload.get('ready_to_execute')}`",
        f"- Ready to spend: `{payload.get('ready_to_spend')}`",
        f"- Cases: `{len(cases)}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    missing_adapters = payload.get("missing_command_adapter_ids")
    if isinstance(missing_adapters, list) and missing_adapters:
        lines.append(
            "- Missing command adapters: "
            + ", ".join(f"`{item}`" for item in missing_adapters)
        )
    missing_reducers = payload.get("missing_result_reducer_ids")
    if isinstance(missing_reducers, list) and missing_reducers:
        lines.append(
            "- Missing result reducers: "
            + ", ".join(f"`{item}`" for item in missing_reducers)
        )
    if payload.get("next_action"):
        lines.append(f"- Next action: {payload.get('next_action')}")
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            f"- Shell commands embedded: `{boundary.get('shell_commands_embedded')}`",
            f"- argv embedded: `{boundary.get('argv_embedded')}`",
            f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
            f"- raw logs public: `{boundary.get('raw_logs_public')}`",
            f"- upload allowed: `{boundary.get('upload_allowed')}`",
            f"- submit allowed: `{boundary.get('submit_allowed')}`",
        ]
    )
    if cases:
        lines.extend(["", "## Cases", ""])
        for case in cases:
            if not isinstance(case, dict):
                continue
            materialization = (
                case.get("command_materialization")
                if isinstance(case.get("command_materialization"), dict)
                else {}
            )
            local_driver = (
                case.get("local_driver_contract")
                if isinstance(case.get("local_driver_contract"), dict)
                else {}
            )
            remote_sandbox = (
                case.get("remote_sandbox_contract")
                if isinstance(case.get("remote_sandbox_contract"), dict)
                else {}
            )
            reducer = case.get("result_reducer") if isinstance(case.get("result_reducer"), dict) else {}
            lines.append(
                "- "
                + f"`{case.get('benchmark_id')}`: command_ready="
                + f"`{materialization.get('ready')}`, reducer_ready="
                + f"`{reducer.get('ready')}`, local_driver="
                + f"`{local_driver.get('ready')}`, remote_sandbox="
                + f"`{remote_sandbox.get('ready')}`, blockers="
                + "`"
                + ",".join(str(item) for item in case.get("blockers", []))
                + "`"
            )
    return "\n".join(lines) + "\n"


def register_benchmark_boundary_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    benchmark_artifact_filter_parser = benchmark_subparsers.add_parser(
        "classify-artifacts",
        help=(
            "Classify benchmark artifact paths before reading them. The classifier "
            "returns basenames and blocker reasons only; it does not read files or "
            "echo host directories."
        ),
    )
    add_subcommand_format(benchmark_artifact_filter_parser)
    benchmark_artifact_filter_parser.add_argument(
        "artifact_paths",
        nargs="+",
        help="Candidate benchmark artifact paths to classify without reading.",
    )
    benchmark_artifact_filter_parser.add_argument(
        "--adapter-kind",
        default="default",
        help=(
            "Benchmark adapter artifact policy key. Unknown values fall back to "
            "default without recording paths."
        ),
    )
    benchmark_artifact_filter_parser.add_argument(
        "--allow-public-filename",
        action="append",
        default=[],
        help=(
            "Additional public compact basename to allow for this classification "
            "run. Only the basename is used and values are filtered."
        ),
    )

    benchmark_candidate_source_parser = benchmark_subparsers.add_parser(
        "candidate-source-boundary",
        help=(
            "Classify candidate-selection source paths before using them. This "
            "does not read files or echo host paths; it blocks raw runner roots, "
            "trial directories, task bodies, trajectories, and Codex transcripts."
        ),
    )
    add_subcommand_format(benchmark_candidate_source_parser)
    benchmark_candidate_source_parser.add_argument(
        "source_paths",
        nargs="+",
        help="Candidate-selection source paths to classify without reading.",
    )
    benchmark_candidate_source_parser.add_argument(
        "--adapter-kind",
        default="default",
        help="Benchmark adapter artifact policy key for compact artifact allowlists.",
    )
    benchmark_candidate_source_parser.add_argument(
        "--allow-public-filename",
        action="append",
        default=[],
        help=(
            "Additional compact/public basename to allow for this classification "
            "run. Only the basename is used and values are filtered."
        ),
    )
    benchmark_candidate_source_parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Return non-zero if any source is blocked.",
    )

    split_control_execution_parser = benchmark_subparsers.add_parser(
        "split-control-execution-seam",
        help=(
            "Build the public-safe execution seam from split-control readiness "
            "and command-adapter facts. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(split_control_execution_parser)
    split_control_execution_parser.add_argument(
        "--readiness-json",
        required=True,
        help=(
            "Path to a benchmark_split_control_remote_executor_readiness_v0 "
            "object. Use '-' to read stdin."
        ),
    )
    split_control_execution_parser.add_argument(
        "--command-adapter-json",
        help=(
            "Optional JSON object keyed by benchmark id with "
            "command_adapter_ready/result_reducer_ready facts. If omitted, "
            "all launch cases are treated as missing command adapters."
        ),
    )
    split_control_execution_parser.add_argument(
        "--execution-mode",
        default="compact_no_upload_dry_run",
        help="Public-safe execution mode label for runner cases.",
    )


def handle_benchmark_boundary_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_BOUNDARY_COMMANDS:
        return None

    if args.benchmark_command == "classify-artifacts":
        payload = filter_public_benchmark_artifact_paths(
            args.artifact_paths,
            adapter_kind=args.adapter_kind,
            extra_public_filenames=args.allow_public_filename,
        )
        print_payload(
            payload,
            output_format(args),
            render_benchmark_artifact_path_filter_markdown,
        )
        return 0

    if args.benchmark_command == "candidate-source-boundary":
        payload = build_benchmark_candidate_source_boundary(
            args.source_paths,
            adapter_kind=args.adapter_kind,
            extra_public_filenames=args.allow_public_filename,
        )
        print_payload(
            payload,
            output_format(args),
            render_benchmark_candidate_source_boundary_markdown,
        )
        if args.require_clean and not payload.get("clean"):
            return 1
        return 0

    def read_json_arg(path_text: str | None, label: str) -> dict[str, object]:
        if not path_text:
            return {}
        raw = sys.stdin.read() if path_text == "-" else Path(path_text).expanduser().read_text(encoding="utf-8")
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ValueError(f"{label} must contain a JSON object")
        return loaded

    try:
        readiness = read_json_arg(args.readiness_json, "--readiness-json")
        command_adapter_payload = read_json_arg(
            args.command_adapter_json,
            "--command-adapter-json",
        )
        command_adapters = (
            command_adapter_payload.get("command_adapters")
            if isinstance(
                command_adapter_payload.get("command_adapters"), dict
            )
            else command_adapter_payload
        )
        launch_plan = build_split_control_remote_executor_launch_plan(
            readiness
        )
        runner_batch = build_split_control_remote_executor_runner_batch(
            launch_plan,
            fresh_readiness=readiness,
            execution_mode=args.execution_mode,
        )
        payload = build_split_control_remote_executor_execution_seam(
            runner_batch,
            command_adapters=command_adapters,
        )
        payload["ok"] = True
        payload["dry_run"] = True
        payload["read_boundary"] = {
            "compact_only": True,
            "readiness_json_read": True,
            "command_adapter_json_read": bool(args.command_adapter_json),
            "command_adapter_wrapper_unwrapped": bool(
                args.command_adapter_json
                and isinstance(
                    command_adapter_payload.get("command_adapters"), dict
                )
            ),
            "raw_task_text_read": False,
            "raw_logs_read": False,
            "trajectory_read": False,
            "shell_commands_read": False,
            "docker_invoked": False,
            "model_api_invoked": False,
            "upload_invoked": False,
            "submit_invoked": False,
        }
    except Exception as exc:
        payload = {
            "ok": False,
            "dry_run": True,
            "schema_version": "benchmark_split_control_remote_executor_execution_seam_v1",
            "error": str(exc),
            "read_boundary": {
                "compact_only": True,
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "trajectory_read": False,
                "shell_commands_read": False,
                "docker_invoked": False,
                "model_api_invoked": False,
                "upload_invoked": False,
                "submit_invoked": False,
            },
        }
    print_payload(
        payload,
        output_format(args),
        render_split_control_execution_seam_markdown,
    )
    return 0 if payload.get("ok") else 1
