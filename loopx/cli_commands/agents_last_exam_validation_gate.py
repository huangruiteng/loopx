from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.agents_last_exam import (
    build_agents_last_exam_validation_run_gate,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

AGENTS_LAST_EXAM_VALIDATION_GATE_COMMANDS = {
    "ale-validation-run-gate",
}


def render_agents_last_exam_validation_run_gate_markdown(
    payload: dict[str, object],
) -> str:
    selected_task = (
        payload.get("selected_task")
        if isinstance(payload.get("selected_task"), dict)
        else {}
    )
    readiness = (
        payload.get("readiness_inputs")
        if isinstance(payload.get("readiness_inputs"), dict)
        else {}
    )
    model_policy = (
        payload.get("model_policy")
        if isinstance(payload.get("model_policy"), dict)
        else {}
    )
    run_boundary = (
        payload.get("run_boundary")
        if isinstance(payload.get("run_boundary"), dict)
        else {}
    )
    decision = (
        payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    )
    lines = [
        "# Agents Last Exam Validation Run Gate",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Ready: `{payload.get('ready')}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
        f"- Selected task: `{selected_task.get('task_id')}`",
        f"- Task material ready: `{readiness.get('task_material_ready')}`",
        f"- Host Codex no-task E2E ready: `{readiness.get('host_codex_no_task_e2e_ready')}`",
        f"- Exact dry-run ready: `{readiness.get('exact_dry_run_ready')}`",
        f"- Launch packet ready: `{readiness.get('launch_packet_ready')}`",
        f"- Fresh source required/ready: `{readiness.get('fresh_source_required')}`/`{readiness.get('fresh_source_ready')}`",
        f"- Compact reducer ready: `{readiness.get('compact_result_reducer_ready')}`",
        f"- Connectivity model: `{model_policy.get('connectivity_e2e_model')}`",
        f"- Formal score agent/candidate: `{model_policy.get('formal_score_agent')}`/`{model_policy.get('formal_score_candidate')}`",
        f"- Task run started by gate: `{run_boundary.get('task_run_started_by_this_gate')}`",
        f"- Upload/submit eligible: `{run_boundary.get('no_upload')}`/`{run_boundary.get('submit_eligible')}`",
        f"- Raw trajectory/task body read: `{run_boundary.get('raw_trajectory_read')}`/`{run_boundary.get('task_body_read_by_loopx')}`",
        f"- Next action: {decision.get('next_allowed_action')}",
    ]
    return "\n".join(lines) + "\n"


def register_agents_last_exam_validation_gate_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    ale_validation_run_gate_parser = benchmark_subparsers.add_parser(
        "ale-validation-run-gate",
        help=(
            "Combine compact ALE readiness artifacts into a pre-run decision "
            "for one local/no-upload validation run. This reads only compact "
            "JSON gates and does not start containers, send Codex prompts, "
            "read raw trajectories, upload, submit, or record local paths."
        ),
    )
    add_subcommand_format(ale_validation_run_gate_parser)
    ale_validation_run_gate_parser.add_argument(
        "--selected-task-id",
        required=True,
        help="Public ALE task id in category/name form.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--validation-hypothesis",
        required=True,
        help="Public-safe hypothesis for why this run can improve LoopX validation.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--task-material-readiness-json",
        required=True,
        help="Compact ale-task-material-readiness JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--host-codex-no-task-e2e-json",
        required=True,
        help="Compact ale-host-codex-cua-no-task-e2e JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--exact-dry-run-json",
        required=True,
        help="Compact ale-local-exact-dry-run-result JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--launch-packet-json",
        help="Optional compact ale-local-launch-packet JSON artifact.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--result-reducer-ready",
        action="store_true",
        help="Mark that the compact ALE result reducer is ready for post-run ingest.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--formal-score-candidate",
        action="store_true",
        help="Mark that the next run is intended as a formal score candidate.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-fresh-source",
        action="store_true",
        help=(
            "Require the launch packet to prove fetch-origin and upstream-current "
            "source freshness. Formal score candidates imply this requirement."
        ),
    )
    ale_validation_run_gate_parser.add_argument(
        "--expected-formal-agent",
        default="host_codex_gpt55_xhigh",
        help="Public-safe expected formal scoring agent id.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--submit-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks submit-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--leaderboard-enabled",
        action="store_true",
        help="Fixture flag proving the gate blocks leaderboard-enabled runs.",
    )
    ale_validation_run_gate_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless the validation-run gate is ready.",
    )


def handle_agents_last_exam_validation_gate_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in AGENTS_LAST_EXAM_VALIDATION_GATE_COMMANDS:
        return None

    if args.benchmark_command == "ale-validation-run-gate":
        try:
            task_material_readiness = json.loads(
                Path(args.task_material_readiness_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            host_codex_no_task_e2e = json.loads(
                Path(args.host_codex_no_task_e2e_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            exact_dry_run_result = json.loads(
                Path(args.exact_dry_run_json)
                .expanduser()
                .read_text(encoding="utf-8")
            )
            launch_packet = None
            if args.launch_packet_json:
                launch_packet = json.loads(
                    Path(args.launch_packet_json)
                    .expanduser()
                    .read_text(encoding="utf-8")
                )
            payload = build_agents_last_exam_validation_run_gate(
                selected_task_id=args.selected_task_id,
                validation_hypothesis=args.validation_hypothesis,
                task_material_readiness=task_material_readiness,
                host_codex_no_task_e2e=host_codex_no_task_e2e,
                exact_dry_run_result=exact_dry_run_result,
                launch_packet=launch_packet,
                result_reducer_ready=bool(args.result_reducer_ready),
                submit_enabled=bool(args.submit_enabled),
                leaderboard_enabled=bool(args.leaderboard_enabled),
                formal_score_candidate=bool(args.formal_score_candidate),
                require_fresh_source=bool(args.require_fresh_source),
                expected_formal_agent=args.expected_formal_agent,
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "schema_version": "agents_last_exam_validation_run_gate_v0",
                "error": "ale_validation_run_gate_failed",
                "error_type": type(exc).__name__,
                "read_boundary": {
                    "compact_only": True,
                    "task_text_read": False,
                    "task_card_content_read": False,
                    "script_content_read": False,
                    "raw_artifacts_read": False,
                    "local_paths_recorded": False,
                    "container_started": False,
                    "model_api_invoked": False,
                    "codex_prompt_sent": False,
                },
            }
        else:
            payload["ok"] = True
            if args.require_ready and payload.get("ready") is not True:
                payload["ok"] = False
                payload["error"] = (
                    payload.get("first_blocker")
                    or "ale_validation_run_gate_not_ready"
                )
        print_payload(
            payload,
            output_format(args),
            render_agents_last_exam_validation_run_gate_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
