from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_ledger import (
    BENCHMARK_RUN_LEDGER_DEFAULT_PATH,
    check_benchmark_run_ledger_drift,
    load_benchmark_run_ledger,
    update_benchmark_run_ledger,
)
from ..history import collect_history, load_registry
from ..paths import resolve_runtime_root
from ..status import (
    compact_benchmark_post_launch_materialization,
    compact_benchmark_run,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_RUN_LEDGER_MAINTENANCE_COMMANDS = {
    "run-ledger-check",
    "run-ledger-upsert",
}


def _compact_benchmark_run_input(
    payload: dict[str, object],
) -> tuple[dict[str, object] | None, str]:
    """Return compact benchmark_run_v0 plus the public-safe input kind."""

    if payload.get("schema_version") == "harbor_job_result_reducer_v0":
        compact = payload.get("compact_benchmark_run")
        if isinstance(compact, dict):
            return compact_benchmark_run(compact), "harbor_job_result_reducer_v0"
    return compact_benchmark_run(payload), "benchmark_run_v0"


def render_benchmark_run_ledger_upsert_markdown(payload: dict[str, object]) -> str:
    ledger = (
        payload.get("benchmark_run_ledger")
        if isinstance(payload.get("benchmark_run_ledger"), dict)
        else {}
    )
    entry = ledger.get("entry") if isinstance(ledger.get("entry"), dict) else {}
    decision = (
        ledger.get("case_decision")
        if isinstance(ledger.get("case_decision"), dict)
        else {}
    )
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Upsert",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{ledger.get('updated')}`",
        f"- benchmark: `{entry.get('benchmark_id')}`",
        f"- case: `{entry.get('case_id')}`",
        f"- arm: `{entry.get('arm_id')}`",
        f"- score: `{entry.get('official_score')}`",
        f"- failure: `{entry.get('failure_class')}`",
        f"- decision: `{decision.get('decision')}`",
        f"- ledger: `{ledger.get('ledger_path')}`",
        f"- compact only: `{read_boundary.get('compact_only')}`",
        f"- raw logs read: `{read_boundary.get('raw_logs_read')}`",
        f"- task text read: `{read_boundary.get('task_text_read')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_check_markdown(payload: dict[str, object]) -> str:
    drift = (
        payload.get("benchmark_run_ledger_drift")
        if isinstance(payload.get("benchmark_run_ledger_drift"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Drift Check",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- drift_detected: `{drift.get('drift_detected')}`",
        f"- checked_history_run_count: `{drift.get('checked_history_run_count')}`",
        f"- terminal_history_run_count: `{drift.get('terminal_history_run_count')}`",
        f"- matched_history_run_count: `{drift.get('matched_history_run_count')}`",
        f"- missing_ledger_run_count: `{drift.get('missing_ledger_run_count')}`",
        f"- non_terminal_skipped_count: `{drift.get('non_terminal_skipped_count')}`",
        f"- ledger_run_count: `{drift.get('ledger_run_count')}`",
    ]
    missing_runs = (
        drift.get("missing_runs") if isinstance(drift.get("missing_runs"), list) else []
    )
    if missing_runs:
        lines.extend(
            [
                "",
                "## Missing Compact Runs",
                "",
                "| Benchmark | Case | Arm | Score | Failure | Catch-up |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for run in missing_runs:
            if not isinstance(run, dict):
                continue
            lines.append(
                "| "
                f"`{run.get('benchmark_id')}` | "
                f"`{run.get('case_id')}` | "
                f"`{run.get('arm_id')}` | "
                f"`{run.get('official_score')}` | "
                f"`{run.get('failure_class')}` | "
                f"`{run.get('catch_up_command_template')}` |"
            )
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def register_benchmark_run_ledger_maintenance_commands(
    benchmark_subparsers: argparse._SubParsersAction,
) -> None:
    benchmark_run_ledger_upsert_parser = benchmark_subparsers.add_parser(
        "run-ledger-upsert",
        help=(
            "Upsert benchmark_run_ledger_v0 from an existing compact "
            "benchmark_run_v0 JSON file. This does not read raw runner artifacts."
        ),
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--benchmark-run-json",
        help="Path to a compact benchmark_run_v0 JSON object. Use '-' to read stdin.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--post-launch-json",
        help=(
            "Path to a compact terminal_bench_post_launch_materialization_v0 "
            "object. Use '-' to read stdin. This records result-finalization "
            "or post-launch failure markers without reading raw runner artifacts."
        ),
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON. Markdown is rendered next to it.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-group-id",
        help="Optional stable run group id for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--arm-id",
        help="Optional arm id override for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--compact-artifact-ref",
        help="Optional public-safe relative reference to the compact run artifact.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--run-ledger-note",
        help="Optional compact note for the ledger row.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview ledger update without writing. This is the default.",
    )
    benchmark_run_ledger_upsert_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the benchmark run ledger update.",
    )

    benchmark_run_ledger_check_parser = benchmark_subparsers.add_parser(
        "run-ledger-check",
        help=(
            "Compare compact benchmark_run_v0 run history with the public "
            "benchmark_run_ledger_v0. This reads compact history only."
        ),
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--goal-id",
        required=True,
        help="Goal id whose compact benchmark run history should be checked.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--history-limit",
        type=int,
        default=500,
        help="Maximum recent compact run-history rows to compare.",
    )
    benchmark_run_ledger_check_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum missing rows to include in output.",
    )


def handle_benchmark_run_ledger_maintenance_command(
    args: argparse.Namespace,
    *,
    registry_path: Path,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_RUN_LEDGER_MAINTENANCE_COMMANDS:
        return None

    if args.benchmark_command == "run-ledger-check":
        try:
            history_payload = collect_history(
                registry_path=registry_path,
                runtime_root=resolve_runtime_root(
                    load_registry(registry_path),
                    args.runtime_root,
                ),
                goal_id=args.goal_id,
                limit=max(0, int(args.history_limit)),
            )
            ledger = load_benchmark_run_ledger(args.run_ledger_path)
            drift = check_benchmark_run_ledger_drift(
                history_records=[
                    run
                    for run in history_payload.get("runs", [])
                    if isinstance(run, dict)
                ],
                ledger=ledger,
                ledger_path=args.run_ledger_path,
                limit=max(0, int(args.limit)),
                cwd=Path.cwd(),
            )
            payload = {
                "ok": True,
                "goal_id": args.goal_id,
                "history_limit": args.history_limit,
                "benchmark_run_ledger_drift": drift,
                "read_boundary": drift.get("read_boundary"),
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "goal_id": args.goal_id,
                "benchmark_run_ledger_drift": {
                    "schema_version": "benchmark_run_ledger_drift_v0",
                    "ok": False,
                    "drift_detected": False,
                },
                "read_boundary": {
                    "compact_only": True,
                    "raw_logs_read": False,
                    "task_text_read": False,
                    "trajectory_read": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                },
                "error": str(exc),
            }
        print_payload(
            payload,
            output_format(args),
            render_benchmark_run_ledger_check_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "run-ledger-upsert":
        try:
            if args.dry_run and args.execute:
                raise ValueError(
                    "benchmark run-ledger-upsert accepts either --dry-run or --execute, not both"
                )
            if bool(args.benchmark_run_json) == bool(args.post_launch_json):
                raise ValueError(
                    "provide exactly one of --benchmark-run-json or --post-launch-json"
                )

            input_path_text = args.benchmark_run_json or args.post_launch_json
            if input_path_text == "-":
                run_input = json.loads(sys.stdin.read())
                compact_artifact_ref = args.compact_artifact_ref
            else:
                input_path = Path(input_path_text).expanduser()
                run_input = json.loads(input_path.read_text(encoding="utf-8"))
                compact_artifact_ref = args.compact_artifact_ref or str(input_path)
            if not isinstance(run_input, dict):
                raise ValueError("ledger input JSON must contain an object")

            if args.benchmark_run_json:
                benchmark_run, input_kind = _compact_benchmark_run_input(run_input)
                if not benchmark_run:
                    raise ValueError(
                        "--benchmark-run-json did not contain a compactable "
                        "benchmark_run_v0 object or harbor_job_result_reducer_v0 "
                        "wrapper with compact_benchmark_run"
                    )
            else:
                benchmark_run = compact_benchmark_post_launch_materialization(
                    run_input
                )
                if not benchmark_run:
                    raise ValueError(
                        "--post-launch-json did not contain a compactable terminal_bench_post_launch_materialization_v0 object"
                    )
                input_kind = "terminal_bench_post_launch_materialization_v0"
            dry_run = not bool(args.execute)
            ledger_update = update_benchmark_run_ledger(
                ledger_path=args.run_ledger_path,
                benchmark_run=benchmark_run,
                compact_artifact_ref=compact_artifact_ref,
                run_group_id=args.run_group_id,
                arm_id=args.arm_id,
                notes=args.run_ledger_note,
                dry_run=dry_run,
            )
            payload = {
                "ok": True,
                "dry_run": dry_run,
                "input_kind": input_kind,
                "benchmark_run_ledger": ledger_update,
                "read_boundary": {
                    "compact_only": True,
                    "raw_logs_read": False,
                    "task_text_read": False,
                    "trajectory_read": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                },
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(args.execute),
                "benchmark_run_ledger": {
                    "updated": False,
                    "ledger_path": args.run_ledger_path,
                },
                "read_boundary": {
                    "compact_only": True,
                    "raw_logs_read": False,
                    "task_text_read": False,
                    "trajectory_read": False,
                    "docker_invoked": False,
                    "model_api_invoked": False,
                    "upload_invoked": False,
                },
                "error": str(exc),
            }
        print_payload(
            payload,
            output_format(args),
            render_benchmark_run_ledger_upsert_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
