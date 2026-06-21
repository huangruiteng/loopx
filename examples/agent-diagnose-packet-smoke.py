#!/usr/bin/env python3
"""Smoke-test LoopX agent-facing diagnosis packets."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_ID = "diagnose-smoke-goal"


def run_cli(*args: str, cwd: Path = REPO_ROOT) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def run_markdown(*args: str, cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "markdown", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def write_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir()
    (project / "README.md").write_text("# Diagnose fixture\n", encoding="utf-8")
    return project


def bootstrap_project(project: Path, runtime: Path, goal_id: str, *, onboarding: bool) -> dict:
    args = [
        "--runtime-root",
        str(runtime),
        "bootstrap",
        "--project",
        str(project),
        "--goal-id",
        goal_id,
        "--objective",
        "Exercise LoopX diagnosis packets.",
        "--goal-doc",
        "README.md",
        "--no-global-sync",
    ]
    if not onboarding:
        args.append("--no-onboarding-scan")
    return run_cli(*args)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-agent-diagnose-smoke-") as tmp:
        root = Path(tmp)
        runtime = root / "runtime"

        ready_project = write_project(root, "ready-project")
        bootstrap_project(ready_project, runtime, GOAL_ID, onboarding=False)
        registry = ready_project / ".loopx" / "registry.json"
        added = run_cli(
            "--registry",
            str(registry),
            "todo",
            "add",
            "--goal-id",
            GOAL_ID,
            "--role",
            "agent",
            "--text",
            "[P1] Inspect the fixture and write a compact diagnosis.",
            "--task-class",
            "advancement_task",
            "--action-kind",
            "analyze",
        )
        assert added["added"] is True, added

        packet = run_cli("--registry", str(registry), "diagnose", "--goal-id", GOAL_ID)
        assert packet["ok"] is True, packet
        assert packet["schema_version"] == "loopx_agent_diagnosis_packet_v0", packet
        assert packet["packet_kind"] == "agent_reasoning_evidence_packet", packet
        assert packet["agent_must_reason"] is True, packet
        selected = packet["selected"]
        assert selected["machine_signals_are_not_final_verdict"] is True, selected
        assert selected["machine_signal"] == "agent_work_attention", selected
        assert "can_self_drive" not in selected, selected
        assert selected["todo_evidence"]["agent_open_count"] == 1, selected
        assert selected["quota_signals"]["should_run"] is True, selected
        assert selected["agent_reasoning_checklist"], selected

        markdown = run_markdown("--registry", str(registry), "diagnose", "--goal-id", GOAL_ID)
        assert "LoopX is not making the final diagnosis" in markdown, markdown
        assert "Agent Reasoning Checklist" in markdown, markdown
        assert "These are for the agent to run" in markdown, markdown

        gated_project = write_project(root, "gated-project")
        gated_goal_id = "diagnose-smoke-gated"
        bootstrap_project(gated_project, runtime, gated_goal_id, onboarding=True)
        gated_registry = gated_project / ".loopx" / "registry.json"
        gated_packet = run_cli("--registry", str(gated_registry), "diagnose", "--goal-id", gated_goal_id)
        gated_selected = gated_packet["selected"]
        assert gated_selected["machine_signal"] == "user_or_controller_attention", gated_selected
        assert gated_selected["todo_evidence"]["user_open_count"] == 1, gated_selected
        assert "autonomous=yes/no" in str(gated_selected["user_question"]), gated_selected
        assert "can_self_drive" not in gated_selected, gated_selected

    print("agent-diagnose-packet-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
