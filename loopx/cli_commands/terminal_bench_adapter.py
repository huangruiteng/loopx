from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.terminal_bench import (
    TERMINAL_BENCH_DEFAULT_DATASET,
    TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
    TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
    build_terminal_bench_remote_executor_command_adapter,
    build_terminal_bench_remote_executor_launch_adapter,
    build_terminal_bench_remote_executor_materializer,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

TERMINAL_BENCH_ADAPTER_COMMANDS = {
    "terminal-bench-command-adapter",
    "terminal-bench-remote-materializer",
    "terminal-bench-remote-launch-adapter",
}


def render_terminal_bench_remote_executor_command_adapter_markdown(
    payload: dict[str, object],
) -> str:
    adapter = (
        payload.get("command_adapter")
        if isinstance(payload.get("command_adapter"), dict)
        else {}
    )
    boundary = (
        adapter.get("boundary") if isinstance(adapter.get("boundary"), dict) else {}
    )
    surface_contract = (
        adapter.get("surface_contract")
        if isinstance(adapter.get("surface_contract"), dict)
        else {}
    )
    local_driver_contract = (
        adapter.get("local_driver_contract")
        if isinstance(adapter.get("local_driver_contract"), dict)
        else {}
    )
    remote_sandbox_contract = (
        adapter.get("remote_sandbox_contract")
        if isinstance(adapter.get("remote_sandbox_contract"), dict)
        else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Command Adapter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Command adapter ready: `{adapter.get('command_adapter_ready')}`",
        f"- Result reducer ready: `{adapter.get('result_reducer_ready')}`",
        "- Remote materializer ready: "
        f"`{surface_contract.get('remote_materializer_ready')}`",
        f"- Entrypoint label: `{adapter.get('entrypoint_label')}`",
        f"- Result reducer label: `{adapter.get('result_reducer_label')}`",
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Local Driver And Remote Sandbox",
        "",
        f"- Local driver ready: `{local_driver_contract.get('ready')}`",
        f"- Local driver label: `{local_driver_contract.get('driver_label')}`",
        f"- Remote sandbox ready: `{remote_sandbox_contract.get('ready')}`",
        f"- Remote sandbox label: `{remote_sandbox_contract.get('sandbox_label')}`",
        "",
        "## Boundary",
        "",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def render_terminal_bench_remote_executor_materializer_markdown(
    payload: dict[str, object],
) -> str:
    materializer = (
        payload.get("materializer")
        if isinstance(payload.get("materializer"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Materializer",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Entrypoint label: `{materializer.get('entrypoint_label')}`",
        f"- Manifest read: `{materializer.get('handle_manifest_read')}`",
        "- Public handle values recorded: "
        f"`{materializer.get('public_handle_values_recorded')}`",
        "- Local Codex driver ready: "
        f"`{materializer.get('local_codex_driver_ready')}`",
        "- Remote agent runtime required: "
        f"`{materializer.get('remote_agent_runtime_required')}`",
        "- Remote Codex runtime required: "
        f"`{materializer.get('remote_codex_runtime_required')}`",
        "- Present handle fields: "
        + ", ".join(f"`{item}`" for item in materializer.get("present_handle_fields", [])),
        "- Missing handle fields: "
        + ", ".join(f"`{item}`" for item in materializer.get("missing_handle_fields", [])),
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Boundary",
        "",
        f"- Compact only: `{boundary.get('compact_only')}`",
        f"- Local Codex driver required: `{boundary.get('local_codex_driver_required')}`",
        f"- Remote agent runtime allowed: `{boundary.get('remote_agent_runtime_allowed')}`",
        f"- Remote Codex runtime allowed: `{boundary.get('remote_codex_runtime_allowed')}`",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- remote path embedded: `{boundary.get('remote_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        "- Codex credentials synced to remote: "
        f"`{boundary.get('codex_credentials_synced_to_remote')}`",
        "- Remote model API invocation allowed: "
        f"`{boundary.get('remote_model_api_invocation_allowed')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def render_terminal_bench_remote_executor_launch_adapter_markdown(
    payload: dict[str, object],
) -> str:
    launch_adapter = (
        payload.get("launch_adapter")
        if isinstance(payload.get("launch_adapter"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Terminal-Bench Remote Executor Launch Adapter",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Benchmark: `{payload.get('benchmark_id')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        "- Ready to request remote sandbox: "
        f"`{launch_adapter.get('ready_to_request_remote_sandbox')}`",
        "- Remote launch result read: "
        f"`{launch_adapter.get('remote_launch_result_read')}`",
        "- Local Codex driver ready: "
        f"`{launch_adapter.get('local_codex_driver_ready')}`",
        "- Remote sandbox ready: "
        f"`{launch_adapter.get('remote_sandbox_ready')}`",
        "- Missing request fields: "
        + ", ".join(
            f"`{item}`" for item in launch_adapter.get("missing_request_fields", [])
        ),
        "- Missing launch result fields: "
        + ", ".join(
            f"`{item}`"
            for item in launch_adapter.get("missing_launch_result_fields", [])
        ),
        f"- Next action: {payload.get('next_action')}",
        "",
        "## Boundary",
        "",
        f"- Compact only: `{boundary.get('compact_only')}`",
        f"- Shell command embedded: `{boundary.get('shell_command_embedded')}`",
        f"- argv embedded: `{boundary.get('argv_embedded')}`",
        f"- host path embedded: `{boundary.get('host_path_embedded')}`",
        f"- remote path embedded: `{boundary.get('remote_path_embedded')}`",
        f"- raw task text public: `{boundary.get('raw_task_text_public')}`",
        f"- raw logs public: `{boundary.get('raw_logs_public')}`",
        "- Codex credentials synced to remote: "
        f"`{boundary.get('codex_credentials_synced_to_remote')}`",
        "- Remote model API invocation allowed: "
        f"`{boundary.get('remote_model_api_invocation_allowed')}`",
        f"- upload allowed: `{boundary.get('upload_allowed')}`",
        f"- submit allowed: `{boundary.get('submit_allowed')}`",
    ]
    blockers = payload.get("blockers")
    if isinstance(blockers, list) and blockers:
        lines.append("- Blockers: " + ", ".join(f"`{item}`" for item in blockers))
    return "\n".join(lines) + "\n"


def register_terminal_bench_adapter_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    terminal_bench_command_adapter_parser = benchmark_subparsers.add_parser(
        "terminal-bench-command-adapter",
        help=(
            "Emit Terminal-Bench command-adapter facts for the split-control "
            "execution seam. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_command_adapter_parser)
    terminal_bench_command_adapter_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--launch-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing launch surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--poll-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact poll surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--resume-surface-not-ready",
        action="store_true",
        help="Fixture flag for a missing no-upload resume surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--compact-ingest-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact Harbor result ingest surface.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--result-reducer-not-ready",
        action="store_true",
        help="Fixture flag for a missing compact result reducer.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--remote-materializer-ready",
        action="store_true",
        help=(
            "Declare that a real remote-executor materializer exists for the "
            "adapter labels. Omit until the runner can actually stage and poll "
            "remote Docker/runner/data handles."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help=(
            "Declare that the local Codex driver owns agent/model/auth/state "
            "for the Terminal-Bench case."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--remote-sandbox-ready",
        action="store_true",
        help=(
            "Declare that the remote executor is only a sandbox for "
            "Docker/runner/data execution and compact artifact return."
        ),
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--surface-blocker",
        action="append",
        default=[],
        help="Public-safe adapter blocker label. Repeat as needed.",
    )
    terminal_bench_command_adapter_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the adapter facts are ready.",
    )

    terminal_bench_remote_materializer_parser = benchmark_subparsers.add_parser(
        "terminal-bench-remote-materializer",
        help=(
            "Reduce private Terminal-Bench remote-executor handles to a "
            "public-safe materializer payload. This does not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_remote_materializer_parser)
    terminal_bench_remote_materializer_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--handle-manifest-json",
        help=(
            "Path to a private JSON object with remote-executor handle fields. "
            "Only field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--handle-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture field name to mark present without reading a "
            "private manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--no-upload-disabled",
        action="store_true",
        help="Fixture flag proving upload-enabled runs are blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help=(
            "Declare that a local Codex driver can control the case while the "
            "remote executor owns only Docker/runner/data work."
        ),
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-agent-runtime-required",
        action="store_true",
        help="Fixture flag proving remote agent-runtime execution is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-codex-runtime-required",
        action="store_true",
        help="Fixture flag proving remote Codex-runtime execution is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--local-codex-credential-sync",
        action="store_true",
        help="Fixture flag proving Codex credential sync to remote is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--remote-model-invocation",
        action="store_true",
        help="Fixture flag proving remote model invocation is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--raw-material-allowed",
        action="store_true",
        help="Fixture flag proving raw task/log/trajectory exposure is blocked.",
    )
    terminal_bench_remote_materializer_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the materializer payload is ready.",
    )

    terminal_bench_remote_launch_adapter_parser = benchmark_subparsers.add_parser(
        "terminal-bench-remote-launch-adapter",
        help=(
            "Reduce a local-driver request plus private remote launch result "
            "to public-safe Terminal-Bench launch-adapter facts. This does "
            "not execute benchmarks."
        ),
    )
    add_subcommand_format(terminal_bench_remote_launch_adapter_parser)
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "benchmark_name",
        choices=["terminal-bench"],
        help="Benchmark family. Only terminal-bench is supported.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--benchmark-id",
        default=TERMINAL_BENCH_DEFAULT_DATASET,
        help="Public-safe split-control benchmark id.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--request-json",
        help=(
            "Path to a private local-driver request JSON object. Only required "
            "field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--request-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture request field name to mark present without "
            "reading a private request manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--launch-result-json",
        help=(
            "Path to a private remote launch result JSON object. Only required "
            "handle field presence is emitted; values are never printed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--launch-result-field",
        action="append",
        default=[],
        help=(
            "Public-safe fixture launch-result field name to mark present "
            "without reading a private result manifest. Repeat as needed."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--local-codex-driver-ready",
        action="store_true",
        help="Declare that the local Codex driver owns auth/model/state.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-sandbox-ready",
        action="store_true",
        help=(
            "Declare that the remote executor is only a Docker/runner/data "
            "sandbox and can return compact launch results."
        ),
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--no-upload-disabled",
        action="store_true",
        help="Fixture flag proving upload-enabled runs are blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving submit-enabled runs are blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--local-codex-credential-sync",
        action="store_true",
        help="Fixture flag proving Codex credential sync to remote is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-agent-runtime-required",
        action="store_true",
        help="Fixture flag proving remote agent-runtime execution is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-codex-runtime-required",
        action="store_true",
        help="Fixture flag proving remote Codex-runtime execution is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--remote-model-invocation",
        action="store_true",
        help="Fixture flag proving remote model invocation is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--raw-material-allowed",
        action="store_true",
        help="Fixture flag proving raw task/log/trajectory exposure is blocked.",
    )
    terminal_bench_remote_launch_adapter_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the launch adapter is ready.",
    )


def handle_terminal_bench_adapter_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in TERMINAL_BENCH_ADAPTER_COMMANDS:
        return None

    if args.benchmark_command == "terminal-bench-command-adapter":
        try:
            if args.benchmark_name != "terminal-bench":
                raise ValueError("only terminal-bench is supported")
            payload = build_terminal_bench_remote_executor_command_adapter(
                benchmark_id=args.benchmark_id,
                launch_surface_ready=not bool(args.launch_surface_not_ready),
                poll_surface_ready=not bool(args.poll_surface_not_ready),
                resume_surface_ready=not bool(args.resume_surface_not_ready),
                compact_ingest_ready=not bool(args.compact_ingest_not_ready),
                result_reducer_ready=not bool(args.result_reducer_not_ready),
                remote_materializer_ready=bool(args.remote_materializer_ready),
                local_codex_driver_ready=bool(args.local_codex_driver_ready),
                remote_sandbox_ready=bool(args.remote_sandbox_ready),
                no_upload=not bool(args.submit_enabled),
                submit_enabled=bool(args.submit_enabled),
                known_blockers=args.surface_blocker,
            )
            payload["ok"] = True
            payload["dry_run"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "terminal_bench_command_adapter_not_ready"
                )
            payload["require_ready"] = bool(args.require_ready)
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": True,
                "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_COMMAND_ADAPTER_SCHEMA,
                "error": str(exc),
                "read_boundary": {
                    "compact_only": True,
                    "shell_commands_read": False,
                    "argv_read": False,
                    "raw_task_text_read": False,
                    "raw_logs_read": False,
                    "trajectory_read": False,
                    "local_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                    "submit_invoked": False,
                },
            }
        print_payload(
            payload,
            output_format(args),
            render_terminal_bench_remote_executor_command_adapter_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "terminal-bench-remote-materializer":
        try:
            if args.benchmark_name != "terminal-bench":
                raise ValueError("only terminal-bench is supported")
            handle_manifest = None
            if args.handle_manifest_json:
                try:
                    loaded_manifest = json.loads(
                        Path(args.handle_manifest_json).read_text(
                            encoding="utf-8"
                        )
                    )
                except (OSError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        "private handle manifest could not be read as a JSON object"
                    ) from exc
                if not isinstance(loaded_manifest, dict):
                    raise ValueError("private handle manifest must be a JSON object")
                handle_manifest = loaded_manifest
            payload = build_terminal_bench_remote_executor_materializer(
                benchmark_id=args.benchmark_id,
                handle_manifest=handle_manifest,
                present_handle_fields=args.handle_field,
                no_upload=not bool(args.no_upload_disabled),
                submit_enabled=bool(args.submit_enabled),
                local_codex_driver_ready=bool(args.local_codex_driver_ready),
                remote_agent_runtime_required=bool(
                    args.remote_agent_runtime_required
                ),
                remote_codex_runtime_required=bool(
                    args.remote_codex_runtime_required
                ),
                local_codex_credential_sync=bool(
                    args.local_codex_credential_sync
                ),
                remote_model_invocation=bool(args.remote_model_invocation),
                raw_material_allowed=bool(args.raw_material_allowed),
            )
            payload["ok"] = True
            payload["dry_run"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "terminal_bench_remote_materializer_not_ready"
                )
            payload["require_ready"] = bool(args.require_ready)
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": True,
                "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_MATERIALIZER_SCHEMA,
                "error": str(exc),
                "read_boundary": {
                    "compact_only": True,
                    "handle_manifest_values_recorded": False,
                    "shell_commands_read": False,
                    "argv_read": False,
                    "raw_task_text_read": False,
                    "raw_logs_read": False,
                    "trajectory_read": False,
                    "local_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                    "submit_invoked": False,
                },
            }
        print_payload(
            payload,
            output_format(args),
            render_terminal_bench_remote_executor_materializer_markdown,
        )
        return 0 if payload.get("ok") else 1

    def read_private_manifest(path_text: str | None, label: str) -> dict[str, object] | None:
        if not path_text:
            return None
        try:
            loaded = json.loads(
                Path(path_text).expanduser().read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"{label} could not be read as a JSON object"
            ) from exc
        if not isinstance(loaded, dict):
            raise ValueError(f"{label} must be a JSON object")
        return loaded

    try:
        if args.benchmark_name != "terminal-bench":
            raise ValueError("only terminal-bench is supported")
        request_manifest = read_private_manifest(
            args.request_json,
            "--request-json",
        )
        launch_result_manifest = read_private_manifest(
            args.launch_result_json,
            "--launch-result-json",
        )
        payload = build_terminal_bench_remote_executor_launch_adapter(
            benchmark_id=args.benchmark_id,
            request_manifest=request_manifest,
            present_request_fields=args.request_field,
            launch_result_manifest=launch_result_manifest,
            present_launch_result_fields=args.launch_result_field,
            local_codex_driver_ready=bool(args.local_codex_driver_ready),
            remote_sandbox_ready=bool(args.remote_sandbox_ready),
            no_upload=not bool(args.no_upload_disabled),
            submit_enabled=bool(args.submit_enabled),
            local_codex_credential_sync=bool(
                args.local_codex_credential_sync
            ),
            remote_agent_runtime_required=bool(
                args.remote_agent_runtime_required
            ),
            remote_codex_runtime_required=bool(
                args.remote_codex_runtime_required
            ),
            remote_model_invocation=bool(args.remote_model_invocation),
            raw_material_allowed=bool(args.raw_material_allowed),
        )
        payload["ok"] = True
        payload["dry_run"] = True
        if args.require_ready and payload.get("ready") is not True:
            payload["ok"] = False
            payload["error"] = (
                payload.get("first_blocker")
                or "terminal_bench_remote_launch_adapter_not_ready"
            )
        payload["require_ready"] = bool(args.require_ready)
    except Exception as exc:
        payload = {
            "ok": False,
            "dry_run": True,
            "schema_version": TERMINAL_BENCH_REMOTE_EXECUTOR_LAUNCH_ADAPTER_SCHEMA,
            "error": str(exc),
            "read_boundary": {
                "compact_only": True,
                "request_manifest_values_recorded": False,
                "launch_result_values_recorded": False,
                "shell_commands_read": False,
                "argv_read": False,
                "raw_task_text_read": False,
                "raw_logs_read": False,
                "trajectory_read": False,
                "local_paths_recorded": False,
                "remote_paths_recorded": False,
                "docker_invoked": False,
                "model_api_invoked": False,
                "upload_invoked": False,
                "submit_invoked": False,
            },
        }
    print_payload(
        payload,
        output_format(args),
        render_terminal_bench_remote_executor_launch_adapter_markdown,
    )
    return 0 if payload.get("ok") else 1
