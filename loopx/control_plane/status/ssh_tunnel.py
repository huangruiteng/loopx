"""Manage an SSH-tunneled LoopX status source.

The personal-workspace source switcher lets an owner point at a configured
SSH host that runs LoopX on its remote loopback. This module automatically
opens the local tunnel and starts the remote status service when missing, so
switching sources in the app does not require manual ssh commands.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

from .ssh_host_catalog import configured_ssh_host_aliases


REMOTE_STATUS_PORT = 8766
_MIN_TUNNEL_PORT = 1024
_MAX_TUNNEL_PORT = 65535
_DEFAULT_WAIT_SECONDS = 12.0
_CONTROL_SOCKET_WAIT_SECONDS = 2.0
_MAX_CONTROL_SOCKET_PATH_BYTES = 72

# Fixed remote bootstrap: resolve the loopx binary and start a loopback
# status server. Only the (already validated) SSH alias is interpolated as an
# ssh argv; this script is never built from user text.
_REMOTE_BOOTSTRAP = (
    "mkdir -p \"$HOME/.codex/loopx\" && "
    "bin=\"$HOME/.local/bin/loopx\"; "
    "[ -x \"$bin\" ] || bin=\"$(command -v loopx || true)\"; "
    "[ -n \"$bin\" ] || { echo 'loopx not found on remote' >&2; exit 1; }; "
    "nohup \"$bin\" --registry \"$HOME/.codex/loopx/registry.global.json\" "
    "serve-status --global-registry --host 127.0.0.1 --port 8766 --limit 80 "
    ">/tmp/loopx-serve-status.log 2>&1 &"
)


def _loopback_status_ok(port: int, *, timeout: float = 8.0) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/status.json", timeout=timeout
        ) as response:
            return int(response.status) == 200
    except (OSError, urllib.error.URLError):
        return False


def _remote_status_ok(alias: str, *, timeout: float = 5.0) -> bool:
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=3",
                alias,
                "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8766/status.json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and result.stdout.strip().endswith("200")


def _start_remote_status(alias: str) -> None:
    subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", alias, _REMOTE_BOOTSTRAP],
        check=True,
        capture_output=True,
        text=True,
        timeout=25,
    )


def _control_socket_directory() -> Path:
    uid = int(getattr(os, "getuid", lambda: 0)())
    # OpenSSH appends a temporary suffix while creating a control socket.
    # macOS exposes a long per-user TMPDIR, which can exceed sockaddr_un's
    # path budget even when our final filename is short. Prefer the stable
    # short /tmp spelling and protect the user-owned child directory below.
    root = (
        Path("/tmp")
        if os.name != "nt" and Path("/tmp").is_dir()
        else Path(tempfile.gettempdir())
    )
    directory = root / f"loopx-ssh-{uid}"
    if directory.exists():
        metadata = directory.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise ValueError("LoopX SSH control directory is not a safe directory")
        if int(getattr(metadata, "st_uid", uid)) != uid:
            raise ValueError("LoopX SSH control directory has an unexpected owner")
    else:
        directory.mkdir(mode=0o700)
    directory.chmod(0o700)
    return directory


def _control_socket_path(alias: str, local_port: int) -> Path:
    identity = f"{alias}\0{local_port}\0{REMOTE_STATUS_PORT}".encode()
    digest = hashlib.sha256(identity).hexdigest()[:24]
    path = _control_socket_directory() / f"{digest}.sock"
    if len(os.fsencode(path)) > _MAX_CONTROL_SOCKET_PATH_BYTES:
        raise ValueError("LoopX SSH control socket path is too long")
    return path


def _managed_tunnel_active(alias: str, local_port: int) -> bool:
    control_socket = _control_socket_path(alias, local_port)
    if not control_socket.exists():
        return False
    metadata = control_socket.lstat()
    if os.name != "nt" and not stat.S_ISSOCK(metadata.st_mode):
        raise ValueError("LoopX SSH control socket is not a socket")
    try:
        result = subprocess.run(
            ["ssh", "-S", str(control_socket), "-O", "check", alias],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _start_managed_tunnel(alias: str, local_port: int) -> None:
    control_socket = _control_socket_path(alias, local_port)
    if control_socket.exists():
        if _managed_tunnel_active(alias, local_port):
            return
        control_socket.unlink()
    try:
        subprocess.run(
            [
                "ssh",
                "-M",
                "-S",
                str(control_socket),
                "-f",
                "-N",
                "-o",
                "ExitOnForwardFailure=yes",
                "-o",
                "ServerAliveInterval=30",
                "-L",
                f"{local_port}:127.0.0.1:{REMOTE_STATUS_PORT}",
                alias,
            ],
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Unable to start the managed SSH tunnel") from exc


def _stop_managed_tunnel(alias: str, local_port: int) -> None:
    control_socket = _control_socket_path(alias, local_port)
    try:
        result = subprocess.run(
            ["ssh", "-S", str(control_socket), "-O", "exit", alias],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Unable to pause the managed SSH tunnel") from exc
    if result.returncode != 0:
        raise ValueError("Unable to pause the managed SSH tunnel")
    deadline = time.monotonic() + _CONTROL_SOCKET_WAIT_SECONDS
    while control_socket.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if control_socket.exists():
        if _managed_tunnel_active(alias, local_port):
            raise ValueError("Managed SSH tunnel did not stop")
        control_socket.unlink()


def _validate_source(
    alias: str,
    local_port: int,
    *,
    ssh_config_path: Path | None,
) -> None:
    if not isinstance(alias, str) or not alias:
        raise ValueError("host alias is required")
    aliases = configured_ssh_host_aliases(ssh_config_path)
    if alias not in aliases:
        raise ValueError(f"unknown SSH host alias: {alias}")
    if isinstance(local_port, bool) or not isinstance(local_port, int) or not (
        _MIN_TUNNEL_PORT <= local_port <= _MAX_TUNNEL_PORT
    ):
        raise ValueError("local tunnel port must be an integer in 1024..65535")


def ensure_ssh_source(
    alias: str,
    local_port: int,
    *,
    ssh_config_path: Path | None = None,
    wait_seconds: float = _DEFAULT_WAIT_SECONDS,
) -> dict[str, object]:
    """Open the tunnel and remote status service for a configured SSH host."""
    _validate_source(alias, local_port, ssh_config_path=ssh_config_path)

    tunnel_required = not _loopback_status_ok(local_port)
    managed_by_loopx = _managed_tunnel_active(alias, local_port)
    remote_started = False
    if tunnel_required:
        if not managed_by_loopx:
            _start_managed_tunnel(alias, local_port)
            managed_by_loopx = True
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if _loopback_status_ok(local_port):
                break
            time.sleep(0.25)
        if not _loopback_status_ok(local_port):
            if not _remote_status_ok(alias):
                _start_remote_status(alias)
                remote_started = True
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                if _loopback_status_ok(local_port):
                    break
                time.sleep(0.25)

    if not _loopback_status_ok(local_port):
        raise ValueError(
            f"SSH tunnel source is not reachable: http://127.0.0.1:{local_port}/status.json"
        )

    return {
        "ok": True,
        "status_url": f"http://127.0.0.1:{local_port}/status.json",
        "tunnel_required": tunnel_required,
        "managed_by_loopx": managed_by_loopx,
        "remote_started": remote_started,
    }


def pause_ssh_source(
    alias: str,
    local_port: int,
    *,
    ssh_config_path: Path | None = None,
) -> dict[str, object]:
    """Stop only the LoopX-owned SSH master for one configured source."""
    _validate_source(alias, local_port, ssh_config_path=ssh_config_path)
    status_url = f"http://127.0.0.1:{local_port}/status.json"
    if not _managed_tunnel_active(alias, local_port):
        if _loopback_status_ok(local_port):
            raise ValueError(
                "SSH tunnel is reachable but is not managed by LoopX; "
                "stop it with the process that created it"
            )
        return {
            "ok": True,
            "status_url": status_url,
            "stopped": False,
            "already_paused": True,
        }
    _stop_managed_tunnel(alias, local_port)
    return {
        "ok": True,
        "status_url": status_url,
        "stopped": True,
        "already_paused": False,
    }
