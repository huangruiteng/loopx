#!/usr/bin/env python3
"""Smoke-test the LoopX named release version contract."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from loopx import __version__  # noqa: E402
from loopx.doctor import build_install_freshness  # noqa: E402
from loopx.release_manifest import (  # noqa: E402
    build_release_manifest,
    package_release_metadata,
    release_version_tag,
)
from loopx.self_update import build_update_plan, render_update_plan_markdown  # noqa: E402


def pyproject_version() -> str:
    in_project = False
    for line in (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            break
        if in_project:
            match = re.match(r'^version\s*=\s*"([^"]+)"$', stripped)
            if match:
                return match.group(1)
    raise AssertionError("pyproject.toml [project].version is missing")


def installed_skill_fixture() -> dict[str, dict[str, bool]]:
    return {
        "loopx-project": {"exists": True, "required_phrases": True},
        "loopx-pr-review": {"exists": True, "required_phrases": True},
        "loopx-doc-registry": {"exists": True, "required_phrases": True},
        "loopx-self-repair": {"exists": True, "required_phrases": True},
    }


def manifest_payload(path: Path, manifest: dict[str, object]) -> dict[str, object]:
    return {
        "available": True,
        "path": str(path),
        "reason": None,
        "manifest": manifest,
    }


def main() -> int:
    expected_tag = f"v{__version__}"
    assert pyproject_version() == __version__
    assert release_version_tag() == expected_tag
    assert release_version_tag(__version__) == expected_tag
    assert package_release_metadata() == {
        "name": "loopx",
        "version": __version__,
        "version_tag": expected_tag,
        "version_source": "loopx.__version__",
    }

    with tempfile.TemporaryDirectory(prefix="loopx-release-version-contract-") as tmp:
        root = Path(tmp)
        release_root = root / "releases" / "20260702T000000Z"
        release_root.mkdir(parents=True)
        manifest = build_release_manifest(
            release_root=release_root,
            release_id=release_root.name,
            installed_at="2026-07-02T00:00:00+00:00",
            env={"LOOPX_REF": "stable"},
        )
        manifest_path = release_root / "release.json"
        manifest_package = manifest["package"]
        assert manifest_package["name"] == "loopx", manifest
        assert manifest_package["version"] == __version__, manifest
        assert manifest_package["version_tag"] == expected_tag, manifest
        assert manifest_package["version_source"] == "loopx.__version__", manifest

        freshness = build_install_freshness(
            command_path=release_root / "scripts" / "loopx",
            release_root=release_root,
            repo_root=REPO_ROOT,
            skills=installed_skill_fixture(),
            release_manifest=manifest_payload(manifest_path, manifest),
            now=datetime(2026, 7, 2, 1, tzinfo=timezone.utc),
        )
        assert freshness["status"] == "fresh", freshness
        assert freshness["requires_upgrade"] is False, freshness
        assert freshness["current_version"] == __version__, freshness
        assert freshness["current_version_tag"] == expected_tag, freshness
        assert freshness["manifest_package_version"] == __version__, freshness
        assert freshness["manifest_package_version_tag"] == expected_tag, freshness
        assert freshness["manifest_package_version_matches_runtime"] is True, freshness

        mismatched_manifest = {
            **manifest,
            "package": {
                "name": "loopx",
                "version": "9.9.9",
                "version_tag": "v9.9.9",
                "version_source": "fixture",
            },
        }
        mismatch = build_install_freshness(
            command_path=release_root / "scripts" / "loopx",
            release_root=release_root,
            repo_root=REPO_ROOT,
            skills=installed_skill_fixture(),
            release_manifest=manifest_payload(manifest_path, mismatched_manifest),
            now=datetime(2026, 7, 2, 1, tzinfo=timezone.utc),
        )
        assert mismatch["status"] == "repair_recommended", mismatch
        assert mismatch["requires_upgrade"] is True, mismatch
        assert mismatch["manifest_package_version_matches_runtime"] is False, mismatch
        assert "package version differs" in mismatch["reason"], mismatch

        update_plan = build_update_plan(
            doctor_payload={
                "path": {
                    "loopx": str(root / "home" / ".local" / "bin" / "loopx"),
                    "loopx_realpath": str(release_root / "scripts" / "loopx"),
                },
                "package": {"release_root": str(release_root)},
                "install_freshness": freshness,
                "release_manifest": manifest_payload(manifest_path, manifest),
            }
        )
        assert update_plan["current"]["current_version_tag"] == expected_tag, update_plan
        assert update_plan["current"]["manifest_package_version"] == __version__, update_plan
        assert update_plan["current"]["manifest_package_version_tag"] == expected_tag, update_plan
        assert update_plan["current"]["manifest_package_version_matches_runtime"] is True, update_plan
        rendered = render_update_plan_markdown(update_plan)
        assert f"Current version tag: `{expected_tag}`" in rendered, rendered
        assert f"Manifest package version tag: `{expected_tag}`" in rendered, rendered

    print("release-version-contract-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
