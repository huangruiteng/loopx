#!/usr/bin/env python3
"""Smart entry for the `/loopx` slash command (registry-driven, Codex-faithful).

Routing by first token:
  (no args) / on       -> arm goal-mode for THIS project's goal. Continuation is
                          in-session via the Stop hook; NO background timer.
  background            -> arm + ALSO install the opt-in launchd heartbeat (a
                          headless `claude -p` loop that survives session close).
  off                  -> disarm goal-mode (and stop the background timer if one
                          was installed). The registry/goal are left intact.
  status               -> show the project's goal + background-timer state.
  <free text task>     -> ONE-SHOT: ensure a goal exists for this project
                          (bootstrap if needed), register a default agent, add
                          the task as a todo, then arm (in-session continuation).

There is NO active-state file. The LoopX registry (`.loopx/registry.json`) is the
single source of truth for goal_id/agent/scope; "goal-mode ON" == an armed marker
exists (see goal_state.py), independent of the opt-in launchd heartbeat.

The default agent `cc` is registered so loopx's identity contract is active and
`quota should-run --agent-id cc` is satisfied.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_AGENT = "cc"

# registry-driven context + arm/disarm marker + the opt-in launchd heartbeat
sys.path.insert(0, str(HERE.parent / "hooks"))
from goal_state import goal_context, find_registry, arm, disarm, heartbeat_plist  # noqa: E402
import heartbeat_timer  # noqa: E402


def gh_prefix():
    """Cross-platform loopx invocation: the CLI shim if on PATH, else the module."""
    exe = shutil.which("loopx")
    return [exe] if exe else [sys.executable, "-m", "loopx.cli"]


def gh(args, cwd=None):
    return subprocess.run(gh_prefix() + args, cwd=cwd, capture_output=True, text=True, timeout=120)


def slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower() or "project"
    return f"cc-{s}"[:48]


def goal_detail(ctx):
    """Objective (from the registry goal entry) + live state (from quota
    should-run) for the `/loopx status` detail view. Best-effort; returns
    (objective, should_run_payload)."""
    gid, reg, agent = ctx.get("goal_id"), ctx.get("registry"), ctx.get("agent_id")
    # The objective lives in the goal's active-state file (its `objective:`
    # frontmatter), not in the registry entry — resolve state_file from the
    # registry, then read it (project root = the registry's grandparent dir).
    objective = ""
    if reg:
        try:
            regp = Path(reg)
            data = json.loads(regp.read_text(encoding="utf-8"))
            entry = next((g for g in data.get("goals", []) if g.get("id") == gid), None)
            sf = (entry or {}).get("state_file")
            if sf:
                text = (regp.parent.parent / sf).read_text(encoding="utf-8")
                m = re.search(r"^objective:\s*(.+)$", text, re.MULTILINE)
                if m:
                    objective = m.group(1).strip().strip('"').strip("'")
        except Exception:
            pass
    payload = {}
    try:
        cmd = gh_prefix() + (["--registry", reg] if reg else []) + \
            ["--format", "json", "quota", "should-run", "--goal-id", gid]
        if agent:
            cmd += ["--agent-id", agent]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        payload = json.loads(out.stdout or "{}")
    except Exception:
        pass
    return objective, payload


def main():
    args = sys.argv[1:]
    first = args[0] if args else None
    proj = Path.cwd()

    # off: disarm goal-mode (and stop the opt-in background timer if installed).
    if first == "off":
        ctx = goal_context(proj)
        gid = ctx.get("goal_id") if ctx else None
        if not gid:
            print("goal-mode OFF (no goal found here)")
            return
        disarm(gid)
        if heartbeat_plist(gid).exists():
            heartbeat_timer.uninstall(gid)   # also stop the background timer
        print(f"goal-mode OFF  goal={gid}")
        return

    # status: full goal detail (objective + live state + open todos + heartbeat).
    if first == "status":
        ctx = goal_context(proj)
        if not ctx:
            print("loopx goal-mode: no goal in this project yet — run `/loopx <task>` to create one.")
            return
        gid = ctx.get("goal_id")
        objective, d = goal_detail(ctx)
        a = d.get("agent_todo_summary") or {}
        done, open_ = a.get("done_count"), a.get("open_count")
        gate = d.get("gate_prompt")
        if gate:
            state = f"⚠ needs you: {gate}"
        elif d.get("should_run") is True:
            state = "▶ running"
        else:
            state = f"⏸ {d.get('state') or 'paused'}" + (f" — {d['reason']}" if d.get("reason") else "")
        print(f"goal      : {gid}")
        print(f"agent     : {ctx.get('agent_id') or DEFAULT_AGENT}")
        if objective:
            print(f"objective : {objective}")
        print(f"state     : {state}")
        if d.get("recommended_action"):
            print(f"next      : {d['recommended_action']}")
        if done is not None or open_ is not None:
            print(f"todos     : {done} done / {open_} open")
        for it in (a.get("first_open_items") or [])[:8]:
            t = (it.get("text") or "").strip()
            if t:
                print(f"   ▸ {t}")
        print(f"scope     : {ctx.get('write_scope')}")
        heartbeat_timer.status(gid)
        return

    # background: arm + install the OPT-IN launchd heartbeat (headless, cross-session).
    if first == "background":
        ctx = goal_context(proj)
        if not ctx or not ctx.get("goal_id"):
            print("goal-mode: no goal here yet. Run `/loopx <task>` first.")
            return
        arm(ctx["goal_id"])
        heartbeat_timer.install(goal_id=ctx["goal_id"], registry=ctx.get("registry"),
                                scope=ctx.get("write_scope") or [str(proj)],
                                agent_id=ctx.get("agent_id") or DEFAULT_AGENT)
        print(f"goal-mode ON + background heartbeat  goal={ctx['goal_id']}")
        print("  ⚠ runs headless `claude -p` UNATTENDED across sessions, gated only by the")
        print("    loopx hook. Stop with /loopx off. (Untrusted code: run cc in a container.)")
        return

    # bare (=on) or `on`: arm THIS project's existing goal (in-session continuation).
    if not args or first == "on":
        ctx = goal_context(proj)
        if not ctx or not ctx.get("goal_id"):
            # bare /loopx with no goal yet is a VALID action, not an error: open
            # loopx mode and ask for the goal. stdout + exit 0 (NOT stderr/exit 2,
            # which Claude Code surfaces as "Shell command failed").
            print("loopx goal-mode: ON and ready — no goal set in this project yet.")
            print("Tell me what to work on and I'll set it up and start working:")
            print("    /loopx <your goal>   e.g.  /loopx 写一个 RTL 模块并跑通仿真")
            print("(already have a goal elsewhere? run `loopx bootstrap` to connect it)")
            return
        arm(ctx["goal_id"])
        print(f"goal-mode ON  goal={ctx['goal_id']}  agent={ctx.get('agent_id') or DEFAULT_AGENT}")
        print("  continuation: in-session via the Stop hook. Cross-session/headless: /loopx background")
        return

    # free-text task -> one-shot setup + arm + start heartbeat (Claude then works)
    task = " ".join(args).strip().strip('"').strip("'")
    reg = find_registry(proj)

    if reg is not None:
        ctx = goal_context(proj) or {}
        goal_id = ctx.get("goal_id")
        registry = str(reg)
    else:
        goal_id = slug(proj.name)
        registry = str(proj / ".loopx" / "registry.json")
        # Claude projects keep goal state under .claude/ (not the Codex-default .codex/)
        state_file = f".claude/goals/{goal_id}/ACTIVE_GOAL_STATE.md"
        r = gh(["bootstrap", "--project", str(proj), "--goal-id", goal_id,
                 "--objective", task, "--state-file", state_file, "--no-onboarding-scan"])
        if "ok: `True`" not in r.stdout and "ok=True" not in r.stdout and r.returncode != 0:
            print("[loopx] bootstrap failed:\n" + (r.stdout + r.stderr)[:600])
            sys.exit(1)

    if not goal_id:
        print("[loopx] could not determine goal id"); sys.exit(1)

    # ensure a default agent so the loop can claim (and so quota identity is registered)
    gh(["--registry", registry, "configure-goal", "--goal-id", goal_id,
         "--primary-agent", DEFAULT_AGENT, "--registered-agent", DEFAULT_AGENT, "--execute"])

    # add the task as an agent todo
    add = gh(["--registry", registry, "--format", "json", "todo", "add",
               "--goal-id", goal_id, "--role", "agent", "--text", task])
    todo_id = ""
    try:
        todo_id = json.loads(add.stdout).get("todo_id", "")
    except Exception:
        pass

    # arm goal-mode (an armed marker; continuation is in-session via the Stop hook).
    # The background launchd heartbeat is opt-in: `/loopx background`.
    arm(goal_id)

    tid = todo_id or "(see should_run output)"
    print("goal-mode ON (stays on until /loopx off)")
    print(f"  goal_id : {goal_id}")
    print(f"  agent   : {DEFAULT_AGENT}")
    print(f"  todo_id : {tid}")
    print(f"  scope   : {proj}")
    print(f"  task    : {task}")
    print(f"  continuation: in-session via the Stop hook (cross-session/headless: /loopx background)")
    print()
    # Hand the model the exact control-plane calls so it does NOT probe the CLI /
    # guess ids (the loopx MCP tools are already wired and zero-config — they read
    # goal_id/agent_id from the registry, so call them with no extra context).
    print("READY: begin working. Use the wired `loopx` MCP tools — do NOT run `loopx --help` or guess ids:")
    print(f"  1. should_run()                                  # confirm you may spend this tick")
    print(f"  2. claim_task(todo_id=\"{tid}\", agent_id=\"{DEFAULT_AGENT}\")")
    print(f"  3. do ONE bounded segment, then VERIFY it with a real check (build/test) — never claim success from reasoning")
    print(f"  4. complete_task(todo_id=\"{tid}\", agent_id=\"{DEFAULT_AGENT}\", evidence=\"<what you ran + result>\")")
    print(f"  5. should_run() again; repeat on the next open todo until the goal converges.")


if __name__ == "__main__":
    main()
