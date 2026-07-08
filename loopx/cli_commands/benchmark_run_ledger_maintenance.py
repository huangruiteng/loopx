from __future__ import annotations

import argparse
import glob
import json
import sys
from collections.abc import Callable
from pathlib import Path

from ..benchmark_ledger import (
    BENCHMARK_RUN_LEDGER_DEFAULT_PATH,
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


def render_benchmark_run_ledger_archive_markdown(payload: dict[str, object]) -> str:
    archive = payload.get("archive") if isinstance(payload.get("archive"), dict) else {}
    samples = (
        archive.get("archived_samples")
        if isinstance(archive.get("archived_samples"), list)
        else []
    )
    lines = [
        "# Benchmark Run Ledger Archive",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- benchmark: `{archive.get('benchmark_id')}`",
        f"- archive_batch_id: `{archive.get('archive_batch_id')}`",
        f"- matched_run_count: `{archive.get('matched_run_count')}`",
        f"- newly_archived_run_count: `{archive.get('newly_archived_run_count')}`",
        f"- already_archived_run_count: `{archive.get('already_archived_run_count')}`",
        f"- kept_run_count: `{archive.get('kept_run_count')}`",
        f"- ledger: `{payload.get('ledger_path')}`",
    ]
    reason = archive.get("reason")
    if reason:
        lines.append(f"- reason: {reason}")
    if samples:
        lines.extend(
            [
                "",
                "## Archived Samples",
                "",
                "| Case | Arm | Run Group | Score | Failure |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for sample in samples:
            if not isinstance(sample, dict):
                continue
            lines.append(
                "| "
                f"`{sample.get('case_id')}` | "
                f"`{sample.get('arm_id')}` | "
                f"`{sample.get('run_group_id')}` | "
                f"`{sample.get('official_score')}` | "
                f"`{sample.get('failure_class')}` |"
            )
    if archive.get("truncated"):
        lines.append("")
        lines.append("Archived samples are truncated.")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_merge_markdown(payload: dict[str, object]) -> str:
    merge = payload.get("merge") if isinstance(payload.get("merge"), dict) else {}
    read_boundary = (
        payload.get("read_boundary")
        if isinstance(payload.get("read_boundary"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Merge",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- source_ledger_count: `{merge.get('source_ledger_count')}`",
        f"- source_run_count: `{merge.get('source_run_count')}`",
        f"- considered_run_count: `{merge.get('considered_run_count')}`",
        f"- merged_run_count: `{merge.get('merged_run_count')}`",
        f"- new_run_id_count: `{merge.get('new_run_id_count')}`",
        f"- target_run_count: `{merge.get('target_run_count')}`",
        f"- source paths recorded: `{merge.get('source_paths_recorded')}`",
        f"- ledger: `{payload.get('ledger_path')}`",
        f"- compact only: `{read_boundary.get('compact_only')}`",
        f"- raw logs read: `{read_boundary.get('raw_logs_read')}`",
        f"- task text read: `{read_boundary.get('task_text_read')}`",
    ]
    if merge.get("skipped_by_reason"):
        lines.append(f"- skipped_by_reason: `{merge.get('skipped_by_reason')}`")
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def render_benchmark_run_ledger_aggregate_markdown(payload: dict[str, object]) -> str:
    aggregate = payload.get("aggregate") if isinstance(payload.get("aggregate"), dict) else {}
    distribution = (
        aggregate.get("distribution")
        if isinstance(aggregate.get("distribution"), dict)
        else {}
    )
    score_summary = (
        aggregate.get("countable_score_summary")
        if isinstance(aggregate.get("countable_score_summary"), dict)
        else {}
    )
    selection_policy = (
        aggregate.get("selection_policy")
        if isinstance(aggregate.get("selection_policy"), dict)
        else {}
    )
    target_lane = (
        selection_policy.get("target_lane")
        if isinstance(selection_policy.get("target_lane"), dict)
        else {}
    )
    lines = [
        "# Benchmark Run Ledger Current Aggregate",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- dry_run: `{payload.get('dry_run')}`",
        f"- updated: `{payload.get('updated')}`",
        f"- benchmark: `{aggregate.get('benchmark_id')}`",
        f"- canonical_covered: `{aggregate.get('canonical_covered')}` / `{aggregate.get('canonical_total')}`",
        f"- countable_cases: `{score_summary.get('countable_case_count')}`",
        f"- countable_score_sum: `{score_summary.get('countable_score_sum')}`",
        f"- countable_score_mean: `{score_summary.get('countable_score_mean')}`",
        f"- distribution: `{distribution}`",
        f"- selection_rule: `{selection_policy.get('rule')}`",
        f"- target_lane_enabled: `{target_lane.get('enabled')}`",
        f"- target_lane_id: `{target_lane.get('lane_id')}`",
        f"- deduped_run_count: `{aggregate.get('deduped_run_count')}`",
        f"- source_ledger_files: `{aggregate.get('source_ledger_files')}`",
        f"- output_json: `{payload.get('output_json')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def register_benchmark_run_ledger_maintenance_commands(
    benchmark_subparsers: argparse._SubParsersAction,
) -> None:
    benchmark_run_ledger_archive_parser = benchmark_subparsers.add_parser(
        "run-ledger-archive",
        help=(
            "Mark matching benchmark_run_ledger_v0 rows archived. Archived rows "
            "remain in JSON but are excluded from default current-case views."
        ),
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON. Markdown is rendered next to it.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--benchmark-id",
        required=True,
        help="Benchmark id whose matching runs should be archived.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--reason",
        required=True,
        help="Public-safe reason recorded on archived rows.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--archive-batch-id",
        help="Optional stable archive batch id. Defaults to a deterministic short id.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--run-group-contains",
        action="append",
        default=[],
        help=(
            "Archive runs whose run_group_id contains this substring. May be "
            "passed multiple times."
        ),
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--keep-run-group-contains",
        action="append",
        default=[],
        help=(
            "Keep runs whose run_group_id contains this substring even when "
            "they match the broader archive scope. May be passed multiple times."
        ),
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Archive only this case id. May be passed multiple times.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--arm-id",
        action="append",
        default=[],
        help="Archive only this arm id. May be passed multiple times.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--archive-all-matching-benchmark",
        action="store_true",
        help=(
            "Allow archiving every run in --benchmark-id except explicit keep "
            "filters. Required when no narrower positive filter is supplied."
        ),
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview archive update without writing. This is the default.",
    )
    benchmark_run_ledger_archive_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the archive update and regenerated Markdown view.",
    )

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

    benchmark_run_ledger_merge_parser = benchmark_subparsers.add_parser(
        "run-ledger-merge",
        help=(
            "Merge multiple public benchmark_run_ledger_v0 JSON files into one "
            "canonical ledger. This reads compact ledger rows only."
        ),
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Target benchmark_run_ledger_v0 JSON. Markdown is rendered next to it.",
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--source-run-ledger-path",
        action="append",
        default=[],
        help="Source benchmark_run_ledger_v0 JSON. May be passed multiple times.",
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--source-run-ledger-glob",
        action="append",
        default=[],
        help=(
            "Glob for source benchmark_run_ledger_v0 JSON files. May be passed "
            "multiple times; matched source paths are not recorded in the output."
        ),
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--benchmark-id",
        action="append",
        default=[],
        help="Only merge runs for this benchmark id. May be passed multiple times.",
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--run-group-contains",
        action="append",
        default=[],
        help=(
            "Only merge runs whose run_group_id contains this public-safe token. "
            "May be passed multiple times."
        ),
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview merge update without writing. This is the default.",
    )
    benchmark_run_ledger_merge_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the merged benchmark run ledger.",
    )

    benchmark_run_ledger_aggregate_parser = benchmark_subparsers.add_parser(
        "run-ledger-aggregate",
        help=(
            "Build a current-case aggregate from benchmark_run_ledger_v0 rows. "
            "Countable official results outrank later missing or infra rows."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Primary benchmark_run_ledger_v0 JSON.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--source-run-ledger-path",
        action="append",
        default=[],
        help="Additional source benchmark_run_ledger_v0 JSON. May be passed multiple times.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--source-run-ledger-glob",
        action="append",
        default=[],
        help=(
            "Glob for additional source benchmark_run_ledger_v0 JSON files. "
            "Matched paths are counted but not recorded in output."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--benchmark-id",
        default="skillsbench@1.1",
        help="Benchmark id to aggregate.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--canonical-case-id",
        action="append",
        default=[],
        help="Canonical case id. May be passed multiple times.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--canonical-case-ids-file",
        help="Text file with one canonical case id per line.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--canonical-case-root",
        help=(
            "Directory whose immediate child directories are canonical case ids. "
            "Use this for benchmark task roots so sanity/preflight tasks outside "
            "the canonical root do not enter the denominator."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--include-noncanonical-sanity-sources",
        action="store_true",
        help=(
            "Keep explicit canonical ids whose ledger rows prove they came from "
            "sanity/noncanonical task sources. Formal SkillsBench aggregates "
            "leave this off so sanity fixtures do not enter the denominator."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--target-lane-id",
        help=(
            "Optional public-safe label for a target lane aggregate, such as "
            "codex-cli-goal-xhigh. This is metadata; matching is controlled by "
            "the run-group substring flags."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--target-run-group-contains",
        action="append",
        default=[],
        help=(
            "Run-group substring for runs in the target lane. May be repeated. "
            "When target backfill substrings are also set, matching target runs "
            "that do not match backfill are treated as current evidence."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--target-current-run-group-contains",
        action="append",
        default=[],
        help=(
            "Run-group substring for current evidence inside the target lane. "
            "May be repeated. Use this only when current evidence cannot be "
            "expressed as target minus backfill."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--target-backfill-run-group-contains",
        action="append",
        default=[],
        help=(
            "Run-group substring for lower-priority backfill evidence inside "
            "the target lane, such as skillsbench-codex-cli-goal-xhigh-full87-."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--output-json",
        help="Optional output JSON path for the aggregate.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview aggregate without writing. This is the default.",
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--execute",
        action="store_true",
        help="Write --output-json.",
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
