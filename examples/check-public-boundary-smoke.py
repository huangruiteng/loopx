#!/usr/bin/env python3
"""Smoke-test check behavior in a fresh directory with no project registry."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DOC_MARKER = "https://" + "la" + "rk" + "office.example/doc"


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT)
    home = cwd / "home"
    home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(home)
    env.pop("GOAL_HARNESS_REGISTRY", None)
    return subprocess.run(
        [sys.executable, "-m", "goal_harness.cli", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        implicit = run_cli(root, "--format", "json", "check", "--scan-root", str(REPO_ROOT))
        if implicit.returncode != 0:
            raise AssertionError(implicit.stderr or implicit.stdout)
        payload = json.loads(implicit.stdout)
        if not payload.get("ok"):
            raise AssertionError(payload)
        warnings = payload.get("warnings") or []
        if not any("registry file does not exist" in str(item) for item in warnings):
            raise AssertionError(payload)

        explicit = run_cli(
            root,
            "--registry",
            str(root / "missing-registry.json"),
            "--format",
            "json",
            "check",
            "--scan-root",
            str(REPO_ROOT),
        )
        if explicit.returncode == 0:
            raise AssertionError(explicit.stdout)
        explicit_payload = json.loads(explicit.stdout)
        if explicit_payload.get("ok"):
            raise AssertionError(explicit_payload)

        project = root / "project"
        project.mkdir()
        (project / "README.md").write_text("public docs stay clean\n", encoding="utf-8")
        for dirname in [".local", ".goal-harness", ".goal-wrapper.local", "runtime"]:
            local_dir = project / dirname
            local_dir.mkdir(parents=True)
            (local_dir / "private.md").write_text(PRIVATE_DOC_MARKER, encoding="utf-8")

        local_only = run_cli(root, "--format", "json", "check", "--scan-root", str(project))
        if local_only.returncode != 0:
            raise AssertionError(local_only.stderr or local_only.stdout)
        local_only_payload = json.loads(local_only.stdout)
        if not local_only_payload.get("ok"):
            raise AssertionError(local_only_payload)
        if (local_only_payload.get("summary") or {}).get("errors"):
            raise AssertionError(local_only_payload)

        (project / "public.md").write_text(PRIVATE_DOC_MARKER, encoding="utf-8")
        public_leak = run_cli(root, "--format", "json", "check", "--scan-root", str(project))
        if public_leak.returncode == 0:
            raise AssertionError(public_leak.stdout)
        public_payload = json.loads(public_leak.stdout)
        errors = public_payload.get("errors") or []
        if not any("public.md" in str(item) and "private_doc_url" in str(item) for item in errors):
            raise AssertionError(public_payload)

    print("check-public-boundary-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
