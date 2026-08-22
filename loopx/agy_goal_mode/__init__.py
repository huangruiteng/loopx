from __future__ import annotations

from pathlib import Path
from typing import Any

AGY_INSTALL_SURFACE = "agy"
DEFAULT_AGY_HOME = ".gemini/antigravity-cli"
SKILLS_SUBDIR = "skills"
SKILLS_ROOT_LABEL = "~/.gemini/antigravity-cli/skills"

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


def agy_activation_extras() -> dict[str, Any]:
    """Keyword overrides for ``_agy_cli_activation``'s facade call.

    Keeps the agy host facts (goal command, tokens, wake tools, gate text,
    activation steps) in the agy package instead of growing
    ``host_loop_activation.py`` past its module metric budget. agy ships BOTH
    halves of a goal-mode host, verified live on 1.1.18: a native goal
    primitive — ``/goal <task>`` ("Run until the specified goal is completely
    finished"), whose host-side forced continuation audits work until the
    model emits ``<!-- GOAL_COMPLETE -->`` — and a native in-session
    scheduler (``schedule`` tool plus background-task/subagent wakes). The
    loop and wakes live and die with the session; no cross-session daemon.
    """
    return {
        "activation_method": "bind_native_goal_with_advisory_quota_entry",
        "extra_host_mutation": {
            "host_loop_primitive": "agy-/goal-and-schedule-tool",
            "loop_driver": "agy_native_goal_loop_with_schedule_wakes",
            "quota_gate_enforcement": "advisory_only",
            "native_goal_command": AGY_GOAL_COMMAND,
            "goal_complete_token": AGY_GOAL_COMPLETE_TOKEN,
            "goal_cancelled_token": AGY_GOAL_CANCELLED_TOKEN,
            "native_wake_tools": list(AGY_NATIVE_WAKE_TOOLS),
            "missing_host_tool_gate": (
                "agy's /goal loop and native wakes fire only while the CLI "
                "session is alive; there is no cross-session daemon. LoopX has "
                "no host hook intercepting native continuations, so quota "
                "pacing is advisory: the facade instructs, it cannot enforce. "
                "If the session ends before the goal is done, show the exact "
                "heartbeat-prompt command for the user to run and do not claim "
                "unattended heartbeat support."
            ),
        },
        "extra_activation_steps": [
            "Bind the objective with the native goal command: "
            "`/goal <task_body>` — agy's forced continuation audits the work "
            "until completion is emitted; `<!-- GOAL_COMPLETE -->` ends the "
            "goal loop and `<!-- GOAL_CANCELLED -->` cancels it.",
            "Start every turn, native wake, and audit-continuation with "
            "`quota should-run` and honor a stop/throttle decision before any "
            "delivery work — instructed pacing, not a host-enforced gate.",
            "When a turn ends with work remaining and quota allows more, arm "
            "the next bounded segment with the native `schedule` tool "
            "(recurring wakes bounded by MaxIterations); the wake re-enters "
            "through `quota should-run` on the same advisory basis.",
        ],
        "host_scheduler_note": (
            "the native `/goal` loop and `schedule` tool drive this session; "
            "quota should-run entry is advisory guidance in the facade, not a "
            "host-enforced gate."
        ),
    }


def agy_home(value: str | None = None) -> Path:
    """The fixed Antigravity CLI home: ``~/.gemini/antigravity-cli``.

    agy discovers global skills from ``~/.gemini/antigravity-cli/skills``
    using the documented flat layout — one markdown file per skill
    (``skills/<name>.md`` with front matter). The official CLI docs do not
    document any home override, so LoopX exposes none either: installs target
    exactly this path (HOME-relative, which keeps tests hermetic), and the
    root is shared with no other host — Gemini CLI reads ``~/.gemini/skills``,
    ZCode reads ``~/.agents/skills``. ``value`` is an internal injection point
    for tests, not a public override.
    """
    raw = value or str(Path.home() / DEFAULT_AGY_HOME)
    return Path(raw).expanduser()
