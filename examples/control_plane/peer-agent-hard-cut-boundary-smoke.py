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
    REPO_ROOT / "examples" / "fixtures",
)
SCAN_FILES = (
    REPO_ROOT / "CONTRIBUTOR_TASKS.md",
    REPO_ROOT / "examples" / "status.example.json",
    REPO_ROOT / "examples" / "registry.example.json",
    REPO_ROOT / "examples" / "controller-subagents.registry.example.json",
)
ALLOWED_LEGACY_PATHS = {
    REPO_ROOT / "loopx" / "configure_goal.py",
    REPO_ROOT / "loopx" / "control_plane" / "agents" / "runtime_model.py",
    REPO_ROOT / "docs" / "reference" / "protocols" / "peer-agent-runtime-v1.md",
    REPO_ROOT / "docs" / "product" / "agent-profile-contract.md",
}
LEGACY_PATTERN = re.compile(
    r"primary_agent|side_agent|handoff_agent|agent_profile_v0|primary_checkout|"
    r"\bprimary agent\b|\bside agent\b|\bside-agent\b",
    re.IGNORECASE,
)


def candidate_files() -> list[Path]:
    files = list(SCAN_FILES)
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or "archive" in path.parts:
                continue
            if path.suffix.lower() not in {".py", ".md", ".json", ".html"}:
                continue
            files.append(path)
    return sorted(set(files))


def main() -> int:
    violations: list[str] = []
    for path in candidate_files():
        if path in ALLOWED_LEGACY_PATHS:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if LEGACY_PATTERN.search(line):
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
    assert not violations, "legacy agent hierarchy escaped migration boundary:\n" + "\n".join(
        violations[:40]
    )
    print("peer-agent-hard-cut-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
