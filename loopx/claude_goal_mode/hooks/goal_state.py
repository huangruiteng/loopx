#!/usr/bin/env python3
"""Goal-mode context resolution — registry-driven, mirroring the Codex model.

There is NO separate goal-mode "active" state file. LoopX's registry
(``.loopx/registry.json``) is the single source of truth, exactly as on Codex,
where a goal lives in the registry (keyed by repo) and an automation either runs
against it or not. We resolve the goal for the current project by walking up from
cwd to the nearest ``.loopx/`` (or legacy ``.goal-harness/``) registry — so two
sessions in different projects are independent, and two sessions in the SAME
project share the one goal (the replaceable-worker model).

"Goal-mode ON" = an armed marker for the goal exists (set by ``/loopx`` /
``/loopx on``, removed by ``/loopx off``). It is INDEPENDENT of the launchd
heartbeat: by default arming relies on the in-session Stop hook to keep working,
and the background headless heartbeat is OPT-IN via ``/loopx background``. Hooks
gate only while armed. (A heartbeat plist also counts as armed — for the
background mode and backward compatibility.)

``LOOPX_GOAL_FORCE=1`` forces armed=true for in-process drivers/tests that gate
without a marker (e.g. goal_driver.py).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REGISTRY_DIRS = (".loopx", ".goal-harness")  # prefer loopx; fall back to legacy
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
LABEL_PREFIX = "com.loopx.heartbeat."
GOAL_MODE_DIR = Path.home() / ".local" / "share" / "loopx" / "goal-mode"


def find_registry(cwd) -> Path | None:
    """Nearest ancestor of cwd (inclusive) holding a registry.json, else None."""
    try:
        cur = Path(cwd).resolve()
    except Exception:
        return None
    for d in [cur, *cur.parents]:
        for sub in REGISTRY_DIRS:
            cand = d / sub / "registry.json"
            if cand.exists():
                return cand
    return None


def project_root_for(cwd) -> Path | None:
    reg = find_registry(cwd)
    return reg.parent.parent if reg else None


def _agent_of(goal: dict):
    coord = goal.get("coordination") or {}
    primary = coord.get("primary_agent")
    if primary:
        return str(primary)
    for entry in coord.get("registered_agents") or []:
        if isinstance(entry, dict):
            val = entry.get("id") or entry.get("agent_id") or entry.get("name")
            if val:
                return str(val)
        elif entry:
            return str(entry)
    return None


def goal_context(cwd) -> dict | None:
    """The current project's goal, read live from the registry. None if no goal.

    Returns goal_id, registry path, agent_id (primary/first registered), and
    write_scope (the goal's repo) — everything the hooks/MCP need, all sourced
    from the registry instead of a duplicated state file."""
    reg = find_registry(cwd)
    if not reg:
        return None
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
    except Exception:
        return None
    goals = data.get("goals") or []
    if not goals:
        return None
    chosen = next((g for g in goals if (g.get("coordination") or {}).get("primary_agent")), goals[0])
    repo = chosen.get("repo")
    root = reg.parent.parent
    scope = [str(repo).replace("\\", "/")] if repo else [str(root).replace("\\", "/")]
    return {
        "goal_id": chosen.get("id"),
        "registry": str(reg).replace("\\", "/"),
        "agent_id": _agent_of(chosen),
        "write_scope": scope,
        "project_root": str(root).replace("\\", "/"),
    }


def _safe(goal_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(goal_id)).strip("-") or "goal"


def heartbeat_label(goal_id: str) -> str:
    return LABEL_PREFIX + _safe(goal_id)


def heartbeat_plist(goal_id: str) -> Path:
    return LAUNCH_AGENTS / f"{heartbeat_label(goal_id)}.plist"


def armed_marker(goal_id: str) -> Path:
    return GOAL_MODE_DIR / f"{heartbeat_label(goal_id)}.armed"


def arm(goal_id) -> None:
    """Turn goal-mode ON for this goal (independent of the launchd heartbeat)."""
    if not goal_id:
        return
    GOAL_MODE_DIR.mkdir(parents=True, exist_ok=True)
    armed_marker(goal_id).write_text("on", encoding="utf-8")


def disarm(goal_id) -> None:
    """Turn goal-mode OFF for this goal (remove the armed marker)."""
    if not goal_id:
        return
    try:
        armed_marker(goal_id).unlink()
    except OSError:
        pass


def is_armed(goal_id) -> bool:
    """Goal-mode is ON when the goal is armed — an armed marker exists, OR the
    launchd heartbeat plist exists (background mode / backward compat), OR forced
    via env."""
    if os.environ.get("LOOPX_GOAL_FORCE") == "1":
        return True
    if not goal_id:
        return False
    return armed_marker(goal_id).exists() or heartbeat_plist(goal_id).exists()


def active_context(cwd) -> dict | None:
    """goal_context for cwd, but only when goal-mode is armed; else None."""
    ctx = goal_context(cwd)
    if not ctx or not is_armed(ctx.get("goal_id")):
        return None
    return ctx
