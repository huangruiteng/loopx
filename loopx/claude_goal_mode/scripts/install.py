#!/usr/bin/env python3
"""One-command GLOBAL install of goal-mode for Claude Code.

Mirrors `scripts/install-local.sh` (which installs the loopx CLI + Codex skill): a
single command wires goal-mode into the USER-level Claude Code config so it works
in *every* goal-connected project, with no per-project setup.

It (idempotently):
  1. ensures the `mcp` package is importable (pip install mcp if missing),
  2. deep-merges the PreToolUse hook + statusLine into ~/.claude/settings.json
     (USER level — statusline shows in every session),
  3. registers the loopx MCP server at user scope (`claude mcp add`),
  4. installs the /loopx user command.

After this, in ANY project that has been `loopx bootstrap`-ed, just type
`/loopx` in Claude Code — no arguments (it auto-detects the project's goal).

Usage:  python install.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_DIR = Path.home() / ".claude"
SETTINGS = CLAUDE_DIR / "settings.json"
# Dedicated venv for the MCP server's `mcp` dependency. A venv is the only
# reliable way to install it on PEP 668 "externally-managed" interpreters
# (Homebrew/system python on macOS), and it keeps the server isolated from the
# user's python so a brew upgrade can't wipe the dependency.
MCP_VENV = Path.home() / ".local" / "share" / "loopx" / "mcp-venv"


def _p(*parts) -> str:
    return str(PLUGIN_ROOT.joinpath(*parts)).replace("\\", "/")


def _python_cmd() -> str:
    """Interpreter to bake into hook / statusline / slash-command strings. Many
    machines register `python` but not `python3`, so resolve the real one at
    install time (prefer python3, then python, then this interpreter) and write
    its absolute path — never a bare `python3` that may not exist."""
    return shutil.which("python3") or shutil.which("python") or sys.executable


def settings_block() -> dict:
    # NOTE: MCP servers are NOT configured in settings.json (Claude Code ignores
    # mcpServers there). They live in ~/.claude.json via `claude mcp add` — see
    # install_mcp(). settings.json carries ONLY hooks + statusLine. We add no
    # global permission rules and no OS sandbox — loopx drives Claude Code
    # directly, and the PreToolUse hook is the whole gate (should_run +
    # write_scope + destructive-bash). So non-loopx projects keep their normal
    # behavior and we never change permissions machine-wide.
    py = _python_cmd()
    return {
        "hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [
                {"type": "command", "command": f'{py} "{_p("hooks", "goal_policy.py")}"', "timeout": 10}]}],
            # Stop hook = loopx-owned deterministic in-session continuation (the
            # Codex CLI cross-turn auto-advance analogue; loopx decides, not /goal).
            "Stop": [{"hooks": [
                {"type": "command", "command": f'{py} "{_p("hooks", "goal_stop.py")}"', "timeout": 15}]}],
        },
        "statusLine": {"type": "command", "command": f'{py} "{_p("statusline", "goal_status.py")}"'},
    }


def _venv_python(venv: Path) -> Path:
    sub = "Scripts" if sys.platform == "win32" else "bin"
    exe = "python.exe" if sys.platform == "win32" else "python"
    return venv / sub / exe


def _has_mcp(py) -> bool:
    try:
        return subprocess.run([str(py), "-c", "import mcp"], capture_output=True).returncode == 0
    except (FileNotFoundError, OSError):
        return False  # interpreter doesn't exist yet (e.g. venv not created)


def install_mcp(dry: bool, py: str):
    """Register the loopx MCP server the supported way: user scope via
    `claude mcp add` (writes ~/.claude.json). settings.json mcpServers is ignored by CC.
    `py` is an interpreter that can import `mcp` (see provision_mcp_python)."""
    import shutil as _sh
    claude = _sh.which("claude")
    mcp_path = _p("mcp", "loopx_mcp.py")
    add = ["mcp", "add", "--scope", "user", "loopx", "--", py, mcp_path]
    if claude:
        print(f"[mcp] claude mcp add --scope user loopx -- {py} <loopx_mcp.py>")
        if not dry:
            # remove the new id (idempotent) and the legacy goal-harness id (migration)
            subprocess.run([claude, "mcp", "remove", "--scope", "user", "loopx"],
                           capture_output=True, text=True)
            subprocess.run([claude, "mcp", "remove", "--scope", "user", "goal-harness"],
                           capture_output=True, text=True)
            r = subprocess.run([claude, *add], capture_output=True, text=True)
            if r.returncode != 0:
                print("  (mcp add failed; add manually:\n   claude " + " ".join(add) + "\n  " +
                      (r.stdout + r.stderr)[:200] + ")")
    else:
        print("[mcp] claude CLI not on PATH — add the MCP server manually:\n   claude " + " ".join(add))


def deep_merge(base: dict, add: dict) -> dict:
    for k, v in add.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_merge(base[k], v)
        elif isinstance(v, list) and isinstance(base.get(k), list):
            base[k] += [x for x in v if x not in base[k]]
        else:
            base[k] = v
    return base


def provision_mcp_python(dry: bool) -> str:
    """Return an interpreter path that can `import mcp`, installing it if needed.

    Order of preference:
      1. the installer's own interpreter, if it already has mcp;
      2. a reused dedicated venv (~/.local/share/loopx/mcp-venv) that has mcp;
      3. a freshly created venv with mcp pip-installed (works under PEP 668);
      4. last resort: `pip install --break-system-packages` into the current python.
    Returns the chosen interpreter; falls back to "python3" with a loud warning if
    every strategy fails (the MCP tools then won't load until mcp is installed).
    """
    if _has_mcp(sys.executable):
        print(f"[deps] mcp already importable by {sys.executable}")
        return sys.executable

    vpy = _venv_python(MCP_VENV)
    if _has_mcp(vpy):
        print(f"[deps] reusing mcp venv {MCP_VENV}")
        return str(vpy)

    if dry:
        print(f"[deps] (dry-run) would create venv {MCP_VENV} and pip install mcp")
        return str(vpy)

    print(f"[deps] creating mcp venv {MCP_VENV} (python is externally-managed, so isolate the dep) ...")
    MCP_VENV.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "venv", str(MCP_VENV)], capture_output=True, text=True)
    if r.returncode == 0:
        subprocess.run([str(vpy), "-m", "pip", "install", "-q", "--upgrade", "pip"], capture_output=True, text=True)
        pip = subprocess.run([str(vpy), "-m", "pip", "install", "-q", "mcp"], capture_output=True, text=True)
        if pip.returncode == 0 and _has_mcp(vpy):
            print(f"[deps] mcp installed into {MCP_VENV}")
            return str(vpy)
        print("[deps] venv pip install failed:\n" + (pip.stdout + pip.stderr)[:300])
    else:
        print("[deps] venv creation failed:\n" + (r.stdout + r.stderr)[:300])

    print("[deps] last resort: pip install --break-system-packages mcp")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--break-system-packages", "mcp"],
                   capture_output=True, text=True)
    if _has_mcp(sys.executable):
        return sys.executable

    print("[deps] WARNING: could not install `mcp`; the loopx MCP tools (should_run/claim_task/"
          "complete_task) will NOT load.\n"
          f"       Fix manually:  {sys.executable} -m venv {MCP_VENV} && "
          f"{vpy} -m pip install mcp")
    return "python3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dry = a.dry_run

    mcp_python = provision_mcp_python(dry)

    # merge user-level settings (preserve existing)
    cur = {}
    if SETTINGS.exists():
        try:
            cur = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    # prune any prior goal-mode hook entries (avoid stacking across reinstalls /
    # release dirs, and drop legacy goal-harness paths) for both events we own
    for event, marker in (("PreToolUse", "goal_policy.py"), ("Stop", "goal_stop.py")):
        for grp in (cur.get("hooks", {}) or {}).get(event, []) or []:
            grp["hooks"] = [h for h in grp.get("hooks", [])
                            if marker not in str(h.get("command", ""))]
        if isinstance(cur.get("hooks", {}).get(event), list):
            cur["hooks"][event] = [g for g in cur["hooks"][event] if g.get("hooks")]
    # drop the legacy loopx GLOBAL credential-deny (older installs added it; we no
    # longer touch permissions machine-wide — minimal intervention)
    if isinstance(cur.get("permissions"), dict):
        cur["permissions"]["deny"] = [r for r in (cur["permissions"].get("deny") or [])
                                      if r not in ("Read(~/.ssh/**)", "Read(~/.aws/**)")]
        if not cur["permissions"].get("deny"):
            cur["permissions"].pop("deny", None)
        if not cur["permissions"]:
            cur.pop("permissions", None)
    # remove any previously-misplaced MCP entry from settings.json (CC ignores it; it belongs in ~/.claude.json)
    if isinstance(cur.get("mcpServers"), dict):
        for stale in ("loopx", "goal-harness"):
            cur["mcpServers"].pop(stale, None)
        if not cur["mcpServers"]:
            cur.pop("mcpServers")
    merged = deep_merge(cur, settings_block())
    print(f"[settings] merge hook + statusLine into {SETTINGS}")
    if not dry:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    install_mcp(dry, mcp_python)

    # NOTE: we intentionally do NOT install a separate ~/.claude/skills entry for
    # Claude Code — it would surface as a duplicate slash entry. The loop
    # discipline is inlined into the /loopx command body below, so loopx shows
    # up as exactly one slash command: /loopx. (Remove any previously-installed
    # copies, including the goal-harness era name.)
    for old in ("goal-harness-project", "loopx-project"):
        old_skill = CLAUDE_DIR / "skills" / old
        if old_skill.exists():
            print(f"[skill] removing duplicate CC skill {old_skill}")
            if not dry:
                shutil.rmtree(old_skill, ignore_errors=True)

    # install user-level /loopx command (absolute path; ${CLAUDE_PLUGIN_ROOT}
    # is only defined for plugin commands, so bake the path for a personal command)
    entry = _p("scripts", "goalmode_cmd.py")
    py = _python_cmd()
    cmd_md = (
        "---\n"
        "description: loopx goal-mode (not Claude Code's built-in /goal). "
        "`/loopx <task>` sets up a goal and works in-session (the Stop hook keeps it going across turns); "
        "bare /loopx = ON; background = opt-in headless timer; off | status.\n"
        "argument-hint: <task to do>  |  (no args = on)  |  background  |  off  |  status\n"
        f"allowed-tools: Bash({py}:*)\n"
        "---\n\n"
        "Run the goal-mode entry and read its output:\n\n"
        f"!`{py} \"{entry}\" $ARGUMENTS`\n\n"
        "FIRST, branch on the output — do this before anything else:\n"
        "- If the output does NOT contain `READY: begin working` (i.e. `off`, a `status` detail "
        "block, or a \"set a goal\" prompt): it is already the complete, user-facing result — show "
        "it to the user VERBATIM and STOP. Do NOT call any tool, plan, or loop, and do NOT summarize "
        "a multi-line `status`/detail block into one line.\n\n"
        "If the output says `READY: begin working`, the output already prints the exact control-plane "
        "steps with the goal_id, agent_id, and todo_id filled in — FOLLOW THEM VERBATIM. Use the wired "
        "`loopx` MCP tools (`should_run`, `claim_task`, `complete_task`) which are zero-config: they read "
        "the goal/agent from goal-mode state, so call them as printed. Do NOT run `loopx --help`, probe "
        "`loopx quota ...` by hand, or guess a goal-id — everything you need is in the output above. "
        "goal-mode STAYS ON until the user runs `/loopx off` — do NOT turn it off yourself. "
        "While ON, every tool call is gated by the loopx PreToolUse policy: read-only allowed; "
        "writes only within the goal's write_scope; should_run=false pauses delivery; destructive "
        "bash denied.\n\n"
        "SAFETY OFFER (do this ONCE, before you start the loop, only when you see "
        "`READY: begin working`): tell the user in one line that this goal will run largely "
        "unattended, gated only by the loopx hook, and that enabling **auto mode** (press Shift+Tab "
        "to cycle to it) adds a classifier that catches exfil/escalation the hook can't — then ask "
        "whether they want it on. Auto mode is the user's own toggle (you cannot force it); wait for "
        "their choice, then begin. Do not repeat this offer on later `/loopx` calls in the same session.\n"
    )
    cmd_path = CLAUDE_DIR / "commands" / "loopx.md"
    # migrate the old entry name: the command is now /loopx, drop the stale /goalmode file
    old_cmd = CLAUDE_DIR / "commands" / "goalmode.md"
    if old_cmd.exists():
        print(f"[command] removing old entry {old_cmd}")
        if not dry:
            old_cmd.unlink()
    print(f"[command] /loopx -> {cmd_path}")
    if not dry:
        cmd_path.parent.mkdir(parents=True, exist_ok=True)
        cmd_path.write_text(cmd_md, encoding="utf-8")

    print("\ngoal-mode installed globally for Claude Code.")
    print("Next: in ANY project that has a goal (loopx bootstrap), open Claude Code and type:")
    print("    /loopx            (no args — auto-detects this project's goal)")
    print("    /loopx off        (exit goal-mode)")
    print("Isolation: the PreToolUse hook gates tools (should_run + write_scope +")
    print("  destructive-bash). For STRONG isolation (untrusted code / unattended),")
    print("  run Claude Code inside a dev container or VM.")
    print("Restart any open Claude Code session so the hook/statusline load.")
    if dry:
        print("\n(dry-run: nothing written)")


if __name__ == "__main__":
    main()
