#!/usr/bin/env python3
"""Goal-mode context resolution — registry-driven, mirroring the Codex model.

LoopX's registry (``.loopx/registry.json``) is the single source of truth for the
project's goal (goal_id / agent / scope), exactly as on Codex. We resolve it by
walking up from cwd to the nearest ``.loopx/`` (or legacy ``.goal-harness/``)
registry — so two sessions in different projects are independent, and two
sessions in the SAME project share the one goal.

"Goal-mode ON / armed" for a project = a ``.claude/loop.md`` exists (written by
``/loopx <task>``). That file is the per-iteration protocol that Claude Code's
native ``/loop`` runs; its presence means loopx is driving this project. The
OPTIONAL PreToolUse hook + statusline gate on this, so they only act where loopx
is actually active. ``LOOPX_GOAL_FORCE=1`` forces armed=true for tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REGISTRY_DIRS = (".loopx", ".goal-harness")  # prefer loopx; fall back to legacy


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

    Returns goal_id, registry path, agent_id (primary/first registered),
    write_scope (the goal's repo), and project_root — everything the hooks / MCP /
    statusline need, all sourced from the registry."""
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


def loop_md_path(project_root) -> Path:
    return Path(project_root) / ".claude" / "loop.md"


def is_armed(project_root) -> bool:
    """Armed = the project has a `.claude/loop.md` (loopx is driving), or forced."""
    if os.environ.get("LOOPX_GOAL_FORCE") == "1":
        return True
    return bool(project_root) and loop_md_path(project_root).exists()


def active_context(cwd) -> dict | None:
    """goal_context for cwd, but only when goal-mode is armed; else None."""
    ctx = goal_context(cwd)
    if not ctx or not is_armed(ctx.get("project_root")):
        return None
    return ctx
