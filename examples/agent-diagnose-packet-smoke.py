#!/usr/bin/env python3
"""Smoke-test LoopX agent-facing diagnosis packets."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from loopx.diagnose import _first_agent_todo_text, render_diagnosis_markdown  # noqa: E402

GOAL_ID = "diagnose-smoke-goal"
SCOPED_GOAL_ID = "diagnose-smoke-agent-scoped"


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


def assert_selected_agent_todo_preferred() -> None:
    selected = "[P0] Run the selected lane-local kernel slice."
    blocked = "[P0] Old blocked item that should not headline diagnose."
    executable = "[P1] Fallback executable item."
    assert (
        _first_agent_todo_text(
            {"agent_lane_next_action": {"text": selected}},
            {
                "backlog_items": [{"status": "blocked", "text": blocked}],
                "first_executable_items": [{"status": "open", "text": executable}],
            },
        )
        == selected
    )


def assert_diagnose_markdown_separates_status_and_packet_goal_counts() -> None:
    markdown = render_diagnosis_markdown(
        {
            "ok": True,
            "packet_kind": "agent_reasoning_evidence_packet",
            "agent_must_reason": True,
            "registry": "fixture-registry.json",
            "runtime_root": "fixture-runtime",
            "selected_goal_id": "selected-goal",
            "goal_count": 24,
            "goal_packet_count": 1,
            "run_count": 42,
            "selected": {
                "todo_evidence": {},
                "quota_signals": {
                    "scheduler_hint": {
                        "action": "run_now",
                        "cadence_class": "active_work",
                        "codex_app": {
                            "apply": "update_rrule",
                            "apply_needed": True,
                            "recommended_rrule": "FREQ=MINUTELY;INTERVAL=3",
                            "current_rrule": "FREQ=MINUTELY;INTERVAL=10",
                            "no_spend_for_cadence_change": True,
                        },
                        "unchanged_poll": {
                            "final_quota_replan_check_enabled": True,
                        },
                    }
                },
            },
            "status_summary": {
                "contract_warnings": [
                    "fixture-goal: duplicate index rows raw=2 unique=1 unexpected=1",
                    "fixture-goal: stale projection warning A",
                    "fixture-goal: stale projection warning B",
                ],
                "contract_warnings_total_count": 4,
                "contract_warnings_truncated": True,
                "contract_errors": [],
                "contract_errors_total_count": 0,
                "contract_errors_truncated": False,
            },
            "goals": [{"goal_id": "selected-goal", "todo_evidence": {}}],
        }
    )
    assert "- status_goals: `24`" in markdown, markdown
    assert "- goal_packets: `1`" in markdown, markdown
    assert "- goals: `24`" not in markdown, markdown
    assert "- scheduler_hint: action=run_now cadence=active_work" in markdown, markdown
    assert "apply_needed=True" in markdown, markdown
    assert "final_replan_check=True" in markdown, markdown
    assert "Status Contract Signals" in markdown, markdown
    assert "duplicate index rows raw=2 unique=1 unexpected=1" in markdown, markdown
    assert "contract_warnings_truncated: total=4" in markdown, markdown


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


def write_agent_scoped_registry(root: Path, runtime: Path) -> Path:
    project = write_project(root, "agent-scoped-project")
    state_file = f".codex/goals/{SCOPED_GOAL_ID}/ACTIVE_GOAL_STATE.md"
    state_path = project / state_file
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "# Agent-Scoped Diagnose Fixture\n\n"
        "## User Todo\n\n"
        "- [ ] [P0 user gate] Review the scoped projection repair PR before merge.\n"
        "  <!-- loopx:todo todo_id=todo_user_gate_scoped status=open "
        "task_class=user_gate action_kind=review_pr priority=P0 "
        "blocks_agent=codex-main-control -->\n\n"
        "## Agent Todo\n\n"
        "- [ ] [P1] Continue only safe fallback work after the scoped gate is projected.\n"
        "  <!-- loopx:todo todo_id=todo_agent_fallback status=open "
        "task_class=advancement_task action_kind=diagnose_projection "
        "claimed_by=codex-main-control priority=P1 -->\n",
        encoding="utf-8",
    )
    registry = project / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": SCOPED_GOAL_ID,
                        "domain": "agent-diagnose-fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": state_file,
                        "adapter": {
                            "kind": "fixture_connected_delivery_v0",
                            "status": "connected-delivery",
                        },
                        "quota": {
                            "compute": 1.0,
                            "window_hours": 24,
                        },
                        "coordination": {
                            "primary_agent": "codex-main-control",
                            "registered_agents": ["codex-main-control", "codex-side-observer"],
                            "agent_profiles": {
                                "codex-main-control": {
                                    "role": "primary-agent",
                                    "scope": "review, merge, final closeout",
                                },
                                "codex-side-observer": {
                                    "role": "side-agent",
                                    "scope": "read-only observation",
                                },
                            },
                            "write_scope": ["docs/**"],
                        },
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


def main() -> int:
    assert_selected_agent_todo_preferred()
    assert_diagnose_markdown_separates_status_and_packet_goal_counts()
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
        assert selected["quota_signals"]["goal_frontier_projection"]["replan_required"] is False, (
            selected
        )
        scheduler_hint = selected["quota_signals"]["scheduler_hint"]
        assert scheduler_hint["schema_version"] == "diagnose_scheduler_hint_summary_v0", selected
        assert "local_scheduler" not in str(scheduler_hint), scheduler_hint
        assert scheduler_hint["codex_app"]["no_spend_for_cadence_change"] is True, scheduler_hint
        assert selected["agent_reasoning_checklist"], selected
        assert any(
            " diagnose " in command and f"--goal-id {GOAL_ID}" in command
            for command in selected["agent_commands"]
        ), selected
        assert any(
            " status " in command and f"--goal-id {GOAL_ID}" in command
            for command in selected["agent_commands"]
        ), selected

        markdown = run_markdown("--registry", str(registry), "diagnose", "--goal-id", GOAL_ID)
        assert "LoopX is not making the final diagnosis" in markdown, markdown
        assert "Agent Reasoning Checklist" in markdown, markdown
        assert "These are for the agent to run" in markdown, markdown
        assert "goal_frontier_projection: replan_required=False" in markdown, markdown
        assert "current_agent_advancement=0" in markdown, markdown
        assert "unclaimed_advancement=1" in markdown, markdown
        assert "scheduler_hint: action=" in markdown, markdown
        assert "no_spend_for_cadence_change=True" in markdown, markdown

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

        scoped_registry = write_agent_scoped_registry(root, runtime)
        scoped_packet = run_cli(
            "--registry",
            str(scoped_registry),
            "--runtime-root",
            str(runtime),
            "diagnose",
            "--goal-id",
            SCOPED_GOAL_ID,
            "--agent-id",
            "codex-main-control",
        )
        scoped_selected = scoped_packet["selected"]
        assert scoped_packet["agent_id"] == "codex-main-control", scoped_packet
        assert scoped_selected["agent_id"] == "codex-main-control", scoped_selected
        assert scoped_selected["machine_signal"] == "user_or_controller_attention", scoped_selected
        assert scoped_selected["todo_evidence"]["user_open_count"] == 1, scoped_selected
        assert "Review the scoped projection repair PR" in str(scoped_selected), scoped_selected
        assert "Regenerate the installed heartbeat automation prompt" not in str(scoped_selected), (
            scoped_selected
        )
        assert (
            scoped_selected["quota_signals"]["agent_identity"]["agent_id"]
            == "codex-main-control"
        ), scoped_selected
        assert any("--agent-id codex-main-control" in command for command in scoped_selected["agent_commands"]), (
            scoped_selected
        )
        assert any(
            f"--goal-id {SCOPED_GOAL_ID}" in command for command in scoped_selected["agent_commands"]
        ), scoped_selected

    print("agent-diagnose-packet-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
