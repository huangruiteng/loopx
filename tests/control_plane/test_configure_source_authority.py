"""A global settings entry must survive ordinary project-to-global projection."""

import json
import subprocess
import sys

import pytest

from loopx.configuration_transaction import goal_capability_configuration_revision
from loopx.configure_goal import configure_goal
from loopx.control_plane.goals.configure_goal_service import (
    configure_goal_with_global_sync,
    read_goal_configuration_with_source_route,
)
from loopx.global_registry import sync_project_registry_to_global


@pytest.fixture
def mirrored_goal(tmp_path):
    source = tmp_path / "project" / ".loopx" / "registry.json"
    runtime = tmp_path / "runtime"
    source.parent.mkdir(parents=True)
    runtime.mkdir()
    source.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(runtime),
                "goals": [
                    {
                        "id": "example",
                        "repo": str(tmp_path / "project"),
                        "status": "active",
                        "spawn_policy": {
                            "mode": "default",
                            "allowed": False,
                            "max_children": 3,
                        },
                    }
                ],
            }
        )
    )
    sync_project_registry_to_global(
        registry_path=source,
        runtime_root_override=str(runtime),
        goal_id="example",
        dry_run=False,
    )
    return source, runtime / "registry.global.json", runtime


def policy(path):
    return json.loads(path.read_text())["goals"][0]["spawn_policy"]


def test_global_cli_change_survives_source_resync(mirrored_goal):
    source, mirror, runtime = mirrored_goal
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "loopx.cli",
            "--registry",
            str(mirror),
            "--runtime-root",
            str(runtime),
            "--format",
            "json",
            "configure-goal",
            "--goal-id",
            "example",
            "--multi-subagent-feature",
            "enabled",
            "--max-children",
            "4",
            "--subagent-model",
            "example-model",
            "--subagent-reasoning-effort",
            "max",
            "--execute",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["ok"] is True
    expected = {
        "mode": "multi_subagent",
        "allowed": True,
        "max_children": 4,
        "model_config": {"model": "example-model", "reasoning_effort": "max"},
    }
    assert policy(source) == expected
    assert policy(mirror) == expected
    sync_project_registry_to_global(
        registry_path=source,
        runtime_root_override=str(runtime),
        goal_id="example",
        dry_run=False,
    )
    assert policy(mirror) == expected


def test_stale_mirror_reads_source_and_rejects_stale_source_revision(mirrored_goal):
    source, mirror, runtime = mirrored_goal
    configure_goal(
        registry_path=source,
        goal_id="example",
        multi_subagent_feature="enabled",
        max_children=4,
        execute=True,
    )
    assert policy(mirror)["allowed"] is False
    current = read_goal_configuration_with_source_route(
        registry_path=mirror, goal_id="example", execute=False
    )
    assert current["after"]["orchestration"]["spawn_allowed"] is True
    revision = goal_capability_configuration_revision(
        "example", current["configuration_catalog"]["capability_catalog"]
    )
    configure_goal(
        registry_path=source, goal_id="example", max_children=2, execute=True
    )
    before = (source.read_bytes(), mirror.read_bytes())
    with pytest.raises(ValueError, match="configuration changed"):
        configure_goal_with_global_sync(
            registry_path=mirror,
            goal_id="example",
            runtime_root_override=str(runtime),
            execute=True,
            max_children=3,
            expected_goal_configuration_revision=revision,
        )
    assert (source.read_bytes(), mirror.read_bytes()) == before


def test_missing_source_never_falls_back_to_writing_mirror(mirrored_goal):
    source, mirror, runtime = mirrored_goal
    source.unlink()
    before = mirror.read_bytes()
    for execute in [False, True]:
        with pytest.raises(ValueError, match="source_registry is missing"):
            configure_goal_with_global_sync(
                registry_path=mirror,
                goal_id="example",
                runtime_root_override=str(runtime),
                execute=execute,
                multi_subagent_feature="enabled",
                max_children=4,
            )
    assert mirror.read_bytes() == before


def test_browser_settings_read_and_apply_use_source(mirrored_goal):
    from tests.test_chat_server_cors import _request, _start_server

    source, mirror, runtime = mirrored_goal
    configure_goal(
        registry_path=source,
        goal_id="example",
        multi_subagent_feature="enabled",
        max_children=2,
        execute=True,
    )
    assert policy(mirror)["allowed"] is False
    server, thread = _start_server()
    server.registry_path = mirror
    server.runtime_root_override = str(runtime)
    server.goal_subagent_configuration_enabled = True
    port = server.server_address[1]
    origin = f"http://127.0.0.1:{port}"
    try:
        response = _request(
            port,
            method="GET",
            origin=origin,
            path="/api/chat/goal-configuration?goal_id=example",
        )
        inspection = json.loads(response.read())
        assert response.status == 200, inspection
        assert inspection["ok"] is True
        serialized = json.dumps(inspection["capability_catalog"])
        assert '"max_children": 2' in serialized
        body = {
            "goal_id": "example",
            "enabled": True,
            "max_children": 4,
            "model_config": {"model": "example-model", "reasoning_effort": "max"},
        }
        response = _request(
            port,
            method="POST",
            origin=origin,
            path="/api/chat/goal-subagents/dry-run",
            body=json.dumps(body).encode(),
        )
        preview = json.loads(response.read())
        assert response.status == 200, preview
        assert preview["before"]["orchestration"]["max_children"] == 2
        body["preview_id"] = preview["preview_id"]
        response = _request(
            port,
            method="POST",
            origin=origin,
            path="/api/chat/goal-subagents/apply",
            body=json.dumps(body).encode(),
        )
        applied = json.loads(response.read())
        assert response.status == 200, applied
        assert applied["ok"] is True
        assert policy(source) == policy(mirror)
        assert policy(source)["max_children"] == 4
        assert policy(source)["model_config"] == body["model_config"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
