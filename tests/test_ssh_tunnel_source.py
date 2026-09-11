from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from loopx.chat_ssh_source_api import SshSourceRequestMixin
from loopx.control_plane.status.ssh_tunnel import (
    _control_socket_path,
    ensure_ssh_source,
    pause_ssh_source,
)


def test_control_socket_path_leaves_space_for_openssh_temporary_suffix() -> None:
    control_socket = _control_socket_path("ark-devbox", 8877)

    assert len(str(control_socket).encode()) <= 72
    if control_socket.parent.exists():
        assert control_socket.parent.stat().st_mode & 0o777 == 0o700


def test_ensure_ssh_source_opens_tunnel_and_returns_status_url() -> None:
    calls: list[list[str]] = []
    probe_count = 0

    def fake_loopback(port: int, **kwargs: object) -> bool:
        nonlocal probe_count
        probe_count += 1
        return probe_count >= 2

    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._loopback_status_ok", fake_loopback
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._remote_status_ok", return_value=True
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._managed_tunnel_active",
        return_value=False,
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._control_socket_path",
        return_value=Path("/tmp/loopx-test-ssh-source.sock"),
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel.subprocess.run",
        side_effect=lambda args, **kwargs: calls.append(list(args)),
    ):
        result = ensure_ssh_source("ark-devbox", 8877, wait_seconds=0.01)

    assert result == {
        "ok": True,
        "status_url": "http://127.0.0.1:8877/status.json",
        "tunnel_required": True,
        "managed_by_loopx": True,
        "remote_started": False,
    }
    tunnel_call = calls[0]
    assert tunnel_call[0] == "ssh"
    assert "-M" in tunnel_call
    assert tunnel_call[tunnel_call.index("-S") + 1] == "/tmp/loopx-test-ssh-source.sock"
    assert "-L" in tunnel_call
    assert "8877:127.0.0.1:8766" in tunnel_call
    assert "ark-devbox" in tunnel_call
    # The alias and port are passed as separate argv entries, never through a shell.
    assert "; " not in " ".join(tunnel_call)


def test_ensure_ssh_source_starts_remote_status_when_missing() -> None:
    probe_count = 0

    def fake_loopback(port: int, **kwargs: object) -> bool:
        nonlocal probe_count
        probe_count += 1
        return probe_count >= 4

    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._loopback_status_ok", fake_loopback
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._remote_status_ok", return_value=False
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._start_remote_status", return_value=None
    ) as start_remote, mock.patch(
        "loopx.control_plane.status.ssh_tunnel._managed_tunnel_active",
        return_value=False,
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._start_managed_tunnel",
        return_value=None,
    ):
        result = ensure_ssh_source("ark-devbox", 8877, wait_seconds=0.01)

    start_remote.assert_called_once_with("ark-devbox")
    assert result["remote_started"] is True
    assert result["managed_by_loopx"] is True


def test_pause_ssh_source_stops_only_the_owned_control_master() -> None:
    calls: list[list[str]] = []

    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._managed_tunnel_active",
        return_value=True,
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._control_socket_path",
        return_value=Path("/tmp/loopx-test-ssh-source.sock"),
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel.subprocess.run",
        side_effect=lambda args, **kwargs: (
            calls.append(list(args)) or SimpleNamespace(returncode=0)
        ),
    ):
        result = pause_ssh_source("ark-devbox", 8877)

    assert result == {
        "ok": True,
        "status_url": "http://127.0.0.1:8877/status.json",
        "stopped": True,
        "already_paused": False,
    }
    assert calls == [[
        "ssh",
        "-S",
        "/tmp/loopx-test-ssh-source.sock",
        "-O",
        "exit",
        "ark-devbox",
    ]]


def test_pause_ssh_source_is_idempotent_when_the_managed_tunnel_is_absent() -> None:
    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._managed_tunnel_active",
        return_value=False,
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._loopback_status_ok",
        return_value=False,
    ):
        result = pause_ssh_source("ark-devbox", 8877)

    assert result["stopped"] is False
    assert result["already_paused"] is True


def test_pause_ssh_source_refuses_to_kill_an_unmanaged_listener() -> None:
    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._managed_tunnel_active",
        return_value=False,
    ), mock.patch(
        "loopx.control_plane.status.ssh_tunnel._loopback_status_ok",
        return_value=True,
    ):
        with pytest.raises(ValueError, match="not managed by LoopX"):
            pause_ssh_source("ark-devbox", 8877)


def test_ensure_ssh_source_rejects_unknown_alias() -> None:
    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ):
        with pytest.raises(ValueError, match="unknown SSH host alias"):
            ensure_ssh_source("evil-host;id", 8877)


def test_ensure_ssh_source_rejects_invalid_port() -> None:
    with mock.patch(
        "loopx.control_plane.status.ssh_tunnel.configured_ssh_host_aliases",
        return_value=["ark-devbox"],
    ):
        with pytest.raises(ValueError, match="local tunnel port"):
            ensure_ssh_source("ark-devbox", 22)
        with pytest.raises(ValueError, match="local tunnel port"):
            ensure_ssh_source("ark-devbox", "8877")
        with pytest.raises(ValueError, match="local tunnel port"):
            ensure_ssh_source("ark-devbox", True)


class _SshSourceHandler(SshSourceRequestMixin):
    def __init__(self, *, host: str = "127.0.0.1") -> None:
        self.server = SimpleNamespace(server_address=(host, 8767), ssh_config_path=None)
        self.errors: list[tuple[str, int]] = []
        self.payloads: list[dict[str, object]] = []

    def _read_json(self) -> dict[str, object]:
        return {"host_alias": "ark-devbox", "local_port": 8877}

    def _require_loopback_origin(self) -> bool:
        return True

    def _send_error(self, message: str, **kwargs: object) -> None:
        self.errors.append((message, int(kwargs.get("status") or 400)))

    def _send_json(
        self, payload: dict[str, object], *, status: int = 200
    ) -> None:
        self.payloads.append(payload)


def test_ssh_source_request_mixin_delegates_validated_loopback_request() -> None:
    handler = _SshSourceHandler()
    receipt = {"ok": True, "status_url": "http://127.0.0.1:8877/status.json"}

    with mock.patch(
        "loopx.chat_ssh_source_api.ensure_ssh_source", return_value=receipt
    ) as ensure:
        handler._ssh_source_ensure()

    ensure.assert_called_once_with(
        "ark-devbox", 8877, ssh_config_path=None
    )
    assert handler.payloads == [receipt]
    assert handler.errors == []


def test_ssh_source_request_mixin_owns_its_post_route_registry() -> None:
    handler = _SshSourceHandler()

    assert set(handler._ssh_source_post_routes()) == {
        "/api/ssh-source/ensure",
        "/api/ssh-source/pause",
    }


def test_ssh_source_request_mixin_pauses_the_exact_managed_tunnel() -> None:
    handler = _SshSourceHandler()
    receipt = {
        "ok": True,
        "status_url": "http://127.0.0.1:8877/status.json",
        "stopped": True,
        "already_paused": False,
    }

    with mock.patch(
        "loopx.chat_ssh_source_api.pause_ssh_source", return_value=receipt
    ) as pause:
        handler._ssh_source_pause()

    pause.assert_called_once_with("ark-devbox", 8877, ssh_config_path=None)
    assert handler.payloads == [receipt]
    assert handler.errors == []


def test_ssh_source_request_mixin_rejects_non_loopback_server() -> None:
    handler = _SshSourceHandler(host="0.0.0.0")

    with mock.patch("loopx.chat_ssh_source_api.ensure_ssh_source") as ensure:
        handler._ssh_source_ensure()

    ensure.assert_not_called()
    assert handler.payloads == []
    assert handler.errors == [
        ("SSH source management requires a loopback LoopX Chat server.", 403)
    ]
