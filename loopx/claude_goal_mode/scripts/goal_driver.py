#!/usr/bin/env python3
"""Embedded Agent-SDK goal-mode driver.

The deterministic alternative to Claude Code's auto loop: loopx decides
(a) whether to run, (b) which todo, (c) which tool calls are allowed, and (d)
when to stop. The agent (claude-agent-sdk query()) is just the executor.

  while loopx says should_run:
      todo = next open todo ; claim it
      run query(prompt=heartbeat(todo),
                hooks={PreToolUse:[goal_policy]},        # permission via goal
                mcp_servers={loopx})                     # state via goal
      verify ; complete todo (or release on failure)
  # continuation is decided by loopx (open todos + should_run), NOT the agent

Requires: pip install claude-agent-sdk ; loopx on PATH.
Run:  python goal_driver.py --goal-id G --registry R [--scope DIR ...] \
        [--agent-id cc] [--max-todos N] [--model ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil as _shutil
import subprocess
import sys
from pathlib import Path

# reuse the exact policy used by the CLI hook
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))
import goal_policy  # noqa: E402

try:
    from claude_agent_sdk import query, ClaudeAgentOptions, HookMatcher
except Exception as e:  # pragma: no cover
    raise SystemExit("Install the SDK first: pip install claude-agent-sdk\n" + str(e))

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _gh_prefix():
    _exe = _shutil.which("loopx")
    return [_exe] if _exe else [sys.executable, "-m", "loopx.cli"]


def gh(registry, args):
    cmd = list(_gh_prefix()) + (["--registry", registry] if registry else []) + args
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return out.stdout or ""


def _should_run_args(goal_id, agent_id):
    args = ["--format", "json", "quota", "should-run", "--goal-id", goal_id]
    if agent_id:
        args += ["--agent-id", agent_id]
    return args


def should_run(registry, goal_id, agent_id=None) -> bool:
    try:
        d = json.loads(gh(registry, _should_run_args(goal_id, agent_id)) or "{}")
        return bool(d.get("should_run"))
    except Exception:
        return False


def next_open_todo(registry, goal_id, agent_id=None):
    try:
        d = json.loads(gh(registry, _should_run_args(goal_id, agent_id)) or "{}")
        a = d.get("agent_todo_summary") or {}
        for it in (a.get("first_open_items") or []):
            if not it.get("claimed_by"):
                return it
        items = a.get("first_open_items") or []
        return items[0] if items else None
    except Exception:
        return None


async def goal_policy_hook(input_data, tool_use_id, context):
    """In-process PreToolUse hook -> deterministic goal policy (same as CLI hook)."""
    return goal_policy.decide(input_data)


async def run_todo(goal_id, todo, agent_id, registry, model):
    todo_id = todo.get("todo_id")
    text = todo.get("text", "")
    gh(registry, ["todo", "claim", "--goal-id", goal_id, "--todo-id", todo_id, "--claimed-by", agent_id])

    prompt = (
        f"You are {agent_id} working under goal-mode (loopx controls permissions and the loop).\n"
        f"Work ONLY on this todo and nothing else:\n  [{todo_id}] {text}\n"
        f"Use the loopx MCP tools to read state. When finished, call the loopx "
        f"complete_task tool with todo_id={todo_id}, agent_id={agent_id}, and concrete evidence.\n"
        f"Every tool call is gated by the goal policy; stay within scope."
    )
    options = ClaudeAgentOptions(
        permission_mode="default",  # the PreToolUse hook does the gating
        hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[goal_policy_hook])]},
        mcp_servers={"loopx": {
            # this interpreter (robust where only `python`, not `python3`, exists)
            "command": sys.executable,
            "args": [str(PLUGIN_ROOT / "mcp" / "loopx_mcp.py")],
        }},
        **({"model": model} if model else {}),
    )
    final = ""
    async for msg in query(prompt=prompt, options=options):
        result = getattr(msg, "result", None)
        if result:
            final = result
    return final


async def main_async(a):
    # This in-process driver has no launchd plist, so force goal-mode "armed" for
    # the in-process PreToolUse hook (goal_policy.decide). Goal context itself is
    # read from the registry by the hook/MCP — no active-state file is written.
    os.environ["LOOPX_GOAL_FORCE"] = "1"

    done = 0
    while a.max_todos <= 0 or done < a.max_todos:
        if not should_run(a.registry, a.goal_id, a.agent_id):
            print(f"[driver] goal '{a.goal_id}' should_run=false -> stop (goal decides).")
            break
        todo = next_open_todo(a.registry, a.goal_id, a.agent_id)
        if not todo:
            print("[driver] no open todos -> goal converged.")
            break
        print(f"[driver] -> todo {todo.get('todo_id')}: {todo.get('text','')[:70]}")
        await run_todo(a.goal_id, todo, a.agent_id, a.registry, a.model)
        # NOTE: verification + todo complete are expected to happen via the agent's
        # complete_task MCP call (gated) or a controller verify step here.
        done += 1
    print(f"[driver] finished after {done} todo(s).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal-id", required=True)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--scope", action="append", default=[])
    ap.add_argument("--agent-id", default="cc")
    ap.add_argument("--max-todos", type=int, default=0)  # 0 = until goal converges
    ap.add_argument("--model", default=None)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
