from __future__ import annotations

import json

from loopx.chat import CHAT_REVIEW_OPEN_TAG, parse_agent_response


def test_unclosed_review_envelope_keeps_visible_answer_and_drops_authority() -> None:
    payload = {
        "message": "正文答复。",
        "proposals": [
            {
                "kind": "todo",
                "text": "must not run",
                "priority": "P0",
            }
        ],
        "protected_action": {
            "operation": "merge",
            "target": "PR #1",
            "summary": "must not run",
        },
        "gate": {"kind": "host_tool_gate", "next_action": "must not run"},
    }

    response = parse_agent_response(
        "正文答复。\n" + CHAT_REVIEW_OPEN_TAG + json.dumps(payload)
    )

    assert response["message"] == "正文答复。"
    assert CHAT_REVIEW_OPEN_TAG not in response["message"]
    assert response["proposals"] == []
    assert response["protected_action"] is None
    assert response["gate"] is None


def test_unclosed_review_envelope_salvages_only_message_when_prefix_is_empty() -> None:
    response = parse_agent_response(
        CHAT_REVIEW_OPEN_TAG
        + json.dumps(
            {
                "message": "可恢复的正文。",
                "proposals": [{"kind": "todo", "text": "must not run"}],
            }
        )
    )

    assert response["message"] == "可恢复的正文。"
    assert response["proposals"] == []
    assert response["protected_action"] is None
    assert response["gate"] is None


def test_truncated_review_envelope_never_leaks_protocol_fragment() -> None:
    response = parse_agent_response(
        '已完成。\n<loopx-review-json>{"message":"已完成。","gate":{"kind":"host'
    )

    assert response["message"] == "已完成。"
    assert "review-json" not in response["message"]
    assert response["proposals"] == []
    assert response["protected_action"] is None
    assert response["gate"] is None
