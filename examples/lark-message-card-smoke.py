#!/usr/bin/env python3
"""Smoke-test public-safe Lark/Feishu message card rendering."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.lark_message_card import (  # noqa: E402
    build_lark_markdown_reply_card,
    compact_markdown,
    compact_plain_text,
    extract_reply_message_id,
)


def main() -> int:
    card = build_lark_markdown_reply_card(
        "**Done**\n- Validated card formatting",
        title="LoopX result",
        template="green",
        footer="LoopX automated reply",
    )

    assert card["config"] == {"wide_screen_mode": True, "enable_forward": True}, card
    assert card["header"]["template"] == "green", card
    assert card["header"]["title"] == {"tag": "plain_text", "content": "LoopX result"}, card
    assert card["elements"][0] == {
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**Done**\n- Validated card formatting"},
    }, card
    assert card["elements"][1]["tag"] == "hr", card
    assert card["elements"][2] == {
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": "LoopX automated reply"}],
    }, card
    escaped_newline_content = build_lark_markdown_reply_card("first\\nsecond")["elements"][0]["text"]["content"]
    assert "\\n" not in escaped_newline_content, escaped_newline_content
    assert "first\nsecond" in escaped_newline_content, escaped_newline_content

    assert compact_plain_text("  one\n\n two  ", max_chars=20) == "one two"
    assert len(compact_plain_text("x" * 100, max_chars=12)) <= 12
    truncated = compact_markdown("x" * 100, max_chars=32)
    assert len(truncated) <= 32, truncated
    assert truncated.endswith("...truncated."), truncated

    parent = "om_parent"
    nested = json.dumps({"data": {"message_id": parent, "reply": {"message_id": "om_reply_json"}}})
    assert extract_reply_message_id(nested, parent_message_id=parent) == "om_reply_json"
    assert extract_reply_message_id("sent parent=om_parent reply=om_reply_plain", parent_message_id=parent) == "om_reply_plain"
    assert extract_reply_message_id("message_id=om_parent", parent_message_id=parent) is None

    print("lark message card smoke ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
