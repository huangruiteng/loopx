"""Ordinary CI covers policy/transport; no test here invokes a model."""

import asyncio
import importlib.util
import json
import os
import subprocess
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("claude_release", REPO / "scripts/qualify-claude-goal-release.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_default_never_probes_or_calls_model(monkeypatch, capsys):
    def forbidden(*_):
        raise AssertionError("must not execute")
    monkeypatch.setattr(runner, "qualify", forbidden)
    monkeypatch.setattr(runner, "prerequisite_failure", forbidden)
    assert runner.main([]) == 0
    assert json.loads(capsys.readouterr().out)["model_executed"] is False


def test_missing_environment_skips_but_attempted_failure_fails(monkeypatch, capsys):
    monkeypatch.setattr(runner, "prerequisite_failure", lambda _: "ark_api_key_unavailable")
    assert runner.main(["--release-live"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "skipped"
    monkeypatch.setattr(runner, "prerequisite_failure", lambda _: None)
    def failure(*_):
        raise RuntimeError("private sentinel must not reach public result")
    monkeypatch.setattr(runner, "qualify", failure)
    assert runner.main(["--release-live"]) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "failed", "error_kind": "RuntimeError"}


def test_provider_binding_does_not_inherit_another_anthropic_account(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "synthetic-ark-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "synthetic-other-provider-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "synthetic-oauth")
    env = runner.host_environment(tmp_path, tmp_path / "bin/loopx")
    assert env["ANTHROPIC_API_KEY"] == "synthetic-ark-key"
    assert env["ANTHROPIC_BASE_URL"] == runner.ARK_ANTHROPIC_BASE
    assert env["ANTHROPIC_MODEL"] == "doubao-seed-evolving"
    assert "ANTHROPIC_AUTH_TOKEN" not in env and "CLAUDE_CODE_OAUTH_TOKEN" not in env
    assert os.environ["ANTHROPIC_AUTH_TOKEN"] == "synthetic-other-provider-key"


def test_child_environment_allowlist_drops_unrelated_secrets_and_operator_home(monkeypatch, tmp_path):
    monkeypatch.setenv("ARK_API_KEY", "synthetic-provider-key")
    forbidden = ("GH_TOKEN", "DATABASE_URL", "CUSTOM_AUTH", "SSH_AUTH_SOCK",
                 "AWS_SECRET_ACCESS_KEY", "NODE_OPTIONS", "BASH_ENV", "CODEX_HOME")
    for key in forbidden:
        monkeypatch.setenv(key, "synthetic-unrelated-value")
    env = runner.host_environment(tmp_path, tmp_path / "bin/loopx")
    # Execute a real child, not just an assertion on a builder's keys.
    result = subprocess.run([sys.executable, "-c", "import os,json; print(json.dumps(dict(os.environ)))"],
                            env=env, capture_output=True, text=True, check=True)
    actual = json.loads(result.stdout)
    assert all(key not in actual for key in (*forbidden, "ARK_API_KEY"))
    assert actual["HOME"] == str(tmp_path / "home")
    assert actual["ANTHROPIC_API_KEY"] == "synthetic-provider-key"


def test_claude_loop_uses_current_contract_not_segment_or_empty_list_stop():
    from loopx.claude_goal_mode.scripts.goalmode_cmd import loop_execution_content, loop_md_content
    from loopx.control_plane.heartbeat.rules import SCOPE_BOUNDED_WORK_RULE

    bootstrap = loop_md_content("goal-a", "agent-a")
    assert "host_prompt" in bootstrap and "loopx:armed" in bootstrap
    assert "writeback/spend" not in bootstrap
    prompt = loop_execution_content("goal-a", "agent-a")
    assert SCOPE_BOUNDED_WORK_RULE in prompt
    assert "interaction_contract" in prompt and "notification" in prompt
    assert "ONE bounded segment" not in prompt and "no open todos remain" not in prompt
    assert "Complete only finished Todos, not partial work" in prompt
    assert 'agent_id="agent-a"' in prompt
    assert "That MCP operation owns writeback/spend" in prompt
    assert "successor_todo_ids" in prompt
    assert "unavailable/incomplete contract" in prompt


def test_host_timeout_fails_and_reaps_the_spawned_process(tmp_path, monkeypatch):
    original = subprocess.Popen
    children = []
    def capture(*args, **kwargs):
        child = original(*args, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(runner.subprocess, "Popen", capture)
    with pytest.raises(subprocess.TimeoutExpired):
        runner.run_host([sys.executable, "-c", "import time; time.sleep(30)"],
                        cwd=tmp_path, env=dict(os.environ), timeout=0.1)
    assert len(children) == 1 and children[0].poll() is not None


def test_host_nonzero_is_not_reported_as_a_successful_model_turn(tmp_path):
    with pytest.raises(AssertionError, match="claude_host_failed"):
        runner.run_host([sys.executable, "-c", "raise SystemExit(2)"],
                        cwd=tmp_path, env=dict(os.environ), timeout=10)


@pytest.mark.parametrize("failed", [False, True])
def test_mcp_oracle_requires_successful_transactions_not_only_invocations(failed):
    events = []
    for todo in sorted(runner.shared.TODOS):
        events.append({"message": {"content": [{"type": "tool_use", "id": todo,
            "name": "mcp__loopx__complete_task", "input": {"todo_id": todo}}]}})
        result = {"ok": not failed, "completed": True, "todo_id": todo,
                  "settlement": {"ok": not failed}}
        events.append({"message": {"content": [{"type": "tool_result", "tool_use_id": todo,
            "content": json.dumps({"result": json.dumps(result)})}]}})
    if failed:
        with pytest.raises(AssertionError, match="mcp_delivery_transactions_not_completed"):
            runner.verify_mcp_completions(events)
    else:
        runner.verify_mcp_completions(events)


def test_real_claude_stdio_mcp_binding_and_identity_gate(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from loopx.claude_goal_mode.scripts.goalmode_cmd import write_loop_md

    project, _, launcher = runner.shared.setup(tmp_path)
    write_loop_md(project, runner.shared.GOAL, runner.shared.AGENT)
    state = project / "ACTIVE_GOAL_STATE.md"
    before = state.read_bytes()
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(REPO / "loopx/claude_goal_mode/mcp/loopx_mcp.py")],
        cwd=str(project), env=runner.shared.host_environment(tmp_path, launcher),
    )
    async def exercise():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {"host_prompt", "should_run", "claim_task", "complete_task"} <= {t.name for t in tools.tools}
                loaded = await session.call_tool("host_prompt", {})
                current = json.loads(loaded.content[0].text)
                assert current["ok"] and current["goal_id"] == runner.shared.GOAL
                assert current["agent_id"] == runner.shared.AGENT
                assert "complete_task" in current["task_body"]
                assert "call the bound LoopX `host_prompt`" not in current["task_body"]
                complete = next(t for t in tools.tools if t.name == "complete_task")
                assert "successor_todo_ids" in complete.inputSchema["properties"]
                guard = await session.call_tool("should_run", {})
                payload = json.loads(guard.content[0].text)
                assert payload["ok"] is True and payload["selected_todo"]["todo_id"] == "todo_reducer"
                rejected = await session.call_tool("claim_task", {"todo_id": "todo_reducer", "agent_id": "other-agent"})
                assert json.loads(rejected.content[0].text)["ok"] is False
    asyncio.run(exercise())
    assert state.read_bytes() == before


def test_real_mcp_delivery_completes_and_settles_existing_plan(tmp_path):
    from loopx.goal_mode_mcp import GoalModeMCPConfig, GoalModeMCPControlPlane

    project, runtime, launcher = runner.shared.setup(tmp_path)
    # Real delivery class: do not substitute same_agent_non_delivery to make
    # this acceptance test green. No live model or external side effect.
    (project / "delivery.txt").write_text("synthetic verified delivery\n")
    control = GoalModeMCPControlPlane(
        GoalModeMCPConfig(server_name="loopx", runtime_profile="claude_code", legacy_host_surface="claude_code"),
        lambda: {"goal_id": runner.shared.GOAL, "agent_id": runner.shared.AGENT,
                 "registry": str(project / ".loopx/registry.json")},
    )
    control.command_prefix = lambda: [str(launcher)]
    result = json.loads(control.complete_task(
        "todo_reducer", runner.shared.AGENT, "synthetic delivery validation passed",
        successor_todo_ids=["todo_cli"],
    ))
    assert result["ok"] is True, "unexpected completion failure"
    todos = runner.shared.cli(launcher, "todo", "list", "--goal-id", runner.shared.GOAL, "--role", "agent")["todos"]
    assert {row["todo_id"] for row in todos} == runner.shared.TODOS
    assert next(row for row in todos if row["todo_id"] == "todo_reducer")["status"] == "done"
    index = runtime / "goals" / runner.shared.GOAL / "runs/index.jsonl"
    spends = [json.loads(line) for line in index.read_text().splitlines()
              if json.loads(line).get("classification") == "quota_slot_spent"]
    assert len(spends) == 1 and spends[0]["todo_id"] == "todo_reducer"
