from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agents_last_exam import (
    build_agents_last_exam_candidate_task_data_scan,
    build_agents_last_exam_task_material_readiness,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS = {
    "ale-task-material-readiness",
    "ale-candidate-task-data-scan",
}


def render_agents_last_exam_task_material_readiness_markdown(
    payload: dict[str, object],
) -> str:
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    public_lists = (
        payload.get("public_task_lists")
        if isinstance(payload.get("public_task_lists"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    task_data = payload.get("task_data") if isinstance(payload.get("task_data"), dict) else {}
    local_staging = (
        task_data.get("local_task_data_staging")
        if isinstance(task_data.get("local_task_data_staging"), dict)
        else {}
    )
    lines = [
        "# Agents Last Exam Task Material Readiness",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Task: `{task.get('task_id')}`",
        f"- Task dir/card/scripts: `{task.get('task_dir_available')}`/`{task.get('task_card_json_present')}`/`{task.get('scripts_dir_present')}`",
        f"- Scorer script count: `{task.get('scorer_script_count')}`",
        f"- Task data checked/ready/source: `{task_data.get('checked')}`/`{task_data.get('ready')}`/`{task_data.get('task_data_source')}`",
        f"- Local task-data staging route/tool/auth checked: `{local_staging.get('route')}`/`{local_staging.get('fetch_tool_present')}`/`{local_staging.get('auth_status_checked')}`",
        f"- Public list membership checked/present: `{public_lists.get('checked')}`/`{public_lists.get('present_count')}`",
        f"- Task body/card/script content read: `{boundary.get('task_body_read')}`/`{boundary.get('task_card_content_read')}`/`{boundary.get('script_content_read')}`",
        f"- Local paths/raw output recorded: `{boundary.get('local_paths_recorded')}`/`{boundary.get('raw_output_recorded')}`",
        f"- Container/model/upload/submit: `{boundary.get('container_started')}`/`{boundary.get('model_api_invoked')}`/`{boundary.get('no_upload')}`/`{boundary.get('submit_eligible')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def render_agents_last_exam_candidate_task_data_scan_markdown(
    payload: dict[str, object],
) -> str:
    selected = (
        payload.get("selected_task_lists")
        if isinstance(payload.get("selected_task_lists"), dict)
        else {}
    )
    summary = (
        payload.get("scan_summary")
        if isinstance(payload.get("scan_summary"), dict)
        else {}
    )
    candidates = (
        payload.get("candidate_tasks")
        if isinstance(payload.get("candidate_tasks"), dict)
        else {}
    )
    boundary = payload.get("boundary") if isinstance(payload.get("boundary"), dict) else {}
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Candidate Task-Data Scan",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected tasks/lists: `{selected.get('selected_task_count')}`/`{selected.get('checked_list_count')}`",
        f"- Configs checked/missing: `{summary.get('task_config_checked_count')}`/`{summary.get('task_config_missing_or_unreadable_count')}`",
        f"- No-task-data formal/demo candidates: `{summary.get('formal_no_task_data_candidate_count')}`/`{summary.get('demo_no_task_data_candidate_count')}`",
        f"- Eligible candidates: `{candidates.get('eligible_no_task_data_candidates')}`",
        f"- Config line scan/source recorded: `{boundary.get('task_config_line_scan')}`/`{boundary.get('task_config_source_content_recorded')}`",
        f"- Task card/script/instruction read: `{boundary.get('task_card_content_read')}`/`{boundary.get('script_content_read')}`/`{boundary.get('task_instruction_file_read')}`",
        f"- Local paths/raw output recorded: `{boundary.get('local_paths_recorded')}`/`{boundary.get('raw_output_recorded')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_task_material_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_task_material_readiness_parser = benchmark_subparsers.add_parser(
        "ale-task-material-readiness",
        help=(
            "Check whether a selected public ALE task has local material signals "
            "needed for a future local/no-upload run. This checks directory, "
            "task_card.json, scripts, scorer scripts, and public selected-task "
            "list membership only; it does not read task card content, task "
            "bodies, scripts, trajectories, screenshots, credentials, upload, or submit."
        ),
    )
    add_subcommand_format(ale_task_material_readiness_parser)
    ale_task_material_readiness_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to check, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--requires-task-data",
        choices=("true", "false", "unknown"),
        help=(
            "Optional compact task-data requirement signal. Use unknown with "
            "--enforce-task-data-source to fail closed before a formal task run."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--task-data-source",
        help=(
            "Compact task_data_source label such as baked_in_sandbox or "
            "gs://ale-data-public. Credential values and paths are never recorded."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--baked-task-input-present",
        action="store_true",
        help="Mark that the selected task's baked sandbox input directory was verified present.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--baked-task-input-readiness-json",
        help=(
            "Compact ale-baked-task-input-readiness JSON artifact to consume "
            "instead of relying on a manual baked-input boolean."
        ),
    )
    ale_task_material_readiness_parser.add_argument(
        "--gcs-sa-key",
        help="Service-account key path to check for existence only; the path/value is never recorded.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--gcs-sa-key-present",
        action="store_true",
        help="Fixture/operator assertion that the service-account key file presence was verified.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--enforce-task-data-source",
        action="store_true",
        help="Require task-data source readiness before returning ready.",
    )
    ale_task_material_readiness_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the task material readiness gate is ready.",
    )

    ale_candidate_task_data_scan_parser = benchmark_subparsers.add_parser(
        "ale-candidate-task-data-scan",
        help=(
            "Scan public ALE selected-task lists for tasks with an explicit "
            "REQUIRES_TASK_DATA=False config signal. The scan records only "
            "counts and public task ids; it does not record task source text, "
            "task cards, instructions, scripts, trajectories, screenshots, "
            "credentials, uploads, or submits."
        ),
    )
    add_subcommand_format(ale_candidate_task_data_scan_parser)
    ale_candidate_task_data_scan_parser.add_argument(
        "--source-root",
        required=True,
        help="Local ALE source checkout root to probe. The path is never recorded.",
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--selected-task-list",
        action="append",
        default=[],
        help=(
            "Public selected_tasks list to scan, relative to selected_tasks/. "
            "May be repeated. Defaults to linux_only.txt and unlicensed/near-term.txt."
        ),
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--allow-demo-candidate",
        action="store_true",
        help="Allow demo/* no-task-data tasks to satisfy readiness.",
    )
    ale_candidate_task_data_scan_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless at least one eligible no-task-data candidate is found.",
    )


def handle_agents_last_exam_task_material_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_TASK_MATERIAL_COMMANDS:
        return None

    if args.benchmark_command == "ale-task-material-readiness":
        try:
            selected_task_lists = (
                args.selected_task_list
                if args.selected_task_list
                else ["linux_only.txt", "unlicensed/near-term.txt"]
            )
            baked_task_input_readiness = None
            if args.baked_task_input_readiness_json:
                baked_task_input_readiness = json.loads(
                    Path(args.baked_task_input_readiness_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
            payload = build_agents_last_exam_task_material_readiness(
                source_root=args.source_root,
                selected_task_id=args.selected_task_id,
                selected_task_lists=selected_task_lists,
                requires_task_data=None
                if args.requires_task_data in {None, "unknown"}
                else args.requires_task_data,
                task_data_source=args.task_data_source,
                baked_task_input_present=True
                if args.baked_task_input_present
                else None,
                baked_task_input_readiness=baked_task_input_readiness,
                gcs_sa_key=args.gcs_sa_key,
                gcs_sa_key_present=True if args.gcs_sa_key_present else None,
                enforce_task_data_source=bool(args.enforce_task_data_source),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_task_material_readiness_v0",
                "error": "ale_task_material_readiness_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
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
                    or "ale_task_material_readiness_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_task_material_readiness_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "ale-candidate-task-data-scan":
        try:
            selected_task_lists = (
                args.selected_task_list
                if args.selected_task_list
                else ["linux_only.txt", "unlicensed/near-term.txt"]
            )
            payload = build_agents_last_exam_candidate_task_data_scan(
                source_root=args.source_root,
                selected_task_lists=selected_task_lists,
                allow_demo_candidate=bool(args.allow_demo_candidate),
            )
        except Exception:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_candidate_task_data_scan_v0",
                "error": "ale_candidate_task_data_scan_failed",
                "read_boundary": {
                    "compact_only": True,
                    "task_config_source_content_recorded": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
                    "task_instruction_file_read": False,
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
                    or "ale_candidate_task_data_scan_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_candidate_task_data_scan_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
