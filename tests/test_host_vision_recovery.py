"""Real CLI/MCP vision recovery: acceptance, accounting and terminal are distinct."""
import importlib.util
import json
from pathlib import Path

import pytest

from loopx.goal_mode_mcp import GoalModeMCPConfig, GoalModeMCPControlPlane

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("host_vision_fixture", REPO / "scripts/qualify-native-goal-release.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def vision(state="no_followup"):
    return {
        "schema_version": "goal_vision_replan_contract_v0", "state": state,
        "vision_patch": {
            "vision_summary": "Deliver the finite local ledger specification.",
            "acceptance_summary": "Replay, reversal and CLI atomic output verified.",
            "last_patch_summary": "Local acceptance tests passed; no external delivery is requested.",
        },
    }


def control_at(root):
    project, runtime, launcher = fixture.setup(root)
    control = GoalModeMCPControlPlane(
        GoalModeMCPConfig(server_name="vision-test", runtime_profile="claude_code", legacy_host_surface="claude_code"),
        lambda: {"goal_id": fixture.GOAL, "agent_id": fixture.AGENT},
    )
    control.command_prefix = lambda: [str(launcher)]
    return control, project, runtime


def spends(runtime):
    rows = [json.loads(row) for row in (runtime / "goals" / fixture.GOAL / "runs/index.jsonl").read_text().splitlines()]
    return [row for row in rows if row.get("classification") == "quota_slot_spent"]


@pytest.mark.parametrize("state,terminal", [("no_followup", True), ("vision_patch_proposed", False), ("vision_closed", False)])
def test_completed_todos_require_vision_decision_not_automatic_goal_close(tmp_path, monkeypatch, state, terminal):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    first = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic lifecycle acceptance", successor_todo_ids=["todo_cli"]))
    assert first["ok"] is True, first
    last = json.loads(control.complete_task("todo_cli", fixture.AGENT, "Synthetic lifecycle acceptance", no_follow_up=True))
    assert last["ok"] is True, last
    before = json.loads(control.should_run())
    assert before["should_run"] is True
    assert before["interaction_contract"]["mode"] != "terminal_no_followup"
    assert len(spends(runtime)) == 2
    repaired = json.loads(control.review_task_vision("todo_cli", fixture.AGENT, vision(state)))
    assert repaired["ok"] is True, repaired
    assert repaired["vision_checkpoint"]["satisfied"] is True
    assert repaired["refresh_recovery"]["decision"] == "supplement_checkpoint"
    replay = json.loads(control.review_task_vision("todo_cli", fixture.AGENT, vision(state)))
    assert replay["ok"] is True, replay
    assert replay["appended"] is False
    assert len(spends(runtime)) == 2
    after = json.loads(control.should_run())
    assert (after["interaction_contract"]["mode"] == "terminal_no_followup") is terminal, after


@pytest.mark.parametrize("policy", ["as_needed", "repeat_until_closed", "repeat_until_closed_long"])
def test_first_delivery_can_author_vision_and_later_delivery_can_preserve_it(tmp_path, monkeypatch, policy):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    authored = vision("vision_patch_proposed")
    authored["vision_patch"]["advancement_policy"] = policy.removesuffix("_long")
    if policy.endswith("_long"):
        authored["vision_patch"]["acceptance_summary"] = (
            "Reducer replay and reversal invariants have been verified against an independent oracle. "
            "Remaining CLI acceptance includes atomic output, malformed input, deterministic ordering, "
            "and documented local invocation. "
        )
        authored["vision_patch"]["vision_summary"] = (
            "Deliver a finite standard-library ledger with deterministic replay and reversal behavior. "
        ) * 4
        authored["vision_patch"]["role_scope"] = "Local implementation, tests and README; no network delivery. " * 3
    result = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=authored))
    assert result["ok"] is True, json.dumps(result)
    assert result["settlement"]["durable_writeback"]["vision_checkpoint"]["satisfied"] is True
    last = json.loads(control.complete_task("todo_cli", fixture.AGENT, "Synthetic acceptance",
        no_follow_up=True, vision_unchanged_reason="The same acceptance remains in scope."))
    assert last["ok"] is True, last
    assert last["settlement"]["durable_writeback"]["vision_checkpoint"]["decision"] == "unchanged_with_reason"
    assert len(spends(runtime)) == 2
    assert json.loads(control.should_run())["should_run"] is True


def test_recovery_cannot_manufacture_completion_or_override_bound_actor(tmp_path, monkeypatch):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    assert json.loads(control.review_task_vision("todo_reducer", "other-agent", vision()))["ok"] is False
    result = json.loads(control.review_task_vision("todo_reducer", fixture.AGENT, vision()))
    assert result["ok"] is False, result
    assert not list(runtime.glob("goals/*/runs/index.jsonl"))


def test_authored_closure_cannot_hide_independent_runnable_work(tmp_path, monkeypatch):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    result = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=vision("no_followup")))
    assert result["ok"] is True, result
    assert len(spends(runtime)) == 1
    quota = json.loads(control.should_run())
    assert quota["should_run"] is True
    assert quota["interaction_contract"]["mode"] != "terminal_no_followup"


def test_bad_vision_is_rejected_before_todo_completion_and_can_be_corrected(tmp_path, monkeypatch):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    state = project / "ACTIVE_GOAL_STATE.md"
    before = state.read_bytes()
    invalid = vision("vision_patch_proposed")
    invalid["vision_patch"]["acceptance_summary"] = "x" * 421
    with pytest.raises(ValueError, match="vision_budget_exceeded"):
        control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
            successor_todo_ids=["todo_cli"], agent_vision=invalid)
    assert state.read_bytes() == before
    assert not list(runtime.glob("goals/*/runs/index.jsonl"))
    corrected = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=vision("vision_patch_proposed")))
    assert corrected["ok"] is True, corrected
    assert len(spends(runtime)) == 1


@pytest.mark.parametrize("length", [240, 241])
def test_unchanged_reason_preflight_precedes_all_completion_effects(tmp_path, monkeypatch, length):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    first = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=vision("vision_patch_proposed")))
    assert first["ok"] is True, first
    state = project / "ACTIVE_GOAL_STATE.md"
    before = state.read_bytes()
    index = runtime / "goals" / fixture.GOAL / "runs/index.jsonl"
    before_index = index.read_bytes()
    calls = []
    original = control.run_cli

    def recorded(args, **kwargs):
        calls.append(args)
        return original(args, **kwargs)

    monkeypatch.setattr(control, "run_cli", recorded)
    if length == 241:
        with pytest.raises(ValueError, match="vision_unchanged_reason exceeds 240 chars"):
            control.complete_task("todo_cli", fixture.AGENT, "Synthetic acceptance",
                no_follow_up=True, vision_unchanged_reason="x" * length)
        assert calls == []  # No lifecycle, writeback or spend command was executed.
        assert state.read_bytes() == before
        assert index.read_bytes() == before_index
        assert len(spends(runtime)) == 1
    # Both valid initial authoring and correcting a rejected request take the
    # real CLI/MCP path. Whitespace is normalized by the same TS owner as refresh.
    result = json.loads(control.complete_task("todo_cli", fixture.AGENT, "Synthetic acceptance",
        no_follow_up=True, vision_unchanged_reason="  " + "x" * 240 + "  "))
    assert result["ok"] is True, result
    checkpoint = result["settlement"]["durable_writeback"]["vision_checkpoint"]
    assert checkpoint["decision"] == "unchanged_with_reason"
    assert checkpoint["unchanged_reason"] == "x" * 240
    assert len(spends(runtime)) == 2
    replay = json.loads(control.complete_task("todo_cli", fixture.AGENT, "Synthetic acceptance",
        no_follow_up=True, vision_unchanged_reason="x" * 240))
    assert replay["ok"] is True, replay
    assert len(spends(runtime)) == 2


def test_legacy_partial_completion_retries_corrected_vision_without_extra_spend(tmp_path, monkeypatch):
    import loopx.control_plane.host_adapter_settlement as adapter

    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    invalid = vision("vision_patch_proposed")
    invalid["vision_patch"]["acceptance_summary"] = "x" * 421
    # Emulate an older host without input preflight. Lifecycle and the rejecting
    # writeback still execute through the real CLI and disposable runtime.
    with monkeypatch.context() as old_host:
        old_host.setattr(adapter, "prepare_vision_refresh", lambda *_args, **_kwargs: {})
        partial = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
            successor_todo_ids=["todo_cli"], agent_vision=invalid))
    assert partial["completed"] is True and partial["ok"] is False
    assert partial["settlement"]["failed_stage"] == "durable_writeback"
    assert partial["recovery"]["tool"] == "complete_task"
    assert partial["recovery"]["settlement_identity"]["todo_id"] == "todo_reducer"
    corrected = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=vision("vision_patch_proposed")))
    assert corrected["ok"] is True, corrected.get("settlement")
    assert len(spends(runtime)) == 1
    replay = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"], agent_vision=vision("vision_patch_proposed")))
    assert replay["ok"] is True, replay.get("settlement")
    assert len(spends(runtime)) == 1


def test_checkpoint_recovery_missing_baseline_conflict_and_lost_response(tmp_path, monkeypatch):
    control, project, runtime = control_at(tmp_path)
    monkeypatch.chdir(project)
    result = json.loads(control.complete_task("todo_reducer", fixture.AGENT, "Synthetic acceptance",
        successor_todo_ids=["todo_cli"]))
    assert result["ok"] is True
    unchanged = json.loads(control.review_task_vision("todo_reducer", fixture.AGENT,
        vision_unchanged_reason="Still correct"))
    assert unchanged.get("vision_checkpoint", {}).get("satisfied") is not True
    assert len(spends(runtime)) == 1
    original = control.run_cli

    def response_lost(args, **kwargs):
        payload = original(args, **kwargs)
        assert json.loads(payload)["ok"] is True, payload
        raise TimeoutError("synthetic response loss after commit")

    monkeypatch.setattr(control, "run_cli", response_lost)
    with pytest.raises(TimeoutError):
        control.review_task_vision("todo_reducer", fixture.AGENT, vision("vision_patch_proposed"))
    monkeypatch.setattr(control, "run_cli", original)
    replay = json.loads(control.review_task_vision("todo_reducer", fixture.AGENT, vision("vision_patch_proposed")))
    assert replay["ok"] is True, replay
    assert replay["appended"] is False
    conflict = json.loads(control.review_task_vision("todo_reducer", fixture.AGENT, vision("no_followup")))
    assert conflict["ok"] is False
    assert len(spends(runtime)) == 1
    # A valid vision decision never consumes the independent open successor.
    assert json.loads(control.should_run())["should_run"] is True


def test_native_outer_controller_owns_new_vision_tool(monkeypatch):
    from loopx.kunluncode_goal_mode.guards import guard_native_controller_writeback
    from types import SimpleNamespace

    monkeypatch.setenv("LOOPX_KUNLUNCODE_OUTER_CONTROLLER", "1")
    control = SimpleNamespace()
    guard_native_controller_writeback(control)
    assert json.loads(control.review_task_vision("todo_any", "agent", vision()))["ok"] is False
