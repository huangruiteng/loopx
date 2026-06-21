#!/usr/bin/env python3
"""Regression for quota should-run executable-backlog projection.

The fixture exercises the real LoopX CLI over an isolated registry,
runtime root, and active state. It protects the control-plane path where a P0
external monitor remains open but has no material transition while a P1
advancement todo is executable. In that state, the hot-path recommendation must
point at the executable backlog item; the monitor remains context, not the
selected action.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "quota-executable-backlog-projection-fixture"
POLL_ACTION = (
    "Agent: continue compact-polling Terminal-Bench train-fasttext until a "
    "terminal compact result/trial reward appears."
)
EXECUTABLE_TODO = (
    "[P1] Behavior regression suite lane: maintain `regression/` as the home "
    "for LoopX CLI plus real Codex CLI interaction regressions."
)


def run_loopx(*args: str, registry: Path, runtime: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(registry),
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
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def write_fixture(
    root: Path,
    *,
    state_next_action: str = POLL_ACTION,
) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    registry_path = project / ".loopx" / "registry.json"

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: quota-recommended-action-fixture\n"
        "owner_mode: goal\n"
        'objective: "Exercise executable backlog projection over monitor context."\n'
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Quota Executable Backlog Projection Fixture\n\n"
        "## Next Action\n\n"
        f"- {state_next_action}\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P0] [P0 monitor] Observe no-upload Terminal-Bench train-fasttext "
        "using compact process/result markers only.\n"
        "  <!-- loopx:todo todo_id=todo_monitor status=open "
        "task_class=continuous_monitor action_kind=monitor "
        "updated_at=2026-01-01T00%3A00%3A00%2B00%3A00 -->\n"
        f"- [ ] {EXECUTABLE_TODO}\n"
        "  <!-- loopx:todo todo_id=todo_executable status=open "
        "task_class=advancement_task action_kind=regression "
        "updated_at=2026-01-01T00%3A00%3A00%2B00%3A00 -->\n",
        encoding="utf-8",
    )
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
                        "domain": "quota-executable-backlog-projection-fixture",
                        "status": "active-read-only",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "harness_self_improvement",
                            "status": "connected-read-only",
                        },
                        "authority_sources": [],
                        "waiting_on": "codex",
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                            "allowed_slots": 5,
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    runs_dir = runtime / "goals" / GOAL_ID / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    progress_record = {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "goal_id": GOAL_ID,
        "classification": "quota_recommended_action_fixture_v0",
        "recommended_action": POLL_ACTION,
        "health_check": "state_file 1/1; registry_goal 1/1",
        "delivery_batch_scale": "implementation",
        "delivery_outcome": "outcome_progress",
        "json_path": str(runs_dir / "2026-01-01T00-00-00+00-00.json"),
        "markdown_path": str(runs_dir / "2026-01-01T00-00-00+00-00.md"),
    }
    Path(progress_record["json_path"]).write_text(json.dumps(progress_record) + "\n", encoding="utf-8")
    Path(progress_record["markdown_path"]).write_text("# Fixture Monitor Context\n", encoding="utf-8")
    with (runs_dir / "index.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(progress_record) + "\n")
    return runtime, registry_path


def assert_executable_backlog_projection(guard: dict[str, Any]) -> None:
    assert guard["should_run"] is True, guard
    assert guard["decision"] == "run", guard
    assert guard["recommended_action"] == EXECUTABLE_TODO, guard
    assert guard["recommended_action"] != POLL_ACTION, guard
    warning = guard["state_action_projection_warning"]
    assert warning["kind"] == "state_action_projection_mismatch", warning
    assert warning["requires_state_writeback"] is True, warning
    assert warning["active_state_next_action"] == POLL_ACTION, warning
    assert warning["selected_recommended_action"] == EXECUTABLE_TODO, warning
    lane = guard["work_lane_contract"]
    assert lane["lane"] == "advancement_task", lane
    assert lane["reason_codes"] == ["open_agent_todo", "external_monitor_context"], lane
    assert guard["interaction_contract"]["agent_channel"]["primary_action"] == (
        "[P1] Behavior regression suite lane"
    ), guard
    packet = guard["protocol_action_packet"]["summary"]
    assert "lane=advancement_task" in packet, packet
    assert "agent_action=[P1] Behavior regression suite lane" in packet, packet
    first_open = guard["agent_todo_summary"]["first_open_items"]
    assert first_open[0]["task_class"] == "continuous_monitor", guard
    assert first_open[1]["task_class"] == "advancement_task", guard


def assert_refresh_state_prefers_open_agent_todo(
    *,
    registry: Path,
    runtime: Path,
) -> None:
    refresh = run_loopx(
        "refresh-state",
        "--goal-id",
        GOAL_ID,
        "--classification",
        "refresh_agent_todo_projection_fixture_v0",
        "--dry-run",
        registry=registry,
        runtime=runtime,
    )
    assert refresh["recommended_action"] == EXECUTABLE_TODO, refresh
    assert refresh["recommended_action"] != POLL_ACTION, refresh


def assert_latest_run_action_does_not_create_false_projection_gap() -> None:
    with tempfile.TemporaryDirectory(
        prefix="loopx-quota-executable-backlog-synced-"
    ) as tmp:
        runtime, registry = write_fixture(
            Path(tmp),
            state_next_action=EXECUTABLE_TODO,
        )
        guard = run_loopx(
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            registry=registry,
            runtime=runtime,
        )
        assert guard["should_run"] is True, guard
        assert guard["recommended_action"] == EXECUTABLE_TODO, guard
        assert guard["recommended_action"] != POLL_ACTION, guard
        assert "state_action_projection_warning" not in guard, guard


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-quota-executable-backlog-") as tmp:
        runtime, registry = write_fixture(Path(tmp))
        guard = run_loopx(
            "quota",
            "should-run",
            "--goal-id",
            GOAL_ID,
            registry=registry,
            runtime=runtime,
        )
        assert_executable_backlog_projection(guard)
        assert_refresh_state_prefers_open_agent_todo(
            registry=registry,
            runtime=runtime,
        )
    assert_latest_run_action_does_not_create_false_projection_gap()
    print("quota-executable-backlog-projection-regression ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
