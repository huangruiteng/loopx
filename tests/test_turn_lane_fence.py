"""One executing bounded Turn per Turn lane.

The fence is a process-level lock, so these tests hold the lane the same way a
running Turn does and assert what the second Turn is told. Admission and release
after a settled Turn are covered end to end by the public dsh smokes, which run
one Turn and then its replay through the same entry.
"""

from __future__ import annotations

from pathlib import Path

from loopx.control_plane.turn_driver.executor import run_loopx_turn_once
from loopx.control_plane.turn_driver.lane_fence import (
    REMEDY_WAIT_FOR_IN_FLIGHT_TURN,
    TURN_LANE_IN_FLIGHT,
    TURN_LANE_OPERATION,
    turn_lane_holder_readback,
    turn_lane_singleflight,
    turn_lane_target,
)

GOAL_ID = "lane-fence-goal"
AGENT_ID = "lane-fence-agent"


def _plan(*, agent_id: str = AGENT_ID) -> dict:
    return {
        "host": {"kind": "dsh", "execution_mode": "isolated-headless"},
        "route": {"kind": "ready_for_host", "would_invoke_host": True},
        "turn_envelope": {"agent_id": agent_id, "goal_id": GOAL_ID},
        "transaction": {"turn_key": "sha256:" + "1" * 64},
    }


def _execute(tmp_path: Path, *, execute: bool = True, plan: dict | None = None) -> dict:
    return run_loopx_turn_once(
        plan or _plan(),
        host_argv=["python3", "-c", "raise SystemExit(0)"],
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id=GOAL_ID,
        timeout_seconds=1.0,
        execute=execute,
    )


def test_a_second_executing_turn_refuses_while_one_holds_the_lane(
    tmp_path: Path,
) -> None:
    with turn_lane_singleflight(
        runtime_root=tmp_path / "runtime", goal_id=GOAL_ID, plan=_plan()
    ) as held:
        assert held is not None
        payload = _execute(tmp_path)

    assert payload["ok"] is False
    assert payload["status"] == "unavailable"
    assert payload["reason"] == TURN_LANE_IN_FLIGHT
    assert payload["remediation"] == [REMEDY_WAIT_FOR_IN_FLIGHT_TURN]
    assert payload["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    assert payload["quota_slot_spend_count"] == 0
    # The refusal names the holder, so an operator can tell what to wait for.
    assert payload["in_flight"]["agent_id"] == AGENT_ID
    assert payload["in_flight"]["operation"] == TURN_LANE_OPERATION
    assert isinstance(payload["in_flight"]["pid"], int)
    assert payload["in_flight"]["acquired_at"]
    # A refusal is a readback, not an invocation of the planned host.
    assert payload["host"] == {"executable": "not_invoked", "kind": "dsh"}


def test_a_preview_never_takes_the_lane(tmp_path: Path) -> None:
    with turn_lane_singleflight(
        runtime_root=tmp_path / "runtime", goal_id=GOAL_ID, plan=_plan()
    ) as held:
        assert held is not None
        payload = _execute(tmp_path, execute=False)

    assert payload["ok"] is True
    assert payload["status"] == "preview"


def test_the_lane_is_goal_and_agent_scoped(tmp_path: Path) -> None:
    root = tmp_path / "runtime"
    same_lane = turn_lane_target(runtime_root=root, goal_id=GOAL_ID, plan=_plan())
    other_agent = turn_lane_target(
        runtime_root=root, goal_id=GOAL_ID, plan=_plan(agent_id="another-agent")
    )
    other_goal = turn_lane_target(
        runtime_root=root, goal_id="another-goal", plan=_plan()
    )

    assert same_lane == turn_lane_target(
        runtime_root=root, goal_id=GOAL_ID, plan=_plan()
    )
    assert len({same_lane, other_agent, other_goal}) == 3
    assert AGENT_ID in same_lane.name
    # A plan without an agent identity still gets a lane instead of no fence.
    unattributed = turn_lane_target(
        runtime_root=root, goal_id=GOAL_ID, plan={"turn_envelope": {}}
    )
    assert unattributed not in {same_lane, other_agent, other_goal}


def test_the_holder_readback_stays_public_safe(tmp_path: Path) -> None:
    target = turn_lane_target(
        runtime_root=tmp_path / "runtime", goal_id=GOAL_ID, plan=_plan()
    )
    with turn_lane_singleflight(
        runtime_root=tmp_path / "runtime", goal_id=GOAL_ID, plan=_plan()
    ):
        holder = turn_lane_holder_readback(target)

    assert holder["agent_id"] == AGENT_ID
    assert holder["operation"] == TURN_LANE_OPERATION
    assert isinstance(holder["pid"], int)
    assert set(holder) == {"agent_id", "operation", "pid", "acquired_at"}
    # The private lock identity and the runtime path never leave the process.
    assert str(tmp_path) not in str(holder)
    assert turn_lane_holder_readback(tmp_path / "absent.lane") == {}
