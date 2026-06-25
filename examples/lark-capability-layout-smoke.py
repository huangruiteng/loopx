#!/usr/bin/env python3
"""Smoke-test that Lark integrations live under the capability package."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark import kanban, message_card, progress_reporter  # noqa: E402


def main() -> int:
    assert kanban.lark_kanban_schema_payload()["schema_version"] == "loopx_lark_kanban_control_plane_v0"
    assert message_card.build_lark_markdown_reply_card("ok")["elements"][0]["text"]["content"] == "ok"
    assert (
        progress_reporter.build_acceptance_notification(
            todo_id="todo_layout",
            goal_id="goal",
            request_text="ok",
        ).stage
        == "accepted"
    )
    print("lark capability layout smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
