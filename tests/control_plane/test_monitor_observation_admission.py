from __future__ import annotations

from pathlib import Path

from tests.control_plane.test_quota_settlement_cli import (
    AGENT_ID,
    DUE_MONITOR_TODO_ID,
    GOAL_ID,
    TODO_ID,
    _append_newly_due_monitor,
    _classification_count,
    _run_cli,
    _spend_run_count,
    _write_fixture,
)


def test_receipt_bound_advancement_allows_one_auxiliary_due_monitor_receipt(
    tmp_path: Path,
) -> None:
    project, runtime, registry_path = _write_fixture(tmp_path)
    turn_instance_id = "turn-advancement-with-auxiliary-monitor"
    guard_args = (
        "quota",
        "should-run",
        "--codex-app",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--turn-instance-id",
        turn_instance_id,
        "--scan-path",
        str(project),
    )
    first_rc, first = _run_cli(registry_path, runtime, *guard_args)
    assert first_rc == 0, first
    assert first["heartbeat_receipt"]["settlement_identity"]["todo_id"] == TODO_ID

    _append_newly_due_monitor(project)
    capability_args = (
        "--available-capability",
        "network",
        "--available-capability",
        "external_evidence_poll",
    )
    replay_rc, replay = _run_cli(
        registry_path,
        runtime,
        *guard_args,
        *capability_args,
    )
    assert replay_rc == 0, replay
    assert replay["selected_todo"]["todo_id"] == TODO_ID
    assert "due_monitor_context" in replay["work_lane_contract"]["reason_codes"]

    poll_args = (
        "quota",
        "monitor-poll",
        "--codex-app",
        "--goal-id",
        GOAL_ID,
        "--agent-id",
        AGENT_ID,
        "--turn-instance-id",
        turn_instance_id,
        "--todo-id",
        DUE_MONITOR_TODO_ID,
        "--target-key",
        "due-monitor-fixture",
        "--result-hash",
        "unchanged-auxiliary-monitor",
        *capability_args,
        "--execute",
        "--scan-path",
        str(project),
    )
    poll_rc, poll = _run_cli(registry_path, runtime, *poll_args)
    poll_replay_rc, poll_replay = _run_cli(
        registry_path,
        runtime,
        *poll_args,
    )

    assert poll_rc == 0, poll
    assert poll["settlement_todo_id"] == TODO_ID
    assert poll["todo_id"] == DUE_MONITOR_TODO_ID
    assert poll["before"]["selected_todo"]["todo_id"] == TODO_ID
    assert poll["after"]["selected_todo"]["todo_id"] == TODO_ID
    assert poll["material_change"] is False
    assert poll_replay_rc == 0, poll_replay
    assert poll_replay["replayed"] is True
    assert _classification_count(runtime, "quota_monitor_poll") == 1
    assert _spend_run_count(runtime) == 0

    final_guard_rc, final_guard = _run_cli(
        registry_path,
        runtime,
        *guard_args,
        *capability_args,
    )
    assert final_guard_rc == 0, final_guard
    assert final_guard["selected_todo"]["todo_id"] == TODO_ID
    assert final_guard["heartbeat_receipt"]["settlement_identity"]["todo_id"] == (
        TODO_ID
    )
