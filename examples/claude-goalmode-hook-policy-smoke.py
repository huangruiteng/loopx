#!/usr/bin/env python3
"""Smoke-test the optional --harden PreToolUse policy gate (goal_policy.decide).

Focus (review P1): `Task` must NOT be unconditionally allowed — it can spawn a
subagent that performs writes, so it must go through the gate. When
should_run=false it is denied; when should_run=true it defers to Claude Code's
normal permission flow (it is not auto-allowed). The test also pins the rest of
the documented boundary so the README and code stay in sync: read-only allowed
before the gate, Edit/Write confined to write_scope, Bash gated by a destructive
denylist, unknown tools deferred.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "loopx" / "claude_goal_mode" / "hooks"))
import goal_policy  # noqa: E402

CTX = {"goal_id": "g", "registry": "/r", "agent_id": "cc",
       "write_scope": ["/proj"], "project_root": "/proj"}


def decision(tool, sr, **tool_input):
    """Run goal_policy.decide for `tool` with a fixed armed context and a forced
    should_run value; return the permissionDecision ('allow'/'deny') or None=defer."""
    goal_policy.active_context = lambda cwd: CTX
    goal_policy.should_run = lambda *a, **k: sr
    ev = {"cwd": "/proj", "tool_name": tool, "tool_input": tool_input}
    return goal_policy.decide(ev).get("hookSpecificOutput", {}).get("permissionDecision")


def main() -> int:
    # should_run == False: the gate is closed for everything except read-only.
    assert decision("Task", False, description="x", prompt="y") == "deny", \
        "Task must be DENIED when should_run=false (it can spawn a writing subagent)"
    assert decision("Write", False, file_path="/proj/a.txt") == "deny", "write denied when gate closed"
    assert decision("Read", False, file_path="/anywhere") == "allow", "read-only stays allowed"

    # should_run == True: Task is NOT auto-allowed; it defers to normal flow.
    assert decision("Task", True, description="x", prompt="y") is None, \
        "Task must DEFER (not be unconditionally allowed) when should_run=true"
    assert decision("Write", True, file_path="/proj/a.txt") == "allow", "in-scope write allowed"
    assert decision("Write", True, file_path="/etc/passwd") == "deny", "out-of-scope write denied"
    assert decision("Bash", True, command="rm -rf /") == "deny", "destructive bash denied"
    assert decision("Bash", True, command="make test") == "allow", "non-destructive bash allowed"
    assert decision("Read", True, file_path="/anywhere") == "allow", "read-only allowed"

    print("claude-goalmode-hook-policy-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
