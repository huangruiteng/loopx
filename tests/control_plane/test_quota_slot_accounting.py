from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.control_plane.quota.slot_accounting import (
    build_quota_slot_preview_for_decision,
    build_quota_slot_spend_event,
    record_quota_slot_spend_from_preview,
)
from loopx.quota import spend_quota_slot
from loopx.rollout_event_log import rollout_event_log_path

GOAL_ID = "quota-slot-accounting-fixture"
AGENT_A = "codex-monitor-a"
AGENT_B = "codex-monitor-b"
SAFE_BYPASS_CASES = (
    pytest.param(
        {"state": "operator_gate", "safe_bypass_allowed": True},
        id="operator-gate",
    ),
    pytest.param(
        {"recovery_delivery_allowed": True, "safe_bypass_allowed": True},
        id="recovery-delivery",
    ),
    pytest.param(
        {
            "effective_action": "outcome_floor_recovery",
            "safe_bypass_allowed": True,
        },
        id="outcome-floor-recovery",
    ),
)


def _write_run_index(runtime: Path, records: list[dict[str, Any]]) -> None:
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _preview(
    runtime: Path,
    *,
    agent_id: str | None = None,
    before_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    before.update(before_overrides or {})
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
    refresh_state: bool = False,
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
    if refresh_state:
        payload.update(
            {
                "recommended_action_source": "explicit_arg",
                "runtime_projection_route": {"schema_version": "runtime_projection_route_v0"},
                "state": {"sha256_16": "fixture"},
            }
        )
    return payload


def test_unchanged_monitor_poll_is_not_accountable_delivery(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(runtime, [_poll("2026-01-01T00:00:00+00:00", material=False)])

    assert _preview(runtime)["ok"] is False


def test_quota_spend_deduplicates_same_turn_effect_key(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    preview = _preview(
        runtime,
        before_overrides={
            "should_run": True,
            "effective_action": "normal_run",
        },
    )
    effect_key = "sha256:" + "b" * 64 + ":quota_spend"
    kwargs = {
        "goal_id": GOAL_ID,
        "self_repair_spend_actions": frozenset(),
        "render_markdown": lambda _payload: "quota fixture",
        "execute": True,
        "source": "adapter",
        "turn_effect_key": effect_key,
    }

    first = record_quota_slot_spend_from_preview(
        preview,
        {"runtime_root": str(runtime)},
        **kwargs,
    )
    replay = record_quota_slot_spend_from_preview(
        preview,
        {"runtime_root": str(runtime)},
        **kwargs,
    )
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"
    index_record = json.loads(index_path.read_text(encoding="utf-8"))
    run_record = json.loads(
        Path(str(first["json_path"])).read_text(encoding="utf-8")
    )

    assert first["appended"] is True
    assert replay["appended"] is False
    assert replay["idempotent"] is True
    assert replay["json_path"] == first["json_path"]
    assert replay["markdown_path"] == first["markdown_path"]
    assert run_record["turn_effect_key"] == effect_key
    assert index_record["turn_effect_key"] == effect_key
    assert run_record["effect_input_hash"] == first["effect_input_hash"]
    assert index_record["effect_input_hash"] == first["effect_input_hash"]
    assert first["before"]["spent_slots"] == 0
    assert first["after"]["spent_slots"] == 1
    assert replay["before"]["spent_slots"] == 0
    assert replay["after"]["spent_slots"] == 1
    assert replay["quota_event"] == first["quota_event"]
    assert len(index_path.read_text(encoding="utf-8").splitlines()) == 1


def test_quota_spend_rejects_turn_effect_key_content_drift(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    preview = _preview(
        runtime,
        before_overrides={
            "should_run": True,
            "effective_action": "normal_run",
        },
    )
    effect_key = "sha256:" + "c" * 64 + ":quota_spend"
    kwargs = {
        "goal_id": GOAL_ID,
        "self_repair_spend_actions": frozenset(),
        "render_markdown": lambda _payload: "quota fixture",
        "execute": True,
        "source": "adapter",
        "turn_effect_key": effect_key,
    }
    record_quota_slot_spend_from_preview(
        preview,
        {"runtime_root": str(runtime)},
        **kwargs,
    )
    changed = json.loads(json.dumps(preview))
    changed["after"]["recommended_action"] = "A different next action."

    with pytest.raises(ValueError, match="turn effect key conflict"):
        record_quota_slot_spend_from_preview(
            changed,
            {"runtime_root": str(runtime)},
            **kwargs,
        )


def test_spend_quota_slot_propagates_turn_effect_key_to_durable_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    preview = _preview(
        runtime,
        before_overrides={
            "should_run": True,
            "effective_action": "normal_run",
        },
    )
    monkeypatch.setattr(
        "loopx.quota.build_quota_slot_preview",
        lambda *_args, **_kwargs: preview,
    )
    effect_key = "sha256:" + "d" * 64 + ":quota_spend"

    first = spend_quota_slot(
        {"runtime_root": str(runtime)},
        goal_id=GOAL_ID,
        execute=True,
        source="adapter",
        turn_effect_key=effect_key,
    )
    replay = spend_quota_slot(
        {"runtime_root": str(runtime)},
        goal_id=GOAL_ID,
        execute=True,
        source="adapter",
        turn_effect_key=effect_key,
    )
    index_path = runtime / "goals" / GOAL_ID / "runs" / "index.jsonl"

    assert first["appended"] is True
    assert replay["appended"] is False
    assert replay["idempotent"] is True
    assert len(index_path.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.parametrize("before_overrides", SAFE_BYPASS_CASES)
def test_safe_bypass_rejects_no_accountable_writeback(
    tmp_path: Path,
    before_overrides: dict[str, Any],
) -> None:
    runtime = tmp_path / "runtime"

    preview = _preview(runtime, before_overrides=before_overrides)

    assert preview["ok"] is False
    assert "requires a latest unspent accountable delivery writeback" in preview[
        "reason"
    ]


@pytest.mark.parametrize("before_overrides", SAFE_BYPASS_CASES)
def test_safe_bypass_consumes_accountable_writeback_once_across_neutral_refresh(
    tmp_path: Path,
    before_overrides: dict[str, Any],
) -> None:
    runtime = tmp_path / "runtime"
    delivery = _run(
        "2026-01-01T00:01:00+00:00",
        classification="validated_fallback",
        delivery_outcome="outcome_progress",
    )
    neutral_refresh = _run(
        "2026-01-01T00:02:00+00:00",
        classification="quality_qualification_vision_checkpoint_ack",
        refresh_state=True,
    )
    _write_run_index(runtime, [delivery, neutral_refresh])

    preview = _preview(runtime, before_overrides=before_overrides)

    assert preview["ok"] is True
    assert preview["safe_bypass_spend"] is True
    assert preview["delivery_run_classification"] == "validated_fallback"
    event = build_quota_slot_spend_event(
        preview,
        self_repair_spend_actions=frozenset(),
    )
    assert "safe-bypass" in event["health_check"]

    with pytest.raises(ValueError, match="requires an eligible"):
        build_quota_slot_spend_event(
            {**preview, "safe_bypass_spend": False},
            self_repair_spend_actions=frozenset(),
        )

    _write_run_index(
        runtime,
        [
            delivery,
            neutral_refresh,
            _spent("2026-01-01T00:03:00+00:00"),
        ],
    )
    assert _preview(runtime, before_overrides=before_overrides)["ok"] is False


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


@pytest.mark.parametrize(
    "later_run",
    [
        _run(
            "2026-01-01T00:02:00+00:00",
            classification="custom_refresh_with_surface_outcome",
            agent_id=AGENT_A,
            delivery_outcome="surface_only",
            refresh_state=True,
        ),
        _run(
            "2026-01-01T00:02:00+00:00",
            classification="operator_note_with_partial_refresh_shape",
            agent_id=AGENT_A,
        )
        | {"state": {"sha256_16": "fixture"}},
    ],
    ids=["explicit-non-accountable-outcome", "partial-refresh-shape"],
)
def test_custom_non_neutral_event_still_fails_closed(
    tmp_path: Path,
    later_run: dict[str, Any],
) -> None:
    runtime = tmp_path / "runtime"
    _write_run_index(
        runtime,
        [
            _poll(
                "2026-01-01T00:01:00+00:00",
                material=True,
                agent_id=AGENT_A,
            ),
            later_run,
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


def _normal_run_before(*, todo_id: str) -> dict[str, Any]:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "spent_slots": 0,
        "allowed_slots": 1440,
    }
    return {
        "ok": True,
        "goal_id": GOAL_ID,
        "should_run": True,
        "normal_delivery_allowed": True,
        "effective_action": "normal_run",
        "state": "eligible",
        "safe_bypass_allowed": False,
        "quota": quota,
        "selected_todo": {"todo_id": todo_id},
    }


def _normal_run_status(runtime: Path) -> dict[str, Any]:
    quota = {
        "compute": 1.0,
        "window_hours": 24,
        "slot_minutes": 1,
        "spent_slots": 0,
        "allowed_slots": 1440,
    }
    return {
        "runtime_root": str(runtime),
        "attention_queue": {"items": [{"goal_id": GOAL_ID}]},
        "run_history": {"goals": [{"id": GOAL_ID, "quota": quota}]},
    }


def _write_typed_settlement_fixture(
    runtime: Path,
    *,
    todo_id: str,
    turn_instance_id: str,
    include_spend: bool = False,
    workspace_requirement: str | None = None,
) -> str:
    effect_id = f"{GOAL_ID}:{AGENT_A}:{todo_id}:{turn_instance_id}"
    identity = {
        "effect_id": effect_id,
        "goal_id": GOAL_ID,
        "agent_id": AGENT_A,
        "todo_id": todo_id,
        "turn_instance_id": turn_instance_id,
    }
    records = [
        {
            **_run(
                "2026-01-01T00:01:00+00:00",
                classification="validated_progress",
                delivery_outcome="outcome_progress",
                agent_id=AGENT_A,
            ),
            "todo_id": todo_id,
            "turn_instance_id": turn_instance_id,
            "settlement_identity": identity,
        }
    ]
    if include_spend:
        records.append(
            {
                **_spent("2026-01-01T00:02:00+00:00", agent_id=AGENT_A),
                "todo_id": todo_id,
                "turn_instance_id": turn_instance_id,
                "settlement_identity": identity,
            }
        )
    _write_run_index(runtime, records)

    guard_details = {
        "todo_id": todo_id,
        "settlement_effect_id": effect_id,
    }
    if workspace_requirement:
        guard_details.update(
            {
                "delivery_workspace_causality_schema_version": (
                    "delivery_workspace_causality_v0"
                ),
                "delivery_workspace_causality_todo_id": todo_id,
                "delivery_workspace_requirement": workspace_requirement,
                "delivery_workspace_causality_source": "selected_todo_contract",
                "delivery_workspace_causality_reason": (
                    "declared_repository_or_write_contract"
                    if workspace_requirement == "required"
                    else "todo_write_contract_not_explicit"
                ),
            }
        )
    events = [
        {
            "schema_version": "loopx_rollout_event_v0",
            "event_id": "event-guard",
            "event_kind": "quota_should_run",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_A,
            "run_id": turn_instance_id,
            "details": guard_details,
        },
        {
            "schema_version": "loopx_rollout_event_v0",
            "event_id": "event-writeback",
            "event_kind": "refresh_state",
            "goal_id": GOAL_ID,
            "agent_id": AGENT_A,
            "run_id": turn_instance_id,
            "details": {"settlement_effect_id": effect_id},
        },
    ]
    if include_spend:
        events.append(
            {
                "schema_version": "loopx_rollout_event_v0",
                "event_id": "event-spend",
                "event_kind": "quota_spend",
                "goal_id": GOAL_ID,
                "agent_id": AGENT_A,
                "run_id": turn_instance_id,
                "details": {"settlement_effect_id": effect_id},
            }
        )
    rollout_path = rollout_event_log_path(runtime, GOAL_ID)
    rollout_path.parent.mkdir(parents=True, exist_ok=True)
    rollout_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    return effect_id


def test_heartbeat_spend_requires_todo_binding(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    before = _normal_run_before(todo_id="todo_selected_binding")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=None,
        source="heartbeat",
    )

    assert preview["ok"] is False
    assert "requires --todo-id todo_selected_binding" in preview["reason"]


def test_heartbeat_spend_rejects_mismatched_todo_binding(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    before = _normal_run_before(todo_id="todo_selected_binding")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=None,
        todo_id="todo_other_binding",
        source="heartbeat",
    )

    assert preview["ok"] is False
    assert "binding mismatch" in preview["reason"]


def test_heartbeat_spend_recovers_completed_todo_identity_after_reselection(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    original_todo_id = "todo_completed_delivery"
    turn_instance_id = "turn-completed-delivery"
    effect_id = _write_typed_settlement_fixture(
        runtime,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
    )
    before = _normal_run_before(todo_id="todo_new_successor")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=AGENT_A,
        todo_id=original_todo_id,
        source="heartbeat",
    )

    assert preview["ok"] is True, preview
    assert preview["delivery_completion_spend"] is True
    assert preview["turn_instance_id"] == turn_instance_id
    assert preview["settlement_identity"]["effect_id"] == effect_id


@pytest.mark.parametrize("workspace_requirement", ["required", "unknown"])
def test_typed_workspace_causality_fails_closed_without_workspace_snapshot(
    tmp_path: Path,
    workspace_requirement: str,
) -> None:
    runtime = tmp_path / "runtime"
    original_todo_id = "todo_completed_delivery"
    turn_instance_id = "turn-completed-delivery"
    _write_typed_settlement_fixture(
        runtime,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
        workspace_requirement=workspace_requirement,
    )
    before = _normal_run_before(todo_id="todo_new_successor")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=AGENT_A,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
        source="heartbeat",
    )

    assert preview["ok"] is False
    assert "requires a valid delivery workspace snapshot" in preview["reason"]
    assert preview["delivery_workspace_causality"]["requirement"] == (
        workspace_requirement
    )
    assert preview["delivery_workspace_validated"] is False


def test_implicit_heartbeat_identity_fails_closed_on_persisted_effect_drift(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    original_todo_id = "todo_completed_delivery"
    turn_instance_id = "turn-completed-delivery"
    _write_run_index(
        runtime,
        [
            {
                **_run(
                    "2026-01-01T00:01:00+00:00",
                    classification="validated_progress",
                    delivery_outcome="outcome_progress",
                    agent_id=AGENT_A,
                ),
                "todo_id": original_todo_id,
                "turn_instance_id": turn_instance_id,
                "settlement_identity": {"effect_id": "drifted-effect-id"},
            }
        ],
    )
    before = _normal_run_before(todo_id="todo_new_successor")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: before,
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=AGENT_A,
        todo_id=original_todo_id,
        source="heartbeat",
    )

    assert preview["ok"] is False
    assert "persisted settlement identity mismatch" in preview["reason"]
    assert preview["settlement_result"]["failure"]["kind"] == "identity_mismatch"


def test_implicit_heartbeat_spend_replays_exactly_once_after_frontier_moves(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    original_todo_id = "todo_completed_delivery"
    turn_instance_id = "turn-completed-delivery"
    _write_typed_settlement_fixture(
        runtime,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
        include_spend=True,
    )

    replay = spend_quota_slot(
        {"runtime_root": str(runtime)},
        goal_id=GOAL_ID,
        execute=True,
        source="heartbeat",
        agent_id=AGENT_A,
        todo_id=original_todo_id,
    )

    assert replay["ok"] is True, replay
    assert replay["appended"] is False
    assert replay["idempotent_replay"] is True
    assert replay["turn_instance_id"] == turn_instance_id


def test_turn_scoped_spend_keeps_original_todo_across_successor_reselection(
    tmp_path: Path,
) -> None:
    runtime = tmp_path / "runtime"
    original_todo_id = "todo_completed_delivery"
    turn_instance_id = "turn-completed-delivery"
    effect_id = _write_typed_settlement_fixture(
        runtime,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
    )
    before = _normal_run_before(todo_id="todo_new_successor")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=AGENT_A,
        todo_id=original_todo_id,
        turn_instance_id=turn_instance_id,
        source="heartbeat",
    )

    assert preview["ok"] is True
    assert preview["delivery_completion_spend"] is True
    assert preview["todo_id"] == original_todo_id
    assert preview["settlement_identity"]["effect_id"] == effect_id
    assert [
        receipt["step_kind"]
        for receipt in preview["settlement_result"]["receipts"]
    ] == ["validation", "durable_writeback"]


def test_heartbeat_spend_records_matching_todo_binding(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    before = _normal_run_before(todo_id="todo_selected_binding")

    preview = build_quota_slot_preview_for_decision(
        _normal_run_status(runtime),
        goal_id=GOAL_ID,
        before=before,
        after_decision=lambda _: {
            **before,
            "quota": {**before["quota"], "spent_slots": 1},
        },
        quota_status_builder=lambda goal, **_: goal["quota"],
        self_repair_spend_actions=frozenset(),
        agent_id=None,
        todo_id="todo_selected_binding",
        source="heartbeat",
    )
    event = build_quota_slot_spend_event(
        preview,
        self_repair_spend_actions=frozenset(),
        source="heartbeat",
    )

    assert preview["ok"] is True
    assert event["quota_event"]["todo_id"] == "todo_selected_binding"
