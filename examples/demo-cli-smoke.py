#!/usr/bin/env python3
"""Smoke-test the one-command local demo path."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "demo-smoke-goal"


def run_cli(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-demo-cli-smoke-") as tmp:
        project = Path(tmp) / "demo-project"
        runtime = Path(tmp) / "runtime"
        resolved_project = project.resolve()
        payload = run_cli(
            "--runtime-root",
            str(runtime),
            "demo",
            "--project",
            str(project),
            "--goal-id",
            GOAL_ID,
        )
        assert payload["ok"] is True, payload
        assert payload["goal_id"] == GOAL_ID, payload
        assert payload["registry"] == str(resolved_project / ".loopx" / "registry.json"), payload
        assert payload["goal_doc_action"] == "created", payload
        assert payload["bootstrap"]["state_action"] == "created", payload
        assert payload["todos"]["user_added"] is True, payload
        assert payload["todos"]["agent_added"] is True, payload
        assert payload["refresh"]["appended"] is True, payload
        assert payload["status"]["ok"] is True, payload
        assert payload["status"]["demo_waiting_on"] == "codex", payload
        assert payload["status"]["demo_user_todos"]["open_count"] == 1, payload
        assert payload["status"]["demo_agent_todos"]["open_count"] == 1, payload
        assert payload["quota"]["should_run"] is True, payload
        assert payload["quota"]["quota"]["spent_slots"] == 0, payload
        dashboard_status_commands = "\n".join(payload["dashboard_status_commands"])
        dashboard_app_commands = "\n".join(payload["dashboard_app_commands"])
        assert f"cd {resolved_project}" in dashboard_status_commands, payload
        assert 'loopx --registry "$registry" serve-status --scan-root "$PWD" --port 8765' in dashboard_status_commands, payload
        assert payload["dashboard_status_scope"] == "project-local-demo", payload
        assert "npm run dev" in dashboard_app_commands, payload
        assert payload["dashboard_status_url"] == "http://127.0.0.1:8765/status.json", payload
        canonical_commands = "\n".join(payload["canonical_dashboard_status_commands"])
        assert "serve-status --global-registry --port 8766 --limit 80" in canonical_commands, payload
        assert payload["canonical_dashboard_status_url"] == "http://127.0.0.1:8766/status.json", payload

        registry = json.loads((project / ".loopx" / "registry.json").read_text(encoding="utf-8"))
        assert len(registry["goals"]) == 1, registry
        assert not (runtime / "registry.global.json").exists(), "demo should not sync into global registry"
        assert (runtime / "goals" / GOAL_ID / "runs" / "index.jsonl").exists(), payload

    print("demo-cli-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
