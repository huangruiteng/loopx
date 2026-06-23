#!/usr/bin/env python3
"""PreToolUse policy gate for goal-mode — loopx's deterministic gate.

There is no OS sandbox in this design (loopx drives Claude Code directly): this
hook IS the whole gate. It emits a deterministic permission decision from loopx
state and does the containment at the tool layer:

- should_run gate (fail-closed)  -> may the agent spend this turn right now?
- Edit/Write -> write_scope        -> deny file edits outside the goal's scope
- Bash -> destructive denylist     -> deny obviously dangerous commands

Limitation (by design): Bash is gated only by a denylist, so a determined shell
command can still write outside write_scope or reach the network. This is the
loopx-original posture — fine for trusted local work. For STRONG isolation
(untrusted code / unattended high-stakes), run Claude Code inside a dev
container or VM, which contains the whole process at the environment level.

Behavior (only while goal-mode is ARMED for the event's project):
- no goal here / goal-mode off            -> {} (no-op; normal permission flow)
- read-only/safe tools                    -> allow
- should_run == false (quota/gate closed) -> deny
- should_run probe unavailable (error)    -> deny for non-read-only tools (FAIL-CLOSED)
- should_run == true:
    * Edit/Write outside write_scope      -> deny
    * Edit/Write within write_scope       -> allow
    * destructive Bash                    -> deny
    * Bash / other                        -> allow

Fail-closed: if the deterministic ``should_run`` probe cannot be reached, a
non-read-only tool is denied rather than allowed, so a flaky/broken control
plane pauses delivery instead of running ungated. Read-only tools stay allowed.

Identity-aware: when the active goal registered an agent (loopx
``coordination.registered_agents``), the context carries ``agent_id`` and this
hook forwards it as ``--agent-id`` to ``loopx quota should-run``. Without it
loopx returns ``automation_prompt_upgrade_required`` and should_run=false — the
Claude Code analogue of Codex's identity-scoped heartbeat prompt.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Goal context is resolved PER PROJECT from the event's cwd via the registry, and
# "armed" = the per-goal launchd heartbeat exists (see goal_state.py). No separate
# active-state file — the registry is the single source of truth, like Codex.
from goal_state import active_context

# Read-only tools are always allowed under goal-mode. Edit/Write are scoped to
# write_scope; Bash is gated by a destructive-command denylist. (No OS sandbox in
# this design — the hook is the whole gate; see the module docstring.)
READONLY_TOOLS = {"Read", "Glob", "Grep", "NotebookRead", "TodoWrite", "Task", "WebFetch", "WebSearch", "ToolSearch"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
DESTRUCTIVE = (
    "rm -rf", "rm -fr", "mkfs", "dd if=", ":(){", "shutdown", "reboot",
    "git push --force", "git reset --hard", "> /dev/sd", "format ",
)


def within(path: str, root: str) -> bool:
    """True if `path` resolves to `root` or a descendant of it."""
    try:
        p = Path(path).resolve()
        r = Path(root).resolve()
        return r == p or r in p.parents
    except Exception:
        return False



import shutil as _shutil
def _gh_prefix():
    _exe = _shutil.which("loopx")
    return [_exe] if _exe else [__import__("sys").executable, "-m", "loopx.cli"]

def emit(decision=None, reason=""):
    if decision is None:
        sys.stdout.write("{}")  # no-op: defer to normal permission flow
        return
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


def should_run(registry, goal_id, agent_id=None) -> bool | None:
    """Return True/False from loopx quota should-run, or None if unknown."""
    if not goal_id:
        return None
    cmd = list(_gh_prefix())
    if registry:
        cmd += ["--registry", registry]
    cmd += ["--format", "json", "quota", "should-run", "--goal-id", goal_id]
    if agent_id:
        cmd += ["--agent-id", agent_id]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(out.stdout or "{}")
        return bool(data.get("should_run"))
    except Exception:
        return None  # caller fails CLOSED on None for non-read-only tools


def decide(ev: dict) -> dict:
    """Pure policy: given a PreToolUse event, return the hookSpecificOutput dict
    (or {} for no-op). Reused by the CLI hook AND the Agent SDK in-process hook.

    The hook is the whole gate (no OS sandbox): should_run (fail-closed) +
    Edit/Write write_scope + a destructive-Bash denylist."""
    # Claude Code feeds the session's working directory on the event; resolve the
    # goal from THAT project's registry, and gate only while goal-mode is armed
    # (the project's heartbeat plist exists). Unrelated/unarmed projects -> no-op.
    cwd = ev.get("cwd") or (ev.get("workspace") or {}).get("current_dir")
    ctx = active_context(cwd)
    if not ctx:
        return {}  # no goal here, or goal-mode off -> defer to normal flow

    goal_id = ctx.get("goal_id")
    registry = ctx.get("registry")
    agent_id = ctx.get("agent_id")
    scope = ctx.get("write_scope") or []
    tool = ev.get("tool_name", "")
    ti = ev.get("tool_input", {}) or {}

    def d(decision, reason):
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason}}

    if tool in READONLY_TOOLS:
        return d("allow", "read-only/safe tool under goal-mode")

    sr = should_run(registry, goal_id, agent_id)  # True / False / None
    if sr is False:
        return d("deny", f"goal '{goal_id}' should_run=false (quota/gate closed)")
    if sr is None:
        # deterministic should_run probe unavailable -> fail closed (non-read-only tool)
        return d("deny", "loopx should_run probe unavailable — failing closed under goal-mode")

    # should_run == True. Scope the Edit/Write file tools to write_scope, and
    # gate Bash with the destructive denylist (the hook is the whole gate).
    if tool in WRITE_TOOLS:
        fp = ti.get("file_path") or ti.get("notebook_path") or ""
        if scope and not any(within(fp, s) for s in scope):
            return d("deny", f"'{fp}' outside goal write_scope {scope}")
        return d("allow", "write within goal scope")
    if tool == "Bash":
        low = (ti.get("command") or "").lower()
        if any(tok in low for tok in DESTRUCTIVE):
            return d("deny", "destructive command blocked by goal policy")
        return d("allow", "bash permitted under goal policy")
    return {}  # unknown tool: defer to normal flow


def main():
    raw = sys.stdin.read() or "{}"
    try:
        ev = json.loads(raw)
    except Exception:
        ev = {}
    result = decide(ev)
    sys.stdout.write(json.dumps(result) if result else "{}")


if __name__ == "__main__":
    main()
