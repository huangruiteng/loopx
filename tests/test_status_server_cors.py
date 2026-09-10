from __future__ import annotations

import http.client
import json
import threading

import pytest

from loopx.status_server import (
    StatusHTTPServer,
    StatusRequestHandler,
    cors_response_headers,
    parse_strict_json_object,
)


def test_cors_response_headers_loopback_origin_is_echoed() -> None:
    headers = cors_response_headers("http://127.0.0.1:8123")

    assert headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:8123"
    assert headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert headers["Vary"] == "Origin"


def test_cors_response_headers_localhost_origin_is_echoed() -> None:
    headers = cors_response_headers("http://localhost:8123")

    assert headers["Access-Control-Allow-Origin"] == "http://localhost:8123"


def test_cors_response_headers_foreign_origin_is_rejected() -> None:
    assert cors_response_headers("https://evil.example") == {}


def test_cors_response_headers_missing_origin_needs_no_cors() -> None:
    assert cors_response_headers(None) == {}


@pytest.mark.parametrize(
    "origin",
    [
        "null",
        "http://127.0.0.1.evil.example",
        "http://localhost.evil.example",
        "http://localhost@evil.example",
        "http://[::1",
    ],
)
def test_cors_response_headers_spoofed_loopback_origins_are_rejected(origin: str) -> None:
    assert cors_response_headers(origin) == {}


def test_cors_response_headers_file_scheme_localhost_is_rejected() -> None:
    # Hostname alone is not enough: only http(s) loopback browser origins may
    # receive ACAO. A file:// localhost Origin must stay ACAO-free.
    assert cors_response_headers("file://localhost") == {}


def _start_server() -> tuple[StatusHTTPServer, threading.Thread]:
    server = StatusHTTPServer(("127.0.0.1", 0), StatusRequestHandler)
    server.verbose = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _get(port: int, *, origin: str | None) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Origin": origin} if origin else {}
    conn.request("GET", "/healthz", headers=headers)
    return conn.getresponse()


def _options(port: int, *, origin: str | None) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Origin": origin} if origin else {}
    conn.request("OPTIONS", "/healthz", headers=headers)
    return conn.getresponse()


def test_healthz_without_origin_omits_acao() -> None:
    server, thread = _start_server()
    try:
        response = _get(server.server_address[1], origin=None)
        body = response.read()
        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") is None
        assert b'"ok": true' in body
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_healthz_with_foreign_origin_omits_acao() -> None:
    server, thread = _start_server()
    try:
        response = _get(server.server_address[1], origin="https://evil.example")
        response.read()
        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_healthz_with_loopback_origin_echoes_acao() -> None:
    server, thread = _start_server()
    try:
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        response = _get(server.server_address[1], origin=origin)
        response.read()
        assert response.status == 200
        assert response.getheader("Access-Control-Allow-Origin") == origin
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_options_preflight_with_foreign_origin_omits_acao() -> None:
    server, thread = _start_server()
    try:
        response = _options(server.server_address[1], origin="https://evil.example")
        response.read()
        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_options_preflight_with_loopback_origin_echoes_acao() -> None:
    server, thread = _start_server()
    try:
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        response = _options(server.server_address[1], origin=origin)
        response.read()
        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") == origin
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e309"])
def test_status_post_rejects_non_finite_json_numbers(number: str) -> None:
    server, thread = _start_server()
    server.reward_dry_run_path = "/reward/dry-run"
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1", server.server_address[1], timeout=5
        )
        connection.request(
            "POST",
            server.reward_dry_run_path,
            body=f'{{"unexpected":{number}}}'.encode(),
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))

        assert response.status == 400
        assert "request body must be strict JSON" in payload["error"]
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_strict_json_accepts_nested_finite_exponents() -> None:
    assert parse_strict_json_object(b'{"values":[1e308,{"small":-1e-308}]}') == {
        "values": [1e308, {"small": -1e-308}]
    }
