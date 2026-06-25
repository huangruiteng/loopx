from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .message_card import compact_markdown
from .scheduler_plan_reporter import (
    render_scheduler_next_batch_chat_text,
    render_scheduler_plan_chat_text,
)


def bridge_help_text() -> str:
    return "\n".join(
        [
            "LoopX Feishu bridge.",
            "",
            "Commands:",
            "/help - show this message",
            "/status - show compact LoopX status",
            "/plan - show safe parallel scheduler plan",
            "/next - show next dispatchable scheduler batch",
            "/check - run LoopX boundary check",
            "/ask <task> - create a LoopX todo and receive progress cards",
        ]
    )


def loopx_status_text(
    *,
    run_text: Callable[..., str],
    loopx_bin: str,
    registry: str,
    agent_id: str,
    max_chars: int,
) -> str:
    out = run_text([loopx_bin, "--registry", registry, "status", "--agent-id", agent_id], timeout=30)
    interesting: list[str] = []
    for line in out.splitlines():
        if (
            line.startswith("- ok:")
            or "Attention Queue" in line
            or "waiting_on=" in line
            or "next_agent_todo" in line
            or "next_user_todo" in line
            or "quota:" in line
            or "action:" in line
            or "status=" in line
        ):
            interesting.append(line)
    return compact_markdown("\n".join(interesting) or out, max_chars=max_chars, suffix="...")


def loopx_check_text(
    *,
    run_text: Callable[..., str],
    loopx_bin: str,
    registry: str,
    control_root: Path,
    max_chars: int,
) -> str:
    return compact_markdown(
        run_text([loopx_bin, "--registry", registry, "check", "--scan-root", str(control_root)], timeout=30),
        max_chars=max_chars,
        suffix="...",
    )


def loopx_scheduler_plan_text(
    *,
    run_json: Callable[..., dict[str, Any]],
    loopx_bin: str,
    registry: str,
    goal_id: str,
    agent_id: str,
    max_chars: int,
) -> str:
    return render_scheduler_plan_chat_text(
        run_json(
            _scheduler_command(
                loopx_bin=loopx_bin,
                registry=registry,
                scheduler_command="plan",
                goal_id=goal_id,
                agent_id=agent_id,
            ),
            timeout=45,
        ),
        max_chars=max_chars,
    )


def loopx_scheduler_next_batch_text(
    *,
    run_json: Callable[..., dict[str, Any]],
    loopx_bin: str,
    registry: str,
    goal_id: str,
    agent_id: str,
    max_chars: int,
) -> str:
    return render_scheduler_next_batch_chat_text(
        run_json(
            _scheduler_command(
                loopx_bin=loopx_bin,
                registry=registry,
                scheduler_command="next-batch",
                goal_id=goal_id,
                agent_id=agent_id,
            ),
            timeout=45,
        ),
        max_chars=max_chars,
    )


def _scheduler_command(
    *,
    loopx_bin: str,
    registry: str,
    scheduler_command: str,
    goal_id: str,
    agent_id: str,
) -> list[str]:
    return [
        loopx_bin,
        "--registry",
        registry,
        "scheduler",
        scheduler_command,
        "--format",
        "json",
        "--goal-id",
        goal_id,
        "--agent-id",
        agent_id,
    ]
