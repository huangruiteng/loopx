from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.testing.canary_harness import (
    run_json_cli,
    run_json_cli_result,
    write_fixture_registry,
)


GOAL_ID = "loopx-meta-peer-completion"
AUTHOR_AGENT = "codex-value-explorer"
REVIEW_AGENT = "codex-quality-qualification"
OTHER_AGENT = "codex-main-control"


def _write_fixture(tmp_path: Path, *, legacy_hierarchy: bool) -> tuple[Path, Path]:
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    state_file = project / ".codex" / "goals" / GOAL_ID / "ACTIVE_GOAL_STATE.md"
    registry_path = project / ".loopx" / "registry.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        "---\n"
        "status: active\n"
        "---\n\n"
        "# Active Goal State\n\n"
        "## Agent Todo\n",
        encoding="utf-8",
    )
    write_fixture_registry(
        project=project,
        runtime_root=runtime,
        registry_path=registry_path,
        goal_id=GOAL_ID,
        domain="loopx-platform",
        adapter_kind="harness_self_improvement",
        registered_agents=[AUTHOR_AGENT, REVIEW_AGENT, OTHER_AGENT],
        quota_allowed_slots=None,
    )
    if legacy_hierarchy:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
        coordination = payload["goals"][0]["coordination"]
        coordination.update(
            {
                "agent_model": "legacy_hierarchy",
                "primary_agent": OTHER_AGENT,
                "side_agent_handoff_agent": REVIEW_AGENT,
            }
        )
        registry_path.write_text(json.dumps(payload), encoding="utf-8")
    return registry_path, state_file


def _add_claimed_source(registry_path: Path) -> dict:
    return run_json_cli(
        "todo",
        "add",
        "--goal-id",
        GOAL_ID,
        "--role",
        "agent",
        "--text",
        "Deliver one bounded control-plane slice.",
        "--task-class",
        "advancement_task",
        "--action-kind",
        "control_plane_slice",
        "--continuation-policy",
        "independent_handoff",
        "--claimed-by",
        AUTHOR_AGENT,
        registry_path=registry_path,
    )


@pytest.mark.parametrize("legacy_hierarchy", [False, True])
def test_claimed_peer_can_complete_with_bound_independent_successor(
    tmp_path: Path,
    legacy_hierarchy: bool,
) -> None:
    registry_path, _state_file = _write_fixture(
        tmp_path,
        legacy_hierarchy=legacy_hierarchy,
    )
    source = _add_claimed_source(registry_path)

    completed = run_json_cli(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        source["todo_id"],
        "--claimed-by",
        AUTHOR_AGENT,
        "--agent-id",
        AUTHOR_AGENT,
        "--evidence",
        "focused validation passed",
        "--next-agent-todo",
        "Independently review the control-plane slice.",
        "--next-claimed-by",
        REVIEW_AGENT,
        "--next-action-kind",
        "independent_review",
        "--next-continuation-policy",
        "independent_handoff",
        "--next-excluded-agent",
        AUTHOR_AGENT,
        registry_path=registry_path,
    )

    successor = completed["next_todos"][0]
    assert completed["mutation_authority"]["mode"] == "registered_peer_actor"
    assert completed["successor_todo_ids"] == [successor["todo_id"]]
    assert successor["claimed_by"] == REVIEW_AGENT
    assert successor["excluded_agents"] == [AUTHOR_AGENT]
    assert successor["unblocks_todo_id"] == source["todo_id"]
    assert successor["blocks_agent"] is None

    done = run_json_cli(
        "todo",
        "list",
        "--goal-id",
        GOAL_ID,
        "--role",
        "agent",
        "--status",
        "done",
        registry_path=registry_path,
    )
    source_readback = next(
        item for item in done["todos"] if item["todo_id"] == source["todo_id"]
    )
    assert source_readback["successor_todo_ids"] == [successor["todo_id"]]


def test_independent_successor_rejects_the_excluded_completing_peer(
    tmp_path: Path,
) -> None:
    registry_path, state_file = _write_fixture(tmp_path, legacy_hierarchy=False)
    source = _add_claimed_source(registry_path)
    before = state_file.read_text(encoding="utf-8")

    returncode, payload = run_json_cli_result(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        source["todo_id"],
        "--claimed-by",
        AUTHOR_AGENT,
        "--agent-id",
        AUTHOR_AGENT,
        "--evidence",
        "focused validation passed",
        "--next-agent-todo",
        "Review your own control-plane slice.",
        "--next-claimed-by",
        AUTHOR_AGENT,
        "--next-continuation-policy",
        "independent_handoff",
        "--next-excluded-agent",
        AUTHOR_AGENT,
        registry_path=registry_path,
    )

    assert returncode == 1
    assert "cannot also appear in next_excluded_agents" in payload["error"]
    assert state_file.read_text(encoding="utf-8") == before


def test_completion_rejects_an_unknown_registry_agent_model_before_write(
    tmp_path: Path,
) -> None:
    registry_path, state_file = _write_fixture(tmp_path, legacy_hierarchy=False)
    source = _add_claimed_source(registry_path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    payload["goals"][0]["coordination"]["agent_model"] = "hierarchy_v2"
    registry_path.write_text(json.dumps(payload), encoding="utf-8")
    before = state_file.read_text(encoding="utf-8")

    returncode, result = run_json_cli_result(
        "todo",
        "complete",
        "--goal-id",
        GOAL_ID,
        "--todo-id",
        source["todo_id"],
        "--claimed-by",
        AUTHOR_AGENT,
        "--agent-id",
        AUTHOR_AGENT,
        "--evidence",
        "must remain atomic",
        "--no-follow-up",
        registry_path=registry_path,
    )

    assert returncode == 1
    assert "coordination.agent_model must be peer_v1" in result["error"]
    assert state_file.read_text(encoding="utf-8") == before
