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

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.quota.goal_boundary import goal_boundary  # noqa: E402


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
        agent_profile = {
            "schema_version": "agent_profile_v1",
            "agent_id": "codex-side-bypass",
            "profile_role": "runtime-validation",
            "scope_summary": "Focused runtime validation and peer claim repairs.",
            "default_task_classes": ["advancement_task"],
            "preferred_action_kinds": ["todo_claim_*", "task_lease_*"],
            "avoid_action_kinds": ["production_*"],
        }
        agent_profile_json = json.dumps(agent_profile)

        inspected = payload(run_cli(registry_path, "configure-goal", "--goal-id", GOAL_ID))
        assert inspected["changed"] is False, inspected
        assert inspected["configuration_catalog"]["disclosure_policy"][
            "first_run_configuration_required"
        ] is False

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
            "--multi-subagent-feature",
            "enabled",
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
            "--agent-model",
            "peer_v1",
            "--agent-profile-json",
            agent_profile_json,
            "--agent-work-mode",
            "codex-side-bypass=monitor_only",
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
            "--issue-fix-reviewer-notification-config",
            ".loopx/config/issue-fix/reviewer-notification-sinks.json",
            "--lark-event-inbox-config",
            ".loopx/config/lark/event-inbox.json",
            "--lark-kanban-heartbeat-sync",
            "--reward-memory-config",
            ".loopx/config/reward-memory/experiment.json",
            "--reward-memory-agent",
            "codex-side-bypass",
        ))
        assert dry["ok"] is True, dry
        assert dry["dry_run"] is True, dry
        assert dry["changed"] is True, dry
        assert "waiting_on" in dry["changed_fields"], dry
        assert "checkpointed_boundary_authority" in dry["changed_fields"], dry
        assert "registered_agents" in dry["changed_fields"], dry
        assert "configured_agent_model" in dry["changed_fields"], dry
        assert "agent_work_modes" in dry["changed_fields"], dry
        assert "write_scope" in dry["changed_fields"], dry
        assert "issue_fix_reviewer_notification" in dry["changed_fields"], dry
        assert "lark_event_inbox" in dry["changed_fields"], dry
        assert "lark_kanban_heartbeat_sync" in dry["changed_fields"], dry
        assert "reward_memory" in dry["changed_fields"], dry
        assert dry["after"]["waiting_on"] == "user_or_controller", dry
        assert dry["after"]["write_scope"] == ["docs/**", "tests/**"], dry
        assert dry["after"]["checkpointed_boundary_authority"]["active_write_scope"] == ["docs/**"], dry
        assert dry["after"]["registered_agents"] == ["codex-main-control", "codex-side-bypass"], dry
        assert dry["after"]["agent_model"] == "peer_v1", dry
        assert dry["after"]["agent_work_modes"] == {
            "codex-side-bypass": "monitor_only"
        }, dry
        assert dry["after"]["issue_fix_reviewer_notification"] == {
            "enabled": True,
            "config_pointer_registered": True,
        }, dry
        assert dry["after"]["lark_event_inbox"] == {
            "enabled": True,
            "config_pointer_registered": True,
        }, dry
        assert dry["after"]["lark_kanban_heartbeat_sync"] == {
            "enabled": True,
        }, dry
        assert dry["after"]["reward_memory"] == {
            "enabled": True,
            "experimental": True,
            "config_pointer_registered": True,
            "enabled_agents": ["codex-side-bypass"],
        }, dry
        assert dry["feature_summary"]["multi_subagent"] == "enabled", dry
        catalog = dry["configuration_catalog"]
        assert catalog["schema_version"] == "loopx_goal_configuration_catalog_v0", catalog
        assert catalog["scope"] == "default_off_optional_capabilities", catalog
        assert catalog["disclosure_policy"]["first_run_configuration_required"] is False
        features = {item["feature_id"]: item for item in catalog["features"]}
        assert set(features) == {
            "multi_subagent",
            "explore_graph",
            "explore_harness",
            "reward_memory",
            "lark_event_inbox",
            "lark_kanban_heartbeat_sync",
        }
        assert features["multi_subagent"]["current"]["enabled"] is True
        assert features["explore_graph"]["current"]["enabled"] is False
        assert "--execute" not in features["explore_harness"]["commands"]["preview_enable"]
        assert "--execute" in features["explore_harness"]["commands"]["apply_enable"]
        assert "--execute" not in features["explore_graph"]["commands"]["preview_disable"]
        assert "--execute" in features["explore_graph"]["commands"]["apply_disable"]
        assert features["lark_event_inbox"]["current"]["enabled"] is True
        assert "--execute" not in features["lark_event_inbox"]["commands"]["preview_enable"]
        assert "--execute" in features["lark_event_inbox"]["commands"]["apply_enable"]
        assert features["lark_kanban_heartbeat_sync"]["current"]["enabled"] is True
        assert "--execute" not in features["lark_kanban_heartbeat_sync"]["commands"]["preview_enable"]
        assert "--execute" in features["lark_kanban_heartbeat_sync"]["commands"]["apply_enable"]
        assert "--no-lark-kanban-heartbeat-sync" in features["lark_kanban_heartbeat_sync"]["commands"]["preview_disable"]
        assert features["reward_memory"]["availability"] == "experimental_opt_in"
        assert features["reward_memory"]["current"]["enabled_agents"] == [
            "codex-side-bypass"
        ]
        assert "--execute" not in features["reward_memory"]["commands"]["preview_enable"]
        assert "--execute" in features["reward_memory"]["commands"]["apply_enable"]
        migration = dry["heartbeat_prompt_migration"]
        assert migration["schema_version"] == "heartbeat_prompt_migration_v1", migration
        assert "agent identity changed" in migration["reason"], migration
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
            "--multi-subagent-feature",
            "enabled",
            "--max-children",
            "2",
            "--allowed-domain",
            "docs,validation",
            "--registered-agent",
            "codex-main-control,codex-side-bypass",
            "--agent-model",
            "peer_v1",
            "--agent-profile-json",
            agent_profile_json,
            "--agent-work-mode",
            "codex-side-bypass=monitor_only",
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
            "--issue-fix-reviewer-notification-config",
            ".loopx/config/issue-fix/reviewer-notification-sinks.json",
            "--lark-event-inbox-config",
            ".loopx/config/lark/event-inbox.json",
            "--lark-kanban-heartbeat-sync",
            "--reward-memory-config",
            ".loopx/config/reward-memory/experiment.json",
            "--reward-memory-agent",
            "codex-side-bypass",
            "--execute",
        ))
        assert applied["ok"] is True, applied
        assert applied["dry_run"] is False, applied
        assert applied["written"] is True, applied
        assert applied["feature_summary"]["multi_subagent"] == "enabled", applied
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
        assert goal["coordination"]["agent_model"] == "peer_v1", goal
        assert goal["coordination"]["agent_profiles"] == {
            "codex-side-bypass": agent_profile,
        }, goal
        assert goal["coordination"]["agent_work_modes"] == {
            "codex-side-bypass": "monitor_only"
        }, goal
        assert goal["coordination"]["write_scope"] == ["docs/**", "tests/**"], goal
        assert goal["waiting_on"] == "user_or_controller", goal
        reviewer_policy = goal["control_plane"]["issue_fix"][
            "reviewer_notification"
        ]
        assert reviewer_policy == {
            "enabled": True,
            "config_path": ".loopx/config/issue-fix/reviewer-notification-sinks.json",
        }, reviewer_policy
        assert goal["control_plane"]["lark_event_inbox"] == {
            "enabled": True,
            "config_path": ".loopx/config/lark/event-inbox.json",
        }, goal
        assert goal["control_plane"]["lark_kanban"] == {
            "heartbeat_sync_enabled": True,
        }, goal
        assert goal["control_plane"]["reward_memory"] == {
            "enabled": True,
            "experimental": True,
            "config_path": ".loopx/config/reward-memory/experiment.json",
            "enabled_agents": ["codex-side-bypass"],
        }, goal
        boundary = goal_boundary(goal, registry_path=registry_path)
        assert boundary["capabilities"]["issue_fix_reviewer_notification"] == {
            "enabled": True,
            "config_pointer_registered": True,
        }, boundary
        assert boundary["capabilities"]["lark_event_inbox"] == {
            "enabled": True,
            "config_pointer_registered": True,
            "drain_command": (
                f"loopx --registry {registry_path} lark-inbox drain "
                "--goal-id configure-goal-fixture"
            ),
            "urgency": {
                "schema_version": "lark_event_inbox_urgency_v0",
                "enabled": True,
                "projection_status": "unavailable",
                "local_private_content_returned": False,
            },
        }, boundary
        expected_kanban_action = {
            "action_id": "lark_kanban_sync",
            "trigger": "material_state_change",
            "command": (
                f"loopx --registry {registry_path} lark-kanban sync-loopx-todos "
                f"--goal-id {GOAL_ID} --project {root / 'project'} --execute"
            ),
            "failure_policy": "nonblocking_no_p0_preemption",
        }
        assert boundary["post_writeback_actions"] == [expected_kanban_action], boundary
        quota_projection = payload(
            run_cli(
                registry_path,
                "quota",
                "should-run",
                "--goal-id",
                GOAL_ID,
                "--agent-id",
                "codex-main-control",
            )
        )
        assert quota_projection["goal_boundary"]["post_writeback_actions"] == [
            expected_kanban_action
        ], quota_projection
        assert quota_projection["interaction_contract"]["cli_channel"][
            "post_writeback_actions"
        ] == [expected_kanban_action], quota_projection
        allowed_boundary = goal_boundary(goal, agent_id="codex-side-bypass")
        assert allowed_boundary["capabilities"]["reward_memory"]["enabled"] is True
        assert allowed_boundary["capabilities"]["reward_memory"][
            "configured_for_agent"
        ] is True
        denied_boundary = goal_boundary(goal, agent_id="codex-main-control")
        assert "reward_memory" not in denied_boundary.get("capabilities", {})
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

        feature_conflict = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--multi-subagent-feature",
            "enabled",
            "--spawn-allowed",
            check=False,
        ))
        assert feature_conflict["ok"] is False, feature_conflict
        assert "cannot be combined" in feature_conflict["error"], feature_conflict

        feature_off_children = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--multi-subagent-feature",
            "off",
            "--max-children",
            "1",
            check=False,
        ))
        assert feature_off_children["ok"] is False, feature_off_children
        assert "max-children greater than 0" in feature_off_children["error"], feature_off_children

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

        invalid_profile = dict(agent_profile, profile_role="primary-agent")
        invalid_profile_result = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--agent-profile-json",
            json.dumps(invalid_profile),
            check=False,
        ))
        assert invalid_profile_result["ok"] is False, invalid_profile_result
        assert "hierarchy role" in invalid_profile_result["error"], invalid_profile_result

        private_profile = dict(
            agent_profile,
            scope_summary="Read /Users/example/private-state before routing.",
        )
        private_profile_result = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--agent-profile-json",
            json.dumps(private_profile),
            check=False,
        ))
        assert private_profile_result["ok"] is False, private_profile_result
        assert "public-safe" in private_profile_result["error"], private_profile_result

        profile_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-agent-profile",
            "codex-side-bypass",
            "--execute",
        ))
        assert profile_cleared["ok"] is True, profile_cleared
        assert "agent_profiles" in profile_cleared["changed_fields"], profile_cleared
        assert "agent_profiles" not in goal_from_registry(registry_path)["coordination"]

        work_mode_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-agent-work-mode",
            "codex-side-bypass",
            "--execute",
        ))
        assert work_mode_cleared["ok"] is True, work_mode_cleared
        assert "agent_work_modes" in work_mode_cleared["changed_fields"], work_mode_cleared
        assert "agent_work_modes" not in goal_from_registry(registry_path)["coordination"]

        invalid_reward_agent = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--reward-memory-agent",
            "codex-not-registered",
            check=False,
        ))
        assert invalid_reward_agent["ok"] is False, invalid_reward_agent
        assert "must already be registered" in invalid_reward_agent["error"]

        reward_memory_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-reward-memory-config",
            "--execute",
        ))
        assert reward_memory_cleared["ok"] is True, reward_memory_cleared
        assert "reward_memory" in reward_memory_cleared["changed_fields"]
        assert "reward_memory" not in goal_from_registry(registry_path)["control_plane"]

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
        assert "configured_agent_model" in agents_cleared["changed_fields"], agents_cleared
        assert "registered_agents" not in goal_from_registry(registry_path)["coordination"], agents_cleared
        assert "agent_model" not in goal_from_registry(registry_path)["coordination"], agents_cleared

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

        feature_disabled = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--multi-subagent-feature",
            "off",
            "--execute",
        ))
        assert feature_disabled["ok"] is True, feature_disabled
        assert feature_disabled["feature_summary"]["multi_subagent"] == "off", feature_disabled
        disabled_goal = goal_from_registry(registry_path)
        assert disabled_goal["spawn_policy"]["mode"] == "default", disabled_goal
        assert disabled_goal["spawn_policy"]["allowed"] is False, disabled_goal
        assert disabled_goal["spawn_policy"]["max_children"] == 0, disabled_goal
        assert disabled_goal["spawn_policy"]["allowed_domains"] == [], disabled_goal

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

        invalid_private_pointer = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--issue-fix-reviewer-notification-config",
            "../outside/reviewer-notification-sinks.json",
            check=False,
        ))
        assert invalid_private_pointer["ok"] is False, invalid_private_pointer
        assert ".loopx/config" in invalid_private_pointer["error"], invalid_private_pointer

        reviewer_config_cleared = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--clear-issue-fix-reviewer-notification-config",
            "--execute",
        ))
        assert reviewer_config_cleared["ok"] is True, reviewer_config_cleared
        cleared_goal = goal_from_registry(registry_path)
        assert "issue_fix" not in cleared_goal["control_plane"], cleared_goal

        kanban_heartbeat_disabled = payload(run_cli(
            registry_path,
            "configure-goal",
            "--goal-id",
            GOAL_ID,
            "--no-lark-kanban-heartbeat-sync",
            "--execute",
        ))
        assert kanban_heartbeat_disabled["ok"] is True, kanban_heartbeat_disabled
        assert kanban_heartbeat_disabled["after"]["lark_kanban_heartbeat_sync"] == {
            "enabled": False,
        }, kanban_heartbeat_disabled
        assert kanban_heartbeat_disabled["heartbeat_prompt_migration"] is None
        disabled_goal = goal_from_registry(registry_path)
        assert disabled_goal["control_plane"]["lark_kanban"] == {
            "heartbeat_sync_enabled": False,
        }, disabled_goal
        disabled_boundary = goal_boundary(disabled_goal)
        assert "post_writeback_actions" not in disabled_boundary
        disabled_quota_projection = payload(
            run_cli(
                registry_path,
                "quota",
                "should-run",
                "--goal-id",
                GOAL_ID,
            )
        )
        assert "post_writeback_actions" not in disabled_quota_projection[
            "goal_boundary"
        ]
        assert "post_writeback_actions" not in disabled_quota_projection[
            "interaction_contract"
        ]["cli_channel"]

    print("configure-goal-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
