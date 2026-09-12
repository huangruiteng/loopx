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
