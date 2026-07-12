#!/usr/bin/env python3
"""Smoke-test the read-only LoopX update planning interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx import __version__  # noqa: E402
from loopx.release_manifest import release_version_tag  # noqa: E402
from loopx.self_update import (
    DEFAULT_UPDATE_REF,
    _installer_env_for_source,
    build_rollback_plan,
    build_update_plan,
    execute_rollback_plan,
    render_update_plan_markdown,
)


def fake_doctor_payload() -> dict[str, object]:
    return {
        "path": {
            "loopx": "/home/user/.local/bin/loopx",
            "loopx_realpath": "/home/user/.local/share/loopx/releases/20260621T170342Z/scripts/loopx",
        },
        "package": {
            "release_root": "/home/user/.local/share/loopx/releases/20260621T170342Z",
        },
        "install_freshness": {
            "status": "stale",
            "requires_upgrade": True,
            "reason": "fixture is intentionally stale",
            "current_version": __version__,
            "current_version_tag": release_version_tag(),
            "release_id": "20260621T170342Z",
            "manifest_package_version": __version__,
            "manifest_package_version_tag": release_version_tag(),
            "manifest_package_version_matches_runtime": True,
        },
        "release_manifest": {
            "available": True,
            "path": "/home/user/.local/share/loopx/releases/20260621T170342Z/release.json",
            "manifest": {
                "schema_version": "loopx_release_manifest_v0",
                "source": {
                    "kind": "github_archive",
                    "repo": "example/loopx",
                    "ref": "stable",
                    "archive_url": "https://codeload.github.com/example/loopx/tar.gz/stable",
                    "archive_sha256": "abc123",
                },
                "package": {
                    "name": "loopx",
                    "version": __version__,
                    "version_tag": release_version_tag(),
                    "version_source": "loopx.__version__",
                },
                "skills": {
                    "digest": "skills123",
                    "items": {},
                },
            },
        },
    }


def fake_fresh_doctor_payload() -> dict[str, object]:
    payload = fake_doctor_payload()
    payload["install_freshness"] = {
        "status": "fresh",
        "requires_upgrade": False,
        "reason": "fixture is intentionally fresh",
        "current_version": __version__,
        "current_version_tag": release_version_tag(),
        "release_id": "20260622T170342Z",
        "manifest_package_version": __version__,
        "manifest_package_version_tag": release_version_tag(),
        "manifest_package_version_matches_runtime": True,
    }
    return payload


def fake_doctor_payload_for_release(release_root: Path) -> dict[str, object]:
    return {
        "path": {
            "loopx": str(release_root.parents[4] / ".local" / "bin" / "loopx"),
            "loopx_realpath": str(release_root / "scripts" / "loopx"),
        },
        "package": {
            "release_root": str(release_root),
        },
        "install_freshness": {
            "status": "fresh",
            "requires_upgrade": False,
            "reason": "fixture release",
            "current_version": __version__,
            "current_version_tag": release_version_tag(),
            "release_id": release_root.name,
            "manifest_package_version": __version__,
            "manifest_package_version_tag": release_version_tag(),
            "manifest_package_version_matches_runtime": True,
        },
    }


def write_fixture_release(home: Path, release_id: str, *, doctor_ok: bool = True) -> Path:
    script = home / ".local" / "share" / "loopx" / "releases" / release_id / "scripts" / "loopx"
    script.parent.mkdir(parents=True, exist_ok=True)
    doctor_body = (
        "  printf '{\"ok\": true, \"source\": \"rollback-smoke\"}\\n'\n"
        "  exit 0\n"
        if doctor_ok
        else "  printf '{\"ok\": false, \"source\": \"rollback-smoke\"}\\n'\n"
        "  exit 7\n"
    )
    script.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == \"--format json doctor\" ]]; then\n"
        f"{doctor_body}"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script.parent.parent


def test_module_plan() -> None:
    payload = build_update_plan(
        repo="example/loopx",
        ref="fixture",
        archive_url="https://example.invalid/loopx.tar.gz",
        doctor_payload=fake_doctor_payload(),
    )
    assert payload["ok"] is True, payload
    assert payload["mode"] == "update", payload
    assert payload["dry_run"] is True, payload
    assert payload["execute_requested"] is False, payload
    assert payload["current"]["requires_upgrade"] is True, payload
    assert payload["current"]["current_version"] == __version__, payload
    assert payload["current"]["current_version_tag"] == release_version_tag(), payload
    assert payload["current"]["manifest_package_version"] == __version__, payload
    assert payload["current"]["manifest_package_version_tag"] == release_version_tag(), payload
    assert payload["current"]["manifest_package_version_matches_runtime"] is True, payload
    assert payload["current"]["release_manifest_available"] is True, payload
    assert payload["current"]["release_manifest"]["source"]["ref"] == "stable", payload
    assert payload["current"]["release_manifest"]["source"]["archive_sha256"] == "abc123", payload
    assert payload["plan"]["mutates_loopx_runtime_state"] is False, payload
    assert payload["plan"]["mutates_release_install"] is False, payload
    assert payload["plan"]["backup"]["available"] is True, payload
    assert payload["plan"]["backup"]["rollback_release_id"] == "20260621T170342Z", payload
    assert "loopx update --rollback 20260621T170342Z" in payload["plan"]["backup"]["rollback_command"], payload
    assert "ln -sfn" not in payload["plan"]["backup"]["rollback_command"], payload
    assert "LOOPX_ARCHIVE_URL=https://example.invalid/loopx.tar.gz" in payload["plan"]["install_command"], payload
    rendered = render_update_plan_markdown(payload)
    assert f"Current version tag: `{release_version_tag()}`" in rendered, rendered
    assert f"Manifest package version tag: `{release_version_tag()}`" in rendered, rendered


def test_default_source_uses_stable_ref() -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        payload = build_update_plan(doctor_payload=fake_doctor_payload())
    assert payload["source"]["ref"] == DEFAULT_UPDATE_REF == "stable", payload
    assert payload["source"]["channel"] == "github_archive_stable", payload
    assert payload["source"]["ref_source"] == "default_stable", payload
    assert "/tar.gz/stable" in payload["source"]["archive_url"], payload
    assert "LOOPX_REF=stable" in payload["plan"]["install_command"], payload
    assert "LOOPX_ARCHIVE_URL=" not in payload["plan"]["install_command"], payload
    default_env = _installer_env_for_source(
        payload["source"],
        base_env={"LOOPX_ARCHIVE_URL": "https://stale.invalid/archive.tar.gz"},
    )
    assert "LOOPX_ARCHIVE_URL" not in default_env, default_env


def test_explicit_archive_url_reaches_installer() -> None:
    payload = build_update_plan(
        repo="example/loopx",
        ref="fixture",
        archive_url="https://example.invalid/loopx.tar.gz",
        doctor_payload=fake_doctor_payload(),
    )
    assert payload["source"]["channel"] == "github_archive_url_override", payload
    assert "LOOPX_ARCHIVE_URL=https://example.invalid/loopx.tar.gz" in payload["plan"]["install_command"], payload
    installer_env = _installer_env_for_source(payload["source"], base_env={})
    assert installer_env["LOOPX_ARCHIVE_URL"] == "https://example.invalid/loopx.tar.gz", installer_env


def test_fresh_check_is_noop_recommendation() -> None:
    payload = build_update_plan(
        repo="example/loopx",
        ref="fixture",
        archive_url="https://example.invalid/loopx.tar.gz",
        check_only=True,
        doctor_payload=fake_fresh_doctor_payload(),
    )
    assert payload["ok"] is True, payload
    assert payload["check_only"] is True, payload
    assert payload["current"]["requires_upgrade"] is False, payload
    assert payload["source_version_check"]["status"] == "skipped", payload
    assert "source version comparison was skipped" in payload["recommended_action"], payload


class FakeVersionResponse:
    def __init__(self, version: str) -> None:
        self.body = f'__version__ = "{version}"\n'.encode()

    def __enter__(self) -> "FakeVersionResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def test_check_compares_selected_source_version() -> None:
    with mock.patch("loopx.self_update.urlopen", return_value=FakeVersionResponse("9.9.9")) as fetch:
        payload = build_update_plan(
            repo="example/loopx",
            ref="stable",
            check_only=True,
            doctor_payload=fake_fresh_doctor_payload(),
        )
    source_check = payload["source_version_check"]
    assert source_check["status"] == "available", payload
    assert source_check["version"] == "9.9.9", payload
    assert source_check["version_tag"] == "v9.9.9", payload
    assert source_check["matches_current"] is False, payload
    assert "differs from installed version" in payload["recommended_action"], payload
    request = fetch.call_args.args[0]
    assert request.full_url == (
        "https://raw.githubusercontent.com/example/loopx/stable/loopx/__init__.py"
    ), request.full_url

    with mock.patch("loopx.self_update.urlopen", return_value=FakeVersionResponse(__version__)):
        current_payload = build_update_plan(
            repo="example/loopx",
            ref="stable",
            check_only=True,
            doctor_payload=fake_fresh_doctor_payload(),
        )
    assert current_payload["source_version_check"]["matches_current"] is True, current_payload
    assert "no update needed" in current_payload["recommended_action"], current_payload


def test_check_degrades_when_source_version_is_unavailable() -> None:
    with mock.patch("loopx.self_update.urlopen", side_effect=OSError("offline")):
        payload = build_update_plan(
            repo="example/loopx",
            ref="stable",
            check_only=True,
            doctor_payload=fake_fresh_doctor_payload(),
        )
    source_check = payload["source_version_check"]
    assert payload["ok"] is True, payload
    assert source_check["status"] == "unavailable", payload
    assert source_check["attempted"] is True, payload
    assert "could not be checked" in payload["recommended_action"], payload


def test_rollback_previous_executes_with_temp_home() -> None:
    with TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        previous_release = write_fixture_release(home, "20260621T170342Z")
        current_release = write_fixture_release(home, "20260622T170342Z")
        payload = build_rollback_plan(
            release_id="previous",
            doctor_payload=fake_doctor_payload_for_release(current_release),
            home=home,
        )
        assert payload["ok"] is True, payload
        assert payload["mode"] == "rollback", payload
        assert payload["plan"]["selected_release_id"] == previous_release.name, payload
        result = execute_rollback_plan(payload, home=home)
        assert result["ok"] is True, result
        loopx_bin = home / ".local" / "bin" / "loopx"
        assert loopx_bin.is_symlink(), loopx_bin
        assert loopx_bin.resolve() == (previous_release / "scripts" / "loopx").resolve(), loopx_bin.resolve()
        assert result["execution"]["doctor_returncode"] == 0, result


def test_rollback_restores_previous_when_doctor_fails() -> None:
    with TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        bad_release = write_fixture_release(home, "20260621T170342Z", doctor_ok=False)
        current_release = write_fixture_release(home, "20260622T170342Z")
        loopx_bin = home / ".local" / "bin" / "loopx"
        loopx_bin.parent.mkdir(parents=True, exist_ok=True)
        loopx_bin.symlink_to(current_release / "scripts" / "loopx")
        payload = build_rollback_plan(
            release_id=bad_release.name,
            doctor_payload=fake_doctor_payload_for_release(current_release),
            home=home,
        )
        assert payload["ok"] is True, payload
        result = execute_rollback_plan(payload, home=home)
        assert result["ok"] is False, result
        assert result["execution"]["doctor_returncode"] == 7, result
        assert result["execution"]["restored_previous_on_failure"] is True, result
        assert loopx_bin.resolve() == (current_release / "scripts" / "loopx").resolve(), loopx_bin.resolve()


def test_cli_check() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "update",
            "--format",
            "json",
            "--check",
            "--repo",
            "example/loopx",
            "--ref",
            "fixture",
            "--archive-url",
            "https://example.invalid/loopx.tar.gz",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["ok"] is True, payload
    assert payload["mode"] == "update", payload
    assert payload["check_only"] is True, payload
    assert payload["dry_run"] is True, payload
    assert payload["source"]["repo"] == "example/loopx", payload
    assert payload["source"]["ref"] == "fixture", payload
    assert payload["plan"]["mutates_loopx_runtime_state"] is False, payload


def test_cli_rollback_previous_with_temp_home() -> None:
    with TemporaryDirectory() as tmpdir:
        home = Path(tmpdir)
        previous_release = write_fixture_release(home, "20260621T170342Z")
        current_release = write_fixture_release(home, "20260622T170342Z")
        loopx_bin = home / ".local" / "bin" / "loopx"
        loopx_bin.parent.mkdir(parents=True, exist_ok=True)
        loopx_bin.symlink_to(current_release / "scripts" / "loopx")
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "loopx.cli",
                "update",
                "--format",
                "json",
                "--rollback",
                "previous",
            ],
            cwd=REPO_ROOT,
            env={"HOME": str(home), "PATH": f"{home / '.local' / 'bin'}:{os.environ.get('PATH', '')}"},
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
        payload = json.loads(result.stdout)
        assert payload["ok"] is True, payload
        assert payload["mode"] == "rollback", payload
        assert payload["plan"]["selected_release_id"] == previous_release.name, payload
        assert loopx_bin.resolve() == (previous_release / "scripts" / "loopx").resolve(), loopx_bin.resolve()


def main() -> int:
    test_module_plan()
    test_default_source_uses_stable_ref()
    test_explicit_archive_url_reaches_installer()
    test_fresh_check_is_noop_recommendation()
    test_check_compares_selected_source_version()
    test_check_degrades_when_source_version_is_unavailable()
    test_rollback_previous_executes_with_temp_home()
    test_rollback_restores_previous_when_doctor_fails()
    test_cli_check()
    test_cli_rollback_previous_with_temp_home()
    print("loopx-update-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
