from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.capabilities.issue_fix.pr_gate_reconcile import (
    reconcile_issue_fix_pr_gate,
)


GOAL_ID = "multi-agent-pr-gate-reconcile"
ACTOR_AGENT = "codex-author"


def _write_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "repo"
    state = project / "ACTIVE_GOAL_STATE.md"
    state.parent.mkdir(parents=True)
    state.write_text(
        "## User Todo / Owner Review Reading Queue\n\n"
        "- [ ] Approve public PR merge.\n"
        "  <!-- loopx:todo todo_id=todo_merge_gate_2298 status=open "
        "task_class=user_gate decision_scope=direction:action:merge_pr_2298 "
        "blocks_agent=codex-author -->\n\n"
        "## Agent Todo\n\n",
        encoding="utf-8",
    )
    registry = tmp_path / "registry.global.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "status": "active",
                        "repo": str(project),
                        "state_file": state.name,
                        "adapter": {"kind": "harness_self_improvement"},
                        "coordination": {
                            "agent_model": "peer_v1",
                            "registered_agents": [ACTOR_AGENT, "codex-review"],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return registry, state


def _reconcile(registry: Path, state: Path, *, agent_id: str | None) -> dict:
    return reconcile_issue_fix_pr_gate(
        registry_path=registry,
        runtime_root_arg=str(registry.parent / "runtime"),
        goal_id=GOAL_ID,
        todo_id="todo_merge_gate_2298",
        agent_id=agent_id,
        project=state.parent,
        url="https://github.com/huangruiteng/loopx/pull/2298",
        provider_payload={
            "state": "MERGED",
            "mergedAt": "2026-07-18T00:00:00Z",
        },
        execute=True,
        generated_at="2026-07-18T00:01:00Z",
    )


def test_multi_agent_legacy_merge_gate_uses_attributed_actor(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)

    result = _reconcile(registry, state, agent_id=ACTOR_AGENT)

    assert result["write_performed"] is True
    assert result["todo_completion"]["status"] == "done"
    assert result["todo_completion"]["mutation_authority"] == {
        "schema_version": "todo_mutation_authority_v0",
        "command": "complete",
        "mode": "registered_peer_actor",
        "actor_agent_id": ACTOR_AGENT,
        "todo_id": "todo_merge_gate_2298",
        "claim_owner": None,
        "registered_agent_count": 2,
    }
    assert "status=done" in state.read_text(encoding="utf-8")


def test_multi_agent_legacy_merge_gate_without_actor_is_atomic(tmp_path: Path) -> None:
    registry, state = _write_fixture(tmp_path)
    before = state.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="requires --agent-id"):
        _reconcile(registry, state, agent_id=None)

    assert state.read_text(encoding="utf-8") == before
