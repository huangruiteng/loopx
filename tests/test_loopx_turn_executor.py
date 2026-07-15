from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    build_loopx_turn_plan,
    load_loopx_turn_plan_from_journal,
    run_loopx_turn_once,
    validate_loopx_turn_host_result,
)
from loopx.control_plane.turn_driver.executor import BuiltInHostError


def _plan() -> dict[str, object]:
    return build_loopx_turn_plan(
        {
            "ok": True,
            "schema_version": "loopx_turn_envelope_v0",
            "goal_id": "fixture-goal",
            "agent_id": "codex-fixture",
            "should_run": True,
            "effective_action": "normal_run",
            "action": {
                "must_attempt": True,
                "delivery_allowed": True,
                "quiet_noop_allowed": False,
                "selected_todo": {
                    "todo_id": "todo_fixture0001",
                    "text": "Advance one public fixture",
                },
            },
            "user": {"action_required": False, "open_count": 0, "notify": "DONT_NOTIFY"},
            "writeback": {"spend_after_validation": True},
            "scheduler": {"action": "run_now"},
            "action_signature": {
                "matches": True,
                "source_hash": "sha256:fixture",
                "envelope_hash": "sha256:fixture",
            },
            "compaction": {"within_budget": True},
        },
        host="generic-cli",
        execution_mode="isolated-headless",
    )


def _host_result(plan: dict[str, object], *, kind: str = "validated_progress") -> dict[str, object]:
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    result: dict[str, object] = {
        "schema_version": LOOPX_TURN_RESULT_SCHEMA_VERSION,
        "turn_key": transaction["turn_key"],
        "result_kind": kind,
        "completed_phases": ["host_execute", "typed_result"],
    }
    if kind == "validated_progress":
        result.update(
            classification="fixture_progress",
            recommended_action="Continue the public fixture",
            next_action="Run the next public fixture check",
            delivery_batch_scale="implementation",
            delivery_outcome="outcome_progress",
            vision_unchanged_reason="The fixture objective is unchanged after validated progress.",
            summary="One public fixture advanced.",
        )
    return result


def _host_argv(result_path: Path, count_path: Path) -> list[str]:
    script = """
import json
import pathlib
import sys
request = json.load(sys.stdin)
result = json.loads(pathlib.Path(sys.argv[1]).read_text())
result["turn_key"] = request["turn_key"]
count = pathlib.Path(sys.argv[2])
count.write_text(str(int(count.read_text()) + 1 if count.exists() else 1))
json.dump(result, sys.stdout)
"""
    return [sys.executable, "-c", script, str(result_path), str(count_path)]


def _callbacks(calls: dict[str, int]):
    def writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True, "classification": "fixture_progress"}

    def spend() -> dict[str, object]:
        calls["spend"] += 1
        return {"ok": True, "appended": True, "slots": 1}

    def scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": False, "disposition": "not_required"}

    return writeback, spend, scheduler


def _passing_validator(
    _plan: dict[str, object],
    _result: dict[str, object],
) -> dict[str, object]:
    return {
        "status": "passed",
        "validator_kind": "fixture",
        "summary": "independent fixture postconditions passed",
    }


def test_host_result_requires_bounded_public_material_fields() -> None:
    plan = _plan()
    result = _host_result(plan)
    result["raw_trajectory"] = "not allowed"

    validation = validate_loopx_turn_host_result(plan, result)

    assert validation["ok"] is False
    assert "unsupported host result fields" in " ".join(validation["errors"])


def test_run_once_preview_has_no_host_or_journal_effects(tmp_path: Path) -> None:
    plan = _plan()

    payload = run_loopx_turn_once(
        plan,
        host_argv=[sys.executable, "-c", "raise SystemExit(9)"],
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=False,
    )

    assert payload["ok"] is True
    assert payload["status"] == "preview"
    assert payload["effects"] == {
        "host_invoked": False,
        "state_written": False,
        "quota_spent": False,
        "scheduler_acknowledged": False,
    }
    assert not (tmp_path / "runtime").exists()


def test_run_once_rejects_oversized_built_in_host_result(tmp_path: Path) -> None:
    plan = _plan()
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)
    oversized = _host_result(plan)
    oversized["summary"] = "x" * 13_000

    payload = run_loopx_turn_once(
        plan,
        host_runner=lambda _request: oversized,
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )

    assert payload["ok"] is False
    assert payload["reason"] == "built-in host result exceeded the result budget"
    assert calls == {"writeback": 0, "spend": 0, "scheduler": 0}


def test_run_once_explicitly_retries_failed_host_without_duplicate_effects(tmp_path: Path) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        if calls["host"] == 1:
            raise BuiltInHostError("codex_cli_model_requires_newer_codex")
        return _host_result(plan)

    kwargs = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
    }
    failed = run_loopx_turn_once(plan, **kwargs)
    replayed = run_loopx_turn_once(plan, **kwargs)
    recovered = run_loopx_turn_once(plan, retry_failed=True, **kwargs)

    assert failed["reason"] == "codex_cli_model_requires_newer_codex"
    assert replayed["replayed"] is True
    assert recovered["status"] == "committed"
    assert calls == {"host": 2, "writeback": 1, "spend": 1, "scheduler": 1}


def test_run_once_commits_once_and_replays_without_duplicate_effects(tmp_path: Path) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    count_path = tmp_path / "host-count"
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)
    kwargs = {
        "host_argv": _host_argv(result_path, count_path),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
    }

    first = run_loopx_turn_once(plan, **kwargs)
    replay = run_loopx_turn_once(plan, **kwargs)

    assert first["ok"] is True
    assert first["status"] == "committed"
    assert first["receipt"]["status"] == "committed"
    assert first["effects"]["host_invoked"] is True
    assert first["effects"]["state_written"] is True
    assert first["effects"]["quota_spent"] is True
    assert replay["replayed"] is True
    assert not any(replay["effects"].values())
    assert count_path.read_text(encoding="utf-8") == "1"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}


def test_run_once_recovers_after_process_exit_before_writeback(tmp_path: Path) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    count_path = tmp_path / "host-count"
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    healthy_writeback, spend, scheduler = _callbacks(calls)

    def interrupted_writeback(_result: dict[str, object]) -> dict[str, object]:
        raise SystemExit(7)

    common = {
        "host_argv": _host_argv(result_path, count_path),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "spend": spend,
        "scheduler": scheduler,
    }
    with pytest.raises(SystemExit):
        run_loopx_turn_once(plan, writeback=interrupted_writeback, **common)

    recovered = run_loopx_turn_once(plan, writeback=healthy_writeback, **common)

    assert recovered["status"] == "committed"
    assert count_path.read_text(encoding="utf-8") == "1"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}


def test_run_once_resumes_after_writeback_without_duplicate_effects(tmp_path: Path) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    count_path = tmp_path / "host-count"
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, healthy_spend, scheduler = _callbacks(calls)

    def interrupted_spend() -> dict[str, object]:
        raise SystemExit(8)

    common = {
        "host_argv": _host_argv(result_path, count_path),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "scheduler": scheduler,
    }
    with pytest.raises(SystemExit):
        run_loopx_turn_once(plan, spend=interrupted_spend, **common)

    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    resumed_plan = load_loopx_turn_plan_from_journal(
        tmp_path / "runtime",
        goal_id="fixture-goal",
        turn_key=str(transaction["turn_key"]),
    )
    recovered = run_loopx_turn_once(resumed_plan, spend=healthy_spend, **common)

    assert recovered["status"] == "committed"
    assert count_path.read_text(encoding="utf-8") == "1"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}


def test_run_once_fails_closed_without_independent_task_validator(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    payload = run_loopx_turn_once(
        plan,
        host_runner=lambda _request: _host_result(plan),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )

    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["result_kind"] == "validation_failed"
    assert payload["validation"]["status"] == "unavailable"
    assert payload["validation"]["recovery_kind"] == "repair_required"
    assert payload["receipt"]["failed_phase"] == "validation"
    assert payload["receipt"]["completed_phases"] == ["host_execute", "typed_result"]
    assert calls == {"writeback": 0, "spend": 0, "scheduler": 0}


def test_run_once_retries_task_validation_without_reinvoking_host(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def reject(
        _plan: dict[str, object],
        _result: dict[str, object],
    ) -> dict[str, object]:
        return {
            "status": "failed",
            "validator_kind": "fixture",
            "summary": "independent fixture postcondition is absent",
            "recovery_kind": "replan_required",
        }

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
    }
    failed = run_loopx_turn_once(plan, task_validator=reject, **common)
    recovered = run_loopx_turn_once(
        plan,
        task_validator=_passing_validator,
        retry_failed=True,
        **common,
    )

    assert failed["result_kind"] == "validation_failed"
    assert failed["validation"]["recovery_kind"] == "replan_required"
    assert recovered["status"] == "committed"
    assert recovered["effects"]["host_invoked"] is False
    assert calls == {"host": 1, "writeback": 1, "spend": 1, "scheduler": 1}


def test_material_result_cannot_use_not_required_validation_receipt(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    payload = run_loopx_turn_once(
        plan,
        host_runner=lambda _request: _host_result(plan),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        task_validator=lambda _plan, _result: {
            "status": "not_required",
            "validator_kind": "fixture",
            "summary": "skip validation",
        },
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )

    assert payload["result_kind"] == "validation_failed"
    assert payload["validation"]["status"] == "inconclusive"
    assert "cannot skip" in payload["validation"]["summary"]
    assert calls == {"writeback": 0, "spend": 0, "scheduler": 0}


def test_run_once_stops_without_writeback_or_spend(tmp_path: Path) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan, kind="wait")), encoding="utf-8")
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    payload = run_loopx_turn_once(
        plan,
        host_argv=_host_argv(result_path, tmp_path / "host-count"),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )

    assert payload["ok"] is True
    assert payload["status"] == "stopped"
    assert payload["receipt"]["status"] == "stopped"
    assert calls == {"writeback": 0, "spend": 0, "scheduler": 0}


def test_run_once_projects_scheduler_action_without_false_ack(tmp_path: Path) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, _scheduler = _callbacks(calls)

    def scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": False, "apply_needed": True, "disposition": "host_action_required"}

    payload = run_loopx_turn_once(
        plan,
        host_argv=_host_argv(result_path, tmp_path / "host-count"),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        task_validator=_passing_validator,
        writeback=writeback,
        spend=spend,
        scheduler=scheduler,
    )

    assert payload["ok"] is True
    assert payload["status"] == "scheduler_action_required"
    assert payload["receipt"]["next_phase"] == "scheduler_apply"
    assert payload["effects"]["scheduler_acknowledged"] is False


def test_run_once_resumes_scheduler_without_repeating_committed_effects(
    tmp_path: Path,
) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    count_path = tmp_path / "host-count"
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, _scheduler = _callbacks(calls)

    def scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        if calls["scheduler"] == 1:
            return {
                "completed": False,
                "apply_needed": True,
                "disposition": "host_action_required",
            }
        return {
            "completed": True,
            "acknowledged": True,
            "disposition": "applied_and_acknowledged",
        }

    kwargs = {
        "host_argv": _host_argv(result_path, count_path),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
    }
    first = run_loopx_turn_once(plan, **kwargs)
    resumed = run_loopx_turn_once(plan, **kwargs)

    assert first["status"] == "scheduler_action_required"
    assert resumed["status"] == "committed"
    assert resumed["effects"]["scheduler_acknowledged"] is True
    assert count_path.read_text(encoding="utf-8") == "1"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 2}
