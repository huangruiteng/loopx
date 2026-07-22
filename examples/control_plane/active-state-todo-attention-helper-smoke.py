#!/usr/bin/env python3
"""Smoke-test active-state todo attention helper branches."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.control_plane.todos.todo_summary import active_state_todo_attention_item  # noqa: E402


GOAL = {"id": "active-state-todo-attention-helper-goal"}
CURRENT_RUN = {"classification": "state_refreshed"}


def compact_text(value: Any, *, limit: int) -> str | None:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def first_open_text(summary: dict[str, Any] | None) -> str | None:
    if not isinstance(summary, dict):
        return None
    for item in summary.get("first_open_items") or []:
        if isinstance(item, dict) and item.get("text"):
            return str(item["text"])
    return None


def open_count(summary: dict[str, Any] | None) -> int:
    if not isinstance(summary, dict):
        return 0
    return int(summary.get("open_count") or 0)


def lifecycle_fields(goal: dict[str, Any], current_run: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "lifecycle_phase": "fixture_phase",
        "lifecycle_flags": ["fixture_flag"],
    }


def attention_item(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


def project(fields: dict[str, Any]) -> dict[str, Any] | None:
    return active_state_todo_attention_item(
        GOAL,
        fields,
        CURRENT_RUN,
        public_safe_compact_text=compact_text,
        first_open_todo_text=first_open_text,
        todo_summary_open_count=open_count,
        goal_lifecycle_fields=lifecycle_fields,
        attention_item=attention_item,
    )


def main() -> None:
    user_item = project(
        {
            "active_state_next_action": "fallback user next action",
            "user_todos": {
                "open_count": 1,
                "first_open_items": [{"text": "[P1] Ask the owner for review."}],
            },
            "agent_todos": {
                "open_count": 1,
                "first_open_items": [{"text": "[P1] Continue implementation."}],
            },
        }
    )
    assert user_item is not None, user_item
    assert user_item["status"] == "active_state_user_todo", user_item
    assert user_item["waiting_on"] == "controller", user_item
    assert user_item["recommended_action"] == "[P1] Ask the owner for review.", user_item
    assert user_item["lifecycle_phase"] == "fixture_phase", user_item

    nonblocking_action = {
        "open_count": 1,
        "first_open_items": [
            {
                "text": "[P1] Review the experiment integration PR.",
                "task_class": "user_action",
                "bound_agent": "codex-main-control",
            }
        ],
    }
    nonblocking_with_agent = project(
        {
            "user_todos": nonblocking_action,
            "agent_todos": {
                "open_count": 1,
                "first_open_items": [
                    {
                        "text": "[P1] Continue the next experiment feature.",
                        "task_class": "advancement_task",
                    }
                ],
            },
        }
    )
    assert nonblocking_with_agent is not None, nonblocking_with_agent
    assert nonblocking_with_agent["status"] == "active_state_agent_todo", (
        nonblocking_with_agent
    )

    nonblocking_empty_frontier = project(
        {
            "user_todos": nonblocking_action,
            "state_projection_gap": {
                "recommended_action": "derive the next concrete agent todo",
            },
        }
    )
    assert nonblocking_empty_frontier is not None, nonblocking_empty_frontier
    assert nonblocking_empty_frontier["status"] == "state_projection_gap", (
        nonblocking_empty_frontier
    )
    assert nonblocking_empty_frontier["waiting_on"] == "codex", (
        nonblocking_empty_frontier
    )

    agent_item = project(
        {
            "active_state_next_action": "fallback agent next action",
            "agent_todos": {
                "open_count": 1,
                "first_open_items": [{"text": "[P2] Continue implementation."}],
            },
        }
    )
    assert agent_item is not None, agent_item
    assert agent_item["status"] == "active_state_agent_todo", agent_item
    assert agent_item["waiting_on"] == "codex", agent_item
    assert agent_item["recommended_action"] == "[P2] Continue implementation.", agent_item

    gap_item = project(
        {
            "state_projection_gap": {
                "recommended_action": "expand the Next Action into parseable todos",
            },
        }
    )
    assert gap_item is not None, gap_item
    assert gap_item["status"] == "state_projection_gap", gap_item
    assert gap_item["waiting_on"] == "codex", gap_item
    assert gap_item["recommended_action"] == "expand the Next Action into parseable todos", gap_item

    assert project({}) is None

    print("active-state-todo-attention-helper-smoke ok")


if __name__ == "__main__":
    main()
