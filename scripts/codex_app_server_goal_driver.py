#!/usr/bin/env python3
"""Minimal Codex app-server Goal turn driver for host-side benchmark agents."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any


class CodexAppServerGoalDriverError(RuntimeError):
    """Raised when the app-server Goal driver cannot start a turn."""


@dataclass
class CodexAppServerGoalTurn:
    process: subprocess.Popen[str]
    thread_id: str
    turn_id: str
    work_dir: Path | None = None
    turn_id_source: str = ""
    turn_start_response_turn_id_present: bool = False
    turn_event_stream_turn_id_present: bool = False
    next_request_id: int = 6
    goal_status: str = ""
    turn_status: str = ""
    turn_completed_observed: bool = False
    assistant_message: str = ""
    agent_message_delta_count: int = 0
    agent_message_item_count: int = 0
    item_completed_count: int = 0
    non_user_item_completed_count: int = 0
    user_message_item_count: int = 0
    session_event_count: int = 0
    session_log_observed: bool = False
    session_task_complete_observed: bool = False
    stream_eof_observed: bool = False
    stream_error_observed: bool = False
    process_exit_observed: bool = False
    process_returncode: int | None = None
    transport_reconnect_attempted: bool = False
    transport_reconnect_succeeded: bool = False
    transport_reconnect_reason: str = ""
    goal_reactivation_attempted: bool = False
    goal_reactivation_succeeded: bool = False
    goal_reactivation_previous_status: str = ""
    goal_reactivation_result_status: str = ""
    notifications: list[str] = field(default_factory=list)
    _responses: "queue.Queue[dict[str, Any] | Exception] | None" = field(
        default=None,
        repr=False,
    )
    _assistant_message_parts: list[str] = field(default_factory=list, repr=False)
    _session_offsets: dict[str, int] = field(default_factory=dict, repr=False)

    def terminate(self, *, timeout_sec: float = 2.0) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            self.process.kill()


def _reader_thread(
    stream: Any,
    out: "queue.Queue[dict[str, Any] | Exception]",
) -> None:
    try:
        for line in stream:
            if not line:
                continue
            try:
                out.put(json.loads(line))
            except Exception as exc:  # pragma: no cover - defensive path.
                out.put(exc)
    finally:
        out.put(EOFError("codex app-server stream closed"))


def _process_descendant_pids(root_pid: int) -> set[int]:
    proc_root = Path("/proc")
    if not proc_root.exists():
        return {root_pid}
    children: dict[int, list[int]] = {}
    for stat_path in proc_root.glob("[0-9]*/stat"):
        try:
            text = stat_path.read_text(errors="ignore")
            pid = int(stat_path.parent.name)
            # /proc/<pid>/stat has a comm field in parentheses; ppid follows it.
            after_comm = text.rsplit(")", 1)[1].strip().split()
            ppid = int(after_comm[1])
        except Exception:
            continue
        children.setdefault(ppid, []).append(pid)
    seen: set[int] = set()
    stack = [root_pid]
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend(children.get(pid, []))
    return seen


def _codex_session_jsonl_paths(turn: CodexAppServerGoalTurn) -> list[Path]:
    paths: list[Path] = []
    if turn.work_dir is not None:
        try:
            paths.extend(turn.work_dir.glob("rollout-*.jsonl"))
        except OSError:
            pass
    proc = turn.process
    proc_root = Path("/proc")
    if not proc_root.exists() or proc.pid is None:
        return sorted(set(paths))
    for pid in sorted(_process_descendant_pids(int(proc.pid))):
        fd_dir = proc_root / str(pid) / "fd"
        if not fd_dir.exists():
            continue
        for fd in fd_dir.iterdir():
            try:
                target = Path(os.readlink(fd))
            except OSError:
                continue
            if target.suffix == ".jsonl" and target.name.startswith("rollout-"):
                paths.append(target)
    return sorted(set(paths))


def _send_json(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise CodexAppServerGoalDriverError("codex_app_server_stdin_closed")
    try:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()
    except BrokenPipeError as exc:
        raise CodexAppServerGoalDriverError("codex_app_server_stdin_broken_pipe") from exc


def _wait_for_response(
    proc: subprocess.Popen[str],
    responses: "queue.Queue[dict[str, Any] | Exception]",
    request_id: int,
    *,
    notifications: list[str],
    timeout_sec: float,
    side_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            msg = responses.get(timeout=max(0.1, min(0.5, deadline - time.monotonic())))
        except queue.Empty:
            continue
        if isinstance(msg, EOFError):
            raise CodexAppServerGoalDriverError("codex_app_server_exited_before_response")
        if isinstance(msg, Exception):
            raise CodexAppServerGoalDriverError(str(msg))
        if msg.get("id") == request_id:
            if msg.get("error"):
                raise CodexAppServerGoalDriverError(
                    json.dumps(msg["error"], sort_keys=True)
                )
            result = msg.get("result")
            return result if isinstance(result, dict) else {}
        event_name = _message_event_name(msg)
        if event_name:
            notifications.append(event_name)
            if side_events is not None:
                side_events.append(msg)
            continue
    raise CodexAppServerGoalDriverError(
        f"timed out waiting for app-server response id={request_id}"
    )


def _start_stdio_app_server_process(
    *,
    codex_bin: str,
    work_dir: Path,
) -> tuple[subprocess.Popen[str], "queue.Queue[dict[str, Any] | Exception]"]:
    proc = subprocess.Popen(
        [codex_bin, "app-server", "--listen", "stdio://", "--enable", "goals"],
        cwd=str(work_dir),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    responses: "queue.Queue[dict[str, Any] | Exception]" = queue.Queue()
    assert proc.stdout is not None
    thread = threading.Thread(target=_reader_thread, args=(proc.stdout, responses))
    thread.daemon = True
    thread.start()
    return proc, responses


def _initialize_app_server(
    *,
    proc: subprocess.Popen[str],
    responses: "queue.Queue[dict[str, Any] | Exception]",
    notifications: list[str],
    response_timeout_sec: float,
) -> None:
    initialize = {
        "id": 1,
        "method": "initialize",
        "params": {
            "clientInfo": {
                "name": "loopx_benchmark_host_agent",
                "title": "LoopX Benchmark Host Agent",
                "version": "0.1.0",
            },
            "capabilities": {"experimentalApi": True},
        },
    }
    _send_json(proc, initialize)
    _wait_for_response(
        proc,
        responses,
        1,
        notifications=notifications,
        timeout_sec=response_timeout_sec,
    )
    _send_json(proc, {"method": "initialized", "params": {}})


def _extract_thread_id(result: dict[str, Any]) -> str:
    thread = result.get("thread")
    if isinstance(thread, dict):
        return str(thread.get("id") or thread.get("threadId") or "")
    return str(result.get("threadId") or "")


def _extract_turn_id(result: dict[str, Any]) -> str:
    turn = result.get("turn")
    if isinstance(turn, dict):
        return str(turn.get("id") or "")
    return str(result.get("turnId") or "")


def _extract_turn_status(result: dict[str, Any]) -> str:
    turn = result.get("turn")
    if isinstance(turn, dict):
        return str(turn.get("status") or "")
    return str(result.get("status") or "")


def _extract_goal_status(result: dict[str, Any]) -> str:
    goal = result.get("goal")
    if isinstance(goal, dict):
        return str(goal.get("status") or "")
    return str(result.get("status") or "")


def _notification_turn_id(params: dict[str, Any]) -> str:
    turn = params.get("turn")
    if isinstance(turn, dict):
        return str(turn.get("id") or turn.get("turnId") or "")
    return str(params.get("turnId") or "")


def _notification_thread_id(params: dict[str, Any]) -> str:
    return str(params.get("threadId") or "")


def _message_event_name(msg: dict[str, Any]) -> str:
    method = str(msg.get("method") or "")
    if method:
        return method
    msg_type = str(msg.get("type") or "")
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
    payload_type = str(
        payload.get("type") or payload.get("event") or payload.get("kind") or ""
    )
    if msg_type and payload_type:
        return f"{msg_type}:{payload_type}"
    return msg_type


def _message_event_payload(msg: dict[str, Any]) -> dict[str, Any]:
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    if params:
        return params
    payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
    return payload


def _event_stream_turn_id(messages: list[dict[str, Any]]) -> str:
    for preferred_method in ("turn/started", "item/started", "item/agentMessage/delta"):
        for msg in messages:
            if _message_event_name(msg) != preferred_method:
                continue
            params = _message_event_payload(msg)
            turn_id = _notification_turn_id(params)
            if turn_id:
                return turn_id
    for msg in messages:
        params = _message_event_payload(msg)
        turn_id = _notification_turn_id(params)
        if turn_id:
            return turn_id
    return ""


def _item_text(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    for key in ("text", "content", "message"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            nested = _item_text(value)
            if nested:
                return nested
    value = item.get("content")
    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        return "".join(parts)
    return ""


def _event_payload_text(payload: dict[str, Any]) -> str:
    text = _item_text(payload)
    if text:
        return text
    for key in ("text", "message", "content"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _record_turn_event(
    turn: CodexAppServerGoalTurn,
    msg: dict[str, Any] | Exception,
    *,
    raise_on_error: bool,
) -> bool:
    if isinstance(msg, EOFError):
        turn.stream_eof_observed = True
        returncode = turn.process.poll()
        if returncode is not None:
            turn.process_exit_observed = True
            turn.process_returncode = int(returncode)
        if raise_on_error:
            raise CodexAppServerGoalDriverError(
                "codex app-server exited before turn completion"
            )
        turn.notifications.append("stream/eof")
        return False
    if isinstance(msg, Exception):
        turn.stream_error_observed = True
        if raise_on_error:
            raise CodexAppServerGoalDriverError(str(msg))
        turn.notifications.append("stream/error")
        return False
    method = str(msg.get("method") or "")
    event_name = _message_event_name(msg)
    if event_name:
        turn.notifications.append(event_name)
    params = _message_event_payload(msg)
    if not event_name:
        return False
    msg_turn_id = _notification_turn_id(params)
    msg_thread_id = _notification_thread_id(params)
    if (
        method == "turn/started"
        and msg_turn_id
        and msg_turn_id != turn.turn_id
        and turn.turn_id_source == "turn_start_response"
        and turn.turn_start_response_turn_id_present
        and not turn.turn_event_stream_turn_id_present
    ):
        # Some app-server/model paths return a placeholder turn id in the
        # turn/start response, then stream the real turn id on turn/started.
        # Treat the streamed id as canonical so subsequent item/turn events are
        # not filtered out as belonging to an unrelated turn.
        turn.turn_id = msg_turn_id
        turn.turn_id_source = "event_stream"
        turn.turn_event_stream_turn_id_present = True
    if msg_turn_id and msg_turn_id != turn.turn_id:
        return False
    if msg_thread_id and msg_thread_id != turn.thread_id:
        return False
    if method == "item/agentMessage/delta":
        delta = params.get("delta")
        if isinstance(delta, str) and delta:
            turn._assistant_message_parts.append(delta)
            turn.agent_message_delta_count += 1
        return False
    if event_name == "event_msg:agent_message":
        item_text = _event_payload_text(params)
        if item_text:
            turn._assistant_message_parts.append(item_text)
        turn.agent_message_item_count += 1
        turn.non_user_item_completed_count += 1
        return False
    if event_name == "response_item:message":
        role = str(params.get("role") or "")
        item_text = _event_payload_text(params)
        if role == "user":
            turn.user_message_item_count += 1
            return False
        if item_text:
            turn._assistant_message_parts.append(item_text)
        turn.agent_message_item_count += 1
        turn.non_user_item_completed_count += 1
        return False
    if event_name in {"response_item:function_call", "response_item:function_call_output"}:
        turn.non_user_item_completed_count += 1
        return False
    if event_name == "response_item:reasoning":
        return False
    if event_name == "event_msg:task_started":
        turn.turn_status = "inProgress"
        return False
    if method == "turn/started":
        turn.turn_status = _extract_turn_status(params) or turn.turn_status
        return False
    if method == "item/completed":
        turn.item_completed_count += 1
        item = params.get("item")
        item_type = str(item.get("type") or "") if isinstance(item, dict) else ""
        if item_type == "userMessage":
            turn.user_message_item_count += 1
            return False
        turn.non_user_item_completed_count += 1
        item_text = _item_text(item)
        if item_type == "agentMessage" and item_text:
            turn.agent_message_item_count += 1
            if not turn._assistant_message_parts:
                turn._assistant_message_parts.append(item_text)
        return False
    if method == "turn/completed":
        turn.turn_completed_observed = True
        turn.turn_status = _extract_turn_status(params) or turn.turn_status
        turn.assistant_message = "".join(turn._assistant_message_parts)
        return True
    if event_name in {
        "event_msg:task_complete",
        "event_msg:task_completed",
        "event_msg:turn_completed",
    }:
        turn.turn_completed_observed = True
        turn.turn_status = _extract_turn_status(params) or "completed"
        turn.assistant_message = "".join(turn._assistant_message_parts)
        return True
    if method == "error":
        message = params.get("message") if isinstance(params, dict) else ""
        if raise_on_error:
            raise CodexAppServerGoalDriverError(str(message or "app-server error"))
        turn.notifications.append("turn/error")
    return False


def _observe_codex_session_events(turn: CodexAppServerGoalTurn) -> bool:
    observed_completion = False
    for path in _codex_session_jsonl_paths(turn):
        try:
            current_size = path.stat().st_size
        except OSError:
            continue
        key = str(path)
        offset = int(turn._session_offsets.get(key, 0) or 0)
        if offset > current_size:
            offset = 0
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                handle.seek(offset)
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except Exception:
                        continue
                    turn.session_log_observed = True
                    turn.session_event_count += 1
                    if _message_event_name(msg) in {
                        "event_msg:task_complete",
                        "event_msg:task_completed",
                        "event_msg:turn_completed",
                    }:
                        turn.session_task_complete_observed = True
                    if _record_turn_event(turn, msg, raise_on_error=False):
                        observed_completion = True
                turn._session_offsets[key] = handle.tell()
        except OSError:
            continue
    return observed_completion or bool(turn.turn_completed_observed)


def observe_codex_app_server_goal_turn(
    turn: CodexAppServerGoalTurn,
    *,
    timeout_sec: float = 0.0,
    until_completed: bool = False,
    raise_on_error: bool = False,
) -> bool:
    """Drain app-server turn events without making completion a success gate."""
    if turn._responses is None:
        return bool(turn.turn_completed_observed)
    returncode = turn.process.poll()
    if returncode is not None:
        turn.process_exit_observed = True
        turn.process_returncode = int(returncode)
    if _observe_codex_session_events(turn):
        return True
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while True:
        wait = 0.0
        if timeout_sec > 0:
            wait = max(0.0, min(0.5, deadline - time.monotonic()))
        try:
            msg = turn._responses.get(timeout=wait) if wait else turn._responses.get_nowait()
        except queue.Empty:
            if _observe_codex_session_events(turn):
                return True
            returncode = turn.process.poll()
            if returncode is not None:
                turn.process_exit_observed = True
                turn.process_returncode = int(returncode)
                if not turn.turn_completed_observed:
                    turn.notifications.append("process/exited")
            if not until_completed or time.monotonic() >= deadline:
                return bool(turn.turn_completed_observed)
            continue
        if _record_turn_event(turn, msg, raise_on_error=raise_on_error):
            return True
        if _observe_codex_session_events(turn):
            return True
        if not until_completed and timeout_sec <= 0:
            continue
        if time.monotonic() >= deadline and not until_completed:
            return bool(turn.turn_completed_observed)


def _wait_for_turn_completion(
    turn: CodexAppServerGoalTurn,
    *,
    timeout_sec: float,
) -> None:
    if not observe_codex_app_server_goal_turn(
        turn,
        timeout_sec=timeout_sec,
        until_completed=True,
        raise_on_error=True,
    ):
        raise CodexAppServerGoalDriverError("timed out waiting for turn completion")


def start_codex_app_server_goal_turn(
    *,
    codex_bin: str,
    work_dir: Path,
    objective: str,
    prompt: str,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    approval_policy: str = "never",
    sandbox: str = "danger-full-access",
    response_timeout_sec: float = 30.0,
    wait_for_completion: bool = False,
    turn_timeout_sec: float | None = None,
) -> CodexAppServerGoalTurn:
    work_dir.mkdir(parents=True, exist_ok=True)
    notifications: list[str] = []
    proc, responses = _start_stdio_app_server_process(
        codex_bin=codex_bin,
        work_dir=work_dir,
    )
    try:
        _initialize_app_server(
            proc=proc,
            responses=responses,
            notifications=notifications,
            response_timeout_sec=response_timeout_sec,
        )

        thread_start = {
            "id": 2,
            "method": "thread/start",
            "params": {
                "cwd": str(work_dir),
                "sandbox": sandbox,
                "approvalPolicy": approval_policy,
            },
        }
        _send_json(proc, thread_start)
        thread_result = _wait_for_response(
            proc,
            responses,
            2,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        thread_id = _extract_thread_id(thread_result)
        if not thread_id:
            raise CodexAppServerGoalDriverError("thread/start did not return thread id")

        goal_set = {
            "id": 3,
            "method": "thread/goal/set",
            "params": {
                "threadId": thread_id,
                "objective": objective,
                "status": "active",
            },
        }
        _send_json(proc, goal_set)
        _wait_for_response(
            proc,
            responses,
            3,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )

        goal_get = {
            "id": 4,
            "method": "thread/goal/get",
            "params": {
                "threadId": thread_id,
            },
        }
        _send_json(proc, goal_get)
        goal_result = _wait_for_response(
            proc,
            responses,
            4,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        goal_status = _extract_goal_status(goal_result)
        if goal_status != "active":
            raise CodexAppServerGoalDriverError(
                f"thread/goal/get did not confirm active goal: {goal_status or 'missing'}"
            )

        turn_params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
            "cwd": str(work_dir),
            "approvalPolicy": approval_policy,
        }
        if model_name:
            turn_params["model"] = model_name
        if reasoning_effort:
            turn_params["effort"] = reasoning_effort
        turn_start = {
            "id": 5,
            "method": "turn/start",
            "params": turn_params,
        }
        _send_json(proc, turn_start)
        turn_start_side_events: list[dict[str, Any]] = []
        turn_result = _wait_for_response(
            proc,
            responses,
            5,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
            side_events=turn_start_side_events,
        )
        response_turn_id = _extract_turn_id(turn_result)
        event_stream_turn_id = _event_stream_turn_id(turn_start_side_events)
        turn_id = event_stream_turn_id or response_turn_id
        if not turn_id:
            raise CodexAppServerGoalDriverError("turn/start did not return turn id")

        turn = CodexAppServerGoalTurn(
            process=proc,
            thread_id=thread_id,
            turn_id=turn_id,
            work_dir=work_dir,
            turn_id_source="event_stream" if event_stream_turn_id else "turn_start_response",
            turn_start_response_turn_id_present=bool(response_turn_id),
            turn_event_stream_turn_id_present=bool(event_stream_turn_id),
            next_request_id=6,
            goal_status=goal_status,
            turn_status=_extract_turn_status(turn_result),
            notifications=notifications,
            _responses=responses,
        )
        for event in turn_start_side_events:
            _record_turn_event(turn, event, raise_on_error=False)
        if wait_for_completion:
            _wait_for_turn_completion(
                turn,
                timeout_sec=turn_timeout_sec or response_timeout_sec,
            )
        return turn
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive path.
            proc.kill()
        raise


def _resume_codex_app_server_goal_thread(
    *,
    codex_bin: str,
    work_dir: Path,
    thread_id: str,
    model_name: str | None,
    approval_policy: str,
    sandbox: str,
    response_timeout_sec: float,
) -> tuple[subprocess.Popen[str], "queue.Queue[dict[str, Any] | Exception]", list[str], int]:
    proc, responses = _start_stdio_app_server_process(
        codex_bin=codex_bin,
        work_dir=work_dir,
    )
    notifications: list[str] = []
    try:
        _initialize_app_server(
            proc=proc,
            responses=responses,
            notifications=notifications,
            response_timeout_sec=response_timeout_sec,
        )
        resume_params: dict[str, Any] = {
            "threadId": thread_id,
            "cwd": str(work_dir),
            "approvalPolicy": approval_policy,
            "sandbox": sandbox,
            "excludeTurns": True,
        }
        if model_name:
            resume_params["model"] = model_name
        _send_json(
            proc,
            {
                "id": 2,
                "method": "thread/resume",
                "params": resume_params,
            },
        )
        resume_result = _wait_for_response(
            proc,
            responses,
            2,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        resumed_thread_id = _extract_thread_id(resume_result)
        if resumed_thread_id and resumed_thread_id != thread_id:
            raise CodexAppServerGoalDriverError(
                "codex_app_server_thread_resume_id_mismatch"
            )
        return proc, responses, notifications, 3
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive path.
            proc.kill()
        raise


def _start_followup_turn_on_transport(
    *,
    proc: subprocess.Popen[str],
    responses: "queue.Queue[dict[str, Any] | Exception]",
    request_id: int,
    notifications: list[str],
    thread_id: str,
    work_dir: Path,
    prompt: str,
    model_name: str | None,
    reasoning_effort: str | None,
    objective: str | None,
    approval_policy: str,
    reactivate_inactive_goal: bool,
    response_timeout_sec: float,
) -> tuple[CodexAppServerGoalTurn, int]:
    goal_get = {
        "id": request_id,
        "method": "thread/goal/get",
        "params": {
            "threadId": thread_id,
        },
    }
    _send_json(proc, goal_get)
    goal_result = _wait_for_response(
        proc,
        responses,
        request_id,
        notifications=notifications,
        timeout_sec=response_timeout_sec,
    )
    request_id += 1
    goal_status = _extract_goal_status(goal_result)
    goal_reactivation_attempted = False
    goal_reactivation_succeeded = False
    goal_reactivation_previous_status = ""
    goal_reactivation_result_status = ""
    if goal_status != "active":
        if not reactivate_inactive_goal:
            raise CodexAppServerGoalDriverError(
                f"codex_app_server_goal_not_active:{goal_status or 'missing'}"
            )
        goal_reactivation_attempted = True
        goal_reactivation_previous_status = goal_status or "missing"
        goal_set_params: dict[str, Any] = {
            "threadId": thread_id,
            "status": "active",
        }
        if objective:
            goal_set_params["objective"] = objective
        _send_json(
            proc,
            {
                "id": request_id,
                "method": "thread/goal/set",
                "params": goal_set_params,
            },
        )
        goal_set_result = _wait_for_response(
            proc,
            responses,
            request_id,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        request_id += 1
        goal_reactivation_result_status = _extract_goal_status(goal_set_result)
        goal_get = {
            "id": request_id,
            "method": "thread/goal/get",
            "params": {
                "threadId": thread_id,
            },
        }
        _send_json(proc, goal_get)
        goal_result = _wait_for_response(
            proc,
            responses,
            request_id,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        request_id += 1
        goal_status = _extract_goal_status(goal_result)
        goal_reactivation_result_status = (
            goal_status or goal_reactivation_result_status or "missing"
        )
        goal_reactivation_succeeded = goal_status == "active"
        if goal_status != "active":
            raise CodexAppServerGoalDriverError(
                f"codex_app_server_goal_reactivation_failed:{goal_status or 'missing'}"
            )

    turn_params: dict[str, Any] = {
        "threadId": thread_id,
        "input": [{"type": "text", "text": prompt}],
        "cwd": str(work_dir),
        "approvalPolicy": approval_policy,
    }
    if model_name:
        turn_params["model"] = model_name
    if reasoning_effort:
        turn_params["effort"] = reasoning_effort
    turn_start = {
        "id": request_id,
        "method": "turn/start",
        "params": turn_params,
    }
    _send_json(proc, turn_start)
    turn_start_side_events: list[dict[str, Any]] = []
    turn_result = _wait_for_response(
        proc,
        responses,
        request_id,
        notifications=notifications,
        timeout_sec=response_timeout_sec,
        side_events=turn_start_side_events,
    )
    request_id += 1
    response_turn_id = _extract_turn_id(turn_result)
    event_stream_turn_id = _event_stream_turn_id(turn_start_side_events)
    turn_id = event_stream_turn_id or response_turn_id
    if not turn_id:
        raise CodexAppServerGoalDriverError("codex_app_server_turn_start_id_missing")

    followup = CodexAppServerGoalTurn(
        process=proc,
        thread_id=thread_id,
        turn_id=turn_id,
        work_dir=work_dir,
        turn_id_source="event_stream" if event_stream_turn_id else "turn_start_response",
        turn_start_response_turn_id_present=bool(response_turn_id),
        turn_event_stream_turn_id_present=bool(event_stream_turn_id),
        next_request_id=request_id,
        goal_status=goal_status,
        turn_status=_extract_turn_status(turn_result),
        goal_reactivation_attempted=goal_reactivation_attempted,
        goal_reactivation_succeeded=goal_reactivation_succeeded,
        goal_reactivation_previous_status=goal_reactivation_previous_status,
        goal_reactivation_result_status=goal_reactivation_result_status,
        notifications=notifications,
        _responses=responses,
    )
    for event in turn_start_side_events:
        _record_turn_event(followup, event, raise_on_error=False)
    return followup, request_id


def start_codex_app_server_goal_followup_turn(
    turn: CodexAppServerGoalTurn,
    *,
    codex_bin: str | None = None,
    work_dir: Path,
    prompt: str,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    objective: str | None = None,
    approval_policy: str = "never",
    sandbox: str = "danger-full-access",
    reconnect_if_needed: bool = True,
    reactivate_inactive_goal: bool = False,
    response_timeout_sec: float = 30.0,
    wait_for_completion: bool = False,
    turn_timeout_sec: float | None = None,
) -> CodexAppServerGoalTurn:
    """Start a follow-up turn in the same app-server thread and goal."""

    if turn._responses is None:
        raise CodexAppServerGoalDriverError("codex_app_server_followup_no_response_stream")
    request_id = max(1, int(turn.next_request_id))
    notifications = list(turn.notifications)
    reconnect_reason = ""
    proc = turn.process
    responses = turn._responses
    returncode = proc.poll()
    if returncode is not None:
        turn.process_exit_observed = True
        turn.process_returncode = int(returncode)
        reconnect_reason = "process_exited"
    try:
        if reconnect_reason:
            raise CodexAppServerGoalDriverError("codex_app_server_followup_transport_unavailable")
        followup, request_id = _start_followup_turn_on_transport(
            proc=proc,
            responses=responses,
            request_id=request_id,
            notifications=notifications,
            thread_id=turn.thread_id,
            work_dir=work_dir,
            prompt=prompt,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            objective=objective,
            approval_policy=approval_policy,
            reactivate_inactive_goal=reactivate_inactive_goal,
            response_timeout_sec=response_timeout_sec,
        )
    except CodexAppServerGoalDriverError as exc:
        reconnectable = str(exc) in {
            "codex_app_server_followup_transport_unavailable",
            "codex_app_server_exited_before_response",
            "codex_app_server_stdin_closed",
            "codex_app_server_stdin_broken_pipe",
        }
        if (
            not reconnect_if_needed
            or not reconnectable
            or not codex_bin
            or not turn.thread_id
        ):
            raise
        reconnect_reason = reconnect_reason or str(exc).removeprefix(
            "codex_app_server_"
        )
        proc, responses, notifications, request_id = _resume_codex_app_server_goal_thread(
            codex_bin=codex_bin,
            work_dir=work_dir,
            thread_id=turn.thread_id,
            model_name=model_name,
            approval_policy=approval_policy,
            sandbox=sandbox,
            response_timeout_sec=response_timeout_sec,
        )
        followup, request_id = _start_followup_turn_on_transport(
            proc=proc,
            responses=responses,
            request_id=request_id,
            notifications=notifications,
            thread_id=turn.thread_id,
            work_dir=work_dir,
            prompt=prompt,
            model_name=model_name,
            reasoning_effort=reasoning_effort,
            objective=objective,
            approval_policy=approval_policy,
            reactivate_inactive_goal=reactivate_inactive_goal,
            response_timeout_sec=response_timeout_sec,
        )
        followup.transport_reconnect_attempted = True
        followup.transport_reconnect_succeeded = True
        followup.transport_reconnect_reason = reconnect_reason
    if wait_for_completion:
        _wait_for_turn_completion(
            followup,
            timeout_sec=turn_timeout_sec or response_timeout_sec,
        )
    return followup


def compact_turn_metadata(turn: CodexAppServerGoalTurn) -> dict[str, Any]:
    assistant_message = turn.assistant_message or ""
    return {
        "schema_version": "codex_app_server_goal_turn_driver_v0",
        "thread_id_present": bool(turn.thread_id),
        "goal_get_present": bool(turn.goal_status),
        "goal_status": turn.goal_status,
        "turn_id_present": bool(turn.turn_id),
        "turn_id_source": turn.turn_id_source,
        "turn_start_response_turn_id_present": bool(
            turn.turn_start_response_turn_id_present
        ),
        "turn_event_stream_turn_id_present": bool(
            turn.turn_event_stream_turn_id_present
        ),
        "turn_status": turn.turn_status,
        "turn_completed_observed": bool(turn.turn_completed_observed),
        "agent_message_delta_count": int(turn.agent_message_delta_count),
        "agent_message_item_count": int(turn.agent_message_item_count),
        "item_completed_count": int(turn.item_completed_count),
        "non_user_item_completed_count": int(turn.non_user_item_completed_count),
        "user_message_item_count": int(turn.user_message_item_count),
        "session_log_observed": bool(turn.session_log_observed),
        "session_event_count": int(turn.session_event_count),
        "session_task_complete_observed": bool(turn.session_task_complete_observed),
        "stream_eof_observed": bool(turn.stream_eof_observed),
        "stream_error_observed": bool(turn.stream_error_observed),
        "process_exit_observed": bool(turn.process_exit_observed),
        "process_returncode": turn.process_returncode,
        "transport_reconnect_attempted": bool(turn.transport_reconnect_attempted),
        "transport_reconnect_succeeded": bool(turn.transport_reconnect_succeeded),
        "transport_reconnect_reason": turn.transport_reconnect_reason,
        "goal_reactivation_attempted": bool(turn.goal_reactivation_attempted),
        "goal_reactivation_succeeded": bool(turn.goal_reactivation_succeeded),
        "goal_reactivation_previous_status": turn.goal_reactivation_previous_status,
        "goal_reactivation_result_status": turn.goal_reactivation_result_status,
        "assistant_message_present": bool(assistant_message),
        "assistant_message_chars": len(assistant_message),
        "assistant_message_sha256": sha256(assistant_message.encode()).hexdigest()
        if assistant_message
        else "",
        "notifications": sorted(set(turn.notifications)),
        "raw_transcript_recorded": False,
        "raw_assistant_message_recorded": False,
    }
