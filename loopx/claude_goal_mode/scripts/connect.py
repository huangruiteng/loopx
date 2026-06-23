#!/usr/bin/env python3
"""One-command Claude Code connect for loopx — the CC counterpart of how
`loopx connect` installs the Codex skill.

Does (idempotently):
  1. `loopx connect` (if --objective given) -> writes registry + state.
  2. Records agent_backend=claude in .loopx/registry.json (additive).
  3. Scaffolds .claude/settings.json in the project: PreToolUse goal policy hook,
     statusline, and the loopx MCP server (absolute paths into this package).
  4. With --install: copies the goal-mode command into ~/.claude (via install.py).

Usage:
  python connect.py --project /path --goal-id G [--objective O] \
     [--registry R] [--scope DIR ...] [--install] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _gh_prefix():
    exe = shutil.which("loopx")
    return [exe] if exe else [sys.executable, "-m", "loopx.cli"]


def deep_merge(base: dict, add: dict) -> dict:
    for k, v in add.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        elif isinstance(v, list) and isinstance(base.get(k), list):
            base[k] += [x for x in v if x not in base[k]]
        else:
            base[k] = v
    return base


def _p(*parts) -> str:
    # forward slashes: valid for Windows Python paths and avoids JSON backslash escaping
    return str(PLUGIN_ROOT.joinpath(*parts)).replace("\\", "/")


def _python_cmd() -> str:
    """Interpreter to bake into hook / statusline / MCP commands. Many machines
    register `python` but not `python3`, so resolve the real one at connect time
    (prefer python3, then python, then this interpreter)."""
    return shutil.which("python3") or shutil.which("python") or sys.executable


def settings_block() -> dict:
    pol = _p("hooks", "goal_policy.py")
    stop = _p("hooks", "goal_stop.py")
    sline = _p("statusline", "goal_status.py")
    mcp = _p("mcp", "loopx_mcp.py")
    py = _python_cmd()
    return {
        "hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": f'{py} "{pol}"', "timeout": 10}]}],
            # Stop hook = loopx-owned deterministic in-session continuation (the
            # Codex CLI cross-turn auto-advance analogue; loopx decides, not /goal).
            "Stop": [{"hooks": [
                {"type": "command", "command": f'{py} "{stop}"', "timeout": 15}]}],
        },
        "statusLine": {"type": "command", "command": f'{py} "{sline}"'},
        "mcpServers": {"loopx": {"command": py, "args": [mcp]}},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--goal-id", required=True)
    ap.add_argument("--objective", default=None)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--scope", action="append", default=[])
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    dry = a.dry_run

    # 1. connect (optional)
    if a.objective:
        cmd = list(_gh_prefix()) + (["--registry", a.registry] if a.registry else []) + \
              ["connect", "--goal-id", a.goal_id, "--objective", a.objective, "--state-file", f".claude/goals/{a.goal_id}/ACTIVE_GOAL_STATE.md"]
        print("[connect]", " ".join(cmd))
        if not dry:
            try:
                subprocess.run(cmd, cwd=str(proj), check=False, timeout=120)
            except Exception as e:
                print("  (connect skipped/failed:", e, ")")

    # 2. record agent_backend in project registry (additive); prefer loopx, fall back to legacy
    if a.registry:
        reg = Path(a.registry)
    else:
        reg = proj / ".loopx" / "registry.json"
        if not reg.exists() and (proj / ".goal-harness" / "registry.json").exists():
            reg = proj / ".goal-harness" / "registry.json"
    if reg.exists():
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
            data.setdefault("agent_backends", [])
            if "claude" not in data["agent_backends"]:
                data["agent_backends"].append("claude")
            print(f"[registry] mark agent_backends += claude  ({reg})")
            if not dry:
                reg.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print("  (registry annotate skipped:", e, ")")
    else:
        print(f"[registry] {reg} not found yet (run with --objective to connect first)")

    # 3. scaffold .claude/settings.json
    settings = proj / ".claude" / "settings.json"
    block = settings_block()
    cur = {}
    if settings.exists():
        try:
            cur = json.loads(settings.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    merged = deep_merge(cur, block)
    print(f"[.claude] scaffold {settings} (PreToolUse + Stop hooks + statusline + MCP)")
    if not dry:
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    # 4. optional global install of the /loopx command + user MCP
    if a.install:
        installer = PLUGIN_ROOT / "scripts" / "install.py"
        print(f"[install] {installer}")
        if not dry and installer.exists():
            subprocess.run([sys.executable, str(installer)], check=False)

    print("\nNext:")
    print("  open Claude Code in the project, then:")
    print("    /loopx            # bare = arm goal-mode for this project's goal")
    print("    /loopx off        # stop goal-mode")
    print("  or run unattended:")
    print(f"    python {PLUGIN_ROOT / 'scripts' / 'goal_run.py'} --goal-id {a.goal_id}" +
          (f" --registry {a.registry}" if a.registry else ""))
    if dry:
        print("\n(dry-run: nothing written)")


if __name__ == "__main__":
    main()
