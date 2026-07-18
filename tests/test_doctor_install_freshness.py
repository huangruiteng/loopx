from __future__ import annotations

from datetime import datetime, timezone
import subprocess
from pathlib import Path

from loopx import __version__
from loopx.doctor import (
    build_install_freshness,
    git_revision_relation,
    trusted_release_ref_for_root,
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(root: Path, text: str) -> str:
    (root / "fixture.txt").write_text(text, encoding="utf-8")
    _git(root, "add", "fixture.txt")
    _git(root, "commit", "-m", text)
    return _git(root, "rev-parse", "HEAD")


def _freshness(
    tmp_path: Path,
    *,
    installed_commit: str,
    comparison_commit: str,
    revision_relation: str,
    freshness_commit: str | None = None,
    freshness_relation: str | None = None,
    source_ref: str | None = None,
) -> dict[str, object]:
    return build_install_freshness(
        command_path=tmp_path / "loopx",
        release_root=tmp_path / "releases" / "20260713T030000Z",
        repo_root=tmp_path,
        skills={"loopx-project": {"exists": True, "required_phrases": True}},
        release_manifest={
            "available": True,
            "manifest": {
                "package": {"version": __version__},
                "source": {
                    "git_commit": installed_commit,
                    "ref": source_ref,
                },
            },
        },
        comparison_source={
            "label": "loopx-canary",
            "root": str(tmp_path),
            "git_commit": comparison_commit,
            "revision_relation": revision_relation,
        },
        freshness_source=(
            {
                "label": "loopx/loopx@main",
                "root": str(tmp_path),
                "git_commit": freshness_commit,
                "git_ref": "origin/main",
                "revision_relation": freshness_relation,
            }
            if freshness_commit
            else None
        ),
        now=datetime(2026, 7, 13, 4, tzinfo=timezone.utc),
    )


def test_older_canary_does_not_stale_newer_default_release(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "loopx@example.invalid")
    _git(tmp_path, "config", "user.name", "LoopX Test")
    older = _commit(tmp_path, "older")
    newer = _commit(tmp_path, "newer")

    relation = git_revision_relation(
        tmp_path,
        installed_commit=newer,
        comparison_commit=older,
    )
    freshness = _freshness(
        tmp_path,
        installed_commit=newer,
        comparison_commit=older,
        revision_relation=relation,
        freshness_commit=newer,
        freshness_relation="same",
    )

    assert relation == "installed_ahead"
    assert freshness["status"] == "fresh"
    assert freshness["requires_upgrade"] is False
    assert freshness["manifest_source_matches_comparison"] is False
    assert freshness["manifest_source_comparison_relation"] == "installed_ahead"


def test_newer_canary_does_not_stale_current_default_release(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "loopx@example.invalid")
    _git(tmp_path, "config", "user.name", "LoopX Test")
    older = _commit(tmp_path, "older")
    newer = _commit(tmp_path, "newer")

    relation = git_revision_relation(
        tmp_path,
        installed_commit=older,
        comparison_commit=newer,
    )
    freshness = _freshness(
        tmp_path,
        installed_commit=older,
        comparison_commit=newer,
        revision_relation=relation,
        freshness_commit=older,
        freshness_relation="same",
    )

    assert relation == "installed_behind"
    assert freshness["status"] == "fresh"
    assert freshness["requires_upgrade"] is False
    assert freshness["manifest_source_comparison_relation"] == "installed_behind"
    assert freshness["manifest_source_freshness_relation"] == "same"


def test_trusted_main_ref_stales_older_default_release(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "loopx@example.invalid")
    _git(tmp_path, "config", "user.name", "LoopX Test")
    older = _commit(tmp_path, "older")
    newer = _commit(tmp_path, "newer")

    freshness = _freshness(
        tmp_path,
        installed_commit=older,
        comparison_commit=newer,
        revision_relation="diverged",
        freshness_commit=newer,
        freshness_relation="installed_behind",
    )

    assert freshness["status"] == "stale"
    assert freshness["requires_upgrade"] is True
    assert "is behind loopx/loopx@main" in str(freshness["reason"])


def test_main_channel_upgrade_command_preserves_source_ref(tmp_path: Path) -> None:
    current = "a" * 40
    freshness = _freshness(
        tmp_path,
        installed_commit=current,
        comparison_commit=current,
        revision_relation="same",
        freshness_commit=current,
        freshness_relation="same",
        source_ref="main",
    )

    command = str(freshness["no_clone_upgrade_command"])
    assert (
        "curl -fsSL https://raw.githubusercontent.com/huangruiteng/loopx/main/"
        "scripts/install-from-github.sh | env LOOPX_REF=main bash"
    ) in command
    assert freshness["upgrade_command"] == command


def test_stable_channel_upgrade_command_keeps_public_default(tmp_path: Path) -> None:
    current = "a" * 40
    freshness = _freshness(
        tmp_path,
        installed_commit=current,
        comparison_commit=current,
        revision_relation="same",
        freshness_commit=current,
        freshness_relation="same",
        source_ref="stable",
    )

    command = str(freshness["no_clone_upgrade_command"])
    assert "LOOPX_REF=" not in command
    assert "scripts/install-from-github.sh | bash" in command
    assert freshness["upgrade_command"] == command


def test_unknown_canary_relation_does_not_stale_current_default_release(tmp_path: Path) -> None:
    current = "a" * 40
    freshness = _freshness(
        tmp_path,
        installed_commit=current,
        comparison_commit="b" * 40,
        revision_relation="unknown",
        freshness_commit=current,
        freshness_relation="same",
    )

    assert freshness["status"] == "fresh"
    assert freshness["requires_upgrade"] is False
    assert freshness["manifest_source_comparison_relation"] == "unknown"
    assert freshness["manifest_source_freshness_relation"] == "same"


def test_trusted_release_ref_matches_manifest_repository(tmp_path: Path) -> None:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "loopx@example.invalid")
    _git(tmp_path, "config", "user.name", "LoopX Test")
    commit = _commit(tmp_path, "main")
    _git(tmp_path, "remote", "add", "origin", "git@github.com:loopx/loopx.git")
    _git(tmp_path, "update-ref", "refs/remotes/origin/main", commit)

    trusted = trusted_release_ref_for_root(
        tmp_path,
        repository="loopx/loopx",
        ref="main",
    )

    assert trusted is not None
    assert trusted["git_commit"] == commit
    assert trusted["git_ref"] == "origin/main"
    assert (
        trusted_release_ref_for_root(
            tmp_path,
            repository="someone-else/loopx",
            ref="main",
        )
        is None
    )
