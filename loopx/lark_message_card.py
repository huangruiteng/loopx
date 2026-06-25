from __future__ import annotations

import json
import re
from typing import Any


DEFAULT_MAX_MARKDOWN_CHARS = 3600
DEFAULT_TITLE_MAX_CHARS = 72
DEFAULT_FOOTER_MAX_CHARS = 96
DEFAULT_TRUNCATION_SUFFIX = "\n\n...truncated."
MESSAGE_ID_RE = re.compile(r"\bom_[A-Za-z0-9_]+\b")


def compact_markdown(
    text: object,
    *,
    max_chars: int = DEFAULT_MAX_MARKDOWN_CHARS,
    suffix: str = DEFAULT_TRUNCATION_SUFFIX,
) -> str:
    value = str(text or "").replace("\r", "").replace("\\r\\n", "\n").replace("\\n", "\n").strip()
    if len(value) <= max_chars:
        return value
    if max_chars <= len(suffix):
        return suffix[-max_chars:]
    return value[: max_chars - len(suffix)].rstrip() + suffix


def compact_plain_text(text: object, *, max_chars: int = DEFAULT_TITLE_MAX_CHARS) -> str:
    value = re.sub(r"\s+", " ", str(text or "").strip())
    return compact_markdown(value, max_chars=max_chars, suffix="...")


def build_lark_markdown_reply_card(
    markdown: object,
    *,
    title: str = "LoopX result",
    template: str = "blue",
    footer: str = "LoopX automated reply",
    max_markdown_chars: int = DEFAULT_MAX_MARKDOWN_CHARS,
) -> dict[str, Any]:
    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {
            "template": template,
            "title": {
                "tag": "plain_text",
                "content": compact_plain_text(title, max_chars=DEFAULT_TITLE_MAX_CHARS),
            },
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": compact_markdown(markdown, max_chars=max_markdown_chars),
                },
            },
            {"tag": "hr"},
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": compact_plain_text(footer, max_chars=DEFAULT_FOOTER_MAX_CHARS),
                    }
                ],
            },
        ],
    }


def _find_message_id(value: object, *, parent_message_id: str | None = None) -> str | None:
    if isinstance(value, dict):
        direct = value.get("message_id")
        if isinstance(direct, str) and direct.startswith("om_") and direct != parent_message_id:
            return direct
        for item in value.values():
            found = _find_message_id(item, parent_message_id=parent_message_id)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_message_id(item, parent_message_id=parent_message_id)
            if found:
                return found
    elif isinstance(value, str):
        for match in MESSAGE_ID_RE.finditer(value):
            message_id = match.group(0)
            if message_id != parent_message_id:
                return message_id
    return None


def extract_reply_message_id(output: object, *, parent_message_id: str | None = None) -> str | None:
    text = str(output or "")
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    if parsed is not None:
        found = _find_message_id(parsed, parent_message_id=parent_message_id)
        if found:
            return found
    return _find_message_id(text, parent_message_id=parent_message_id)
