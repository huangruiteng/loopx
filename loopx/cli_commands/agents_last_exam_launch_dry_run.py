from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agents_last_exam import (
    AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
    AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
    build_agents_last_exam_local_exact_dry_run_result,
    build_agents_last_exam_local_launch_packet,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_LAUNCH_DRY_RUN_COMMANDS = {
    "ale-local-launch-packet",
    "ale-local-exact-dry-run-result",
}


def render_agents_last_exam_local_launch_packet_markdown(
    payload: dict[str, object],
) -> str:
    source_lock = (
        payload.get("source_lock")
        if isinstance(payload.get("source_lock"), dict)
        else {}
    )
    runner = payload.get("runner") if isinstance(payload.get("runner"), dict) else {}
    experiment_spec = (
        payload.get("experiment_spec")
        if isinstance(payload.get("experiment_spec"), dict)
        else {}
    )
    launch_packet = (
        payload.get("launch_packet")
        if isinstance(payload.get("launch_packet"), dict)
        else {}
    )
    case_state = (
        payload.get("case_state_init_contract")
        if isinstance(payload.get("case_state_init_contract"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Launch Packet",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Source head: `{source_lock.get('head')}`",
        f"- Upstream current: `{source_lock.get('head_matches_upstream')}`",
        f"- Fetch origin attempted/ok: `{source_lock.get('fetch_origin_attempted')}`/`{source_lock.get('fetch_origin_ok')}`",
        f"- Source root path recorded: `{source_lock.get('source_root_path_recorded')}`",
        f"- Runner command label: `{runner.get('command_label')}`",
        f"- Runner module available: `{runner.get('python_module_available')}`",
        f"- Experiment spec: `{experiment_spec.get('relative_path')}`",
        f"- Experiment spec exists/content read: `{experiment_spec.get('exists')}`/`{experiment_spec.get('content_read')}`",
        f"- Mode: `{launch_packet.get('mode')}`",
        f"- Will execute/start container: `{launch_packet.get('will_execute')}`/`{launch_packet.get('will_start_container')}`",
        f"- Will upload/submit: `{launch_packet.get('will_upload')}`/`{launch_packet.get('will_submit')}`",
        f"- Case state init required/path: `{case_state.get('init_required_before_worker')}`/`{case_state.get('case_state_path')}`",
        f"- Case state schema: `{case_state.get('schema_version')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_local_exact_dry_run_result_markdown(
    payload: dict[str, object],
) -> str:
    environment = (
        payload.get("environment")
        if isinstance(payload.get("environment"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Local Exact Dry-Run Result",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Exit code: `{payload.get('exit_code')}`",
        f"- Experiment: `{payload.get('experiment')}`",
        f"- Environment: `{environment.get('kind')}` / `{environment.get('route')}`",
        f"- Concurrency: `{payload.get('concurrency')}`",
        f"- Unit count declared/parsed: `{payload.get('unit_count_declared')}`/`{payload.get('unit_count_parsed')}`",
        f"- Raw stdout recorded: `{boundary.get('raw_stdout_recorded')}`",
        f"- Container started: `{boundary.get('container_started')}`",
        f"- Task body read: `{boundary.get('task_body_read')}`",
        f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
        f"- Upload/submit eligible: `{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_launch_dry_run_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_local_launch_packet_parser = benchmark_subparsers.add_parser(
        "ale-local-launch-packet",
        help=(
            "Build a no-execution Agents' Last Exam local dry-run launch packet. "
            "This combines source, runner, Docker preflight, and experiment-spec "
            "existence gates without starting containers, reading task bodies, "
            "invoking model APIs, uploading, or submitting."
        ),
    )
    add_subcommand_format(ale_local_launch_packet_parser)
    ale_local_launch_packet_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec",
        required=True,
        help=(
            "Public relative path to the ALE experiment spec under source root "
            "or --experiment-spec-root."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--experiment-spec-root",
        help=(
            "Optional external spec root for LoopX wrapper specs. The "
            "path is probed for existence only and never recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--selected-task-id",
        help="Optional public task id label for the metadata-only candidate.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--expected-repo-url",
        default="https://github.com/rdi-berkeley/agents-last-exam.git",
        help="Expected public ALE repository URL.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-binary",
        default="python3",
        help="PATH-visible runner binary name to probe.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-python-module",
        default="ale_run",
        help="Python module expected to provide the ALE runner CLI.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--runner-command-label",
        default="python-m-ale-run",
        help="Public-safe label for the configured runner command.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--snapshot",
        default=AGENTS_LAST_EXAM_DEFAULT_SNAPSHOT,
        help="ALE snapshot label to check. Defaults to cpu-free-ubuntu.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--image",
        default=AGENTS_LAST_EXAM_DEFAULT_DOCKER_IMAGE,
        help="Primary local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--alternate-image",
        default=AGENTS_LAST_EXAM_DEFAULT_ALT_DOCKER_IMAGE,
        help="Optional alternate local Docker image ref to inspect.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--operator-authorized",
        action="store_true",
        help="Mark that the operator authorized local container start for dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--allow-public-task-material",
        action="store_true",
        help="Mark that public ALE task material may be touched by a later dry-run.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--fetch-origin",
        action="store_true",
        help=(
            "Run git fetch --prune origin before launch-packet source freshness "
            "checks. No raw git output, command argv, or local paths are recorded."
        ),
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-upstream-current",
        action="store_true",
        help="Require the ALE checkout HEAD to match upstream before the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the launch packet is ready.",
    )
    ale_local_launch_packet_parser.add_argument(
        "--no-docker-probe",
        action="store_true",
        help="Do not call Docker; emit a fixture-like blocked launch packet.",
    )

    ale_local_exact_dry_run_result_parser = benchmark_subparsers.add_parser(
        "ale-local-exact-dry-run-result",
        help=(
            "Reduce ALE `run --dry-run` stdout into a compact public-safe result. "
            "This reads only the provided dry-run stdout file and records labels "
            "and counts, never raw stdout, task text, paths, trajectories, "
            "screenshots, credentials, uploads, or command argv."
        ),
    )
    add_subcommand_format(ale_local_exact_dry_run_result_parser)
    ale_local_exact_dry_run_result_parser.add_argument(
        "--stdout-file",
        required=True,
        help=(
            "File containing ALE dry-run stdout to reduce. The path and raw text "
            "are not recorded."
        ),
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--exit-code",
        required=True,
        help="Exit code from the ALE dry-run command.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-task-id",
        help="Optional public task id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--expected-agent-id",
        help="Optional public agent id expected in the dry-run matrix.",
    )
    ale_local_exact_dry_run_result_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the compact dry-run result is ready.",
    )


def handle_agents_last_exam_launch_dry_run_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_LAUNCH_DRY_RUN_COMMANDS:
        return None

    if args.benchmark_command == "ale-local-launch-packet":
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
            payload = build_agents_last_exam_local_launch_packet(
                source_root=args.source_root,
                experiment_spec_relative_path=args.experiment_spec,
                experiment_spec_root=args.experiment_spec_root,
                selected_task_id=args.selected_task_id,
                expected_repo_url=args.expected_repo_url,
                snapshot=args.snapshot,
                image_ref=args.image,
                alternate_image_ref=args.alternate_image,
                runner_binary=args.runner_binary,
                runner_python_module=args.runner_python_module,
                runner_command_label=args.runner_command_label,
                operator_authorized=bool(args.operator_authorized),
                allow_public_task_material=bool(args.allow_public_task_material),
                fetch_origin=bool(args.fetch_origin),
                require_upstream_current=bool(args.require_upstream_current),
                image_metadata=image_metadata,
                alternate_image_metadata=alternate_image_metadata,
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_launch_packet_v0",
                "error": "ale_local_launch_packet_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "experiment_spec_content_read": False,
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
                    or "ale_local_launch_packet_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_launch_packet_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-local-exact-dry-run-result":
        try:
            stdout_text = Path(args.stdout_file).expanduser().read_text(
                encoding="utf-8"
            )
            payload = build_agents_last_exam_local_exact_dry_run_result(
                stdout_text=stdout_text,
                exit_code=args.exit_code,
                expected_task_id=args.expected_task_id,
                expected_agent_id=args.expected_agent_id,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_local_exact_dry_run_result_v0",
                "error": "ale_local_exact_dry_run_result_failed",
                "error_type": type(exc).__name__,
                "read_boundary": {
                    "compact_only": True,
                    "raw_stdout_recorded": False,
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
                    or "ale_local_exact_dry_run_result_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_local_exact_dry_run_result_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
