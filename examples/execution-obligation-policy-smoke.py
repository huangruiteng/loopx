#!/usr/bin/env python3
"""Smoke-test the extracted execution-obligation policy helper."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.work_items.execution_obligation import build_execution_obligation  # noqa: E402


def obligation(
    *,
    should_run: bool = True,
    effective_action: str = "normal_run",
    recommendation: dict | None = None,
    work_lane_contract: dict | None = None,
    external_evidence_observation: dict | None = None,
    successor_replan_mode: str = "successor_replan_required",
) -> dict:
    return build_execution_obligation(
        should_run=should_run,
        effective_action=effective_action,
        heartbeat_recommendation=recommendation or {},
        work_lane_contract=work_lane_contract,
        external_evidence_observation=external_evidence_observation,
        successor_replan_mode=successor_replan_mode,
    )


def assert_exact_mode(
    name: str,
    payload: dict,
    *,
    kind: str,
    minimum: str | None,
    contract: str | None = None,
    delivery_allowed: bool | None = None,
) -> None:
    assert payload["kind"] == kind, (name, payload)
    assert payload["must_attempt_work"] is True, (name, payload)
    assert payload["notify_is_execution_gate"] is False, (name, payload)
    if minimum is None:
        assert "minimum" not in payload, (name, payload)
    else:
        assert payload["minimum"] == minimum, (name, payload)
    if contract is not None:
        assert payload["contract"] == contract, (name, payload)
    if delivery_allowed is not None:
        assert payload["delivery_allowed"] is delivery_allowed, (name, payload)


def main() -> int:
    peer_workspace = obligation(
        recommendation={
            "recommended_mode": "repair_agent_workspace",
            "spend_policy": "no spend until relocated",
        }
    )
    assert_exact_mode(
        "peer-agent-workspace",
        peer_workspace,
        kind="agent_workspace_repair",
        minimum="one_workspace_move_then_guard_rerun",
        contract="agent_workspace_guard",
        delivery_allowed=False,
    )
    assert peer_workspace["spend_policy"] == "no spend until relocated", peer_workspace

    evidence = obligation(
        should_run=False,
        external_evidence_observation={
            "required": True,
            "spend_policy": "no spend until observed",
        },
    )
    assert_exact_mode(
        "external-evidence",
        evidence,
        kind="external_evidence_observation_required",
        minimum="one_read_only_observation_or_compact_blocker",
        contract="external_evidence_observation",
        delivery_allowed=False,
    )
    assert evidence["spend_policy"] == "no spend until observed", evidence

    quiet = obligation(
        recommendation={"stop_if_unchanged": True},
    )
    assert quiet == {
        "must_attempt_work": False,
        "kind": "quiet_noop_if_unchanged",
        "notify_is_execution_gate": False,
        "reason": (
            "this mode allows a quiet no-op only after confirming the current state "
            "source is unchanged and no concrete safe handoff exists"
        ),
    }, quiet

    replan = obligation(
        recommendation={
            "recommended_mode": "autonomous_replan_required",
            "replan_obligation": {"stall_threshold": 6},
        }
    )
    assert_exact_mode(
        "autonomous-replan",
        replan,
        kind="autonomous_replan_required",
        minimum="one_bounded_replan_segment",
    )
    assert replan["stall_threshold"] == 6, replan

    empty_frontier_replan = obligation(
        recommendation={
            "recommended_mode": "autonomous_replan_required",
            "replan_obligation": {
                "stall_threshold": 2,
                "agent_todo_writeback_required": True,
            },
        }
    )
    assert_exact_mode(
        "empty-frontier-autonomous-replan",
        empty_frontier_replan,
        kind="autonomous_replan_required",
        minimum="one_bounded_replan_with_agent_todo_writeback",
        contract="autonomous_replan_agent_todo_writeback",
    )
    assert "create a concrete runnable agent todo" in empty_frontier_replan[
        "contract_obligation"
    ], empty_frontier_replan

    successor = obligation(
        recommendation={
            "recommended_mode": "custom_successor_mode",
            "spend_policy": "spend after projection repair",
        },
        successor_replan_mode="custom_successor_mode",
    )
    assert_exact_mode(
        "successor-replan",
        successor,
        kind="custom_successor_mode",
        minimum="one_successor_replan_or_no_followup_writeback",
        contract="deferred_resume_projection",
        delivery_allowed=False,
    )
    assert successor["spend_policy"] == "spend after projection repair", successor

    state_gap = obligation(
        recommendation={
            "recommended_mode": "repair_state_projection_gap",
            "spend_policy": "spend after projection repair",
        }
    )
    assert_exact_mode(
        "state-projection-gap",
        state_gap,
        kind="state_projection_gap_repair",
        minimum="one_replan_or_todo_expansion_or_blocker_writeback_segment",
        contract="state_projection_gap",
        delivery_allowed=False,
    )

    boundary = obligation(
        recommendation={"recommended_mode": "repair_boundary_projection"}
    )
    assert_exact_mode(
        "boundary-projection",
        boundary,
        kind="boundary_projection_repair",
        minimum="one_boundary_projection_or_blocker_writeback_segment",
        contract="goal_boundary.write_scope",
        delivery_allowed=False,
    )

    capability = obligation(
        recommendation={"recommended_mode": "repair_capability_bridge"}
    )
    assert_exact_mode(
        "capability-bridge",
        capability,
        kind="capability_bridge_repair",
        minimum="one_bridge_or_environment_repair_or_blocker_writeback_segment",
        contract="capability_gate",
        delivery_allowed=False,
    )

    work_lane = obligation(
        recommendation={"recommended_mode": "follow_work_lane_contract"},
        work_lane_contract={
            "obligation": "advance_one_bounded_segment",
            "must_attempt_work": True,
        },
    )
    assert work_lane == {
        "must_attempt_work": True,
        "kind": "work_lane_contract",
        "contract": "work_lane_contract",
        "contract_obligation": "advance_one_bounded_segment",
        "notify_is_execution_gate": False,
        "reason": (
            "work_lane_contract.obligation is the machine execution contract; "
            "heartbeat_recommendation is explanatory"
        ),
    }, work_lane

    generic_run = obligation(
        recommendation={"recommended_mode": "steering_audit_then_one_step"},
        effective_action="normal_run",
    )
    assert generic_run == {
        "must_attempt_work": True,
        "kind": "normal_run",
        "minimum": "one_bounded_segment",
        "notify_is_execution_gate": False,
        "reason": (
            "should_run=true means a Codex-actionable turn exists; heartbeat notify "
            "only controls whether to interrupt the user"
        ),
    }, generic_run

    generic_skip = obligation(
        should_run=False,
        effective_action="quota_wait",
        recommendation={"recommended_mode": "wait"},
    )
    assert generic_skip == {
        "must_attempt_work": False,
        "kind": "quota_wait",
        "notify_is_execution_gate": False,
        "reason": (
            "should_run=false blocks delivery unless an explicit safe-bypass or "
            "self-repair action is exposed"
        ),
    }, generic_skip

    print("execution-obligation-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
