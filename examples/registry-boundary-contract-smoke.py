#!/usr/bin/env python3
"""Smoke-test registry boundary classification and CLI import wiring."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from goal_harness.registry import inspect_registry_boundary  # noqa: E402


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="goal-harness-registry-boundary-") as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        (root / ".gitignore").write_text(".goal-harness/\n", encoding="utf-8")

        local_registry = root / ".goal-harness" / "registry.json"
        local_registry.parent.mkdir()
        local_registry.write_text('{"goals":[]}\n', encoding="utf-8")
        local_payload = inspect_registry_boundary(local_registry)
        assert local_payload["ok"] is True, local_payload
        assert local_payload["boundary_kind"] == "project_local_private_registry", local_payload
        assert local_payload["github_push_allowed"] is False, local_payload
        assert local_payload["should_be_gitignored"] is True, local_payload
        assert local_payload["git"]["ignored"] is True, local_payload
        assert local_payload["path_recorded"] is False, local_payload

        public_fixture = root / "examples" / "registry.example.json"
        public_fixture.parent.mkdir()
        public_fixture.write_text('{"goals":[]}\n', encoding="utf-8")
        subprocess.run(
            ["git", "add", ".gitignore", "examples/registry.example.json"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        public_payload = inspect_registry_boundary(public_fixture)
        assert public_payload["ok"] is True, public_payload
        assert public_payload["boundary_kind"] == "public_fixture_registry_projection", public_payload
        assert public_payload["github_push_allowed"] is True, public_payload
        assert public_payload["git"]["tracked"] is True, public_payload

        cli_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "goal_harness.cli",
                "--format",
                "json",
                "registry-boundary",
                "--path",
                str(local_registry),
                "--require-gitignored",
            ],
            cwd=REPO_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        cli_payload = json.loads(cli_result.stdout)
        assert cli_payload["ok"] is True, cli_payload
        assert cli_payload["path_label"] == "registry.json", cli_payload
        rendered = json.dumps(cli_payload, sort_keys=True)
        assert str(root) not in rendered, rendered


if __name__ == "__main__":
    run()
    print("registry-boundary-contract-smoke ok")
