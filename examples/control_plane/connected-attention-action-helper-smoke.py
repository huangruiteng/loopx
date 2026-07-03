#!/usr/bin/env python3
"""Smoke-test connected-without-run attention action sync helper."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.projections.todo_summary import sync_connected_attention_action_from_todos  # noqa: E402


AGENT_ACTION = "[P2] Run the first read-only project map."


def first_open_text(summary: dict[str, Any] | None) -> str | None:
    if not isinstance(summary, dict):
        return None
    for item in summary.get("first_open_items") or []:
        if isinstance(item, dict) and item.get("text"):
            return str(item["text"])
    return None


def sync(item: dict[str, Any]) -> None:
    sync_connected_attention_action_from_todos(
        item,
        first_open_todo_text=first_open_text,
    )


def main() -> None:
    item = {
        "status": "connected_without_run",
        "recommended_action": "fallback action",
        "agent_todos": {
            "first_open_items": [{"text": AGENT_ACTION}],
        },
        "project_asset": {
            "next_action": "fallback action",
        },
    }
    sync(item)
    assert item["recommended_action"] == AGENT_ACTION, item
    assert item["project_asset"]["next_action"] == AGENT_ACTION, item

    no_agent_action = {
        "status": "connected_without_run",
        "recommended_action": "fallback action",
        "agent_todos": {"first_open_items": []},
        "project_asset": {"next_action": "fallback action"},
    }
    sync(no_agent_action)
    assert no_agent_action["recommended_action"] == "fallback action", no_agent_action
    assert no_agent_action["project_asset"]["next_action"] == "fallback action", no_agent_action

    other_status = {
        "status": "active_state_agent_todo",
        "recommended_action": "keep me",
        "agent_todos": {"first_open_items": [{"text": AGENT_ACTION}]},
        "project_asset": {"next_action": "keep me"},
    }
    sync(other_status)
    assert other_status["recommended_action"] == "keep me", other_status
    assert other_status["project_asset"]["next_action"] == "keep me", other_status

    no_project_asset = {
        "status": "connected_without_run",
        "recommended_action": "fallback action",
        "agent_todos": {"first_open_items": [{"text": AGENT_ACTION}]},
    }
    sync(no_project_asset)
    assert no_project_asset["recommended_action"] == AGENT_ACTION, no_project_asset

    print("connected-attention-action-helper-smoke ok")


if __name__ == "__main__":
    main()
