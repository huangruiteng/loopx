#!/usr/bin/env python3
"""Keep hierarchy tokens confined to the explicit peer migration boundary."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = (
    REPO_ROOT / "loopx",
    REPO_ROOT / "docs",
    REPO_ROOT / "skills",
    REPO_ROOT / "apps" / "presentation" / "dashboard" / "src",
    REPO_ROOT / "apps" / "presentation" / "dashboard" / "smoke",
    REPO_ROOT / "examples" / "fixtures",
)
SCAN_FILES = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.zh-CN.md",
    REPO_ROOT / "CONTRIBUTOR_TASKS.md",
    REPO_ROOT / "apps" / "presentation" / "dashboard" / "README.md",
    REPO_ROOT / "examples" / "status.example.json",
    REPO_ROOT / "examples" / "registry.example.json",
    REPO_ROOT / "examples" / "peer-agent-task-orchestration.registry.example.json",
    REPO_ROOT / "examples" / "complex-project-readonly-map.example.json",
    REPO_ROOT / "examples" / "dashboard-frontstage-browser-smoke.mjs",
    REPO_ROOT / "examples" / "dashboard-home-browser-smoke.mjs",
)
ALLOWED_LEGACY_PATHS = {
    REPO_ROOT / "loopx" / "control_plane" / "agents" / "legacy_migration.py",
    REPO_ROOT / "loopx" / "control_plane" / "todos" / "contract.py",
    REPO_ROOT / "docs" / "reference" / "protocols" / "peer-agent-runtime-v1.md",
    REPO_ROOT / "docs" / "project-agent-todo-contract.md",
    REPO_ROOT / "docs" / "product" / "agent-profile-contract.md",
}
LEGACY_PATTERN = re.compile(
    r"\bprimary_agent\b|\bprimary_review\b|\bside_agent\b|\bhandoff_agent\b|"
    r"\bagent_profile_v0\b|\bprimary_checkout\b|"
    r"\bprimary agent\b|\bside agent\b|\bside-agent\b|\bmain controller\b|"
    r"controller/sub-agent|controller-subagent|controller owns|"
    r'"role"\s*:\s*"(?:controller|subagent)"',
    re.IGNORECASE,
)
LEGACY_STABLE_IDENTIFIERS = ("showcase-side-agent-self-iteration",)


def candidate_files() -> list[Path]:
    files = list(SCAN_FILES)
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or "archive" in path.parts:
                continue
            if path.suffix.lower() not in {".py", ".md", ".json", ".html", ".ts", ".tsx", ".mjs"}:
                continue
            files.append(path)
    return sorted(set(files))


def main() -> int:
    for token in (
        "primary_agent",
        "primary_review",
        "side_agent",
        "handoff_agent",
        "agent_profile_v0",
        "primary_checkout",
    ):
        assert LEGACY_PATTERN.search(token), token
    for domain_term in ("primary_reviewers", "primary_review_score"):
        assert not LEGACY_PATTERN.search(domain_term), domain_term

    violations: list[str] = []
    for path in candidate_files():
        if path in ALLOWED_LEGACY_PATHS:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            scan_line = line
            for identifier in LEGACY_STABLE_IDENTIFIERS:
                scan_line = scan_line.replace(identifier, "")
            if LEGACY_PATTERN.search(scan_line):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
    assert not violations, "legacy agent hierarchy escaped migration boundary:\n" + "\n".join(
        violations[:40]
    )
    print("peer-agent-hard-cut-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
