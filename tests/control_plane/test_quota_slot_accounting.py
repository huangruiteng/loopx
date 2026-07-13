from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.quota.slot_accounting import (
    build_quota_slot_preview_for_decision,
    build_quota_slot_spend_event,
)


GOAL_ID = "quota-slot-accounting-fixture"
AGENT_A = "codex-monitor-a"
AGENT_B = "codex-monitor-b"


def _write_run_index(runtime: Path, records: list[dict[str, Any]]) -> None:
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _preview(runtime: Path, *, agent_id: str | None = None) -> dict[str, Any]:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "spent_slots": 0,
        "allowed_slots": 1440,
    }
    before = {
        "ok": True,
        "goal_id": GOAL_ID,
        "should_run": False,
        "effective_action": "monitor_quiet_skip",
        "state": "eligible",
        "safe_bypass_allowed": False,
        "quota": quota,
    }
    status = {
        "runtime_root": str(runtime),
        "attention_queue": {"items": [{"goal_id": GOAL_ID}]},
        "run_history": {"goals": [{"id": GOAL_ID, "quota": quota}]},
    }

    return build_quota_slot_preview_for_decision(
        status,
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**quota, "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=agent_id,
    )


def _poll(
    generated_at: str,
    *,
    material: bool,
    agent_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "quota_monitor_poll",
        "delivery_outcome": "outcome_progress" if material else "surface_only",
        "material_change": material,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def _spent(generated_at: str, *, agent_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": "quota_slot_spent",
    }
    if agent_id:
        payload["agent_id"] = agent_id
    return payload


def _run(
    generated_at: str,
    *,
    classification: str,
    agent_id: str | None = None,
    delivery_outcome: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "generated_at": generated_at,
        "goal_id": GOAL_ID,
        "classification": classification,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    if delivery_outcome:
        payload["delivery_outcome"] = delivery_outcome
    return payload


def test_unchanged_monitor_poll_is_not_accountable_delivery(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(runtime, [_poll("2026-01-01T00:00:00+00:00", material=False)])

    assert _preview(runtime)["ok"] is False


def test_material_monitor_poll_builds_attributed_spend_event(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    material_poll = _poll(
        "2026-01-01T00:01:00+00:00",
        material=True,
        agent_id=AGENT_A,
    )
    _write_run_index(runtime, [material_poll])

    preview = _preview(runtime, agent_id=AGENT_A)

    assert preview["ok"] is True
    assert preview["delivery_completion_spend"] is True
    assert preview["delivery_run_classification"] == "quota_monitor_poll"
    assert preview["delivery_run_generated_at"] == material_poll["generated_at"]
    assert preview["delivery_run_agent_id"] == AGENT_A
    event = build_quota_slot_spend_event(
        preview,
        self_repair_spend_actions=frozenset(),
    )
    assert event["agent_id"] == AGENT_A
    assert event["quota_event"]["delivery_run_agent_id"] == AGENT_A


def test_scoped_lookup_rejects_other_agent_but_unscoped_remains_compatible(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [_poll("2026-01-01T00:01:00+00:00", material=True, agent_id=AGENT_A)],
    )

    assert _preview(runtime, agent_id=AGENT_B)["ok"] is False
    assert _preview(runtime)["delivery_run_agent_id"] == AGENT_A


def test_interleaved_peer_spend_does_not_hide_scoped_delivery(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    material_a = _poll(
        "2026-01-01T00:01:00+00:00",
        material=True,
        agent_id=AGENT_A,
    )
    _write_run_index(
        runtime,
        [
            material_a,
            _poll("2026-01-01T00:02:00+00:00", material=True, agent_id=AGENT_B),
            _spent("2026-01-01T00:03:00+00:00", agent_id=AGENT_B),
        ],
    )

    scoped_a = _preview(runtime, agent_id=AGENT_A)

    assert scoped_a["ok"] is True
    assert scoped_a["delivery_run_generated_at"] == material_a["generated_at"]
    assert scoped_a["delivery_run_agent_id"] == AGENT_A
    assert _preview(runtime, agent_id=AGENT_B)["ok"] is False
    assert _preview(runtime)["ok"] is False


@pytest.mark.parametrize(
    "neutral_classification",
    ["state_refreshed", "quota_scheduler_ack"],
)
def test_same_agent_neutral_event_does_not_hide_scoped_delivery(
    tmp_path: Path,
    neutral_classification: str,
) -> None:
    runtime = tmp_path / "runtime"
    material_poll = _poll(
        "2026-01-01T00:01:00+00:00",
        material=True,
        agent_id=AGENT_A,
    )
    _write_run_index(
        runtime,
        [
            material_poll,
            _run(
                "2026-01-01T00:02:00+00:00",
                classification=neutral_classification,
                agent_id=AGENT_A,
            ),
        ],
    )

    preview = _preview(runtime, agent_id=AGENT_A)

    assert preview["ok"] is True
    assert preview["delivery_run_generated_at"] == material_poll["generated_at"]
    assert preview["delivery_run_classification"] == "quota_monitor_poll"


def test_explicit_non_accountable_refresh_still_fails_closed(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [
            _poll(
                "2026-01-01T00:01:00+00:00",
                material=True,
                agent_id=AGENT_A,
            ),
            _run(
                "2026-01-01T00:02:00+00:00",
                classification="state_refreshed",
                agent_id=AGENT_A,
                delivery_outcome="surface_only",
            ),
        ],
    )

    assert _preview(runtime, agent_id=AGENT_A)["ok"] is False


def test_accountable_refresh_becomes_latest_delivery(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    accountable_refresh = _run(
        "2026-01-01T00:02:00+00:00",
        classification="state_refreshed",
        agent_id=AGENT_A,
        delivery_outcome="outcome_progress",
    )
    _write_run_index(
        runtime,
        [
            _poll(
                "2026-01-01T00:01:00+00:00",
                material=True,
                agent_id=AGENT_A,
            ),
            accountable_refresh,
        ],
    )

    preview = _preview(runtime, agent_id=AGENT_A)

    assert preview["ok"] is True
    assert preview["delivery_run_generated_at"] == accountable_refresh["generated_at"]
    assert preview["delivery_run_classification"] == "state_refreshed"


def test_other_same_agent_non_delivery_event_still_fails_closed(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [
            _poll(
                "2026-01-01T00:01:00+00:00",
                material=True,
                agent_id=AGENT_A,
            ),
            _run(
                "2026-01-01T00:02:00+00:00",
                classification="operator_note",
                agent_id=AGENT_A,
            ),
        ],
    )

    assert _preview(runtime, agent_id=AGENT_A)["ok"] is False


def test_legacy_unscoped_delivery_remains_attributable(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [_poll("2026-01-01T00:01:00+00:00", material=True)],
    )

    preview = _preview(runtime, agent_id=AGENT_A)

    assert preview["ok"] is True
    assert preview["delivery_run_agent_id"] is None


def test_same_agent_spend_blocks_duplicate_completion(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [
            _poll("2026-01-01T00:01:00+00:00", material=True, agent_id=AGENT_A),
            _spent("2026-01-01T00:02:00+00:00", agent_id=AGENT_A),
        ],
    )

    assert _preview(runtime, agent_id=AGENT_A)["ok"] is False
