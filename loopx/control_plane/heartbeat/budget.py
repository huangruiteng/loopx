"""Heartbeat prompt budget helpers inside the heartbeat bounded context."""

from __future__ import annotations

from typing import Any


INTERFACE_BUDGET_CHARS = {
    "full": 12_000,
    "compact": 6_500,
    "brief": 3_500,
    "thin": 2_500,
    "visible_goal": 4_000,
}
NATIVE_GOAL_HOST_MAX_CHARS = INTERFACE_BUDGET_CHARS["visible_goal"]


def heartbeat_prompt_mode(
    *,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
) -> str:
    if full:
        return "full"
    if thin:
        return "thin"
    if brief:
        return "brief"
    if compact:
        return "compact"
    return "thin"


def prompt_budget_text(text: str, *, goal_id: str, active_state: str) -> str:
    return text.replace(goal_id, "<GOAL_ID>").replace(active_state, "<ACTIVE_STATE>")


def build_interface_budget(
    *,
    task_body: str,
    goal_id: str,
    active_state: str,
    full: bool = False,
    compact: bool = False,
    brief: bool = False,
    thin: bool = False,
    native_goal_host: bool = False,
) -> dict[str, Any]:
    mode = (
        "visible_goal"
        if native_goal_host
        else heartbeat_prompt_mode(full=full, compact=compact, brief=brief, thin=thin)
    )
    budget_text = prompt_budget_text(task_body, goal_id=goal_id, active_state=active_state)
    budget_chars = len(budget_text)
    max_chars = INTERFACE_BUDGET_CHARS[mode]
    return {
        "mode": mode,
        "char_count": len(task_body),
        "line_count": len(task_body.splitlines()),
        "budget_char_count": budget_chars,
        "max_chars": max_chars,
        "within_budget": budget_chars <= max_chars,
    }
