#!/usr/bin/env python3
"""Smoke-test monitor-poll todo metadata writeback."""

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


GOAL_ID = "monitor-poll-writeback-fixture"
AGENT_ID = "codex-product-capability"
TODO_ID = "todo_monitorpoll000"
TARGET_KEY = "update-note-draft-pr"
OTHER_TARGET_KEY = "other-monitor-target"


def write_fixture(
    root: Path,
    *,
    selected_target_key: str | None = TARGET_KEY,
    include_other_monitor: bool = False,
) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    monitor_metadata = (
        f"target_key={selected_target_key} "
        if selected_target_key
        else ""
    )
    other_monitor = (
        "- [ ] [P1] Poll another monitor target.\n"
        "  <!-- loopx:todo "
        "todo_id=todo_monitorpoll111 "
        "status=open "
        "task_class=continuous_monitor "
        "action_kind=poll "
        f"claimed_by={AGENT_ID} "
        f"target_key={OTHER_TARGET_KEY} "
        "cadence=15m "
        "next_due_at=2026-01-01T00:00:00+00:00 "
        "result_hash=old "
        "consecutive_no_change=1 "
        "material_change=false "
        "-->\n"
        if include_other_monitor
        else ""
    )
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Objective\n\n"
        "Exercise due monitor poll writeback.\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] Poll the update-note draft PR for material changes.\n"
        "  <!-- loopx:todo "
        f"todo_id={TODO_ID} "
        "status=open "
        "task_class=continuous_monitor "
        "action_kind=poll "
        f"claimed_by={AGENT_ID} "
        f"{monitor_metadata}"
        "cadence=15m "
        "next_due_at=2026-01-01T00:00:00+00:00 "
        "result_hash=old "
        "consecutive_no_change=1 "
        "material_change=false "
        "-->\n"
        f"{other_monitor}",
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
                        "domain": "monitor-poll-writeback",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "coordination": {
                            "registered_agents": [AGENT_ID],
                            "primary_agent": AGENT_ID,
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, state_file


def run_cli(registry_path: Path, *args: str) -> dict:
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
        check=True,
        text=True,
        capture_output=True,
    )
    return json.loads(result.stdout)


def run_cli_expect_error(registry_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
    assert result.returncode != 0, result
    return result


def agent_todos(state_file: Path) -> list[dict]:
    fields = parse_active_state_todos(state_file.read_text(encoding="utf-8"))
    return fields["agent_todos"]["items"]


def find_todo(state_file: Path, todo_id: str) -> dict:
    for item in agent_todos(state_file):
        if item.get("todo_id") == todo_id:
            return item
    raise AssertionError(f"missing todo {todo_id}")


def run_index_records(registry_path: Path) -> list[dict]:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    runtime = Path(str(registry["common_runtime_root"]))
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    if not index_path.exists():
        return []
    return [
        json.loads(line)
        for line in index_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def assert_due_monitor_selected(registry_path: Path, *, due_count: int = 1) -> None:
    quota = run_cli(
        registry_path,
        "quota",
        "should-run",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
    )
    assert quota["should_run"] is True, quota
    contract = quota.get("work_lane_contract")
    assert isinstance(contract, dict), quota
    assert contract.get("obligation") == "attempt_due_monitor", quota
    assert contract.get("selected_todo_id") == TODO_ID, quota
    assert contract.get("monitor_due_count") == due_count, quota


def assert_unchanged_writeback() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-unchanged-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))
        assert_due_monitor_selected(registry_path)

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--todo-id",
            TODO_ID,
            "--result-hash",
            "old",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["appended"] is True, payload
        writeback = payload["todo_writeback"]
        assert writeback["todo_id"] == TODO_ID, payload
        assert writeback["consecutive_no_change"] == 2, payload
        item = find_todo(state_file, TODO_ID)
        assert item["result_hash"] == "old", item
        assert item["consecutive_no_change"] == "2", item
        assert item["last_checked_at"], item
        assert item["next_due_at"] != "2026-01-01T00:00:00+00:00", item
        assert item["material_change"] == "false", item
        assert payload["classification"] == "quota_monitor_poll", payload
        assert payload["delivery_outcome"] == "surface_only", payload
        assert "no quota spend" in payload["health_check"], payload
        records = run_index_records(registry_path)
        assert [record["classification"] for record in records] == ["quota_monitor_poll"], records


def assert_material_transition_followup() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-material-") as tmp:
        registry_path, state_file = write_fixture(Path(tmp))
        assert_due_monitor_selected(registry_path)

        payload = run_cli(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--target-key",
            TARGET_KEY,
            "--result-hash",
            "new",
            "--material-change",
            "--next-agent-todo",
            "Review the material monitor transition and prepare a public-safe packet.",
            "--execute",
        )
        assert payload["ok"] is True, payload
        assert payload["material_change"] is True, payload
        writeback = payload["todo_writeback"]
        assert writeback["consecutive_no_change"] == 0, payload
        assert writeback["next_todos"], payload
        monitor = find_todo(state_file, TODO_ID)
        assert monitor["result_hash"] == "new", monitor
        assert monitor["consecutive_no_change"] == "0", monitor
        assert monitor["material_change"] == "true", monitor
        successors = [
            item
            for item in agent_todos(state_file)
            if item.get("unblocks_todo_id") == TODO_ID
        ]
        assert successors, agent_todos(state_file)
        assert successors[0]["task_class"] == "advancement_task", successors[0]
        records = run_index_records(registry_path)
        assert [record["classification"] for record in records] == ["quota_monitor_poll"], records
        assert records[0]["delivery_outcome"] == "outcome_progress", records[0]


def assert_target_key_cannot_hijack_selected_due_monitor() -> None:
    with tempfile.TemporaryDirectory(prefix="loopx-monitor-poll-target-key-") as tmp:
        registry_path, state_file = write_fixture(
            Path(tmp),
            selected_target_key=None,
            include_other_monitor=True,
        )
        assert_due_monitor_selected(registry_path, due_count=2)

        result = run_cli_expect_error(
            registry_path,
            "quota",
            "monitor-poll",
            "--goal-id",
            GOAL_ID,
            "--agent-id",
            AGENT_ID,
            "--target-key",
            OTHER_TARGET_KEY,
            "--result-hash",
            "new",
            "--execute",
        )
        payload = json.loads(result.stdout)
        assert payload["ok"] is False, payload
        assert "monitor-poll requires" in payload["reason"], payload
        selected = find_todo(state_file, TODO_ID)
        other = find_todo(state_file, "todo_monitorpoll111")
        assert selected["result_hash"] == "old", selected
        assert other["result_hash"] == "old", other
        assert run_index_records(registry_path) == [], run_index_records(registry_path)


def main() -> int:
    assert_unchanged_writeback()
    assert_material_transition_followup()
    assert_target_key_cannot_hijack_selected_due_monitor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
