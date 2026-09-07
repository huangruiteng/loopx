from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import loopx.chat_server as chat
from loopx.extensions.lark.cli_resolution import LarkCliResolution
from loopx.extensions.lark.goal_topic_runtime import LarkGoalTopicRuntimeService


def test_real_chat_entrypoint_serves_while_binding_discovery_is_blocked(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    servers: list[chat.ChatHTTPServer] = []
    home = tmp_path / "home"
    registry = home / ".loopx" / "registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"goals": []}))
    assets = tmp_path / "web"
    assets.mkdir()
    (assets / "index.html").write_text("<html>workspace fixture</html>")

    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.chdir(tmp_path)

    class Server(chat.ChatHTTPServer):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            servers.append(self)

    def blocked_snapshot(**_kwargs: Any) -> dict[str, Any]:
        entered.set()
        assert release.wait(10)
        return {}

    monkeypatch.setattr(chat, "ChatHTTPServer", Server)
    monkeypatch.setattr(
        chat, "build_lark_goal_topic_runtime_snapshot", blocked_snapshot
    )
    monkeypatch.setattr(
        chat,
        "resolve_lark_cli_for_runtime",
        lambda **_kwargs: LarkCliResolution(
            None, False, "missing", None, "lark_cli_not_installed"
        ),
    )
    worker = threading.Thread(
        target=chat.serve_chat,
        kwargs={
            "runtime_root_override": tmp_path / "runtime",
            "port": 0,
            "assets_dir": assets,
            "codex_bin": "nonexistent-loopx-test-codex",
            "claude_bin": "nonexistent-loopx-test-claude",
        },
        daemon=True,
    )
    worker.start()
    try:
        assert entered.wait(5)
        assert servers[0].action_service.registry_path == registry.resolve()
        assert servers[0].action_service.workspace_roots == (tmp_path.resolve(),)
        base = f"http://127.0.0.1:{servers[0].server_port}"
        for route in ("/healthz", "/api/chat/capabilities"):
            with urlopen(base + route, timeout=2) as response:
                assert json.load(response)["ok"] is True
        with urlopen(base + chat.DEFAULT_CHAT_PATH, timeout=2) as response:
            assert b"workspace fixture" in response.read()
        servers[0].shutdown()
        worker.join(2)
        assert not worker.is_alive(), "shutdown must not wait for project access"
    finally:
        release.set()
        if servers and worker.is_alive():
            servers[0].shutdown()
        worker.join(5)


def test_late_discovery_cannot_resume_queues_or_start_consumers_after_close(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    applied: list[object] = []

    def snapshot() -> dict[str, Any]:
        entered.set()
        assert release.wait(5)
        return {}

    service = LarkGoalTopicRuntimeService(
        snapshot_provider=snapshot,
        runtime_root=tmp_path,
        runtime_controller=object(),
        profile_poller=lambda *args: applied.append(args),
    )
    monkeypatch.setattr(service, "_resume_session_queues", applied.append)
    service.start()
    original = service._startup_thread
    service.start()
    assert service._startup_thread is original
    try:
        assert entered.wait(2)
        service.close()
    finally:
        release.set()
        assert original is not None
        original.join(2)
    service.refresh()
    service.start()
    assert not original.is_alive()
    assert applied == []
    assert service.active_profiles() == []


def test_initial_discovery_failure_retries_without_an_app_restart(
    tmp_path: Path,
) -> None:
    calls = []

    def snapshot() -> dict[str, Any]:
        calls.append(None)
        if len(calls) == 1:
            raise OSError("fixture unavailable")
        return {}

    service = LarkGoalTopicRuntimeService(
        snapshot_provider=snapshot,
        runtime_root=tmp_path,
        runtime_controller=object(),
    )
    try:
        service.start()
        assert service._startup_thread is not None
        service._startup_thread.join(7)
        assert not service._startup_thread.is_alive()
        assert len(calls) == 2
        assert service.active_profiles() == []
    finally:
        service.close()


def test_close_does_not_wait_for_real_queue_file_read(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from loopx.chat_runtime import ChatRuntimeController
    from loopx.chat_store import ChatSessionStore

    store = ChatSessionStore(tmp_path)
    session = store.create_session(
        goal_id="fixture",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture",
    )
    session_id = session["session_id"]
    turn, _ = store.create_queued_turn(
        session_id, client_turn_id="queued", message="synthetic fixture"
    )
    target = store._turn_path(session_id, turn["turn_id"])
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    original_read = Path.read_text

    def slow_read(path: Path, *args: Any, **kwargs: Any) -> str:
        if path == target:
            entered.set()
            assert release.wait(5)
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", slow_read)
    controller = ChatRuntimeController(store=store, codex_bin="unavailable-fixture")
    effects: list[Any] = []
    monkeypatch.setattr(
        controller, "resume_session_queue", lambda **kwargs: effects.append(kwargs)
    )
    snapshot = {
        "target_payload": {
            "targets": {
                "bot": {
                    "name": "bot",
                    "provider": "lark",
                    "enabled": True,
                    "identity": {"sender_profile": "fixture"},
                }
            }
        },
        "binding_payloads": {
            "fixture": {
                "bindings": {
                    "fixture": {
                        "goal_id": "fixture",
                        "provider": "lark",
                        "enabled": True,
                        "target_ref": "bot",
                        "session_id": session_id,
                        "routing": {"ingress_mode": "session_queue"},
                    }
                }
            }
        },
        "goal_contexts": {"fixture": {"work_dir": str(tmp_path)}},
    }
    service = LarkGoalTopicRuntimeService(
        snapshot_provider=lambda: snapshot,
        runtime_root=tmp_path,
        runtime_controller=controller,
        profile_poller=lambda *args: effects.append(args),
    )
    service.start()
    closer = threading.Thread(
        target=lambda: (service.close(), closed.set()), daemon=True
    )
    try:
        assert entered.wait(2), "the real queued-turn file must be read"
        closer.start()
        assert closed.wait(1), "close must return while queue I/O remains blocked"
    finally:
        release.set()
        closer.join(2)
        assert service._startup_thread is not None
        service._startup_thread.join(2)
        controller.close()
    assert effects == []
    assert service.active_profiles() == []


def test_queue_worker_admission_is_io_free_and_close_fences_late_session_read(
    tmp_path: Path, monkeypatch: Any
) -> None:
    from loopx.chat_runtime import ChatRuntimeController
    from loopx.chat_store import ChatSessionStore

    store = ChatSessionStore(tmp_path)
    session = store.create_session(
        goal_id="fixture",
        agent_id="codex",
        adapter_kind="codex",
        upstream_thread_id="fixture",
    )
    controller = ChatRuntimeController(store=store, codex_bin="unavailable-fixture")
    entered, release, admitted = threading.Event(), threading.Event(), threading.Event()
    effects: list[Any] = []
    original_load = store.load_session

    def slow_load(session_id: str) -> Any:
        entered.set()
        assert release.wait(5)
        return original_load(session_id)

    monkeypatch.setattr(store, "load_session", slow_load)
    monkeypatch.setattr(
        controller, "_ensure_adapter", lambda *args, **kwargs: effects.append(args)
    )

    def admit() -> None:
        controller.resume_session_queue(
            session_id=session["session_id"], work_dir=tmp_path, objective="fixture"
        )
        admitted.set()

    admission = threading.Thread(target=admit, daemon=True)
    admission.start()
    try:
        assert entered.wait(2)
        assert admitted.wait(1), "worker admission must not wait for session files"
        workers = list(controller.session_queue_threads.values())
        controller.close()
    finally:
        release.set()
        admission.join(2)
        for worker in list(controller.session_queue_threads.values()):
            worker.join(2)
    for worker in workers:
        worker.join(2)
    assert effects == []
    assert not controller.session_queue_workers
