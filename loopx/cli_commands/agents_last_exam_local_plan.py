from __future__ import annotations

import argparse
from collections.abc import Callable

from ..benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    build_agents_last_exam_local_dry_run_plan,
    build_agents_last_exam_local_preflight,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS = {
    "ale-local-preflight",
    "ale-local-dry-run-plan",
}


def render_agents_last_exam_local_preflight_markdown(payload: dict[str, object]) -> str:
    provider = (
        payload.get("provider") if isinstance(payload.get("provider"), dict) else {}
    )
    required_image = (
        provider.get("required_image")
        if isinstance(provider.get("required_image"), dict)
        else {}
    )
    boundary = (
        payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Preflight",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Provider: `{provider.get('kind')}`",
        f"- No cloud: `{provider.get('no_cloud')}`",
        f"- Required image present: `{required_image.get('present')}`",
        f"- Required image arch/os: `{required_image.get('architecture')}`/`{required_image.get('os')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_dry_run_plan_markdown(payload: dict[str, object]) -> str:
    adapter_plan = (
        payload.get("adapter_plan")
        if isinstance(payload.get("adapter_plan"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Dry-Run Plan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Mode: `{adapter_plan.get('mode')}`",
        f"- Provider: `{adapter_plan.get('provider')}`",
        f"- Will start container: `{adapter_plan.get('will_start_container')}`",
        f"- Will read task body: `{adapter_plan.get('will_read_task_body')}`",
        f"- Will upload/submit: `{adapter_plan.get('will_upload')}`/`{adapter_plan.get('will_submit')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_local_plan_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_local_preflight_parser = benchmark_subparsers.add_parser(
        "ale-local-preflight",
        help=(
            "Check Agents' Last Exam local no-cloud/no-upload adapter readiness. "
            "This may inspect local Docker image metadata, but it does not start "
            "containers, read task bodies, call model APIs, upload, or claim "
            "leaderboard evidence."
        ),
    )
    add_subcommand_format(ale_local_preflight_parser)
    ale_local_preflight_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_preflight_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_preflight_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_preflight_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_preflight_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is preflight-ready.",
    )
    ale_local_preflight_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the local no-cloud/no-upload preflight is ready.",
    )
    ale_local_preflight_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked preflight. "
            "Used by dependency-free smokes."
        ),
    )

    ale_local_dry_run_plan_parser = benchmark_subparsers.add_parser(
        "ale-local-dry-run-plan",
        help=(
            "Build an Agents' Last Exam local adapter dry-run plan without "
            "running the adapter. This contract-only gate may inspect local "
            "Docker image metadata, but it does not start containers, read task "
            "bodies, invoke model APIs, upload, or claim score evidence."
        ),
    )
    add_subcommand_format(ale_local_dry_run_plan_parser)
    ale_local_dry_run_plan_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is dry-run-plan-ready.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the contract-only dry-run plan is ready.",
    )
    ale_local_dry_run_plan_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked plan. "
            "Used by dependency-free smokes."
        ),
    )


def handle_agents_last_exam_local_plan_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_LOCAL_PLAN_COMMANDS:
        return None

    if args.benchmark_command == "ale-local-preflight":
        try:
            image_metadata = None
            alternate_image_metadata = None
            if args.no_docker_probe:
                image_metadata = {
                    "image_ref": args.image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
                alternate_image_metadata = {
                    "image_ref": args.alternate_image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
            payload = build_agents_last_exam_local_preflight(
                selected_task_id=args.selected_task_id,
                snapshot=args.snapshot,
                provider_kind=args.provider_kind,
                image_ref=args.image,
                alternate_image_ref=args.alternate_image,
                image_metadata=image_metadata,
                alternate_image_metadata=alternate_image_metadata,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_preflight_v0",
                "error": "ale_local_preflight_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
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
                    or "ale_local_preflight_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_preflight_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-local-dry-run-plan":
        try:
            image_metadata = None
            alternate_image_metadata = None
            if args.no_docker_probe:
                image_metadata = {
                    "image_ref": args.image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
                alternate_image_metadata = {
                    "image_ref": args.alternate_image,
                    "present": False,
                    "probe_available": False,
                    "first_blocker": "docker_probe_disabled",
                }
            payload = build_agents_last_exam_local_dry_run_plan(
                selected_task_id=args.selected_task_id,
                snapshot=args.snapshot,
                provider_kind=args.provider_kind,
                image_ref=args.image,
                alternate_image_ref=args.alternate_image,
                image_metadata=image_metadata,
                alternate_image_metadata=alternate_image_metadata,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_dry_run_plan_v0",
                "error": "ale_local_dry_run_plan_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_local_dry_run_plan_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_dry_run_plan_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
