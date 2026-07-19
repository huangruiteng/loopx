from __future__ import annotations

import pytest

from loopx.control_plane.scheduler.state import rrule_for_minutes
from loopx.control_plane.scheduler.state_transition_rules import (
    SchedulerCadenceTransition,
    SchedulerHostTransition,
    decide_scheduler_cadence_transition,
    decide_scheduler_host_transition,
)


RESET_TOKEN = "reset-token"
IDENTITY_SIGNATURE = "identity-signature"
TARGET_15 = rrule_for_minutes(15)
TARGET_30 = rrule_for_minutes(30)
HOST_60 = rrule_for_minutes(60)


def _scheduler_state(
    *,
    progression_index: object = 1,
    last_applied_rrule: str = TARGET_30,
    reset_token: str = RESET_TOKEN,
    identity_signature: str = IDENTITY_SIGNATURE,
) -> dict:
    return {
        "progression_index": progression_index,
        "last_applied_rrule": last_applied_rrule,
        "reset_token": reset_token,
        "identity_signature": identity_signature,
    }


CADENCE_CASES = [
    {
        "id": "missing_state_starts_at_initial",
        "state": {},
        "expected": (0, "missing", SchedulerCadenceTransition.INITIAL, False),
    },
    {
        "id": "changed_identity_resets_to_initial",
        "state": _scheduler_state(reset_token="old-token"),
        "expected": (
            0,
            "reset_required",
            SchedulerCadenceTransition.IDENTITY_RESET,
            False,
        ),
    },
    {
        "id": "unacknowledged_failure_retries_current_index",
        "state": _scheduler_state(last_applied_rrule=TARGET_15),
        "has_failures": True,
        "expected": (
            1,
            "same_identity",
            SchedulerCadenceTransition.RETRY_UNACKNOWLEDGED_FAILURE,
            False,
        ),
    },
    {
        "id": "acknowledged_failure_can_advance_after_interval",
        "state": _scheduler_state(),
        "has_failures": True,
        "expected": (
            2,
            "same_identity",
            SchedulerCadenceTransition.ADVANCE_AFTER_INTERVAL,
            True,
        ),
    },
    {
        "id": "active_work_holds_initial_cadence",
        "state": _scheduler_state(progression_index=2, last_applied_rrule=HOST_60),
        "advance": False,
        "expected": (
            0,
            "same_identity",
            SchedulerCadenceTransition.HOLD_ACTIVE_INITIAL,
            True,
        ),
    },
    {
        "id": "settled_cadence_holds_until_interval_elapsed",
        "state": _scheduler_state(),
        "elapsed": False,
        "expected": (
            1,
            "same_identity",
            SchedulerCadenceTransition.HOLD_UNTIL_INTERVAL,
            True,
        ),
    },
    {
        "id": "elapsed_terminal_index_stays_capped",
        "state": _scheduler_state(progression_index=2, last_applied_rrule=HOST_60),
        "expected": (
            2,
            "same_identity",
            SchedulerCadenceTransition.ADVANCE_AFTER_INTERVAL,
            True,
        ),
    },
    {
        "id": "invalid_failed_index_recovers_at_initial",
        "state": _scheduler_state(
            progression_index="invalid", last_applied_rrule=TARGET_15
        ),
        "has_failures": True,
        "expected": (
            0,
            "same_identity",
            SchedulerCadenceTransition.RETRY_UNACKNOWLEDGED_FAILURE,
            False,
        ),
    },
]


@pytest.mark.parametrize(
    "case", CADENCE_CASES, ids=[case["id"] for case in CADENCE_CASES]
)
def test_scheduler_cadence_transition_table(case: dict) -> None:
    decision = decide_scheduler_cadence_transition(
        [15, 30, 60],
        scheduler_state=case["state"],
        reset_token=RESET_TOKEN,
        identity_signature=IDENTITY_SIGNATURE,
        advance_same_identity=case.get("advance", True),
        applied_interval_elapsed=case.get("elapsed", True),
        has_host_update_failures=case.get("has_failures", False),
    )

    assert (
        decision.current_index,
        decision.state_status,
        decision.transition,
        decision.current_cadence_acknowledged,
    ) == case["expected"]


def _failure(*, target: str, host: str) -> dict:
    return {"target_rrule": target, "observed_host_rrule": host}


HOST_CASES = [
    {
        "id": "settled_same_identity",
        "already_applied": True,
        "expected": SchedulerHostTransition.SETTLED,
    },
    {
        "id": "matching_host_repairs_identity_with_ack",
        "state_status": "reset_required",
        "already_applied": True,
        "expected": SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED,
    },
    {
        "id": "matching_host_new_progression_requires_ack",
        "already_applied": True,
        "persisted": False,
        "expected": SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED,
    },
    {
        "id": "matching_host_acks_current_target_failure",
        "already_applied": True,
        "failures": [_failure(target=TARGET_15, host=HOST_60)],
        "expected": SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED,
    },
    {
        "id": "unrelated_failure_does_not_unsettle_matching_host",
        "already_applied": True,
        "failures": [_failure(target=TARGET_30, host=HOST_60)],
        "expected": SchedulerHostTransition.SETTLED,
    },
    {
        "id": "drift_requires_apply",
        "observed": HOST_60,
        "effective": HOST_60,
        "expected": SchedulerHostTransition.APPLY_REQUIRED,
    },
    {
        "id": "exact_failed_pair_suppresses_repeat",
        "observed": HOST_60,
        "effective": HOST_60,
        "recorded": _failure(target=TARGET_15, host=HOST_60),
        "expected": SchedulerHostTransition.RECORDED_FAILURE_SUPPRESSED,
    },
    {
        "id": "different_failed_target_does_not_suppress",
        "observed": HOST_60,
        "effective": HOST_60,
        "recorded": _failure(target=TARGET_30, host=HOST_60),
        "expected": SchedulerHostTransition.APPLY_REQUIRED,
    },
    {
        "id": "changed_host_invalidates_failed_pair",
        "observed": TARGET_30,
        "effective": TARGET_30,
        "recorded": _failure(target=TARGET_15, host=HOST_60),
        "expected": SchedulerHostTransition.APPLY_REQUIRED,
    },
    {
        "id": "persisted_match_without_host_observation_reapplies_after_reset",
        "state_status": "reset_required",
        "observed": "",
        "effective": TARGET_15,
        "already_applied": True,
        "expected": SchedulerHostTransition.APPLY_REQUIRED,
    },
]


@pytest.mark.parametrize("case", HOST_CASES, ids=[case["id"] for case in HOST_CASES])
def test_scheduler_host_transition_table(case: dict) -> None:
    observed = case.get("observed", TARGET_15)
    decision = decide_scheduler_host_transition(
        state_status=case.get("state_status", "same_identity"),
        observed_host_rrule=observed,
        effective_host_rrule=case.get("effective", observed),
        current_rrule=TARGET_15,
        current_rrule_already_applied=case.get("already_applied", False),
        scheduler_state_acknowledges_current_rrule=case.get("persisted", True),
        all_host_update_failures=case.get("failures", []),
        recorded_host_failure=case.get("recorded"),
    )

    assert decision.transition == case["expected"]
    assert decision.apply_needed is (
        decision.transition == SchedulerHostTransition.APPLY_REQUIRED
    )
    assert decision.ack_needed is (
        decision.transition
        in {
            SchedulerHostTransition.APPLY_REQUIRED,
            SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED,
        }
    )


def test_unrelated_failure_order_does_not_change_host_transition() -> None:
    unrelated = [
        _failure(target=TARGET_30, host=HOST_60),
        _failure(target=HOST_60, host=TARGET_30),
    ]

    transitions = {
        decide_scheduler_host_transition(
            state_status="same_identity",
            observed_host_rrule=TARGET_15,
            effective_host_rrule=TARGET_15,
            current_rrule=TARGET_15,
            current_rrule_already_applied=True,
            scheduler_state_acknowledges_current_rrule=True,
            all_host_update_failures=failures,
            recorded_host_failure=failures[-1],
        ).transition
        for failures in (unrelated, list(reversed(unrelated)))
    }

    assert transitions == {SchedulerHostTransition.SETTLED}
