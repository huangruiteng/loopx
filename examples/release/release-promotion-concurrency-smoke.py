#!/usr/bin/env python3
"""Regression coverage for collision-safe, revision-verifiable promotions."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
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


def assert_install_waits_for_promotion_guard(root: Path) -> None:
    env = {**install_env(root), "LOOPX_RELEASE_ID": "guarded"}
    releases_dir = Path(env["LOOPX_RELEASES_DIR"])
    releases_dir.mkdir(parents=True)
    guard_path = releases_dir / ".install-guard"
    legacy_lock = releases_dir / ".install-lock"
    with guard_path.open("a+", encoding="utf-8") as guard:
        fcntl.flock(guard.fileno(), fcntl.LOCK_EX)
        process = subprocess.Popen(
            [str(INSTALL_SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and process.poll() is None:
                assert not legacy_lock.exists(), legacy_lock
                time.sleep(0.05)
            assert process.poll() is None, process.communicate()
        except Exception:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise
        finally:
            fcntl.flock(guard.fileno(), fcntl.LOCK_UN)

    stdout, stderr = process.communicate(timeout=120)
    assert process.returncode == 0, (stdout, stderr)
    assert release_path(stdout).is_dir(), stdout


def assert_legacy_lock_timeout_preserves_live_owner(root: Path) -> None:
    env = {**install_env(root), "LOOPX_RELEASE_ID": "live-owner-timeout"}
    releases_dir = Path(env["LOOPX_RELEASES_DIR"])
    legacy_lock = releases_dir / ".install-lock"
    legacy_lock.mkdir(parents=True)
    owner_pid = str(os.getpid())
    (legacy_lock / "pid").write_text(f"{owner_pid}\n", encoding="utf-8")

    fast_bin = root / "fast-sleep-bin"
    fast_bin.mkdir()
    fast_sleep = fast_bin / "sleep"
    fast_sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fast_sleep.chmod(0o755)
    env["PATH"] = f"{fast_bin}{os.pathsep}{env['PATH']}"

    try:
        process = subprocess.run(
            [str(INSTALL_SCRIPT)],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert process.returncode == 1, (process.stdout, process.stderr)
        assert "timed out waiting for another local install" in process.stderr
        assert legacy_lock.is_dir(), legacy_lock
        assert (legacy_lock / "pid").read_text(encoding="utf-8") == f"{owner_pid}\n"
    finally:
        if legacy_lock.exists():
            shutil.rmtree(legacy_lock)


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
    assert len(set(release_paths)) == len(processes), release_paths
    for path in release_paths:
        manifest = json.loads((path / "release.json").read_text(encoding="utf-8"))
        assert manifest["release_id"] == path.name, manifest

    wrapper = Path(env["LOOPX_BIN_DIR"]) / "loopx"
    assert wrapper.is_symlink(), wrapper
    assert wrapper.resolve().parents[1] in release_paths, wrapper.resolve()
    doctor_env = {**env, "PATH": f"{wrapper.parent}:{env['PATH']}"}
    standard_doctor = subprocess.run(
        [str(wrapper), "--format", "json", "doctor"],
        cwd=root,
        env=doctor_env,
        check=True,
        capture_output=True,
        text=True,
    )
    standard_payload = json.loads(standard_doctor.stdout)
    standard_check_ids = {item["id"] for item in standard_payload["checks"]}
    assert standard_payload["mode"] == "standard", standard_payload
    assert not {
        "command_package_same_root",
        "representative_cli_commands",
        "representative_cli_imports",
        "representative_package_paths",
    } & standard_check_ids, standard_payload

    deep_doctor = subprocess.run(
        [str(wrapper), "--format", "json", "doctor", "--deep"],
        cwd=root,
        env=doctor_env,
        check=True,
        capture_output=True,
        text=True,
    )
    deep_payload = json.loads(deep_doctor.stdout)
    deep_checks = {item["id"]: item for item in deep_payload["checks"]}
    assert deep_payload["mode"] == "deep", deep_payload
    for check_id in (
        "command_package_same_root",
        "representative_cli_commands",
        "representative_cli_imports",
        "representative_package_paths",
    ):
        assert deep_checks[check_id]["ok"] is True, deep_payload


def assert_incomplete_candidate_does_not_replace_default(root: Path) -> None:
    env = {**install_env(root), "LOOPX_RELEASE_ID": "broken-candidate"}
    wrapper = Path(env["LOOPX_BIN_DIR"]) / "loopx"
    good_target = wrapper.resolve(strict=True)

    broken_root = root / "broken-source"
    shutil.copytree(REPO_ROOT / "loopx", broken_root / "loopx")
    shutil.copytree(REPO_ROOT / "scripts", broken_root / "scripts")
    for filename in ("LICENSE", "README.md", "pyproject.toml"):
        shutil.copy2(REPO_ROOT / filename, broken_root / filename)
    (broken_root / "loopx" / "quota.py").unlink()

    result = subprocess.run(
        [str(broken_root / "scripts" / "install-local.sh")],
        cwd=broken_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout
    assert "release candidate doctor validation failed" in result.stderr, result.stderr
    assert wrapper.resolve(strict=True) == good_target, wrapper.resolve()
    assert not (Path(env["LOOPX_RELEASES_DIR"]) / "broken-candidate").exists()


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
        assert_install_waits_for_promotion_guard(root)
        assert_legacy_lock_timeout_preserves_live_owner(root)
        assert_concurrent_release_ids_are_distinct(root)
        assert_incomplete_candidate_does_not_replace_default(root)
        assert_resolved_archive_commit_is_recorded(root)
    print("release-promotion-concurrency-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
