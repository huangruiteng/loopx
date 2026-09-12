"""Public graph semantics: lineage is not execution authority."""
import json
import subprocess
import sys

import pytest
from canonical_authority_fixture import initialize_canonical_authority, isolate_sqlite_runtime

from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
from loopx.control_plane.coordination.runtime_shadow import build_todo_runtime_shadow_projection
from loopx.control_plane.todos.active_state_todo_parser import parse_todo_source
from loopx.control_plane.todos.contract import format_todo_metadata_line
from loopx.control_plane.todos.todo_summary import canonical_todo_read_record, structured_todo_item
from loopx.status import active_state_todo_fields
from loopx.status import build_task_graph_projection


def todo(todo_id, **fields):
    return {"todo_id": todo_id, "text": todo_id, "status": "open", **fields}


def graph(rows, total=None):
    return build_task_graph_projection(
        {"goal_id": "graph-goal", "agent_todos": {
            "items": rows, "total_count": len(rows) if total is None else total,
            "open_count": sum(row["status"] != "done" for row in rows),
        }}, goal={"id": "graph-goal"},
    )


def edges_by_todo(result):
    ids = {n["node_id"]: n["refs"]["todo_ids"][0]
           for n in result["nodes"] if n["kind"] == "deliverable"}
    return {(ids[e["from_node_id"]], ids[e["to_node_id"]], e["relation"])
            for e in result["edges"]
            if e["from_node_id"] in ids and e["to_node_id"] in ids}


def test_successor_lineage_is_not_a_completion_dependency():
    result = graph([todo("todo_root"), todo("todo_parent", status="done",
                    successor_todo_ids=["todo_root"])])
    assert edges_by_todo(result) == {("todo_root", "todo_parent", "continues")}


def test_monitor_condition_is_visible_without_claiming_monitor_completion():
    result = graph([todo("todo_root", resume_when="monitor_changed:todo_monitor"),
                    todo("todo_monitor", task_class="continuous_monitor")])
    assert ("todo_root", "todo_monitor", "depends_on") in edges_by_todo(result)
    edge = next(e for e in result["edges"] if e["relation"] == "depends_on")
    assert "generation" in edge["reason"].lower()


def test_unblocks_child_is_prerequisite_of_parent_not_the_reverse():
    result = graph([todo("todo_root"), todo("todo_child", unblocks_todo_id="todo_root")])
    assert ("todo_root", "todo_child", "depends_on") in edges_by_todo(result)
    reversed_root = graph([todo("todo_child", unblocks_todo_id="todo_root"), todo("todo_root")])
    assert ("todo_child", "todo_root", "depends_on") not in edges_by_todo(reversed_root)


def test_missing_relation_target_is_not_reported_as_complete():
    result = graph([todo("todo_root", resume_when="todo_done:todo_missing")])
    assert result["limits"]["missing_predecessor_count"] == 1
    assert result["limits"]["topology_complete"] is False


def test_lineage_and_condition_between_same_pair_are_both_retained():
    result = graph([todo("todo_root", resume_when="todo_done:todo_parent"),
                    todo("todo_parent", status="done", successor_todo_ids=["todo_root"])])
    assert edges_by_todo(result) == {
        ("todo_root", "todo_parent", "continues"),
        ("todo_root", "todo_parent", "depends_on"),
    }


@pytest.mark.parametrize("provider,display", [
    ("legacy", "current"), ("file", "current"), ("sqlite", "current"),
    ("file", "missing"), ("sqlite", "missing"),
])
def test_real_status_reader_uses_provider_snapshot_without_repair_writes(tmp_path, monkeypatch, provider, display):
    isolate_sqlite_runtime(tmp_path, monkeypatch)
    state = tmp_path / "STATE.md"
    source = "\n".join([
        "# Goal", "## Agent Todo", "- [ ] Deliver selected work",
        format_todo_metadata_line(todo_id="todo_root", status="open", task_class="advancement_task",
                                  resume_when="monitor_changed:todo_monitor"),
        "- [ ] Observe changes",
        format_todo_metadata_line(todo_id="todo_monitor", status="open", task_class="continuous_monitor",
                                  material_change_generation=2),
        "- [x] Earlier delivery",
        format_todo_metadata_line(todo_id="todo_parent", status="done", successor_todo_ids=["todo_root"]),
        "## User Todo", "",
    ])
    state.write_text(source)
    runtime = tmp_path / "runtime"
    goal = {"id": "graph-goal", "repo": str(tmp_path), "state_file": str(state), "status": "active",
            "domain": "software", "adapter": {"kind": "manual"}}
    if provider != "legacy":
        groups, _, _ = parse_todo_source(source)
        records = [canonical_todo_read_record(structured_todo_item(item, role=role,
                   source_section=item.get("source_section")))
                   for role, rows in groups.items() for item in rows]
        initialize_canonical_authority(runtime, goal["id"],
            build_todo_runtime_shadow_projection(goal_id=goal["id"], todos=records),
            state_path=state, provider=provider)
        if display == "missing":
            state.unlink()
    before = read_canonical_todos_if_promoted(runtime_root=runtime, goal_id=goal["id"])
    fields = active_state_todo_fields(goal, runtime_root=runtime)
    result = build_task_graph_projection({"goal_id": goal["id"], **fields}, goal=goal)
    assert ("todo_root", "todo_monitor", "depends_on") in edges_by_todo(result)
    assert ("todo_root", "todo_parent", "continues") in edges_by_todo(result)
    assert read_canonical_todos_if_promoted(runtime_root=runtime, goal_id=goal["id"]) == before
    assert (state.read_text() if state.exists() else None) == (None if display == "missing" else source)

    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"common_runtime_root": str(runtime), "goals": [goal]}))
    process = subprocess.run([sys.executable, "-m", "loopx.cli", "--registry", str(registry),
        "--format", "json", "status", "--goal-id", goal["id"]],
        capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, (process.stderr, json.loads(process.stdout).get("contract_errors"))
    assert "graph-goal" in process.stdout
    assert read_canonical_todos_if_promoted(runtime_root=runtime, goal_id=goal["id"]) == before
    assert (state.read_text() if state.exists() else None) == (None if display == "missing" else source)
