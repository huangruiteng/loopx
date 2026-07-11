#!/usr/bin/env python3
"""Focused smoke for fresh Codex CLI goal TUI session startup."""

from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import loopx.codex_cli_goal_tui as goal_tui  # noqa: E402


def main() -> int:
    calls: list[tuple[str, object]] = []

    def fake_run(command: list[str], **_kwargs: object) -> None:
        calls.append(("run", command))

    def fake_kill(tmux_name: str) -> None:
        calls.append(("kill", tmux_name))

    def fake_type_text_and_submit(*, tmux_name: str, text: str) -> None:
        calls.append(("type", (tmux_name, text)))

    original_run = goal_tui.subprocess.run
    original_wait = goal_tui.wait_for_codex_cli_tui_ready
    original_prewarm = goal_tui.prewarm_codex_cli_goal_thread
    original_kill = goal_tui.tmux_kill_session
    original_capture = goal_tui.tmux_capture
    original_type_text_and_submit = goal_tui.tmux_type_text_and_submit
    try:
        goal_tui.subprocess.run = fake_run  # type: ignore[assignment]
        goal_tui.tmux_kill_session = fake_kill  # type: ignore[assignment]
        goal_tui.wait_for_codex_cli_tui_ready = (  # type: ignore[assignment]
            lambda *_args, **_kwargs: True
        )
        goal_tui.prewarm_codex_cli_goal_thread = (  # type: ignore[assignment]
            lambda **_kwargs: True
        )
        stage, prewarmed = goal_tui.start_codex_cli_goal_tui_session(
            tmux_name="fresh-goal",
            cwd="/tmp/public-workspace",
            shell_command="codex --no-alt-screen",
            thread_prewarm=True,
            thread_prewarm_timeout_sec=120,
        )
        assert (stage, prewarmed) == ("", True)
        assert calls[0] == (
            "run",
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                "fresh-goal",
                "-c",
                "/tmp/public-workspace",
                "codex --no-alt-screen",
            ],
        )

        calls.clear()
        goal_tui.wait_for_codex_cli_tui_ready = (  # type: ignore[assignment]
            lambda *_args, **_kwargs: False
        )
        stage, prewarmed = goal_tui.start_codex_cli_goal_tui_session(
            tmux_name="not-ready",
            cwd="/tmp/public-workspace",
            shell_command="codex",
            thread_prewarm=False,
            thread_prewarm_timeout_sec=120,
        )
        assert (stage, prewarmed) == ("tui_ready_timeout", False)
        assert calls[-1] == ("kill", "not-ready")

        calls.clear()
        goal_tui.wait_for_codex_cli_tui_ready = (  # type: ignore[assignment]
            lambda *_args, **_kwargs: True
        )
        goal_tui.prewarm_codex_cli_goal_thread = (  # type: ignore[assignment]
            lambda **_kwargs: False
        )
        stage, prewarmed = goal_tui.start_codex_cli_goal_tui_session(
            tmux_name="prewarm-failed",
            cwd="/tmp/public-workspace",
            shell_command="codex",
            thread_prewarm=True,
            thread_prewarm_timeout_sec=120,
        )
        assert (stage, prewarmed) == ("thread_prewarm_timeout", False)
        assert calls[-1] == ("kill", "prewarm-failed")

        calls.clear()
        goal_tui.prewarm_codex_cli_goal_thread = original_prewarm
        goal_tui.tmux_type_text_and_submit = fake_type_text_and_submit  # type: ignore[assignment]
        goal_tui.tmux_capture = (  # type: ignore[assignment]
            lambda _tmux_name: goal_tui.CODEX_CLI_GOAL_THREAD_PREWARM_MARKER
        )
        assert goal_tui.prewarm_codex_cli_goal_thread(
            tmux_name="typed-prewarm",
            timeout_sec=1,
        )
        assert calls == [
            (
                "type",
                (
                    "typed-prewarm",
                    goal_tui.CODEX_CLI_GOAL_THREAD_PREWARM_PROMPT,
                ),
            )
        ]
    finally:
        goal_tui.subprocess.run = original_run  # type: ignore[assignment]
        goal_tui.wait_for_codex_cli_tui_ready = original_wait  # type: ignore[assignment]
        goal_tui.prewarm_codex_cli_goal_thread = original_prewarm  # type: ignore[assignment]
        goal_tui.tmux_kill_session = original_kill  # type: ignore[assignment]
        goal_tui.tmux_capture = original_capture  # type: ignore[assignment]
        goal_tui.tmux_type_text_and_submit = original_type_text_and_submit  # type: ignore[assignment]

    print("codex-cli-goal-tui-session-smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
