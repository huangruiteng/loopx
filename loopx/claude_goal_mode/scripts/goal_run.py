#!/usr/bin/env python3
"""loopx CC heartbeat driver — the Claude Code counterpart of the Codex
timer+heartbeat (Codex has a native goal app-server; Claude Code does not, so the
loop is external).

Each tick:
  1. loopx quota should-run     -> stop if the goal is paused/closed
  2. loopx heartbeat-prompt      -> the agent-neutral worker task body
  3. claude -p (gated by the goal-mode PreToolUse hook) does one bounded segment
  4. loop; continuation is decided by loopx (should_run + open todos),
     NOT by the agent. Includes API-overload (529) backoff via `claude --continue`.

It also "arms" the goal-mode state file so the PreToolUse hook + statusline gate
the right goal (same flag that `/loopx` / `/loopx on` sets), including the registered
agent_id so should-run carries identity.

Usage:
  python goal_run.py --goal-id G [--registry R] [--scope DIR ...] \
     [--agent-id cc] [--max-ticks N] [--model M] [--brief|--thin|--compact] \
     [--backoff-seconds 600] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# The launchd timer runs this with cwd=/ , so the project root comes from the
# --scope argument. No active-state file is written: the registry (goal truth) +
# the heartbeat plist (armed) are what the hooks/MCP read, like Codex.
OVERLOAD = ("overloaded", "529", "rate limit", "rate_limit", "too many requests", "service unavailable")



import shutil as _shutil
def _gh_prefix():
    _exe = _shutil.which("loopx")
    return [_exe] if _exe else [__import__("sys").executable, "-m", "loopx.cli"]


def gh(registry, args):
    cmd = list(_gh_prefix()) + (["--registry", registry] if registry else []) + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


def should_run(registry, goal_id, agent_id=None) -> bool:
    try:
        args = ["--format", "json", "quota", "should-run", "--goal-id", goal_id]
        if agent_id:
            args += ["--agent-id", agent_id]
        d = json.loads(gh(registry, args).stdout or "{}")
        return bool(d.get("should_run"))
    except Exception:
        return False


def heartbeat_prompt(registry, goal_id, form, agent_id=None) -> str:
    args = ["heartbeat-prompt", form, "--goal-id", goal_id]
    if agent_id:
        # registered agents make an unscoped heartbeat-prompt fail closed, so
        # carry the identity + a scope (mirrors loopx render_quota_guard_command).
        args += ["--agent-id", agent_id,
                 "--agent-scope", "primary review, verification, merge, and coordination"]
    out = gh(registry, args)
    body = out.stdout.strip()
    return body or f"Heartbeat for goal {goal_id}: ask `loopx quota should-run`, do one bounded verified segment, write back."


def run_claude(prompt: str, model, backoff: int, dry_run: bool, cwd=None) -> int:
    base = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "default"]
    if model:
        base += ["--model", model]
    if dry_run:
        print("[dry-run] would run:", " ".join(base), "< <heartbeat prompt>", f"(cwd={cwd})")
        print("[dry-run] prompt head:", prompt[:160].replace("\n", " "))
        return 0
    attempt = 0
    cmd = base
    stdin_text = prompt
    while attempt <= 8:
        # cwd = project root so the PreToolUse hook + loopx MCP (both cwd-scoped)
        # resolve THIS project's goal-mode state, and the worker edits the project.
        proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, cwd=cwd)
        tail = (proc.stdout[-4000:] + proc.stderr[-2000:]).lower()
        if proc.returncode == 0 and not any(t in tail for t in OVERLOAD):
            return 0
        if any(t in tail for t in OVERLOAD):
            attempt += 1
            print(f"[goal_run] API overload -> wait {backoff}s then --continue (attempt {attempt})")
            time.sleep(backoff)
            cmd = base + ["--continue"]
            stdin_text = "Continue the task where you left off; re-run any interrupted step."
            continue
        return proc.returncode  # genuine non-overload failure
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--goal-id", required=True)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--scope", action="append", default=[])
    ap.add_argument("--agent-id", default="cc")
    ap.add_argument("--max-ticks", type=int, default=0)  # 0 = until goal converges
    ap.add_argument("--model", default=None)
    ap.add_argument("--backoff-seconds", type=int, default=600)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--thin", action="store_const", dest="form", const="--thin")
    grp.add_argument("--compact", action="store_const", dest="form", const="--compact")
    grp.add_argument("--brief", action="store_const", dest="form", const="--brief")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    form = a.form or "--thin"

    project_root = Path(a.scope[0]) if a.scope else Path.cwd()
    print(f"[goal_run] tick start: goal={a.goal_id} scope={a.scope or '(unbounded)'} "
          f"agent={a.agent_id} project={project_root}")

    tick = 0
    while a.max_ticks <= 0 or tick < a.max_ticks:
        if not should_run(a.registry, a.goal_id, a.agent_id):
            print(f"[goal_run] should_run=false for '{a.goal_id}' -> stop (goal decides).")
            break
        tick += 1
        prompt = heartbeat_prompt(a.registry, a.goal_id, form, a.agent_id)
        prompt += (
            f"\n\nYou are {a.agent_id} under goal-mode. Use the loopx MCP tools "
            f"(should_run/list_todos/claim_task/complete_task). Every tool call is gated by the goal policy."
        )
        print(f"[goal_run] tick {tick}: dispatching claude (form={form}, cwd={project_root})")
        rc = run_claude(prompt, a.model, a.backoff_seconds, a.dry_run, cwd=str(project_root))
        if a.dry_run:
            print("[goal_run] dry-run: single tick only."); break
        if rc != 0:
            print(f"[goal_run] claude exited rc={rc}; stopping to avoid a hot loop."); break
        gh(a.registry, ["refresh-state", "--goal-id", a.goal_id])
    print(f"[goal_run] finished after {tick} tick(s).")


if __name__ == "__main__":
    main()
