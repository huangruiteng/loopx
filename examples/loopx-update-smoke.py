#!/usr/bin/env python3
"""Smoke-test the read-only LoopX update planning interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.self_update import (
    DEFAULT_UPDATE_REF,
    build_rollback_plan,
    build_update_plan,
    execute_rollback_plan,
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
            "current_version": "0.1.2",
            "release_id": "20260621T170342Z",
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
                    "version": "0.1.2",
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
        "current_version": "0.1.3",
        "release_id": "20260622T170342Z",
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
            "current_version": "0.1.3",
            "release_id": release_root.name,
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


def test_default_source_uses_stable_ref() -> None:
    payload = build_update_plan(doctor_payload=fake_doctor_payload())
    assert payload["source"]["ref"] == DEFAULT_UPDATE_REF == "stable", payload
    assert payload["source"]["channel"] == "github_archive_stable", payload
    assert payload["source"]["ref_source"] == "default_stable", payload
    assert "/tar.gz/stable" in payload["source"]["archive_url"], payload
    assert "LOOPX_REF=stable" in payload["plan"]["install_command"], payload


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
    assert "no update needed" in payload["recommended_action"], payload
    assert "force a refresh" in payload["recommended_action"], payload
    assert "--execute` if you accept" not in payload["recommended_action"], payload


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
    test_fresh_check_is_noop_recommendation()
    test_rollback_previous_executes_with_temp_home()
    test_rollback_restores_previous_when_doctor_fails()
    test_cli_check()
    test_cli_rollback_previous_with_temp_home()
    print("loopx-update-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
