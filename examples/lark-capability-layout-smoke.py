#!/usr/bin/env python3
"""Smoke-test Lark presentation sinks and the capability facade."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.capabilities.lark import kanban as capability_kanban  # noqa: E402
from loopx.capabilities.lark import message_card as capability_message_card  # noqa: E402
from loopx.presentation.sinks.lark import kanban, message_card  # noqa: E402


def main() -> int:
    assert kanban.lark_kanban_schema_payload()["schema_version"] == "loopx_lark_kanban_control_plane_v0"
    assert message_card.build_lark_markdown_reply_card("ok")["elements"][0]["text"]["content"] == "ok"
    assert capability_kanban.lark_kanban_schema_payload == kanban.lark_kanban_schema_payload
    assert capability_message_card.build_lark_markdown_reply_card == message_card.build_lark_markdown_reply_card
    print("lark capability layout smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
