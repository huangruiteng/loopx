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
import threading
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from loopx.benchmark_adapters.skillsbench_bridge_guard import (  # noqa: E402
    LOOPX_COMMAND_INSTRUMENTATION_SOURCE,
)


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

_BRIDGE_GUARD_NAMESPACE: dict[str, Any] = {
    "re": re,
    "shlex": shlex,
    "sys": sys,
}
# The generated sandbox wrapper and the host broker must apply the exact same
# command parser. Load the trusted in-repo source once instead of duplicating it.
exec(LOOPX_COMMAND_INSTRUMENTATION_SOURCE, _BRIDGE_GUARD_NAMESPACE)
_loopx_invocation_count = _BRIDGE_GUARD_NAMESPACE["loopx_invocation_count"]
_loopx_subcommands = _BRIDGE_GUARD_NAMESPACE["loopx_subcommands"]


def _send_json_line(sock: socket.socket, payload: dict[str, Any]) -> None:
    sock.sendall(json.dumps(payload, separators=(",", ":")).encode() + b"\n")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    tmp_path.write_text(
        json.dumps(payload, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


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
    private_bridge_command = ""
    if isinstance(extra, dict):
        private_bridge_command = str(extra.get("private_bridge_command") or "")
        env_extra = extra.get("env") if isinstance(extra.get("env"), dict) else extra
    else:
        env_extra = extra
    command = command.replace("{private_bridge_command}", private_bridge_command)
    command = command.replace(
        "{private_bridge_command_sh}",
        shlex.quote(private_bridge_command),
    )
    return command.replace("{loopx_allowed_env}", _allowed_env_assignments(env_extra))


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


def _write_process_stdin_async(
    proc: subprocess.Popen[str],
    stdin_text: str | None,
) -> None:
    """Feed stdin without blocking the watchdog loop on a full pipe."""

    if stdin_text is None or proc.stdin is None:
        return
    stdin_pipe = proc.stdin
    proc.stdin = None

    def _writer() -> None:
        try:
            stdin_pipe.write(stdin_text)
            stdin_pipe.close()
        except (BrokenPipeError, ValueError, OSError):
            pass

    threading.Thread(
        target=_writer,
        name="loopx-reverse-channel-stdin-writer",
        daemon=True,
    ).start()


def _read_agent_operations_jsonl(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:200_000]
    except OSError:
        return ""


def _bridge_summary_has_inflight_operation(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    starts = 0
    completions = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        phase = str(record.get("record_phase") or "").strip().lower()
        if phase == "complete" and not _bridge_operation_record_interrupted(record):
            completions += 1
        elif phase == "start" or record.get("operation_observed") is True:
            starts += 1
    return starts > completions


def _bridge_operation_record_interrupted(record: dict[str, Any]) -> bool:
    rc = record.get("returncode")
    if isinstance(rc, int) and not isinstance(rc, bool) and rc < 0:
        return True
    category = str(record.get("failure_category") or "")
    return record.get("interrupted") is True or category in {
        "bridge_operation_interrupted",
        "bridge_controller_interrupted",
    }


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
    original = _extract_private_bridge_command(prompt)
    if original:
        return prompt.replace(original, replacement)
    pattern = r"(Private bridge command:\n)([^\n]+)"
    return re.sub(
        pattern,
        lambda match: f"{match.group(1)}{replacement}",
        prompt,
        count=1,
    )


def _prompt_requires_bridge_first_action(prompt: str) -> bool:
    text = prompt or ""
    if "Private bridge command:" not in text:
        return False
    lowered = text.lower()
    required_markers = (
        "loopx_skillsbench_local_acp_relay_bridge_ready",
        "mandatory product-mode solver checkpoint",
        "mandatory product-mode closeout checkpoint",
        "must start with either a task-facing sandbox bridge operation",
        "your first tool action should be a shell",
        "your first agent action must be a shell/tool call",
        "your first agent action must be a task-facing shell/tool call",
        "first run the case-local quota/todo commands",
        "first loopx cli action must invoke `start-goal",
        "this benchmark treatment executes the actual agent contract for `/loopx",
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


def _append_agent_operation_record(
    summary_path: Path,
    record: dict[str, Any],
) -> None:
    try:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        with summary_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        pass


def _agent_operation_record(stdin_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdin_text)
    except (json.JSONDecodeError, TypeError, ValueError):
        payload = {}
    operation = payload.get("operation") if isinstance(payload, dict) else ""
    subcommands: list[str] = []
    loopx_invocations = 0
    if isinstance(payload, dict) and operation == "exec":
        command_text = payload.get("command")
        if isinstance(command_text, str):
            loopx_invocations = int(_loopx_invocation_count(command_text))
            subcommands = list(_loopx_subcommands(command_text))
    return {
        "schema_version": "skillsbench_remote_bridge_agent_operation_v0",
        "operation": operation if isinstance(operation, str) else "unknown",
        "loopx_invocation_count": loopx_invocations,
        "loopx_cli_call": loopx_invocations > 0,
        "loopx_subcommands": subcommands[:2],
        "loopx_state_read": subcommands[:2]
        in (
            ["start-goal"],
            ["quota", "should-run"],
            ["status"],
            ["diagnose"],
        ),
        "loopx_state_write": bool(
            subcommands
            and (
                subcommands[0] in {"todo", "refresh-state"}
                or subcommands[:2] == ["quota", "spend-slot"]
            )
        ),
        "task_facing_operation": bool(
            operation in {"read_file", "write_file", "cleanup"}
            or (operation == "exec" and loopx_invocations == 0)
        ),
        "operation_observed": True,
        "raw_request_recorded": False,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "raw_task_text_recorded": False,
        "credential_values_recorded": False,
        "host_paths_recorded": False,
        "remote_paths_recorded": False,
    }


def _run_prompt_bridge_broker_payload(
    payload: dict[str, Any],
    *,
    bridge_command: str,
    private_bridge_command: str,
    default_timeout_sec: float,
    stop_event: threading.Event,
    summary_path: Path,
) -> dict[str, Any]:
    """Execute a Codex-requested bridge outside the Codex sandbox."""

    stdin_text = str(payload.get("stdin") or "")
    operation_record = _agent_operation_record(stdin_text)
    operation_record["record_phase"] = "start"
    _append_agent_operation_record(summary_path, operation_record)
    if int(operation_record["loopx_invocation_count"]) > 1:
        stderr_text = (
            "bridge request rejected: send exactly one LoopX CLI command per "
            "operation=exec request\n"
        )
        complete_record = dict(operation_record)
        complete_record.update(
            {
                "record_phase": "complete",
                "returncode": 2,
                "success": False,
                "stdout_bytes": 0,
                "stderr_bytes": len(stderr_text.encode("utf-8")),
                "failure_category": (
                    "multiple_loopx_commands_per_bridge_request"
                ),
            }
        )
        _append_agent_operation_record(summary_path, complete_record)
        return {
            "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
            "exit_code": 2,
            "stdout": "",
            "stderr": stderr_text,
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "credential_values_recorded": False,
        }

    broker_payload = dict(payload)
    broker_payload["private_bridge_command"] = private_bridge_command
    command = _bridge_command_with_payload_env(bridge_command, broker_payload)
    env = _safe_env(payload.get("env"))
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
        env=env,
        start_new_session=True,
    )
    _write_process_stdin_async(proc, stdin_text)
    deadline = time.monotonic() + max(1.0, float(default_timeout_sec))
    interrupted = False
    while proc.poll() is None:
        if stop_event.is_set() or time.monotonic() >= deadline:
            interrupted = True
            _stop_process_group(proc, sig=signal.SIGTERM)
            break
        time.sleep(0.05)
    if interrupted:
        stdout_text, stderr_text = _communicate_after_stop(proc)
        complete_record = dict(operation_record)
        complete_record.update(
            {
                "record_phase": "complete",
                "returncode": 124,
                "success": False,
                "stdout_bytes": len(stdout_text.encode("utf-8")),
                "stderr_bytes": len(stderr_text.encode("utf-8")),
                "failure_category": "bridge_operation_interrupted",
                "interrupted": True,
                "controller_interrupted": True,
            }
        )
        _append_agent_operation_record(summary_path, complete_record)
        return {
            "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
            "exit_code": 124,
            "stdout": stdout_text,
            "stderr": stderr_text or "prompt bridge broker interrupted\n",
            "raw_stdout_recorded": False,
            "raw_stderr_recorded": False,
            "credential_values_recorded": False,
        }
    stdout_text, stderr_text = proc.communicate()
    failure_category = ""
    if proc.returncode != 0:
        if "PermissionError" in stderr_text or "Operation not permitted" in stderr_text:
            failure_category = "bridge_client_permission_error"
        elif "No such file or directory" in stderr_text:
            failure_category = "bridge_command_not_found"
        elif proc.returncode == 255 and command.lstrip().startswith("ssh "):
            failure_category = "bridge_ssh_unavailable"
        else:
            failure_category = "bridge_command_failed"
    complete_record = dict(operation_record)
    complete_record.update(
        {
            "record_phase": "complete",
            "returncode": int(proc.returncode),
            "success": proc.returncode == 0,
            "stdout_bytes": len((stdout_text or "").encode("utf-8")),
            "stderr_bytes": len((stderr_text or "").encode("utf-8")),
        }
    )
    if failure_category:
        complete_record["failure_category"] = failure_category
    _append_agent_operation_record(summary_path, complete_record)
    public_stderr = stderr_text or ""
    if failure_category:
        public_stderr = (
            f"LOOPX_PROMPT_BRIDGE_FAILURE_CATEGORY={failure_category}\n{public_stderr}"
        )
    return {
        "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
        "exit_code": int(proc.returncode),
        "stdout": stdout_text or "",
        "stderr": public_stderr,
        "raw_stdout_recorded": False,
        "raw_stderr_recorded": False,
        "credential_values_recorded": False,
    }


def _start_prompt_bridge_broker(
    *,
    local_cwd: Path,
    bridge_command: str,
    private_bridge_command: str,
    default_timeout_sec: float,
    summary_path: Path,
) -> tuple[Path, threading.Event, threading.Thread]:
    queue_dir = local_cwd / ".loopx-prompt-bridge-broker"
    client_path = local_cwd / "loopx-local-prompt-bridge"
    _write_json_file_client(str(queue_dir), client_path)
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_serve_json_file_queue,
        kwargs={
            "queue_dir": queue_dir,
            "once": False,
            "poll_interval_sec": 0.02,
            "handler": lambda payload: _run_prompt_bridge_broker_payload(
                payload,
                bridge_command=bridge_command,
                private_bridge_command=private_bridge_command,
                default_timeout_sec=default_timeout_sec,
                stop_event=stop_event,
                summary_path=summary_path,
            ),
            "stop_event": stop_event,
        },
        name="loopx-prompt-bridge-broker",
        daemon=True,
    )
    thread.start()
    return client_path, stop_event, thread


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
        prompt_bridge_stop_event: threading.Event | None = None
        prompt_bridge_thread: threading.Thread | None = None
        if prompt_bridge_command and stdin_prompt is not None:
            private_bridge_command = _extract_private_bridge_command(stdin_prompt)
            if private_bridge_command:
                agent_operations_summary_path = tmp_path / "agent-bridge-ops.jsonl"
                broker_client, prompt_bridge_stop_event, prompt_bridge_thread = (
                    _start_prompt_bridge_broker(
                        local_cwd=local_cwd,
                        bridge_command=prompt_bridge_command,
                        private_bridge_command=private_bridge_command,
                        default_timeout_sec=timeout,
                        summary_path=agent_operations_summary_path,
                    )
                )
                stdin_prompt = _rewrite_private_bridge_command(
                    stdin_prompt,
                    str(broker_client),
                )
        cmd = [codex_bin, *args]
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE
                if stdin_prompt is not None
                else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=True,
            )
            _write_process_stdin_async(proc, stdin_prompt)
            deadline = time.monotonic() + timeout
            first_action_deadline = 0.0
            if (
                stdin_prompt is not None
                and prompt_bridge_command
                and first_action_timeout_sec > 0
                and _prompt_requires_bridge_first_action(stdin_prompt)
            ):
                first_action_deadline = time.monotonic() + max(
                    1.0, float(first_action_timeout_sec)
                )
            first_action_seen = not bool(first_action_deadline)
            bridge_idle_timeout_sec = max(0.0, float(bridge_idle_timeout_sec or 0.0))
            bridge_activity_seen = False
            last_agent_operations_size = 0
            last_bridge_activity_at = time.monotonic()
            timeout_kind = ""
            while proc.poll() is None:
                now = time.monotonic()
                if agent_operations_summary_path:
                    try:
                        current_agent_operations_size = (
                            agent_operations_summary_path.stat().st_size
                        )
                    except OSError:
                        current_agent_operations_size = 0
                    if current_agent_operations_size > last_agent_operations_size:
                        last_agent_operations_size = current_agent_operations_size
                        last_bridge_activity_at = now
                        bridge_activity_seen = True
                        first_action_seen = True
                    elif not first_action_seen and current_agent_operations_size > 0:
                        first_action_seen = True
                if (
                    not first_action_seen
                    and first_action_deadline
                    and now >= first_action_deadline
                ):
                    timeout_kind = "codex_exec_first_action_timeout"
                    _stop_process_group(proc, sig=signal.SIGTERM)
                    break
                if (
                    bridge_activity_seen
                    and agent_operations_summary_path is not None
                    and bridge_idle_timeout_sec > 0
                    and not _bridge_summary_has_inflight_operation(
                        agent_operations_summary_path
                    )
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
        finally:
            if prompt_bridge_stop_event is not None:
                prompt_bridge_stop_event.set()
            if prompt_bridge_thread is not None:
                prompt_bridge_thread.join(timeout=5)


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
    command = _bridge_command_with_payload_env(bridge_command, payload)
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


def _serve_json_file_queue(
    queue_dir: Path,
    *,
    once: bool,
    poll_interval_sec: float,
    handler: Any,
    stop_event: threading.Event | None = None,
) -> int:
    requests_dir = queue_dir / "requests"
    processing_dir = queue_dir / "processing"
    responses_dir = queue_dir / "responses"
    requests_dir.mkdir(parents=True, exist_ok=True)
    processing_dir.mkdir(parents=True, exist_ok=True)
    responses_dir.mkdir(parents=True, exist_ok=True)
    poll_interval_sec = max(0.01, float(poll_interval_sec or 0.05))
    while stop_event is None or not stop_event.is_set():
        for request_path in sorted(requests_dir.glob("*.json")):
            processing_path = processing_dir / request_path.name
            try:
                os.replace(request_path, processing_path)
            except FileNotFoundError:
                continue
            except OSError:
                continue
            response_path = responses_dir / request_path.name
            try:
                try:
                    payload_raw = processing_path.read_text(encoding="utf-8")
                    payload = json.loads(payload_raw or "{}")
                    if not isinstance(payload, dict):
                        payload = {}
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
                if not isinstance(response, dict):
                    response = {
                        "schema_version": SERVER_RESPONSE_SCHEMA_VERSION,
                        "exit_code": 1,
                        "stdout": "",
                        "stderr": "invalid bridge response",
                        "raw_task_text_recorded": False,
                        "credential_values_recorded": False,
                    }
                _atomic_write_json(response_path, response)
            finally:
                try:
                    processing_path.unlink()
                except FileNotFoundError:
                    pass
            if once:
                return 0
        if stop_event is None:
            time.sleep(poll_interval_sec)
        else:
            stop_event.wait(poll_interval_sec)
    return 0


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


def _write_json_file_client(queue_dir: str, output_path: Path) -> None:
    script = f"""#!/usr/bin/env python3
import json, os, sys, time, uuid
from pathlib import Path
QUEUE = Path({queue_dir!r})
REQUESTS = QUEUE / 'requests'
RESPONSES = QUEUE / 'responses'

def fail(message: str) -> None:
    sys.stderr.write(message + '\\n')
    raise SystemExit(125)

def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{{path.name}}.{{os.getpid()}}.{{time.monotonic_ns()}}.tmp")
    tmp.write_text(json.dumps(payload, separators=(',', ':'), sort_keys=True), encoding='utf-8')
    os.replace(tmp, path)

request_id = f"{{int(time.time() * 1000)}}-{{os.getpid()}}-{{uuid.uuid4().hex}}"
payload = {{
    'schema_version': {CLIENT_SCHEMA_VERSION!r},
    'request_id': request_id,
    'stdin': sys.stdin.read(),
    'env': {{k: os.environ.get(k, '') for k in ('AI_ADDR','AI_PORT','GOAL_HARNESS_REMOTE_BENCH_ROOT')}},
    'private_bridge_command': os.environ.get('LOOPX_PRIVATE_BRIDGE_COMMAND', ''),
}}
request_path = REQUESTS / f"{{request_id}}.json"
response_path = RESPONSES / f"{{request_id}}.json"
try:
    atomic_write_json(request_path, payload)
except OSError as exc:
    fail(f"reverse channel request write failed: {{type(exc).__name__}}")
deadline = time.monotonic() + float(os.environ.get(
    'LOOPX_REVERSE_RESPONSE_TIMEOUT_SEC',
    os.environ.get('LOOPX_REVERSE_JSON_TIMEOUT_SEC', '300'),
))
resp = None
while time.monotonic() < deadline:
    try:
        if response_path.exists():
            resp = json.loads(response_path.read_text(encoding='utf-8') or '{{}}')
            break
    except json.JSONDecodeError:
        fail('reverse channel response invalid')
    except OSError:
        pass
    time.sleep(float(os.environ.get('LOOPX_REVERSE_FILE_POLL_INTERVAL_SEC', '0.05')))
if resp is None:
    fail('reverse channel response missing')
if not isinstance(resp, dict):
    fail('reverse channel response invalid')
try:
    response_path.unlink()
except OSError:
    pass
out = resp.get('stdout')
err = resp.get('stderr')
if isinstance(out, str): sys.stdout.write(out)
if isinstance(err, str): sys.stderr.write(err)
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
    'private_bridge_command': os.environ.get('LOOPX_PRIVATE_BRIDGE_COMMAND', ''),
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

    json_file_server = sub.add_parser("serve-json-file")
    json_file_server.add_argument("--queue-dir", required=True)
    json_file_server.add_argument(
        "--bridge-command",
        required=True,
        help=(
            "Private JSON bridge command. Use {loopx_allowed_env} inside nested "
            "remote commands to forward AI_ADDR/AI_PORT without logging values."
        ),
    )
    json_file_server.add_argument("--timeout-sec", type=float, default=300.0)
    json_file_server.add_argument("--poll-interval-sec", type=float, default=0.05)
    json_file_server.add_argument("--once", action="store_true")

    write_client = sub.add_parser("write-client")
    write_client.add_argument(
        "--kind",
        choices=("codex", "json", "json-file"),
        required=True,
    )
    write_client.add_argument("--socket")
    write_client.add_argument("--queue-dir")
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
    if args.command == "serve-json-file":
        return _serve_json_file_queue(
            Path(args.queue_dir),
            once=bool(args.once),
            poll_interval_sec=args.poll_interval_sec,
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
            if not args.socket:
                parser.error("--socket is required for --kind codex")
            _write_codex_client(args.socket, output)
        elif args.kind == "json":
            if not args.socket:
                parser.error("--socket is required for --kind json")
            _write_json_client(args.socket, output)
        else:
            if not args.queue_dir:
                parser.error("--queue-dir is required for --kind json-file")
            _write_json_file_client(args.queue_dir, output)
        print(json.dumps({"ok": True, "kind": args.kind, "raw_path_recorded": False}))
        return 0
    if args.command == "probe-socket":
        print(
            json.dumps(
                _probe_socket(Path(args.socket), timeout_sec=args.timeout_sec),
                sort_keys=True,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
