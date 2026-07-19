from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from loopx.control_plane.todos.completion_policy import CompletionPolicy
from loopx.control_plane.testing.canary_harness import (
    run_json_cli,
    run_json_cli_result,
    write_fixture_registry,
)


GOAL_ID = "completion-policy-fixture"
AGENT_ID = "codex-quality-qualification"


def test_completion_policy_does_not_duplicate_runtime_model_authority() -> None:
    assert "agent_model" not in {field.name for field in fields(CompletionPolicy)}


def test_completion_rejects_unknown_runtime_model_before_write(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\nstatus: active\n---\n\n# Active Goal State\n\n## Agent Todo\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="loopx-platform",
        adapter_kind="harness_self_improvement",
        registered_agents=[AGENT_ID, "codex-main-control"],
        quota_allowed_slots=None,
    )
    source = run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "agent",
        "--text",
        "Validate the completion boundary.",
        "--claimed-by",
        AGENT_ID,
        registry_path=registry_path,
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["goals"][0]["coordination"]["agent_model"] = "hierarchy_v2"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    before = state_file.read_text(encoding="utf-8")

    returncode, result = run_json_cli_result(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        source["todo_id"],
        "--claimed-by",
        AGENT_ID,
        "--agent-id",
        AGENT_ID,
        "--evidence",
        "must remain atomic",
        "--no-follow-up",
        registry_path=registry_path,
    )

    assert returncode == 1
    assert "coordination.agent_model must be peer_v1" in result["error"]
    assert state_file.read_text(encoding="utf-8") == before
