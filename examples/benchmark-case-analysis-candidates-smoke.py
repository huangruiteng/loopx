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

from loopx.benchmark_case_analysis import (  # noqa: E402
    BENCHMARK_CASE_ANALYSIS_CANDIDATE_REPORT_SCHEMA_VERSION,
    BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION,
    apply_accepted_case_analysis_records,
    build_case_analysis_candidate_report,
    build_case_analysis_upsert_proposals,
    render_case_analysis_markdown,
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
            },
            "terminal-bench@2.0": {
                "benchmark_id": "terminal-bench@2.0",
                "cases": {
                    "coverage-row-only": {
                        "case_id": "coverage-row-only",
                        "latest_decision": {
                            "decision": "paired_baseline_solved_treatment_preserved"
                        },
                        "runs": [
                            {"run_id": "baseline", "official_score": 1.0},
                            {"run_id": "treatment", "official_score": 1.0},
                        ],
                    }
                },
            },
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
        "terminal_bench_current_protocol_coverage": {
            "schema_version": "terminal_bench_current_protocol_coverage_v0",
            "rows": [
                {
                    "case_id": "coverage-row-only",
                    "decision": "paired_baseline_solved_treatment_preserved",
                    "case_analysis_status": "coverage_row_only_no_deep_case_note_yet",
                }
            ],
        },
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


def test_proposed_records_from_fixture() -> None:
    proposals = build_case_analysis_upsert_proposals(
        ledger=fixture_ledger(),
        analysis=fixture_analysis(),
    )
    assert len(proposals) == 2, proposals
    first = proposals[0]
    assert first["schema_version"] == (
        BENCHMARK_CASE_ANALYSIS_UPSERT_PROPOSAL_SCHEMA_VERSION
    ), first
    assert first["proposal_status"] == "proposal_only_not_applied", first
    assert first["case_id"] == "new-no-uplift", first
    assert first["classification"] == "no_uplift_candidate_proposal", first
    assert first["source_boundary"]["proposal_only"] is True, first
    assert first["source_boundary"]["raw_logs_recorded"] is False, first
    assert first["source_boundary"]["raw_task_text_recorded"] is False, first
    assert first["source_boundary"]["trajectory_recorded"] is False, first
    assert_public_safe(json.dumps(proposals, ensure_ascii=False))

    report = build_case_analysis_candidate_report(
        ledger=fixture_ledger(),
        analysis=fixture_analysis(),
        include_proposed_records=True,
        proposal_limit=1,
    )
    assert report["candidate_count"] == 2, report
    assert report["proposed_record_count"] == 1, report
    assert len(report["proposed_records"]) == 1, report
    assert "Proposed Case-Analysis Records" in (
        render_case_analysis_candidate_report_markdown(report)
    )
    assert_public_safe(render_case_analysis_candidate_report_markdown(report))


def test_generated_safe_acceptance_policy_from_fixture() -> None:
    proposals = build_case_analysis_upsert_proposals(
        ledger=fixture_ledger(),
        analysis=fixture_analysis(),
        acceptance_policy="generated-safe",
    )
    assert len(proposals) == 2, proposals
    assert [proposal["proposal_status"] for proposal in proposals] == [
        "accepted_generated_not_applied",
        "accepted_generated_not_applied",
    ], proposals
    assert proposals[0]["classification"] == "generated_no_uplift_asset", proposals
    assert proposals[0]["source_boundary"]["proposal_only"] is False, proposals
    assert proposals[0]["source_boundary"]["accepted_generated_case_analysis"] is True
    assert proposals[0]["acceptance_policy"]["accepted"] is True, proposals

    result = apply_accepted_case_analysis_records(
        analysis=fixture_analysis(),
        records=proposals,
    )
    assert result["added_count"] == 2, result
    assert result["skipped_count"] == 0, result
    by_case = {
        (case["benchmark_id"], case["case_id"]): case
        for case in result["analysis"]["cases"]
    }
    generated = by_case[("bench@v1", "new-no-uplift")]
    assert generated["classification"] == "generated_no_uplift_asset", generated
    assert generated["evidence_status"] == (
        "generated_from_compact_benchmark_run_ledger"
    ), generated
    assert generated["source_boundary"]["raw_logs_recorded"] is False, generated
    markdown = render_case_analysis_markdown(
        result["analysis"],
        existing_markdown="old generated header\n\n## Treatment Policy Control Set\n\nkeep me\n",
    )
    assert "new-no-uplift" in markdown, markdown
    assert "generated no-uplift asset" in markdown, markdown
    assert "new-baseline-pass" in markdown, markdown
    assert "generated baseline-solved control asset" in markdown, markdown
    assert "## Treatment Policy Control Set" in markdown and "keep me" in markdown
    assert_public_safe(json.dumps(result["analysis"], ensure_ascii=False))
    assert_public_safe(markdown)


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
        proposals_output = subprocess.check_output(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
                "--ledger",
                str(ledger_path),
                "--analysis",
                str(analysis_path),
                "--include-proposed-records",
                "--proposal-limit",
                "1",
            ],
            text=True,
        )
        proposal_report = json.loads(proposals_output)
        assert proposal_report["candidate_count"] == 2, proposal_report
        assert proposal_report["proposed_record_count"] == 1, proposal_report
        assert proposal_report["proposed_records"][0]["proposal_status"] == (
            "proposal_only_not_applied"
        ), proposal_report
        assert_public_safe(proposals_output)
        accepted_output = root / "accepted-analysis.json"
        accepted_markdown = root / "accepted-analysis.md"
        (root / "analysis.md").write_text(
            "old generated header\n\n## Treatment Policy Control Set\n\npreserve-details\n",
            encoding="utf-8",
        )
        accepted_report_output = subprocess.check_output(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
                "--ledger",
                str(ledger_path),
                "--analysis",
                str(analysis_path),
                "--acceptance-policy",
                "generated-safe",
                "--apply-accepted",
                "--output-analysis",
                str(accepted_output),
                "--output-markdown",
                str(accepted_markdown),
            ],
            text=True,
        )
        accepted_report = json.loads(accepted_report_output)
        assert accepted_report["accepted_record_count"] == 2, accepted_report
        assert accepted_report["accepted_upsert"]["added_count"] == 2, (
            accepted_report
        )
        assert accepted_report["accepted_upsert"]["markdown_written"] is True, (
            accepted_report
        )
        accepted_analysis = json.loads(accepted_output.read_text(encoding="utf-8"))
        assert accepted_output.read_text(encoding="utf-8").lstrip().startswith(
            '{\n  "schema_version"'
        ), accepted_output.read_text(encoding="utf-8")[:120]
        accepted_cases = {
            (case["benchmark_id"], case["case_id"])
            for case in accepted_analysis["cases"]
        }
        assert ("bench@v1", "new-no-uplift") in accepted_cases, accepted_analysis
        accepted_markdown_text = accepted_markdown.read_text(encoding="utf-8")
        assert "new-no-uplift" in accepted_markdown_text, accepted_markdown_text
        assert "new-baseline-pass" in accepted_markdown_text, accepted_markdown_text
        assert "preserve-details" in accepted_markdown_text, accepted_markdown_text
        assert_public_safe(accepted_report_output)
        assert_public_safe(accepted_markdown_text)


def test_loopx_benchmark_cli_on_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="case-analysis-candidates-gh-cli-") as tmp:
        root = Path(tmp)
        ledger_path = root / "ledger.json"
        analysis_path = root / "analysis.json"
        ledger_path.write_text(json.dumps(fixture_ledger()), encoding="utf-8")
        analysis_path.write_text(json.dumps(fixture_analysis()), encoding="utf-8")
        output = subprocess.check_output(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "--format",
                "json",
                "benchmark",
                "case-analysis-candidates",
                "--run-ledger-path",
                str(ledger_path),
                "--case-analysis-path",
                str(analysis_path),
            ],
            text=True,
        )
        payload = json.loads(output)
        assert payload["ok"] is True, payload
        assert payload["report"]["candidate_count"] == 2, payload
        assert payload["read_boundary"]["compact_only"] is True, payload
        assert payload["read_boundary"]["raw_logs_read"] is False, payload
        assert payload["read_boundary"]["task_text_read"] is False, payload
        assert payload["read_boundary"]["trajectory_read"] is False, payload
        assert_public_safe(output)
        proposals_output = subprocess.check_output(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "--format",
                "json",
                "benchmark",
                "case-analysis-candidates",
                "--run-ledger-path",
                str(ledger_path),
                "--case-analysis-path",
                str(analysis_path),
                "--include-proposed-records",
                "--proposal-limit",
                "1",
            ],
            text=True,
        )
        proposals_payload = json.loads(proposals_output)
        assert proposals_payload["ok"] is True, proposals_payload
        assert proposals_payload["report"]["proposed_record_count"] == 1, (
            proposals_payload
        )
        assert proposals_payload["report"]["proposed_records"][0][
            "proposal_status"
        ] == "proposal_only_not_applied", proposals_payload
        assert_public_safe(proposals_output)
        accepted_output = root / "accepted-loopx-analysis.json"
        accepted_markdown = root / "accepted-loopx-analysis.md"
        analysis_path.with_suffix(".md").write_text(
            "old generated header\n\n## Treatment Policy Control Set\n\ncli-preserve-details\n",
            encoding="utf-8",
        )
        accepted_payload_output = subprocess.check_output(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "--format",
                "json",
                "benchmark",
                "case-analysis-candidates",
                "--run-ledger-path",
                str(ledger_path),
                "--case-analysis-path",
                str(analysis_path),
                "--acceptance-policy",
                "generated-safe",
                "--apply-accepted",
                "--output-case-analysis-path",
                str(accepted_output),
                "--output-case-analysis-markdown-path",
                str(accepted_markdown),
            ],
            text=True,
        )
        accepted_payload = json.loads(accepted_payload_output)
        assert accepted_payload["ok"] is True, accepted_payload
        assert accepted_payload["report"]["accepted_record_count"] == 2, (
            accepted_payload
        )
        assert accepted_payload["accepted_upsert"]["added_count"] == 2, (
            accepted_payload
        )
        assert accepted_payload["accepted_upsert"]["markdown_written"] is True, (
            accepted_payload
        )
        assert accepted_output.exists(), accepted_payload
        assert accepted_markdown.exists(), accepted_payload
        accepted_markdown_text = accepted_markdown.read_text(encoding="utf-8")
        assert "new-no-uplift" in accepted_markdown_text, accepted_markdown_text
        assert "cli-preserve-details" in accepted_markdown_text, accepted_markdown_text
        assert_public_safe(accepted_payload_output)
        assert_public_safe(accepted_markdown_text)
        markdown = subprocess.check_output(
            [
                str(REPO_ROOT / "scripts" / "loopx"),
                "benchmark",
                "case-analysis-candidates",
                "--run-ledger-path",
                str(ledger_path),
                "--case-analysis-path",
                str(analysis_path),
            ],
            text=True,
        )
        assert "# Benchmark Case-Analysis Candidates" in markdown, markdown
        assert "Read Boundary" in markdown, markdown
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
    proposal_output = subprocess.check_output(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "benchmark_case_analysis_candidates.py"),
            "--include-proposed-records",
            "--proposal-limit",
            "3",
        ],
        text=True,
    )
    assert_public_safe(proposal_output)
    proposal_report = json.loads(proposal_output)
    assert proposal_report["proposed_record_count"] == 3, proposal_report
    assert all(
        record["source_boundary"]["raw_logs_recorded"] is False
        and record["source_boundary"]["raw_task_text_recorded"] is False
        and record["source_boundary"]["trajectory_recorded"] is False
        and record["source_boundary"]["proposal_only"] is True
        for record in proposal_report["proposed_records"]
    ), proposal_report


def main() -> None:
    test_candidate_report_from_fixture()
    test_proposed_records_from_fixture()
    test_generated_safe_acceptance_policy_from_fixture()
    test_candidate_cli_on_fixture()
    test_loopx_benchmark_cli_on_fixture()
    test_default_assets_have_public_safe_candidates()
    print("benchmark-case-analysis-candidates-smoke ok")


if __name__ == "__main__":
    main()
