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

from goal_harness.benchmark_case_analysis import (  # noqa: E402
    build_case_analysis_candidate_report,
    load_json,
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_case_analysis_candidate_report(
        ledger=load_json(args.ledger),
        analysis=load_json(args.analysis),
    )
    if args.format == "markdown":
        sys.stdout.write(render_case_analysis_candidate_report_markdown(report))
    else:
        sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
