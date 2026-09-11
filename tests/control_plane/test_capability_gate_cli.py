"""Real quota reads preserve requirement/target semantics across authority sources."""
import json

import pytest
from canonical_authority_fixture import initialize_canonical_authority, isolate_sqlite_runtime
from loopx.control_plane.coordination.runtime_shadow import build_runtime_shadow_source_snapshot
from loopx.control_plane.coordination.local_authority import read_canonical_todos_if_promoted
from loopx.control_plane.testing.canary_harness import write_fixture_registry, run_json_cli_result


@pytest.mark.parametrize("provider", ["markdown", "file", "sqlite"])
@pytest.mark.parametrize("network_available", [False, True])
def test_real_quota_capability_gate_does_not_enable_repair_outputs(tmp_path, monkeypatch, provider, network_available):
    if provider == "sqlite":
        isolate_sqlite_runtime(tmp_path, monkeypatch)
    state, runtime, registry = tmp_path / "STATE.md", tmp_path / "runtime", tmp_path / "registry.json"
    state.write_text(
        "# Goal\n\n## Agent Todo\n\n"
        "- [ ] [P0] Inspect external evidence\n"
        "  <!-- loopx:todo todo_id=todo_external role=agent status=open task_class=advancement_task claimed_by=agent-a required_capabilities=network -->\n"
        "- [ ] [P1] Repair the bridge\n"
        "  <!-- loopx:todo todo_id=todo_repair role=agent status=open task_class=advancement_task claimed_by=agent-a required_capabilities=network target_capabilities=network -->\n"
        "- [ ] [P2] Inspect protected evidence\n"
        "  <!-- loopx:todo todo_id=todo_owner role=agent status=open task_class=advancement_task claimed_by=agent-a required_capabilities=credentials -->\n"
        "\n## User Todo / Owner Review Reading Queue\n\n"
    )
    write_fixture_registry(project=tmp_path, runtime_root=runtime, registry_path=registry, goal_id="goal-a",
                           domain="software", adapter_kind="generic_project_goal_v0", state_file=str(state),
                           registered_agents=["agent-a"], quota_allowed_slots=None)
    if provider != "markdown":
        goal = json.loads(registry.read_text())["goals"][0]
        projection, _ = build_runtime_shadow_source_snapshot(goal=goal, runtime_root=runtime,
                                                             state_path=state, registry_path=registry)
        initialize_canonical_authority(runtime, "goal-a", projection, state_path=state, provider=provider)
        state.unlink()
    before = state.read_bytes() if state.exists() else None
    authority = read_canonical_todos_if_promoted(runtime_root=runtime, goal_id="goal-a")
    args = ["quota", "should-run", "--goal-id", "goal-a", "--agent-id", "agent-a",
            "--include-detail", "agent-todos", "--scan-path", str(tmp_path)]
    if network_available:
        args += ["--available-capability", "network"]
    code, packet = run_json_cli_result(*args, registry_path=registry, runtime_root=runtime)
    assert code == 0, packet
    gate = packet["capability_gate"]
    assert gate["action"] == "run"
    assert gate["owner_missing"] == ["credentials"]
    assert ("network" in gate["available"]) is network_available
    ids = [row["todo_id"] for row in gate["runnable_candidates"]]
    assert ids == (["todo_external", "todo_repair"] if network_available else ["todo_repair"])
    assert gate["repair_candidate_count"] == (0 if network_available else 1)
    assert (state.read_bytes() if state.exists() else None) == before
    assert read_canonical_todos_if_promoted(runtime_root=runtime, goal_id="goal-a") == authority
