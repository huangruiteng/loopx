#!/usr/bin/env python3
"""Stop hook for goal-mode — loopx's DETERMINISTIC in-session continuation.

The Claude analogue of Codex CLI's cross-turn auto-advance, but loopx — NOT a
transcript-reading model — decides whether to keep going. After each turn, while
goal-mode is armed for this project, we ask ``loopx quota should-run``. If loopx
says run AND there is open agent work, we BLOCK the stop and hand the model the
next bounded step; otherwise we let the turn end and return control to the user.

This is deliberately NOT Claude Code's built-in ``/goal``: continuation is gated
by the loopx control plane (``should_run`` + open todos), never by a model
judging the conversation. Termination is loopx's deterministic state — quota
slots exhaust (``should_run`` -> false) or todos finish (``open_count`` -> 0).

Fail-OPEN by design: if ``should_run`` cannot be reached, or quota is closed, or
there is no open work, we ALLOW the stop. A Stop hook that failed CLOSED would
trap the session in a loop — the opposite of the PreToolUse gate's fail-closed.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# Share the registry-driven resolver with the other hooks (sibling module).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from goal_state import active_context


def _gh_prefix():
    exe = shutil.which("loopx")
    return [exe] if exe else [sys.executable, "-m", "loopx.cli"]


def should_continue(ev: dict) -> tuple[bool, str]:
    """Return (block_stop, reason). block_stop=True keeps the session working.

    Pure-ish: resolves the project goal from the event cwd and asks loopx
    ``quota should-run``. Kept separate from main() so it is unit-testable."""
    cwd = ev.get("cwd") or (ev.get("workspace") or {}).get("current_dir")
    ctx = active_context(cwd)
    if not ctx:
        return (False, "")  # no goal here / goal-mode off -> let it stop
    goal_id = ctx.get("goal_id")
    if not goal_id:
        return (False, "")

    cmd = list(_gh_prefix())
    if ctx.get("registry"):
        cmd += ["--registry", ctx["registry"]]
    cmd += ["--format", "json", "quota", "should-run", "--goal-id", goal_id]
    if ctx.get("agent_id"):
        cmd += ["--agent-id", ctx["agent_id"]]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        d = json.loads(out.stdout or "{}")
    except Exception:
        return (False, "")  # fail OPEN: can't reach loopx -> let it stop

    if d.get("should_run") is not True:
        return (False, "")  # quota/gate closed or converged -> stop
    open_count = (d.get("agent_todo_summary") or {}).get("open_count") or 0
    if not open_count:
        return (False, "")  # nothing open -> stop

    reason = (
        f"loopx goal '{goal_id}': should_run=true with {open_count} open todo(s). "
        "Do NOT stop yet — keep advancing the goal: call the loopx should_run MCP "
        "tool, claim the next open todo, do ONE bounded segment, VERIFY it with a "
        "real check (build/test), complete_task with evidence, then re-check "
        "should_run. Stop only when should_run=false or no open todos remain."
    )
    return (True, reason)


def main():
    raw = sys.stdin.read() or "{}"
    try:
        ev = json.loads(raw)
    except Exception:
        ev = {}
    block, reason = should_continue(ev)
    if block:
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    else:
        sys.stdout.write("{}")


if __name__ == "__main__":
    main()
