"""Coarse production-call and compact transport contracts for delivery history."""
from copy import deepcopy
import json

import pytest

from loopx import status
from loopx.control_plane.work_items import delivery_history


def test_status_selects_one_bounded_history_batch_before_crossing(monkeypatch) -> None:
    calls = []
    actual = delivery_history.effect_runtime_result

    def record(method, request):
        calls.append(request)
        return actual(method, request)

    monkeypatch.setattr(delivery_history, "effect_runtime_result", record)
    runs = [{"generated_at": f"2026-09-01T00:00:{i:02d}Z", "classification": "custom_delivery",
             "delivery_outcome": "surface_only", "delivery_batch_scale": "test_only"} for i in range(50)]
    before = deepcopy(runs)
    result = status.project_asset_handoff_state(ready=True,
        project_asset={"execution_profile": {"outcome_floor": {"outcome_markers": ["merged"]}}},
        latest_runs=runs)
    assert len(calls) == 1
    assert len(calls[0]["runs"]) == 3
    assert result["post_handoff_small_scale_streak"] == 3
    assert result["post_handoff_outcome_gap_streak"] == 3
    assert result["post_handoff_latest_run"]["generated_at"].endswith("49Z")
    assert len(result["post_handoff_recent_runs"]) == 3
    assert runs == before


def test_huge_untrusted_fields_do_not_enter_the_decision_request(monkeypatch) -> None:
    calls = []
    actual = delivery_history.effect_runtime_result

    def record(method, request):
        calls.append(request)
        return actual(method, request)

    monkeypatch.setattr(delivery_history, "effect_runtime_result", record)
    run = {"delivery_outcome": "surface_only", "classification": "Display label", "health_check": "x" * 3_000_000,
           "recommended_action": "x" * 3_000_000, "compact_evidence": {"raw": "x" * 3_000_000},
           "progress_observation": {"payload": "x" * 3_000_000}}
    result = delivery_history.project_delivery_history([run])
    assert len(json.dumps(calls[0])) < 1_000
    assert "classification" not in calls[0]["runs"][0]
    assert result["runs"][0]["outcome_followthrough"]["latest_classification"] == "Display label"
    run["classification"] = "a different narrative" * 100_000
    delivery_history.project_delivery_history([run])
    assert calls[0] == calls[1]


@pytest.mark.parametrize("identity", ["a" * 3_000_000, "a" * 128 + " " * 200 + "b"])
def test_oversized_typed_values_stay_invalid_after_compaction(identity) -> None:
    run = {"delivery_outcome": "outcome_gap", "todo_id": identity,
           "progress_observation": {"schema_version": "typed_progress_observation_v0", "result_class": "blocked",
               "work_item_id": identity, "blocker_id": "blocker-a", "evidence_ids": ["evidence-a"]}}
    signal = delivery_history.project_delivery_history([run])["runs"][0]
    assert signal["delivery_turn_kind"] == "outcome_gap"
    assert signal["outcome_followthrough"]["required"] is True


def test_truncated_enum_cannot_alias_a_valid_prefix_after_trim() -> None:
    signal = delivery_history.project_delivery_history([{
        "delivery_outcome": "primary_goal_outcome" + " " * 200 + "invalid",
        "delivery_turn_kind": "blocker_writeback" + " " * 200 + "invalid",
        "delivery_batch_scale": "implementation" + " " * 200 + "invalid",
        "outcome_followthrough_required": True,
    }])["runs"][0]
    assert signal["delivery_outcome"] == "unknown"
    assert signal["delivery_turn_kind"] == "unknown"
    assert signal["delivery_batch_scale"] == "unknown"
    assert signal["outcome_followthrough"]["required"] is True


def test_empty_status_history_does_not_start_runtime(monkeypatch) -> None:
    def unexpected(*_args, **_kwargs):
        raise AssertionError("empty history needs no runtime")

    monkeypatch.setattr(delivery_history, "effect_runtime_result", unexpected)
    assert status.project_post_handoff_history([]) == {}


def test_unavailable_runtime_never_falls_back_to_python_classification(monkeypatch) -> None:
    def unavailable(*_args, **_kwargs):
        raise RuntimeError("isolated unavailable runtime")

    monkeypatch.setattr(delivery_history, "effect_runtime_result", unavailable)
    rows = [{"delivery_outcome": "surface_only"}]
    with pytest.raises(RuntimeError, match="isolated unavailable runtime"):
        delivery_history.project_delivery_history(rows)


@pytest.mark.parametrize("result", [None, {}, {"schema_version": "delivery_history_v0", "runs": []}])
def test_invalid_response_cannot_silently_drop_history(monkeypatch, result) -> None:
    monkeypatch.setattr(delivery_history, "effect_runtime_result", lambda *_args: result)
    rows = [{"delivery_outcome": "surface_only"}]
    with pytest.raises(RuntimeError, match="shape mismatch"):
        delivery_history.project_delivery_history(rows)
