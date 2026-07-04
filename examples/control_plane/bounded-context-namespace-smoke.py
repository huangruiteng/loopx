#!/usr/bin/env python3
"""Guard repo-local control-plane code against legacy projection shims."""

from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_IMPORT = "loopx.projections"
LEGACY_PACKAGE_PREFIX = "loopx/projections/"
TEXT_SUFFIXES = {".py", ".md"}
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}


def _git_ls_files(*patterns: str) -> list[str] | None:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", *patterns],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        return None
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _fallback_repo_files() -> list[str]:
    paths: list[str] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        paths.append(path.relative_to(REPO_ROOT).as_posix())
    return sorted(paths)


def tracked_text_files() -> list[Path]:
    files = _git_ls_files("*.py", "*.md")
    if files is None:
        files = [
            path
            for path in _fallback_repo_files()
            if Path(path).suffix in TEXT_SUFFIXES
        ]
    return [
        REPO_ROOT / line.strip()
        for line in files
        if line.strip() and (REPO_ROOT / line.strip()).exists()
    ]


def tracked_files() -> list[str]:
    files = _git_ls_files()
    if files is not None:
        return files
    return _fallback_repo_files()


def assert_no_tracked_legacy_projection_package() -> None:
    offenders = [
        path
        for path in tracked_files()
        if path.startswith(LEGACY_PACKAGE_PREFIX)
        and (REPO_ROOT / path).exists()
    ]
    assert offenders == [], (
        "legacy loopx/projections shims should not be kept for repo-local code; "
        "move implementations to loopx.control_plane.<bounded_context>",
        offenders,
    )


def assert_repo_local_imports_use_bounded_contexts() -> None:
    offenders: list[str] = []
    for path in tracked_text_files():
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        if LEGACY_IMPORT in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], {
        "legacy_import": LEGACY_IMPORT,
        "offenders": offenders[:20],
        "offender_count": len(offenders),
    }


def main() -> int:
    assert_no_tracked_legacy_projection_package()
    assert_repo_local_imports_use_bounded_contexts()
    print("bounded-context-namespace-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
