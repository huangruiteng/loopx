from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

from loopx.chat_server import ChatHTTPServer, ChatRequestHandler
from loopx.extensions.lark.cli_resolution import LarkCliResolution


def _start_server() -> tuple[ChatHTTPServer, threading.Thread]:
    server = ChatHTTPServer(("127.0.0.1", 0), ChatRequestHandler)
    server.verbose = False
    server.selected_goal_id = None
    server.registry_path = Path("/tmp/loopx-test-registry.json")
    server.runtime_root_override = None
    server.scan_roots = []
    server.limit = 20
    server.runtime_controller = _RuntimeController()
    server.lark_cli_resolution = LarkCliResolution(
        command=None,
        available=False,
        source="missing",
        version=None,
        error_code="lark_cli_not_installed",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def test_completed_todos_are_scoped_paginated_and_redacted(monkeypatch) -> None:
    def read_todos(**kwargs):
        assert kwargs["goal_id"] == "test-goal"
        assert kwargs["status"] == "done"
        assert kwargs["role"] == "agent"
        assert kwargs["agent_id"] == "worker"
        return {
            "project": "/private/project",
            "state_file": "/private/project/state.md",
            "todos": [
                {"todo_id": f"todo_{index}", "text": "Read /private/project/state.md", "done": True,
                 "status": "done", "task_class": "advancement_task", "archive_state": "active",
                 "claimed_by": "worker", "evidence": "private evidence"}
                for index in range(3)
            ] + [
                {"todo_id": "todo_monitor", "done": True, "task_class": "continuous_monitor"},
                {"text": "no identity", "done": True, "task_class": "advancement_task", "archive_state": "active"},
                {"todo_id": "todo_archive", "done": True, "task_class": "advancement_task", "archive_state": "archive"},
                {"todo_id": "todo_open", "done": False, "task_class": "advancement_task"},
            ],
        }

    monkeypatch.setattr("loopx.chat_completed_todos_api.list_goal_todos", read_todos)
    server, thread = _start_server()
    try:
        response = _request(server.server_address[1], method="GET", origin=None,
                            path="/api/chat/todos/completed?goal_id=test-goal&agent_id=worker&limit=2")
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["total"] == 3
        assert payload["next_offset"] == 2
        assert [item["todo_id"] for item in payload["items"]] == ["todo_2", "todo_1"]
        assert "/private/project" not in json.dumps(payload)
        assert "evidence" not in payload["items"][0]
        response = _request(server.server_address[1], method="GET", origin=None,
                            path="/api/chat/todos/completed?goal_id=test-goal&agent_id=worker&offset=2&limit=2")
        payload = json.loads(response.read())
        assert [item["todo_id"] for item in payload["items"]] == ["todo_0"]
        assert payload["next_offset"] is None
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_completed_todos_report_unknown_goal_as_not_found(monkeypatch) -> None:
    def unknown_goal(**kwargs):
        raise ValueError("unknown goal")

    monkeypatch.setattr("loopx.chat_completed_todos_api.list_goal_todos", unknown_goal)
    server, thread = _start_server()
    try:
        response = _request(server.server_address[1], method="GET", origin=None,
                            path="/api/chat/todos/completed?goal_id=missing")
        response.read()
        assert response.status == 404
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_completed_todos_reject_invalid_queries_before_reading(monkeypatch) -> None:
    def unexpected_read(**kwargs):
        raise AssertionError("must not read task state")

    monkeypatch.setattr("loopx.chat_completed_todos_api.list_goal_todos", unexpected_read)
    server, thread = _start_server()
    try:
        for query in ("", "goal_id=", "goal_id=test&limit=0", "goal_id=test&offset=-1",
                      "goal_id=test&limit=101", "goal_id=test&limit=no", "goal_id=test&state_file=secret",
                      "goal_id=test&goal_id=other"):
            response = _request(server.server_address[1], method="GET", origin=None,
                                path=f"/api/chat/todos/completed?{query}")
            response.read()
            assert response.status == 400
        server.selected_goal_id = "allowed"
        response = _request(server.server_address[1], method="GET", origin=None,
                            path="/api/chat/todos/completed?goal_id=other")
        response.read()
        assert response.status == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


class _RuntimeController:
    def capabilities(self) -> list[dict[str, object]]:
        return []

    def close(self) -> None:
        return None


def _request(
    port: int,
    *,
    method: str,
    origin: str | None,
    path: str = "/api/chat/capabilities",
) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Origin": origin} if origin else {}
    connection.request(method, path, headers=headers)
    return connection.getresponse()


def test_chat_json_echoes_loopback_cors_origin() -> None:
    server, thread = _start_server()
    try:
        origin = "http://127.0.0.1:49152"
        response = _request(
            server.server_address[1],
            method="GET",
            origin=origin,
        )
        response.read()

        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") == origin
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_capabilities_expose_public_runtime_identity() -> None:
    server, thread = _start_server()
    try:
        response = _request(
            server.server_address[1],
            method="GET",
            origin=None,
        )
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert payload["runtime_identity"]["schema_version"] == (
            "loopx_runtime_identity_v1"
        )
        assert set(payload["runtime_identity"]) == {
            "schema_version",
            "package_version",
            "release_id",
            "source_revision",
        }
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_json_rejects_foreign_cors_origin() -> None:
    server, thread = _start_server()
    try:
        response = _request(
            server.server_address[1],
            method="GET",
            origin="https://evil.example",
        )
        response.read()

        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_options_exposes_loopback_preflight_only() -> None:
    server, thread = _start_server()
    try:
        origin = "http://127.0.0.1:49152"
        response = _request(
            server.server_address[1],
            method="OPTIONS",
            origin=origin,
        )
        response.read()

        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") == origin
        assert response.getheader("Access-Control-Allow-Methods") == (
            "GET, POST, DELETE, OPTIONS"
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_status_forwards_valid_goal_activation_scope(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_collect_status(**kwargs):
        calls.append(kwargs)
        return {"ok": True, "scope": kwargs.get("activation_state_filter")}

    monkeypatch.setattr("loopx.chat_status_api.collect_status", fake_collect_status)
    server, thread = _start_server()
    server.goal_subagent_configuration_enabled = True
    try:
        response = _request(
            server.server_address[1],
            method="GET",
            origin=None,
            path="/status.json?goal_activation=active",
        )
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert payload == {"ok": True, "scope": "active"}
        assert calls[0]["activation_state_filter"] == "active"
        assert calls[0]["include_goal_subagent_configuration"] is True
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_status_rejects_invalid_goal_activation_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "loopx.chat_status_api.collect_status",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("must fail before collection")),
    )
    server, thread = _start_server()
    try:
        response = _request(
            server.server_address[1],
            method="GET",
            origin=None,
            path="/status.json?goal_activation=active&goal_activation=stopped",
        )
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 400
        assert payload["error_code"] == "invalid_goal_activation"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
