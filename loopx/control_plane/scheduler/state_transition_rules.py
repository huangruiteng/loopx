from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .state import normalize_scheduler_rrule, rrule_for_minutes


class SchedulerCadenceTransition(str, Enum):
    INITIAL = "initial"
    IDENTITY_RESET = "identity_reset"
    RETRY_UNACKNOWLEDGED_FAILURE = "retry_unacknowledged_failure"
    HOLD_ACTIVE_INITIAL = "hold_active_initial"
    ADVANCE_AFTER_INTERVAL = "advance_after_interval"
    HOLD_UNTIL_INTERVAL = "hold_until_interval"


@dataclass(frozen=True)
class SchedulerCadenceDecision:
    current_index: int
    state_status: str
    transition: SchedulerCadenceTransition
    current_cadence_acknowledged: bool


def decide_scheduler_cadence_transition(
    progression_minutes: Sequence[int],
    *,
    scheduler_state: Mapping[str, Any],
    reset_token: str,
    identity_signature: str,
    advance_same_identity: bool,
    applied_interval_elapsed: bool,
    has_host_update_failures: bool,
) -> SchedulerCadenceDecision:
    """Choose the cadence index without rendering a scheduler hint."""

    if not progression_minutes:
        raise ValueError("scheduler cadence progression must not be empty")
    if not scheduler_state:
        return SchedulerCadenceDecision(
            current_index=0,
            state_status="missing",
            transition=SchedulerCadenceTransition.INITIAL,
            current_cadence_acknowledged=False,
        )

    same_identity = (
        scheduler_state.get("reset_token") == reset_token
        and scheduler_state.get("identity_signature") == identity_signature
    )
    if not same_identity:
        return SchedulerCadenceDecision(
            current_index=0,
            state_status="reset_required",
            transition=SchedulerCadenceTransition.IDENTITY_RESET,
            current_cadence_acknowledged=False,
        )

    try:
        applied_index = int(scheduler_state.get("progression_index"))
    except (TypeError, ValueError):
        applied_index = -1
    applied_target_rrule = (
        rrule_for_minutes(progression_minutes[applied_index])
        if 0 <= applied_index < len(progression_minutes)
        else ""
    )
    current_cadence_acknowledged = (
        normalize_scheduler_rrule(scheduler_state.get("last_applied_rrule"))
        == applied_target_rrule
    )

    if has_host_update_failures and not current_cadence_acknowledged:
        next_index = applied_index
        transition = SchedulerCadenceTransition.RETRY_UNACKNOWLEDGED_FAILURE
    elif not advance_same_identity:
        next_index = 0
        transition = SchedulerCadenceTransition.HOLD_ACTIVE_INITIAL
    elif applied_interval_elapsed:
        next_index = applied_index + 1
        transition = SchedulerCadenceTransition.ADVANCE_AFTER_INTERVAL
    else:
        next_index = applied_index
        transition = SchedulerCadenceTransition.HOLD_UNTIL_INTERVAL

    return SchedulerCadenceDecision(
        current_index=min(max(next_index, 0), len(progression_minutes) - 1),
        state_status="same_identity",
        transition=transition,
        current_cadence_acknowledged=current_cadence_acknowledged,
    )


class SchedulerHostTransition(str, Enum):
    APPLY_REQUIRED = "apply_required"
    HOST_MATCH_ACK_REQUIRED = "host_match_ack_required"
    RECORDED_FAILURE_SUPPRESSED = "recorded_failure_suppressed"
    SETTLED = "settled"


@dataclass(frozen=True)
class SchedulerHostDecision:
    transition: SchedulerHostTransition
    current_target_has_failure: bool
    repeated_failed_pair: bool

    @property
    def apply_needed(self) -> bool:
        return self.transition == SchedulerHostTransition.APPLY_REQUIRED

    @property
    def host_match_ack_needed(self) -> bool:
        return self.transition == SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED

    @property
    def host_failure_suppressed(self) -> bool:
        return self.transition == SchedulerHostTransition.RECORDED_FAILURE_SUPPRESSED

    @property
    def ack_needed(self) -> bool:
        return self.transition in {
            SchedulerHostTransition.APPLY_REQUIRED,
            SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED,
        }


def decide_scheduler_host_transition(
    *,
    state_status: str,
    observed_host_rrule: str,
    effective_host_rrule: str,
    current_rrule: str,
    current_rrule_already_applied: bool,
    scheduler_state_acknowledges_current_rrule: bool,
    all_host_update_failures: Collection[Mapping[str, Any]],
    recorded_host_failure: Mapping[str, Any] | None,
) -> SchedulerHostDecision:
    """Classify the host action from normalized scheduler facts."""

    current_target_has_failure = any(
        normalize_scheduler_rrule(failure.get("target_rrule")) == current_rrule
        for failure in all_host_update_failures
    )
    failed_target_rrule = normalize_scheduler_rrule(
        (recorded_host_failure or {}).get("target_rrule")
    )
    failed_observed_host_rrule = normalize_scheduler_rrule(
        (recorded_host_failure or {}).get("observed_host_rrule")
    )
    repeated_failed_pair = bool(
        failed_target_rrule == current_rrule
        and failed_observed_host_rrule == effective_host_rrule
    )

    if (
        observed_host_rrule
        and current_rrule_already_applied
        and (
            not scheduler_state_acknowledges_current_rrule
            or state_status != "same_identity"
            or current_target_has_failure
        )
    ):
        transition = SchedulerHostTransition.HOST_MATCH_ACK_REQUIRED
    elif current_rrule_already_applied and state_status == "same_identity":
        transition = SchedulerHostTransition.SETTLED
    elif repeated_failed_pair:
        transition = SchedulerHostTransition.RECORDED_FAILURE_SUPPRESSED
    else:
        transition = SchedulerHostTransition.APPLY_REQUIRED

    return SchedulerHostDecision(
        transition=transition,
        current_target_has_failure=current_target_has_failure,
        repeated_failed_pair=repeated_failed_pair,
    )
