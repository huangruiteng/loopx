from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from loopx.control_plane.turn_driver import (
    LOOPX_TURN_RESULT_SCHEMA_VERSION,
    TurnEffectEnvelope,
    TurnLeaseController,
    build_loopx_turn_plan,
    load_turn_events,
    load_loopx_turn_plan_from_journal,
    rebuild_turn_projection,
    run_loopx_turn_once as _run_loopx_turn_once,
    validate_loopx_turn_host_result,
)
from loopx.control_plane.work_items.task_lease import inspect_task_lease
from loopx.control_plane.work_items.task_lease import transfer_task_lease
from loopx.control_plane.turn_driver.executor import BuiltInHostError
from loopx.control_plane.turn_driver.settlement import execute_turn_driver_settlement
from loopx.control_plane.turn_driver.transaction import TRANSACTION_PHASES


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


def _adaptive_plan() -> dict[str, object]:
    plan = _plan()
    envelope = plan["turn_envelope"]
    assert isinstance(envelope, dict)
    envelope["action"]["selected_todo"] = {"todo_id": "todo-stale"}
    envelope["task_orchestration_contract"] = {
        "schema_version": "task_orchestration_contract_v2",
        "mode": "adaptive",
        "primary_todo_id": "todo_fixture0001",
    }
    return build_loopx_turn_plan(
        envelope,
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
    if kind in {"validated_progress", "validated_completion"}:
        result.update(
            classification=(
                "fixture_progress"
                if kind == "validated_progress"
                else "fixture_completion"
            ),
            recommended_action=(
                "Continue the public fixture."
                if kind == "validated_progress"
                else "Refresh the active goal after this Todo completion."
            ),
            next_action=(
                "Run the next public fixture check."
                if kind == "validated_progress"
                else "Select the next Todo from a fresh decision."
            ),
            delivery_batch_scale="implementation",
            delivery_outcome="outcome_progress",
            vision_unchanged_reason="The fixture objective is unchanged after validated progress.",
            summary=(
                "One public fixture advanced."
                if kind == "validated_progress"
                else "One public fixture completed."
            ),
        )
    return result


def test_typed_settlement_fails_closed_when_journal_receipt_payload_is_missing() -> None:
    transaction = _plan()["transaction"]
    assert isinstance(transaction, dict)
    calls = {"writeback": 0, "spend": 0, "checkpoint": 0}

    result = execute_turn_driver_settlement(
        transaction,
        transaction_phases=TRANSACTION_PHASES,
        completed_phases=TRANSACTION_PHASES[:4],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda: calls.__setitem__("writeback", calls["writeback"] + 1)
        or {"ok": True, "appended": True},
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        checkpoint=lambda _kind, _payload, _phases: calls.__setitem__(
            "checkpoint", calls["checkpoint"] + 1
        ),
    )

    assert result.failure is not None
    assert result.failure.kind.value == "receipt_missing"
    assert result.failure.step_kind.value == "durable_writeback"
    assert [receipt.step_kind.value for receipt in result.receipts] == ["validation"]
    assert calls == {"writeback": 0, "spend": 0, "checkpoint": 0}


def test_typed_settlement_fails_closed_when_plan_has_no_settlement_plan() -> None:
    transaction = _plan()["transaction"]
    assert isinstance(transaction, dict)
    legacy = {
        key: value
        for key, value in transaction.items()
        if key != "settlement_plan"
    }
    calls = {"writeback": 0, "spend": 0, "checkpoint": 0}

    result = execute_turn_driver_settlement(
        legacy,
        transaction_phases=TRANSACTION_PHASES,
        completed_phases=TRANSACTION_PHASES[:3],
        writeback_payload=None,
        quota_spend_payload=None,
        writeback=lambda: calls.__setitem__("writeback", calls["writeback"] + 1)
        or {"ok": True, "appended": True},
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        checkpoint=lambda _kind, _payload, _phases: calls.__setitem__(
            "checkpoint", calls["checkpoint"] + 1
        ),
    )

    assert result.failure is not None
    assert result.failure.kind.value == "receipt_missing"
    assert result.failure.step_kind.value == "validation"
    assert "typed settlement plan" in result.failure.reason
    assert result.receipts == ()
    assert calls == {"writeback": 0, "spend": 0, "checkpoint": 0}


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


def _journal(runtime_root: Path) -> dict[str, object]:
    journal_paths = list(
        (runtime_root / "goals" / "fixture-goal" / "turn-journals").glob("*.jsonl")
    )
    assert len(journal_paths) == 1
    turn_key = f"sha256:{journal_paths[0].stem}"
    events = load_turn_events(runtime_root, "fixture-goal", turn_key)
    states = [
        event["payload"]["state"]
        for event in events
        if isinstance(event.get("payload"), dict)
        and isinstance(event["payload"].get("state"), dict)
    ]
    assert states
    return states[-1]


def _passing_validator(
    _plan: dict[str, object],
    _result: dict[str, object],
) -> dict[str, object]:
    return {
        "status": "passed",
        "validator_kind": "fixture",
        "summary": "independent fixture postconditions passed",
    }


def _write_lease_registry(tmp_path: Path) -> Path:
    state = tmp_path / "ACTIVE_GOAL_STATE.md"
    state.write_text(
        "\n".join(
            [
                "---",
                "status: active",
                "updated_at: 2026-01-01T00:00:00+00:00",
                "---",
                "",
                "# Fixture Goal",
                "",
                "## Agent Todo",
                "",
                "- [ ] [P0] Advance one public fixture.",
                "  <!-- loopx:todo todo_id=todo_fixture0001 status=open "
                "claimed_by=codex-fixture priority=P0 -->",
                "",
            ]
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "common_runtime_root": str(tmp_path / "runtime"),
                "goals": [
                    {
                        "id": "fixture-goal",
                        "status": "active",
                        "repo": str(tmp_path),
                        "state_file": state.name,
                        "coordination": {
                            "registered_agents": ["codex-fixture"],
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return registry


_TURN_CONTROLLERS: dict[tuple[str, str], TurnLeaseController] = {}


def run_loopx_turn_once(
    plan: dict[str, object],
    **kwargs: object,
) -> dict[str, object]:
    if kwargs.get("execute") is True and "lease_controller" not in kwargs:
        runtime_root = kwargs.get("runtime_root")
        assert isinstance(runtime_root, Path)
        transaction = plan.get("transaction")
        assert isinstance(transaction, dict)
        turn_key = str(transaction["turn_key"])
        key = (str(runtime_root), turn_key)
        controller = _TURN_CONTROLLERS.get(key)
        if controller is None:
            registry = _write_lease_registry(runtime_root.parent)
            controller = TurnLeaseController(
                registry_path=registry,
                runtime_root=runtime_root,
                goal_id="fixture-goal",
                todo_id="todo_fixture0001",
                owner="codex-fixture",
                idempotency_key=f"turn:{turn_key}",
                write_scopes=["docs/**"],
                ttl_seconds=120,
            )
            _TURN_CONTROLLERS[key] = controller
        kwargs["lease_controller"] = controller
    return _run_loopx_turn_once(plan, **kwargs)


def test_turn_lease_controller_preserves_fence_across_renew_and_release(
    tmp_path: Path,
) -> None:
    registry = _write_lease_registry(tmp_path)
    controller = TurnLeaseController(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key="turn:fixture",
        write_scopes=["docs/**"],
        ttl_seconds=120,
    )

    acquired = controller.acquire()
    renewed = controller.renew(acquired)
    controller.require_current(renewed)
    controller.release(renewed)

    assert renewed.token == acquired.token
    assert renewed.generation == acquired.generation
    assert renewed.version > acquired.version
    inspected = inspect_task_lease(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
    )
    assert inspected["active"] is False
    assert inspected["lease"]["status"] == "released"


def test_turn_lease_heartbeat_renews_without_changing_fencing_token(
    tmp_path: Path,
) -> None:
    registry = _write_lease_registry(tmp_path)
    controller = TurnLeaseController(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key="turn:fixture",
        write_scopes=["docs/**"],
        ttl_seconds=120,
        heartbeat_interval_seconds=0.01,
    )
    acquired = controller.acquire()

    with controller.heartbeat(acquired) as current:
        deadline = time.monotonic() + 1
        while current().version == acquired.version and time.monotonic() < deadline:
            time.sleep(0.005)
    renewed = current()

    assert renewed.version > acquired.version
    assert renewed.token == acquired.token
    assert renewed.generation == acquired.generation
    controller.release(renewed)


def test_turn_effect_guard_serializes_lease_transfer_with_effect_commit(
    tmp_path: Path,
) -> None:
    registry = _write_lease_registry(tmp_path)
    controller = TurnLeaseController(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key="turn:fixture:a",
        write_scopes=["docs/**"],
        ttl_seconds=120,
    )
    acquired = controller.acquire()
    effect_entered = threading.Event()
    allow_effect_exit = threading.Event()
    transfer_finished = threading.Event()

    def hold_effect() -> None:
        with controller.effect_guard(acquired):
            effect_entered.set()
            assert allow_effect_exit.wait(timeout=2)

    def transfer() -> None:
        transfer_task_lease(
            registry_path=registry,
            runtime_root=tmp_path / "runtime",
            goal_id="fixture-goal",
            todo_id="todo_fixture0001",
            owner="codex-fixture",
            idempotency_key="turn:fixture:a",
            new_owner="codex-fixture",
            new_idempotency_key="turn:fixture:b",
            expected_version=acquired.version,
        )
        transfer_finished.set()

    effect_thread = threading.Thread(target=hold_effect)
    effect_thread.start()
    assert effect_entered.wait(timeout=1)
    transfer_thread = threading.Thread(target=transfer)
    transfer_thread.start()
    time.sleep(0.05)

    assert transfer_finished.is_set() is False
    allow_effect_exit.set()
    effect_thread.join(timeout=2)
    transfer_thread.join(timeout=2)
    assert transfer_finished.is_set() is True


def test_run_once_rejects_stale_worker_after_lease_transfer(
    tmp_path: Path,
) -> None:
    plan = _plan()
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    turn_key = str(transaction["turn_key"])
    registry = _write_lease_registry(tmp_path)
    runtime_root = tmp_path / "runtime"
    controller_a = TurnLeaseController(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=f"turn:{turn_key}:a",
        write_scopes=["docs/**"],
        ttl_seconds=120,
    )
    controller_b = TurnLeaseController(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=f"turn:{turn_key}:b",
        write_scopes=["docs/**"],
        ttl_seconds=120,
    )
    host_a_entered = threading.Event()
    release_host_a = threading.Event()
    b_after_scheduler_apply = threading.Event()
    release_worker_b = threading.Event()
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    results: dict[str, dict[str, object]] = {}

    def host_a(_request: dict[str, object]) -> dict[str, object]:
        host_a_entered.set()
        assert release_host_a.wait(timeout=3)
        result = _host_result(plan)
        result["summary"] = "Worker A stale result must never be journaled."
        return result

    def host_b(_request: dict[str, object]) -> dict[str, object]:
        result = _host_result(plan)
        result["summary"] = "Worker B owns the durable result."
        return result

    def writeback(
        envelope: TurnEffectEnvelope,
        _result: dict[str, object],
    ) -> dict[str, object]:
        assert envelope.phase_key == f"{turn_key}:durable_writeback"
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def spend(envelope: TurnEffectEnvelope) -> dict[str, object]:
        assert envelope.phase_key == f"{turn_key}:quota_spend"
        calls["spend"] += 1
        return {"ok": True, "appended": True}

    def scheduler(
        envelope: TurnEffectEnvelope,
        _spend: dict[str, object],
    ) -> dict[str, object]:
        assert envelope.phase_key == f"{turn_key}:scheduler_apply"
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": True}

    common = {
        "project": tmp_path,
        "runtime_root": runtime_root,
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "spend": spend,
        "scheduler": scheduler,
    }

    def run_a() -> None:
        results["a"] = run_loopx_turn_once(
            plan,
            host_runner=host_a,
            lease_controller=controller_a,
            **common,
        )

    def pause_b(phase: str) -> None:
        if phase == "after_scheduler_apply":
            b_after_scheduler_apply.set()
            assert release_worker_b.wait(timeout=3)

    def run_b() -> None:
        results["b"] = run_loopx_turn_once(
            plan,
            host_runner=host_b,
            lease_controller=controller_b,
            fault_injector=pause_b,
            **common,
        )

    worker_a = threading.Thread(target=run_a)
    worker_a.start()
    assert host_a_entered.wait(timeout=2)
    active = inspect_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
    )["lease"]
    assert isinstance(active, dict)
    transfer_task_lease(
        registry_path=registry,
        runtime_root=runtime_root,
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=f"turn:{turn_key}:a",
        new_owner="codex-fixture",
        new_idempotency_key=f"turn:{turn_key}:b",
        expected_version=int(active["version"]),
    )
    worker_b = threading.Thread(target=run_b)
    worker_b.start()
    assert b_after_scheduler_apply.wait(timeout=2)
    release_host_a.set()
    worker_a.join(timeout=2)

    assert results["a"]["status"] == "failed_closed"
    assert results["a"]["reason_code"] == "stale_fencing_token"
    release_worker_b.set()
    worker_b.join(timeout=2)
    assert results["b"]["status"] == "committed"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}
    events = load_turn_events(runtime_root, "fixture-goal", turn_key)
    assert "Worker A stale result" not in json.dumps(events)
    projection = rebuild_turn_projection(runtime_root, "fixture-goal", turn_key)
    assert projection["fencing_token"] == results["b"]["fencing_token"]


@pytest.mark.parametrize(
    "crash_phase",
    [
        "after_host",
        "after_validation",
        "after_writeback",
        "after_spend",
        "after_scheduler_apply",
    ],
)
def test_run_once_resumes_after_each_durable_phase_without_duplicate_effects(
    tmp_path: Path,
    crash_phase: str,
) -> None:
    plan = _plan()
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    turn_key = str(transaction["turn_key"])
    registry = _write_lease_registry(tmp_path)
    controller = TurnLeaseController(
        registry_path=registry,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        todo_id="todo_fixture0001",
        owner="codex-fixture",
        idempotency_key=f"turn:{turn_key}",
        write_scopes=["docs/**"],
        ttl_seconds=120,
    )
    calls = {"host": 0, "writeback": 0, "spend": 0, "scheduler": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def writeback(
        _envelope: TurnEffectEnvelope,
        _result: dict[str, object],
    ) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def spend(_envelope: TurnEffectEnvelope) -> dict[str, object]:
        calls["spend"] += 1
        return {"ok": True, "appended": True}

    def scheduler(
        _envelope: TurnEffectEnvelope,
        _spend: dict[str, object],
    ) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": True}

    def crash_after_persisted_phase(phase: str) -> None:
        if phase == crash_phase:
            raise SystemExit(91)

    common = {
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
        "lease_controller": controller,
    }
    with pytest.raises(SystemExit, match="91"):
        run_loopx_turn_once(
            plan,
            fault_injector=crash_after_persisted_phase,
            **common,
        )

    recovered = run_loopx_turn_once(plan, **common)

    assert recovered["status"] == "committed"
    assert calls == {"host": 1, "writeback": 1, "spend": 1, "scheduler": 1}


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
    assert failed["result_kind"] == "host_failure"
    assert failed["receipt"]["result_kind"] == "host_failure"
    assert failed["receipt"]["failed_phase"] == "host_execute"
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
    assert [
        receipt["step_kind"]
        for receipt in first["settlement_result"]["receipts"]
    ] == ["validation", "durable_writeback", "quota_spend"]
    assert first["effects"]["host_invoked"] is True
    assert first["effects"]["state_written"] is True
    assert first["effects"]["quota_spent"] is True
    assert replay["replayed"] is True
    assert not any(replay["effects"].values())
    assert count_path.read_text(encoding="utf-8") == "1"
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}


def test_run_once_legacy_plan_without_settlement_plan_is_upgraded(
    tmp_path: Path,
) -> None:
    plan = _plan()
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    transaction.pop("settlement_plan", None)
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(_host_result(plan)), encoding="utf-8")
    count_path = tmp_path / "host-count"
    calls = {"writeback": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    committed = run_loopx_turn_once(
        plan,
        host_argv=_host_argv(result_path, count_path),
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

    assert committed["ok"] is True
    assert committed["status"] == "committed"
    assert committed["receipt"]["status"] == "committed"
    assert committed["settlement_result"]["ok"] is True
    assert (
        [
            receipt["step_kind"]
            for receipt in committed["settlement_result"]["receipts"]
        ]
        == ["validation", "durable_writeback", "quota_spend"]
    )
    assert calls == {"writeback": 1, "spend": 1, "scheduler": 1}


def test_adaptive_completion_upgrades_legacy_plan_with_primary_todo_identity(
    tmp_path: Path,
) -> None:
    plan = _adaptive_plan()
    transaction = plan["transaction"]
    assert isinstance(transaction, dict)
    transaction.pop("settlement_plan", None)
    calls = {"completion": 0, "spend": 0, "scheduler": 0}

    def completion_writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["completion"] += 1
        return {
            "ok": True,
            "appended": True,
            "completion": {
                "todo_id": "todo_fixture0001",
                "continuation": "active_goal",
            },
        }

    committed = run_loopx_turn_once(
        plan,
        host_runner=lambda _request: _host_result(
            plan,
            kind="validated_completion",
        ),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        task_validator=_passing_validator,
        writeback=lambda _result: {"ok": True, "appended": True},
        completion_writeback=completion_writeback,
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        scheduler=lambda _spend: calls.__setitem__(
            "scheduler", calls["scheduler"] + 1
        )
        or {"completed": True, "acknowledged": True},
    )

    assert committed["status"] == "committed"
    assert committed["receipt"]["lineage"]["todo_id"] == "todo_fixture0001"
    assert calls == {"completion": 1, "spend": 1, "scheduler": 1}


def test_validated_completion_requires_explicit_lifecycle_writeback(
    tmp_path: Path,
) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(_host_result(plan, kind="validated_completion")),
        encoding="utf-8",
    )
    calls = {"writeback": 0, "completion": 0, "spend": 0, "scheduler": 0}

    def writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def spend() -> dict[str, object]:
        calls["spend"] += 1
        return {"ok": True, "appended": True}

    def scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": True}

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

    assert payload["result_kind"] == "validation_failed"
    assert payload["receipt"]["failed_phase"] == "validation"
    assert calls == {"writeback": 0, "completion": 0, "spend": 0, "scheduler": 0}


def test_validated_completion_commits_once_with_lifecycle_outcome(
    tmp_path: Path,
) -> None:
    plan = _plan()
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(_host_result(plan, kind="validated_completion")),
        encoding="utf-8",
    )
    calls = {"writeback": 0, "completion": 0, "spend": 0, "scheduler": 0}
    writeback, spend, scheduler = _callbacks(calls)

    def completion_writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["completion"] += 1
        return {
            "ok": True,
            "appended": True,
            "completion": {
                "todo_id": "todo_fixture0001",
                "continuation": "active_goal",
            },
        }

    kwargs = {
        "host_argv": _host_argv(result_path, tmp_path / "host-count"),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "completion_writeback": completion_writeback,
        "spend": spend,
        "scheduler": scheduler,
    }
    first = run_loopx_turn_once(plan, **kwargs)
    replay = run_loopx_turn_once(plan, **kwargs)

    assert first["status"] == "committed"
    assert first["effects"]["state_written"] is True
    assert first["effects"]["quota_spent"] is True
    assert replay["replayed"] is True
    assert not any(replay["effects"].values())
    assert calls == {"writeback": 0, "completion": 1, "spend": 1, "scheduler": 1}
    assert _journal(tmp_path / "runtime")["writeback"]["completion"] == {
        "todo_id": "todo_fixture0001",
        "continuation": "active_goal",
    }


def test_invalid_completion_outcome_fails_closed_without_spending(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"completion": 0, "spend": 0, "scheduler": 0}
    writeback, _spend, _scheduler = _callbacks(calls)

    def completion_writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["completion"] += 1
        return {
            "ok": True,
            "appended": True,
            "completion": {"todo_id": "todo_other", "continuation": "active_goal"},
        }

    payload = run_loopx_turn_once(
        plan,
        host_runner=lambda _request: _host_result(plan, kind="validated_completion"),
        project=tmp_path,
        runtime_root=tmp_path / "runtime",
        goal_id="fixture-goal",
        timeout_seconds=5,
        execute=True,
        task_validator=_passing_validator,
        writeback=writeback,
        completion_writeback=completion_writeback,
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1) or {
            "ok": True,
            "appended": True,
        },
        scheduler=lambda _spend: calls.__setitem__("scheduler", calls["scheduler"] + 1)
        or {"completed": True, "acknowledged": True},
    )

    assert payload["result_kind"] == "writeback_failed"
    assert payload["receipt"]["result_kind"] == "writeback_failed"
    assert payload["receipt"]["failed_phase"] == "durable_writeback"
    assert payload["settlement_result"]["failure"]["kind"] == "writeback_rejected"
    assert calls == {"completion": 1, "spend": 0, "scheduler": 0}


def test_validated_completion_recovers_after_writeback_without_repeating_completion(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"completion": 0, "spend": 0, "scheduler": 0}

    def completion_writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["completion"] += 1
        return {
            "ok": True,
            "appended": True,
            "completion": {
                "todo_id": "todo_fixture0001",
                "continuation": "active_goal",
            },
        }

    def interrupted_spend() -> dict[str, object]:
        calls["spend"] += 1
        raise SystemExit(8)

    def scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": True}

    def healthy_spend() -> dict[str, object]:
        calls["spend"] += 1
        return {"ok": True, "appended": True}

    common = {
        "host_runner": lambda _request: _host_result(
            plan,
            kind="validated_completion",
        ),
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": lambda _result: {"ok": True, "appended": True},
        "completion_writeback": completion_writeback,
        "scheduler": scheduler,
    }
    with pytest.raises(SystemExit):
        run_loopx_turn_once(plan, spend=interrupted_spend, **common)

    recovered = run_loopx_turn_once(
        plan,
        spend=healthy_spend,
        **common,
    )

    assert recovered["status"] == "committed"
    assert calls == {"completion": 1, "spend": 2, "scheduler": 1}


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

    interrupted = _journal(tmp_path / "runtime")
    assert interrupted["completed_phases"] == [
        "host_execute",
        "typed_result",
        "validation",
    ]
    assert interrupted["task_validation"]["status"] == "passed"
    assert "writeback" not in interrupted

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

    interrupted = _journal(tmp_path / "runtime")
    assert interrupted["completed_phases"] == [
        "host_execute",
        "typed_result",
        "validation",
        "durable_writeback",
    ]
    assert interrupted["writeback"]["appended"] is True
    assert "quota_spend" not in interrupted

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


def test_cancellation_before_writeback_preserves_prefix_and_resumes(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def cancelled_writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        raise KeyboardInterrupt

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "spend": lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        "scheduler": lambda _spend: {"completed": True, "acknowledged": True},
    }
    with pytest.raises(KeyboardInterrupt):
        run_loopx_turn_once(plan, writeback=cancelled_writeback, **common)

    assert _journal(tmp_path / "runtime")["completed_phases"] == [
        "host_execute",
        "typed_result",
        "validation",
    ]
    recovered = run_loopx_turn_once(
        plan,
        writeback=lambda _result: calls.__setitem__(
            "writeback", calls["writeback"] + 1
        )
        or {"ok": True, "appended": True},
        **common,
    )

    assert recovered["status"] == "committed"
    assert calls == {"host": 1, "writeback": 2, "spend": 1}


def test_cancellation_during_scheduler_preserves_settlement_and_resumes(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0, "scheduler": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def spend() -> dict[str, object]:
        calls["spend"] += 1
        return {"ok": True, "appended": True}

    def cancelled_scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        raise KeyboardInterrupt

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "spend": spend,
    }
    with pytest.raises(KeyboardInterrupt):
        run_loopx_turn_once(plan, scheduler=cancelled_scheduler, **common)

    interrupted_journal = _journal(tmp_path / "runtime")
    assert interrupted_journal["completed_phases"] == [
        "host_execute",
        "typed_result",
        "validation",
        "durable_writeback",
        "quota_spend",
    ]
    assert [
        receipt["step_kind"]
        for receipt in interrupted_journal["settlement_result"]["receipts"]
    ] == ["validation", "durable_writeback", "quota_spend"]

    def healthy_scheduler(_spend: dict[str, object]) -> dict[str, object]:
        calls["scheduler"] += 1
        return {"completed": True, "acknowledged": True}

    recovered = run_loopx_turn_once(plan, scheduler=healthy_scheduler, **common)

    assert recovered["status"] == "committed"
    assert calls == {"host": 1, "writeback": 1, "spend": 1, "scheduler": 2}


def test_permission_denial_from_host_is_typed_and_explicitly_retried(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        if calls["host"] == 1:
            raise PermissionError("host denied")
        return _host_result(plan)

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": lambda _result: calls.__setitem__(
            "writeback", calls["writeback"] + 1
        )
        or {"ok": True, "appended": True},
        "spend": lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        "scheduler": lambda _spend: {"completed": True, "acknowledged": True},
    }
    failed = run_loopx_turn_once(plan, **common)
    replayed = run_loopx_turn_once(plan, **common)
    recovered = run_loopx_turn_once(plan, retry_failed=True, **common)

    assert failed["result_kind"] == "host_failure"
    assert failed["receipt"]["failed_phase"] == "host_execute"
    assert failed["reason"] == "PermissionError"
    assert replayed["replayed"] is True
    assert recovered["status"] == "committed"
    assert calls == {"host": 2, "writeback": 1, "spend": 1}


def test_permission_denial_during_spend_preserves_writeback_and_resumes(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def denied_spend() -> dict[str, object]:
        calls["spend"] += 1
        raise PermissionError("quota ledger denied")

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "scheduler": lambda _spend: {"completed": True, "acknowledged": True},
    }
    with pytest.raises(PermissionError):
        run_loopx_turn_once(plan, spend=denied_spend, **common)

    assert _journal(tmp_path / "runtime")["completed_phases"] == [
        "host_execute",
        "typed_result",
        "validation",
        "durable_writeback",
    ]
    recovered = run_loopx_turn_once(
        plan,
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        **common,
    )

    assert recovered["status"] == "committed"
    assert calls == {"host": 1, "writeback": 1, "spend": 2}


def test_budget_rejection_is_typed_and_retry_does_not_repeat_writeback(
    tmp_path: Path,
) -> None:
    plan = _plan()
    calls = {"host": 0, "writeback": 0, "spend": 0}

    def host(_request: dict[str, object]) -> dict[str, object]:
        calls["host"] += 1
        return _host_result(plan)

    def writeback(_result: dict[str, object]) -> dict[str, object]:
        calls["writeback"] += 1
        return {"ok": True, "appended": True}

    def reject_budget() -> dict[str, object]:
        calls["spend"] += 1
        return {
            "ok": False,
            "appended": False,
            "reason": "quota budget rejected",
        }

    common = {
        "host_runner": host,
        "project": tmp_path,
        "runtime_root": tmp_path / "runtime",
        "goal_id": "fixture-goal",
        "timeout_seconds": 5,
        "execute": True,
        "task_validator": _passing_validator,
        "writeback": writeback,
        "scheduler": lambda _spend: {"completed": True, "acknowledged": True},
    }
    failed = run_loopx_turn_once(plan, spend=reject_budget, **common)

    assert failed["result_kind"] == "quota_spend_failed"
    assert failed["receipt"]["result_kind"] == "quota_spend_failed"
    assert failed["receipt"]["failed_phase"] == "quota_spend"
    assert failed["settlement_result"]["failure"]["kind"] == "budget_rejected"
    assert [
        receipt["step_kind"]
        for receipt in failed["settlement_result"]["receipts"]
    ] == ["validation", "durable_writeback"]
    assert failed["effects"]["state_written"] is True
    assert failed["effects"]["quota_spent"] is False

    recovered = run_loopx_turn_once(
        plan,
        spend=lambda: calls.__setitem__("spend", calls["spend"] + 1)
        or {"ok": True, "appended": True},
        retry_failed=True,
        **common,
    )

    assert recovered["status"] == "committed"
    assert calls == {"host": 1, "writeback": 1, "spend": 2}


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
