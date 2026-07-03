#!/usr/bin/env python3
"""Smoke-test capped public-safe follow-up todo capture."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.status import parse_active_state_todos  # noqa: E402


GOAL_ID = "todo-capture-followups-goal"
FOLLOWUP_ONE = "[P1] Add a public fixture that exercises deferred candidate promotion."
FOLLOWUP_TWO = "[P1] Document the public operator command summary contract."
FOLLOWUP_THREE = "[P2] Compare stale open todos against recent validation gaps."


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Keep follow-up capture bounded.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Preserve the existing agent todo for duplicate detection.\n"
        "  <!-- loopx:todo todo_id=todo_existing status=open task_class=advancement_task -->\n",
        encoding="utf-8",
    )
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "todo-capture-followups-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "authority_sources": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, state_file


def run_cli(registry_path: Path, *args: str, check: bool = True) -> dict:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry_path),
            "--format",
            "json",
            *args,
        ],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-todo-capture-followups-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))
        original = state_file.read_text(encoding="utf-8")

        dry_run = run_cli(
            registry_path,
            "todo",
            "capture-followups",
            "--goal-id",
            GOAL_ID,
            "--follow-up",
            FOLLOWUP_ONE,
            "--follow-up",
            FOLLOWUP_TWO,
            "--follow-up",
            FOLLOWUP_THREE,
            "--evidence",
            "examples/control_plane/todo-capture-followups-smoke.py#main",
            "--action-kind",
            "implement",
            "--required-write-scope",
            "examples/**",
            "--dry-run",
        )
        assert dry_run["ok"] is True, dry_run
        assert dry_run["dry_run"] is True, dry_run
        assert dry_run["recorded_count"] == 2, dry_run
        assert dry_run["skipped_count"] == 1, dry_run
        assert dry_run["items"][2]["skipped_reason"] == "max_items_exceeded", dry_run
        assert state_file.read_text(encoding="utf-8") == original

        payload = run_cli(
            registry_path,
            "todo",
            "capture-followups",
            "--goal-id",
            GOAL_ID,
            "--follow-up",
            FOLLOWUP_ONE,
            "--follow-up",
            FOLLOWUP_ONE,
            "--follow-up",
            FOLLOWUP_TWO,
            "--follow-up",
            "Inspect /private/tmp/raw-output before writing a todo.",
            "--evidence",
            "examples/control_plane/todo-capture-followups-smoke.py#main",
            "--action-kind",
            "implement",
            "--required-write-scope",
            "examples/**",
        )
        assert payload["ok"] is True, payload
        assert payload["dry_run"] is False, payload
        assert payload["recorded_count"] == 2, payload
        assert payload["skipped_count"] == 2, payload
        assert payload["items"][1]["skipped_reason"] == "duplicate", payload
        assert payload["items"][3]["skipped_reason"] == "unsafe_boundary:local_absolute_path", payload

        fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
        agent_items = fields["agent_todos"]["items"]
        texts = [item["text"] for item in agent_items]
        assert FOLLOWUP_ONE in texts, texts
        assert FOLLOWUP_TWO in texts, texts
        assert FOLLOWUP_THREE not in texts, texts
        assert not any("claimed_by" in item for item in agent_items), agent_items
        first_followup = next(item for item in agent_items if item["text"] == FOLLOWUP_ONE)
        assert first_followup["task_class"] == "advancement_task", first_followup
        assert first_followup["action_kind"] == "implement", first_followup
        assert first_followup["required_write_scopes"] == ["examples/**"], first_followup
        assert first_followup["evidence"] == "examples/control_plane/todo-capture-followups-smoke.py#main", first_followup

        duplicate_again = run_cli(
            registry_path,
            "todo",
            "capture-followups",
            "--goal-id",
            GOAL_ID,
            "--follow-up",
            FOLLOWUP_ONE,
            "--evidence",
            "examples/control_plane/todo-capture-followups-smoke.py#main",
        )
        assert duplicate_again["recorded_count"] == 0, duplicate_again
        assert duplicate_again["items"][0]["skipped_reason"] == "duplicate", duplicate_again

        unsafe_evidence = run_cli(
            registry_path,
            "todo",
            "capture-followups",
            "--goal-id",
            GOAL_ID,
            "--follow-up",
            "[P2] This item is otherwise public-safe.",
            "--evidence",
            "/private/tmp/raw-evidence.txt",
            check=False,
        )
        assert unsafe_evidence["ok"] is False, unsafe_evidence
        assert "evidence is not public-safe" in unsafe_evidence["error"], unsafe_evidence

    print("todo-capture-followups-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
