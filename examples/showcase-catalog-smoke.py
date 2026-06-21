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
        (".codex", "/loopx"),
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
    assert catalog["schema_version"] == "loopx_showcase_catalog_v0", catalog
    cases = catalog.get("cases")
    assert isinstance(cases, list) and len(cases) >= 2, catalog

    case_ids = {case.get("id") for case in cases}
    assert "2026-06-17-blocked-p0-safe-rotation" in case_ids, case_ids
    assert "2026-06-19-dynamic-workflow-hardware-agent" in case_ids, case_ids
    assert "2026-06-19-loopx-self-iteration" in case_ids, case_ids
    frontstage_ids = [case.get("id") for case in cases if isinstance(case.get("frontend_card"), dict)]
    assert frontstage_ids[:3] == [
        "2026-06-17-blocked-p0-safe-rotation",
        "2026-06-19-loopx-self-iteration",
        "2026-06-19-dynamic-workflow-hardware-agent",
    ], frontstage_ids

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
        appendix = case.get("appendix_surface")
        assert isinstance(frontend, dict) or isinstance(appendix, dict), case
        if isinstance(frontend, dict):
            assert frontend.get("visual_metaphor"), case
            assert isinstance(frontend.get("story_beats"), list) and len(frontend["story_beats"]) >= 3, case
        else:
            assert appendix.get("reason"), case
            assert appendix.get("public_surface") == "appendix_only", case

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
        if case.get("status") == "public_safe_case_spec":
            assert demo_command is None, case
            assert isinstance(appendix, dict), case
            storyboard = case.get("storyboard_path")
            assert isinstance(storyboard, str) and storyboard.startswith("docs/showcases/"), case
            storyboard_path = REPO_ROOT / storyboard
            assert storyboard_path.is_file(), case
            assert_public_safe(storyboard_path)
            feedback_contract = case.get("feedback_contract_path")
            if feedback_contract is not None:
                assert isinstance(feedback_contract, str) and feedback_contract.startswith("docs/showcases/"), case
                feedback_contract_path = REPO_ROOT / feedback_contract
                assert feedback_contract_path.is_file(), case
                assert_public_safe(feedback_contract_path)
        if case_id == "2026-06-19-loopx-self-iteration":
            assert case.get("status") == "public_evidence_case", case
            assert demo_command is None, case
            workload = case.get("workload_signal")
            assert isinstance(workload, dict), case
            assert workload.get("anchor_commit") == "86d6d9d", workload
            assert workload.get("scope") == "whole_public_repository", workload
            whole_repository = workload.get("whole_repository")
            assert isinstance(whole_repository, dict), workload
            assert whole_repository.get("commit_count", 0) >= 800, whole_repository
            assert whole_repository.get("files_touched", 0) >= 570, whole_repository
            assert whole_repository.get("insertions", 0) >= 260000, whole_repository
            assert whole_repository.get("deletions", 0) >= 40000, whole_repository
            recent_window = workload.get("recent_window")
            assert isinstance(recent_window, dict), workload
            assert recent_window.get("since") == "2026-06-18T00:00:00+08:00", recent_window
            assert recent_window.get("commit_count", 0) >= 240, recent_window
            assert recent_window.get("files_touched", 0) >= 210, recent_window
            public_window = workload.get("public_window")
            assert isinstance(public_window, dict), workload
            assert public_window.get("calendar_days", 0) >= 19, public_window
            assert public_window.get("active_commit_days", 0) >= 16, public_window
            efficiency = workload.get("efficiency_model")
            assert isinstance(efficiency, dict), workload
            assert efficiency.get("baseline") == "AI-coding-assisted product process", efficiency
            estimated_days = efficiency.get("estimated_developer_days")
            assert isinstance(estimated_days, dict), efficiency
            assert estimated_days.get("low", 0) >= 50, estimated_days
            assert estimated_days.get("high", 0) >= estimated_days.get("low", 0), estimated_days
            assert "side_agent_scope" in case.get("pattern_tags", []), case
            assert "efficiency_evidence_model" in case.get("pattern_tags", []), case
            page_text = read(page)
            for phrase in (
                "LoopX was used to improve a fast-moving LoopX repository",
                "The public repository history shows a connected long-horizon feature chain",
                "Efficiency Evidence Model",
                "The baseline below already assumes competent AI coding help",
                "59-92 developer-days",
                "3.0x-4.7x calendar",
                "Benchmark and adapter maturation",
                "Control-plane correctness",
                "Planning and dreaming lanes",
                "--side-agent-self-merged --evidence",
                "The workload signal is the whole public repository through fixed anchor commit",
                "completion evidence recorded self-merge and validation outcomes",
            ):
                assert phrase in page_text, phrase

    docs_index = read(REPO_ROOT / "docs" / "README.md")
    repo_readme = read(REPO_ROOT / "README.md")
    assert "showcases/README.md" in docs_index, "docs index must link showcases"
    assert "docs/showcases/README.md" in repo_readme, "README must link showcases"
    for phrase in (
        "Loop engineering for long-running AI agents.",
        "https://huangruiteng.github.io/loopx/frontstage/",
        "docs/outreach/frontstage-demo-script.md",
        "## See It In Action",
        "docs/showcases/cases/0617-blocked-p0-safe-rotation.md",
        "docs/showcases/cases/0619-loopx-self-iteration.md",
        "docs/showcases/cases/0619-dynamic-workflow-hardware-agent.md",
    ):
        assert phrase in repo_readme, phrase

    print("showcase-catalog-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
