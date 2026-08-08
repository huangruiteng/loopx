from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
from collections.abc import Callable
from pathlib import Path

from ..benchmark_adapters.edgebench import (
    EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS,
    build_edgebench_sforge_preflight,
    build_edgebench_sforge_run_plan,
    reduce_edgebench_final_result,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

EDGEBENCH_COMMANDS = {
    "edgebench-preflight",
    "edgebench-run-plan",
    "edgebench-result-reduce",
}


def _render(title: str, payload: dict[str, object]) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Schema: `{payload.get('schema_version')}`",
        f"- Task: `{payload.get('task_id')}`",
        f"- Ready/countable: `{payload.get('ready', payload.get('countable'))}`",
        f"- First blocker: `{payload.get('first_blocker')}`",
    ]
    decision = payload.get("decision")
    if isinstance(decision, dict):
        lines.append(f"- Next action: {decision.get('next_allowed_action')}")
    boundary = payload.get("boundary")
    if isinstance(boundary, dict):
        lines.extend(
            [
                f"- No execution: `{boundary.get('no_execution')}`",
                f"- Container started: `{boundary.get('container_started')}`",
                f"- Model API invoked: `{boundary.get('model_api_invoked')}`",
                f"- Upload/submit invoked: `{boundary.get('upload_invoked')}`/`{boundary.get('submit_invoked')}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _load_json_object(path: str) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload


def register_edgebench_commands(
    benchmark_subparsers: argparse._SubParsersAction,
    add_subcommand_format: Callable[[argparse.ArgumentParser], None],
) -> None:
    preflight = benchmark_subparsers.add_parser(
        "edgebench-preflight",
        help=(
            "Check compact EdgeBench/SForge readiness without fetching tasks, "
            "pulling images, starting containers, invoking models, uploading, or submitting."
        ),
    )
    add_subcommand_format(preflight)
    preflight.add_argument("--task-id", required=True)
    preflight.add_argument(
        "--backend",
        choices=["docker", "kubernetes"],
        default="docker",
    )
    preflight.add_argument("--task-catalog-ready", action="store_true")
    preflight.add_argument("--task-images-ready", action="store_true")
    preflight.add_argument("--judge-ready", action="store_true")
    preflight.add_argument(
        "--no-environment-probe",
        action="store_true",
        help="Skip host/SForge/container-runtime probes for dependency-free smokes.",
    )
    preflight.add_argument("--require-ready", action="store_true")

    run_plan = benchmark_subparsers.add_parser(
        "edgebench-run-plan",
        help=(
            "Build a private single-task SForge launch plan from a compact "
            "preflight. This never launches SForge or reads credentials."
        ),
    )
    add_subcommand_format(run_plan)
    run_plan.add_argument("--preflight-json", required=True)
    run_plan.add_argument("--agent", required=True)
    run_plan.add_argument("--model", required=True)
    run_plan.add_argument("--run-id", required=True)
    run_plan.add_argument(
        "--timeout-seconds",
        type=int,
        default=7_200,
        help=(
            "Bounded task budget. Must not exceed the official 12-hour "
            f"budget ({EDGEBENCH_OFFICIAL_TIMEOUT_SECONDS} seconds)."
        ),
    )
    run_plan.add_argument("--require-ready", action="store_true")

    result = benchmark_subparsers.add_parser(
        "edgebench-result-reduce",
        help=(
            "Reduce an SForge final_result.json into compact public-safe "
            "best-score evidence without reading raw logs or trajectories."
        ),
    )
    add_subcommand_format(result)
    result.add_argument("--result-json", required=True)
    result.add_argument("--task-id", required=True)
    result.add_argument("--run-id", required=True)
    result.add_argument("--require-countable", action="store_true")


def handle_edgebench_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in EDGEBENCH_COMMANDS:
        return None

    try:
        if args.benchmark_command == "edgebench-preflight":
            probe = not args.no_environment_probe
            container_command = "docker" if args.backend == "docker" else "kubectl"
            payload = build_edgebench_sforge_preflight(
                task_id=args.task_id,
                backend=args.backend,
                linux_host=(platform.system().lower() == "linux") if probe else False,
                sforge_available=(
                    importlib.util.find_spec("sforge") is not None
                    or shutil.which("sforge") is not None
                )
                if probe
                else False,
                container_runtime_available=shutil.which(container_command) is not None
                if probe
                else False,
                task_catalog_ready=args.task_catalog_ready,
                task_images_ready=args.task_images_ready,
                judge_ready=args.judge_ready,
            )
            payload["ok"] = not args.require_ready or payload["ready"] is True
            if not payload["ok"]:
                payload["error"] = payload["first_blocker"]
            title = "EdgeBench SForge Preflight"
        elif args.benchmark_command == "edgebench-run-plan":
            payload = build_edgebench_sforge_run_plan(
                preflight=_load_json_object(args.preflight_json),
                agent=args.agent,
                model=args.model,
                timeout_seconds=args.timeout_seconds,
                run_id=args.run_id,
            )
            payload["ok"] = not args.require_ready or payload["ready"] is True
            if not payload["ok"]:
                payload["error"] = payload["first_blocker"]
            title = "EdgeBench SForge Run Plan"
        else:
            payload = reduce_edgebench_final_result(
                task_id=args.task_id,
                run_id=args.run_id,
                result=_load_json_object(args.result_json),
            )
            payload["ok"] = not args.require_countable or payload["countable"] is True
            if not payload["ok"]:
                payload["error"] = payload["first_blocker"]
            title = "EdgeBench Compact Result"
    except (OSError, ValueError, json.JSONDecodeError):
        payload = {
            "ok": False,
            "schema_version": "edgebench_command_error_v0",
            "error": "edgebench_input_invalid",
            "boundary": {
                "no_execution": True,
                "container_started": False,
                "model_api_invoked": False,
                "upload_invoked": False,
                "submit_invoked": False,
            },
        }
        title = "EdgeBench Command Error"

    print_payload(
        payload,
        output_format(args),
        lambda item: _render(title, item),
    )
    return 0 if payload.get("ok") else 1
