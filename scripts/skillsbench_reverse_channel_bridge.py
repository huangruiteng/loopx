#!/usr/bin/env python3
"""Serve restartable SkillsBench reverse-channel bridge endpoints.

The split-control SkillsBench route sometimes needs a remote benchmark host to
call back into a local Codex CLI.  This helper keeps that bridge explicit and
testable: client wrappers speak one JSON line over a Unix socket, while local
servers execute Codex or a sandbox JSON bridge without recording raw task data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CLIENT_SCHEMA_VERSION = "skillsbench_reverse_channel_client_v0"
SERVER_RESPONSE_SCHEMA_VERSION = "skillsbench_reverse_channel_response_v0"
SOCKET_PROBE_SCHEMA_VERSION = "skillsbench_reverse_channel_socket_probe_v0"
ALLOWED_PAYLOAD_ENV_KEYS = ("AI_ADDR", "AI_PORT", "GOAL_HARNESS_REMOTE_BENCH_ROOT")


def _send_json_line(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")


def _recv_json_line(conn: socket.socket) -> dict[str, Any]:
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    if not data:
        return {}
    return json.loads(data.decode("utf-8"))


def _safe_env(extra: object) -> dict[str, str]:
    env = os.environ.copy()
    env.update(_allowed_payload_env(extra))
    return env


def _allowed_payload_env(extra: object) -> dict[str, str]:
    env: dict[str, str] = {}
    if isinstance(extra, dict):
        for key, value in extra.items():
            if not isinstance(key, str):
                continue
            if key in ALLOWED_PAYLOAD_ENV_KEYS:
                env[key] = str(value)
    return env


def _allowed_env_assignments(extra: object) -> str:
    env = _allowed_payload_env(extra)
    return " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items())


def _bridge_command_with_payload_env(command: str, extra: object) -> str:
    return command.replace("{loopx_allowed_env}", _allowed_env_assignments(extra))


def _replace_output_last_message(args: list[str], replacement: Path) -> str | None:
    for index, token in enumerate(args[:-1]):
        if token == "--output-last-message":
            original = args[index + 1]
            args[index + 1] = str(replacement)
            return original
    return None


def _replace_remote_cwd(args: list[str], replacement: Path) -> str | None:
    for index, token in enumerate(args[:-1]):
        if token in {"-C", "--cwd"}:
            original = args[index + 1]
            args[index + 1] = str(replacement)
            return original
    return None


def _rewrite_private_bridge_command(prompt: str, replacement: str | None) -> str:
    if not replacement:
        return prompt
    pattern = r"(Private bridge command:\n)([^\n]+)"
    return re.sub(pattern, r"\1" + replacement, prompt, count=1)


def _run_codex_payload(
    payload: dict[str, Any],
    *,
    codex_bin: str,
    default_timeout_sec: float,
    prompt_bridge_command: str | None,
) -> dict[str, Any]:
    args = [str(item) for item in payload.get("args") or []]
    if not args:
        args = ["exec", "--help"]
    if args and args[0] == "exec":
        args[0] = "exec"
    timeout = payload.get("timeout_sec")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        timeout = default_timeout_sec
    timeout = max(1.0, min(float(timeout), max(float(default_timeout_sec), 1.0)))
    env = _safe_env(payload.get("env"))
    with tempfile.TemporaryDirectory(prefix="loopx-reverse-codex-") as tmp:
        tmp_path = Path(tmp)
        last_message_path = tmp_path / "last-message.txt"
        local_cwd = tmp_path / "cwd"
        local_cwd.mkdir(parents=True, exist_ok=True)
        remote_last_message_path = _replace_output_last_message(args, last_message_path)
        _replace_remote_cwd(args, local_cwd)
        if prompt_bridge_command and args:
            args[-1] = _rewrite_private_bridge_command(args[-1], prompt_bridge_command)
        cmd = [codex_bin, *args]
        try:
            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
            try:
                last_message = last_message_path.read_text(encoding="utf-8")
            except OSError:
                last_message = ""
            return {
                "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                "exit_code": int(proc.returncode),
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
                "last_message": last_message,
                "remote_last_message_path": remote_last_message_path,
                "raw_task_text_recorded": False,
                "credential_values_recorded": False,
            }
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return {
                "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                "exit_code": 124,
                "stdout": stdout,
                "stderr": stderr,
                "last_message": "",
                "remote_last_message_path": remote_last_message_path,
                "raw_task_text_recorded": False,
                "credential_values_recorded": False,
            }


def _run_json_bridge_payload(
    payload: dict[str, Any],
    *,
    bridge_command: str,
    default_timeout_sec: float,
) -> dict[str, Any]:
    timeout = max(1.0, float(default_timeout_sec))
    stdin_text = str(payload.get("stdin") or "")
    payload_env = payload.get("env")
    env = _safe_env(payload_env)
    command = _bridge_command_with_payload_env(bridge_command, payload_env)
    try:
        proc = subprocess.run(
            command,
            input=stdin_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        return {
            "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
            "exit_code": int(proc.returncode),
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "credential_values_recorded": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
            "exit_code": 124,
            "stdout": stdout,
            "stderr": stderr,
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "credential_values_recorded": False,
        }


def _serve_socket(
    socket_path: Path,
    *,
    once: bool,
    handler: Any,
) -> int:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        socket_path.unlink()
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX)
    server.bind(str(socket_path))
    socket_path.chmod(0o600)
    server.listen(8)
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    payload = _recv_json_line(conn)
                    if not payload:
                        continue
                    response = handler(payload)
                except Exception as exc:  # keep client deterministic
                    response = {
                        "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": type(exc).__name__,
                        "raw_task_text_recorded": False,
                        "credential_values_recorded": False,
                    }
                try:
                    _send_json_line(conn, response)
                except (BrokenPipeError, ConnectionResetError):
                    if once:
                        return 1
                    continue
            if once:
                return 0
    finally:
        server.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass


def _write_codex_client(socket_path: str, output_path: Path) -> None:
    script = f"""#!/usr/bin/env python3
import json, os, socket, sys
SOCK = {socket_path!r}
payload = {{
    'schema_version': {CLIENT_SCHEMA_VERSION!r},
    'args': sys.argv[1:],
    'env': {{k: os.environ.get(k, '') for k in ('AI_ADDR','AI_PORT','GOAL_HARNESS_REMOTE_BENCH_ROOT')}},
    'timeout_sec': float(os.environ.get('LOOPX_REVERSE_CODEX_TIMEOUT_SEC', '7200')),
}}
s=socket.socket(socket.AF_UNIX)
s.settimeout(float(os.environ.get('LOOPX_REVERSE_CONNECT_TIMEOUT_SEC', '30')))
s.connect(SOCK)
s.settimeout(float(os.environ.get(
    'LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC',
    os.environ.get('LOOPX_REVERSE_CODEX_TIMEOUT_SEC', '7200'),
)))
s.sendall(json.dumps(payload).encode()+b'\\n')
data=b''
while not data.endswith(b'\\n'):
    chunk=s.recv(65536)
    if not chunk:
        break
    data += chunk
resp=json.loads(data.decode() or '{{}}')
out=resp.get('stdout')
err=resp.get('stderr')
if isinstance(out, str): sys.stdout.write(out)
if isinstance(err, str): sys.stderr.write(err)
last=resp.get('last_message')
remote_path=resp.get('remote_last_message_path')
if isinstance(last, str) and isinstance(remote_path, str) and remote_path:
    os.makedirs(os.path.dirname(remote_path) or '.', exist_ok=True)
    with open(remote_path, 'w', encoding='utf-8') as fh:
        fh.write(last)
sys.exit(int(resp.get('exit_code') or 0))
"""
    output_path.write_text(script, encoding="utf-8")
    output_path.chmod(0o700)


def _write_json_client(socket_path: str, output_path: Path) -> None:
    script = f"""#!/usr/bin/env python3
import json, os, socket, sys
SOCK = {socket_path!r}
payload = {{
    'schema_version': {CLIENT_SCHEMA_VERSION!r},
    'stdin': sys.stdin.read(),
    'env': {{k: os.environ.get(k, '') for k in ('AI_ADDR','AI_PORT','GOAL_HARNESS_REMOTE_BENCH_ROOT')}},
}}
s=socket.socket(socket.AF_UNIX)
s.settimeout(float(os.environ.get('LOOPX_REVERSE_CONNECT_TIMEOUT_SEC', '30')))
s.connect(SOCK)
s.settimeout(float(os.environ.get(
    'LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC',
    os.environ.get('LOOPX_REVERSE_JSON_TIMEOUT_SEC', '300'),
)))
s.sendall(json.dumps(payload).encode()+b'\\n')
data=b''
while not data.endswith(b'\\n'):
    chunk=s.recv(65536)
    if not chunk:
        break
    data += chunk
resp=json.loads(data.decode() or '{{}}')
out=resp.get('stdout')
err=resp.get('stderr')
if isinstance(out, str): sys.stdout.write(out)
if isinstance(err, str): sys.stderr.write(err)
sys.exit(int(resp.get('exit_code') or 0))
"""
    output_path.write_text(script, encoding="utf-8")
    output_path.chmod(0o700)


def _probe_socket(socket_path: Path, *, timeout_sec: float) -> dict[str, Any]:
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(timeout_sec)
    try:
        sock.connect(str(socket_path))
        return {
            "schema_version": SOCKET_PROBE_SCHEMA_VERSION,
            "ready": True,
            "first_blocker": "skillsbench_reverse_channel_socket_ready",
            "raw_output_recorded": False,
            "credential_values_recorded": False,
        }
    except FileNotFoundError:
        blocker = "skillsbench_reverse_channel_socket_missing"
    except ConnectionRefusedError:
        blocker = "skillsbench_reverse_channel_socket_orphaned"
    except TimeoutError:
        blocker = "skillsbench_reverse_channel_socket_timeout"
    except OSError:
        blocker = "skillsbench_reverse_channel_socket_connect_failed"
    finally:
        sock.close()
    return {
        "schema_version": SOCKET_PROBE_SCHEMA_VERSION,
        "ready": False,
        "first_blocker": blocker,
        "raw_output_recorded": False,
        "credential_values_recorded": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    codex_server = sub.add_parser("serve-codex")
    codex_server.add_argument("--socket", required=True)
    codex_server.add_argument("--codex-bin", default="codex")
    codex_server.add_argument("--timeout-sec", type=float, default=7200.0)
    codex_server.add_argument("--prompt-bridge-command")
    codex_server.add_argument("--once", action="store_true")

    json_server = sub.add_parser("serve-json")
    json_server.add_argument("--socket", required=True)
    json_server.add_argument(
        "--bridge-command",
        required=True,
        help=(
            "Private JSON bridge command. Use {loopx_allowed_env} inside nested "
            "remote commands to forward AI_ADDR/AI_PORT without logging values."
        ),
    )
    json_server.add_argument("--timeout-sec", type=float, default=300.0)
    json_server.add_argument("--once", action="store_true")

    write_client = sub.add_parser("write-client")
    write_client.add_argument("--kind", choices=("codex", "json"), required=True)
    write_client.add_argument("--socket", required=True)
    write_client.add_argument("--output", required=True)

    probe = sub.add_parser("probe-socket")
    probe.add_argument("--socket", required=True)
    probe.add_argument("--timeout-sec", type=float, default=3.0)

    args = parser.parse_args(argv)
    if args.command == "serve-codex":
        return _serve_socket(
            Path(args.socket),
            once=bool(args.once),
            handler=lambda payload: _run_codex_payload(
                payload,
                codex_bin=args.codex_bin,
                default_timeout_sec=args.timeout_sec,
                prompt_bridge_command=args.prompt_bridge_command,
            ),
        )
    if args.command == "serve-json":
        return _serve_socket(
            Path(args.socket),
            once=bool(args.once),
            handler=lambda payload: _run_json_bridge_payload(
                payload,
                bridge_command=args.bridge_command,
                default_timeout_sec=args.timeout_sec,
            ),
        )
    if args.command == "write-client":
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.kind == "codex":
            _write_codex_client(args.socket, output)
        else:
            _write_json_client(args.socket, output)
        print(json.dumps({"ok": True, "kind": args.kind, "raw_path_recorded": False}))
        return 0
    if args.command == "probe-socket":
        print(json.dumps(_probe_socket(Path(args.socket), timeout_sec=args.timeout_sec), sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
