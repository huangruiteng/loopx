#!/usr/bin/env python3
"""Smoke-test completed Agent Todo archive CLI."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-archive-completed-goal"


def state_text() -> str:
    done_lines = []
    for index in range(1, 15):
        done_lines.append(f"- [x] [P1] Completed implementation lane {index}.\n")
        if index == 1:
            done_lines.append("  Continuation detail must move with the archived item.\n")
    return (
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Todo Archive Fixture\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Keep current open benchmark validation work visible.\n"
        + "".join(done_lines)
        + "- [ ] [P2] Keep monitor work after completed items visible.\n\n"
        "## Completed Work Archive\n\n"
        "- [x] [P1] Previously archived completed work.\n"
    )


def write_fixture(root: Path) -> tuple[Path, Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = ".codex/goals/todo-archive-completed-goal/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(state_text(), encoding="utf-8")
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "todo-archive-completed-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, runtime, state_path


def run_cli(registry_path: Path, runtime: Path, *args: str, check: bool = True) -> dict:
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
        check=check,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-archive-completed-") as tmp:
        registry_path, runtime, state_path = write_fixture(Path(tmp))
        original = state_path.read_text(encoding="utf-8")
        parsed = parse_active_state_todos(original)
        assert parsed["agent_todos"]["done_count"] == 14, parsed
        assert parsed["agent_todos"]["open_count"] == 2, parsed

        dry_run = run_cli(
            registry_path,
            runtime,
            "todo",
            "archive-completed",
            "--goal-id",
            GOAL_ID,
            "--max-active-done",
            "12",
        )
        assert dry_run["ok"] is True, dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["changed"] is True, dry_run
        assert dry_run["moved_count"] == 2, dry_run
        assert state_path.read_text(encoding="utf-8") == original

        execute = run_cli(
            registry_path,
            runtime,
            "todo",
            "archive-completed",
            "--goal-id",
            GOAL_ID,
            "--max-active-done",
            "12",
            "--execute",
        )
        assert execute["ok"] is True, execute
        assert execute["dry_run"] is False, execute
        assert execute["changed"] is True, execute
        assert execute["active_done_before"] == 14, execute
        assert execute["active_done_after"] == 12, execute
        assert execute["moved_count"] == 2, execute

        updated = state_path.read_text(encoding="utf-8")
        parsed_after = parse_active_state_todos(updated)
        assert parsed_after["agent_todos"]["done_count"] == 12, parsed_after
        assert parsed_after["agent_todos"]["open_count"] == 2, parsed_after
        assert updated.index("## Completed Work Archive") < updated.index("[P1] Completed implementation lane 1.")
        assert "Continuation detail must move with the archived item." in updated
        assert updated.count("[P1] Completed implementation lane 1.") == 1
        assert updated.count("[P1] Completed implementation lane 2.") == 1
        assert "updated_at: 2026-01-01T00:00:00+00:00" not in updated

    print("todo-archive-completed-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
