from __future__ import annotations

import argparse

from ..benchmark_ledger import BENCHMARK_RUN_LEDGER_DEFAULT_PATH


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
        "--active-case-id",
        action="append",
        default=[],
        help=(
            "Case id for a currently running or reserved case that should not be "
            "selected as runnable missing work. May be repeated."
        ),
    )
    benchmark_run_ledger_aggregate_parser.add_argument(
        "--active-case-ids-file",
        help="Text file with one currently running or reserved case id per line.",
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
