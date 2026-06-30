#!/usr/bin/env python3
"""Hold a reverse-tunnel session while running a remote SkillsBench command.

This helper is intentionally local-side: the remote benchmark host cannot
create an ``ssh -R`` tunnel back to itself. The launcher owns the tunnel process,
probes the remote loopback proxy through SSH, runs one remote command, and then
cleans the tunnel up. Public output records only lifecycle status and compact
counts; raw SSH destinations, remote commands, proxy URLs, and command output
are private.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "skillsbench_reverse_tunnel_supervisor_v0"
DEFAULT_REMOTE_FORWARD = "127.0.0.1:18180:127.0.0.1:18180"
DEFAULT_TEST_HOST = "chatgpt.com"
DEFAULT_TEST_PORT = 443


def _host_kind(value: str) -> str:
    normalized = value.strip("[]").lower()
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return "loopback"
    if normalized.startswith("10.") or normalized.startswith("192.168."):
        return "private"
    if normalized.startswith("172."):
        try:
            second_octet = int(normalized.split(".", 2)[1])
        except (IndexError, ValueError):
            second_octet = -1
        if 16 <= second_octet <= 31:
            return "private"
    return "public_or_unknown"


def _parse_remote_forward(value: str) -> dict[str, Any]:
    parts = value.split(":")
    if len(parts) != 4:
        raise ValueError(
            "--remote-forward must use host:port:host:port form, "
            "for example 127.0.0.1:18180:127.0.0.1:18180"
        )
    remote_host, remote_port, local_host, local_port = parts
    return {
        "remote_host": remote_host,
        "remote_port": int(remote_port),
        "local_host": local_host,
        "local_port": int(local_port),
    }


def _forward_public_contract(remote_forward: str) -> dict[str, Any]:
    parsed = _parse_remote_forward(remote_forward)
    return {
        "remote_host_kind": _host_kind(parsed["remote_host"]),
        "remote_port": parsed["remote_port"],
        "local_host_kind": _host_kind(parsed["local_host"]),
        "local_port": parsed["local_port"],
        "raw_forward_recorded": False,
    }


def _ssh_base_command(args: argparse.Namespace) -> list[str]:
    command = [
        args.ssh_bin,
        "-x",
        "-T",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "ControlPersist=no",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ServerAliveInterval={max(1, int(args.server_alive_interval_sec))}",
        "-o",
        f"ServerAliveCountMax={max(1, int(args.server_alive_count_max))}",
    ]
    for option in args.ssh_option or []:
        command.extend(["-o", option])
    return command


def _tunnel_command(args: argparse.Namespace) -> list[str]:
    keepalive = max(1, int(args.keepalive_interval_sec))
    remote_keepalive = (
        f"while true; do sleep {keepalive}; "
        "echo loopx_reverse_tunnel_keepalive >&2; done"
    )
    return [
        *_ssh_base_command(args),
        "-o",
        "ExitOnForwardFailure=yes",
        "-R",
        args.remote_forward,
        args.ssh_destination,
        remote_keepalive,
    ]


def _probe_command(args: argparse.Namespace) -> str:
    parsed = _parse_remote_forward(args.remote_forward)
    timeout = max(1.0, float(args.probe_timeout_sec))
    code = (
        "# LOOPX_REVERSE_TUNNEL_PROBE\n"
        "import socket, sys\n"
        f"proxy_host = {parsed['remote_host']!r}\n"
        f"proxy_port = {parsed['remote_port']!r}\n"
        f"test_host = {args.test_host!r}\n"
        f"test_port = {int(args.test_port)!r}\n"
        f"timeout = {timeout!r}\n"
        "sock = socket.create_connection((proxy_host, proxy_port), timeout)\n"
        "sock.settimeout(timeout)\n"
        "request = (\n"
        "    f'CONNECT {test_host}:{test_port} HTTP/1.1\\r\\n'\n"
        "    f'Host: {test_host}:{test_port}\\r\\n'\n"
        "    'Proxy-Connection: close\\r\\n\\r\\n'\n"
        ")\n"
        "sock.sendall(request.encode('ascii'))\n"
        "response = sock.recv(256).decode('iso-8859-1', errors='replace')\n"
        "sock.close()\n"
        "print(response.splitlines()[0] if response.splitlines() else '')\n"
    )
    return "python3 -c " + shlex.quote(code)


def _run_remote_probe(args: argparse.Namespace) -> tuple[bool, str]:
    command = [*_ssh_base_command(args), args.ssh_destination, _probe_command(args)]
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, float(args.probe_timeout_sec) + 5.0),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "probe_timeout"
    except OSError:
        return False, "probe_launch_failed"
    output = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    if proc.returncode == 0 and " 200 " in f" {output} ":
        return True, "http_connect_ready"
    if " 407 " in f" {output} ":
        return False, "proxy_auth_required"
    if proc.returncode != 0:
        return False, "probe_exit_nonzero"
    return False, "proxy_connect_rejected"


def _stop_process_group(proc: subprocess.Popen[Any], *, grace_sec: float = 5.0) -> str:
    if proc.poll() is not None:
        return "already_exited"
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return "already_exited"
    except OSError:
        try:
            proc.terminate()
        except OSError:
            pass
    deadline = time.monotonic() + max(0.0, grace_sec)
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try:
                proc.kill()
            except OSError:
                pass
        return "killed"
    return "terminated"


def _write_private_log(
    path: str | None,
    *,
    stdout_text: str,
    stderr_text: str,
) -> bool:
    if not path:
        return False
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        (
            "# stdout\n"
            f"{stdout_text}\n"
            "# stderr\n"
            f"{stderr_text}\n"
        ),
        encoding="utf-8",
    )
    return True


def _size_bucket(value: str) -> str:
    size = len(value.encode("utf-8", errors="replace"))
    if size <= 0:
        return "empty"
    if size < 200:
        return "1_199"
    if size < 1000:
        return "200_999"
    if size < 5000:
        return "1000_4999"
    return "5000_plus"


def run_supervisor(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started_at = time.time()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "tunnel_started": False,
        "tunnel_ready": False,
        "probe_attempt_count": 0,
        "probe_status": "not_started",
        "remote_command_requested": bool(args.remote_command),
        "raw_ssh_destination_recorded": False,
        "raw_remote_command_recorded": False,
        "raw_probe_output_recorded": False,
        "raw_remote_output_recorded": False,
        "private_log_written": False,
        "remote_forward": _forward_public_contract(args.remote_forward),
    }

    tunnel_proc: subprocess.Popen[Any] | None = None
    try:
        tunnel_proc = subprocess.Popen(
            _tunnel_command(args),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
        payload["tunnel_started"] = True
    except OSError as exc:
        payload["first_blocker"] = "reverse_tunnel_launch_failed"
        payload["tunnel_error_type"] = type(exc).__name__[:80]
        return 2, payload

    deadline = time.monotonic() + max(1.0, float(args.tunnel_ready_timeout_sec))
    while time.monotonic() < deadline:
        if tunnel_proc.poll() is not None:
            payload["first_blocker"] = "reverse_tunnel_process_exited_before_ready"
            payload["tunnel_exit_code"] = tunnel_proc.returncode
            return 2, payload
        ready, status = _run_remote_probe(args)
        payload["probe_attempt_count"] = int(payload["probe_attempt_count"]) + 1
        payload["probe_status"] = status
        if ready:
            payload["tunnel_ready"] = True
            break
        time.sleep(max(0.1, float(args.probe_interval_sec)))

    if payload["tunnel_ready"] is not True:
        payload["first_blocker"] = "reverse_tunnel_probe_not_ready"
        return 2, payload

    if args.preflight_only or not args.remote_command:
        payload["ok"] = True
        return 0, payload

    command = [*_ssh_base_command(args), args.ssh_destination, args.remote_command]
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1.0, float(args.run_timeout_sec)),
            check=False,
        )
        stdout_text = proc.stdout or ""
        stderr_text = proc.stderr or ""
        payload["remote_command_exit_code"] = proc.returncode
        payload["remote_stdout_size_bucket"] = _size_bucket(stdout_text)
        payload["remote_stderr_size_bucket"] = _size_bucket(stderr_text)
        payload["private_log_written"] = _write_private_log(
            args.private_log_path,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        payload["ok"] = proc.returncode == 0
        if proc.returncode != 0:
            payload["first_blocker"] = "remote_command_exit_nonzero"
        return (0 if proc.returncode == 0 else proc.returncode or 1), payload
    except subprocess.TimeoutExpired as exc:
        stdout_text = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr_text = exc.stderr if isinstance(exc.stderr, str) else ""
        payload["remote_command_timeout"] = True
        payload["remote_stdout_size_bucket"] = _size_bucket(stdout_text)
        payload["remote_stderr_size_bucket"] = _size_bucket(stderr_text)
        payload["private_log_written"] = _write_private_log(
            args.private_log_path,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )
        payload["first_blocker"] = "remote_command_timeout"
        return 124, payload
    finally:
        payload["duration_sec"] = round(max(0.0, time.time() - started_at), 3)
        if tunnel_proc is not None:
            payload["tunnel_cleanup_status"] = _stop_process_group(tunnel_proc)
            if tunnel_proc.returncode is not None:
                payload["tunnel_exit_code"] = tunnel_proc.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-bin", default="ssh")
    parser.add_argument("--ssh-destination", required=True)
    parser.add_argument(
        "--ssh-option",
        action="append",
        default=[],
        help="Additional -o option for every ssh invocation, e.g. ConnectTimeout=10.",
    )
    parser.add_argument("--server-alive-interval-sec", type=int, default=30)
    parser.add_argument("--server-alive-count-max", type=int, default=3)
    parser.add_argument("--remote-forward", default=DEFAULT_REMOTE_FORWARD)
    parser.add_argument("--test-host", default=DEFAULT_TEST_HOST)
    parser.add_argument("--test-port", type=int, default=DEFAULT_TEST_PORT)
    parser.add_argument("--probe-timeout-sec", type=float, default=8.0)
    parser.add_argument("--probe-interval-sec", type=float, default=1.0)
    parser.add_argument("--tunnel-ready-timeout-sec", type=float, default=30.0)
    parser.add_argument("--keepalive-interval-sec", type=int, default=20)
    parser.add_argument("--run-timeout-sec", type=float, default=7200.0)
    parser.add_argument("--remote-command", default="")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--private-log-path",
        default=None,
        help="Optional private stdout/stderr capture for the remote command.",
    )
    parser.add_argument(
        "--public-output-path",
        default=None,
        help="Optional path for compact public-safe supervisor JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rc, payload = run_supervisor(args)
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.public_output_path:
        path = Path(args.public_output_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
