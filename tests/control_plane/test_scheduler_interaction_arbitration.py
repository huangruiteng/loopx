from __future__ import annotations

from copy import deepcopy

import pytest

from loopx.control_plane.scheduler.arbitration import (
    SchedulerDisposition,
    build_scheduler_arbitration,
)
from loopx.control_plane.scheduler.scheduler_hint import build_scheduler_hint
from loopx.control_plane.work_items.interaction_contract import (
    build_interaction_contract,
)


AGENT_SCOPE_ACTIONS = {
    "agent_scope_exhausted",
    "agent_scope_wait",
    "reassignment_required",
    "successor_replan_required",
}


def _payload(
    *,
    mode: str,
    should_run: bool,
    user_required: bool,
    must_attempt: bool,
    delivery_allowed: bool,
    quiet_noop_allowed: bool,
) -> dict:
    return {
        "goal_id": "scheduler-authority-test",
        "agent_identity": {"agent_id": "codex-quality-qualification"},
        "should_run": should_run,
        "effective_action": mode,
        "recommended_action": "Exercise the final interaction decision.",
        "heartbeat_recommendation": {
            "recommended_mode": mode,
            "notify": "NOTIFY" if user_required else "DONT_NOTIFY",
            "spend_policy": "spend only after validated writeback",
        },
        "execution_obligation": {
            "must_attempt_work": should_run,
            "spend_policy": "spend only after validated writeback",
        },
        "automation_liveness": {
            "automation_action": "execute_bounded_work" if should_run else "keep_active_quiet",
            "spend_policy": "spend only after validated writeback",
        },
        "interaction_contract": {
            "schema_version": "loopx_interaction_contract_v0",
            "mode": mode,
            "user_channel": {"action_required": user_required, "notify": "DONT_NOTIFY"},
            "agent_channel": {
                "must_attempt": must_attempt,
                "delivery_allowed": delivery_allowed,
                "quiet_noop_allowed": quiet_noop_allowed,
            },
            "cli_channel": {"next_cli_actions": [], "spend_allowed_now": False},
        },
    }


@pytest.mark.parametrize(
    ("name", "payload", "disposition", "cadence"),
    [
        (
            "blocking-gate",
            _payload(
                mode="user_gate",
                should_run=False,
                user_required=True,
                must_attempt=False,
                delivery_allowed=False,
                quiet_noop_allowed=False,
            ),
            SchedulerDisposition.HUMAN_GATE,
            "human_gate",
        ),
        (
            "nonblocking-notice-with-work",
            _payload(
                mode="bounded_delivery_with_user_notice",
                should_run=True,
                user_required=True,
                must_attempt=True,
                delivery_allowed=True,
                quiet_noop_allowed=False,
            ),
            SchedulerDisposition.ACTIVE_WORK,
            "active_work",
        ),
        (
            "repair-only",
            _payload(
                mode="automation_prompt_upgrade",
                should_run=False,
                user_required=False,
                must_attempt=True,
                delivery_allowed=False,
                quiet_noop_allowed=False,
            ),
            SchedulerDisposition.ACTIVE_WORK,
            "active_work",
        ),
        (
            "mapped-compatibility",
            _payload(
                mode="mapped_noop_if_unchanged",
                should_run=True,
                user_required=False,
                must_attempt=False,
                delivery_allowed=False,
                quiet_noop_allowed=True,
            ),
            SchedulerDisposition.UNCHANGED_WAIT,
            "unchanged_noop",
        ),
        (
            "successor-replan",
            _payload(
                mode="successor_replan_required",
                should_run=True,
                user_required=False,
                must_attempt=True,
                delivery_allowed=False,
                quiet_noop_allowed=False,
            ),
            SchedulerDisposition.ACTIVE_WORK,
            "active_work",
        ),
        (
            "terminal-no-followup",
            _payload(
                mode="terminal_no_followup",
                should_run=False,
                user_required=False,
                must_attempt=False,
                delivery_allowed=False,
                quiet_noop_allowed=True,
            ),
            SchedulerDisposition.TERMINAL_STOP,
            "terminal_no_followup",
        ),
    ],
)
def test_interaction_contract_drives_scheduler(
    name: str,
    payload: dict,
    disposition: SchedulerDisposition,
    cadence: str,
) -> None:
    arbitration = build_scheduler_arbitration(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )
    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert arbitration.ok, (name, arbitration)
    assert arbitration.disposition == disposition, (name, arbitration)
    assert hint["cadence_class"] == cadence, (name, hint)
    assert hint["reason_code"] == arbitration.reason_code, (name, hint)


def test_raw_should_run_cannot_override_blocking_gate() -> None:
    payload = _payload(
        mode="user_gate",
        should_run=True,
        user_required=True,
        must_attempt=False,
        delivery_allowed=False,
        quiet_noop_allowed=False,
    )

    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["action"] == "backoff_waiting_for_user"
    assert hint["cadence_class"] == "human_gate"
    assert "consistency_error" not in hint


def test_raw_should_run_false_cannot_silently_cancel_final_contract_delivery() -> None:
    payload = _payload(
        mode="bounded_delivery",
        should_run=False,
        user_required=False,
        must_attempt=True,
        delivery_allowed=True,
        quiet_noop_allowed=False,
    )

    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["cadence_class"] == "active_work"
    assert hint["action"] == "run_now"
    assert "consistency_error" not in hint


def test_branch_order_mutation_is_killed_by_final_contract() -> None:
    payload = _payload(
        mode="user_gate",
        should_run=False,
        user_required=True,
        must_attempt=False,
        delivery_allowed=False,
        quiet_noop_allowed=False,
    )
    mutated = deepcopy(payload)
    mutated["automation_liveness"]["automation_action"] = "execute_bounded_work"
    mutated["execution_obligation"]["must_attempt_work"] = True

    hint = build_scheduler_hint(
        mutated,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["cadence_class"] == "human_gate"
    assert hint["action"] != "run_now"


def test_raw_terminal_liveness_cannot_override_active_final_contract() -> None:
    payload = _payload(
        mode="bounded_delivery",
        should_run=True,
        user_required=False,
        must_attempt=True,
        delivery_allowed=True,
        quiet_noop_allowed=False,
    )
    payload["automation_liveness"]["automation_action"] = (
        "stop_terminal_no_followup"
    )

    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["action"] == "run_now"
    assert hint["cadence_class"] == "active_work"


def test_terminal_state_is_projected_into_final_interaction_contract() -> None:
    contract = build_interaction_contract(
        {
            "goal_id": "terminal-contract-test",
            "state": "terminal_no_followup",
            "effective_action": "terminal_no_followup",
            "should_run": False,
            "normal_delivery_allowed": False,
            "recovery_delivery_allowed": False,
            "self_repair_allowed": False,
            "heartbeat_recommendation": {"notify": "DONT_NOTIFY"},
            "execution_obligation": {"must_attempt_work": False},
        }
    )

    assert contract["mode"] == "terminal_no_followup"
    assert contract["user_channel"]["action_required"] is False
    assert contract["agent_channel"]["must_attempt"] is False
    assert contract["agent_channel"]["delivery_allowed"] is False
    assert contract["agent_channel"]["quiet_noop_allowed"] is True
    assert contract["cli_channel"]["spend_after_validation"] is False


def test_terminal_contract_with_open_action_fails_closed() -> None:
    payload = _payload(
        mode="terminal_no_followup",
        should_run=False,
        user_required=True,
        must_attempt=False,
        delivery_allowed=False,
        quiet_noop_allowed=False,
    )

    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["action"] == "repair_interaction_contract_projection"
    assert (
        "interaction_contract.terminal_conflicts_with_open_action"
        in hint["consistency_error"]["errors"]
    )


def test_structurally_invalid_contract_fails_closed() -> None:
    payload = _payload(
        mode="bounded_delivery",
        should_run=True,
        user_required=False,
        must_attempt=True,
        delivery_allowed=True,
        quiet_noop_allowed=False,
    )
    del payload["interaction_contract"]["agent_channel"]["quiet_noop_allowed"]

    hint = build_scheduler_hint(
        payload,
        agent_scope_frontier_actions=AGENT_SCOPE_ACTIONS,
    )

    assert hint["cadence_class"] == "control_plane_repair"
    assert (
        "interaction_contract.agent_channel.quiet_noop_allowed_must_be_boolean"
        in hint["consistency_error"]["errors"]
    )
