from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from loopx.control_plane.testing.doubao_model_behavior_actor import (
    DOUBAO_2_1_PRO_MODEL,
    DOUBAO_CHAT_COMPLETIONS_ENDPOINT,
    DoubaoOnboardingModelBehaviorActor,
)
from loopx.control_plane.testing.onboarding_model_behavior_qualification import (
    ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
    ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION,
    build_onboarding_model_behavior_actor_request,
    normalize_onboarding_model_behavior_actor_result,
    onboarding_entry_semantic_contract,
)


def _packet() -> dict[str, Any]:
    return {
        "schema_version": "loopx_start_goal_guided_v0",
        "goal_id": "fixture-goal",
        "agent_id": "codex-fixture",
        "guided_transaction": {
            "writes_now": False,
            "spends_quota_now": False,
            "ordered_steps": [{"id": "connect_if_needed"}],
        },
        "commands": {
            "goal_start_connect_if_needed": "loopx bootstrap --project $PROJECT",
            "goal_start_refresh_state": "loopx refresh-state --goal-id fixture-goal",
            "goal_start_host_loop_activation": "loopx heartbeat-prompt --thin",
            "goal_start_quota_should_run": "loopx quota should-run",
        },
        "host_loop_activation": {
            "agent_id": "codex-fixture",
            "activation_required_after_todo_write": True,
        },
    }


def test_direct_onboarding_actor_uses_no_tool_provider_boundary() -> None:
    captured: dict[str, Any] = {}
    contract = onboarding_entry_semantic_contract(_packet())
    decision = {
        "schema_version": ONBOARDING_MODEL_BEHAVIOR_DECISION_SCHEMA_VERSION,
        "phase": "entry",
        "next_action": "connect_if_needed",
        "semantic_contract": contract,
        "reason_codes": ["source_aligned"],
    }

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
        return {"choices": [{"message": {"content": json.dumps(decision)}}]}

    actor = DoubaoOnboardingModelBehaviorActor(
        api_key="fixture-key-not-a-secret",
        transport=transport,
        timeout_seconds=18,
    )
    request = build_onboarding_model_behavior_actor_request(
        _packet(),
        qualification_id="onboarding-direct-doubao-001",
        phase="entry",
    )
    result = normalize_onboarding_model_behavior_actor_result(
        actor(request),
        phase="entry",
    )

    assert captured["endpoint"] == DOUBAO_CHAT_COMPLETIONS_ENDPOINT
    assert captured["body"]["model"] == DOUBAO_2_1_PRO_MODEL
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert "tools" not in captured["body"]
    provider_input = json.loads(captured["body"]["messages"][1]["content"])
    assert set(provider_input) == {"schema_version", "phase", "packet"}
    assert "qualification_id" not in provider_input
    assert "sandbox" not in provider_input
    assert result["schema_version"] == ONBOARDING_MODEL_BEHAVIOR_RESULT_SCHEMA_VERSION
    assert result["tool_calls"] == []
    assert "fixture-key" not in json.dumps(result, sort_keys=True)
