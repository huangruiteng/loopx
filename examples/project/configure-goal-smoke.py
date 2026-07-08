#!/usr/bin/env python3
"""Smoke-test the safe per-goal registry configuration command."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GOAL_ID = "configure-goal-fixture"


def write_registry(root: Path) -> Path:
    state_file = root / "project" / ".codex/goals/configure-goal-fixture/STATE.md"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        "# Active Goal State\n\n## Agent Todo\n\n- [ ] Keep this todo during scope migration.\n",
        encoding="utf-8",
    )
    registry_path = root / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(root / "runtime"),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "configure-goal-smoke",
                        "status": "active",
                        "repo": str(root / "project"),
                        "state_file": ".codex/goals/configure-goal-fixture/STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "quota": {"compute": 1, "window_hours": 24},
                        "spawn_policy": {"mode": "default", "allowed": False, "max_children": 0},
                        "control_plane": {
                            "self_repair": {
                                "enabled": False,
                                "allow_health_blocker_repair": False,
                                "allow_waiting_projection_repair": False,
                            }
                        },
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def run_cli(registry_path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
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
        check=check,
        text=True,
        capture_output=True,
    )


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def goal_from_registry(registry_path: Path) -> dict:
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    return registry["goals"][0]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-configure-goal-smoke-") as tmp:
        root = Path(tmp)
        registry_path = write_registry(root)
        original = registry_path.read_text(encoding="utf-8")

        dry = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
            "--self-repair-enabled",
            "--self-repair-health",
            "--self-repair-waiting-projection",
            "--orchestration-mode",
            "multi_subagent",
            "--spawn-allowed",
            "--max-children",
            "2",
            "--allowed-domain",
            "docs",
            "--allowed-domain",
            "validation",
            "--registered-agent",
            "codex-main-control",
            "--registered-agent",
            "codex-side-bypass,codex-main-control",
            "--primary-agent",
            "codex-main-control",
            "--write-scope",
            "docs/**",
            "--write-scope",
            "tests/**,docs/**",
            "--waiting-on",
            "user_or_controller",
            "--boundary-authority-scope",
            "docs/**",
            "--boundary-authority-source",
            "operator_gate_resume_contract_v0:fixture",
            "--boundary-authority-decision-id",
            "gate-fixture-1",
        ))
        assert dry["ok"] is True, dry
        assert dry["dry_run"] is True, dry
        assert dry["changed"] is True, dry
        assert "waiting_on" in dry["changed_fields"], dry
        assert "checkpointed_boundary_authority" in dry["changed_fields"], dry
        assert "registered_agents" in dry["changed_fields"], dry
        assert "primary_agent" in dry["changed_fields"], dry
        assert "write_scope" in dry["changed_fields"], dry
        assert dry["after"]["waiting_on"] == "user_or_controller", dry
        assert dry["after"]["write_scope"] == ["docs/**", "tests/**"], dry
        assert dry["after"]["checkpointed_boundary_authority"]["active_write_scope"] == ["docs/**"], dry
        assert dry["after"]["registered_agents"] == ["codex-main-control", "codex-side-bypass"], dry
        assert dry["after"]["primary_agent"] == "codex-main-control", dry
        migration = dry["heartbeat_prompt_migration"]
        assert migration["schema_version"] == "heartbeat_prompt_migration_v0", migration
        assert "coordination.registered_agents" in migration["reason"], migration
        migration_commands = migration["commands"]
        assert [item["agent_id"] for item in migration_commands] == [
            "codex-main-control",
            "codex-side-bypass",
        ], migration
        assert "heartbeat-prompt --thin" in migration_commands[0]["command"], migration
        assert "--agent-id codex-main-control" in migration_commands[0]["command"], migration
        assert "--agent-scope" in migration_commands[1]["command"], migration
        assert dry["written"] is False, dry
        assert registry_path.read_text(encoding="utf-8") == original

        applied = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
            "--self-repair-enabled",
            "--self-repair-health",
            "--self-repair-waiting-projection",
            "--orchestration-mode",
            "multi_subagent",
            "--spawn-allowed",
            "--max-children",
            "2",
            "--allowed-domain",
            "docs,validation",
            "--registered-agent",
            "codex-main-control,codex-side-bypass",
            "--primary-agent",
            "codex-main-control",
            "--write-scope",
            "docs/**,tests/**",
            "--waiting-on",
            "user_or_controller",
            "--boundary-authority-scope",
            "docs/**",
            "--boundary-authority-source",
            "operator_gate_resume_contract_v0:fixture",
            "--boundary-authority-decision-id",
            "gate-fixture-1",
            "--execute",
        ))
        assert applied["ok"] is True, applied
        assert applied["dry_run"] is False, applied
        assert applied["written"] is True, applied
        assert applied["heartbeat_prompt_migration"]["commands"][0]["agent_id"] == "codex-main-control", applied
        goal = goal_from_registry(registry_path)
        assert goal["quota"]["compute"] == 0.5, goal
        assert goal["control_plane"]["self_repair"]["enabled"] is True, goal
        assert goal["control_plane"]["self_repair"]["allow_health_blocker_repair"] is True, goal
        assert goal["control_plane"]["self_repair"]["allow_waiting_projection_repair"] is True, goal
        assert goal["spawn_policy"]["mode"] == "multi_subagent", goal
        assert goal["spawn_policy"]["allowed"] is True, goal
        assert goal["spawn_policy"]["max_children"] == 2, goal
        assert goal["spawn_policy"]["allowed_domains"] == ["docs", "validation"], goal
        assert goal["coordination"]["registered_agents"] == ["codex-main-control", "codex-side-bypass"], goal
        assert goal["coordination"]["primary_agent"] == "codex-main-control", goal
        assert goal["coordination"]["write_scope"] == ["docs/**", "tests/**"], goal
        assert goal["waiting_on"] == "user_or_controller", goal
        authority = goal["coordination"]["checkpointed_boundary_authority"][0]
        assert authority["schema_version"] == "checkpointed_boundary_authority_v0", authority
        assert authority["write_scope"] == ["docs/**"], authority
        assert authority["source"] == "operator_gate_resume_contract_v0:fixture", authority
        assert authority["decision_id"] == "gate-fixture-1", authority
        state_file = root / "project" / ".codex/goals/configure-goal-fixture/STATE.md"
        state_before_scope_migration = state_file.read_text(encoding="utf-8")

        scope_migrated = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--write-scope",
            "loopx/**,docs/**",
            "--execute",
        ))
        assert scope_migrated["ok"] is True, scope_migrated
        assert scope_migrated["changed"] is True, scope_migrated
        assert scope_migrated["written"] is True, scope_migrated
        assert "write_scope" in scope_migrated["changed_fields"], scope_migrated
        assert scope_migrated["before"]["write_scope"] == ["docs/**", "tests/**"], scope_migrated
        assert scope_migrated["after"]["write_scope"] == ["docs/**", "tests/**", "loopx/**"], scope_migrated
        assert scope_migrated["heartbeat_prompt_migration"] is None, scope_migrated
        assert goal_from_registry(registry_path)["coordination"]["write_scope"] == [
            "docs/**",
            "tests/**",
            "loopx/**",
        ]
        assert state_file.read_text(encoding="utf-8") == state_before_scope_migration

        no_change = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0.5",
        ))
        assert no_change["ok"] is True, no_change
        assert no_change["changed"] is False, no_change

        cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-waiting-on",
            "--execute",
        ))
        assert cleared["ok"] is True, cleared
        assert cleared["changed"] is True, cleared
        assert "waiting_on" in cleared["changed_fields"], cleared
        assert "waiting_on" not in goal_from_registry(registry_path), cleared

        authority_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-boundary-authority",
            "--execute",
        ))
        assert authority_cleared["ok"] is True, authority_cleared
        assert authority_cleared["changed"] is True, authority_cleared
        assert "checkpointed_boundary_authority" in authority_cleared["changed_fields"], authority_cleared
        assert "checkpointed_boundary_authority" not in goal_from_registry(registry_path)["coordination"], authority_cleared

        agents_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-registered-agents",
            "--execute",
        ))
        assert agents_cleared["ok"] is True, agents_cleared
        assert agents_cleared["changed"] is True, agents_cleared
        assert "registered_agents" in agents_cleared["changed_fields"], agents_cleared
        assert "primary_agent" in agents_cleared["changed_fields"], agents_cleared
        assert "registered_agents" not in goal_from_registry(registry_path)["coordination"], agents_cleared
        assert "primary_agent" not in goal_from_registry(registry_path)["coordination"], agents_cleared

        scope_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-write-scope",
            "--execute",
        ))
        assert scope_cleared["ok"] is True, scope_cleared
        assert scope_cleared["changed"] is True, scope_cleared
        assert "write_scope" in scope_cleared["changed_fields"], scope_cleared
        assert goal_from_registry(registry_path)["coordination"]["write_scope"] == [], scope_cleared

        invalid = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--quota-compute",
            "0",
            check=False,
        ))
        assert invalid["ok"] is False, invalid
        assert "greater than 0" in invalid["error"], invalid

        invalid_replace = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--replace-write-scope",
            check=False,
        ))
        assert invalid_replace["ok"] is False, invalid_replace
        assert "requires --write-scope" in invalid_replace["error"], invalid_replace

    print("configure-goal-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
