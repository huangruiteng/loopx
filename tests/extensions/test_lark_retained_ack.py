"""Received ACK retention is separate from transient processing and source ACK."""

import json

import pytest

from loopx.extensions.lark.event_inbox import load_lark_event_inbox_config
from loopx.extensions.lark.inbox_reactions import (
    complete_lark_event_inbox_reactions,
    lark_inbox_reaction_receipts,
    mark_lark_event_inbox_processing,
    record_lark_inbox_reaction,
)
from tests.extensions.test_lark_inbox_reactions import _fixture, ReactionRunner


def test_retained_ack_survives_processing_completion_and_restart(tmp_path):
    config, inbox, project = _fixture(tmp_path)
    payload = json.loads(config.read_text())
    payload["reply"]["received_reaction_policy"] = "retain"
    config.write_text(json.dumps(payload))
    record_lark_inbox_reaction(
        inbox=inbox,
        message_id="om_reaction_fixture",
        phase="received",
        reaction_id="reaction_Get",
        emoji_type="Get",
    )
    args = dict(
        project=project,
        config_path=config,
        message_id="om_reaction_fixture",
        execute=True,
    )
    processing = ReactionRunner()
    assert mark_lark_event_inbox_processing(**args, runner=processing)["ok"]
    assert not any("delete" in c for c in processing.calls)
    assert set(
        lark_inbox_reaction_receipts(inbox=inbox, message_id=args["message_id"])
    ) == {"received", "processing"}
    # A newly constructed runner simulates service restart; only disk receipts survive.
    completion = ReactionRunner()
    result = complete_lark_event_inbox_reactions(**args, runner=completion)
    assert result["ok"] and result["deleted_count"] == 1
    assert all(
        c[c.index("--reaction-id") + 1] == "reaction_OnIt" for c in completion.calls
    )
    assert set(
        lark_inbox_reaction_receipts(inbox=inbox, message_id=args["message_id"])
    ) == {"received"}
    replay = ReactionRunner()
    assert complete_lark_event_inbox_reactions(**args, runner=replay)["ok"]
    assert replay.calls == []


def test_generic_default_cleans_only_recorded_reaction(tmp_path):
    config, inbox, project = _fixture(tmp_path)
    record_lark_inbox_reaction(
        inbox=inbox,
        message_id="om_reaction_fixture",
        phase="received",
        reaction_id="reaction_Get",
        emoji_type="Get",
    )
    parsed = load_lark_event_inbox_config(project=project, config_path=config)
    assert parsed["reply"]["received_reaction_policy"] == "transient"
    runner = ReactionRunner()
    result = complete_lark_event_inbox_reactions(
        project=project,
        config_path=config,
        message_id="om_reaction_fixture",
        execute=True,
        runner=runner,
    )
    assert result["deleted_count"] == 1
    assert (
        lark_inbox_reaction_receipts(inbox=inbox, message_id="om_reaction_fixture")
        == {}
    )


@pytest.mark.parametrize("value", ["", None, True, [], "typo"])
def test_invalid_retention_does_not_silently_change_behavior(tmp_path, value):
    config, _, project = _fixture(tmp_path)
    payload = json.loads(config.read_text())
    payload["reply"]["received_reaction_policy"] = value
    config.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="received_reaction_policy"):
        load_lark_event_inbox_config(project=project, config_path=config)
