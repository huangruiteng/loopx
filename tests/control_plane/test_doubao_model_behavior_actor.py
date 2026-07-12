from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from loopx.control_plane.testing.doubao_model_behavior_actor import (
    DOUBAO_2_1_PRO_MODEL,
    DOUBAO_CHAT_COMPLETIONS_ENDPOINT,
    DoubaoModelBehaviorActor,
)
from loopx.control_plane.testing.model_behavior_qualification import (
    build_model_behavior_actor_request,
    normalize_model_behavior_actor_result,
)


def _request() -> dict[str, Any]:
    return build_model_behavior_actor_request(
        {"schema_version": "loopx_turn_envelope_v0"},
        qualification_id="case-direct-doubao-001",
        arm="candidate_packet",
    )


def _decision() -> dict[str, Any]:
    return {
        "schema_version": "model_behavior_decision_v0",
        "decision": "execute",
        "selected_todo_id": "todo_fixture001",
        "user_action_required": False,
        "must_attempt_work": True,
        "delivery_allowed": True,
        "quiet_noop_allowed": False,
        "external_write_requested": False,
        "intended_action_kinds": ["inspect", "test", "writeback"],
        "reason_codes": ["bounded_delivery"],
    }


def test_direct_actor_uses_canonical_endpoint_without_tools_or_raw_retention() -> None:
    captured: dict[str, Any] = {}

    def transport(
        *,
        endpoint: str,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        captured.update(
            endpoint=endpoint,
            headers=dict(headers),
            body=json.loads(body),
            timeout_seconds=timeout_seconds,
        )
        return {"choices": [{"message": {"content": json.dumps(_decision())}}]}

    actor = DoubaoModelBehaviorActor(
        api_key="fixture-key-not-a-secret",
        transport=transport,
        timeout_seconds=12,
    )
    result = normalize_model_behavior_actor_result(actor(_request()))

    assert captured["endpoint"] == DOUBAO_CHAT_COMPLETIONS_ENDPOINT
    expected_authorization = "Bearer " + "fixture-key-not-a-secret"
    assert captured["headers"]["Authorization"] == expected_authorization
    assert captured["body"]["model"] == DOUBAO_2_1_PRO_MODEL
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "tools" not in captured["body"]
    assert captured["timeout_seconds"] == 12
    assert result["actor_ref"] == f"ark:{DOUBAO_2_1_PRO_MODEL}"
    assert result["tool_calls"] == []
    assert "fixture-key" not in json.dumps(result, sort_keys=True)


def test_environment_factory_fails_closed_without_injected_key() -> None:
    with pytest.raises(RuntimeError, match="ARK_API_KEY is not injected"):
        DoubaoModelBehaviorActor.from_environment(environ={})

    with pytest.raises(ValueError, match="allowlisted Doubao 2.1"):
        DoubaoModelBehaviorActor.from_environment(
            environ={
                "ARK_API_KEY": "fixture-key-not-a-secret",
                "LOOPX_MODEL_BEHAVIOR_MODEL": "future-model-v9",
            }
        )


@pytest.mark.parametrize(
    "response, message",
    [
        ({}, "exactly one choice"),
        ({"choices": [{"message": {"content": "not-json"}}]}, "not valid JSON"),
        (
            {"choices": [{"message": {"content": "[]"}}]},
            "decision must be an object",
        ),
    ],
)
def test_actor_rejects_malformed_provider_responses(
    response: Mapping[str, Any], message: str
) -> None:
    actor = DoubaoModelBehaviorActor(
        api_key="fixture-key-not-a-secret",
        transport=lambda **_: response,
    )
    with pytest.raises(RuntimeError, match=message):
        actor(_request())


def test_actor_sanitizes_unexpected_transport_errors() -> None:
    def transport(**_: Any) -> Mapping[str, Any]:
        raise OSError("provider error containing private transport detail")

    actor = DoubaoModelBehaviorActor(
        api_key="fixture-key-not-a-secret",
        transport=transport,
    )
    with pytest.raises(RuntimeError) as exc_info:
        actor(_request())

    assert str(exc_info.value) == "Doubao actor provider transport failed"


def test_actor_rejects_noncanonical_request_before_transport() -> None:
    called = False

    def transport(**_: Any) -> Mapping[str, Any]:
        nonlocal called
        called = True
        return {}

    actor = DoubaoModelBehaviorActor(
        api_key="fixture-key-not-a-secret",
        transport=transport,
    )
    request = _request()
    request["sandbox"] = {**request["sandbox"], "tools_enabled": True}

    with pytest.raises(ValueError, match="canonical no-write contract"):
        actor(request)
    assert called is False
