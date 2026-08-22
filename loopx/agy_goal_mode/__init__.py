from __future__ import annotations

import os
from pathlib import Path

AGY_INSTALL_SURFACE = "agy"
AGY_HOME_ENV = "AGY_CLI_HOME"
DEFAULT_AGY_HOME = ".gemini/antigravity-cli"
SKILLS_SUBDIR = "skills"
SKILLS_ROOT_LABEL = "AGY_CLI_HOME/skills"

# Native in-session automation primitives agy ships (verified against agy
# 1.1.18 live; no external driver involved). The `schedule` tool takes
# DurationSeconds + a wake Prompt, supports recurring wakes via MaxIterations
# and one-shot early-termination conditions.
AGY_NATIVE_WAKE_TOOLS = (
    "schedule",
    "manage_task",
    "invoke_subagent",
    "send_message",
    "manage_inbox",
)

AGY_NATIVE_WAKE_FACTS = (
    "native `schedule` tool: DurationSeconds + Prompt wake message, recurring "
    "wakes via MaxIterations, one-shot early-termination conditions",
    "background tasks (`manage_task`) and async subagents "
    "(`invoke_subagent`/`send_message`) wake a live session without an "
    "external driver",
    "`hooks.json` (user or plugin) runs PostToolUse/Stop/PostInvocation "
    "automation on tool events",
)

# Native goal primitive (built into the agy binary; live-verified on 1.1.18 in
# both the interactive TUI and headless `-p` print mode). The host injects a
# forced-continuation contract that audits work until the model emits the
# completion token; `GoalState` persists across the session.
AGY_GOAL_COMMAND = "/goal"
AGY_GOAL_COMMAND_DESCRIPTION = "Run until the specified goal is completely finished."
AGY_GOAL_COMPLETE_TOKEN = "<!-- GOAL_COMPLETE -->"
AGY_GOAL_CANCELLED_TOKEN = "<!-- GOAL_CANCELLED -->"


def agy_home(value: str | None = None) -> Path:
    """Antigravity CLI discovers user skills from AGY_CLI_HOME/skills.

    The Antigravity CLI binary is ``agy``. It ships a native goal primitive —
    the ``/goal <task>`` command ("Run until the specified goal is completely
    finished"): the host injects a forced-continuation contract that keeps
    auditing the work until the model emits ``<!-- GOAL_COMPLETE -->`` (or
    cancels with ``<!-- GOAL_CANCELLED -->``), verified live in both the
    interactive TUI and headless ``-p`` mode. It also ships native in-session
    automation — the ``schedule`` tool wakes a live session with a prompt on
    a timer (recurring via MaxIterations), and background tasks, async
    subagents and agent messages can wake a session without an external
    driver. LoopX gates every turn, wake and audit-continuation through
    quota; agy's goal loop enforces thoroughness, LoopX enforces pacing and
    authorization. The global skills root is
    ``~/.gemini/antigravity-cli/skills`` (directory-style ``SKILL.md``
    entries) and is shared with no other host, so installs there cannot
    collide with the ZCode or Gemini CLI surfaces.
    """
    raw = value or os.environ.get(AGY_HOME_ENV) or str(Path.home() / DEFAULT_AGY_HOME)
    return Path(raw).expanduser()
