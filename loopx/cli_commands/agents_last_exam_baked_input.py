from __future__ import annotations

import argparse
from collections.abc import Callable

from ..benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    build_agents_last_exam_baked_task_input_readiness,
    build_agents_last_exam_baked_task_input_scan,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS = {
    "ale-baked-task-input-readiness",
    "ale-baked-task-input-scan",
}


def render_agents_last_exam_baked_task_input_readiness_markdown(
    payload: dict[str, object],
) -> str:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    image = payload.get("image") if isinstance(payload.get("image"), dict) else {}
    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Baked Task Input Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected task: `{task.get('task_id')}`",
        f"- Image present: `{image.get('present')}`",
        f"- Probe attempted/container started: `{probe.get('attempted')}`/`{probe.get('container_started')}`",
        f"- Baked input present/readable: `{probe.get('baked_input_present')}`/`{probe.get('baked_input_readable')}`",
        f"- Expected path recorded: `{probe.get('expected_path_recorded')}`",
        f"- Task run/model/upload/submit: `{boundary.get('task_run_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Task data content read: `{boundary.get('task_data_content_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_baked_task_input_scan_markdown(
    payload: dict[str, object],
) -> str:
    selected = (
        payload.get("selected_tasks")
        if isinstance(payload.get("selected_tasks"), dict)
        else {}
    )
    probe = payload.get("probe") if isinstance(payload.get("probe"), dict) else {}
    candidates = (
        payload.get("candidates")
        if isinstance(payload.get("candidates"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Baked Task Input Scan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected/probed tasks: `{selected.get('selected_task_count')}`/`{selected.get('probed_task_count')}`",
        f"- Probe attempted/container started: `{probe.get('attempted')}`/`{probe.get('container_started')}`",
        f"- Baked input candidate count: `{probe.get('baked_input_candidate_count')}`",
        f"- Candidate ids: `{candidates.get('eligible_baked_input_candidates')}`",
        f"- Expected paths/argv/stdout recorded: `{probe.get('expected_path_recorded')}`/`{probe.get('command_argv_recorded')}`/`{probe.get('stdout_recorded')}`",
        f"- Task run/model/upload/submit: `{boundary.get('task_run_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Task data content read/listed: `{boundary.get('task_data_content_read')}`/`{boundary.get('directory_listed')}`",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_baked_input_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_baked_task_input_readiness_parser = benchmark_subparsers.add_parser(
        "ale-baked-task-input-readiness",
        help=(
            "Probe whether a local ALE Docker image contains a selected task's "
            "baked input directory. This may start a tiny shell in Docker, but "
            "it does not run the task, list files, read task data, invoke models, "
            "upload, submit, or record local/container paths."
        ),
    )
    add_subcommand_format(ale_baked_task_input_readiness_parser)
    ale_baked_task_input_readiness_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Local ALE Docker image ref to probe.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="PATH-visible Docker binary name to use.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Timeout for the tiny Docker path-existence probe.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--no-docker-run",
        action="store_true",
        help="Do not start Docker; emit a fixture-like blocked readiness payload.",
    )
    ale_baked_task_input_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the baked task input readiness gate is ready.",
    )

    ale_baked_task_input_scan_parser = benchmark_subparsers.add_parser(
        "ale-baked-task-input-scan",
        help=(
            "Batch-scan public ALE selected tasks for baked input directories in "
            "a local Docker image. This may start one tiny shell in Docker, but "
            "does not run tasks, list files, read task data, invoke models, "
            "upload, submit, or record local/container paths."
        ),
    )
    add_subcommand_format(ale_baked_task_input_scan_parser)
    ale_baked_task_input_scan_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to read selected-task lists from. The path is never recorded.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to scan, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Local ALE Docker image ref to probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--docker-binary",
        default="docker",
        help="PATH-visible Docker binary name to use.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--max-tasks",
        type=int,
        default=120,
        help="Maximum selected public task ids to probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=180,
        help="Timeout for the batch Docker path-existence probe.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--no-docker-run",
        action="store_true",
        help="Do not start Docker; emit a fixture-like blocked scan payload.",
    )
    ale_baked_task_input_scan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless at least one baked-input candidate is found.",
    )


def handle_agents_last_exam_baked_input_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_BAKED_INPUT_COMMANDS:
        return None

    if args.benchmark_command == "ale-baked-task-input-readiness":
        try:
            image_metadata = None
            if args.no_docker_run:
                image_metadata = {
                    "image_ref": args.image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_run_probe_disabled",
                }
            payload = build_agents_last_exam_baked_task_input_readiness(
                selected_task_id=args.selected_task_id,
                image_ref=args.image,
                image_metadata=image_metadata,
                docker_binary=args.docker_binary,
                timeout_seconds=args.timeout_seconds,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_baked_task_input_readiness_v0",
                "error": "ale_baked_task_input_readiness_failed",
                "read_boundary": {
                    "compact_only": True,
                    "path_existence_only": True,
                    "task_text_read": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
                    "task_data_content_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_baked_task_input_readiness_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_baked_task_input_readiness_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-baked-task-input-scan":
        try:
            selected_task_lists = (
                args.selected_task_list
                if args.selected_task_list
                else ["linux_only.txt", "unlicensed/near-term.txt"]
            )
            image_metadata = None
            if args.no_docker_run:
                image_metadata = {
                    "image_ref": args.image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_run_probe_disabled",
                }
            payload = build_agents_last_exam_baked_task_input_scan(
                source_root=args.source_root,
                selected_task_lists=selected_task_lists,
                image_ref=args.image,
                image_metadata=image_metadata,
                docker_binary=args.docker_binary,
                max_tasks=args.max_tasks,
                timeout_seconds=args.timeout_seconds,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_baked_task_input_scan_v0",
                "error": "ale_baked_task_input_scan_failed",
                "read_boundary": {
                    "compact_only": True,
                    "path_existence_only": True,
                    "selected_task_lists_read": True,
                    "task_text_read": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
                    "task_data_content_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_baked_task_input_scan_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_baked_task_input_scan_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
