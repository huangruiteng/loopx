from __future__ import annotations

import argparse
import glob
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_ledger import (
    archive_benchmark_run_ledger_runs,
    build_benchmark_run_ledger_current_aggregate,
    check_benchmark_run_ledger_drift,
    load_benchmark_run_ledger,
    merge_benchmark_run_ledgers,
    upsert_benchmark_run_ledger_entry,
    update_benchmark_run_ledger,
)
from ..history import collect_history, load_registry
from ..paths import resolve_runtime_root
from ..status import (
    compact_benchmark_post_launch_materialization,
    compact_benchmark_run,
)
from .benchmark_run_ledger_maintenance_rendering import (
    render_benchmark_run_ledger_aggregate_markdown,
    render_benchmark_run_ledger_archive_markdown,
    render_benchmark_run_ledger_check_markdown,
    render_benchmark_run_ledger_merge_markdown,
    render_benchmark_run_ledger_upsert_markdown,
)


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_RUN_LEDGER_MAINTENANCE_COMMANDS = {
    "run-ledger-archive",
    "run-ledger-aggregate",
    "run-ledger-check",
    "run-ledger-merge",
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


def _iter_loaded_ledger_runs(ledger: dict[str, object]) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    benchmarks = ledger.get("benchmarks") if isinstance(ledger.get("benchmarks"), dict) else {}
    for benchmark in benchmarks.values():
        if not isinstance(benchmark, dict):
            continue
        cases = benchmark.get("cases") if isinstance(benchmark.get("cases"), dict) else {}
        for case in cases.values():
            if not isinstance(case, dict):
                continue
            for run in case.get("runs") or []:
                if isinstance(run, dict):
                    runs.append(run)
    return runs


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

    if args.benchmark_command == "run-ledger-archive":
        try:
            if args.dry_run and args.execute:
                raise ValueError(
                    "benchmark run-ledger-archive accepts either --dry-run or --execute, not both"
                )
            payload = archive_benchmark_run_ledger_runs(
                ledger_path=args.run_ledger_path,
                benchmark_id=args.benchmark_id,
                reason=args.reason,
                run_group_contains=list(args.run_group_contains or []),
                keep_run_group_contains=list(args.keep_run_group_contains or []),
                case_ids=list(args.case_id or []),
                arm_ids=list(args.arm_id or []),
                archive_all_matching_benchmark=bool(
                    args.archive_all_matching_benchmark
                ),
                archive_batch_id=args.archive_batch_id,
                dry_run=not bool(args.execute),
            )
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(getattr(args, "execute", False)),
                "updated": False,
                "ledger_path": args.run_ledger_path,
                "archive": {
                    "schema_version": "benchmark_run_ledger_archive_v0",
                    "ok": False,
                    "benchmark_id": getattr(args, "benchmark_id", ""),
                },
                "error": str(exc),
            }
        print_payload(
            payload,
            output_format(args),
            render_benchmark_run_ledger_archive_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "run-ledger-merge":
        try:
            if args.dry_run and args.execute:
                raise ValueError(
                    "benchmark run-ledger-merge accepts either --dry-run or --execute, not both"
                )
            source_paths = [Path(value).expanduser() for value in args.source_run_ledger_path]
            for pattern in args.source_run_ledger_glob or []:
                source_paths.extend(
                    Path(value).expanduser()
                    for value in glob.glob(str(Path(pattern).expanduser()), recursive=True)
                )
            if not source_paths:
                raise ValueError(
                    "provide at least one --source-run-ledger-path or --source-run-ledger-glob"
                )
            merge_update = merge_benchmark_run_ledgers(
                target_ledger_path=args.run_ledger_path,
                source_ledger_paths=source_paths,
                benchmark_ids=list(args.benchmark_id or []),
                run_group_contains=list(args.run_group_contains or []),
                dry_run=not bool(args.execute),
            )
            payload = {
                "ok": True,
                "dry_run": not bool(args.execute),
                "updated": bool(args.execute),
                "ledger_path": args.run_ledger_path,
                "markdown_path": merge_update.get("markdown_path"),
                "merge": merge_update.get("merge"),
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
                "dry_run": not bool(getattr(args, "execute", False)),
                "updated": False,
                "ledger_path": args.run_ledger_path,
                "merge": {
                    "schema_version": "benchmark_run_ledger_merge_v0",
                    "ok": False,
                    "source_paths_recorded": False,
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
            render_benchmark_run_ledger_merge_markdown,
        )
        return 0 if payload.get("ok") else 1

    if args.benchmark_command == "run-ledger-aggregate":
        try:
            if args.dry_run and args.execute:
                raise ValueError(
                    "benchmark run-ledger-aggregate accepts either --dry-run or --execute, not both"
                )
            source_paths = [Path(args.run_ledger_path).expanduser()]
            source_paths.extend(Path(value).expanduser() for value in args.source_run_ledger_path)
            for pattern in args.source_run_ledger_glob or []:
                source_paths.extend(
                    Path(value).expanduser()
                    for value in glob.glob(str(Path(pattern).expanduser()), recursive=True)
                )
            canonical_case_ids = list(args.canonical_case_id or [])
            if args.canonical_case_ids_file:
                canonical_case_ids.extend(
                    line.strip()
                    for line in Path(args.canonical_case_ids_file)
                    .expanduser()
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                )
            if args.canonical_case_root:
                canonical_root = Path(args.canonical_case_root).expanduser()
                if not canonical_root.is_dir():
                    raise ValueError(
                        f"--canonical-case-root is not a directory: {canonical_root}"
                    )
                canonical_case_ids.extend(
                    child.name
                    for child in sorted(canonical_root.iterdir(), key=lambda item: item.name)
                    if child.is_dir() and child.name
                )
            active_case_ids = list(args.active_case_id or [])
            if args.active_case_ids_file:
                active_case_ids.extend(
                    line.strip()
                    for line in Path(args.active_case_ids_file)
                    .expanduser()
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                )
            merged_ledger = load_benchmark_run_ledger(args.run_ledger_path)
            source_ledger_count = 0
            source_run_count = 0
            considered_run_count = 0
            unique_source_paths = []
            seen_sources = set()
            for source_path in source_paths:
                source_key = str(source_path.resolve(strict=False))
                if source_key in seen_sources:
                    continue
                seen_sources.add(source_key)
                unique_source_paths.append(source_path)
                if not source_path.exists():
                    continue
                source_ledger_count += 1
                source_ledger = load_benchmark_run_ledger(source_path)
                for run in _iter_loaded_ledger_runs(source_ledger):
                    source_run_count += 1
                    if run.get("benchmark_id") != args.benchmark_id:
                        continue
                    considered_run_count += 1
                    merged_ledger = upsert_benchmark_run_ledger_entry(
                        merged_ledger,
                        dict(run),
                    )
            aggregate = build_benchmark_run_ledger_current_aggregate(
                merged_ledger,
                benchmark_id=args.benchmark_id,
                canonical_case_ids=canonical_case_ids or None,
                active_case_ids=active_case_ids or None,
                source_ledger_count=source_ledger_count,
                exclude_noncanonical_sanity_sources=not bool(
                    args.include_noncanonical_sanity_sources
                ),
                target_lane_id=args.target_lane_id,
                target_run_group_contains=list(args.target_run_group_contains or []),
                target_current_run_group_contains=list(
                    args.target_current_run_group_contains or []
                ),
                target_backfill_run_group_contains=list(
                    args.target_backfill_run_group_contains or []
                ),
            )
            output_json = Path(args.output_json).expanduser() if args.output_json else None
            if args.execute:
                if output_json is None:
                    raise ValueError("--execute requires --output-json")
                output_json.parent.mkdir(parents=True, exist_ok=True)
                output_json.write_text(
                    json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n",
                    encoding="utf-8",
                )
            payload = {
                "ok": True,
                "dry_run": not bool(args.execute),
                "updated": bool(args.execute),
                "output_json": str(output_json) if output_json else None,
                "aggregate": aggregate,
                "merge_preview": {
                    "schema_version": "benchmark_run_ledger_aggregate_source_merge_v0",
                    "source_ledger_count": source_ledger_count,
                    "source_run_count": source_run_count,
                    "considered_run_count": considered_run_count,
                    "source_paths_recorded": False,
                    "unique_source_path_count": len(unique_source_paths),
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
            }
        except Exception as exc:
            payload = {
                "ok": False,
                "dry_run": not bool(getattr(args, "execute", False)),
                "updated": False,
                "output_json": getattr(args, "output_json", None),
                "aggregate": {"ok": False},
                "error": str(exc),
            }
        print_payload(
            payload,
            output_format(args),
            render_benchmark_run_ledger_aggregate_markdown,
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
            compact_artifact_ref_cwd = None
            if input_path_text == "-":
                run_input = json.loads(sys.stdin.read())
                compact_artifact_ref = args.compact_artifact_ref
            else:
                input_path = Path(input_path_text).expanduser()
                run_input = json.loads(input_path.read_text(encoding="utf-8"))
                if args.compact_artifact_ref:
                    compact_artifact_ref = args.compact_artifact_ref
                else:
                    compact_artifact_ref = str(input_path)
                    compact_artifact_ref_cwd = input_path.parent
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
                cwd=compact_artifact_ref_cwd,
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
