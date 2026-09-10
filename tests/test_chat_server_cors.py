from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

import pytest

from loopx.chat_action_store import ChatActionStore
from loopx.chat_actions import ChatActionService
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
    body: bytes | None = None,
) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Origin": origin} if origin else {}
    connection.request(method, path, body=body, headers=headers)
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


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_chat_post_rejects_non_finite_json_numbers(number: str) -> None:
    server, thread = _start_server()
    try:
        response = _request(
            server.server_address[1],
            method="POST",
            origin=None,
            path="/api/ssh-source/ensure",
            body=f'{{"host_alias":"","local_port":{number}}}'.encode(),
        )
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 400
        assert "request body must be strict JSON" in payload["error"]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_chat_action_context_cannot_persist_or_emit_overflowed_float(
    tmp_path: Path,
) -> None:
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps({"schema_version": "0.1", "goals": [{"id": "goal-one"}]}),
        encoding="utf-8",
    )
    action_store = ChatActionStore(tmp_path / "actions")
    server, thread = _start_server()
    server.action_store = action_store
    server.action_service = ChatActionService(
        store=action_store,
        registry_path=registry_path,
    )
    try:
        response = _request(
            server.server_address[1],
            method="POST",
            origin=None,
            path="/api/actions/preview",
            body=(
                b'{"action_kind":"goal.lifecycle","summary":"Stop goal",'
                b'"normalized_parameters":{"goal_id":"goal-one","operation":"stop"},'
                b'"context":{"nested":{"overflow":1e309}},'
                b'"idempotency_key":"stop-goal-one"}'
            ),
        )
        response_body = response.read()

        assert response.status == 400
        assert b"Infinity" not in response_body
        assert json.loads(response_body)["error_code"] == "invalid_action_preview"
        assert action_store.list() == []
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


def test_workspace_directory_skips_expensive_projection_and_respects_scope(monkeypatch) -> None:
    registry = {"goals": [{"id": "alpha", "display_name": "Alpha"}, {"id": "beta"}]}
    monkeypatch.setattr("loopx.chat_status_api.load_registry", lambda _: registry)
    monkeypatch.setattr("loopx.chat_status_api.collect_status", lambda **_: (_ for _ in ()).throw(AssertionError("directory must not collect status")))
    server, thread = _start_server()
    server.selected_goal_id = "alpha"
    try:
        response = _request(server.server_address[1], method="GET", origin=None, path="/status.json?view=workspace-directory")
        payload = json.loads(response.read())
        assert response.status == 200
        assert [goal["id"] for goal in payload["goals"]] == ["alpha"]
        assert payload["schema_version"] == "loopx_workspace_directory_v1"
        for query in ("goal_id=beta", "goal_id=alpha&goal_id=beta", "goal_id=", "view=unknown", "view=workspace-directory&view=workspace-directory"):
            response = _request(server.server_address[1], method="GET", origin=None, path="/status.json?" + query)
            response.read()
            assert response.status == 400
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_workspace_scoped_status_revision_and_membership_fences(monkeypatch) -> None:
    registry = {"goals": [{"id": "alpha"}, {"id": "beta"}]}
    monkeypatch.setattr("loopx.chat_status_api.load_registry", lambda _: registry)
    calls = []
    def collect(**kwargs):
        calls.append(kwargs["goal_id"])
        return {"ok": True}
    monkeypatch.setattr("loopx.chat_status_api.collect_status", collect)
    server, thread = _start_server()
    try:
        response = _request(server.server_address[1], method="GET", origin=None, path="/status.json?goal_id=alpha")
        payload = json.loads(response.read())
        assert response.status == 200
        assert calls == ["alpha"]
        assert payload["workspace_registry_revision"]
        response = _request(server.server_address[1], method="GET", origin=None, path="/status.json?goal_id=missing")
        response.read()
        assert response.status == 404
        assert calls == ["alpha"]
        def racing_collect(**kwargs):
            registry["goals"].pop()
            return {"ok": True}
        monkeypatch.setattr("loopx.chat_status_api.collect_status", racing_collect)
        response = _request(server.server_address[1], method="GET", origin=None, path="/status.json?goal_id=alpha")
        response.read()
        assert response.status == 409
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
