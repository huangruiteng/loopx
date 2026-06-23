from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

from ..benchmark_case_analysis import (
    apply_accepted_case_analysis_records,
    build_case_analysis_candidate_report,
    load_json as load_benchmark_case_analysis_json,
    render_case_analysis_candidate_report_markdown,
    render_case_analysis_markdown,
)
from ..benchmark_ledger import BENCHMARK_RUN_LEDGER_DEFAULT_PATH


PrintPayload = Callable[
    [dict[str, object], str, Callable[[dict[str, object]], str]],
    None,
]
OutputFormat = Callable[[argparse.Namespace], str]

BENCHMARK_RUN_LEDGER_CASE_ANALYSIS_COMMANDS = {"case-analysis-candidates"}


def render_benchmark_case_analysis_candidates_markdown(
    payload: dict[str, object],
) -> str:
    if payload.get("ok") and isinstance(payload.get("report"), dict):
        report = payload["report"]
        text = render_case_analysis_candidate_report_markdown(report)
        read_boundary = (
            payload.get("read_boundary")
            if isinstance(payload.get("read_boundary"), dict)
            else {}
        )
        return (
            text
            + "\n## Read Boundary\n\n"
            + f"- compact only: `{read_boundary.get('compact_only')}`\n"
            + f"- raw logs read: `{read_boundary.get('raw_logs_read')}`\n"
            + f"- task text read: `{read_boundary.get('task_text_read')}`\n"
            + f"- trajectory read: `{read_boundary.get('trajectory_read')}`\n"
            + (
                "\n## Accepted Upsert\n\n"
                f"- output_written: `{payload['accepted_upsert'].get('output_written')}`\n"
                f"- markdown_written: `{payload['accepted_upsert'].get('markdown_written')}`\n"
                f"- added_count: `{payload['accepted_upsert'].get('added_count')}`\n"
                f"- skipped_count: `{payload['accepted_upsert'].get('skipped_count')}`\n"
                if isinstance(payload.get("accepted_upsert"), dict)
                else ""
            )
        )
    lines = [
        "# Benchmark Case-Analysis Candidates",
        "",
        f"- ok: `{payload.get('ok')}`",
    ]
    if payload.get("error"):
        lines.append(f"- error: {payload.get('error')}")
    return "\n".join(lines) + "\n"


def register_benchmark_run_ledger_case_analysis_commands(
    benchmark_subparsers: argparse._SubParsersAction,
) -> None:
    benchmark_case_analysis_candidates_parser = benchmark_subparsers.add_parser(
        "case-analysis-candidates",
        help=(
            "Find public-safe benchmark case-analysis candidates from the compact "
            "benchmark run ledger and existing case-analysis keys."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--run-ledger-path",
        default=str(BENCHMARK_RUN_LEDGER_DEFAULT_PATH),
        help="Path to benchmark_run_ledger_v0 JSON.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--case-analysis-path",
        default=str(
            BENCHMARK_RUN_LEDGER_DEFAULT_PATH.with_name(
                "benchmark-case-analysis.json"
            )
        ),
        help="Path to benchmark_case_analysis_v0 JSON.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--include-proposed-records",
        action="store_true",
        help=(
            "Include proposal-only benchmark_case_analysis_v0 record drafts. "
            "This does not edit the case-analysis file."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--proposal-limit",
        type=int,
        default=None,
        help="Maximum proposal records to include when --include-proposed-records is set.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--acceptance-policy",
        choices=("proposal-only", "generated-safe"),
        default="proposal-only",
        help=(
            "Policy for proposed records. generated-safe marks only narrow, "
            "compact-ledger-derived records as accepted for explicit upsert."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--apply-accepted",
        action="store_true",
        help=(
            "Apply accepted generated-safe records to --output-case-analysis-path. "
            "This never reads raw logs/task text/trajectories."
        ),
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--output-case-analysis-path",
        default=None,
        help="Output path for --apply-accepted. Required when applying.",
    )
    benchmark_case_analysis_candidates_parser.add_argument(
        "--output-case-analysis-markdown-path",
        default=None,
        help=(
            "Optional Markdown output path for --apply-accepted. The generated "
            "summary/table is refreshed from compact JSON and existing deep "
            "case notes are preserved when available."
        ),
    )


def handle_benchmark_run_ledger_case_analysis_command(
    args: argparse.Namespace,
    *,
    print_payload: PrintPayload,
    output_format: OutputFormat,
) -> int | None:
    if args.benchmark_command not in BENCHMARK_RUN_LEDGER_CASE_ANALYSIS_COMMANDS:
        return None

    if args.benchmark_command == "case-analysis-candidates":
        try:
            if args.apply_accepted and args.acceptance_policy != "generated-safe":
                raise ValueError(
                    "--apply-accepted requires --acceptance-policy generated-safe"
                )
            if args.apply_accepted and not args.output_case_analysis_path:
                raise ValueError(
                    "--apply-accepted requires --output-case-analysis-path"
                )
            ledger = load_benchmark_case_analysis_json(args.run_ledger_path)
            analysis = load_benchmark_case_analysis_json(args.case_analysis_path)
            report = build_case_analysis_candidate_report(
                ledger=ledger,
                analysis=analysis,
                include_proposed_records=(
                    args.include_proposed_records or args.apply_accepted
                ),
                proposal_limit=args.proposal_limit,
                acceptance_policy=args.acceptance_policy,
            )
            payload = {
                "ok": True,
                "report": report,
                "run_ledger_path": str(args.run_ledger_path),
                "case_analysis_path": str(args.case_analysis_path),
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
            if args.apply_accepted:
                result = apply_accepted_case_analysis_records(
                    analysis=analysis,
                    records=report.get("proposed_records", []),
                )
                output_path = Path(args.output_case_analysis_path)
                output_path.write_text(
                    json.dumps(
                        result["analysis"],
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                markdown_written = False
                if args.output_case_analysis_markdown_path:
                    markdown_path = Path(args.output_case_analysis_markdown_path)
                    existing_markdown = None
                    if markdown_path.exists():
                        existing_markdown = markdown_path.read_text(
                            encoding="utf-8"
                        )
                    else:
                        default_markdown_path = Path(
                            args.case_analysis_path
                        ).with_suffix(".md")
                        if default_markdown_path.exists():
                            existing_markdown = default_markdown_path.read_text(
                                encoding="utf-8"
                            )
                    markdown_path.write_text(
                        render_case_analysis_markdown(
                            result["analysis"],
                            existing_markdown=existing_markdown,
                        ),
                        encoding="utf-8",
                    )
                    markdown_written = True
                payload["accepted_upsert"] = {
                    "output_written": True,
                    "markdown_written": markdown_written,
                    "added_count": result["added_count"],
                    "skipped_count": result["skipped_count"],
                }
        except Exception as exc:
            payload = {
                "ok": False,
                "run_ledger_path": str(args.run_ledger_path),
                "case_analysis_path": str(args.case_analysis_path),
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
            render_benchmark_case_analysis_candidates_markdown,
        )
        return 0 if payload.get("ok") else 1

    return None
