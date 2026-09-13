from __future__ import annotations

import stat

import pytest

from loopx.extensions.lark.manager_reply_delivery import (
    load_delivery,
    pending_delivery,
    write_delivery,
)
from test_lark_inbox_reactions import _fixture


def test_manager_delivery_state_is_private_event_bound_and_tamper_evident(
    tmp_path,
):
    config, _, project = _fixture(tmp_path, lifecycle=False)
    event = {
        "event_id": "evt_reply_fixture",
        "message_id": "om_reaction_fixture",
        "sender_id": "ou_owner_fixture",
        "content": "Give me a status update.",
    }
    path, existing = load_delivery(
        project=project, config_path=config, event=event
    )
    assert existing is None
    payload = pending_delivery(
        event=event,
        text="Complete answer.",
        content_format="markdown",
        effect_receipt=None,
        failure_code=None,
    )

    write_delivery(path, payload)

    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    _, loaded = load_delivery(project=project, config_path=config, event=event)
    assert loaded == payload

    tampered = {**payload, "delivery_text": "Changed answer."}
    write_delivery(path, tampered)
    with pytest.raises(ValueError, match="pending delivery content"):
        load_delivery(project=project, config_path=config, event=event)


def test_sent_verified_state_requires_readback_and_idempotency_receipt(tmp_path):
    config, _, project = _fixture(tmp_path, lifecycle=False)
    event = {
        "event_id": "evt_reply_fixture",
        "message_id": "om_reaction_fixture",
        "sender_id": "ou_owner_fixture",
        "content": "Give me a status update.",
    }
    path, _ = load_delivery(project=project, config_path=config, event=event)
    payload = pending_delivery(
        event=event,
        text="Complete answer.",
        content_format="text",
        effect_receipt=None,
        failure_code=None,
    )
    payload["status"] = "sent_verified"
    write_delivery(path, payload)

    with pytest.raises(ValueError, match="verified delivery receipt"):
        load_delivery(project=project, config_path=config, event=event)
