#!/usr/bin/env python3
"""Minimal MCP server exposing loopx state to the agent.

Tools: list_todos, claim_task, complete_task, should_run.
Each shells out to the loopx CLI (deterministic control plane).

Requires: pip install mcp
Config (registry/goal/agent) is resolved PER PROJECT from this process's cwd via
the `.loopx/registry.json` (see goal_state.py): each Claude Code session launches
its own stdio MCP subprocess inheriting the session's working directory, so the
goal scoping is per-project — no global state shared across sessions.

These tools are the loopx control-plane protocol that native `/loop` drives each
iteration (via `.claude/loop.md`): should_run -> claim_task -> bounded work ->
verify -> complete_task (which also spends one quota slot after writeback).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:  # pragma: no cover
    raise SystemExit("MCP SDK not installed. Run: pip install mcp\n" + str(e))

# share the registry-driven resolver with the hooks (sibling hooks/ dir)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
from goal_state import goal_context

mcp = FastMCP("loopx")



import shutil as _shutil
def _gh_prefix():
    _exe = _shutil.which("loopx")
    return [_exe] if _exe else [__import__("sys").executable, "-m", "loopx.cli"]

def _state() -> dict:
    # registry-derived context for THIS project (cwd) — the control-plane tools
    # work whenever a goal exists, independent of the optional hook/loop.md.
    return goal_context(Path.cwd()) or {}


def _ctx():
    st = _state()
    return st.get("goal_id"), st.get("registry")


def _agent_id():
    return _state().get("agent_id")


def _gh(args: list[str]) -> str:
    goal_id, registry = _ctx()
    cmd = list(_gh_prefix())
    if registry:
        cmd += ["--registry", registry]
    cmd += args
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return (out.stdout or "") + (("\n" + out.stderr) if out.returncode else "")


def _no_goal_msg() -> str:
    return json.dumps({"error": "goal-mode is not active in this project; run /loopx <task> first"})


@mcp.tool()
def should_run() -> str:
    """Whether the active goal should run now (quota/gate)."""
    gid, _ = _ctx()
    if not gid:
        return _no_goal_msg()
    args = ["--format", "json", "quota", "should-run", "--goal-id", gid]
    aid = _agent_id()
    if aid:
        args += ["--agent-id", aid]
    return _gh(args)


@mcp.tool()
def list_todos() -> str:
    """List the active goal's open agent todos (with todo_id + claimed_by)."""
    gid, _ = _ctx()
    if not gid:
        return _no_goal_msg()
    args = ["--format", "json", "quota", "should-run", "--goal-id", gid]
    aid = _agent_id()
    if aid:
        args += ["--agent-id", aid]
    return _gh(args)


@mcp.tool()
def claim_task(todo_id: str, agent_id: str) -> str:
    """Soft-claim a todo for an agent."""
    gid, _ = _ctx()
    return _gh(["todo", "claim", "--goal-id", gid, "--todo-id", todo_id, "--claimed-by", agent_id])


@mcp.tool()
def complete_task(todo_id: str, agent_id: str, evidence: str, next_agent_todo: str = "") -> str:
    """Complete a todo (with evidence), then spend one quota slot.

    Mirrors the Codex heartbeat contract: spend exactly once AFTER validated
    writeback. The slot is accounted only when the completion reports ok, with
    source=heartbeat so it lines up with Codex spend accounting."""
    gid, _ = _ctx()
    args = ["todo", "complete", "--goal-id", gid, "--todo-id", todo_id,
            "--claimed-by", agent_id, "--evidence", evidence]
    if next_agent_todo:
        # Don't hard-code a next claimer. With --next-agent-todo and no
        # --next-claimed-by, LoopX assigns the new todo using its own completion
        # semantics — to the completing agent (here `agent_id`, which /loopx
        # registered), or to an explicit review_handoff peer selected by task policy.
        # Hard-coding an unregistered id
        # like `cc-controller` would fail registration.
        args += ["--next-agent-todo", next_agent_todo]
    out = _gh(args)
    # spend-slot only on a validated completion (ok), matching "spend after writeback"
    if "ok: `True`" in out or "ok=True" in out or '"ok": true' in out.lower():
        spend = ["quota", "spend-slot", "--goal-id", gid, "--slots", "1",
                 "--source", "heartbeat", "--execute"]
        if agent_id:
            spend += ["--agent-id", agent_id]
        out += "\n--- spend-slot ---\n" + _gh(spend)
    return out


if __name__ == "__main__":
    mcp.run()
