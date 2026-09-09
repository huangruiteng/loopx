from __future__ import annotations

import io
import json
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
