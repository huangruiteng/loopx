#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_json(*args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)
    return payload


def test_missing_project_stops_before_mutation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "fresh-project"
        project.mkdir()
        payload = run_json(
            "bootstrap-command-pack",
            "--project",
            str(project),
            "--goal-id",
            "fresh-goal",
            "--agent-id",
            "codex-test-agent",
        )
        connection = payload["project_connection"]
        assert isinstance(connection, dict)
        assert payload["schema_version"] == "loopx_bootstrap_command_pack_v0"
        assert payload["slash_command"] == "/loopx"
        assert payload["read_only"] is True
        assert connection["connection_state"] == "not_connected"
        assert connection["mutation_confirmation_required"] is True
        assert not (project / ".loopx").exists()
        assert not (project / ".codex").exists()

        safety = payload["safety_contract"]
        assert isinstance(safety, dict)
        assert safety["writes_registry"] is False
        assert safety["writes_state_file"] is False
        assert safety["spends_quota"] is False

        next_step = payload["recommended_next_step"]
        assert isinstance(next_step, dict)
        assert next_step["requires_user_confirmation"] is True
        assert "--dry-run" in str(next_step["dry_run_command"])
        assert "--codex-app-heartbeat ask" in str(next_step["dry_run_command"])
        assert "--dry-run" not in str(next_step["after_confirmation_command"])
        assert "/loopx-summary-all" not in json.dumps(payload)


def test_connected_project_reuses_existing_state() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "connected-project"
        state_file = project / ".codex" / "goals" / "connected-goal" / "ACTIVE_GOAL_STATE.md"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("# Active Goal State\n", encoding="utf-8")
        registry = project / ".loopx" / "registry.json"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "goals": [
                        {
                            "id": "connected-goal",
                            "status": "active",
                            "repo": str(project),
                            "state_file": ".codex/goals/connected-goal/ACTIVE_GOAL_STATE.md",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        payload = run_json(
            "bootstrap-command-pack",
            "--project",
            str(project),
            "--goal-id",
            "connected-goal",
        )
        connection = payload["project_connection"]
        assert isinstance(connection, dict)
        assert connection["connection_state"] == "connected"
        assert connection["mutation_confirmation_required"] is False

        next_step = payload["recommended_next_step"]
        assert isinstance(next_step, dict)
        assert next_step["kind"] == "status_and_loop_activation"
        assert next_step["requires_user_confirmation"] is False
        assert "dry_run_command" not in next_step
        assert "loopx status" in str(payload["commands"])


def main() -> int:
    test_missing_project_stops_before_mutation()
    test_connected_project_reuses_existing_state()
    print("bootstrap command pack smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
