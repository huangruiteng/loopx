from __future__ import annotations

import subprocess

from loopx.boundary_authority import build_checkpointed_boundary_authority_entry
from loopx.capabilities.explore.harness_gate import resolve_explore_harness_gate
from loopx.control_plane.quota.goal_boundary import (
    declared_available_capabilities,
    goal_boundary,
)
from loopx.control_plane.quota.task_orchestration import (
    apply_task_orchestration_contract,
)


def test_goal_boundary_uses_registry_goal_for_scope_and_capability_projection() -> None:
    boundary = goal_boundary(
        {
            "adapter_kind": "project",
            "adapter_status": "connected",
            "available_capabilities": ["registry-root"],
            "coordination": {
                "write_scope": ["docs/**"],
                "available_capabilities": ["registry-coordination"],
                "requires_parent_approval": ["write", "", "publish"],
            },
            "project_asset": {
                "available_capabilities": ["registry-project-asset"],
            },
            "guards": ["stay public", ""],
        },
        item={
            "available_capabilities": ["item-root"],
            "coordination": {
                "write_scope": ["private-item/**"],
                "available_capabilities": ["item-coordination"],
            },
            "project_asset": {
                "available_capabilities": ["item-project-asset"],
            },
        },
    )

    assert boundary is not None
    assert boundary["adapter"] == {
        "kind": "project",
        "status": "connected",
    }
    assert boundary["write_scope"] == ["docs/**"]
    assert boundary["available_capabilities"] == [
        "registry_root",
        "registry_coordination",
        "registry_project_asset",
    ]
    assert boundary["requires_parent_approval"] == ["write", "publish"]
    assert boundary["guards"] == ["stay public"]
    assert "peer_task_coordination" not in boundary


def test_goal_boundary_projects_only_explicit_valid_peer_coordinator() -> None:
    boundary = goal_boundary(
        {
            "coordination": {
                "registered_agents": ["codex-alpha", "codex-beta"],
                "peer_task_coordination": {
                    "coordinator_agent_id": "codex-alpha",
                },
            },
        }
    )

    assert boundary is not None
    assert boundary["peer_task_coordination"] == {
        "enabled": True,
        "coordinator_agent_id": "codex-alpha",
    }

    invalid = goal_boundary(
        {
            "coordination": {
                "peer_task_coordination": {
                    "coordinator_agent_id": "../../private",
                },
            },
        }
    )
    assert invalid is None


def test_goal_boundary_projects_credential_free_repository_identity(
    tmp_path,
) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    subprocess.run(["git", "init", str(project)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "remote",
            "add",
            "origin",
            "https://github.com/owner/loopx.git",
        ],
        check=True,
        capture_output=True,
    )

    boundary = goal_boundary(
        {
            "id": "repository-boundary-fixture",
            "repo": str(project),
            "spawn_policy": {
                "mode": "multi_subagent",
                "allowed": True,
                "max_children": 2,
            },
        }
    )

    assert boundary is not None
    assert boundary["task_repository"] == "git:github.com/owner/loopx"

    summary = {
        "items": [
            {
                "todo_id": "todo_primary",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "inspect",
                "task_domain": "code",
                "text": "Inspect the primary lane.",
            },
            {
                "todo_id": "todo_same_repo",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "inspect",
                "task_domain": "code",
                "task_repository": "git:github.com/owner/loopx",
                "text": "Inspect the same repository.",
            },
            {
                "todo_id": "todo_other_repo",
                "status": "open",
                "task_class": "advancement_task",
                "action_kind": "inspect",
                "task_domain": "code",
                "task_repository": "git:github.com/owner/private",
                "text": "Inspect another repository.",
            },
        ]
    }
    contract, _work_lane = apply_task_orchestration_contract(
        fallback_work_lane_contract={"lane": "advancement_task"},
        goal_boundary=boundary,
        agent_identity={
            "agent_id": "codex-fixture",
            "registered_agents": ["codex-fixture"],
        },
        agent_todo_summary=summary,
        raw_agent_todo_summary=summary,
        available_capabilities=["subagent_spawn"],
    )

    assert contract is not None
    assert [lane["todo_id"] for lane in contract["eligible_child_lanes"]] == [
        "todo_same_repo"
    ]
    assert contract["blocked_lanes"] == [
        {
            "todo_id": "todo_other_repo",
            "task_domain": "code",
            "reason_codes": ["task_repository_not_allowed"],
        }
    ]


def test_goal_boundary_requires_boolean_spawn_authority() -> None:
    for authority_key in ("allowed", "spawn_allowed"):
        boundary = goal_boundary(
            {
                "spawn_policy": {
                    authority_key: "false",
                    "max_children": 2,
                    "explore_harness": {"enabled": True},
                }
            }
        )

        assert boundary is not None
        assert boundary["orchestration"] == {
            "mode": "default",
            "spawn_allowed": False,
            "max_children": 2,
            "explore_harness": {"enabled": True},
        }
        gate = resolve_explore_harness_gate(
            boundary["orchestration"],
            requested_width=2,
            max_lanes=8,
            max_lanes_label="max_worker_lanes",
        )
        assert gate["state"] == "analysis_only"
        assert gate["reason"] == "spawn_not_allowed_by_goal_boundary"


def test_goal_boundary_appends_only_active_checkpointed_write_scopes() -> None:
    active = build_checkpointed_boundary_authority_entry(
        write_scopes=["tests/**", "loopx/**"],
        source="operator_gate_resume_contract_v0:active",
        recorded_at="2026-07-01T00:00:00+00:00",
    )
    expired = build_checkpointed_boundary_authority_entry(
        write_scopes=["runners/**"],
        source="operator_gate_resume_contract_v0:expired",
        recorded_at="2026-07-01T00:00:00+00:00",
        expires_at="2000-01-01T00:00:00+00:00",
    )

    boundary = goal_boundary(
        {
            "coordination": {
                "write_scope": ["docs/**", "tests/**", "docs/**"],
                "checkpointed_boundary_authority": [active, expired],
            }
        }
    )

    assert boundary is not None
    assert boundary["write_scope"] == ["docs/**", "tests/**", "loopx/**"]
    authority = boundary["checkpointed_boundary_authority"]
    assert authority["active_count"] == 1
    assert authority["inactive_count"] == 1
    assert authority["active_write_scope"] == ["tests/**", "loopx/**"]


def test_declared_available_capabilities_preserves_layer_order_and_deduplicates() -> None:
    assert declared_available_capabilities(
        {
            "available_capabilities": ["root", "shared"],
            "coordination": {
                "available_capabilities": ["coordination", "shared"],
            },
            "project_asset": {
                "available_capabilities": ["project-asset", "root"],
            },
        }
    ) == [
        "root",
        "shared",
        "coordination",
        "project_asset",
    ]
