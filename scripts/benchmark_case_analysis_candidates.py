#!/usr/bin/env python3
"""Find public-safe benchmark case-analysis promotion candidates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_case_analysis import (  # noqa: E402
    apply_accepted_case_analysis_records,
    build_case_analysis_candidate_report,
    load_json,
    render_case_analysis_markdown,
    render_case_analysis_candidate_report_markdown,
)


DEFAULT_ROOT = REPO_ROOT / "docs" / "research" / "long-horizon-agent-benchmarks"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_ROOT / "benchmark-run-ledger.json",
        help="Compact benchmark-run-ledger JSON path.",
    )
    parser.add_argument(
        "--analysis",
        type=Path,
        default=DEFAULT_ROOT / "benchmark-case-analysis.json",
        help="Benchmark case-analysis JSON path.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format.",
    )
    parser.add_argument(
        "--include-proposed-records",
        action="store_true",
        help=(
            "Include proposal-only benchmark_case_analysis_v0 record drafts. "
            "This does not edit the case-analysis file."
        ),
    )
    parser.add_argument(
        "--proposal-limit",
        type=int,
        default=None,
        help="Maximum proposal records to include when --include-proposed-records is set.",
    )
    parser.add_argument(
        "--acceptance-policy",
        choices=("proposal-only", "generated-safe"),
        default="proposal-only",
        help=(
            "Policy for proposed records. generated-safe marks only narrow, "
            "compact-ledger-derived records as accepted for explicit upsert."
        ),
    )
    parser.add_argument(
        "--apply-accepted",
        action="store_true",
        help=(
            "Apply accepted generated-safe records to --output-analysis. "
            "This never reads raw logs/task text/trajectories."
        ),
    )
    parser.add_argument(
        "--output-analysis",
        type=Path,
        default=None,
        help="Output path for --apply-accepted. Required when applying.",
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
        default=None,
        help=(
            "Optional Markdown output path for --apply-accepted. The generated "
            "summary/table is refreshed from compact JSON and existing deep "
            "case notes are preserved when available."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    include_proposals = args.include_proposed_records or args.apply_accepted
    if args.apply_accepted and args.acceptance_policy != "generated-safe":
        raise SystemExit("--apply-accepted requires --acceptance-policy generated-safe")
    if args.apply_accepted and args.output_analysis is None:
        raise SystemExit("--apply-accepted requires --output-analysis")
    ledger = load_json(args.ledger)
    analysis = load_json(args.analysis)
    report = build_case_analysis_candidate_report(
        ledger=ledger,
        analysis=analysis,
        include_proposed_records=include_proposals,
        proposal_limit=args.proposal_limit,
        acceptance_policy=args.acceptance_policy,
    )
    if args.apply_accepted:
        result = apply_accepted_case_analysis_records(
            analysis=analysis,
            records=report.get("proposed_records", []),
        )
        args.output_analysis.write_text(
            json.dumps(
                result["analysis"],
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        markdown_written = False
        if args.output_markdown is not None:
            existing_markdown = None
            if args.output_markdown.exists():
                existing_markdown = args.output_markdown.read_text(encoding="utf-8")
            elif args.analysis.with_suffix(".md").exists():
                existing_markdown = args.analysis.with_suffix(".md").read_text(
                    encoding="utf-8"
                )
            args.output_markdown.write_text(
                render_case_analysis_markdown(
                    result["analysis"],
                    existing_markdown=existing_markdown,
                ),
                encoding="utf-8",
            )
            markdown_written = True
        report["accepted_upsert"] = {
            "output_written": True,
            "markdown_written": markdown_written,
            "added_count": result["added_count"],
            "skipped_count": result["skipped_count"],
        }
    if args.format == "markdown":
        sys.stdout.write(render_case_analysis_candidate_report_markdown(report))
    else:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
