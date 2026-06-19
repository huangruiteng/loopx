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
            assert workload.get("git_range") == "32b466d^..9acdaa2", workload
            assert workload.get("commit_count", 0) >= 10, workload
            assert workload.get("files_touched", 0) >= 40, workload
            assert workload.get("insertions", 0) >= 2500, workload
            assert "side_agent_scope" in case.get("pattern_tags", []), case
            page_text = read(page)
            for phrase in (
                "Goal Harness was used to improve Goal Harness itself",
                "--side-agent-self-merged --evidence",
                "The public self-iteration slice",
                "evidence writeback",
            ):
                assert phrase in page_text, phrase

    docs_index = read(REPO_ROOT / "docs" / "README.md")
    repo_readme = read(REPO_ROOT / "README.md")
    assert "showcases/README.md" in docs_index, "docs index must link showcases"
    assert "docs/showcases/README.md" in repo_readme, "README must link showcases"

    print("showcase-catalog-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
