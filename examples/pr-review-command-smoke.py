#!/usr/bin/env python3
"""Smoke-test the public-safe `loopx pr-review` command."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import loopx.pr_review as pr_review_module
from loopx.pr_review import _github_search_date

FIXTURE = REPO_ROOT / "examples" / "fixtures" / "pr-review.public.json"
PRIVATE_PATTERNS = [
    re.compile(r"/" + r"Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/" + r"private/"),
    re.compile(r"/tmp/"),
    re.compile(r"/var/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "loopx.cli", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


def assert_public_safe(payload: dict[str, object]) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    for pattern in PRIVATE_PATTERNS:
        if pattern.search(text):
            raise AssertionError(f"pr-review payload leaked private pattern {pattern.pattern!r}")


def main() -> int:
    assert _github_search_date("2026-06-28T00:00:00+08:00") == "2026-06-27"
    assert _github_search_date("2026-06-28T00:00:00Z") == "2026-06-28"
    calls: list[list[str]] = []

    def fake_run_gh_json(args: list[str], *, cwd: Path | None = None) -> object:
        calls.append(args)
        assert args[:2] == ["pr", "list"], calls
        assert "--search" in args and "updated:>=2026-06-27" in args, args
        return [
            {
                "number": 900,
                "title": "Runtime review fixture",
                "url": "https://github.com/owner/repo/pull/900",
                "state": "OPEN",
                "updatedAt": "2026-06-28T00:01:00Z",
                "files": [{"path": "loopx/status.py", "additions": 4, "deletions": 1}],
                "changedFiles": 1,
                "additions": 4,
                "deletions": 1,
                "statusCheckRollup": [],
            }
        ]

    original_run_gh_json = pr_review_module._run_gh_json
    try:
        pr_review_module._run_gh_json = fake_run_gh_json
        fetched = pr_review_module.fetch_github_pull_requests(
            repo="owner/repo",
            limit=10,
            state_filter="all",
            since="2026-06-28T00:00:00+08:00",
        )
    finally:
        pr_review_module._run_gh_json = original_run_gh_json
    assert len(calls) == 1, calls
    assert fetched[0]["number"] == 900, fetched
    assert fetched[0]["files"][0]["path"] == "loopx/status.py", fetched

    payload = json.loads(
        run_cli("--format", "json", "pr-review", "--fixture", str(FIXTURE), "--limit", "5").stdout
    )
    assert payload["schema_version"] == "loopx_pr_review_command_response_v0", payload
    request = payload["request"]
    assert request["command"] == "/loopx-pr-review", request
    assert (
        request["cli_command"]
        == "loopx pr-review [--repo owner/repo] [--state open|merged|all] [--since ISO]"
    ), request
    assert request["privacy_mode"] == "public_safe_github_metadata", request
    assert request["dry_run"] is True, request
    assert request["repository"] == "huangruiteng/loopx", request
    assert request["state_filter"] == "all", request
    assert payload["summary"]["total_pr_count"] == 4, payload["summary"]
    assert payload["summary"]["open_pr_count"] == 3, payload["summary"]
    assert payload["summary"]["merged_pr_count"] == 1, payload["summary"]
    assert payload["summary"]["post_merge_review_count"] == 1, payload["summary"]
    assert payload["summary"]["review_attention_count"] == 3, payload["summary"]
    assert payload["summary"]["draft_count"] == 1, payload["summary"]
    sequence = payload["review_sequence"]
    assert sequence[0]["number"] == 773, sequence
    assert sequence[-1]["number"] == 775, sequence
    assert any(item["number"] == 770 and item["state"] == "MERGED" for item in sequence), sequence
    assert sequence[0]["main_risk_level"] == "low", sequence[0]
    merged_sequence = next(item for item in sequence if item["number"] == 770)
    assert merged_sequence["main_risk_level"] == "high", merged_sequence
    first = payload["pull_requests"][0]
    assert first["number"] == 773, first
    assert "newcomer command path" in first["motivation"], first
    card = first["guided_review_card"]
    assert card["schema_version"] == "guided_pr_review_card_v0", card
    assert 100 <= len(card["brief"]) <= 210, card["brief"]
    assert card["brief"].startswith("动机："), card["brief"]
    assert "改动：" in card["brief"], card["brief"]
    assert "风险：" in card["brief"], card["brief"]
    assert "检查：" in card["brief"], card["brief"]
    assert "Review：" in card["brief"], card["brief"]
    assert "concrete_changes" in card, card
    detailed = first["detailed_change_analysis"]
    assert detailed["schema_version"] == "pr_detailed_change_analysis_v0", detailed
    assert "具体改动集中" in detailed["summary"], detailed
    assert detailed["area_breakdown"], detailed
    assert detailed["file_walkthrough"], detailed
    diff_evidence = detailed["diff_evidence"]
    assert diff_evidence["available"] is True, diff_evidence
    assert diff_evidence["source"] == "fixture_public_patch", diff_evidence
    assert diff_evidence["omitted_raw_patch"] is True, diff_evidence
    assert "public docs heading changed" in diff_evidence["top_signals"], diff_evidence
    assert detailed["per_file_diff_insights"], detailed
    first_insight = detailed["per_file_diff_insights"][0]
    assert first_insight["path"] == "docs/guides/newcomer-command-path.md", first_insight
    assert first_insight["added_lines"] >= 3, first_insight
    assert first_insight["change_story"], first_insight
    assert first_insight["review_question"], first_insight
    assert detailed["review_order"][0] == "docs/guides/newcomer-command-path.md", detailed
    first_file = detailed["file_walkthrough"][0]
    assert first_file["path"] == "docs/guides/newcomer-command-path.md", first_file
    assert "Review focus" not in first_file["meaning"], first_file
    assert first_file["review_focus"], first_file
    assert first["checks"]["counts"]["success"] == 2, first["checks"]
    assert "public_docs" in first["areas"], first["areas"]
    main_risk = first["main_regression_analysis"]
    assert main_risk["schema_version"] == "main_regression_analysis_v0", main_risk
    assert main_risk["risk_level"] == "low", main_risk
    assert any("Runtime regression risk is low" in item for item in main_risk["potential_regressions"]), main_risk
    merged = next(item for item in payload["pull_requests"] if item["number"] == 770)
    merged_main_risk = merged["main_regression_analysis"]
    assert merged_main_risk["risk_level"] == "high", merged_main_risk
    assert merged_main_risk["post_merge_review"] is True, merged_main_risk
    assert any("Control-plane routing" in item for item in merged_main_risk["potential_regressions"]), merged_main_risk
    assert any("post-merge" in item for item in merged_main_risk["verification_focus"]), merged_main_risk
    assert payload["boundary"]["absolute_paths_recorded"] is False, payload["boundary"]
    assert_public_safe(payload)

    open_only = json.loads(
        run_cli(
            "--format",
            "json",
            "pr-review",
            "--fixture",
            str(FIXTURE),
            "--state",
            "open",
            "--limit",
            "5",
        ).stdout
    )
    assert open_only["summary"]["total_pr_count"] == 3, open_only["summary"]
    assert open_only["summary"]["merged_pr_count"] == 0, open_only["summary"]

    windowed = json.loads(
        run_cli(
            "--format",
            "json",
            "pr-review",
            "--fixture",
            str(FIXTURE),
            "--since",
            "2026-06-27T12:20:00Z",
            "--limit",
            "5",
        ).stdout
    )
    assert windowed["request"]["since"] == "2026-06-27T12:20:00Z", windowed["request"]
    assert windowed["summary"]["total_pr_count"] == 3, windowed["summary"]
    assert windowed["summary"]["open_pr_count"] == 2, windowed["summary"]
    assert windowed["summary"]["merged_pr_count"] == 1, windowed["summary"]
    assert any(item["number"] == 770 for item in windowed["review_sequence"]), windowed["review_sequence"]

    markdown = run_cli("pr-review", "--fixture", str(FIXTURE), "--limit", "1").stdout
    assert "# Project PR Review Queue" in markdown, markdown
    assert "current gh repository" not in markdown, markdown
    assert "state_filter: `all`" in markdown, markdown
    assert "merged=`" in markdown, markdown
    assert "main_risk=`low`" in markdown, markdown
    assert "> 动机：" in markdown, markdown
    assert "- 动机:" in markdown, markdown
    assert "- 具体改动:" in markdown, markdown
    assert "- 详细改动分析:" in markdown, markdown
    assert "- 改动拆解:" in markdown, markdown
    assert "- 文件 walkthrough:" in markdown, markdown
    assert "- 真实 diff 证据:" in markdown, markdown
    assert "- hunk-level insights:" in markdown, markdown
    assert "raw_patch_omitted=`True`" in markdown, markdown
    assert "- 推荐阅读顺序:" in markdown, markdown
    assert "- 风险:" in markdown, markdown
    assert "- 检查:" in markdown, markdown
    assert "- Review prompt:" in markdown, markdown
    assert "main regression risk:" in markdown, markdown
    assert "potential main regressions:" in markdown, markdown
    assert "verification focus:" in markdown, markdown
    assert "## Review Sequence" in markdown, markdown
    assert "PR #773" in markdown, markdown
    assert "review prompts" in markdown, markdown

    print("pr-review-command-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
