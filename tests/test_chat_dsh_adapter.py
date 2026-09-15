"""The steward's managed-host transport runs one bounded, read-only segment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from loopx.chat import CHAT_REVIEW_CLOSE_TAG, CHAT_REVIEW_OPEN_TAG
from loopx.chat_agent import CodexChatAgentError
from loopx.chat_dsh import (
    HISTORY_LIMIT,
    MANAGED_HOST_CHAT_FAILED,
    MANAGED_HOST_CHAT_TIMEOUT,
    STEWARD_SEGMENT_ENV,
    DshChatAdapter,
)


class _Runner:
    """Records the segment input and returns a scripted outcome."""

    def __init__(self, outcome: Any) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.outcome


def _envelope(message: str) -> str:
    payload = {
        "message": message,
        "proposals": [],
        "protected_action": None,
        "context_handoff": None,
        "gate": None,
    }
    return (
        "visible answer\n"
        + CHAT_REVIEW_OPEN_TAG
        + json.dumps(payload)
        + CHAT_REVIEW_CLOSE_TAG
    )


def _adapter(runner: _Runner, tmp_path: Path) -> DshChatAdapter:
    return DshChatAdapter(
        objective="You are the LoopX manager.",
        work_dir=tmp_path,
        provider="deepseek-official",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        runner=runner,
    )


def test_a_segment_carries_the_resolved_profile_and_a_read_only_boundary(
    tmp_path: Path,
) -> None:
    runner = _Runner({"final_response": _envelope("answer"), "finish_reason": "stop"})
    events: list[tuple[str, dict[str, Any]]] = []

    response = _adapter(runner, tmp_path).start_turn(
        "status please", lambda kind, payload: events.append((kind, payload))
    )

    call = runner.calls[0]
    assert call["provider"] == "deepseek-official"
    assert call["model"] == "deepseek-v4-flash"
    assert call["reasoning_effort"] == "high"
    # The channel pins its own segments read-only; dsh enforces it.
    assert call["env"] == STEWARD_SEGMENT_ENV
    assert call["session_root"] == tmp_path / ".local" / ".dsh-sessions"
    assert response["message"] == "answer"
    assert [kind for kind, _payload in events] == [
        "turn.started",
        "agent.phase",
        "answer.delta",
        "answer.final",
    ]


def test_the_segment_input_keeps_the_channel_objective_and_turn_contract(
    tmp_path: Path,
) -> None:
    runner = _Runner({"final_response": _envelope("answer")})

    _adapter(runner, tmp_path).start_turn("status please", lambda *_args: None)

    prompt = runner.calls[0]["prompt"]
    assert prompt.startswith("You are the LoopX manager.")
    assert "Operator user message:\nstatus please" in prompt
    assert CHAT_REVIEW_OPEN_TAG in prompt


def test_an_empty_final_message_fails_closed(tmp_path: Path) -> None:
    runner = _Runner({"final_response": "", "finish_reason": "error"})

    with pytest.raises(CodexChatAgentError) as raised:
        _adapter(runner, tmp_path).start_turn("status please", lambda *_args: None)

    assert raised.value.error_code == MANAGED_HOST_CHAT_FAILED


def test_an_unreadable_segment_result_fails_closed(tmp_path: Path) -> None:
    runner = _Runner(["not", "a", "mapping"])

    with pytest.raises(CodexChatAgentError) as raised:
        _adapter(runner, tmp_path).start_turn("status please", lambda *_args: None)

    assert raised.value.error_code == MANAGED_HOST_CHAT_FAILED


def test_a_raising_runner_surfaces_one_typed_failure(tmp_path: Path) -> None:
    def failing(**_kwargs: Any) -> Any:
        raise RuntimeError("provider detail that must not become the error code")

    adapter = DshChatAdapter(
        objective="objective",
        work_dir=tmp_path,
        provider="deepseek-official",
        model="deepseek-v4-flash",
        reasoning_effort="high",
        runner=failing,
    )

    with pytest.raises(CodexChatAgentError) as raised:
        adapter.start_turn("status please", lambda *_args: None)

    assert raised.value.error_code == MANAGED_HOST_CHAT_FAILED
    assert "provider detail" not in raised.value.error_code


def test_a_segment_that_never_returns_times_out(tmp_path: Path) -> None:
    import threading

    release = threading.Event()
    try:
        adapter = DshChatAdapter(
            objective="objective",
            work_dir=tmp_path,
            provider="deepseek-official",
            model="deepseek-v4-flash",
            reasoning_effort="high",
            timeout_sec=0.05,
            runner=lambda **_kwargs: release.wait(5),
        )

        with pytest.raises(CodexChatAgentError) as raised:
            adapter.start_turn("status please", lambda *_args: None)
    finally:
        release.set()

    assert raised.value.error_code == MANAGED_HOST_CHAT_TIMEOUT


def test_visible_history_is_bounded_and_reaches_the_next_segment(
    tmp_path: Path,
) -> None:
    runner = _Runner({"final_response": _envelope("first answer")})
    adapter = _adapter(runner, tmp_path)
    adapter.start_turn("first question", lambda *_args: None)
    runner.outcome = {"final_response": _envelope("second answer")}

    adapter.start_turn("second question", lambda *_args: None)

    assert adapter.history == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "second question"},
        {"role": "assistant", "content": "second answer"},
    ]
    assert len(adapter.history) <= HISTORY_LIMIT
