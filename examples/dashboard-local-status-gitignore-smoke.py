#!/usr/bin/env python3
"""Smoke-test dashboard local status exports stay outside git."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_ONLY_PATHS = [
    "apps/presentation/dashboard/public/status.local.json",
    "apps/presentation/dashboard/dist/status.local.json",
    "apps/presentation/dashboard/dist/index.html",
]


def git_check_ignore(path: str) -> str:
    result = subprocess.run(
        ["git", "check-ignore", "-v", path],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout


def main() -> int:
    for path in LOCAL_ONLY_PATHS:
        output = git_check_ignore(path)
        assert path in output, output

    readme = (REPO_ROOT / "apps/presentation/dashboard/README.md").read_text(encoding="utf-8")
    assert "`status.local.json` is intentionally git-ignored" in readme, readme
    assert "examples/status.example.json" in readme, readme

    print("dashboard-local-status-gitignore-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
