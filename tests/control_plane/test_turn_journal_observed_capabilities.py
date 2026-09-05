from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver.journal_store import (
    turn_journal_observed_capabilities,
)


GOAL_ID = "journal-capability-goal"
AGENT_ID = "codex-journal-capability"
TURN_ID = "turn-journal-evidence-7"
OTHER_TURN = "turn-journal-unrelated-8"


def _write_journal(
    runtime: Path,
    *,
    turn_instance_id: str = TURN_ID,
    boundary: dict[str, object] | None = None,
    capability_gate: dict[str, object] | None = None,
    digest: str = "c" * 64,
) -> None:
    turns = runtime / "goals" / GOAL_ID / "turns"
    turns.mkdir(parents=True, exist_ok=True)
    envelope: dict[str, object] = {"goal_id": GOAL_ID, "agent_id": AGENT_ID}
    if boundary is not None:
        envelope["boundary"] = boundary
    if capability_gate is not None:
        envelope["capability_gate"] = capability_gate
    (turns / f"{digest}.json").write_text(
        json.dumps(
            {
                "schema_version": "loopx_turn_journal_v0",
                "turn_key": f"sha256:{digest}",
                "goal_id": GOAL_ID,
                "status": "committed",
                "plan": {
                    "transaction": {"turn_instance_id": turn_instance_id},
                    "turn_envelope": envelope,
                },
            }
        ),
        encoding="utf-8",
    )


def test_read_declared_boundary_capabilities(tmp_path: Path) -> None:
    _write_journal(
        tmp_path,
        boundary={"available_capabilities": ["network", "lark_bot_message_write"]},
    )

    assert turn_journal_observed_capabilities(
        tmp_path, goal_id=GOAL_ID, turn_instance_id=TURN_ID
    ) == ["network", "lark_bot_message_write"]


def test_read_gate_proven_capabilities_when_none_missing(tmp_path: Path) -> None:
    _write_journal(
        tmp_path,
        capability_gate={
            "required_capabilities": ["network"],
            "missing_capabilities": [],
        },
    )

    assert turn_journal_observed_capabilities(
        tmp_path, goal_id=GOAL_ID, turn_instance_id=TURN_ID
    ) == ["network"]


def test_missing_gate_capabilities_stay_unproven(tmp_path: Path) -> None:
    _write_journal(
        tmp_path,
        capability_gate={
            "required_capabilities": ["network", "lark_bot_message_write"],
            "missing_capabilities": ["network"],
        },
    )

    assert turn_journal_observed_capabilities(
        tmp_path, goal_id=GOAL_ID, turn_instance_id=TURN_ID
    ) == []


@pytest.mark.parametrize("turn_instance_id", [OTHER_TURN, ""])
def test_unmatched_turn_returns_none(tmp_path: Path, turn_instance_id: str) -> None:
    _write_journal(tmp_path)

    assert (
        turn_journal_observed_capabilities(
            tmp_path, goal_id=GOAL_ID, turn_instance_id=turn_instance_id
        )
        is None
    )


def test_missing_or_unreadable_journals_fail_closed(tmp_path: Path) -> None:
    observed = turn_journal_observed_capabilities(
        tmp_path, goal_id=GOAL_ID, turn_instance_id=TURN_ID
    )
    assert observed is None

    turns = tmp_path / "goals" / GOAL_ID / "turns"
    turns.mkdir(parents=True)
    (turns / "corrupt.json").write_text("{not json", encoding="utf-8")
    (turns / f"{'d' * 64}.json").write_text(
        json.dumps({"schema_version": "unsupported_v9"}),
        encoding="utf-8",
    )

    observed_after = turn_journal_observed_capabilities(
        tmp_path, goal_id=GOAL_ID, turn_instance_id=TURN_ID
    )
    assert observed_after is None
