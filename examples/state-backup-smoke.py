#!/usr/bin/env python3
"""Smoke-test local LoopX state backup planning and execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.state_backup import build_state_backup_plan, execute_state_backup_plan


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, object]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def seed_fixture(root: Path) -> tuple[Path, Path, Path]:
    home = root / "home"
    codex_home = home / ".codex"
    runtime = codex_home / "loopx"
    project = root / "project"

    write_json(runtime / "registry.global.json", {"schema_version": "0.1", "goals": [{"id": "fixture"}]})
    write_json(project / ".loopx" / "registry.json", {"schema_version": "0.1", "goals": [{"id": "fixture"}]})
    write_text(project / ".codex" / "goals" / "fixture" / "ACTIVE_GOAL_STATE.md", "# fixture\n")
    write_text(project / ".local" / "goals" / "fixture" / "ACTIVE_GOAL_STATE.md", "# local fixture\n")
    write_json(codex_home / "automations" / "fixture.json", {"automation_id": "fixture"})
    write_text(codex_home / "skills" / "loopx-fixture" / "SKILL.md", "# fixture skill\n")

    # This path lives under the default output dir and must not be captured.
    write_text(runtime / "backups" / "old" / "stale.txt", "stale backup\n")
    return project, runtime, codex_home


def run_cli(project: Path, runtime: Path, backup_id: str, env: dict[str, str]) -> dict[str, object]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--format",
            "json",
            "--runtime-root",
            str(runtime),
            "backup-state",
            "--project",
            str(project),
            "--backup-id",
            backup_id,
            "--execute",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    return json.loads(result.stdout)


def assert_archive(payload: dict[str, object]) -> None:
    archive_path = Path(str(payload["archive_path"]))
    manifest_path = Path(str(payload["manifest_path"]))
    assert archive_path.exists(), payload
    assert manifest_path.exists(), payload
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "loopx_state_backup_v0", manifest
    assert manifest["dry_run"] is False, manifest
    execution = manifest["execution"]
    assert execution["archive_sha256"], execution
    assert execution["archive_size_bytes"] > 0, execution
    with tarfile.open(archive_path, "r:gz") as archive:
        names = set(archive.getnames())
    assert "runtime-root/registry.global.json" in names, names
    assert "project/.loopx/registry.json" in names, names
    assert "project/.codex/goals/fixture/ACTIVE_GOAL_STATE.md" in names, names
    assert "project/.local/goals/fixture/ACTIVE_GOAL_STATE.md" in names, names
    assert "codex/automations/fixture.json" in names, names
    assert "codex/skills/loopx-fixture/SKILL.md" in names, names
    assert "manifest.json" in names, names
    assert "runtime-root/backups/old/stale.txt" not in names, names


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-state-backup-smoke-") as tmp:
        root = Path(tmp)
        project, runtime, codex_home = seed_fixture(root)
        env = {
            **os.environ,
            "HOME": str(codex_home.parent),
            "CODEX_HOME": str(codex_home),
            "PYTHONPATH": str(REPO_ROOT),
        }
        old_home = os.environ.get("HOME")
        old_codex_home = os.environ.get("CODEX_HOME")
        os.environ["HOME"] = str(codex_home.parent)
        os.environ["CODEX_HOME"] = str(codex_home)
        try:
            plan = build_state_backup_plan(project=project, runtime_root=runtime, backup_id="module-fixture")
            assert plan["ok"] is True, plan
            assert plan["dry_run"] is True, plan
            assert plan["summary"]["included_target_count"] >= 5, plan
            applied = execute_state_backup_plan(plan)
            assert applied["ok"] is True, applied
            assert applied["dry_run"] is False, applied
            assert_archive(applied)
        finally:
            if old_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = old_home
            if old_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_codex_home

        cli_payload = run_cli(project, runtime, "cli-fixture", env)
        assert cli_payload["ok"] is True, cli_payload
        assert cli_payload["summary"]["included_target_count"] >= 5, cli_payload
        assert_archive(cli_payload)

    print("state-backup-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
