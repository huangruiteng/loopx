from __future__ import annotations

import pytest

from loopx.control_plane.scheduler.ack import build_scheduler_ack_plan
from loopx.control_plane.scheduler.state import (
    CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
)


AGENT_ID = "codex-scheduler-ack-table"
EXPECTED_RRULE = "FREQ=MINUTELY;INTERVAL=30"
RESET_TOKEN = "reset-token"
IDENTITY_SIGNATURE = "identity-signature"
STALE_WITHIN = "FREQ=MINUTELY;INTERVAL=31"


def _decision(*, cadence_class: str = "active_work") -> dict:
    return {
        "scheduler_hint": {
            "cadence_class": cadence_class,
            "codex_app": {
                "recommended_rrule": EXPECTED_RRULE,
                "stateful_backoff": {
                    "state_key": CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
                    "current_rrule": EXPECTED_RRULE,
                    "apply_needed": True,
                    "ack_needed": False,
                    "reset_token": RESET_TOKEN,
                    "identity_signature": IDENTITY_SIGNATURE,
                },
            },
        }
    }


ACK_DECISION_CASES = [
    {
        "id": "exact_apply_ack",
        "rrule": EXPECTED_RRULE,
        "expected": {"ok": True, "already_applied": False},
    },
    {
        "id": "exact_host_match_ack",
        "rrule": EXPECTED_RRULE,
        "apply": False,
        "ack": True,
        "expected": {"ok": True, "host_match_ack": True},
    },
    {
        "id": "monitor_stale_hint_within_tolerance",
        "cadence": "monitor_wait",
        "rrule": STALE_WITHIN,
        "proof": True,
        "expected": {"ok": True, "stale_hint_accepted": True},
    },
    {
        "id": "monitor_stale_hint_below_current",
        "cadence": "monitor_wait",
        "rrule": "FREQ=MINUTELY;INTERVAL=29",
        "proof": True,
        "expected": {"ok": False},
    },
    {
        "id": "monitor_stale_hint_outside_tolerance",
        "cadence": "monitor_wait",
        "rrule": "FREQ=MINUTELY;INTERVAL=33",
        "proof": True,
        "expected": {"ok": False},
    },
    {
        "id": "monitor_stale_hint_without_identity_proof",
        "cadence": "monitor_wait",
        "rrule": STALE_WITHIN,
        "expected": {"ok": False},
    },
    {
        "id": "non_monitor_never_accepts_stale_hint",
        "rrule": STALE_WITHIN,
        "proof": True,
        "expected": {"ok": False},
    },
    {
        "id": "missing_rrule_while_ack_required",
        "rrule": None,
        "expected": {"ok": False},
    },
    {
        "id": "steady_state_needs_no_ack",
        "rrule": None,
        "apply": False,
        "expected": {"ok": True, "already_applied": True},
    },
]


@pytest.mark.parametrize(
    "case",
    ACK_DECISION_CASES,
    ids=[case["id"] for case in ACK_DECISION_CASES],
)
def test_scheduler_ack_decision_table(case: dict) -> None:
    decision = _decision(cadence_class=case.get("cadence", "active_work"))
    stateful_backoff = decision["scheduler_hint"]["codex_app"]["stateful_backoff"]
    stateful_backoff["apply_needed"] = case.get("apply", True)
    stateful_backoff["ack_needed"] = case.get("ack", False)

    result = build_scheduler_ack_plan(
        decision,
        agent_id=AGENT_ID,
        applied_rrule=case["rrule"],
        reset_token=RESET_TOKEN if case.get("proof") else None,
        identity_signature=IDENTITY_SIGNATURE if case.get("proof") else None,
    )

    expected = case["expected"]
    assert {key: result.get(key) for key in expected} == expected


@pytest.mark.parametrize(
    ("mutation", "expected_reason_fragment"),
    [
        ("missing_agent", "--agent-id"),
        ("wrong_state_key", "--state-key"),
        ("wrong_reset_token", "--reset-token"),
        ("wrong_identity_signature", "--identity-signature"),
    ],
)
def test_scheduler_ack_scope_proof_rejects_mutations(
    mutation: str,
    expected_reason_fragment: str,
) -> None:
    decision = _decision()
    kwargs = {
        "agent_id": AGENT_ID,
        "state_key": CODEX_APP_STATEFUL_BACKOFF_STATE_KEY,
        "applied_rrule": EXPECTED_RRULE,
        "reset_token": RESET_TOKEN,
        "identity_signature": IDENTITY_SIGNATURE,
    }
    if mutation == "missing_agent":
        kwargs["agent_id"] = None
    elif mutation == "wrong_state_key":
        kwargs["state_key"] = "scheduler.wrong.state"
    elif mutation == "wrong_reset_token":
        kwargs["reset_token"] = "wrong-reset"
    elif mutation == "wrong_identity_signature":
        kwargs["identity_signature"] = "wrong-identity"

    result = build_scheduler_ack_plan(decision, **kwargs)

    assert result["ok"] is False
    assert expected_reason_fragment in result["reason"]
