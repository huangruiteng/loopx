from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

from loopx import __version__
from loopx.self_update import build_update_plan


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLED_COMMIT = "1" * 40
TARGET_COMMIT = "2" * 40


class FakeVersionResponse:
    def __init__(self) -> None:
        self.body = f'__version__ = "{__version__}"\n'.encode()

    def __enter__(self) -> FakeVersionResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


def doctor_payload(
    *,
    installed_commit: str | None = INSTALLED_COMMIT,
    target_commit: str | None = TARGET_COMMIT,
    relation: str = "installed_behind",
    source_ref: str = "main",
) -> dict[str, object]:
    return {
        "path": {
            "loopx": "/home/user/.local/bin/loopx",
            "loopx_realpath": "/home/user/.local/share/loopx/releases/fixture/scripts/loopx",
        },
        "package": {
            "release_root": "/home/user/.local/share/loopx/releases/fixture",
        },
        "install_freshness": {
            "status": "stale" if relation == "installed_behind" else "fresh",
            "requires_upgrade": relation == "installed_behind",
            "current_version": __version__,
            "release_id": "fixture",
            "manifest_package_version": __version__,
            "manifest_package_version_matches_runtime": True,
            "manifest_source_repo": "example/loopx",
            "manifest_source_ref": source_ref,
            "manifest_source_git_commit": installed_commit,
            "freshness_source_label": f"example/loopx@{source_ref}",
            "freshness_source_git_commit": target_commit,
            "manifest_source_freshness_relation": relation,
        },
        "release_manifest": {
            "available": True,
            "manifest": {
                "source": {
                    "repo": "example/loopx",
                    "ref": source_ref,
                    "git_commit": installed_commit,
                }
            },
        },
    }


def build_check(doctor: dict[str, object], *, ref: str = "main") -> dict[str, object]:
    with mock.patch("loopx.self_update.urlopen", return_value=FakeVersionResponse()):
        return build_update_plan(
            repo="example/loopx",
            ref=ref,
            check_only=True,
            doctor_payload=doctor,
        )


def test_same_version_older_commit_requires_release_or_install_successor() -> None:
    payload = build_check(doctor_payload())

    assert payload["source_version_check"]["matches_current"] is True
    activation = payload["runtime_activation_qualification"]
    assert activation["decision"] == "release_or_install_successor_required"
    assert activation["runtime_active"] is False
    assert activation["installed_source_commit"] == INSTALLED_COMMIT
    assert activation["target_source_commit"] == TARGET_COMMIT
    assert activation["successor"] == {
        "required": True,
        "kind": "release_or_install",
    }
    assert "project a release/install successor" in payload["recommended_action"]


def test_equal_commit_proves_runtime_active() -> None:
    payload = build_check(
        doctor_payload(target_commit=INSTALLED_COMMIT, relation="same")
    )

    activation = payload["runtime_activation_qualification"]
    assert activation["decision"] == "runtime_active"
    assert activation["runtime_active"] is True
    assert activation["source_identity_matches"] is True
    assert activation["successor"] == {"required": False, "kind": None}


def test_missing_commit_lineage_never_proves_runtime_active() -> None:
    payload = build_check(doctor_payload(target_commit=None, relation="same"))

    activation = payload["runtime_activation_qualification"]
    assert activation["decision"] == "activation_qualification_required"
    assert activation["runtime_active"] is None
    assert activation["successor"] == {
        "required": True,
        "kind": "activation_qualification",
    }


def test_different_selected_source_never_reuses_unrelated_lineage() -> None:
    payload = build_check(
        doctor_payload(target_commit=INSTALLED_COMMIT, relation="same", source_ref="stable"),
        ref="main",
    )

    activation = payload["runtime_activation_qualification"]
    assert activation["decision"] == "activation_qualification_required"
    assert activation["runtime_active"] is None
    assert activation["source_identity_matches"] is False
    assert activation["qualified_source"]["ref"] == "stable"
    assert activation["selected_source"]["ref"] == "main"


def test_cli_check_qualifies_explicit_installed_doctor_snapshot(tmp_path: Path) -> None:
    doctor_path = tmp_path / "installed-doctor.json"
    doctor_path.write_text(json.dumps(doctor_payload()), encoding="utf-8")

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
            "main",
            "--archive-url",
            "https://example.invalid/loopx.tar.gz",
            "--installed-doctor-json",
            str(doctor_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["installed_doctor_source"] == "explicit_json"
    activation = payload["runtime_activation_qualification"]
    assert activation["decision"] == "release_or_install_successor_required"
    assert activation["installed_source_commit"] == INSTALLED_COMMIT
    assert activation["target_source_commit"] == TARGET_COMMIT


def test_cli_rejects_installed_doctor_snapshot_outside_check(tmp_path: Path) -> None:
    doctor_path = tmp_path / "installed-doctor.json"
    doctor_path.write_text(json.dumps(doctor_payload()), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "update",
            "--format",
            "json",
            "--dry-run",
            "--installed-doctor-json",
            str(doctor_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1, (result.stdout, result.stderr)
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"] == "--installed-doctor-json requires update --check"
