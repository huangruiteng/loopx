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


def test_claude_loop_uses_current_contract_not_segment_or_empty_list_stop():
    from loopx.claude_goal_mode.scripts.goalmode_cmd import loop_md_content
    from loopx.control_plane.heartbeat.rules import SCOPE_BOUNDED_WORK_RULE

    prompt = loop_md_content("goal-a", "agent-a")
    assert SCOPE_BOUNDED_WORK_RULE in prompt
    assert "interaction_contract" in prompt and "notification" in prompt
    assert "ONE bounded segment" not in prompt and "no open todos remain" not in prompt
    assert "Complete only finished Todos, not partial work" in prompt
    assert 'agent_id="agent-a"' in prompt
    assert "That MCP operation owns writeback/spend" in prompt
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
        cwd=str(project), env={**os.environ, "PYTHONPATH": str(REPO),
                              "PATH": str(launcher.parent) + os.pathsep + os.environ["PATH"]},
    )
    async def exercise():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert {"should_run", "claim_task", "complete_task"} <= {t.name for t in tools.tools}
                guard = await session.call_tool("should_run", {})
                payload = json.loads(guard.content[0].text)
                assert payload["ok"] is True and payload["selected_todo"]["todo_id"] == "todo_reducer"
                rejected = await session.call_tool("claim_task", {"todo_id": "todo_reducer", "agent_id": "other-agent"})
                assert json.loads(rejected.content[0].text)["ok"] is False
    asyncio.run(exercise())
    assert state.read_bytes() == before
