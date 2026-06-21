#!/usr/bin/env python3
"""Smoke-test first-connect onboarding scan and todo candidate projection."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.onboarding import ONBOARDING_SCAN_SCHEMA_VERSION  # noqa: E402
from loopx.status import parse_active_state_todos  # noqa: E402


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def run_cli(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def make_project(root: Path, name: str) -> Path:
    project = root / name
    project.mkdir()
    (project / "README.md").write_text("# Fixture Project\n\nInitial goal.\n", encoding="utf-8")
    (project / "pyproject.toml").write_text(
        "[project]\nname = \"fixture-project\"\nversion = \"0.1.0\"\n",
        encoding="utf-8",
    )
    run("git", "init", cwd=project)
    run("git", "add", "README.md", "pyproject.toml", cwd=project)
    run(
        "git",
        "-c",
        "user.email=loopx-smoke@example.com",
        "-c",
        "user.name=LoopX Smoke",
        "commit",
        "-m",
        "Initial fixture project",
        cwd=project,
    )
    with (project / "README.md").open("a", encoding="utf-8") as f:
        f.write("\nPending local change.\n")
    return project


def state_text(project: Path, goal_id: str) -> str:
    return (project / ".codex" / "goals" / goal_id / "ACTIVE_GOAL_STATE.md").read_text(encoding="utf-8")


def action_kinds(items: list[dict]) -> set[str]:
    return {str(item.get("action_kind") or "") for item in items}


def assert_default_onboarding(project: Path, runtime: Path) -> None:
    goal_id = "onboarding-smoke-default"
    payload = run_cli(
        "--runtime-root",
        str(runtime),
        "bootstrap",
        "--project",
        str(project),
        "--goal-id",
        goal_id,
        "--objective",
        "Exercise onboarding candidate projection.",
        "--goal-doc",
        "README.md",
        "--no-global-sync",
    )
    assert payload["ok"] is True, payload
    scan = payload["onboarding_scan"]
    assert scan["schema_version"] == ONBOARDING_SCAN_SCHEMA_VERSION, scan
    assert scan["is_git_repo"] is True, scan
    assert scan["status_path_count"] >= 1, scan
    assert scan["recent_commits"], scan
    assert "README.md" in scan["signal_files"], scan
    assert any(item["path"] == "pyproject.toml" for item in scan["validation_signal_files"]), scan
    assert scan["scan_policy"]["raw_file_bodies_read"] is False, scan
    candidates = payload["onboarding_agent_todo_candidates"]
    candidate_kinds = {candidate["action_kind"] for candidate in candidates}
    assert "repo_status_review" in candidate_kinds, candidates
    assert "commit_summary" in candidate_kinds, candidates
    assert "validation_plan" in candidate_kinds, candidates
    assert payload["onboarding_acceptance_required"] is True, payload
    assert payload["autonomous_advance_choice_required"] is True, payload
    assert payload["onboarding_todos_written"] is True, payload
    assert len(payload["accept_candidate_commands"]) == len(candidates), payload

    registry_path = project / ".loopx" / "registry.json"
    status_payload = run_cli("--registry", str(registry_path), "status")
    status_item = status_payload["attention_queue"]["items"][0]
    assert "Present the onboarding scan" in status_item["recommended_action"], status_item
    assert "Present the onboarding scan" in status_item["project_asset"]["next_action"], status_item
    assert status_item["user_todos"]["open_count"] == 1, status_item
    assert status_item["agent_todos"]["open_count"] == 1, status_item

    quota_payload = run_cli("--registry", str(registry_path), "quota", "should-run", "--goal-id", goal_id)
    assert quota_payload["should_run"] is True, quota_payload
    assert quota_payload["requires_user_action"] is True, quota_payload
    assert "Present the onboarding scan" in quota_payload["recommended_action"], quota_payload
    assert quota_payload["user_todo_summary"]["open_count"] == 1, quota_payload
    assert quota_payload["agent_todo_summary"]["open_count"] == 1, quota_payload

    text = state_text(project, goal_id)
    assert "## Onboarding Control" in text, text
    assert "## Proposed Onboarding Candidates" in text, text
    assert "Candidate agent todos: `requires user selection before delivery work`" in text, text
    assert "Autonomous advancement: `requires an explicit user yes/no choice`" in text, text
    assert "## User Todo / Owner Review Reading Queue" in text, text
    assert "## Agent Todo" in text, text
    assert "accepted numbers plus autonomous=yes/no" in text, text

    todos = parse_active_state_todos(text)
    user_items = todos.get("user_todos", {}).get("items", [])
    agent_items = todos["agent_todos"]["items"]
    assert len(user_items) == 1, user_items
    assert len(agent_items) == 1, agent_items
    assert action_kinds(user_items) == {"onboarding_decision"}, user_items
    assert action_kinds(agent_items) == {"onboarding_todo_review"}, agent_items


def assert_preauthorized_onboarding(project: Path, runtime: Path) -> None:
    goal_id = "onboarding-smoke-preauth"
    payload = run_cli(
        "--runtime-root",
        str(runtime),
        "bootstrap",
        "--project",
        str(project),
        "--goal-id",
        goal_id,
        "--objective",
        "Exercise preauthorized onboarding candidate projection.",
        "--goal-doc",
        "README.md",
        "--accept-onboarding-agent-todos",
        "--begin-autonomous-advance",
        "--no-global-sync",
    )
    assert payload["ok"] is True, payload
    assert payload["onboarding_acceptance_required"] is False, payload
    assert payload["autonomous_advance_choice_required"] is False, payload
    text = state_text(project, goal_id)
    assert "Candidate agent todos: `accepted and written into Agent Todo`" in text, text
    assert "Autonomous advancement: `allowed after accepted agent todos and a fresh quota guard`" in text, text
    assert "Choose which proposed onboarding agent todos" not in text, text

    todos = parse_active_state_todos(text)
    user_items = todos.get("user_todos", {}).get("items", [])
    agent_items = todos["agent_todos"]["items"]
    assert user_items == [], user_items
    assert len(agent_items) == len(payload["onboarding_agent_todo_candidates"]), agent_items
    kinds = action_kinds(agent_items)
    assert "repo_status_review" in kinds, agent_items
    assert "commit_summary" in kinds, agent_items
    assert "validation_plan" in kinds, agent_items


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-onboarding-smoke-") as tmp:
        root = Path(tmp)
        runtime = root / "runtime"
        project = make_project(root, "fixture-project")
        assert_default_onboarding(project, runtime)
        assert_preauthorized_onboarding(project, runtime)

    print("onboarding-connect-candidates-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
