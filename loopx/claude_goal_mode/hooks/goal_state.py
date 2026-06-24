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
import re
from pathlib import Path

REGISTRY_DIRS = (".loopx", ".goal-harness")  # prefer loopx; fall back to legacy

_ARMED_RE = re.compile(r"<!--\s*loopx:armed\s*(\{.*?\})\s*-->")


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


def loop_md_path(project_root) -> Path:
    return Path(project_root) / ".claude" / "loop.md"


def read_armed_goal(project_root) -> dict | None:
    """The goal_id/agent_id that `/loopx` armed for THIS project, parsed from the
    `loopx:armed` marker it writes at the top of `.claude/loop.md`. None if the
    project isn't armed or the marker is absent/unparseable.

    This is what lets goal_context resolve the *armed* goal rather than guessing
    by registry order, so a multi-goal repo gates/claims/completes the goal the
    user actually set up."""
    if not project_root:
        return None
    try:
        text = loop_md_path(project_root).read_text(encoding="utf-8")
    except Exception:
        return None
    m = _ARMED_RE.search(text)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except Exception:
        return None
    return d if isinstance(d, dict) and d.get("goal_id") else None


def goal_context(cwd) -> dict | None:
    """The current project's goal, read live from the registry. None if no goal.

    Returns goal_id, registry path, agent_id, write_scope (the goal's repo), and
    project_root — everything the hooks / MCP / statusline need. When the project
    is armed (`.claude/loop.md` carries a `loopx:armed` marker), the marker's goal
    is authoritative; otherwise we fall back to the primary-agent / first goal."""
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
    root = reg.parent.parent
    # Prefer the goal /loopx armed for this project; only fall back to registry
    # order when there is no armed marker or it points at a goal not in the registry.
    armed = read_armed_goal(root)
    chosen = None
    armed_agent = None
    if armed:
        chosen = next((g for g in goals if g.get("id") == armed.get("goal_id")), None)
        if chosen is not None:
            armed_agent = armed.get("agent_id")
    if chosen is None:
        chosen = next((g for g in goals if (g.get("coordination") or {}).get("primary_agent")), goals[0])
    repo = chosen.get("repo")
    scope = [str(repo).replace("\\", "/")] if repo else [str(root).replace("\\", "/")]
    return {
        "goal_id": chosen.get("id"),
        "registry": str(reg).replace("\\", "/"),
        "agent_id": armed_agent or _agent_of(chosen),
        "write_scope": scope,
        "project_root": str(root).replace("\\", "/"),
    }


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
