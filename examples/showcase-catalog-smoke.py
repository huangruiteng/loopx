#!/usr/bin/env python3
"""Smoke-test the public showcase catalog and case pages."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "docs" / "showcases" / "showcase-catalog.json"
SHOWCASES = REPO_ROOT / "docs" / "showcases" / "README.md"
PRIVATE_MARKERS = tuple(
    "".join(parts)
    for parts in (
        ("lark", "office.com"),
        ("internal", "-api-drive"),
        ("bytedance.com", "/wiki"),
        ("/", "Users/"),
        (".codex", "/goal-harness"),
        ("BEGIN", " PRIVATE ", "KEY"),
        ("Author", "ization:"),
        ("to", "ken="),
        ("pass", "word="),
    )
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_public_safe(path: Path) -> None:
    text = read(path)
    for marker in PRIVATE_MARKERS:
        assert marker not in text, f"{path}: private marker {marker!r}"


def main() -> int:
    catalog = json.loads(read(CATALOG))
    assert catalog["schema_version"] == "goal_harness_showcase_catalog_v0", catalog
    cases = catalog.get("cases")
    assert isinstance(cases, list) and len(cases) >= 2, catalog

    case_ids = {case.get("id") for case in cases}
    assert "2026-06-17-blocked-p0-safe-rotation" in case_ids, case_ids
    assert "2026-06-19-dynamic-workflow-hardware-agent" in case_ids, case_ids
    assert "2026-06-19-goal-harness-self-iteration" in case_ids, case_ids

    assert_public_safe(CATALOG)
    assert_public_safe(SHOWCASES)

    for case in cases:
        case_id = str(case.get("id") or "")
        page = REPO_ROOT / str(case.get("case_page") or "")
        assert page.is_file(), case
        assert_public_safe(page)
        assert case.get("title"), case
        assert case.get("headline"), case
        assert case.get("evidence_boundary"), case
        assert case.get("user_value"), case
        assert isinstance(case.get("pattern_tags"), list) and case["pattern_tags"], case
        frontend = case.get("frontend_card")
        assert isinstance(frontend, dict), case
        assert frontend.get("visual_metaphor"), case
        assert isinstance(frontend.get("story_beats"), list) and len(frontend["story_beats"]) >= 3, case

        demo_command = case.get("demo_command")
        if case.get("status") == "reproducible_synthetic_demo":
            assert isinstance(demo_command, str) and demo_command.startswith("python3 examples/"), case
            demo_path = REPO_ROOT / demo_command.split(" ", 2)[1]
            assert demo_path.is_file(), case
        if case.get("status") == "redacted_stub_pending_contributor_details":
            assert demo_command is None, case
            page_text = read(page)
            assert "public-safe stub" in page_text, case_id
            assert "No reproducible public demo is included yet" in page_text, case_id
        if case_id == "2026-06-19-goal-harness-self-iteration":
            assert case.get("status") == "public_evidence_case", case
            assert demo_command is None, case
            workload = case.get("workload_signal")
            assert isinstance(workload, dict), case
            assert workload.get("anchor_commit") == "0510dda", workload
            assert workload.get("scope") == "whole_public_repository_with_side_agent_slice", workload
            whole_repository = workload.get("whole_repository")
            assert isinstance(whole_repository, dict), workload
            assert whole_repository.get("commit_count", 0) >= 700, whole_repository
            assert whole_repository.get("files_touched", 0) >= 500, whole_repository
            assert whole_repository.get("insertions", 0) >= 200000, whole_repository
            assert whole_repository.get("deletions", 0) >= 40000, whole_repository
            recent_window = workload.get("recent_window")
            assert isinstance(recent_window, dict), workload
            assert recent_window.get("since") == "2026-06-18T00:00:00+08:00", recent_window
            assert recent_window.get("commit_count", 0) >= 170, recent_window
            assert recent_window.get("files_touched", 0) >= 180, recent_window
            side_agent_slice = workload.get("side_agent_slice")
            assert isinstance(side_agent_slice, dict), workload
            assert side_agent_slice.get("git_range") == "32b466d^..0510dda", side_agent_slice
            assert side_agent_slice.get("commit_count", 0) >= 14, side_agent_slice
            assert side_agent_slice.get("files_touched", 0) >= 45, side_agent_slice
            assert side_agent_slice.get("insertions", 0) >= 3000, side_agent_slice
            assert "side_agent_scope" in case.get("pattern_tags", []), case
            page_text = read(page)
            for phrase in (
                "Goal Harness was used to improve a fast-moving Goal Harness repository",
                "The public repository history shows a connected long-horizon feature chain",
                "Benchmark and adapter maturation",
                "Control-plane correctness",
                "Planning and dreaming lanes",
                "--side-agent-self-merged --evidence",
                "The workload signal is the whole public repository through fixed anchor commit",
                "32b466d^..0510dda",
                "completion evidence recorded self-merge and validation outcomes",
            ):
                assert phrase in page_text, phrase

    docs_index = read(REPO_ROOT / "docs" / "README.md")
    repo_readme = read(REPO_ROOT / "README.md")
    assert "showcases/README.md" in docs_index, "docs index must link showcases"
    assert "docs/showcases/README.md" in repo_readme, "README must link showcases"
    for phrase in (
        "Long-running agent work, without losing the plot.",
        "## See It In Action",
        "docs/showcases/cases/0617-blocked-p0-safe-rotation.md",
        "docs/showcases/cases/0619-goal-harness-self-iteration.md",
        "docs/showcases/cases/0619-dynamic-workflow-hardware-agent.md",
    ):
        assert phrase in repo_readme, phrase

    print("showcase-catalog-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
