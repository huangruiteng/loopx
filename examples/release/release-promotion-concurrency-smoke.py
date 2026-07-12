#!/usr/bin/env python3
"""Regression coverage for collision-safe, revision-verifiable promotions."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-local.sh"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.release_manifest import build_release_manifest  # noqa: E402


def install_env(root: Path) -> dict[str, str]:
    home = root / "home"
    return {
        **os.environ,
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "LOOPX_BIN_DIR": str(home / ".local" / "bin"),
        "LOOPX_RELEASES_DIR": str(home / ".local" / "share" / "loopx" / "releases"),
        "LOOPX_SHELL_PROFILE": str(home / ".zshrc"),
        "LOOPX_INSTALL_CANARY": "0",
        "LOOPX_INSTALL_SKILL": "0",
        "LOOPX_INSTALL_SLASH_COMMANDS": "0",
        "LOOPX_PROMOTE_DEFAULT": "1",
        "LOOPX_PYTHON": sys.executable,
        "PATH": os.environ.get("PATH", ""),
        "SHELL": "/bin/zsh",
    }


def release_path(stdout: str) -> Path:
    prefix = "- release: "
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return Path(line.removeprefix(prefix))
    raise AssertionError(stdout)


def assert_concurrent_release_ids_are_distinct(root: Path) -> None:
    env = {**install_env(root), "LOOPX_RELEASE_ID": "same-second"}
    releases_dir = Path(env["LOOPX_RELEASES_DIR"])
    stale_lock = releases_dir / ".install-lock"
    stale_lock.mkdir(parents=True)
    (stale_lock / "pid").write_text("999999999\n", encoding="utf-8")
    processes = [
        subprocess.Popen(
            [str(INSTALL_SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    completed = [process.communicate(timeout=120) for process in processes]
    for process, (stdout, stderr) in zip(processes, completed):
        assert process.returncode == 0, (stdout, stderr)

    release_paths = [release_path(stdout).resolve() for stdout, _ in completed]
    assert len(set(release_paths)) == 2, release_paths
    for path in release_paths:
        manifest = json.loads((path / "release.json").read_text(encoding="utf-8"))
        assert manifest["release_id"] == path.name, manifest

    wrapper = Path(env["LOOPX_BIN_DIR"]) / "loopx"
    assert wrapper.is_symlink(), wrapper
    assert wrapper.resolve().parents[1] in release_paths, wrapper.resolve()


def assert_resolved_archive_commit_is_recorded(root: Path) -> None:
    release_root = root / "manifest-release"
    release_root.mkdir()
    expected_commit = "1" * 40
    manifest = build_release_manifest(
        release_root=release_root,
        release_id="archive-fixture",
        source_root=None,
        env={
            "LOOPX_ARCHIVE_URL": "https://example.com/loopx.tar.gz",
            "LOOPX_RESOLVED_SOURCE_GIT_COMMIT": expected_commit,
        },
    )
    assert manifest["source"]["git_commit"] == expected_commit, manifest


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-release-promotion-concurrency-") as tmp:
        root = Path(tmp)
        assert_concurrent_release_ids_are_distinct(root)
        assert_resolved_archive_commit_is_recorded(root)
    print("release-promotion-concurrency-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
