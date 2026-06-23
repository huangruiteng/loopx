#!/usr/bin/env python3
"""Connect a project to loopx for Claude Code (PROJECT-scoped).

Thin wrapper: (1) `loopx connect` the repo, (2) mark `agent_backends += claude`
in the project registry, (3) install the Claude adapter at PROJECT scope (the
loopx MCP + the `/loopx` command into this project's `.claude/`) by delegating to
install.py. No global config, no OS sandbox. The run loop is native `/loop`.

  python connect.py --project DIR --goal-id G [--objective "…"] [--harden]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _gh_prefix():
    exe = shutil.which("loopx")
    return [exe] if exe else [sys.executable, "-m", "loopx.cli"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--goal-id", required=True)
    ap.add_argument("--objective", default=None)
    ap.add_argument("--registry", default=None)
    ap.add_argument("--harden", action="store_true",
                    help="also install the optional PreToolUse should_run gate + statusline (project scope)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    dry = a.dry_run

    # 1. connect the repo to loopx (optional, when an objective is given)
    if a.objective:
        cmd = list(_gh_prefix()) + (["--registry", a.registry] if a.registry else []) + \
              ["connect", "--goal-id", a.goal_id, "--objective", a.objective,
               "--state-file", f".claude/goals/{a.goal_id}/ACTIVE_GOAL_STATE.md"]
        print("[connect]", " ".join(cmd))
        if not dry:
            try:
                subprocess.run(cmd, cwd=str(proj), check=False, timeout=120)
            except Exception as e:
                print("  (connect skipped/failed:", e, ")")

    # 2. mark agent_backends += claude in the project registry (additive)
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

    # 3. install the Claude adapter at PROJECT scope (MCP + /loopx command [+ --harden])
    installer = PLUGIN_ROOT / "scripts" / "install.py"
    inst = [sys.executable, str(installer), "--scope", "project", "--project", str(proj)]
    if a.harden:
        inst.append("--harden")
    if dry:
        inst.append("--dry-run")
    print("[install]", " ".join(inst))
    subprocess.run(inst, check=False)

    print("\nNext: open Claude Code in the project, then:")
    print("    /loopx <task>     # set the goal, write .claude/loop.md, do the first segment")
    print("    /loop             # drive the loop (native; loopx should_run gates each tick)")
    print("    /loopx off        # remove the loop protocol")


if __name__ == "__main__":
    main()
