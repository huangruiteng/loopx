from __future__ import annotations

import pytest

from loopx.control_plane.turn_driver import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    LoopXTurnResultKind,
    build_loopx_turn_transaction_plan,
    loopx_turn_execution_committed,
    loopx_turn_execution_has_durable_effects,
    loopx_turn_execution_recovery_required,
    validate_loopx_turn_receipt,
)


def _plan() -> dict[str, object]:
    return build_loopx_turn_transaction_plan(
        planned=True,
        lineage={
            "goal_id": "fixture-goal",
            "agent_id": "codex-fixture",
            "todo_id": "todo_fixture0001",
            "action_hash": "sha256:fixture",
        },
        host="codex-cli",
        execution_mode="interactive-visible",
        session_action="resume",
    )


def _result(
    plan: dict[str, object],
    *,
    result_kind: LoopXTurnResultKind = LoopXTurnResultKind.VALIDATED_PROGRESS,
    completed_phases: list[str] | None = None,
    failed_phase: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
        "turn_key": plan["turn_key"],
        "result_kind": result_kind.value,
        "completed_phases": (
            completed_phases
            if completed_phases is not None
            else ["host_execute", "typed_result", "validation"]
        ),
    }
    if failed_phase:
        result["failed_phase"] = failed_phase
    return result


def test_validated_result_becomes_writeback_eligible_without_spend() -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(plan, _result(plan))

    assert receipt["ok"] is True
    assert receipt["status"] == "validated"
    assert receipt["next_phase"] == "durable_writeback"
    assert receipt["commit_eligibility"] == {
        "writeback": True,
        "quota_spend": False,
        "scheduler_ack": False,
    }


def test_fully_committed_result_proves_writeback_spend_and_ack_order() -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(plan, completed_phases=list(plan["phases"])),
    )

    assert receipt["ok"] is True
    assert receipt["status"] == "committed"
    assert receipt["next_phase"] is None
    assert receipt["commit_eligibility"] == {
        "writeback": True,
        "quota_spend": True,
        "scheduler_ack": True,
    }


@pytest.mark.parametrize(
    "completed_phases",
    [
        ["host_execute", "typed_result", "durable_writeback"],
        ["host_execute", "typed_result", "validation", "quota_spend"],
        [
            "host_execute",
            "typed_result",
            "validation",
            "durable_writeback",
            "quota_spend",
            "scheduler_ack",
        ],
    ],
)
def test_receipt_rejects_skipped_transaction_phases(
    completed_phases: list[str],
) -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(plan, completed_phases=completed_phases),
    )

    assert receipt["ok"] is False
    assert "ordered transaction prefix" in " ".join(receipt["errors"])
    assert receipt["commit_eligibility"]["quota_spend"] is False


def test_receipt_rejects_turn_lineage_drift() -> None:
    plan = _plan()
    result = _result(plan)
    result["turn_key"] = "sha256:another-turn"

    receipt = validate_loopx_turn_receipt(plan, result)

    assert receipt["ok"] is False
    assert "turn_key" in " ".join(receipt["errors"])


@pytest.mark.parametrize(
    ("kind", "completed", "failed_phase"),
    [
        (LoopXTurnResultKind.HOST_FAILURE, [], "host_execute"),
        (
            LoopXTurnResultKind.VALIDATION_FAILED,
            ["host_execute", "typed_result"],
            "validation",
        ),
        (
            LoopXTurnResultKind.WRITEBACK_FAILED,
            ["host_execute", "typed_result", "validation"],
            "durable_writeback",
        ),
        (
            LoopXTurnResultKind.QUOTA_SPEND_FAILED,
            [
                "host_execute",
                "typed_result",
                "validation",
                "durable_writeback",
            ],
            "quota_spend",
        ),
    ],
)
def test_typed_failure_stops_at_its_declared_phase(
    kind: LoopXTurnResultKind,
    completed: list[str],
    failed_phase: str,
) -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(
            plan,
            result_kind=kind,
            completed_phases=completed,
            failed_phase=failed_phase,
        ),
    )

    assert receipt["ok"] is True
    assert receipt["status"] == "failed"
    assert receipt["next_phase"] == failed_phase
    assert receipt["commit_eligibility"]["quota_spend"] is False


def test_no_spend_result_cannot_claim_a_spent_transaction() -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(
            plan,
            result_kind=LoopXTurnResultKind.WAIT,
            completed_phases=list(plan["phases"][:5]),
        ),
    )

    assert receipt["ok"] is False
    assert "cannot spend quota" in " ".join(receipt["errors"])


def test_wait_result_stops_without_effect_eligibility() -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(
            plan,
            result_kind=LoopXTurnResultKind.WAIT,
            completed_phases=["host_execute", "typed_result"],
        ),
    )

    assert receipt["ok"] is True
    assert receipt["status"] == "stopped"
    assert receipt["next_phase"] is None
    assert receipt["commit_eligibility"] == {
        "writeback": False,
        "quota_spend": False,
        "scheduler_ack": False,
    }


def test_material_result_requires_completed_validation() -> None:
    plan = _plan()

    receipt = validate_loopx_turn_receipt(
        plan,
        _result(plan, completed_phases=["host_execute", "typed_result"]),
    )

    assert receipt["ok"] is False
    assert "requires completed validation" in " ".join(receipt["errors"])


def test_non_executable_plan_rejects_a_result() -> None:
    plan = build_loopx_turn_transaction_plan(
        planned=False,
        lineage={"goal_id": "fixture", "agent_id": "agent", "todo_id": "todo"},
        host="codex-cli",
        execution_mode="interactive-visible",
        session_action="none",
    )

    receipt = validate_loopx_turn_receipt(plan, _result(plan))

    assert receipt["ok"] is False
    assert "not executable" in " ".join(receipt["errors"])


def test_public_execution_outcome_predicates_share_transaction_semantics() -> None:
    committed = {
        "status": "committed",
        "validation": {"status": "passed"},
        "receipt": {"status": "committed"},
        "effects": {"state_written": True, "quota_spent": True},
    }
    repair = {
        "status": "failed",
        "validation": {
            "status": "failed",
            "recovery_kind": "repair_required",
        },
        "receipt": {"status": "failed", "failed_phase": "validation"},
        "effects": {"state_written": False, "quota_spent": False},
    }

    assert loopx_turn_execution_committed(committed) is True
    assert loopx_turn_execution_recovery_required(committed) is False
    assert loopx_turn_execution_has_durable_effects(committed) is True
    assert loopx_turn_execution_committed(repair) is False
    assert loopx_turn_execution_recovery_required(repair) is True
    assert loopx_turn_execution_has_durable_effects(repair) is False

    repair["effects"] = {"state_written": True, "quota_spent": False}
    assert loopx_turn_execution_has_durable_effects(repair) is True
