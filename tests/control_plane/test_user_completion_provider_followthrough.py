"""The public completion caller must carry dependent effects across promotion."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from canonical_authority_fixture import initialize_canonical_authority, isolate_sqlite_runtime
from test_todo_decision_scope_lifecycle import (
    AGENT_ID, GOAL_ID, PUBLISH_SCOPE, _add_target_and_gate, _write_fixture,
)
from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.todos import complete_goal_todo, list_goal_todos


@pytest.mark.parametrize("provider", ["legacy", "file", "sqlite"])
@pytest.mark.parametrize("outcome", ["approve", "reject", "cancel"])
def test_public_completion_commits_linked_decision(tmp_path: Path, monkeypatch, provider, outcome):
    isolate_sqlite_runtime(tmp_path, monkeypatch)
    _, state, registry = _write_fixture(tmp_path)
    config = json.loads(registry.read_text())
    config["common_runtime_root"] = str(tmp_path / "runtime")
    registry.write_text(json.dumps(config))
    target, gate = _add_target_and_gate(
        registry, required_scopes=[PUBLISH_SCOPE], target_status="blocked",
    )
    if provider != "legacy":
        source = list_goal_todos(registry_path=registry, goal_id=GOAL_ID)["todos"]
        projection = build_todo_runtime_shadow_projection(
            goal_id=GOAL_ID, handoff_mode="soft_claim", todos=source,
        )
        initialize_canonical_authority(tmp_path / "runtime", GOAL_ID, projection,
                                       state_path=state, provider=provider)
    result = complete_goal_todo(
        registry_path=registry, goal_id=GOAL_ID, todo_id=gate["todo_id"],
        role="user", agent_id=AGENT_ID, decision_outcome=outcome,
        evidence="Synthetic owner decision for this exact action",
    )
    rows = {row["todo_id"]: row for row in list_goal_todos(
        registry_path=registry, goal_id=GOAL_ID)["todos"]}
    assert result["decision_outcome"] == outcome
    assert rows[gate["todo_id"]]["status"] == "done"
    dependent = rows[target["todo_id"]]
    assert dependent["claimed_by"] == AGENT_ID
    if outcome == "approve":
        assert dependent["status"] == "open"
        assert not dependent.get("required_decision_scopes")
        assert result["unblock_resume"]["state"] == "resumed"
        assert result["decision_scope_resolution"]["state"] == "resolved"
    else:
        assert dependent["status"] == "blocked"
        assert dependent["required_decision_scopes"]
        assert dependent["decision_scope_outcomes"][0]["outcome"] == outcome
        assert result["unblock_resume"]["state"] == (
            "decision_rejected" if outcome == "reject" else "decision_cancelled")
