from __future__ import annotations

import argparse
from collections.abc import Callable

from ..benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    build_agents_last_exam_local_runner_readiness,
    build_agents_last_exam_local_source_readiness,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS = {
    "ale-local-runner-readiness",
    "ale-local-source-readiness",
}


def render_agents_last_exam_local_runner_readiness_markdown(
    payload: dict[str, object],
) -> str:
    runner_probe = (
        payload.get("runner_probe")
        if isinstance(payload.get("runner_probe"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Local Runner Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Snapshot: `{payload.get('snapshot')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Preflight ready: `{payload.get('preflight_ready')}`",
        f"- Dry-run plan ready: `{payload.get('dry_run_plan_ready')}`",
        f"- Runner binary: `{runner_probe.get('binary')}`",
        f"- Runner binary available: `{runner_probe.get('binary_available')}`",
        f"- Runner Python module: `{runner_probe.get('python_module')}`",
        f"- Runner Python module available: `{runner_probe.get('python_module_available')}`",
        f"- Runner source root declared/available: `{runner_probe.get('source_root_declared')}`/`{runner_probe.get('source_root_available')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Public task material authorized: `{boundary.get('operator_authorized_public_task_material')}`",
        f"- Upload/submit allowed: `{boundary.get('upload_allowed')}`/`{boundary.get('submit_allowed')}`",
        f"- Model API allowed/invoked: `{boundary.get('model_api_allowed')}`/`{boundary.get('model_api_invoked')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
        f"- Compact only: `{read_boundary.get('compact_only')}`",
        f"- Raw artifacts read: `{read_boundary.get('raw_artifacts_read')}`",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_source_readiness_markdown(
    payload: dict[str, object],
) -> str:
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    runner_probe = (
        payload.get("runner_probe")
        if isinstance(payload.get("runner_probe"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Source Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Expected repo: `{source.get('expected_repo')}`",
        f"- Remote matches expected: `{source.get('remote_matches_expected')}`",
        f"- Source head: `{source.get('head')}`",
        f"- Upstream current: `{source.get('head_matches_upstream')}`",
        f"- Upstream ahead/behind: `{source.get('upstream_ahead_count')}`/`{source.get('upstream_behind_count')}`",
        f"- Fetch origin attempted/ok: `{source.get('fetch_origin_attempted')}`/`{source.get('fetch_origin_ok')}`",
        f"- Source root path recorded: `{source.get('source_root_path_recorded')}`",
        f"- Runner Python module: `{runner_probe.get('python_module')}`",
        f"- Runner Python module available: `{runner_probe.get('python_module_available')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_runner_source_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_local_runner_readiness_parser = benchmark_subparsers.add_parser(
        "ale-local-runner-readiness",
        help=(
            "Check whether a real Agents' Last Exam local dry-run runner is "
            "explicitly configured. This may inspect local Docker image metadata "
            "and PATH availability for a runner binary, but it does not start "
            "containers, read task bodies, invoke model APIs, upload, or submit."
        ),
    )
    add_subcommand_format(ale_local_runner_readiness_parser)
    ale_local_runner_readiness_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--provider-kind",
        choices=["docker"],
        default="docker",
        help="Provider kind. Only local docker is runner-ready.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-binary",
        help=(
            "PATH-visible runner binary name to probe. Absolute or relative paths "
            "are rejected so local paths are not recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-python-module",
        help=(
            "Optional Python module to probe when the runner command is "
            "`python -m <module>`. The module path is never recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-source-root",
        help=(
            "Optional local source checkout root to add only for module probing. "
            "The local path is never recorded in output."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--runner-command-label",
        help=(
            "Public-safe label for the configured runner command. The command "
            "argv itself is never recorded."
        ),
    )
    ale_local_runner_readiness_parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Mark that the operator authorized local container start for dry-run.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--allow-public-task-material",
        action="store_true",
        help="Mark that public ALE task material may be touched by a later dry-run.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the local runner readiness gate is ready.",
    )
    ale_local_runner_readiness_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help=(
            "Do not call Docker; emit a fixture-like blocked readiness payload. "
            "Used by dependency-free smokes."
        ),
    )

    ale_local_source_readiness_parser = benchmark_subparsers.add_parser(
        "ale-local-source-readiness",
        help=(
            "Check whether a local Agents' Last Exam source checkout can be used "
            "as a redacted public runner source lock. This reads git metadata and "
            "module availability only; it does not start containers, read task "
            "bodies, invoke model APIs, upload, or submit."
        ),
    )
    add_subcommand_format(ale_local_source_readiness_parser)
    ale_local_source_readiness_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--expected-repo-url",
        default="https://github.com/rdi-berkeley/agents-last-exam.git",
        help="Expected public ALE repository URL.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--runner-python-module",
        default="ale_run",
        help="Python module expected to provide the ALE runner CLI.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--fetch-origin",
        action="store_true",
        help=(
            "Run git fetch --prune origin before checking freshness. The command "
            "argv, local path, and raw git output are never recorded."
        ),
    )
    ale_local_source_readiness_parser.add_argument(
        "--require-upstream-current",
        action="store_true",
        help="Require HEAD to match the configured upstream ref before returning ready.",
    )
    ale_local_source_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the source readiness gate is ready.",
    )


def handle_agents_last_exam_runner_source_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_RUNNER_SOURCE_COMMANDS:
        return None

    if args.benchmark_command == "ale-local-runner-readiness":
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
            payload = build_agents_last_exam_local_runner_readiness(
                selected_task_id=args.selected_task_id,
                snapshot=args.snapshot,
                provider_kind=args.provider_kind,
                image_ref=args.image,
                alternate_image_ref=args.alternate_image,
                runner_binary=args.runner_binary,
                runner_python_module=args.runner_python_module,
                runner_source_root=args.runner_source_root,
                runner_command_label=args.runner_command_label,
                operator_authorized=bool(args.operator_authorized),
                allow_public_task_material=bool(args.allow_public_task_material),
                fetch_origin=bool(getattr(args, "fetch_origin", False)),
                require_upstream_current=bool(
                    getattr(args, "require_upstream_current", False)
                ),
                image_metadata=image_metadata,
                alternate_image_metadata=alternate_image_metadata,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_runner_readiness_v0",
                "error": "ale_local_runner_readiness_failed",
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
                    or "ale_local_runner_readiness_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_runner_readiness_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-local-source-readiness":
        try:
            payload = build_agents_last_exam_local_source_readiness(
                source_root=args.source_root,
                expected_repo_url=args.expected_repo_url,
                runner_python_module=args.runner_python_module,
                fetch_origin=bool(args.fetch_origin),
                require_upstream_current=bool(args.require_upstream_current),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_source_readiness_v0",
                "error": "ale_local_source_readiness_failed",
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
                    or "ale_local_source_readiness_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_source_readiness_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
