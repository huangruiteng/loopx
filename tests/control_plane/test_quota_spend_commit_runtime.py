from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from loopx.control_plane.quota.spend_commit import (
    build_quota_slot_spend_event,
    record_quota_slot_spend_from_preview,
)
from loopx.presentation.renderers.quota_event_markdown import (
    render_quota_slot_preview_markdown,
)


GOAL_ID = "quota-spend-commit-runtime"
AGENT_ID = "codex-main-control"


def _decision(spent_slots: int) -> dict[str, object]:
    return {
        "should_run": True,
        "normal_delivery_allowed": True,
        "recovery_delivery_allowed": False,
        "effective_action": "advance",
        "self_repair_allowed": False,
        "capability_repair_allowed": False,
        "workspace_repair_allowed": False,
        "state": "eligible",
        "safe_bypass_allowed": False,
        "safe_bypass_kind": None,
        "blocked_action_scope": None,
        "quota": {
            "compute": 1.0,
            "window_hours": 24,
            "slot_minutes": 1,
            "spent_slots": spent_slots,
            "allowed_slots": 1440,
        },
    }


def _preview(**updates: object) -> dict[str, object]:
    return {
        "ok": True,
        "mode": "spend-slot",
        "dry_run": True,
        "goal_id": GOAL_ID,
        "slots": 1,
        "agent_id": AGENT_ID,
        "appended": False,
        "registry_mutated": False,
        "before": _decision(0),
        "after": _decision(1),
        "delivery_completion_spend": False,
        "safe_bypass_spend": False,
        "delivery_workspace_validated": False,
        **updates,
    }


def _commit(runtime_root: Path, preview: dict[str, object]) -> dict[str, object]:
    return record_quota_slot_spend_from_preview(
        preview,
        {"runtime_root": str(runtime_root)},
        goal_id=GOAL_ID,
        execute=True,
        source="heartbeat",
    )


def test_python_facade_uses_typed_event_and_durable_transaction(
    tmp_path: Path,
) -> None:
    preview = _preview()
    record = build_quota_slot_spend_event(
        preview,
        source="heartbeat",
        generated_at="2026-08-25T12:00:00+08:00",
    )
    assert record["classification"] == "quota_slot_spent"
    assert record["quota_spend_commit"]["schema_version"] == (
        "quota_spend_commit_receipt_v0"
    )
    assert record["quota_event"]["accounting_projection"] == {
        "schema_version": "quota_slot_accounting_projection_v0",
        "settlement_event_semantics": "append_only",
        "spent_slots_semantics": "rolling_window_aggregate",
        "before_after_semantics": "same_status_payload_projection",
        "window_hours": 24,
    }
    assert "does not replay or undo" in record["quota_event"]["rolling_window_note"]

    written = _commit(tmp_path, preview)
    assert written["appended"] is True
    assert written["idempotent_replay"] is False
    persisted = json.loads(Path(written["json_path"]).read_text(encoding="utf-8"))
    assert persisted["quota_spend_commit"]["effect_id"] == written["effect_id"]
    assert (
        persisted["quota_event"]["accounting_projection"]
        == written["accounting_projection"]
    )
    assert (
        persisted["quota_event"]["rolling_window_note"]
        == written["rolling_window_note"]
    )
    assert "settlement_event=append_only" in Path(written["markdown_path"]).read_text(
        encoding="utf-8"
    )
    assert Path(written["markdown_path"]).read_text(encoding="utf-8") == (
        render_quota_slot_preview_markdown(written) + "\n"
    )
    index_rows = Path(written["index_path"]).read_text(encoding="utf-8").splitlines()
    assert len(index_rows) == 1

    replayed = _commit(tmp_path, preview)
    assert replayed["appended"] is False
    assert replayed["idempotent_replay"] is True
    assert Path(written["index_path"]).read_text(encoding="utf-8").splitlines() == (
        index_rows
    )


def test_python_facade_serializes_concurrent_exact_effect_retries(
    tmp_path: Path,
) -> None:
    preview = _preview(effect_ref="provider-effect#quota_spend")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _commit(tmp_path, preview), range(2)))

    assert sorted(result["appended"] for result in results) == [False, True]
    assert sum(bool(result["idempotent_replay"]) for result in results) == 1
    index_path = Path(results[0]["index_path"])
    assert len(index_path.read_text(encoding="utf-8").splitlines()) == 1


def test_python_facade_rejects_malformed_and_semantically_invalid_requests(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="after.spent_slots"):
        _commit(tmp_path, _preview(after=_decision(2)))
    with pytest.raises(ValueError, match="source must be one of"):
        record_quota_slot_spend_from_preview(
            _preview(),
            {"runtime_root": str(tmp_path)},
            goal_id=GOAL_ID,
            execute=True,
            source="invalid",
        )
    with pytest.raises(ValueError, match="does not match commit goal_id"):
        record_quota_slot_spend_from_preview(
            _preview(),
            {"runtime_root": str(tmp_path)},
            goal_id="other-goal",
            execute=True,
        )


def test_python_facade_rejects_unsafe_goal_before_filesystem_effect(
    tmp_path: Path,
) -> None:
    unsafe_goal_id = "../outside"
    with pytest.raises(ValueError, match="single path segment"):
        record_quota_slot_spend_from_preview(
            _preview(goal_id=unsafe_goal_id),
            {"runtime_root": str(tmp_path)},
            goal_id=unsafe_goal_id,
            execute=True,
        )
    assert not (tmp_path / "goals").exists()
