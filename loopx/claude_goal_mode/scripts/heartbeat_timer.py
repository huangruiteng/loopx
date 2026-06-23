#!/usr/bin/env python3
"""Persistent goal-mode heartbeat for Claude Code — the launchd analogue of the
Codex App recurring heartbeat automation.

Codex App owns a platform-level timer that periodically wakes a thread (a
replaceable worker); LoopX decides via ``quota should-run`` whether that wakeup
should spend delivery compute. Claude Code's interactive TUI has no such standing
timer, so we put it OUTSIDE the session: a per-goal launchd LaunchAgent fires
``goal_run.py --max-ticks 1`` every ``interval`` seconds. Each tick:

  should_run (deterministic gate) -> heartbeat-prompt (the same versioned
  contract Codex uses) -> headless ``claude -p`` as the executor (cwd = project)
  -> validated writeback + spend-slot (done inside the worker via complete_task).

This survives session close and reboot (RunAtLoad + StartInterval), so a goal can
advance for days unattended — exactly the Codex "set it once and it keeps working"
property. ``should_run=false`` makes a tick a no-op (no claude spawned, no spend),
so the timer firing does not by itself burn compute.

Usage:
  heartbeat_timer.py install --goal-id G --registry R --scope DIR --agent-id A [--interval 600] [--form --compact]
  heartbeat_timer.py uninstall --goal-id G
  heartbeat_timer.py status --goal-id G
"""
from __future__ import annotations

import argparse
import plistlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL_RUN = HERE / "goal_run.py"
LOG_DIR = Path.home() / "Library" / "Logs" / "loopx"

# label/plist path come from goal_state so the PreToolUse "armed" check (plist
# exists?) and the timer we install agree by construction.
sys.path.insert(0, str(HERE.parent / "hooks"))
from goal_state import LAUNCH_AGENTS, heartbeat_label as _label, heartbeat_plist as _plist_path


def _bin_path() -> str:
    # launchd jobs start with a minimal PATH; bake in the dirs where `loopx` and
    # `claude` live so goal_run.py's shutil.which() resolves them.
    dirs = [str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin",
            "/usr/local/bin", "/usr/bin", "/bin", "/usr/sbin", "/sbin"]
    return ":".join(dirs)


def install(goal_id, registry, scope, agent_id, interval=600, form="--compact", python=None):
    """Write + (re)load a per-goal LaunchAgent that runs one heartbeat tick every `interval`s."""
    if not goal_id:
        print("heartbeat_timer: --goal-id required", file=sys.stderr)
        return 2
    python = python or sys.executable
    project_root = scope[0] if scope else str(Path.cwd())
    log = LOG_DIR / f"{_label(goal_id)}.log"

    args = [python, str(GOAL_RUN), "--goal-id", goal_id, "--max-ticks", "1", form]
    if registry:
        args += ["--registry", registry]
    for s in scope or []:
        args += ["--scope", s]
    if agent_id:
        args += ["--agent-id", agent_id]

    plist = {
        "Label": _label(goal_id),
        "ProgramArguments": args,
        "StartInterval": int(interval),
        "RunAtLoad": True,
        "WorkingDirectory": project_root,
        "EnvironmentVariables": {"PATH": _bin_path()},
        "StandardOutPath": str(log),
        "StandardErrorPath": str(log),
        "ProcessType": "Background",
    }
    path = _plist_path(goal_id)
    try:
        LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            plistlib.dump(plist, f)
    except OSError as e:
        # A filesystem restriction (e.g. a user-enabled sandbox) can block writing
        # the launchd plist. Skip the background timer rather than crash —
        # in-session continuation via the Stop hook still advances the goal.
        print(f"heartbeat: could not write {path} ({e}); skipping the background "
              f"timer. In-session continuation (Stop hook) still works.")
        return 0

    # reload: unload first (ignore errors), then load -w so it persists across logins
    subprocess.run(["launchctl", "unload", "-w", str(path)], capture_output=True, text=True)
    r = subprocess.run(["launchctl", "load", "-w", str(path)], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"heartbeat_timer: launchctl load failed: {(r.stdout + r.stderr).strip()[:300]}", file=sys.stderr)
        return 1
    print(f"heartbeat ON  label={_label(goal_id)}  every {interval}s  log={log}")
    return 0


def uninstall(goal_id):
    path = _plist_path(goal_id)
    if path.exists():
        # Unload first (stops the timer firing) — this is what actually turns the
        # heartbeat off. Removing the plist FILE is secondary.
        subprocess.run(["launchctl", "unload", "-w", str(path)], capture_output=True, text=True)
        try:
            path.unlink()
            print(f"heartbeat OFF  removed {path.name}")
        except OSError as e:
            # A filesystem restriction (e.g. a user-enabled sandbox) can block
            # deleting a file outside write_scope. The timer is already unloaded
            # above, so goal-mode is effectively off; report instead of crashing.
            print(f"heartbeat OFF (unloaded), but could not remove {path} ({e}).\n"
                  f"  Remove it manually:  rm -f \"{path}\"")
    else:
        print(f"heartbeat: no timer installed for goal '{goal_id}'")
    return 0


def status(goal_id):
    label = _label(goal_id)
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    line = next((ln for ln in r.stdout.splitlines() if label in ln), None)
    if line:
        print(f"heartbeat RUNNING  {line.strip()}")
    elif _plist_path(goal_id).exists():
        print(f"heartbeat INSTALLED (not loaded)  {_plist_path(goal_id)}")
    else:
        print(f"heartbeat NONE  for goal '{goal_id}'")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ins = sub.add_parser("install")
    ins.add_argument("--goal-id", required=True)
    ins.add_argument("--registry", default=None)
    ins.add_argument("--scope", action="append", default=[])
    ins.add_argument("--agent-id", default="cc")
    ins.add_argument("--interval", type=int, default=600)
    ins.add_argument("--form", default="--compact", choices=["--thin", "--compact", "--brief"])
    ins.add_argument("--python", default=None)
    for name in ("uninstall", "status"):
        p = sub.add_parser(name)
        p.add_argument("--goal-id", required=True)
    a = ap.parse_args()

    if a.cmd == "install":
        return install(a.goal_id, a.registry, a.scope, a.agent_id, a.interval, a.form, a.python)
    if a.cmd == "uninstall":
        return uninstall(a.goal_id)
    return status(a.goal_id)


if __name__ == "__main__":
    sys.exit(main())
