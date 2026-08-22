"""Focused tests for the remaining shared settlement projection facade."""

import pytest

from loopx.control_plane.effect_program import (
    SettlementIdentity,
    SettlementStepKind,
)
from loopx.control_plane.settlement_driver import (
    effect_ids_match,
    settlement_receipt,
)
from loopx.control_plane.turn_driver.settlement import execute_turn_driver_settlement


IDENTITY = SettlementIdentity(
    goal_id="fixture-goal",
    agent_id="fixture-agent",
    todo_id="todo_fixture0001",
    turn_instance_id="fixture-turn",
)
PHASES = (
    "host_execute",
    "typed_result",
    "validation",
    "durable_writeback",
    "quota_spend",
)
TRANSACTION = {"settlement_plan": {"identity": IDENTITY.as_dict()}}


def test_effect_ids_match_allows_missing_and_equal_provenance() -> None:
    assert effect_ids_match(None, IDENTITY.effect_id) is True
    assert effect_ids_match(IDENTITY.effect_id, IDENTITY.effect_id) is True
    assert effect_ids_match("other-effect", IDENTITY.effect_id) is False


def test_settlement_receipt_is_committed_under_the_identity() -> None:
    receipt = settlement_receipt(
        IDENTITY,
        step_kind=SettlementStepKind.VALIDATION,
        source_ref="rollout_event:abc",
    )
    assert receipt.step_kind is SettlementStepKind.VALIDATION
    assert receipt.status == "committed"
    assert receipt.effect_id == IDENTITY.effect_id
    assert receipt.source_ref == "rollout_event:abc"


def test_turn_settlement_prepares_before_invoking_legacy_callbacks() -> None:
    events: list[str] = []

    result = execute_turn_driver_settlement(
        TRANSACTION,
        transaction_phases=PHASES,
        completed_phases=PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda: events.append("writeback") or {"ok": True, "appended": True},
        spend=lambda: events.append("spend") or {"ok": True, "appended": True},
        checkpoint=lambda step, _payload, _phases: events.append(
            f"checkpoint:{step.value}"
        ),
        prepare=lambda step, _effect_ref: events.append(f"prepare:{step.value}"),
    )

    assert result.failure is None
    assert events == [
        "prepare:durable_writeback",
        "writeback",
        "checkpoint:durable_writeback",
        "prepare:quota_spend",
        "spend",
        "checkpoint:quota_spend",
    ]


def test_turn_settlement_passes_stable_effect_refs_to_new_callbacks() -> None:
    observed_refs: list[str] = []

    result = execute_turn_driver_settlement(
        TRANSACTION,
        transaction_phases=PHASES,
        completed_phases=PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda effect_ref: (
            observed_refs.append(effect_ref) or {"ok": True, "appended": True}
        ),
        spend=lambda *, effect_ref: (
            observed_refs.append(effect_ref) or {"ok": True, "appended": True}
        ),
        checkpoint=lambda _step, _payload, _phases: None,
        prepare=lambda _step, _effect_ref: None,
    )

    assert result.failure is None
    assert observed_refs == [
        f"{IDENTITY.effect_id}#durable_writeback",
        f"{IDENTITY.effect_id}#quota_spend",
    ]


def test_turn_settlement_checkpoints_committed_readback_without_reexecution() -> None:
    effect_ref = f"{IDENTITY.effect_id}#durable_writeback"
    events: list[str] = []

    result = execute_turn_driver_settlement(
        TRANSACTION,
        transaction_phases=PHASES,
        completed_phases=PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda: pytest.fail("committed effect must not execute again"),
        spend=lambda: {"ok": True, "appended": True},
        checkpoint=lambda step, _payload, _phases: events.append(
            f"checkpoint:{step.value}"
        ),
        prepare=lambda step, _effect_ref: events.append(f"prepare:{step.value}"),
        effect_attempts={
            "durable_writeback": {"status": "prepared", "effect_ref": effect_ref}
        },
        effect_resolvers={
            SettlementStepKind.DURABLE_WRITEBACK: lambda observed_ref: {
                "kind": "committed",
                "payload": {
                    "ok": True,
                    "appended": True,
                    "effect_ref": observed_ref,
                },
            }
        },
    )

    assert result.failure is None
    assert events == [
        "checkpoint:durable_writeback",
        "prepare:quota_spend",
        "checkpoint:quota_spend",
    ]


def test_turn_settlement_reexecutes_absent_readback_with_the_same_ref() -> None:
    effect_ref = f"{IDENTITY.effect_id}#durable_writeback"
    observed_refs: list[str] = []

    result = execute_turn_driver_settlement(
        TRANSACTION,
        transaction_phases=PHASES,
        completed_phases=PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda observed_ref: (
            observed_refs.append(observed_ref) or {"ok": True, "appended": True}
        ),
        spend=lambda: {"ok": True, "appended": True},
        checkpoint=lambda _step, _payload, _phases: None,
        prepare=lambda _step, _effect_ref: None,
        effect_attempts={
            "durable_writeback": {"status": "prepared", "effect_ref": effect_ref}
        },
        effect_resolvers={
            SettlementStepKind.DURABLE_WRITEBACK: lambda _effect_ref: {"kind": "absent"}
        },
    )

    assert result.failure is None
    assert observed_refs == [effect_ref]


@pytest.mark.parametrize(
    "resolver",
    [
        None,
        lambda _effect_ref: {
            "kind": "unknown",
            "reason": "provider readback timed out",
        },
    ],
)
def test_turn_settlement_fails_closed_when_prepared_outcome_is_unknown(
    resolver,
) -> None:
    effect_ref = f"{IDENTITY.effect_id}#durable_writeback"
    calls = {"writeback": 0}
    resolvers = (
        {} if resolver is None else {SettlementStepKind.DURABLE_WRITEBACK: resolver}
    )

    result = execute_turn_driver_settlement(
        TRANSACTION,
        transaction_phases=PHASES,
        completed_phases=PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda: (
            calls.__setitem__("writeback", calls["writeback"] + 1)
            or {"ok": True, "appended": True}
        ),
        spend=lambda: {"ok": True, "appended": True},
        checkpoint=lambda _step, _payload, _phases: None,
        effect_attempts={
            "durable_writeback": {"status": "prepared", "effect_ref": effect_ref}
        },
        effect_resolvers=resolvers,
    )

    assert result.failure is not None
    assert result.failure.kind.value == "effect_outcome_unknown"
    assert result.failure.step_kind is SettlementStepKind.DURABLE_WRITEBACK
    assert calls["writeback"] == 0
