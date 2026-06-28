#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_json(*args: str, env: dict[str, str] | None = None) -> dict[str, object]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    result = subprocess.run(
        [sys.executable, "-m", "loopx.cli", "--format", "json", *args],
        cwd=REPO_ROOT,
        env=process_env,
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
        slash_catalog = payload["available_slash_commands"]
        assert isinstance(slash_catalog, dict)
        assert slash_catalog["schema_version"] == "loopx_slash_command_catalog_v0"
        command_names = {item["command"] for item in slash_catalog["commands"]}
        assert "/loopx" in command_names
        assert "/loopx <goal text>" in command_names
        assert "/loopx-global-summary" in command_names
        assert "/loopx-global-gates" in command_names
        onboarding = payload["onboarding_hint"]
        assert onboarding["tell_new_users"] is True
        assert "LoopX command surface is available. Useful commands:" in onboarding["suggested_user_note"]
        assert "loopx slash-commands" in onboarding["suggested_user_note"]
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
        assert "GitHub issue/PR fix" in plan_prompt
        assert "loopx issue-fix workflow-plan" in plan_prompt
        assert "external comments, PR creation, merge, publish" in plan_prompt
        assert "issue_fix_workflow_plan_template" in commands
        issue_fix_template = str(commands["issue_fix_workflow_plan_template"])
        assert "issue-fix workflow-plan" in issue_fix_template
        assert "--url <github-issue-or-pr-url>" in issue_fix_template
        assert "--repo-path <approved-repo>" in issue_fix_template
        assert "--validation-label '<validation command>'" in issue_fix_template
        assert "--agent-id codex-test-agent" in str(commands["goal_start_quota_should_run"])
        assert "Same-priority items use that write order as the tie-breaker" in str(payload["message"])
        assert "preview the issue-fix route before todo writeback" in str(payload["message"])
        domain_routes = goal_start["domain_route_hints"]
        assert domain_routes["issue_fix_workflow"]["when"].startswith("goal text contains")
        assert "workflow-plan" in domain_routes["issue_fix_workflow"]["preview_command"]
        assert "explicit gates" in domain_routes["issue_fix_workflow"]["writeback"]
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


def test_linked_git_worktree_reuses_canonical_source_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        primary = root / "primary"
        primary.mkdir()
        subprocess.run(["git", "init"], cwd=primary, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(
            ["git", "config", "user.email", "loopx@example.invalid"],
            cwd=primary,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            ["git", "config", "user.name", "LoopX Smoke"],
            cwd=primary,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (primary / "README.md").write_text("# primary\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=primary, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=primary,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        worktree = root / "linked-worktree"
        subprocess.run(
            ["git", "worktree", "add", "-b", "linked-smoke", str(worktree)],
            cwd=primary,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        canonical_goal = "canonical-goal"
        state_file = primary / ".codex" / "goals" / canonical_goal / "ACTIVE_GOAL_STATE.md"
        state_file.parent.mkdir(parents=True)
        state_file.write_text("# Active Goal State\n", encoding="utf-8")
        primary_registry = primary / ".loopx" / "registry.json"
        primary_registry.parent.mkdir(parents=True)
        primary_payload = {
            "schema_version": "0.1",
            "goals": [
                {
                    "id": canonical_goal,
                    "status": "active",
                    "repo": str(primary),
                    "state_file": ".codex/goals/canonical-goal/ACTIVE_GOAL_STATE.md",
                }
            ],
        }
        primary_registry.write_text(json.dumps(primary_payload, indent=2) + "\n", encoding="utf-8")

        shadow_goal = "linked-worktree-goal"
        shadow_state = worktree / ".codex" / "goals" / shadow_goal / "ACTIVE_GOAL_STATE.md"
        shadow_state.parent.mkdir(parents=True)
        shadow_state.write_text("# Shadow State\n", encoding="utf-8")
        shadow_registry = worktree / ".loopx" / "registry.json"
        shadow_registry.parent.mkdir(parents=True)
        shadow_registry.write_text(
            json.dumps(
                {
                    "schema_version": "0.1",
                    "goals": [
                        {
                            "id": shadow_goal,
                            "status": "active",
                            "repo": str(worktree),
                            "state_file": ".codex/goals/linked-worktree-goal/ACTIVE_GOAL_STATE.md",
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        runtime = root / "runtime"
        global_registry = runtime / "registry.global.json"
        global_registry.parent.mkdir(parents=True)
        global_payload = {
            "schema_version": "0.1",
            "registry_role": "global-local",
            "goals": [
                {
                    **primary_payload["goals"][0],
                    "source_registry": str(primary_registry),
                    "synced_at": "2026-06-28T00:00:00+00:00",
                },
                {
                    "id": shadow_goal,
                    "status": "active",
                    "repo": str(worktree),
                    "state_file": ".codex/goals/linked-worktree-goal/ACTIVE_GOAL_STATE.md",
                    "source_registry": str(shadow_registry),
                    "synced_at": "2026-06-28T00:00:00+00:00",
                },
            ],
        }
        global_registry.write_text(json.dumps(global_payload, indent=2) + "\n", encoding="utf-8")

        payload = run_json(
            "bootstrap-command-pack",
            "--project",
            str(worktree),
            env={"LOOPX_RUNTIME_ROOT": str(runtime)},
        )

        connection = payload["project_connection"]
        assert isinstance(connection, dict)
        alias = connection["canonical_project_alias"]
        assert isinstance(alias, dict)
        assert alias["applied"] is True, alias
        assert alias["kind"] == "git_worktree_canonical_source_registry", alias
        assert Path(str(connection["input_project"])).resolve() == worktree.resolve(), connection
        assert Path(str(payload["project"])).resolve() == primary.resolve(), payload
        assert payload["goal_id"] == canonical_goal, payload
        assert Path(str(connection["registry"])).resolve() == primary_registry.resolve(), connection
        assert Path(str(connection["state_file"])).resolve() == state_file.resolve(), connection
        assert connection["connection_state"] == "connected", connection
        assert payload["recommended_next_step"]["requires_user_confirmation"] is False, payload
        assert shadow_goal not in str(payload["message"])


def test_skill_slash_fallback_contract() -> None:
    skill_text = (REPO_ROOT / "skills" / "loopx-project" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    pr_review_skill_text = (REPO_ROOT / "skills" / "loopx-pr-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(skill_text.split())
    pr_review_normalized = " ".join(pr_review_skill_text.split())

    assert "## Slash Command Fallback" in skill_text
    assert "`/loopx`" in skill_text
    assert "`/loopx <goal text>`" in skill_text
    assert "loopx bootstrap-command-pack --project ." in skill_text
    assert "canonical_project_alias" in skill_text
    assert "worktree-local shadow goal" in skill_text
    assert '--goal-text "<GOAL_TEXT>"' in skill_text
    assert "read/status-first" in skill_text
    assert "explicit goal-start intent" in normalized
    assert "planner order plus `todo add` write order" in normalized
    assert "do not silently downgrade `/loopx <goal text>`" in normalized
    assert "`/loopx-global-summary`" in skill_text
    assert "Legacy `/loop-global-*` forms" in normalized
    assert "loopx slash-commands" in skill_text
    assert "not project bootstrap commands" in normalized
    assert "`/loopx-pr-review`" in skill_text
    assert "load the narrower `loopx-pr-review` skill" in normalized
    assert "Do not handle `/loopx-pr-review` from this broader project skill" in normalized
    assert "do not route it to `loopx-pr-merge` unless" in normalized
    assert "loopx --format json pr-review --state all" not in skill_text
    assert "loopx --format json pr-review --state all" in pr_review_skill_text
    assert "full JSON first" in pr_review_normalized
    assert "agent_response_contract" in pr_review_skill_text
    assert "pull_requests[].review_template" in pr_review_skill_text
    assert "pull_requests[].evidence_commands" in pr_review_skill_text
    assert "`.summary`, `.review_sequence`, or a table" in pr_review_skill_text
    assert "review_groups.unmerged" in pr_review_skill_text
    assert "review_groups.merged" in pr_review_skill_text
    assert "Do not fill the five-block review from title" in pr_review_normalized


def main() -> int:
    test_missing_project_stops_before_mutation()
    test_goal_text_invocation_plans_ranked_todos_before_activation()
    test_connected_project_reuses_existing_state()
    test_linked_git_worktree_reuses_canonical_source_registry()
    test_skill_slash_fallback_contract()
    print("bootstrap command pack smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
