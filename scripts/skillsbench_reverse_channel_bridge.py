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
import signal
import shlex
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CLIENT_SCHEMA_VERSION = "skillsbench_reverse_channel_client_v0"
SERVER_RESPONSE_SCHEMA_VERSION = "skillsbench_reverse_channel_response_v0"
JSON_PREFLIGHT_RESPONSE_SCHEMA_VERSION = (
    "skillsbench_reverse_channel_json_preflight_response_v0"
)
_CODEX_EXEC_OPTIONS_WITH_VALUE = {
    "-C",
    "--cd",
    "--color",
    "--config",
    "-c",
    "--image",
    "-i",
    "--model",
    "-m",
    "--oss",
    "--output-last-message",
    "--profile",
    "-p",
    "--sandbox",
    "-s",
}
SOCKET_PROBE_SCHEMA_VERSION = "skillsbench_reverse_channel_socket_probe_v0"
ALLOWED_PAYLOAD_ENV_KEYS = (
    "AI_ADDR",
    "AI_PORT",
    "GOAL_HARNESS_REMOTE_BENCH_ROOT",
    "LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH",
)


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


def _stop_process_group(proc: subprocess.Popen[str], *, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
        return
    except ProcessLookupError:
        return
    except OSError:
        pass
    try:
        proc.send_signal(sig)
    except ProcessLookupError:
        return
    except OSError:
        if sig == signal.SIGKILL:
            try:
                proc.kill()
            except OSError:
                pass


def _communicate_after_stop(proc: subprocess.Popen[str]) -> tuple[str, str]:
    try:
        stdout_text, stderr_text = proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        _stop_process_group(proc, sig=signal.SIGKILL)
        stdout_text, stderr_text = proc.communicate(timeout=5)
    return stdout_text or "", stderr_text or ""


def _read_agent_operations_jsonl(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:200_000]
    except OSError:
        return ""


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


def _extract_private_bridge_command(prompt: str) -> str | None:
    match = re.search(r"Private bridge command:\n([^\n]+)", prompt)
    if not match:
        return None
    text = match.group(1).strip()
    return text or None


def _rewrite_private_bridge_command(prompt: str, replacement: str | None) -> str:
    if not replacement:
        return prompt
    pattern = r"(Private bridge command:\n)([^\n]+)"
    return re.sub(pattern, r"\1" + replacement, prompt, count=1)


def _prompt_requires_bridge_first_action(prompt: str) -> bool:
    text = prompt or ""
    if "Private bridge command:" not in text:
        return False
    lowered = text.lower()
    required_markers = (
        "loopx_skillsbench_local_acp_relay_bridge_ready",
        "your first tool action should be a shell",
        "your first agent action must be a shell/tool call",
        "your first agent action must be a task-facing shell/tool call",
        "first run the case-local quota/todo commands",
        "this route simulates `/loopx <task objective>` goal start",
        "compact ranked",
        "selected runnable p0",
    )
    return any(marker in lowered for marker in required_markers)


def _split_codex_exec_prompt_for_stdin(args: list[str]) -> tuple[list[str], str | None]:
    """Move the positional codex exec prompt out of argv and into stdin.

    Host-local benchmark prompts can contain raw task text. Passing them as a
    process argument exposes them to process-list observers on shared hosts, so
    the reverse bridge feeds the prompt through stdin and closes stdin
    immediately instead.
    """

    if not args or args[0] != "exec":
        return args, None
    positional_indices: list[int] = []
    index = 1
    while index < len(args):
        item = args[index]
        if item == "--":
            positional_indices.extend(range(index + 1, len(args)))
            break
        if item in _CODEX_EXEC_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if item.startswith("-"):
            index += 1
            continue
        positional_indices.append(index)
        index += 1
    if not positional_indices:
        return args, None
    prompt_index = positional_indices[-1]
    prompt = args[prompt_index]
    return args[:prompt_index] + args[prompt_index + 1 :], prompt


def _write_instrumented_prompt_bridge(
    *,
    tmp_path: Path,
    bridge_command: str,
    private_bridge_command: str | None,
) -> tuple[Path, Path]:
    """Wrap a local prompt bridge and emit public-safe agent operation records."""

    wrapper_path = tmp_path / "loopx-local-prompt-bridge"
    summary_path = tmp_path / "agent-bridge-ops.jsonl"
    script = f"""#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

SUMMARY_PATH = Path({str(summary_path)!r})
BRIDGE_COMMAND_TEMPLATE = {bridge_command!r}
PRIVATE_BRIDGE_COMMAND = {private_bridge_command!r}

def allowed_env_assignments() -> str:
    keys = (
        "AI_ADDR",
        "AI_PORT",
        "GOAL_HARNESS_REMOTE_BENCH_ROOT",
        "LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH",
    )
    return " ".join(
        f"{{key}}={{shlex.quote(os.environ.get(key, ''))}}"
        for key in keys
        if os.environ.get(key)
    )

def bridge_command() -> str:
    command = BRIDGE_COMMAND_TEMPLATE
    private_bridge = PRIVATE_BRIDGE_COMMAND or ""
    command = command.replace("{{private_bridge_command}}", private_bridge)
    command = command.replace(
        "{{private_bridge_command_sh}}",
        shlex.quote(private_bridge),
    )
    command = command.replace("{{loopx_allowed_env}}", allowed_env_assignments())
    return command

def loopx_subcommands(command: str) -> list[str]:
    try:
        tokens = shlex.split(command or "")
    except ValueError:
        tokens = (command or "").split()
    idx = -1
    for i, token in enumerate(tokens):
        if token == "loopx" or token.endswith("/loopx"):
            idx = i
            break
    if idx < 0:
        return []
    out: list[str] = []
    skip = False
    for token in tokens[idx + 1:]:
        if skip:
            skip = False
            continue
        if token.startswith("--"):
            if "=" not in token and token in {{"--goal-id", "--todo-id", "--claimed-by", "--status", "--note", "--evidence", "--classification", "--registry", "--runtime-root", "--slots", "--source", "--format"}}:
                skip = True
            continue
        if token.startswith("-"):
            continue
        if re.match(r"^[A-Za-z][A-Za-z0-9_-]{{0,40}}$", token):
            out.append(token)
            if len(out) >= 2:
                break
    return out

raw = sys.stdin.read()
record: dict[str, object] = {{
    "schema_version": "skillsbench_remote_bridge_agent_operation_v0",
    "raw_request_recorded": False,
    "raw_stdout_recorded": False,
    "raw_stderr_recorded": False,
    "raw_task_text_recorded": False,
    "credential_values_recorded": False,
    "host_paths_recorded": False,
    "remote_paths_recorded": False,
}}
try:
    payload = json.loads(raw)
except Exception:
    payload = {{}}
operation = payload.get("operation") if isinstance(payload, dict) else ""
record["operation"] = operation if isinstance(operation, str) else "unknown"
subcommands: list[str] = []
if isinstance(payload, dict) and payload.get("operation") == "exec":
    command_text = payload.get("command")
    if isinstance(command_text, str):
        subcommands = loopx_subcommands(command_text)
record["loopx_cli_call"] = bool(subcommands)
record["loopx_subcommands"] = subcommands[:2]
record["loopx_state_read"] = subcommands[:2] in (["quota", "should-run"], ["status"], ["diagnose"])
record["loopx_state_write"] = bool(subcommands and (
    subcommands[0] in {{"todo", "refresh-state"}}
    or subcommands[:2] == ["quota", "spend-slot"]
))
record["task_facing_operation"] = bool(
    operation in {{"read_file", "write_file", "cleanup"}}
    or (operation == "exec" and not subcommands)
)
record["operation_observed"] = True
try:
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\\n")
except OSError:
    pass
proc = subprocess.run(
    bridge_command(),
    input=raw,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=True,
)
sys.stdout.write(proc.stdout)
sys.stderr.write(proc.stderr)
raise SystemExit(proc.returncode)
"""
    wrapper_path.write_text(script, encoding="utf-8")
    wrapper_path.chmod(0o700)
    return wrapper_path, summary_path


def _run_codex_payload(
    payload: dict[str, Any],
    *,
    codex_bin: str,
    default_timeout_sec: float,
    prompt_bridge_command: str | None,
    first_action_timeout_sec: float = 0.0,
    bridge_idle_timeout_sec: float = 0.0,
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
        args, stdin_prompt = _split_codex_exec_prompt_for_stdin(args)
        if stdin_prompt is None:
            payload_stdin = payload.get("stdin")
            if isinstance(payload_stdin, str) and payload_stdin:
                stdin_prompt = payload_stdin
        agent_operations_summary_path: Path | None = None
        if prompt_bridge_command and stdin_prompt is not None:
            private_bridge_command = _extract_private_bridge_command(stdin_prompt)
            if private_bridge_command:
                instrumented_bridge, agent_operations_summary_path = (
                    _write_instrumented_prompt_bridge(
                        tmp_path=tmp_path,
                        bridge_command=prompt_bridge_command,
                        private_bridge_command=private_bridge_command,
                    )
                )
                stdin_prompt = _rewrite_private_bridge_command(
                    stdin_prompt,
                    str(instrumented_bridge),
                )
        cmd = [codex_bin, *args]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if stdin_prompt is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,
            )
            if stdin_prompt is not None and proc.stdin is not None:
                try:
                    proc.stdin.write(stdin_prompt)
                    proc.stdin.close()
                    proc.stdin = None
                except BrokenPipeError:
                    proc.stdin = None
            deadline = time.monotonic() + timeout
            first_action_deadline = 0.0
            if (
                stdin_prompt is not None
                and prompt_bridge_command
                and first_action_timeout_sec > 0
                and _prompt_requires_bridge_first_action(stdin_prompt)
            ):
                first_action_deadline = (
                    time.monotonic() + max(1.0, float(first_action_timeout_sec))
                )
            first_action_seen = not bool(first_action_deadline)
            bridge_idle_timeout_sec = max(0.0, float(bridge_idle_timeout_sec or 0.0))
            last_agent_operations_size = 0
            last_bridge_activity_at = time.monotonic()
            timeout_kind = ""
            while proc.poll() is None:
                now = time.monotonic()
                if not first_action_seen and agent_operations_summary_path:
                    try:
                        current_agent_operations_size = (
                            agent_operations_summary_path.stat().st_size
                        )
                    except OSError:
                        current_agent_operations_size = 0
                    if current_agent_operations_size > last_agent_operations_size:
                        last_agent_operations_size = current_agent_operations_size
                        last_bridge_activity_at = now
                        first_action_seen = True
                    elif current_agent_operations_size > 0:
                        first_action_seen = True
                if not first_action_seen and first_action_deadline and now >= first_action_deadline:
                    timeout_kind = "codex_exec_first_action_timeout"
                    _stop_process_group(proc, sig=signal.SIGTERM)
                    break
                if (
                    first_action_seen
                    and agent_operations_summary_path is not None
                    and bridge_idle_timeout_sec > 0
                    and now - last_bridge_activity_at >= bridge_idle_timeout_sec
                ):
                    timeout_kind = "codex_exec_bridge_idle_timeout"
                    _stop_process_group(proc, sig=signal.SIGTERM)
                    break
                if now >= deadline:
                    timeout_kind = "codex_exec_timeout"
                    _stop_process_group(proc, sig=signal.SIGTERM)
                    break
                time.sleep(0.1)
            if timeout_kind:
                stdout_text, stderr_text = _communicate_after_stop(proc)
            else:
                stdout_text, stderr_text = proc.communicate()
            if timeout_kind:
                return {
                    "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                    "exit_code": 124,
                    "stdout": stdout_text or "",
                    "stderr": f"{timeout_kind}\n",
                    "last_message": "",
                    "remote_last_message_path": remote_last_message_path,
                    "agent_operations_jsonl": _read_agent_operations_jsonl(
                        agent_operations_summary_path
                    ),
                    "agent_operations_raw_material_recorded": False,
                    "raw_task_text_recorded": False,
                    "credential_values_recorded": False,
                }
            try:
                last_message = last_message_path.read_text(encoding="utf-8")
            except OSError:
                last_message = ""
            return {
                "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                "exit_code": int(proc.returncode),
                "stdout": stdout_text or "",
                "stderr": stderr_text or "",
                "last_message": last_message,
                "remote_last_message_path": remote_last_message_path,
                "agent_operations_jsonl": _read_agent_operations_jsonl(
                    agent_operations_summary_path
                ),
                "agent_operations_raw_material_recorded": False,
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
                "agent_operations_jsonl": _read_agent_operations_jsonl(
                    agent_operations_summary_path
                ),
                "agent_operations_raw_material_recorded": False,
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
    try:
        request = json.loads(stdin_text or "{}")
    except json.JSONDecodeError:
        request = {}
    if isinstance(request, dict) and request.get("operation") == "preflight":
        return {
            "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
            "exit_code": 0,
            "stdout": json.dumps(
                {
                    "schema_version": JSON_PREFLIGHT_RESPONSE_SCHEMA_VERSION,
                    "ok": True,
                    "operation": "preflight",
                    "stage": "reverse_channel_json_server",
                    "raw_stdout_recorded": False,
                    "raw_stderr_recorded": False,
                    "raw_task_text_recorded": False,
                    "credential_values_recorded": False,
                    "host_paths_recorded": False,
                    "remote_paths_recorded": False,
                    "upload_performed": False,
                    "submit_performed": False,
                },
                sort_keys=True,
            )
            + "\n",
            "stderr": "",
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "credential_values_recorded": False,
        }
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
    'stdin': sys.stdin.read(),
    'env': {{k: os.environ.get(k, '') for k in ('AI_ADDR','AI_PORT','GOAL_HARNESS_REMOTE_BENCH_ROOT','LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH')}},
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
if not data:
    sys.stderr.write('reverse channel response missing\\n')
    sys.exit(125)
try:
    resp=json.loads(data.decode())
except Exception:
    sys.stderr.write('reverse channel response invalid\\n')
    sys.exit(125)
if not isinstance(resp, dict):
    sys.stderr.write('reverse channel response invalid\\n')
    sys.exit(125)
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
ops = resp.get('agent_operations_jsonl')
ops_path = os.environ.get('LOOPX_REMOTE_AGENT_OPS_SUMMARY_PATH', '')
if isinstance(ops, str) and ops and ops_path:
    os.makedirs(os.path.dirname(ops_path) or '.', exist_ok=True)
    with open(ops_path, 'a', encoding='utf-8') as fh:
        fh.write(ops)
        if not ops.endswith('\\n'):
            fh.write('\\n')
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
if not data:
    sys.stderr.write('reverse channel response missing\\n')
    sys.exit(125)
try:
    resp=json.loads(data.decode())
except Exception:
    sys.stderr.write('reverse channel response invalid\\n')
    sys.exit(125)
if not isinstance(resp, dict):
    sys.stderr.write('reverse channel response invalid\\n')
    sys.exit(125)
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
    codex_server.add_argument("--first-action-timeout-sec", type=float, default=0.0)
    codex_server.add_argument("--bridge-idle-timeout-sec", type=float, default=0.0)
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
                first_action_timeout_sec=args.first_action_timeout_sec,
                bridge_idle_timeout_sec=args.bridge_idle_timeout_sec,
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
