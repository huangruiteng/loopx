#!/usr/bin/env python3
"""Minimal Codex app-server Goal turn driver for host-side benchmark agents."""

from __future__ import annotations

import json
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
    next_request_id: int = 6
    goal_status: str = ""
    turn_status: str = ""
    turn_completed_observed: bool = False
    assistant_message: str = ""
    agent_message_delta_count: int = 0
    agent_message_item_count: int = 0
    item_completed_count: int = 0
    notifications: list[str] = field(default_factory=list)
    _responses: "queue.Queue[dict[str, Any] | Exception] | None" = field(
        default=None,
        repr=False,
    )
    _assistant_message_parts: list[str] = field(default_factory=list, repr=False)

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


def _send_json(proc: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if proc.stdin is None:
        raise CodexAppServerGoalDriverError("codex app-server stdin is closed")
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _wait_for_response(
    proc: subprocess.Popen[str],
    responses: "queue.Queue[dict[str, Any] | Exception]",
    request_id: int,
    *,
    notifications: list[str],
    timeout_sec: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            msg = responses.get(timeout=max(0.1, min(0.5, deadline - time.monotonic())))
        except queue.Empty:
            continue
        if isinstance(msg, EOFError):
            raise CodexAppServerGoalDriverError("codex app-server exited before response")
        if isinstance(msg, Exception):
            raise CodexAppServerGoalDriverError(str(msg))
        method = msg.get("method")
        if method:
            notifications.append(str(method))
            continue
        if msg.get("id") == request_id:
            if msg.get("error"):
                raise CodexAppServerGoalDriverError(
                    json.dumps(msg["error"], sort_keys=True)
                )
            result = msg.get("result")
            return result if isinstance(result, dict) else {}
    raise CodexAppServerGoalDriverError(
        f"timed out waiting for app-server response id={request_id}"
    )


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


def _record_turn_event(
    turn: CodexAppServerGoalTurn,
    msg: dict[str, Any] | Exception,
    *,
    raise_on_error: bool,
) -> bool:
    if isinstance(msg, EOFError):
        if raise_on_error:
            raise CodexAppServerGoalDriverError(
                "codex app-server exited before turn completion"
            )
        turn.notifications.append("stream/eof")
        return False
    if isinstance(msg, Exception):
        if raise_on_error:
            raise CodexAppServerGoalDriverError(str(msg))
        turn.notifications.append("stream/error")
        return False
    method = str(msg.get("method") or "")
    if method:
        turn.notifications.append(method)
    params = msg.get("params") if isinstance(msg.get("params"), dict) else {}
    if not method:
        return False
    msg_turn_id = _notification_turn_id(params)
    msg_thread_id = _notification_thread_id(params)
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
    if method == "item/completed":
        turn.item_completed_count += 1
        item = params.get("item")
        item_text = _item_text(item)
        if item_text:
            turn.agent_message_item_count += 1
            if not turn._assistant_message_parts:
                turn._assistant_message_parts.append(item_text)
        return False
    if method == "turn/completed":
        turn.turn_completed_observed = True
        turn.turn_status = _extract_turn_status(params) or turn.turn_status
        turn.assistant_message = "".join(turn._assistant_message_parts)
        return True
    if method == "error":
        message = params.get("message") if isinstance(params, dict) else ""
        if raise_on_error:
            raise CodexAppServerGoalDriverError(str(message or "app-server error"))
        turn.notifications.append("turn/error")
    return False


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
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while True:
        wait = 0.0
        if timeout_sec > 0:
            wait = max(0.0, min(0.5, deadline - time.monotonic()))
        try:
            msg = turn._responses.get(timeout=wait) if wait else turn._responses.get_nowait()
        except queue.Empty:
            if not until_completed or time.monotonic() >= deadline:
                return bool(turn.turn_completed_observed)
            continue
        if _record_turn_event(turn, msg, raise_on_error=raise_on_error):
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
    notifications: list[str] = []
    assert proc.stdout is not None
    thread = threading.Thread(target=_reader_thread, args=(proc.stdout, responses))
    thread.daemon = True
    thread.start()
    try:
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
        turn_result = _wait_for_response(
            proc,
            responses,
            5,
            notifications=notifications,
            timeout_sec=response_timeout_sec,
        )
        turn_id = _extract_turn_id(turn_result)
        if not turn_id:
            raise CodexAppServerGoalDriverError("turn/start did not return turn id")

        turn = CodexAppServerGoalTurn(
            process=proc,
            thread_id=thread_id,
            turn_id=turn_id,
            next_request_id=6,
            goal_status=goal_status,
            turn_status=_extract_turn_status(turn_result),
            notifications=notifications,
            _responses=responses,
        )
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


def start_codex_app_server_goal_followup_turn(
    turn: CodexAppServerGoalTurn,
    *,
    work_dir: Path,
    prompt: str,
    model_name: str | None = None,
    reasoning_effort: str | None = None,
    approval_policy: str = "never",
    response_timeout_sec: float = 30.0,
    wait_for_completion: bool = False,
    turn_timeout_sec: float | None = None,
) -> CodexAppServerGoalTurn:
    """Start a follow-up turn in the same app-server thread and goal."""

    if turn._responses is None:
        raise CodexAppServerGoalDriverError("follow-up turn has no response stream")
    if turn.process.poll() is not None:
        raise CodexAppServerGoalDriverError("codex app-server is not running")
    request_id = max(1, int(turn.next_request_id))
    notifications = turn.notifications

    goal_get = {
        "id": request_id,
        "method": "thread/goal/get",
        "params": {
            "threadId": turn.thread_id,
        },
    }
    _send_json(turn.process, goal_get)
    goal_result = _wait_for_response(
        turn.process,
        turn._responses,
        request_id,
        notifications=notifications,
        timeout_sec=response_timeout_sec,
    )
    request_id += 1
    goal_status = _extract_goal_status(goal_result)
    if goal_status != "active":
        raise CodexAppServerGoalDriverError(
            f"thread/goal/get did not confirm active goal: {goal_status or 'missing'}"
        )

    turn_params: dict[str, Any] = {
        "threadId": turn.thread_id,
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
    _send_json(turn.process, turn_start)
    turn_result = _wait_for_response(
        turn.process,
        turn._responses,
        request_id,
        notifications=notifications,
        timeout_sec=response_timeout_sec,
    )
    request_id += 1
    turn_id = _extract_turn_id(turn_result)
    if not turn_id:
        raise CodexAppServerGoalDriverError("turn/start did not return turn id")

    followup = CodexAppServerGoalTurn(
        process=turn.process,
        thread_id=turn.thread_id,
        turn_id=turn_id,
        next_request_id=request_id,
        goal_status=goal_status,
        turn_status=_extract_turn_status(turn_result),
        notifications=notifications,
        _responses=turn._responses,
    )
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
        "turn_status": turn.turn_status,
        "turn_completed_observed": bool(turn.turn_completed_observed),
        "agent_message_delta_count": int(turn.agent_message_delta_count),
        "agent_message_item_count": int(turn.agent_message_item_count),
        "item_completed_count": int(turn.item_completed_count),
        "assistant_message_present": bool(assistant_message),
        "assistant_message_chars": len(assistant_message),
        "assistant_message_sha256": sha256(assistant_message.encode()).hexdigest()
        if assistant_message
        else "",
        "notifications": sorted(set(turn.notifications)),
        "raw_transcript_recorded": False,
        "raw_assistant_message_recorded": False,
    }
