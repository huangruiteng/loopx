"""A successor transition must survive the following refresh/history read."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import quote

import pytest

from loopx.cli import main as cli_main
from loopx.control_plane.status.autonomous_replan_projection import (
    AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD,
    autonomous_replan_obligation_from_runs,
)
from loopx.control_plane.work_items.semantic_replan_writeback import (
    ReplanWritebackRejected,
    enforce_open_replan_writeback,
)

GOAL = "successor-review-fixture"
AGENT = "fixture-agent"


def history() -> list[dict]:
    return [dict(classification="evidence_validated", agent_id=AGENT,
                 generated_at=f"2026-08-01T00:{i:02d}:00Z")
            for i in reversed(range(AUTONOMOUS_REPLAN_PERIODIC_RUN_THRESHOLD))]


def successor_state(obligation_id: str, *, owner: str = AGENT) -> str:
    return ("# Goal\n\n## Agent Todo\n\n- [ ] [P1] Verify a new source.\n"
            "  <!-- loopx:todo todo_id=todo_source_audit status=open "
            f"task_class=advancement_task claimed_by={owner} action_kind=research "
            f"target_key=source-audit replan_obligation_id={obligation_id} "
            f"updated_at={quote('2026-08-01T01:00:00Z', safe='')} -->\n")


def test_cli_successor_refresh_resets_periodic_window(tmp_path: Path, capsys) -> None:
    project = tmp_path / "project"
    project.mkdir()
    state = project / "ACTIVE_GOAL_STATE.md"
    state.write_text("# Goal\n\n## Agent Todo\n")
    runtime = tmp_path / "runtime"
    index = runtime / "goals" / GOAL / "runs" / "index.jsonl"
    index.parent.mkdir(parents=True)
    runs = history()
    index.write_text("".join(json.dumps(row) + "\n" for row in reversed(runs)))
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [{
        "id": GOAL, "status": "active", "repo": str(project), "state_file": state.name,
        "coordination": {"agent_model": "peer_v1", "registered_agents": [AGENT]},
    }]}))
    obligation = autonomous_replan_obligation_from_runs(runs, agent_todos={}, agent_id=AGENT)
    assert obligation is not None
    common = ["--registry", str(registry), "--runtime-root", str(runtime), "--format", "json"]
    assert cli_main(common + ["todo", "add", "--goal-id", GOAL, "--role", "agent",
        "--text", "[P1] Verify a new source", "--task-class", "advancement_task",
        "--action-kind", "research", "--target-key", "source-audit", "--claimed-by", AGENT,
        "--replan-obligation-id", obligation["obligation_id"]]) == 0
    added = json.loads(capsys.readouterr().out)
    assert added["replan_transition"]["outcome"] == "new_runnable_successor"
    assert cli_main(common + ["refresh-state", "--goal-id", GOAL, "--agent-id", AGENT,
        "--progress-scope", "agent_lane", "--classification", "bounded_replan_progress",
        "--delivery-outcome", "surface_only", "--no-global-sync"]) == 0
    refreshed = json.loads(capsys.readouterr().out)
    persisted = json.loads(Path(refreshed["json_path"]).read_text())
    ack = persisted["autonomous_replan_ack"]
    assert ack["recorded"] is True
    delta = ack["semantic_delta"]
    assert delta["obligation_id"] == obligation["obligation_id"]
    assert delta["successor_todo_id"] == added["todo_id"]
    assert delta["satisfying_outcomes"] == ["new_runnable_successor"]
    compact = json.loads(index.read_text().splitlines()[-1])
    assert compact["autonomous_replan_ack"]["recorded"] is True
    assert autonomous_replan_obligation_from_runs(
        [compact, *runs], agent_todos={}, agent_id=AGENT) is None
    # A full *new* window must re-arm; old history is not erased.
    checkpoint = datetime.fromisoformat(compact["generated_at"])
    new_runs = [{**row, "generated_at": (checkpoint + timedelta(minutes=i + 1)).isoformat()}
                for i, row in enumerate(reversed(runs))]
    assert autonomous_replan_obligation_from_runs(
        [*reversed(new_runs), compact, *runs], agent_todos={}, agent_id=AGENT) is not None


@pytest.mark.parametrize("guard", [None, "replan-different"])
def test_transition_cannot_settle_a_different_turn_guard(guard) -> None:
    runs = history()
    obligation = autonomous_replan_obligation_from_runs(runs, agent_todos={}, agent_id=AGENT)
    assert enforce_open_replan_writeback(newest_first_runs=runs,
        state_text=successor_state(obligation["obligation_id"]), agent_id=AGENT,
        goal_id=GOAL, guard_scoped=True,
        guard_semantic_replan_obligation_id=guard) is None


def test_transition_settles_only_exact_guard_and_owner() -> None:
    runs = history()
    obligation = autonomous_replan_obligation_from_runs(runs, agent_todos={}, agent_id=AGENT)
    kwargs = dict(newest_first_runs=runs, agent_id=AGENT, goal_id=GOAL,
                  guard_scoped=True, guard_semantic_replan_obligation_id=obligation["obligation_id"])
    delta = enforce_open_replan_writeback(
        state_text=successor_state(obligation["obligation_id"]), **kwargs)
    assert delta and delta["accepted"] is True
    with pytest.raises(ReplanWritebackRejected):
        enforce_open_replan_writeback(
            state_text=successor_state(obligation["obligation_id"], owner="another-agent"), **kwargs)


@pytest.mark.parametrize("route", ["writeback", "successor", "canonical-successor"])
def test_long_chain_ack_survives_real_cli_history_and_peer_claim(tmp_path: Path, route: str) -> None:
    import subprocess
    import sys

    project = tmp_path / "project"
    project.mkdir()
    runtime = tmp_path / "runtime"
    state = project / "ACTIVE_GOAL_STATE.md"
    rows = [
        f"- [ ] [P1] Synthetic work {i}.\n"
        f"  <!-- loopx:todo todo_id=todo_owned_{i:02} status=open "
        f"task_class=advancement_task claimed_by={AGENT} "
        "updated_at=2026-08-01T00%3A00%3A00Z -->\n"
        for i in range(15)
    ]
    state.write_text("---\nstatus: active\n---\n\n# Goal\n\n## Agent Todo\n\n" + "".join(rows) +
        "- [ ] [P1] Synthetic shared work.\n"
        "  <!-- loopx:todo todo_id=todo_shared_work status=open "
        "task_class=advancement_task updated_at=2026-08-01T00%3A00%3A00Z -->\n")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [{
        "id": GOAL, "status": "active", "repo": str(project), "state_file": state.name,
        "domain": "synthetic-replan",
        "adapter": {"kind": "fixture_connected_delivery_v0", "status": "connected-delivery"},
        "quota": {"compute": 1.0, "window_hours": 24},
        "coordination": {"agent_model": "peer_v1", "registered_agents": [AGENT, "peer-agent"]},
    }]}))

    if route == "canonical-successor":
        from canonical_authority_fixture import initialize_canonical_authority
        from loopx.control_plane.todos.active_state_todo_parser import parse_active_state_todos
        todos = parse_active_state_todos(state.read_text(), item_limit=None)["agent_todos"]["items"]
        module = (Path(__file__).resolve().parents[2] / "tests/control_plane_ts/authority_projection_fixture.ts").as_uri()
        built = subprocess.run(["node", "--no-warnings", "--experimental-strip-types", "--input-type=module", "-e",
            f"import {{authorityProjectionFixture}} from {json.dumps(module)};"
            "let s='';for await(const c of process.stdin)s+=c;"
            "process.stdout.write(JSON.stringify(authorityProjectionFixture(process.argv[1],JSON.parse(s),[], 'legacy')));", GOAL],
            input=json.dumps(todos), capture_output=True, text=True, check=True, timeout=30)
        initialize_canonical_authority(runtime, GOAL, json.loads(built.stdout), state_path=state)

    def call(*args):
        completed = subprocess.run([sys.executable, "-m", "loopx.cli", "--registry", str(registry),
            "--runtime-root", str(runtime), "--format", "json", *args],
            capture_output=True, text=True, timeout=60)
        assert completed.returncode == 0, completed.stdout + completed.stderr
        return json.loads(completed.stdout)

    def guard():
        result = call("quota", "should-run", "--goal-id", GOAL, "--agent-id", AGENT,
            "--runtime-profile", "generic_cli")
        return result.get("autonomous_replan_obligation")

    original = guard()
    assert original and "long_todo_chain" in [t["kind"] for t in original["triggers"]]
    progress_args = ["--progress-result-class", "advanced", "--progress-surface-id", "artifact-adoption",
        "--progress-evidence-id", "evidence:independent-acceptance"]
    if route.endswith("successor"):
        added = call("todo", "add", "--goal-id", GOAL, "--role", "agent", "--claimed-by", AGENT,
            "--text", "Validate dependent artifact adoption", "--task-class", "advancement_task",
            "--action-kind", "validate", "--target-key", "artifact-adoption",
            "--replan-obligation-id", original["obligation_id"])
        progress_args = []
    refreshed = call("refresh-state", "--goal-id", GOAL, "--agent-id", AGENT,
        "--classification", "bounded_replan_progress", "--delivery-outcome", "surface_only",
        *progress_args,
        "--vision-unchanged-reason", "The synthetic acceptance remains unchanged.",
        "--no-global-sync", "--suppress-external-sinks")
    persisted = json.loads(Path(refreshed["json_path"]).read_text())
    ack = persisted["autonomous_replan_ack"]
    assert ack["recorded"] and ack["semantic_delta"]["accepted"]
    if route.endswith("successor"):
        assert ack["semantic_delta"]["successor_todo_id"] == added["todo_id"]
        assert ack["semantic_delta"]["successor_origin_obligation_id"] == original["obligation_id"]
    assert ack["semantic_delta"]["trigger_checkpoints"][0]["frontier_owned_identity"]
    compact = json.loads((runtime / "goals" / GOAL / "runs" / "index.jsonl").read_text().splitlines()[-1])
    assert compact["autonomous_replan_ack"]["semantic_delta"]["trigger_checkpoints"] == (
        ack["semantic_delta"]["trigger_checkpoints"])
    if route.endswith("successor"):
        for field in ("successor_todo_id", "successor_origin_obligation_id", "successor_binding"):
            assert compact["autonomous_replan_ack"]["semantic_delta"][field] == ack["semantic_delta"][field]
    assert guard() is None
    call("todo", "claim", "--goal-id", GOAL, "--todo-id", "todo_shared_work",
        "--agent-id", "peer-agent", "--claimed-by", "peer-agent")
    assert guard() is None
    call("todo", "update", "--goal-id", GOAL, "--todo-id", "todo_owned_00",
        "--agent-id", AGENT, "--text", "Changed material acceptance for this lane")
    rearmed = guard()
    assert rearmed and rearmed["rearmed_after_obligation_id"] == ack["semantic_delta"]["obligation_id"]
