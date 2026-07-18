#!/usr/bin/env python3
"""Smoke-test local default upgrade propagation planning."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.configure_goal import configure_goal  # noqa: E402
from loopx.heartbeat_prompt import build_heartbeat_prompt  # noqa: E402
from loopx.upgrade import build_upgrade_plan, prompt_digest, render_upgrade_plan_markdown  # noqa: E402


GOAL_ID = "upgrade-plan-goal"
DEFERRED_GOAL_ID = "planned-main-control"
REGISTERED_GOAL_ID = "registered-agent-upgrade-plan-goal"
REGISTERED_AGENT_ID = "codex-current"


def write_fixture(root: Path) -> tuple[Path, Path]:
    project = root / "project"
    runtime = root / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "## Next Action\n\n"
        "- Keep the fixture heartbeat prompt current.\n",
        encoding="utf-8",
    )
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": GOAL_ID,
                        "domain": "fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "quota": {"compute": 1.0, "window_hours": 24},
                    },
                    {
                        "id": DEFERRED_GOAL_ID,
                        "domain": "fixture",
                        "status": "planned-high-complexity",
                        "attention_status": "stage_deferred_not_installed",
                        "recommended_action": "Do not install this heartbeat until the operator authorizes the stage.",
                        "repo": str(project),
                        "state_file": f".codex/goals/{GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "planned_read_only_map_v0", "status": "planned"},
                        "quota": {"compute": 1.0, "window_hours": 24},
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path, root / "installed-heartbeats.json"


def assert_unknown_manifest_blocks_promotion(registry_path: Path) -> dict:
    payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
    assert payload["ok"] is True, payload
    assert payload["prompt_modes"] == ["thin"], payload
    assert payload["summary"]["managed_goal_count"] == 1, payload
    assert payload["summary"]["stage_deferred_goal_count"] == 1, payload
    assert payload["summary"]["unknown_prompt_count"] == 1, payload
    assert payload["summary"]["installed_manifest_available"] is False, payload
    assert payload["summary"]["installed_manifest_source"] == "codex_app_automations", payload
    assert payload["summary"]["installed_manifest_entry_count"] == 0, payload
    assert payload["summary"]["installed_manifest_has_task_body"] is False, payload
    assert payload["summary"]["installed_prompt_policy_warning_count"] == 0, payload
    assert payload["summary"]["installed_prompt_policy_warning_prompt_count"] == 0, payload
    assert payload["summary"]["ready_for_default_promotion"] is False, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["schema_version"] == "default_upgrade_propagation_v0", payload
    assert propagation["managed_target_count"] == 1, payload
    assert propagation["deferred_target_count"] == 1, payload
    assert propagation["update_count"] == 1, payload
    assert propagation["unknown_count"] == 1, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["managed_targets"][0]["action"] == "regenerate_installed_prompt", payload
    assert propagation["managed_targets"][0]["reason"] == "installed prompt is missing from the manifest", payload
    assert propagation["stage_deferred_targets"][0]["action"] == "skip_stage_deferred", payload
    deferred = payload["stage_deferred_heartbeats"][0]
    assert deferred["goal_id"] == DEFERRED_GOAL_ID, payload
    assert deferred["requires_update"] is False, payload
    assert deferred["attention_status"] == "stage_deferred_not_installed", payload
    goal = payload["managed_heartbeats"][0]
    assert goal["goal_id"] == GOAL_ID, payload
    assert goal["state_file_exists"] is True, payload
    thin_prompt = goal["generated_prompts"]["thin"]
    assert thin_prompt["within_interface_budget"] is True, payload
    assert thin_prompt["interface_budget"]["mode"] == "thin", payload
    assert thin_prompt["interface_budget_char_count"] <= thin_prompt["interface_budget_max_chars"], payload
    assert goal["installed_prompts"]["thin"]["status"] == "unknown", payload
    markdown = render_upgrade_plan_markdown(payload)
    assert "ready_for_default_promotion: `False`" in markdown, markdown
    assert "stage_deferred_goal_count: `1`" in markdown, markdown
    assert "## Default Upgrade Propagation" in markdown, markdown
    assert "deferred_install_count: `0`" in markdown, markdown
    assert "action=`skip_stage_deferred`" in markdown, markdown
    assert "## Stage Deferred Heartbeats" in markdown, markdown
    assert DEFERRED_GOAL_ID in markdown, markdown
    return payload


def assert_matching_manifest_is_ready(registry_path: Path, manifest_path: Path, first_payload: dict) -> None:
    goal = first_payload["managed_heartbeats"][0]
    prompt_sha = goal["generated_prompts"]["thin"]["sha256"]
    manifest_path.write_text(
        json.dumps(
            {
                "automations": [
                    {
                        "automation_id": "fixture-heartbeat",
                        "goal_id": GOAL_ID,
                        "mode": "thin",
                        "prompt_sha256": prompt_sha,
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payload = build_upgrade_plan(
        registry_path=registry_path,
        installed_manifest=manifest_path,
        cli_bin="loopx",
    )
    assert payload["summary"]["unknown_prompt_count"] == 0, payload
    assert payload["summary"]["stale_prompt_count"] == 0, payload
    assert payload["summary"]["current_prompt_count"] == 1, payload
    assert payload["summary"]["not_installed_prompt_count"] == 0, payload
    assert payload["summary"]["stage_deferred_goal_count"] == 1, payload
    assert payload["summary"]["installed_manifest_entry_count"] == 1, payload
    assert payload["summary"]["installed_manifest_has_task_body"] is False, payload
    assert payload["summary"]["installed_prompt_policy_warning_count"] == 0, payload
    assert payload["summary"]["installed_prompt_policy_warning_prompt_count"] == 0, payload
    assert payload["summary"]["ready_for_default_promotion"] is True, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["ready_for_default_promotion"] is True, payload
    assert propagation["managed_target_count"] == 1, payload
    assert propagation["deferred_target_count"] == 1, payload
    assert propagation["update_count"] == 0, payload
    assert propagation["current_count"] == 1, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["managed_targets"][0]["action"] == "current", payload
    assert propagation["stage_deferred_targets"][0]["action"] == "skip_stage_deferred", payload
    assert payload["managed_heartbeats"][0]["installed_prompts"]["thin"]["status"] == "current", payload


def assert_not_installed_manifest_is_ready(registry_path: Path, manifest_path: Path) -> None:
    manifest_path.write_text(
        json.dumps(
            {
                "automations": [
                    {
                        "goal_id": GOAL_ID,
                        "mode": "thin",
                        "installed": False,
                        "status": "not_installed",
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    payload = build_upgrade_plan(
        registry_path=registry_path,
        installed_manifest=manifest_path,
        cli_bin="loopx",
    )
    assert payload["summary"]["unknown_prompt_count"] == 0, payload
    assert payload["summary"]["stale_prompt_count"] == 0, payload
    assert payload["summary"]["current_prompt_count"] == 0, payload
    assert payload["summary"]["not_installed_prompt_count"] == 1, payload
    assert payload["summary"]["stage_deferred_goal_count"] == 1, payload
    assert payload["summary"]["installed_manifest_entry_count"] == 1, payload
    assert payload["summary"]["installed_manifest_has_task_body"] is False, payload
    assert payload["summary"]["installed_prompt_policy_warning_count"] == 0, payload
    assert payload["summary"]["installed_prompt_policy_warning_prompt_count"] == 0, payload
    assert payload["summary"]["ready_for_default_promotion"] is True, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["ready_for_default_promotion"] is True, payload
    assert propagation["not_installed_noop_count"] == 1, payload
    assert propagation["update_count"] == 0, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["managed_targets"][0]["action"] == "not_installed_noop", payload
    installed = payload["managed_heartbeats"][0]["installed_prompts"]["thin"]
    assert payload["managed_heartbeats"][0]["requires_update"] is False, payload
    assert installed["status"] == "not_installed", payload
    assert installed["requires_update"] is False, payload
    assert installed["installed"] is False, payload


def assert_stage_deferred_selection_is_not_upgrade_work(registry_path: Path) -> None:
    payload = build_upgrade_plan(
        registry_path=registry_path,
        cli_bin="loopx",
        goal_ids=[DEFERRED_GOAL_ID],
    )
    assert payload["summary"]["managed_goal_count"] == 0, payload
    assert payload["summary"]["unknown_prompt_count"] == 0, payload
    assert payload["summary"]["stale_prompt_count"] == 0, payload
    assert payload["summary"]["stage_deferred_goal_count"] == 1, payload
    assert payload["managed_heartbeats"] == [], payload
    assert payload["stage_deferred_heartbeats"][0]["goal_id"] == DEFERRED_GOAL_ID, payload
    assert payload["stage_deferred_heartbeats"][0]["requires_update"] is False, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["managed_target_count"] == 0, payload
    assert propagation["deferred_target_count"] == 1, payload
    assert propagation["update_count"] == 0, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["stage_deferred_targets"][0]["action"] == "skip_stage_deferred", payload
    assert "stage-deferred" in payload["recommended_action"], payload


def write_codex_app_automation(codex_home: Path, *, prompt: str) -> Path:
    automation_path = codex_home / "automations" / GOAL_ID / "automation.toml"
    automation_path.parent.mkdir(parents=True, exist_ok=True)
    automation_path.write_text(
        "\n".join(
            [
                "version = 1",
                f'id = "{GOAL_ID}"',
                'kind = "heartbeat"',
                'name = "Upgrade Plan Fixture"',
                f"prompt = {json.dumps(prompt)}",
                'status = "ACTIVE"',
                'rrule = "RRULE:FREQ=MINUTELY;INTERVAL=5"',
                'target_thread_id = "fixture-thread"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return automation_path


def write_registered_fixture(root: Path) -> Path:
    project = root / "registered-project"
    runtime = root / "registered-runtime"
    state_file = project / ".codex" / "goals" / REGISTERED_GOAL_ID / "ACTIVE_GOAL_STATE.md"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "updated_at: 2026-01-01T00:00:00+00:00\n"
        "---\n\n"
        "## Agent Todo\n\n"
        "- [ ] Keep the registered-agent heartbeat prompt current.\n",
        encoding="utf-8",
    )
    registry_path = project / ".loopx" / "registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": REGISTERED_GOAL_ID,
                        "domain": "fixture",
                        "status": "active",
                        "repo": str(project),
                        "state_file": f".codex/goals/{REGISTERED_GOAL_ID}/ACTIVE_GOAL_STATE.md",
                        "adapter": {"kind": "generic_project_goal_v0", "status": "connected"},
                        "coordination": {
                            "registered_agents": [REGISTERED_AGENT_ID],
                            "primary_agent": REGISTERED_AGENT_ID,
                        },
                        "quota": {"compute": 1.0, "window_hours": 24},
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return registry_path


def write_registered_codex_app_automation(codex_home: Path, *, prompt: str) -> Path:
    automation_path = codex_home / "automations" / REGISTERED_GOAL_ID / "automation.toml"
    automation_path.parent.mkdir(parents=True, exist_ok=True)
    automation_path.write_text(
        "\n".join(
            [
                "version = 1",
                f'id = "{REGISTERED_GOAL_ID}"',
                'kind = "heartbeat"',
                'name = "Registered Agent Fixture"',
                f"prompt = {json.dumps(prompt)}",
                'status = "ACTIVE"',
                'rrule = "RRULE:FREQ=MINUTELY;INTERVAL=3"',
                'target_thread_id = "fixture-thread"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    return automation_path


def assert_registered_agent_activation_is_checked(root: Path) -> None:
    registry_path = write_registered_fixture(root)
    payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
    assert payload["summary"]["managed_goal_count"] == 1, payload
    assert payload["summary"]["unknown_prompt_count"] == 1, payload
    assert payload["summary"]["host_loop_activated_goal_count"] == 0, payload
    assert payload["summary"]["host_loop_missing_goal_count"] == 1, payload
    assert payload["summary"]["ready_for_default_promotion"] is False, payload
    assert "peer runtime automation migration" in payload["recommended_action"], payload
    assert payload["summary"]["peer_runtime_automation_migration_count"] == 1, payload
    goal = payload["managed_heartbeats"][0]
    assert goal["requires_update"] is True, payload
    assert goal["registered_agents"] == [REGISTERED_AGENT_ID], payload
    assert "primary_agent" not in goal, payload
    migration = goal["peer_runtime_automation_migration"]
    assert migration["required"] is True, migration
    assert migration["host_update_required_once"] is False, migration
    assert migration["host_updates"] == [], migration
    assert migration["migration_id"] in migration["completion_command"], migration
    assert "thin:codex-current" in goal["generated_prompts"], payload
    assert "thin:codex-current" in goal["installed_prompts"], payload
    activation = goal["host_loop_activation"]
    assert activation["status"] == "missing", payload
    assert activation["activated"] is False, payload
    assert activation["missing_targets"] == ["thin:codex-current"], payload
    assert "do not claim LoopX setup complete" in activation["recommended_action"], payload

    rendered = build_heartbeat_prompt(
        goal_id=REGISTERED_GOAL_ID,
        active_state=None,
        active_state_source="registry",
        resolved_active_state=Path(goal["state_file"]),
        thin=True,
        cli_bin="loopx",
        agent_id=REGISTERED_AGENT_ID,
        registered_agents=[REGISTERED_AGENT_ID],
        available_capabilities=["network", "external_evidence_poll"],
        runtime_profile="codex_app_heartbeat",
    )["task_body"]
    write_registered_codex_app_automation(root / "registered-codex-home", prompt=rendered)
    old_codex_home = os.environ.get("CODEX_HOME")
    os.environ["CODEX_HOME"] = str(root / "registered-codex-home")
    try:
        pending_payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
        pending_migration = pending_payload["managed_heartbeats"][0][
            "peer_runtime_automation_migration"
        ]
        pending_goal = pending_payload["managed_heartbeats"][0]
        pending_prompt = pending_goal["generated_prompts"]["thin:codex-current"]
        assert "--available-capability network" in pending_prompt["command"], pending_prompt
        assert "--available-capability external_evidence_poll" in pending_prompt["command"], (
            pending_prompt
        )
        assert pending_goal["installed_prompts"]["thin:codex-current"][
            "available_capabilities"
        ] == ["network", "external_evidence_poll"], pending_goal
        assert pending_migration["host_update_required_once"] is False, pending_migration
        pending_markdown = render_upgrade_plan_markdown(pending_payload)
        assert pending_migration["migration_id"] in pending_markdown, pending_markdown
        configure_goal(
            registry_path=registry_path,
            goal_id=REGISTERED_GOAL_ID,
            automation_prompt_migration_ack=pending_migration["migration_id"],
            execute=True,
        )
        current_payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
    finally:
        if old_codex_home is None:
            os.environ.pop("CODEX_HOME", None)
        else:
            os.environ["CODEX_HOME"] = old_codex_home
    current_goal = current_payload["managed_heartbeats"][0]
    assert current_payload["summary"]["current_prompt_count"] == 1, current_payload
    assert current_payload["summary"]["host_loop_activated_goal_count"] == 1, current_payload
    assert current_payload["summary"]["host_loop_missing_goal_count"] == 0, current_payload
    assert current_payload["summary"]["peer_runtime_automation_migration_count"] == 0, current_payload
    assert current_payload["summary"]["ready_for_default_promotion"] is True, current_payload
    assert current_goal["installed_prompts"]["thin:codex-current"]["status"] == "current", current_payload
    assert current_goal["requires_update"] is False, current_payload
    assert current_goal["installed_prompts"]["thin:codex-current"]["agent_id"] == REGISTERED_AGENT_ID, current_payload
    assert current_payload["installed_manifest"]["entries"][0]["agent_id"] == REGISTERED_AGENT_ID, current_payload
    assert current_goal["host_loop_activation"]["activated"] is True, current_payload
    markdown = render_upgrade_plan_markdown(current_payload)
    assert "host_loop_activation: surface=`codex_app_heartbeat` status=`current` activated=`True`" in markdown, markdown


def assert_codex_app_automation_is_discovered(registry_path: Path, codex_home: Path, first_payload: dict) -> None:
    rendered = build_heartbeat_prompt(
        goal_id=GOAL_ID,
        active_state=None,
        active_state_source="registry",
        thin=True,
        cli_bin="loopx",
        runtime_profile="codex_app_heartbeat",
    )["task_body"]
    expected_sha = first_payload["managed_heartbeats"][0]["generated_prompts"]["thin"]["sha256"]
    assert prompt_digest(rendered) == expected_sha, first_payload
    write_codex_app_automation(
        codex_home,
        prompt=rendered,
    )
    payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
    assert payload["installed_manifest"]["source"] == "codex_app_automations", payload
    assert payload["installed_manifest"]["available"] is True, payload
    auto_entry = payload["installed_manifest"]["entries"][0]
    assert "task_body" not in auto_entry, payload
    assert auto_entry["prompt_sha256"] == expected_sha, payload
    assert auto_entry["prompt_policy_audit"]["status"] == "clean", payload
    assert auto_entry["prompt_policy_audit"]["warning_count"] == 0, payload
    assert payload["summary"]["installed_manifest_entry_count"] == 1, payload
    assert payload["summary"]["installed_manifest_task_body_count"] == 0, payload
    assert payload["summary"]["installed_manifest_has_task_body"] is False, payload
    assert payload["summary"]["installed_prompt_policy_warning_count"] == 0, payload
    assert payload["summary"]["installed_prompt_policy_warning_prompt_count"] == 0, payload
    assert payload["summary"]["unknown_prompt_count"] == 0, payload
    assert payload["summary"]["stale_prompt_count"] == 0, payload
    assert payload["summary"]["current_prompt_count"] == 1, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["update_count"] == 0, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["managed_targets"][0]["action"] == "current", payload
    installed = payload["managed_heartbeats"][0]["installed_prompts"]["thin"]
    assert installed["status"] == "current", payload
    assert installed["automation_id"] == GOAL_ID, payload
    assert installed["installed"] is True, payload
    assert payload["summary"]["ready_for_default_promotion"] is True, payload


def assert_codex_app_stale_policy_prompt_is_flagged(registry_path: Path, codex_home: Path) -> None:
    stale_prompt = (
        f"Advance `{GOAL_ID}` from the registry-declared active state.\n\n"
        "Primary stability objective: keep a project-specific controller policy in the installed prompt.\n"
        "Current controller policy:\n"
        "- If `should_run=false`: no implementation, adapter work, file edits, research, exploration, or spend.\n"
        "- If `safe_bypass_kind=outcome_floor_recovery`: attempt one bounded recovery segment.\n"
        "Details: loopx heartbeat-prompt --compact --goal-id "
        f"{GOAL_ID} --active-state /tmp/stale/ACTIVE_GOAL_STATE.md\n"
    )
    write_codex_app_automation(codex_home, prompt=stale_prompt)
    payload = build_upgrade_plan(registry_path=registry_path, cli_bin="loopx")
    assert payload["summary"]["ready_for_default_promotion"] is False, payload
    assert payload["summary"]["stale_prompt_count"] == 1, payload
    assert payload["summary"]["installed_prompt_policy_warning_prompt_count"] == 1, payload
    assert payload["summary"]["installed_prompt_policy_warning_count"] == 3, payload
    auto_entry = payload["installed_manifest"]["entries"][0]
    assert "task_body" not in auto_entry, payload
    audit = auto_entry["prompt_policy_audit"]
    assert audit["status"] == "warning", payload
    kinds = {warning["kind"] for warning in audit["warnings"]}
    assert kinds == {
        "should_run_false_before_safe_bypass",
        "embedded_project_policy",
        "pinned_active_state_argument",
    }, payload
    installed = payload["managed_heartbeats"][0]["installed_prompts"]["thin"]
    assert installed["requires_update"] is True, payload
    assert installed["prompt_policy_audit"]["warning_count"] == 3, payload
    propagation = payload["default_upgrade_propagation"]
    assert propagation["update_count"] == 1, payload
    assert propagation["policy_warning_count"] == 3, payload
    assert propagation["deferred_install_count"] == 0, payload
    assert propagation["managed_targets"][0]["action"] == "regenerate_installed_prompt", payload
    assert (
        propagation["managed_targets"][0]["reason"]
        == "installed prompt policy warnings must be cleared before default promotion"
    ), payload
    markdown = render_upgrade_plan_markdown(payload)
    assert "installed_prompt_policy_warning_count: `3`" in markdown, markdown
    assert "should_run_false_before_safe_bypass" in markdown, markdown
    assert "embedded_project_policy" in markdown, markdown
    assert "pinned_active_state_argument" in markdown, markdown


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="loopx-upgrade-plan-smoke-") as raw_tmp:
        root = Path(raw_tmp)
        old_codex_home = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(root / "codex-home")
        try:
            registry_path, manifest_path = write_fixture(root)
            first_payload = assert_unknown_manifest_blocks_promotion(registry_path)
            assert_matching_manifest_is_ready(registry_path, manifest_path, first_payload)
            assert_not_installed_manifest_is_ready(registry_path, manifest_path)
            assert_stage_deferred_selection_is_not_upgrade_work(registry_path)
            assert_codex_app_automation_is_discovered(registry_path, root / "codex-home", first_payload)
            assert_codex_app_stale_policy_prompt_is_flagged(registry_path, root / "codex-home")
            assert_registered_agent_activation_is_checked(root)
        finally:
            if old_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_codex_home
    print("upgrade-plan-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
