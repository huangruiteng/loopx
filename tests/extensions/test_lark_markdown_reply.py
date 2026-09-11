import json

import pytest

from loopx.extensions.lark.outbound import (
    lark_markdown_post_content, lark_markdown_preview_matches,
    lark_markdown_readback_matches, normalize_lark_outbound_text,
)
from loopx.extensions.lark.inbox_reply import reply_lark_event_inbox
from test_lark_inbox_reactions import ReplyRunner, _fixture

TEXT = "进展\n\n- **结果**\n  - 证据\n\n```python\nif ok:\n    done()\n```"


def test_post_preview_preserves_structure_without_fetching_or_rewriting():
    text = normalize_lark_outbound_text(TEXT, preserve_format=True)
    assert text == TEXT
    content = lark_markdown_post_content(text)
    payload = {"api": [{"body": {"msg_type": "post", "content": content}}]}
    assert lark_markdown_preview_matches(text=text, payload=payload)
    payload["api"][0]["body"]["msg_type"] = "text"
    assert not lark_markdown_preview_matches(text=text, payload=payload)


@pytest.mark.parametrize("change", ["type", "indent", "missing", "mention", "extra_node"])
def test_readback_rejects_delivery_or_content_changes(change):
    content = json.loads(lark_markdown_post_content(TEXT))
    message = {"msg_type": "post", "body": {"content": content}}
    assert lark_markdown_readback_matches(text=TEXT, message=message)
    if change == "type":
        message["msg_type"] = "text"
    elif change == "indent":
        content["zh_cn"]["content"][0][0]["text"] = TEXT.replace("    done", "done")
    elif change == "missing":
        content["zh_cn"]["content"][0][0]["text"] = "进展"
    elif change == "mention":
        message["mentions"] = [{"id": "unexpected"}]
    else:
        content["zh_cn"]["content"][0].append({"tag": "text", "text": "extra"})
    assert not lark_markdown_readback_matches(text=TEXT, message=message)


@pytest.mark.parametrize("placement", ["source_context", "source_thread"])
def test_reply_transport_verifies_post_and_reuses_exact_idempotent_request(tmp_path, placement):
    config, _, project = _fixture(tmp_path, lifecycle=False)
    value = json.loads(config.read_text())
    value["reply"]["placement_policy"] = placement
    config.write_text(json.dumps(value))
    fallback = ReplyRunner()
    calls = []
    def runner(args):
        calls.append(args)
        if "+messages-send" in args or "+messages-reply" in args:
            assert "--markdown" not in args and "--text" not in args
            assert args[args.index("--msg-type") + 1] == "post"
            content = args[args.index("--content") + 1]
            assert json.loads(content)["zh_cn"]["content"][0][0]["text"] == TEXT
            result = {"api": [{"body": {"msg_type": "post", "content": content}}]} if "--dry-run" in args else {"message_id": "om_reply_fixture"}
            return {"returncode": 0, "stdout": json.dumps(result)}
        if "+messages-mget" in args:
            return {"returncode": 0, "stdout": json.dumps({"items": [{"message_id": "om_reply_fixture", "msg_type": "post", "content": TEXT}]})}
        return fallback(args)
    receipts = [reply_lark_event_inbox(project=project, config_path=config,
        message_id="om_reaction_fixture", text=TEXT, content_format="markdown",
        execute=True, runner=runner) for _ in range(2)]
    assert all(result["reply_verified"] for result in receipts)
    assert receipts[0]["idempotency_key"] == receipts[1]["idempotency_key"]
    sent = [args for args in calls if "--content" in args and "--dry-run" not in args]
    assert sent[0] == sent[1]
    assert ("--reply-in-thread" in sent[0]) == (placement == "source_thread")


def test_large_post_falls_back_before_send_without_truncating(tmp_path):
    config, _, project = _fixture(tmp_path, lifecycle=False)
    text = "- 完整内容\n" * 2000
    fallback = ReplyRunner(readback_text=text.strip())
    calls = []
    def runner(args):
        calls.append(args)
        if "--content" in args:
            assert "--dry-run" in args  # oversized post must never be sent
            return {"returncode": 0, "stdout": json.dumps({"api": [{"body": {
                "msg_type": "post", "content": args[args.index("--content") + 1],
            }}]})}
        return fallback(args)
    result = reply_lark_event_inbox(project=project, config_path=config,
        message_id="om_reaction_fixture", text=text, content_format="markdown",
        execute=True, runner=runner)
    assert result["reply_verified"]
    assert result["content_format"] == "text"
    assert result["format_fallback"] == "post_size_limit"
    sent = [args for args in calls if "--text" in args and "--dry-run" not in args]
    assert len(sent) == 1
    assert sent[0][sent[0].index("--text") + 1] == text.strip()


def test_markdown_request_with_mentions_keeps_verified_text_transport(tmp_path):
    config, _, project = _fixture(tmp_path, lifecycle=False)
    text = '<at open_id="ou_public_reviewer">Reviewer</at> please review'
    runner = ReplyRunner(readback_text="@_user_1 please review", readback_mentions=[{
        "key": "@_user_1", "id": "ou_public_reviewer", "name": "Reviewer",
    }])
    result = reply_lark_event_inbox(project=project, config_path=config,
        message_id="om_reaction_fixture", text=text, content_format="markdown",
        execute=True, runner=runner)
    assert result["reply_verified"]
    assert result["content_format"] == "text"
    assert all("--content" not in args for args in runner.calls)
