from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.configure_goal import configure_goal
from loopx.control_plane.scheduler.execution_context import (
    GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
)
from loopx.control_plane.testing.quota_fixtures import (
    quota_status_payload,
    quota_todo_item,
)
from loopx.quota import build_quota_should_run


GOAL_ID = "paused-quota-precedence-fixture"
AGENT_ID = "codex-paused-agent"


def _paused_status(*, required_capabilities: list[str] | None = None) -> dict:
    todo = quota_todo_item(
        todo_id="todo_paused_delivery",
        title="Advance paused delivery.",
        claimed_by=AGENT_ID,
        required_capabilities=required_capabilities or [],
    )
    return quota_status_payload(
        goal_id=GOAL_ID,
        status="active",
        recommended_action="Advance the delivery.",
        agent_todo_items=[todo],
        quota_state="paused",
        quota_extra={"compute": 0, "reason": "paused fixture"},
        coordination={
            "agent_model": "peer_v1",
            "registered_agents": [AGENT_ID],
        },
    )


def _assert_authoritatively_paused(payload: dict) -> None:
    assert payload["state"] == "paused"
    assert payload["decision"] == "skip"
    assert payload["should_run"] is False
    assert payload["effective_action"] == "quota_skip"
    assert payload["actionable_by_codex"] is False
    assert payload["self_repair_allowed"] is False
    assert payload["capability_repair_allowed"] is False
    assert payload["workspace_repair_allowed"] is False
    assert payload["heartbeat_recommendation"]["recommended_mode"] == "quota_paused"
    assert payload["heartbeat_recommendation"]["notify"] == "DONT_NOTIFY"
    assert payload["execution_obligation"]["must_attempt_work"] is False
    assert payload["interaction_contract"]["mode"] == "skip"
    assert payload["scheduler_hint"]["action"] != "run_now"


def test_paused_quota_preempts_capability_bridge_repair() -> None:
    payload = build_quota_should_run(
        _paused_status(required_capabilities=["network"]),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        available_capabilities=[],
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )

    _assert_authoritatively_paused(payload)
    assert "capability_gate" not in payload


def test_paused_quota_preempts_workspace_repair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "loopx.quota.build_agent_workspace_guard",
        lambda *args, **kwargs: {
            "schema_version": "agent_workspace_guard_v1",
            "reason": "workspace fixture requires relocation",
            "required_action": "rerun from the assigned worktree",
        },
    )

    payload = build_quota_should_run(
        _paused_status(),
        goal_id=GOAL_ID,
        agent_id=AGENT_ID,
        scheduler_execution_context=GENERIC_CLI_OUTER_CONTROLLER_SCHEDULER_CONTEXT,
    )

    _assert_authoritatively_paused(payload)
    assert "workspace_guard" not in payload


def test_configure_goal_accepts_zero_compute_as_pause(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "goals": [
                    {
                        "id": GOAL_ID,
                        "repo": str(tmp_path),
                        "quota": {"compute": 1.0, "window_hours": 24},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = configure_goal(
        registry_path=registry,
        goal_id=GOAL_ID,
        quota_compute=0,
        execute=True,
    )

    assert result["written"] is True
    stored = json.loads(registry.read_text(encoding="utf-8"))
    assert stored["goals"][0]["quota"]["compute"] == 0


def test_configure_goal_rejects_negative_compute(tmp_path: Path) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps({"goals": [{"id": GOAL_ID, "repo": str(tmp_path)}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="greater than or equal to 0"):
        configure_goal(
            registry_path=registry,
            goal_id=GOAL_ID,
            quota_compute=-0.1,
            execute=False,
        )
