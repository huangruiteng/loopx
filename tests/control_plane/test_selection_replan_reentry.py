"""A deferred selection must expose a runnable recovery before settlement."""
import shlex

import pytest

from test_quota_settlement_cli import (
    AGENT_ID, GOAL_ID, SELECTED_REPLAN_TODO_ID, TODO_ID,
    _configure_autonomous_replan_fixture, _configure_selected_todo_replan_fixture,
    _configure_selectable_alternative, _heartbeat_receipt_count, _projected_cli_args,
    _run_cli, _run_generated_cli, _spend_run_count, _write_fixture,
)


@pytest.mark.parametrize("binding", ["todo", "autonomous_replan"])
def test_deferred_selection_recovers_same_turn_and_settles_once(tmp_path, binding):
    project, runtime, registry = _write_fixture(tmp_path)
    _configure_selectable_alternative(project)
    turn = "turn-selection-preempted"
    guard = ("quota", "should-run", "--codex-app", "--goal-id", GOAL_ID,
             "--agent-id", AGENT_ID, "--turn-instance-id", turn, "--scan-path", str(project))
    rc, first = _run_cli(registry, runtime, *guard)
    assert rc == 0 and first["decision"] == "run"
    assert first["interaction_contract"]["cli_channel"]["selection_required"]
    assert "settlement_identity" not in first["heartbeat_receipt"]
    if binding == "todo":
        _configure_selected_todo_replan_fixture(project, registry)
        selected_id = SELECTED_REPLAN_TODO_ID
    else:
        _configure_autonomous_replan_fixture(project, runtime, registry)
        selected_id = TODO_ID
    rc, deferred = _run_cli(registry, runtime, *guard, "--todo-id", selected_id)
    assert rc == 1 and not deferred["should_run"]
    assert deferred["heartbeat_receipt"]["event_id"] == first["heartbeat_receipt"]["event_id"]
    assert _heartbeat_receipt_count(runtime, turn) == 1
    channel = deferred["interaction_contract"]["cli_channel"]
    assert "settlement_plan" not in channel
    assert "replan_settlement_contract" not in channel
    [command] = channel["next_cli_actions"]
    assert "rerun quota should-run" in deferred["recommended_action"]
    assert deferred["execution_obligation"]["reason"] == deferred["recommended_action"]
    assert deferred["interaction_contract"]["agent_channel"]["primary_action"] == command
    rc, envelope = _run_cli(
        registry, runtime, *guard, "--todo-id", selected_id, "--turn-envelope"
    )
    assert rc == 1, envelope
    assert envelope["replan_action_packet"] is None
    assert envelope["action"]["primary_action"].startswith("loopx ")
    assert not envelope["action"]["must_attempt"]
    assert not envelope["action"]["delivery_allowed"]
    [recovery_preview] = envelope["writeback"]["next_cli_actions"]
    assert recovery_preview.startswith("loopx ")
    assert not envelope["writeback"]["spend_after_validation"]
    assert _heartbeat_receipt_count(runtime, turn) == 1
    argv = shlex.split(command)
    assert argv[argv.index("--turn-instance-id") + 1] == turn
    assert "--todo-id" not in argv and "--replan-obligation-id" not in argv
    assert "should-run" in argv and "--codex-app" in argv
    assert not deferred["interaction_contract"]["agent_channel"]["must_attempt"]
    rc, resumed = _run_generated_cli(command, registry_path=registry)
    assert rc == 0, resumed
    receipt = resumed["heartbeat_receipt"]
    assert receipt["status"] == "upgraded"
    identity = receipt["settlement_identity"]
    assert identity["turn_instance_id"] == turn
    assert ("todo_id" in identity) == (binding == "todo")
    assert _heartbeat_receipt_count(runtime, turn) == 2
    cli = resumed["interaction_contract"]["cli_channel"]
    assert cli["settlement_plan"]["identity"] == identity
    refresh = next(c for c in cli["next_cli_actions"] if "refresh-state" in c)
    for key, value in {"<advanced|blocked|exploration_exhausted|no_followup>": "advanced",
                       "<surface-id>": "accepted-artifact", "<hypothesis-id>": "adoption",
                       "<probe-kind>": "acceptance", "<evidence-id>": "evidence:readback"}.items():
        refresh = refresh.replace(key, value)
    rc, result = _run_cli(registry, runtime, *_projected_cli_args(refresh, turn_instance_id=turn))
    assert rc == 0, result
    assert result["settlement_result"]["ok"]
    spend = next(c for c in cli["next_cli_actions"] if "spend-slot" in c)
    spend_args = _projected_cli_args(spend, turn_instance_id=turn)
    for replay in (False, True):
        rc, result = _run_cli(registry, runtime, *spend_args, "--scan-path", str(project))
        assert rc == 0, result
        assert result["settlement_result"]["ok"]
        if replay:
            assert result["idempotent_replay"] and not result["appended"]
    assert _spend_run_count(runtime) == 1
    rc, settled = _run_cli(registry, runtime, *guard)
    assert rc == 0
    if binding == "autonomous_replan":
        assert settled["effective_action"] == "heartbeat_settled_skip"
    assert settled["heartbeat_receipt"]["settlement_identity"] == identity
    rc, conflict = _run_cli(registry, runtime, *guard, "--todo-id", "todo_another_selection")
    assert rc == 1 and conflict["ok"] is False
    assert _heartbeat_receipt_count(runtime, turn) == 2
    assert _spend_run_count(runtime) == 1
