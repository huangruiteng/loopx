"""Small helpers for driving the visible Codex CLI ``/goal`` TUI surface."""

from __future__ import annotations


CODEX_CLI_GOAL_COMMAND_PREFIX = "/goal "


def build_codex_cli_goal_tui_input(objective: str) -> str:
    """Return one pasteable TUI input that sets a Codex CLI goal.

    The Codex TUI parses ``/goal`` as a slash command before later paste
    buffers are associated with it, so the command and objective must be
    submitted as one input buffer.
    """

    return f"{CODEX_CLI_GOAL_COMMAND_PREFIX}{objective}"
