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
        assert {"form": "/loopx <goal text>", "mode": "goal_plan_write_and_activate"} in payload["slash_forms"]
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


def test_goal_text_invocation_plans_ranked_todos_before_activation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp) / "goal-start-project"
        project.mkdir()
        payload = run_json(
            "bootstrap-command-pack",
            "--project",
            str(project),
            "--goal-id",
            "goal-start",
            "--agent-id",
            "codex-test-agent",
            "--goal-text",
            "Ship the lightweight issue triage workflow",
        )

        assert payload["goal_text"] == "Ship the lightweight issue triage workflow"
        next_step = payload["recommended_next_step"]
        assert isinstance(next_step, dict)
        assert next_step["kind"] == "goal_plan_write_and_activate"
        assert next_step["requires_user_confirmation"] is False
        assert next_step["confirmation_source"] == "/loopx <goal text>"
        assert "--objective 'Ship the lightweight issue triage workflow'" in str(
            next_step["connect_command_if_needed"]
        )
        assert "--no-onboarding-scan" in str(next_step["connect_command_if_needed"])

        goal_start = payload["goal_start_contract"]
        assert isinstance(goal_start, dict)
        assert goal_start["schema_version"] == "loopx_goal_start_command_v0"
        assert goal_start["planner"]["required_before_todo_write"] is True
        profiles = goal_start["planner"]["profiles"]
        assert profiles["open_ended_product_direction"]["suggested_items_min"] == 2
        assert profiles["open_ended_product_direction"]["suggested_items_max"] == 5
        assert profiles["clear_bounded_problem"]["item_count_policy"] == "planner_sized"
        assert profiles["clear_bounded_problem"][
            "may_reuse_current_todo_when_it_already_represents_the_plan"
        ] is True
        assert "minimum sufficient ordered todo plan" in goal_start["planner"]["budget_policy"]
        ordering = goal_start["priority_ordering"]
        assert ordering["bucket_order"] == ["P0", "P1", "P2"]
        assert ordering["same_priority_tie_breaker"] == "planner_order_then_todo_write_order"
        assert "todo index" in ordering["storage_contract"]

        commands = payload["commands"]
        assert isinstance(commands, dict)
        plan_prompt = str(commands["goal_start_plan_prompt"])
        assert "broad or fuzzy product direction uses 2-5" in plan_prompt
        assert "clear bounded problems use a planner-sized ordered todo plan" in plan_prompt
        assert "avoid management-only filler" in plan_prompt
        assert "Every new todo starts with `[P0]`, `[P1]`, or `[P2]`" in plan_prompt
        assert "Preserve that exact order" in plan_prompt
        assert "--agent-id codex-test-agent" in str(commands["goal_start_quota_should_run"])
        assert "Same-priority items use that write order as the tie-breaker" in str(payload["message"])
        assert not (project / ".loopx").exists()
        assert not (project / ".codex").exists()


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


def test_skill_slash_fallback_contract() -> None:
    skill_text = (REPO_ROOT / "skills" / "loopx-project" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(skill_text.split())

    assert "## Slash Command Fallback" in skill_text
    assert "`/loopx`" in skill_text
    assert "`/loopx <goal text>`" in skill_text
    assert "loopx bootstrap-command-pack --project ." in skill_text
    assert '--goal-text "<GOAL_TEXT>"' in skill_text
    assert "read/status-first" in skill_text
    assert "explicit goal-start intent" in normalized
    assert "planner order plus `todo add` write order" in normalized
    assert "do not silently downgrade `/loopx <goal text>`" in normalized
    assert "`/loopx-global-summary`" in skill_text
    assert "Legacy `/loop-global-*` forms" in normalized
    assert "not project bootstrap commands" in normalized


def main() -> int:
    test_missing_project_stops_before_mutation()
    test_goal_text_invocation_plans_ranked_todos_before_activation()
    test_connected_project_reuses_existing_state()
    test_skill_slash_fallback_contract()
    print("bootstrap command pack smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
