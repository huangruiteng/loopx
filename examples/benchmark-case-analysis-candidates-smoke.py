#!/usr/bin/env python3
"""Smoke-test public-safe benchmark case-analysis candidate detection."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.benchmark_case_analysis import (  # noqa: E402
    BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION,
    build_case_analysis_candidate_report,
    render_case_analysis_candidate_report_markdown,
)


FORBIDDEN_PATTERNS = [
    re.compile(r"/Users/"),
    re.compile(r"trajectory/", re.IGNORECASE),
    re.compile(r"\.local/"),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
]


def assert_public_safe(text: str) -> None:
    for pattern in FORBIDDEN_PATTERNS:
        assert not pattern.search(text), pattern.pattern


def fixture_ledger() -> dict:
    return {
        "schema_version": "benchmark_run_ledger_v0",
        "benchmarks": {
            "bench@v1": {
                "benchmark_id": "bench@v1",
                "cases": {
                    "existing-case": {
                        "case_id": "existing-case",
                        "latest_decision": {"decision": "paired_no_score_uplift"},
                        "runs": [{"run_id": "old"}],
                    },
                    "new-no-uplift": {
                        "case_id": "new-no-uplift",
                        "latest_decision": {"decision": "paired_no_score_uplift"},
                        "runs": [
                            {"run_id": "baseline", "official_score": 0.0},
                            {"run_id": "treatment", "official_score": 0.0},
                        ],
                    },
                    "new-baseline-pass": {
                        "case_id": "new-baseline-pass",
                        "latest_decision": {
                            "decision": "baseline_passed_not_current_treatment_priority"
                        },
                        "runs": [{"run_id": "pass", "official_score": 1.0}],
                    },
                    "empty-case": {
                        "case_id": "empty-case",
                        "latest_decision": {"decision": "no_runs_recorded"},
                        "runs": [],
                    },
                },
            }
        },
    }


def fixture_analysis() -> dict:
    return {
        "schema_version": "benchmark_case_analysis_v0",
        "cases": [
            {
                "benchmark_id": "bench@v1",
                "case_id": "existing-case",
                "analysis_id": "bench__existing-case__paired_no_score_uplift",
            }
        ],
    }


def test_candidate_report_from_fixture() -> None:
    report = build_case_analysis_candidate_report(
        ledger=fixture_ledger(),
        analysis=fixture_analysis(),
    )
    assert report["schema_version"] == (
        BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION
    ), report
    candidates = report["candidates"]
    assert [candidate["case_id"] for candidate in candidates] == [
        "new-no-uplift",
        "new-baseline-pass",
    ], candidates
    by_case = {candidate["case_id"]: candidate for candidate in candidates}
    assert by_case["new-no-uplift"]["candidate_class"] == (
        "paired_no_uplift_candidate"
    ), by_case
    assert by_case["new-no-uplift"]["promotion_priority"] == "P1", by_case
    assert by_case["new-baseline-pass"]["candidate_class"] == (
        "baseline_solved_control_candidate"
    ), by_case
    assert report["source_boundary"]["raw_logs_recorded"] is False, report
    assert report["source_boundary"]["raw_task_text_recorded"] is False, report
    assert report["source_boundary"]["trajectory_recorded"] is False, report
    assert_public_safe(json.dumps(report, ensure_ascii=False))
    assert_public_safe(render_case_analysis_candidate_report_markdown(report))


def test_candidate_cli_on_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="case-analysis-candidates-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        analysis_path = root / "analysis.json"
        ledger_path.write_text(json.dumps(fixture_ledger()), encoding="utf-8")
        analysis_path.write_text(json.dumps(fixture_analysis()), encoding="utf-8")
        output = subprocess.check_output(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
                "--ledger",
                str(ledger_path),
                "--analysis",
                str(analysis_path),
            ],
            text=True,
        )
        report = json.loads(output)
        assert report["candidate_count"] == 2, report
        markdown = subprocess.check_output(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
                "--ledger",
                str(ledger_path),
                "--analysis",
                str(analysis_path),
                "--format",
                "markdown",
            ],
            text=True,
        )
        assert "new-no-uplift" in markdown, markdown
        assert "existing-case" not in markdown, markdown
        assert_public_safe(markdown)


def test_default_assets_have_public_safe_candidates() -> None:
    output = subprocess.check_output(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
        ],
        text=True,
    )
    assert_public_safe(output)
    report = json.loads(output)
    assert report["candidate_count"] >= 1, report
    assert all(
        candidate["raw_logs_recorded"] is False
        and candidate["raw_task_text_recorded"] is False
        and candidate["trajectory_recorded"] is False
        for candidate in report["candidates"]
    ), report


def main() -> None:
    test_candidate_report_from_fixture()
    test_candidate_cli_on_fixture()
    test_default_assets_have_public_safe_candidates()
    print("benchmark-case-analysis-candidates-smoke ok")


if __name__ == "__main__":
    main()
