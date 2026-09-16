"""Untracked entries git cannot hash must not break the change-window ledger."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from loopx.capabilities.repository_change_window.repository import (
    UNTRACKED_DIRECTORY_ENTRY_LIMIT,
    _untracked_directory_digest,
    repository_change_fingerprint,
    resolve_repository_context,
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    global_config = tmp_path / "empty-global-gitconfig"
    global_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "missing-system-gitconfig"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "LoopX Test")
    _git(repo, "config", "user.email", "loopx@example.invalid")
    _git(repo, "remote", "add", "origin", "git@example.invalid:example/repo.git")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-m", "base")
    return repo


def test_an_untracked_symlink_to_a_directory_still_produces_a_fingerprint(
    repository: Path,
) -> None:
    """A linked directory is one entry no object hash accepts."""

    # The link points outside the checkout, like a shared dependency directory.
    linked = repository.parent / "outside"
    linked.mkdir()
    (linked / "app.js").write_text("first\n", encoding="utf-8")
    (repository / "node_modules").symlink_to(linked, target_is_directory=True)

    # The test asserts the premise: git lists the link, and refuses to hash it.
    listed = _git(repository, "ls-files", "--others", "--exclude-standard")
    assert listed.splitlines() == ["node_modules"]
    refused = subprocess.run(
        ["git", "-C", str(repository), "hash-object", "--no-filters", "--", "node_modules"],
        capture_output=True,
    )
    assert refused.returncode != 0

    context = resolve_repository_context(repository)
    first = repository_change_fingerprint(context)

    assert first["contains_path_names"] is False
    # Same tree, same digest: the link participates instead of failing.
    assert first["digest"] == repository_change_fingerprint(context)["digest"]

    # Re-pointing the link is a content change, and the fingerprint sees it.
    elsewhere = repository.parent / "elsewhere"
    elsewhere.mkdir()
    (repository / "node_modules").unlink()
    (repository / "node_modules").symlink_to(elsewhere, target_is_directory=True)

    assert repository_change_fingerprint(context)["digest"] != first["digest"]


def test_an_untracked_symlink_to_a_file_keeps_its_target_as_content(
    repository: Path,
) -> None:
    """A file link keeps behaving like the blob git stores for it."""

    (repository / "first.txt").write_text("one\n", encoding="utf-8")
    (repository / "second.txt").write_text("two\n", encoding="utf-8")
    link = repository / "current.txt"
    link.symlink_to(repository / "first.txt")
    context = resolve_repository_context(repository)
    first = repository_change_fingerprint(context)["digest"]

    link.unlink()
    link.symlink_to(repository / "second.txt")

    assert repository_change_fingerprint(context)["digest"] != first


def test_the_directory_inventory_stays_bounded_and_says_when_it_truncates(
    repository: Path,
) -> None:
    """A directory entry is digested by a bounded inventory, never by its size."""

    build = repository / "build"
    build.mkdir()
    (build / "manifest.json").write_text('{"v": 1}\n', encoding="utf-8")
    complete = _untracked_directory_digest(repository, "build")

    assert complete == _untracked_directory_digest(repository, "build")
    (build / "extra.js").write_text("x\n", encoding="utf-8")
    assert _untracked_directory_digest(repository, "build") != complete

    bounded = []
    for index in range(UNTRACKED_DIRECTORY_ENTRY_LIMIT):
        bounded.append((build / f"chunk-{index:04d}.js"))
        bounded[-1].write_text("x\n", encoding="utf-8")
    truncated = _untracked_directory_digest(repository, "build")

    # Past the bound the digest stops reading, and records that it did.
    (build / "chunk-extra.js").write_text("x\n", encoding="utf-8")
    assert _untracked_directory_digest(repository, "build") == truncated
