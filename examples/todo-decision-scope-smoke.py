#!/usr/bin/env python3
"""Smoke-test structured decision scopes on LoopX todos."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "decision-scope-smoke"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import parse_active_state_todos  # noqa: E402


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Decision Scope Smoke\n\n"
        "## User Todo / Owner Review Reading Queue\n\n"
        "- [ ] Approve writing generated docs.\n"
        "  <!-- loopx:todo todo_id=todo_user_gate status=open task_class=user_gate "
        "decision_scope=%7B%22granularity%22:%22project%22,%22kind%22:%22write_scope%22,"
        "%22reason_summary%22:%22owner%20approves%20docs%20write%22,%22scope_key%22:%22docs/**%22%7D -->\n\n"
        "## Agent Todo\n\n"
        "- [ ] Write the docs after the owner gate clears.\n"
        "  <!-- loopx:todo todo_id=todo_agent_write status=open task_class=advancement_task "
        "required_decision_scopes=%5B%7B%22granularity%22:%22project%22,%22kind%22:%22write_scope%22,"
        "%22scope_key%22:%22docs/**%22%7D%5D safety_class=local_write -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {"kind": "harness_self_improvement"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_path, runtime


def run_cli(registry_path: Path, runtime: Path, *args: str) -> dict:
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
            *args,
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-decision-scope-") as tmp:
        registry_path, runtime = write_fixture(Path(tmp))
        parsed = parse_active_state_todos((Path(tmp) / "project" / f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md").read_text())
        user_item = parsed["user_todos"]["first_open_items"][0]
        agent_item = parsed["agent_todos"]["first_open_items"][0]
        assert user_item["decision_scope"]["kind"] == "write_scope", user_item
        assert user_item["decision_scope"]["scope_key"] == "docs/**", user_item
        assert agent_item["required_decision_scopes"][0]["scope_key"] == "docs/**", agent_item
        assert agent_item["safety_class"] == "local_write", agent_item

        user_payload = run_cli(
            registry_path,
            runtime,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "user",
            "--text",
            "Approve external run.",
            "--task-class",
            "user_gate",
            "--decision-scope-kind",
            "resource",
            "--decision-scope-granularity",
            "action",
            "--decision-scope-key",
            "benchmark:smoke",
            "--dry-run",
        )
        assert user_payload["decision_scope"]["kind"] == "resource", user_payload
        assert user_payload["decision_scope"]["scope_key"] == "benchmark:smoke", user_payload

        agent_payload = run_cli(
            registry_path,
            runtime,
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "Run benchmark after approval.",
            "--required-decision-scope",
            "resource:action:benchmark:smoke",
            "--safety-class",
            "external_run",
            "--dry-run",
        )
        assert agent_payload["required_decision_scopes"][0]["scope_key"] == "benchmark:smoke", agent_payload
        assert agent_payload["safety_class"] == "external_run", agent_payload

    print("todo decision scope smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
