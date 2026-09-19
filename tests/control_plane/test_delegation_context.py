from __future__ import annotations

import json
from pathlib import Path

from loopx.control_plane.agent_context import project_goal_agent_context
from loopx.control_plane.collaboration import delegation_context


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    project = tmp_path / "project"
    config_dir = project / ".loopx" / "config"
    config_dir.mkdir(parents=True)
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "goals": [
                    {
                        "id": "goal-a",
                        "repo": str(project),
                        "status": "active",
                        "coordination": {
                            "registered_agents": ["coordinator", "worker"]
                        },
                    }
                ],
            }
        )
    )
    config = config_dir / "delegations.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": "loopx_local_delegation_v0",
                "bindings": [
                    {
                        "id": "independent-review",
                        "agent_id": "worker",
                        "todo_id": "todo-review",
                        "requesters": ["coordinator"],
                        "workspace": str(tmp_path / "worker"),
                        "host_args": ["--host", "generic-cli"],
                        "timeout_seconds": 60,
                        "output_refs": ["result.json"],
                    }
                ],
            }
        )
    )
    return project, registry, tmp_path / "runtime"


def test_projects_authorized_route_without_private_binding_material(
    tmp_path: Path, monkeypatch
) -> None:
    project, registry, runtime = _fixture(tmp_path)
    monkeypatch.setattr(
        delegation_context,
        "managed_executor_binding_from_host_args",
        lambda *_args, **_kwargs: {
            "executor": "managed-runtime",
            "executor_kind": "managed",
            "execution_profile": "model-a@high",
            "available": True,
            "unavailable_reason": None,
        },
    )
    packet = delegation_context.project_delegation_context(
        runtime_root=runtime,
        registry_path=registry,
        goal_id="goal-a",
        agent_id="coordinator",
        project=project,
        execution_config=".loopx/config/delegations.json",
    )
    assert packet["configuration_state"] == "ready"
    assert packet["authorized_count"] == packet["projected_count"] == 1
    assert packet["operation_receipts"] == {"observed": 0}
    assert packet["routes"] == [
        {
            "binding_id": "independent-review",
            "agent_id": "worker",
            "todo_id": "todo-review",
            "runtime_id": "managed-runtime",
            "executor_kind": "managed",
            "readiness": "ready",
            "execution_profile": "model-a@high",
        }
    ]
    encoded = json.dumps(packet)
    assert str(project) not in encoded
    assert "host_args" not in encoded
    assert "output_refs" not in encoded


def test_missing_config_is_blocked_observation_not_empty_success(tmp_path: Path) -> None:
    project, registry, runtime = _fixture(tmp_path)
    packet = delegation_context.project_delegation_context(
        runtime_root=runtime,
        registry_path=registry,
        goal_id="goal-a",
        agent_id="coordinator",
        project=project,
        execution_config=".loopx/config/missing.json",
    )
    assert packet["configuration_state"] == "blocked"
    assert packet["reason_code"] == "delegation_context_unavailable"
    assert packet["routes"] == []


def test_symlinked_config_is_blocked_even_when_target_is_inside_project(
    tmp_path: Path,
) -> None:
    project, registry, runtime = _fixture(tmp_path)
    config = project / ".loopx" / "config" / "delegations.json"
    real_config = config.with_name("delegations-real.json")
    config.rename(real_config)
    config.symlink_to(real_config)

    packet = delegation_context.project_delegation_context(
        runtime_root=runtime,
        registry_path=registry,
        goal_id="goal-a",
        agent_id="coordinator",
        project=project,
        execution_config=".loopx/config/delegations.json",
    )

    assert packet["configuration_state"] == "blocked"
    assert packet["reason_code"] == "delegation_context_unavailable"


def test_disabled_capability_does_not_read_retained_execution_config(
    tmp_path: Path, monkeypatch
) -> None:
    project, registry, runtime = _fixture(tmp_path)
    monkeypatch.setattr(
        delegation_context,
        "project_delegation_context",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must not read")),
    )

    context = project_goal_agent_context(
        phase="before_plan",
        scope={"goal_id": "goal-a", "agent_id": "coordinator", "todo_id": None},
        goal={
            "id": "goal-a",
            "repo": str(project),
            "spawn_policy": {
                "mode": "multi_subagent",
                "allowed": False,
                "max_children": 2,
                "execution_config": ".loopx/config/delegations.json",
            },
        },
        registry_path=registry,
        runtime_root=runtime,
    )

    assert context is None
