from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

from .chat import (
    CHAT_AGENT_RESPONSE_SCHEMA_VERSION,
    CHAT_REVIEW_CLOSE_TAG,
    CHAT_REVIEW_OPEN_TAG,
    VisibleResponseStreamFilter,
    parse_agent_response,
)


class CodexChatAgentError(RuntimeError):
    def __init__(self, message: str, *, gate: dict[str, str], error_code: str = "host_gate") -> None:
        super().__init__(message)
        self.gate = gate
        self.error_code = error_code


class CodexChatTimeoutError(CodexChatAgentError):
    pass


class _LegacyModelCatalogSchemaError(RuntimeError):
    pass


def _host_tool_gate(summary: str, next_action: str) -> dict[str, str]:
    return {
        "kind": "host_tool_gate",
        "summary": summary,
        "next_action": next_action,
    }


def _approval_gate(summary: str) -> dict[str, str]:
    return {
        "kind": "approval_gate",
        "summary": summary,
        "next_action": "Review the request in the active host before continuing.",
    }


def _is_legacy_model_catalog_error(value: Any) -> bool:
    # App-server currently reports catalog schema failures only as JSON-RPC
    # prose. Keep this compatibility classifier bound to its three stable
    # schema tokens until the host exposes a typed configuration error code.
    if not isinstance(value, dict):
        return False
    message = str(value.get("message") or "").lower()
    return (
        "model_catalog_json" in message
        and "missing field" in message
        and "base_instructions" in message
    )


def _model_catalog_compatibility_error() -> CodexChatAgentError:
    return CodexChatAgentError(
        "Codex app-server model catalog compatibility retry failed",
        gate=_host_tool_gate(
            "Codex app-server could not load a compatible model catalog for LoopX Chat.",
            "Update the Codex CLI model catalog or remove its legacy override, then retry the session.",
        ),
    )


@contextmanager
def _current_builtin_model_catalog(codex_bin: str) -> Iterator[Path]:
    """Materialize the selected Codex binary's current built-in catalog only."""

    with tempfile.TemporaryDirectory(prefix="loopx-chat-codex-home-") as codex_home:
        env = os.environ.copy()
        env["CODEX_HOME"] = codex_home
        try:
            result = subprocess.run(
                [codex_bin, "debug", "models"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=15,
                check=False,
            )
            payload = json.loads(result.stdout) if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            raise _model_catalog_compatibility_error() from exc
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list) or not models or any(
            not isinstance(model, dict) or not str(model.get("base_instructions") or "").strip()
            for model in models
        ):
            raise _model_catalog_compatibility_error()
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="loopx-chat-model-catalog-",
            suffix=".json",
            delete=False,
        ) as handle:
            json.dump(payload, handle, ensure_ascii=False)
            catalog_path = Path(handle.name)
        try:
            yield catalog_path
        finally:
            catalog_path.unlink(missing_ok=True)


def _reader(stream: Any, messages: "queue.Queue[dict[str, Any] | Exception]") -> None:
    try:
        for line in stream:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception as exc:  # pragma: no cover - defensive transport path.
                messages.put(exc)
                continue
            if isinstance(payload, dict):
                messages.put(payload)
    finally:
        messages.put(EOFError("Codex app-server stream closed"))


def _extract_id(result: dict[str, Any], container: str, fallback: str) -> str:
    nested = result.get(container)
    if isinstance(nested, dict):
        value = nested.get("id") or nested.get(fallback)
        return str(value or "")
    return str(result.get(fallback) or "")


def _event_turn_id(message: dict[str, Any]) -> str:
    params = message.get("params")
    if not isinstance(params, dict):
        return ""
    turn = params.get("turn")
    if isinstance(turn, dict):
        return str(turn.get("id") or turn.get("turnId") or "")
    return str(params.get("turnId") or "")


def _event_thread_id(message: dict[str, Any]) -> str:
    params = message.get("params")
    return str(params.get("threadId") or "") if isinstance(params, dict) else ""


def _agent_item_text(message: dict[str, Any]) -> str:
    params = message.get("params")
    if not isinstance(params, dict):
        return ""
    item = params.get("item")
    if not isinstance(item, dict) or item.get("type") != "agentMessage":
        return ""
    content = item.get("content")
    if isinstance(content, list):
        return "".join(
            str(part.get("text") or "")
            for part in content
            if isinstance(part, dict) and part.get("type") in {"text", "outputText"}
        )
    return str(item.get("text") or "")


def _turn_prompt(
    user_message: str,
    *,
    context_summary: str = "",
    execution_mode: bool = False,
) -> str:
    envelope = {
        "schema_version": CHAT_AGENT_RESPONSE_SCHEMA_VERSION,
        "message": "Short answer for the operator.",
        "proposals": [
            {
                "kind": "todo",
                "text": "One bounded Todo.",
                "priority": "P1",
                "rationale": "Why this is the next safe step.",
            }
        ],
        "protected_action": None,
        "gate": None,
    }
    role = (
        "You are the execution agent for a confirmed LoopX Task. Work only from the project root. "
        "Execute the operator task now. Inspect the repository, edit files, and run focused validation as needed. "
        "Use the existing branch and worktree. Commit or push only when the operator task explicitly requests it. "
        "Keep changes bounded to the confirmed Task and stop at any permission, identity, or destructive-operation gate. "
        if execution_mode
        else
        "You are the planning agent inside LoopX Chat. Work only from the project root. "
    )
    planning_limits = (
        "Use read-only repository commands only when the operator explicitly asks for repository facts or when evidence is required to answer accurately. "
        "Do not use tools for ordinary conversation, exact-wording requests, or status questions that can be answered from the supplied LoopX context. "
        "Do not edit files, mutate LoopX state, create commits, send messages, or request elevated access. "
        if not execution_mode
        else ""
    )
    protected_action_contract = (
        "For a protected operation (merge, release, deploy, delete, or payment), interpret the operator's semantic intent. "
        "Set protected_action only when the dominant request is to perform exactly one operation now and the operator supplied a concrete target. "
        "Use only operation, target, and summary; copy the target from the operator instead of inventing or resolving it. "
        "Discussion, quotation, hypotheticals, exact-wording requests, negation, targetless requests, and compound operations must use protected_action=null; ask a useful clarification in message when needed. "
        "A protected_action is only an untrusted proposal for LoopX typed preview and never authority to execute. "
        if not execution_mode
        else "This is already a confirmed execution turn, so protected_action must be null. "
    )
    return (
        role
        + "The operator message below is the current task. Answer it directly and do not replace it "
        + "with an autonomous project task. "
        + planning_limits
        + "When the operator requests a durable Goal, Todo, Agent binding, heartbeat, monitor, gate, or correction change, "
        "describe the bounded proposal clearly so LoopX can route it through typed preview and explicit apply. "
        + protected_action_contract
        + "Never claim the change has been written without a verified control-plane receipt. "
        "If you encounter an identity, approval, or host-tool gate, stop and describe it in gate. "
        "Reply in Chinese unless the operator asks for another language. Keep proposals bounded and reviewable. "
        "Do not expose chain-of-thought, tool narration, intended steps, or scratch work. "
        "First write the complete operator-facing answer as ordinary text. Start with the conclusion, "
        "use short sentences or lines so the answer can stream, and include at most five actionable items. "
        "Then append exactly one machine-readable envelope whose message field repeats that complete answer. "
        "protected_action must be null or an object shaped as "
        '{"operation":"merge|release|deploy|delete|payment","target":"user-stated target","summary":"short public-safe proposal"}. '
        "Do not write anything after the closing tag. Use these tags and shape:\n"
        f"{CHAT_REVIEW_OPEN_TAG}{json.dumps(envelope, ensure_ascii=False)}{CHAT_REVIEW_CLOSE_TAG}\n\n"
        + (f"LoopX context (supporting context only):\n{context_summary.strip()}\n\n" if context_summary.strip() else "")
        + f"Operator user message:\n{user_message.strip()}"
    )


@dataclass
class CodexChatAgentSession:
    process: subprocess.Popen[str]
    messages: "queue.Queue[dict[str, Any] | Exception]"
    thread_id: str
    work_dir: Path
    context_summary: str = ""
    execution_mode: bool = False
    response_timeout_sec: float = 30.0
    idle_timeout_sec: float = 180.0
    hard_timeout_sec: float = 900.0
    next_request_id: int = 5
    current_turn_id: str = ""
    model_catalog_compatibility_applied: bool = False
    _pending_events: "queue.Queue[dict[str, Any]]" = field(default_factory=queue.Queue, repr=False)
    _response_waiters: dict[int, "queue.Queue[dict[str, Any]]"] = field(
        default_factory=dict,
        repr=False,
    )
    _write_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _request_id_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _response_waiters_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _message_dispatch_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def start(
        cls,
        *,
        codex_bin: str,
        work_dir: Path,
        goal_id: str,
        objective: str,
        response_timeout_sec: float = 30.0,
        idle_timeout_sec: float = 180.0,
        hard_timeout_sec: float = 900.0,
        resume_thread_id: str | None = None,
        execution_mode: bool = False,
        codex_home: Path | None = None,
        _compatibility_catalog_path: Path | None = None,
    ) -> "CodexChatAgentSession":
        resolved = shutil.which(codex_bin)
        if not resolved:
            raise CodexChatAgentError(
                "Codex executable is unavailable",
                gate=_host_tool_gate(
                    "Codex host tool is unavailable for LoopX Chat.",
                    "Install or select a working Codex CLI, then start LoopX Chat again.",
                ),
            )
        root = work_dir.resolve()
        # Pin the host store explicitly, including compatibility retries. Never
        # redirect an existing thread by inheriting a different launch context.
        runtime_home = (codex_home or Path(os.environ.get("CODEX_HOME") or "~/.codex")).expanduser().resolve()
        runtime_env = os.environ.copy()
        runtime_env["CODEX_HOME"] = str(runtime_home)
        command = [resolved, "app-server"]
        if _compatibility_catalog_path is not None:
            command.extend(
                [
                    "-c",
                    f"model_catalog_json={json.dumps(str(_compatibility_catalog_path))}",
                ]
            )
        command.extend(["--listen", "stdio://"])
        try:
            process = subprocess.Popen(
                command,
                cwd=str(root),
                env=runtime_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise CodexChatAgentError(
                "Codex app-server could not start",
                gate=_host_tool_gate(
                    "Codex app-server could not start for LoopX Chat.",
                    "Verify the Codex CLI installation and app-server support.",
                ),
            ) from exc

        messages: "queue.Queue[dict[str, Any] | Exception]" = queue.Queue()
        assert process.stdout is not None
        reader = threading.Thread(target=_reader, args=(process.stdout, messages), daemon=True)
        reader.start()
        session = cls(
            process=process,
            messages=messages,
            thread_id="",
            work_dir=root,
            context_summary=f"{goal_id}: {objective}".strip(),
            response_timeout_sec=response_timeout_sec,
            idle_timeout_sec=idle_timeout_sec,
            hard_timeout_sec=hard_timeout_sec,
            execution_mode=execution_mode,
            model_catalog_compatibility_applied=_compatibility_catalog_path is not None,
        )
        try:
            session._request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "loopx_chat",
                        "title": "LoopX Chat",
                        "version": "0.1.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
                request_id=1,
            )
            session._notify("initialized", {})
            thread_result = session._request(
                "thread/resume" if resume_thread_id else "thread/start",
                {
                    **({"threadId": resume_thread_id, "excludeTurns": True} if resume_thread_id else {}),
                    "cwd": str(root),
                    "sandbox": "workspace-write" if execution_mode else "read-only",
                    "approvalPolicy": "never",
                },
                request_id=2,
            )
            session.thread_id = _extract_id(thread_result, "thread", "threadId")
            if not session.thread_id:
                raise session._runtime_error("Codex app-server did not return a thread id.")
            if resume_thread_id and session.thread_id != resume_thread_id:
                raise session._runtime_error("Codex app-server resumed an unexpected thread.")
            # Chat keeps its Goal binding in LoopX's local Session state and supplies
            # that public-safe context in each Turn prompt. Codex Goal mode is reserved
            # for autonomous execution; enabling it here causes conversational messages
            # to be treated as continuation ticks instead of the current user task.
            session.next_request_id = 3
            return session
        except _LegacyModelCatalogSchemaError as exc:
            session.close()
            if _compatibility_catalog_path is not None:
                raise _model_catalog_compatibility_error() from exc
            with _current_builtin_model_catalog(resolved) as catalog_path:
                return cls.start(
                    codex_bin=resolved,
                    work_dir=root,
                    goal_id=goal_id,
                    objective=objective,
                    response_timeout_sec=response_timeout_sec,
                    idle_timeout_sec=idle_timeout_sec,
                    hard_timeout_sec=hard_timeout_sec,
                    resume_thread_id=resume_thread_id,
                    execution_mode=execution_mode,
                    codex_home=runtime_home,
                    _compatibility_catalog_path=catalog_path,
                )
        except Exception:
            session.close()
            raise

    def _runtime_error(self, summary: str) -> CodexChatAgentError:
        return CodexChatAgentError(
            summary,
            gate=_host_tool_gate(
                summary,
                "Check the Codex app-server host capability, then retry the session.",
            ),
        )

    def _write(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise self._runtime_error("Codex app-server input stream is closed.")
        try:
            with self._write_lock:
                self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
                self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise self._runtime_error("Codex app-server input stream closed unexpectedly.") from exc

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._write({"method": method, "params": params})

    def _next_message(self, *, deadline: float) -> dict[str, Any]:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise self._runtime_error("Codex app-server timed out.")
            try:
                message = self.messages.get(timeout=min(0.5, remaining))
            except queue.Empty:
                continue
            if isinstance(message, EOFError):
                raise self._runtime_error("Codex app-server closed before completing the request.")
            if isinstance(message, Exception):
                raise self._runtime_error("Codex app-server returned an unreadable response.")
            return message

    def _route_response(self, message: dict[str, Any]) -> bool:
        response_id = message.get("id")
        if not isinstance(response_id, int):
            return False
        with self._response_waiters_lock:
            waiter = self._response_waiters.get(response_id)
        if waiter is None:
            return False
        waiter.put(message)
        return True

    def _next_event(self, *, deadline: float) -> dict[str, Any]:
        while True:
            with self._message_dispatch_lock:
                try:
                    return self._pending_events.get_nowait()
                except queue.Empty:
                    pass
                message = self._next_message(deadline=deadline)
                if self._route_response(message):
                    continue
                return message

    def _check_server_gate(self, message: dict[str, Any]) -> None:
        if message.get("id") is not None and message.get("method"):
            raise CodexChatAgentError(
                "Codex app-server requested host approval",
                gate=_approval_gate("Codex requested host approval during a read-only chat turn."),
            )

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        request_id: int | None = None,
    ) -> dict[str, Any]:
        if request_id is None:
            with self._request_id_lock:
                request_id = self.next_request_id
                self.next_request_id += 1
        waiter: "queue.Queue[dict[str, Any]]" = queue.Queue(maxsize=1)
        with self._response_waiters_lock:
            self._response_waiters[request_id] = waiter
        try:
            self._write({"id": request_id, "method": method, "params": params})
            deadline = time.monotonic() + self.response_timeout_sec
            while True:
                try:
                    message = waiter.get_nowait()
                except queue.Empty:
                    with self._message_dispatch_lock:
                        try:
                            message = waiter.get_nowait()
                        except queue.Empty:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise self._runtime_error("Codex app-server timed out.")
                            try:
                                raw = self.messages.get(timeout=min(0.1, remaining))
                            except queue.Empty:
                                continue
                            if isinstance(raw, EOFError):
                                raise self._runtime_error(
                                    "Codex app-server closed before completing the request."
                                )
                            if isinstance(raw, Exception):
                                raise self._runtime_error(
                                    "Codex app-server returned an unreadable response."
                                )
                            message = raw
                            if (
                                message.get("id") != request_id
                                and self._route_response(message)
                            ):
                                continue
                            if message.get("id") != request_id:
                                self._check_server_gate(message)
                                self._pending_events.put(message)
                                continue
                if message.get("id") == request_id:
                    if message.get("error"):
                        if method in {"thread/start", "thread/resume"} and _is_legacy_model_catalog_error(
                            message.get("error")
                        ):
                            raise _LegacyModelCatalogSchemaError
                        raise self._runtime_error(f"Codex app-server rejected {method}.")
                    result = message.get("result")
                    return result if isinstance(result, dict) else {}
                raise self._runtime_error("Codex app-server returned an unexpected response.")
        finally:
            with self._response_waiters_lock:
                self._response_waiters.pop(request_id, None)

    def steer(self, user_message: str, *, expected_turn_id: str) -> str:
        """Inject one user message into the exact active Codex Turn."""

        text = " ".join(str(user_message or "").split())
        selected_turn_id = str(expected_turn_id or "").strip()
        if not text or not selected_turn_id:
            raise ValueError("steering requires a message and expected active turn id")
        result = self._request(
            "turn/steer",
            {
                "threadId": self.thread_id,
                "expectedTurnId": selected_turn_id,
                "input": [
                    {
                        "type": "text",
                        "text": _turn_prompt(
                            text,
                            context_summary=self.context_summary,
                            execution_mode=self.execution_mode,
                        ),
                    }
                ],
            },
        )
        turn_id = _extract_id(result, "turn", "turnId")
        if turn_id != selected_turn_id:
            raise self._runtime_error("Codex app-server steered an unexpected turn.")
        return turn_id

    def interrupt(self, turn_id: str | None = None) -> None:
        selected_turn_id = str(turn_id or self.current_turn_id or "")
        if not selected_turn_id:
            return
        with self._request_id_lock:
            request_id = self.next_request_id
            self.next_request_id += 1
        self._write(
            {
                "id": request_id,
                "method": "turn/interrupt",
                "params": {"threadId": self.thread_id, "turnId": selected_turn_id},
            }
        )

    def send(
        self,
        user_message: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        text = " ".join(str(user_message or "").split())
        if not text:
            raise ValueError("user message is required")
        with self._request_id_lock:
            request_id = self.next_request_id
            self.next_request_id += 1
        turn_input: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": _turn_prompt(
                    text,
                    context_summary=self.context_summary,
                    execution_mode=self.execution_mode,
                ),
            }
        ]
        for attachment in attachments or []:
            image_url = str(attachment.get("data_url") or "")
            if image_url:
                turn_input.append({"type": "image", "url": image_url, "detail": "auto"})
        turn_result = self._request(
            "turn/start",
            {
                "threadId": self.thread_id,
                "input": turn_input,
                "cwd": str(self.work_dir),
                "approvalPolicy": "never",
            },
            request_id=request_id,
        )
        turn_id = _extract_id(turn_result, "turn", "turnId")
        self.current_turn_id = turn_id
        if on_event:
            on_event("turn.started", {"upstream_turn_id": turn_id})
        parts: list[str] = []
        display_filter = VisibleResponseStreamFilter(protected_paths=[self.work_dir])
        visible_delta_count = 0
        started_at = time.monotonic()
        last_activity_at = started_at
        while True:
            now = time.monotonic()
            if now - started_at >= self.hard_timeout_sec:
                raise self._timeout_error("hard_timeout", "Codex Chat turn reached its hard time limit.")
            if now - last_activity_at >= self.idle_timeout_sec:
                raise self._timeout_error("idle_timeout", "Codex Chat turn stopped producing activity.")
            deadline = min(started_at + self.hard_timeout_sec, last_activity_at + self.idle_timeout_sec)
            try:
                message = self._next_event(deadline=deadline)
            except CodexChatAgentError:
                now = time.monotonic()
                if now - started_at >= self.hard_timeout_sec:
                    raise self._timeout_error(
                        "hard_timeout",
                        "Codex Chat turn reached its hard time limit.",
                    )
                if now - last_activity_at >= self.idle_timeout_sec:
                    raise self._timeout_error(
                        "idle_timeout",
                        "Codex Chat turn stopped producing activity.",
                    )
                raise
            last_activity_at = time.monotonic()
            self._check_server_gate(message)
            event_thread_id = _event_thread_id(message)
            event_turn_id = _event_turn_id(message)
            if event_thread_id and event_thread_id != self.thread_id:
                continue
            if message.get("method") == "turn/started" and event_turn_id:
                turn_id = event_turn_id
                self.current_turn_id = turn_id
            if event_turn_id and turn_id and event_turn_id != turn_id:
                continue
            method = str(message.get("method") or "")
            params = message.get("params")
            if on_event:
                phase = {
                    "turn/started": "正在连接 Agent",
                    "item/started": "正在读取 Goal 上下文",
                    "item/completed": "已完成一项检查",
                    "turn/completed": "正在整理回答",
                }.get(method)
                if phase:
                    on_event("agent.phase", {"label": phase, "method": method})
            if method == "item/agentMessage/delta" and isinstance(params, dict):
                delta = params.get("delta")
                if isinstance(delta, str):
                    parts.append(delta)
                    visible = display_filter.feed(delta)
                    if visible and on_event:
                        visible_delta_count += 1
                        on_event("answer.delta", {"text": visible})
            elif method == "item/completed":
                item_text = _agent_item_text(message)
                if item_text and not parts:
                    parts.append(item_text)
                    visible = display_filter.feed(item_text)
                    if visible and on_event:
                        visible_delta_count += 1
                        on_event("answer.delta", {"text": visible})
            elif method == "turn/completed":
                turn = params.get("turn") if isinstance(params, dict) else None
                turn_status = str(turn.get("status") or "") if isinstance(turn, dict) else ""
                if turn_status == "failed":
                    raise self._runtime_error("Codex app-server reported a terminal turn failure.")
                if turn_status == "interrupted":
                    raise CodexChatAgentError(
                        "Codex app-server reported an interrupted turn.",
                        error_code="interrupted",
                        gate=_host_tool_gate(
                            "The Codex Chat turn was interrupted.",
                            "Send a new message to continue in the same session.",
                        ),
                    )
                break
            elif method == "error":
                if isinstance(params, dict) and params.get("willRetry") is True:
                    if on_event:
                        on_event(
                            "agent.phase",
                            {"label": "Codex 正在重试", "method": method},
                        )
                    continue
                raise self._runtime_error("Codex app-server reported a turn error.")
        visible_tail = display_filter.finish()
        if visible_tail and on_event:
            visible_delta_count += 1
            on_event("answer.delta", {"text": visible_tail})
        raw_response = "".join(parts)
        response = parse_agent_response(raw_response, protected_paths=[self.work_dir])
        if on_event:
            if CHAT_REVIEW_OPEN_TAG not in raw_response or CHAT_REVIEW_CLOSE_TAG not in raw_response:
                on_event("protocol.warning", {"error_code": "missing_review_envelope"})
            if visible_delta_count == 0:
                on_event("answer.delta", {"text": str(response.get("message") or "")})
            on_event("answer.final", {"response": response})
        self.current_turn_id = ""
        return response

    def _timeout_error(self, error_code: str, summary: str) -> CodexChatTimeoutError:
        return CodexChatTimeoutError(
            summary,
            error_code=error_code,
            gate=_host_tool_gate(summary, "Interrupt the turn or retry in the same session."),
        )

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=2)

    def __enter__(self) -> "CodexChatAgentSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
