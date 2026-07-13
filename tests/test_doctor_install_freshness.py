from __future__ import annotations

from datetime import datetime, timezone
import subprocess
from pathlib import Path

from loopx import __version__
from loopx.doctor import build_install_freshness, git_revision_relation


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
                "source": {"git_commit": installed_commit},
            },
        },
        comparison_source={
            "label": "loopx-canary",
            "root": str(tmp_path),
            "git_commit": comparison_commit,
            "revision_relation": revision_relation,
        },
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
    )

    assert relation == "installed_ahead"
    assert freshness["status"] == "fresh"
    assert freshness["requires_upgrade"] is False
    assert freshness["manifest_source_matches_comparison"] is False
    assert freshness["manifest_source_comparison_relation"] == "installed_ahead"


def test_newer_canary_stales_older_default_release(tmp_path: Path) -> None:
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
    )

    assert relation == "installed_behind"
    assert freshness["status"] == "stale"
    assert freshness["requires_upgrade"] is True
    assert "is behind loopx-canary" in str(freshness["reason"])
