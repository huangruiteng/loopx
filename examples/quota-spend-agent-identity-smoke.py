#!/usr/bin/env python3
"""Smoke-test spend-slot identity on registered multi-agent goals."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "examples" / "quota-plan-smoke.py"


def load_quota_plan_fixture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("quota_plan_smoke_fixture", FIXTURE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_quota(root: Path, registry_path: Path, runtime: Path, *args: str) -> tuple[dict, int]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "quota",
            *args,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    return json.loads(result.stdout), result.returncode


def main() -> int:
    fixture = load_quota_plan_fixture()

    with tempfile.TemporaryDirectory(prefix="loopx-quota-spend-agent-identity-") as tmp:
        root = Path(tmp)
        registry_path, runtime, project = fixture.write_cli_fixture(root, scoped_agents=True)
        index_path = runtime / "goals" / "near-limit-half" / "runs" / "index.jsonl"
        registry_before = registry_path.read_text(encoding="utf-8")
        index_before = index_path.read_text(encoding="utf-8")

        unscoped_payload, unscoped_code = run_quota(
            root,
            registry_path,
            runtime,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--scan-path",
            str(project),
        )
        before = unscoped_payload["before"]
        assert unscoped_code == 1, unscoped_payload
        assert unscoped_payload["ok"] is False, unscoped_payload
        assert unscoped_payload["dry_run"] is True, unscoped_payload
        assert unscoped_payload["appended"] is False, unscoped_payload
        assert unscoped_payload["registry_mutated"] is False, unscoped_payload
        assert unscoped_payload["agent_id"] is None, unscoped_payload
        assert before["effective_action"] == "automation_prompt_upgrade_required", unscoped_payload
        assert before["should_run"] is False, unscoped_payload
        assert registry_path.read_text(encoding="utf-8") == registry_before
        assert index_path.read_text(encoding="utf-8") == index_before

        scoped_payload, scoped_code = run_quota(
            root,
            registry_path,
            runtime,
            "spend-slot",
            "--goal-id",
            "near-limit-half",
            "--slots",
            "1",
            "--source",
            "heartbeat",
            "--execute",
            "--agent-id",
            fixture.SCOPED_AGENT_ID,
            "--scan-path",
            str(project),
        )
        assert scoped_code == 0, scoped_payload
        assert scoped_payload["ok"] is True, scoped_payload
        assert scoped_payload["appended"] is True, scoped_payload
        assert scoped_payload["agent_id"] == fixture.SCOPED_AGENT_ID, scoped_payload

    print("quota-spend-agent-identity-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
