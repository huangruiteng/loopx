from __future__ import annotations

import io
import json
import queue
from pathlib import Path

import loopx.chat_agent as chat_agent
import pytest


class _FakeAppServerProcess:
    def __init__(self) -> None:
        responses = [
            {"id": 1, "result": {"serverInfo": {"name": "fake-codex"}}},
            {"id": 2, "result": {"thread": {"id": "thread-loopx-chat"}}},
        ]
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(
            "".join(json.dumps(response) + "\n" for response in responses)
        )
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return 0

    def kill(self) -> None:
        self.returncode = -1


def test_codex_chat_app_server_stdio_uses_utf8(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    launch_options: dict[str, object] = {}

    def fake_popen(command: list[str], **kwargs: object) -> _FakeAppServerProcess:
        assert command == ["codex", "app-server", "--listen", "stdio://"]
        launch_options.update(kwargs)
        return _FakeAppServerProcess()

    monkeypatch.setattr(chat_agent.shutil, "which", lambda _binary: "codex")
    monkeypatch.setattr(chat_agent.subprocess, "Popen", fake_popen)

    session = chat_agent.CodexChatAgentSession.start(
        codex_bin="codex",
        work_dir=tmp_path,
        goal_id="loopx-chat-smoke",
        objective="Keep multilingual chat transport stable.",
    )
    try:
        assert launch_options["encoding"] == "utf-8"
    finally:
        session.close()


@pytest.mark.parametrize(
    ("item", "expected_activity"),
    [
        ({"type": "userMessage"}, "Agent 已收到消息"),
        ({"type": "agentMessage"}, "Agent 正在生成回答"),
        ({"type": "commandExecution"}, "Agent 正在执行命令"),
        ({"type": "reasoning"}, "Agent 正在思考"),
        ({"type": "mcpToolCall"}, "Agent 正在调用工具"),
        ({"type": "futureItem", "text": "private-fixture-content"}, "Agent 正在处理"),
        ({}, "Agent 正在处理"),
    ],
)
def test_turn_activity_does_not_invent_goal_reads_or_successful_checks(
    monkeypatch, tmp_path, item, expected_activity,
):
    session = chat_agent.CodexChatAgentSession(
        process=_FakeAppServerProcess(), messages=queue.Queue(),
        thread_id="thread-fixture", work_dir=tmp_path,
    )
    upstream = iter([
        {"method": "turn/started", "params": {"turn": {"id": "turn-fixture"}}},
        {"method": "item/started", "params": {"item": item}},
        # Completion can mean a failed command or receipt of a user message;
        # neither is evidence that a Goal check passed.
        {"method": "item/completed", "params": {"item": {**item, "status": "failed"}}},
        {"method": "item/agentMessage/delta", "params": {"delta": "Ready."}},
        {"method": "turn/completed", "params": {"turn": {"status": "completed"}}},
    ])
    monkeypatch.setattr(session, "_request", lambda *a, **kw: {"turn": {"id": "turn-fixture"}})
    monkeypatch.setattr(session, "_next_event", lambda **kw: next(upstream))
    events = []
    session.send("Reply briefly.", on_event=lambda kind, payload: events.append((kind, payload)))
    phases = [p for kind, p in events if kind == "agent.phase"]
    assert phases[1]["label"] == expected_activity
    assert phases[0]["label"] == "Agent 已开始处理"
    assert phases[2]["label"] == "Agent 返回了处理状态"
    assert not any("检查" in p["label"] or "Goal" in p["label"] for p in phases)
    assert "private-fixture-content" not in json.dumps(phases)
    assert any(kind == "answer.delta" and p["text"] == "Ready." for kind, p in events)


def test_codex_chat_pins_explicit_home_in_child_environment(monkeypatch, tmp_path):
    options = {}

    def popen(command, **kwargs):
        options.update(kwargs)
        return _FakeAppServerProcess()

    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "ambient"))
    monkeypatch.setattr(chat_agent.shutil, "which", lambda _: "codex")
    monkeypatch.setattr(chat_agent.subprocess, "Popen", popen)
    session = chat_agent.CodexChatAgentSession.start(
        codex_bin="codex", work_dir=tmp_path, goal_id="fixture", objective="fixture",
        codex_home=tmp_path / "bound",
    )
    try:
        assert options["env"]["CODEX_HOME"] == str((tmp_path / "bound").resolve())
        assert chat_agent.os.environ["CODEX_HOME"] == str(tmp_path / "ambient")
    finally:
        session.close()


@pytest.mark.parametrize('resume_thread_id', [None, 'thread-loopx-chat'])
def test_explicit_manager_model_and_effort_reach_start_resume_and_turn(monkeypatch, tmp_path, resume_thread_id):
    process = _FakeAppServerProcess()
    monkeypatch.setattr(chat_agent.shutil, 'which', lambda _: 'codex')
    monkeypatch.setattr(chat_agent.subprocess, 'Popen', lambda *a, **k: process)
    session = chat_agent.CodexChatAgentSession.start(
        codex_bin='codex', work_dir=tmp_path, goal_id='loopx-manager', objective='global',
        model='gpt-6-astra', reasoning_effort='medium', resume_thread_id=resume_thread_id,
    )
    try:
        requests = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
        start = next(r for r in requests if r['method'] in {'thread/start','thread/resume'})
        assert start['params']['model'] == 'gpt-6-astra'
        assert start['params']['config']['model_reasoning_effort'] == 'medium'
        turns = []
        def request(method, params, **kwargs):
            turns.append((method, params))
            return {'turn': {'id': 'fixture-turn'}}
        monkeypatch.setattr(session, '_request', request)
        monkeypatch.setattr(session, '_next_event', lambda **kwargs: {'method':'turn/completed','params':{'turn':{'status':'completed'}}})
        session.send('Which Goals?')
        assert turns[0][0] == 'turn/start'
        assert turns[0][1]['model'] == 'gpt-6-astra'
        assert turns[0][1]['effort'] == 'medium'
    finally:
        session.close()


@pytest.mark.parametrize("terminal_method", ["error", "turn/completed"])
@pytest.mark.parametrize("info,expected", [
    ("cyberPolicy", "cyber_policy"),
    ("misalignmentPolicyViolation", "misalignment_policy_violation"),
    ("usageLimitExceeded", "usage_limit_exceeded"),
    ("rateLimitExceeded", "rate_limit_exceeded"),
    ("contextWindowExceeded", "context_window_exceeded"),
    ("unauthorized", "unauthorized"),
    ("futureVariant", "host_gate"),
    ({"unknown": "cyberPolicy"}, "host_gate"),
    (None, "host_gate"),
])
def test_typed_terminal_errors_preserve_category_without_promoting_partial_answer(
    monkeypatch, tmp_path, terminal_method, info, expected,
):
    session = chat_agent.CodexChatAgentSession(
        process=_FakeAppServerProcess(), messages=queue.Queue(),
        thread_id="thread-fixture", work_dir=tmp_path,
    )
    error = {"codexErrorInfo": info, "message": "private-fixture cyberPolicy",
             "additionalDetails": "private-fixture"}
    params = {"threadId": "thread-fixture", "turnId": "turn-fixture"}
    if terminal_method == "error":
        params.update(error=error, willRetry=False)
    else:
        params["turn"] = {"id": "turn-fixture", "status": "failed", "error": error}
    upstream = iter([
        {"method": "item/agentMessage/delta", "params": {"delta": "Partial answer."}},
        {"method": terminal_method, "params": params},
    ])
    monkeypatch.setattr(session, "_request", lambda *a, **kw: {"turn": {"id": "turn-fixture"}})
    monkeypatch.setattr(session, "_next_event", lambda **kw: next(upstream))
    events = []
    with pytest.raises(chat_agent.CodexChatAgentError) as caught:
        session.send("Report progress.", on_event=lambda k, p: events.append((k, p)))
    assert caught.value.error_code == expected
    assert "private-fixture" not in str(caught.value) + json.dumps(caught.value.gate)
    assert not any(k == "answer.final" for k, _ in events)
    if expected in {"cyber_policy", "misalignment_policy_violation"}:
        assert caught.value.gate["kind"] == "policy_gate"
        assert "不会自动重放" in caught.value.gate["next_action"]


def test_retry_and_unrelated_policy_events_do_not_terminate_current_turn(monkeypatch, tmp_path):
    session = chat_agent.CodexChatAgentSession(
        process=_FakeAppServerProcess(), messages=queue.Queue(),
        thread_id="thread-fixture", work_dir=tmp_path,
    )
    upstream = iter([
        {"method": "error", "params": {"threadId": "other-thread", "turnId": "turn-fixture", "error": {"codexErrorInfo": "cyberPolicy"}, "willRetry": False}},
        {"method": "error", "params": {"threadId": "thread-fixture", "turnId": "other-turn", "error": {"codexErrorInfo": "cyberPolicy"}, "willRetry": False}},
        {"method": "error", "params": {"threadId": "thread-fixture", "turnId": "turn-fixture", "error": {"codexErrorInfo": "rateLimitExceeded"}, "willRetry": True}},
        {"method": "item/agentMessage/delta", "params": {"delta": "Recovered."}},
        {"method": "turn/completed", "params": {"turn": {"id": "turn-fixture", "status": "completed"}}},
    ])
    monkeypatch.setattr(session, "_request", lambda *a, **kw: {"turn": {"id": "turn-fixture"}})
    monkeypatch.setattr(session, "_next_event", lambda **kw: next(upstream))
    events = []
    result = session.send("Report progress.", on_event=lambda k, p: events.append((k, p)))
    assert result["message"] == "Recovered."
    assert any(k == "agent.phase" and p["label"] == "Codex 正在重试" for k, p in events)
    assert sum(k == "answer.final" for k, p in events) == 1
