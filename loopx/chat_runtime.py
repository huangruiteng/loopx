"""Runtime-neutral orchestration for durable LoopX Chat sessions."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Any, Callable, Protocol

from .chat_manager import (
    MANAGER_AGENT_GOAL_ID, MANAGER_AGENT_OBJECTIVE, MANAGER_CONTEXT_VERSION,
    is_manager_channel, manager_model_config, manager_workspace, manager_skill_text,
)
from .chat_acp import ACPStdioAdapter
from .chat_agent import CodexChatAgentError, CodexChatAgentSession, CodexChatTimeoutError
from .chat_endpoints import AgentEndpointRegistry
from .kiro_cli_goal_mode import (
    KIRO_CLI_BIN,
    KIRO_CLI_CHAT_ADAPTER_KIND,
    KIRO_CLI_CHAT_AGENT_ID,
    KIRO_CLI_CHAT_DISPLAY_NAME,
    kiro_cli_chat_command,
)
from .chat_store import (
    CHAT_SESSION_MODE_ATTACHED,
    TERMINAL_TURN_STATES,
    ChatSessionStore,
    utc_now,
)
from .chat_providers import ClaudeCodeAdapter, direct_model_from_environment


EventSink = Callable[[str, dict[str, Any]], None]
class ChatRuntimeAdapter(Protocol):
    @property
    def upstream_thread_id(self) -> str: ...

    def capabilities(self) -> dict[str, Any]: ...
    def start_turn(self, message: str, event_sink: EventSink) -> dict[str, Any]: ...
    def interrupt_turn(self, turn_id: str | None = None) -> None: ...
    def close_session(self) -> None: ...
    def healthcheck(self) -> bool: ...


@dataclass
class CodexAppServerAdapter:
    session: CodexChatAgentSession

    @property
    def upstream_thread_id(self) -> str:
        return self.session.thread_id

    @classmethod
    def start(
        cls,
        *,
        codex_bin: str,
        work_dir: Path,
        goal_id: str,
        objective: str,
        resume_thread_id: str | None = None,
        startup_timeout_sec: float = 30.0,
        idle_timeout_sec: float = 180.0,
        hard_timeout_sec: float = 900.0,
        execution_mode: bool = False,
        codex_home: Path | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        dynamic_tools: list[dict[str, Any]] | None = None,
    ) -> "CodexAppServerAdapter":
        return cls(
            CodexChatAgentSession.start(
                codex_bin=codex_bin,
                work_dir=work_dir,
                goal_id=goal_id,
                objective=objective,
                response_timeout_sec=startup_timeout_sec,
                idle_timeout_sec=idle_timeout_sec,
                hard_timeout_sec=hard_timeout_sec,
                execution_mode=execution_mode,
                resume_thread_id=resume_thread_id,
                codex_home=codex_home,
                model=model,
                reasoning_effort=reasoning_effort,
                dynamic_tools=dynamic_tools,
            )
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "adapter_kind": "codex_app_server",
            "streaming": True,
            "resume": True,
            "interrupt": True,
            "steering": True,
        }

    def start_turn(self, message: str, event_sink: EventSink) -> dict[str, Any]:
        return self.session.send(message, on_event=event_sink)

    def steer_turn(self, message: str, expected_turn_id: str) -> str:
        return self.session.steer(message, expected_turn_id=expected_turn_id)

    def start_turn_with_attachments(
        self,
        message: str,
        event_sink: EventSink,
        attachments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self.session.send(message, attachments=attachments, on_event=event_sink)

    def interrupt_turn(self, turn_id: str | None = None) -> None:
        self.session.interrupt(turn_id)

    def close_session(self) -> None:
        self.session.close()

    def healthcheck(self) -> bool:
        return self.session.process.poll() is None


class _TurnEventBuffer:
    """Keep live events readable in memory and checkpoint them in bounded batches."""

    def __init__(
        self,
        *,
        store: ChatSessionStore,
        session_id: str,
        turn_id: str,
        event_flush_interval_sec: float = 0.05,
        metadata_checkpoint_interval_sec: float = 0.5,
    ) -> None:
        self.store = store
        self.session_id = session_id
        self.turn_id = turn_id
        self.event_flush_interval_sec = event_flush_interval_sec
        self.metadata_checkpoint_interval_sec = metadata_checkpoint_interval_sec
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.closed = False
        self.last_checkpoint_at = time.monotonic()
        turn = store.load_turn(session_id, turn_id) or {}
        self.progress: dict[str, Any] = {
            "last_activity_at": turn.get("last_activity_at") or utc_now(),
            "first_event_at": turn.get("first_event_at"),
            "delta_count": int(turn.get("delta_count") or 0),
        }
        self.metadata_dirty = False
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()

    def _flush_loop(self) -> None:
        while not self.stop_event.wait(self.event_flush_interval_sec):
            try:
                self.store.flush_events(self.session_id, self.turn_id)
            except Exception:
                # Pending rows remain queued. The owning Turn retries during close,
                # where a persistent failure is handled by the normal runtime path.
                return

    def _checkpoint_locked(self, *, force: bool = False) -> None:
        if not self.metadata_dirty:
            return
        now = time.monotonic()
        if not force and now - self.last_checkpoint_at < self.metadata_checkpoint_interval_sec:
            return
        changes = dict(self.progress)
        if not changes.get("first_event_at"):
            changes.pop("first_event_at", None)
        self.store.update_turn(
            self.session_id,
            self.turn_id,
            expected_statuses={"starting", "running"} if "status" in changes else None,
            **changes,
        )
        self.store.update_session(
            self.session_id,
            last_activity_at=str(changes["last_activity_at"]),
        )
        self.metadata_dirty = False
        self.last_checkpoint_at = now

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        with self.lock:
            if self.closed:
                return
            now = utc_now()
            self.progress["last_activity_at"] = now
            if not self.progress.get("first_event_at"):
                self.progress["first_event_at"] = now
            if kind in {"answer.delta", "assistant.delta"}:
                self.progress["delta_count"] = int(self.progress.get("delta_count") or 0) + 1
            if kind == "turn.started":
                self.progress["status"] = "running"
                self.progress["upstream_turn_id"] = payload.get("upstream_turn_id")
            self.metadata_dirty = True
            self.store.append_event(
                self.session_id,
                self.turn_id,
                kind=kind,
                payload=payload,
                buffered=True,
            )
            self._checkpoint_locked(force=kind == "turn.started")

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
        self.stop_event.set()
        self.flush_thread.join(timeout=max(1.0, self.event_flush_interval_sec * 4))
        with self.lock:
            self.store.flush_events(self.session_id, self.turn_id)
            self._checkpoint_locked(force=True)


class ChatRuntimeController:
    def __init__(
        self,
        *,
        store: ChatSessionStore,
        codex_bin: str,
        claude_bin: str = "claude",
        kiro_cli_bin: str = KIRO_CLI_BIN,
        startup_timeout_sec: float = 30.0,
        idle_timeout_sec: float = 180.0,
        hard_timeout_sec: float = 900.0,
        endpoint_registry: AgentEndpointRegistry | None = None,
        registry_path: Path | None = None,
        manager_scope_resolver: Callable[[dict[str, Any]], list[str] | None] | None = None,
    ) -> None:
        self.store = store
        self.registry_path = registry_path
        self.manager_scope_resolver = manager_scope_resolver
        self.codex_bin = codex_bin
        # Capture once; the service's startup environment is not session identity.
        self.codex_home = Path(
            os.environ.get("LOOPX_CHAT_CODEX_HOME")
            or os.environ.get("CODEX_HOME")
            or "~/.codex"
        ).expanduser().resolve()
        self.claude_bin = claude_bin
        self.kiro_cli_bin = kiro_cli_bin
        self.startup_timeout_sec = startup_timeout_sec
        self.idle_timeout_sec = idle_timeout_sec
        self.hard_timeout_sec = hard_timeout_sec
        self.endpoint_registry = endpoint_registry or AgentEndpointRegistry(store.root)
        self.adapters: dict[str, ChatRuntimeAdapter] = {}
        self.cancelled_turns: set[tuple[str, str]] = set()
        self.turn_event_buffers: dict[tuple[str, str], _TurnEventBuffer] = {}
        self.turn_done_events: dict[tuple[str, str], threading.Event] = {}
        self.lock = threading.RLock()
        self.session_open_locks: dict[tuple[str, str, str], threading.Lock] = {}
        self.session_adapter_locks: dict[str, threading.Lock] = {}
        self.session_queue_workers: set[str] = set()
        self.session_queue_threads: dict[str, threading.Thread] = {}
        self.closed = threading.Event()

    def capabilities(self) -> list[dict[str, Any]]:
        builtins = [
            {
                "agent_id": "codex",
                "display_name": "Codex",
                "adapter_kind": "codex_app_server",
                "available": bool(shutil.which(self.codex_bin)),
                "streaming": True,
                "resume": True,
                "interrupt": True,
                "tool_calls": True,
                "trust_scope": "read_only",
                "source": "builtin",
            },
            {
                "agent_id": "claude-code",
                "display_name": "Claude Code",
                "adapter_kind": "claude_code_cli",
                "available": bool(shutil.which(self.claude_bin)),
                "streaming": True,
                "resume": True,
                "interrupt": True,
                "tool_calls": True,
                "trust_scope": "read_only",
                "source": "builtin",
            },
            {
                # Kiro CLI ships an ACP stdio agent (`kiro-cli acp`), so it is
                # reachable through the existing ACP adapter without a new
                # transport. It is a built-in row rather than something the
                # owner must hand-register, because LoopX already owns the
                # host's facts; `available` stays a live PATH probe so an
                # uninstalled host renders as needing configuration instead of
                # failing at session open.
                "agent_id": KIRO_CLI_CHAT_AGENT_ID,
                "display_name": KIRO_CLI_CHAT_DISPLAY_NAME,
                "adapter_kind": KIRO_CLI_CHAT_ADAPTER_KIND,
                "available": bool(shutil.which(self.kiro_cli_bin)),
                "streaming": True,
                "resume": True,
                "interrupt": True,
                "tool_calls": True,
                # Kiro owns its persistent permission rules. LoopX cancels
                # interactive ACP permission requests, but cannot turn an
                # existing host-level `allow` rule into a read-only sandbox.
                "trust_scope": "workspace_write",
                "source": "builtin",
            },
            {
                "agent_id": "anthropic-api",
                "display_name": "Claude API",
                "adapter_kind": "anthropic_messages_api",
                "available": bool(os.environ.get("ANTHROPIC_API_KEY", "").strip()),
                "streaming": False,
                "resume": True,
                "interrupt": False,
                "tool_calls": True,
                "trust_scope": "read_only",
                "source": "builtin",
            },
            {
                "agent_id": "openai-api",
                "display_name": "OpenAI API",
                "adapter_kind": "openai_messages_api",
                "available": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
                "streaming": False,
                "resume": True,
                "interrupt": False,
                "tool_calls": True,
                "trust_scope": "read_only",
                "source": "builtin",
            },
        ]
        return [*builtins, *(endpoint.public_summary() for endpoint in self.endpoint_registry.list())]

    @staticmethod
    def _managed_upstream_mode(session: dict[str, Any]) -> str:
        return (
            "chat"
            if session.get("agent_id") == "codex"
            else str(session.get("upstream_mode") or "default")
        )

    def _start_adapter(
        self,
        *,
        agent_id: str,
        work_dir: Path,
        goal_id: str,
        objective: str,
        resume_thread_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
        execution_mode: bool = False,
    ) -> ChatRuntimeAdapter:
        if agent_id == "codex":
            from .capabilities.manager_context.inspection import READ_TOOL
            history_context = ""
            if history:
                history_lines = [
                    f"{item.get('role', 'user')}: {str(item.get('content') or '').strip()}"
                    for item in history[-12:]
                    if str(item.get("content") or "").strip()
                ]
                if history_lines:
                    history_context = "\nPrevious visible Chat messages:\n" + "\n".join(history_lines)
            return CodexAppServerAdapter.start(
                codex_bin=self.codex_bin,
                codex_home=self.codex_home,
                work_dir=work_dir,
                goal_id=goal_id,
                objective=f"{objective}{history_context}" + (
                    "\n" + manager_skill_text() if goal_id == MANAGER_AGENT_GOAL_ID else ""
                ),
                resume_thread_id=resume_thread_id,
                startup_timeout_sec=self.startup_timeout_sec,
                idle_timeout_sec=self.idle_timeout_sec,
                hard_timeout_sec=self.hard_timeout_sec,
                execution_mode=execution_mode,
                **(manager_model_config() if goal_id == MANAGER_AGENT_GOAL_ID and not execution_mode else {}),
                **({"dynamic_tools": [READ_TOOL]} if goal_id == MANAGER_AGENT_GOAL_ID and not execution_mode else {}),
            )
        if agent_id == "claude-code":
            return ClaudeCodeAdapter.start(
                claude_bin=self.claude_bin,
                work_dir=work_dir,
                resume_thread_id=resume_thread_id,
                tool_scope="read_only",
                context_summary=f"{goal_id}: {objective}".strip(),
            )
        if agent_id in {"anthropic-api", "openai-api"}:
            return direct_model_from_environment(
                provider="anthropic" if agent_id == "anthropic-api" else "openai",
                work_dir=work_dir,
                session_id=resume_thread_id,
                history=history,
            )
        if agent_id == KIRO_CLI_CHAT_AGENT_ID:
            return ACPStdioAdapter.start(
                command=kiro_cli_chat_command(self.kiro_cli_bin),
                work_dir=work_dir,
                resume_thread_id=resume_thread_id,
                startup_timeout_sec=self.startup_timeout_sec,
                idle_timeout_sec=self.idle_timeout_sec,
                hard_timeout_sec=self.hard_timeout_sec,
                execution_mode=execution_mode,
            )
        endpoint = self.endpoint_registry.get(agent_id)
        if endpoint is not None:
            return ACPStdioAdapter.start(
                command=endpoint.command,
                work_dir=work_dir,
                agent_work_dir=endpoint.mapped_work_dir(work_dir),
                resume_thread_id=resume_thread_id,
                startup_timeout_sec=self.startup_timeout_sec,
                idle_timeout_sec=self.idle_timeout_sec,
                hard_timeout_sec=self.hard_timeout_sec,
                execution_mode=execution_mode,
            )
        raise ValueError(f"unknown Agent endpoint: {agent_id}")

    def open_session(
        self,
        *,
        goal_id: str,
        agent_id: str,
        work_dir: Path,
        objective: str,
        mode: str,
        channel_id: str | None = None,
        agent_goal_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        capability = next((item for item in self.capabilities() if item["agent_id"] == agent_id), None)
        if capability is None:
            raise ValueError(f"unknown Agent endpoint: {agent_id}")
        if not capability["available"]:
            raise ValueError(f"Agent endpoint is unavailable: {agent_id}")
        if mode not in {"resume_latest", "new"}:
            raise ValueError("mode must be resume_latest or new")
        selected_channel = channel_id or f"goal.{goal_id}"
        if is_manager_channel(selected_channel):
            work_dir = manager_workspace(self.store.root, selected_channel)
            objective = MANAGER_AGENT_OBJECTIVE
            agent_goal_id = MANAGER_AGENT_GOAL_ID
            if selected_channel == "manager":
                goal_id = MANAGER_AGENT_GOAL_ID
        route_goal_id = "*" if is_manager_channel(selected_channel) else goal_id
        route_key = (route_goal_id, agent_id, selected_channel)
        with self.lock:
            route_lock = self.session_open_locks.setdefault(route_key, threading.Lock())
        with route_lock:
            if mode == "resume_latest":
                latest = self.store.latest_session(
                    goal_id=None if is_manager_channel(selected_channel) else goal_id,
                    agent_id=agent_id,
                    channel_id=selected_channel,
                )
                if latest is not None:
                    self._ensure_adapter(latest, work_dir=work_dir, objective=objective)
                    return self.store.load_session(latest["session_id"]) or latest, True
            adapter = self._start_adapter(
                agent_id=agent_id,
                work_dir=work_dir,
                goal_id=agent_goal_id or goal_id,
                objective=objective,
                execution_mode=selected_channel.startswith("task."),
            )
            persisted = self.store.create_session(
                goal_id=goal_id,
                agent_id=agent_id,
                executor_endpoint_id=agent_id,
                adapter_kind=str(capability["adapter_kind"]),
                upstream_thread_id=adapter.upstream_thread_id,
                upstream_mode="chat" if agent_id == "codex" else "default",
                channel_id=selected_channel,
                codex_home=str(self.codex_home) if agent_id == "codex" else None,
            )
            if is_manager_channel(selected_channel):
                persisted = self.store.update_session(persisted["session_id"], manager_context_version=MANAGER_CONTEXT_VERSION)
            with self.lock:
                self.adapters[persisted["session_id"]] = adapter
            return persisted, False

    def _session_adapter_lock(self, session_id: str) -> threading.Lock:
        with self.lock:
            return self.session_adapter_locks.setdefault(session_id, threading.Lock())

    def _check_codex_home(self, session: dict[str, Any]) -> None:
        if session.get("agent_id") != "codex" or session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
            return
        bound_home = session.get("codex_home")
        if bound_home is not None and bound_home != str(self.codex_home):
            raise CodexChatAgentError(
                "This managed Session belongs to a different Codex home. Restart LoopX Chat "
                "with its original LOOPX_CHAT_CODEX_HOME; do not copy or rebind its history.",
                error_code="codex_home_mismatch",
                gate=None,
            )

    def _ensure_adapter(
        self,
        session: dict[str, Any],
        *,
        work_dir: Path,
        objective: str,
    ) -> ChatRuntimeAdapter:
        session_id = str(session["session_id"])
        with self._session_adapter_lock(session_id):
            return self._ensure_adapter_locked(
                session,
                work_dir=work_dir,
                objective=objective,
            )

    def _ensure_adapter_locked(
        self,
        session: dict[str, Any],
        *,
        work_dir: Path,
        objective: str,
        interrupted_turn_id: str | None = None,
    ) -> ChatRuntimeAdapter:
        session_id = str(session["session_id"])
        current_session = self.store.load_session(session_id)
        if current_session is None or current_session.get("status") == "closed":
            raise KeyError("chat session was not found")
        session = current_session
        if is_manager_channel(session.get("channel_id")):
            work_dir = manager_workspace(self.store.root, str(session["channel_id"]))
            objective = MANAGER_AGENT_OBJECTIVE
        self._check_codex_home(session)
        if session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
            raise CodexChatAgentError(
                "The attached host Session must be served by its existing host bridge.",
                error_code="attached_session_requires_host_bridge",
            )
        with self.lock:
            current = self.adapters.get(session_id)
            if current is not None and current.healthcheck():
                return current
            if current is not None:
                current.close_session()
                self.adapters.pop(session_id, None)
        self.store.update_session(session_id, status="resuming", last_error_code=None)
        active_turn_id = interrupted_turn_id or session.get("active_turn_id")
        if active_turn_id:
            active = self.store.load_turn(session_id, str(active_turn_id))
            if active and active.get("status") not in TERMINAL_TURN_STATES:
                failed = self.store.update_turn(
                    session_id,
                    str(active_turn_id),
                    expected_statuses={"queued", "starting", "running", "interrupting"},
                    status="failed",
                    error_code="server_restarted",
                    error="LoopX Chat restarted before this turn completed.",
                    completed_at=utc_now(),
                )
                if failed is not None:
                    self.store.append_event(
                        session_id,
                        str(active_turn_id),
                        kind="turn.failed",
                        payload={"error_code": "server_restarted"},
                    )
        try:
            stored_messages = self.store.messages(session_id)
            history = [
                {
                    "role": "assistant" if item.get("role") == "agent" else "user",
                    "content": str(item.get("text") or ""),
                }
                for item in stored_messages
                if item.get("role") in {"user", "agent"}
            ]
            legacy_manager_context = (
                is_manager_channel(session.get("channel_id"))
                and session.get("manager_context_version") != MANAGER_CONTEXT_VERSION
            )
            legacy_codex_goal_thread = (
                session.get("agent_id") == "codex"
                and session.get("upstream_mode") != "chat"
            )
            retry_failed_claude_session = (
                session.get("agent_id") == "claude-code"
                and (
                    session.get("last_error_code") == "provider_unavailable"
                    or bool(stored_messages and stored_messages[-1].get("role") == "error")
                )
            )
            adapter = self._start_adapter(
                agent_id=str(session["agent_id"]),
                work_dir=work_dir,
                goal_id=(
                    MANAGER_AGENT_GOAL_ID
                    if is_manager_channel(session.get("channel_id"))
                    else str(session["goal_id"])
                ),
                objective=objective,
                resume_thread_id=(
                    None
                    if legacy_codex_goal_thread or retry_failed_claude_session or legacy_manager_context
                    else str(session["upstream_thread_id"])
                ),
                history=(
                    history
                    if legacy_codex_goal_thread or retry_failed_claude_session or legacy_manager_context
                    or session.get("agent_id") in {"anthropic-api", "openai-api"}
                    else None
                ),
                execution_mode=str(session.get("channel_id") or "").startswith("task."),
            )
        except Exception as exc:
            self.store.update_session(
                session_id,
                status="resume_failed",
                active_turn_id=None,
                last_error_code="resume_failed",
            )
            gate = exc.gate if isinstance(exc, CodexChatAgentError) else None
            raise CodexChatAgentError(
                "The previous Agent conversation could not be restored.",
                error_code="resume_failed",
                gate=gate,
            ) from exc
        with self.lock:
            self.adapters[session_id] = adapter
        try:
            if session.get("agent_id") == "codex" and session.get("codex_home") is None:
                # A legacy session is bound only after successful upstream resume,
                # not when a service happens to start in a new environment.
                self.store.update_session(session_id, codex_home=str(self.codex_home))
            if is_manager_channel(session.get("channel_id")):
                changes = {"manager_context_version": MANAGER_CONTEXT_VERSION}
                if session["channel_id"] == "manager":
                    changes["goal_id"] = MANAGER_AGENT_GOAL_ID
                self.store.update_session(session_id, **changes)
            self.store.restore_managed_session_if_idle(
                session_id,
                upstream_thread_id=adapter.upstream_thread_id,
                upstream_mode=self._managed_upstream_mode(session),
            )
        except Exception:
            with self.lock:
                owns_adapter = self.adapters.get(session_id) is adapter
                if owns_adapter:
                    self.adapters.pop(session_id, None)
            if owns_adapter:
                adapter.close_session()
            raise
        return adapter

    def submit_turn(
        self,
        *,
        session_id: str,
        client_turn_id: str,
        message: str,
        attachments: list[dict[str, Any]] | None = None,
        work_dir: Path,
        objective: str,
    ) -> tuple[dict[str, Any], bool]:
        session = self.store.load_session(session_id)
        if session is None:
            raise KeyError("chat session was not found")
        if session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
            if attachments:
                raise ValueError("attached host session queue does not yet accept attachments")
            return self.store.create_queued_turn(
                session_id,
                client_turn_id=client_turn_id,
                message=message,
                origin="web",
            )
        with self._session_adapter_lock(session_id):
            adapter = self._ensure_adapter_locked(
                session,
                work_dir=work_dir,
                objective=objective,
            )
            turn, created = self.store.create_turn(
                session_id,
                client_turn_id=client_turn_id,
                message=message,
                attachments=attachments,
            )
        if not created:
            return turn, False
        worker = threading.Thread(
            target=self._run_turn,
            kwargs={
                "session_id": session_id,
                "turn_id": str(turn["turn_id"]),
                "message": message,
                "attachments": attachments or [],
                "adapter": adapter,
            },
            daemon=True,
        )
        with self.lock:
            self.turn_done_events[(session_id, str(turn["turn_id"]))] = threading.Event()
        worker.start()
        return turn, True

    def steer_active_turn(
        self,
        *,
        session_id: str,
        client_ingress_id: str,
        message: str,
    ) -> tuple[dict[str, Any], bool]:
        """Steer the exact active Codex Turn with durable ingress deduplication."""

        session = self.store.load_session(session_id)
        if session is None or session.get("status") == "closed":
            raise KeyError("chat session was not found")
        receipt, created = self.store.create_ingress_receipt(
            session_id,
            client_ingress_id=client_ingress_id,
            mode="live_steering",
            message=message,
        )
        if session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
            capabilities = session.get("attached_capabilities")
            capabilities = capabilities if isinstance(capabilities, dict) else {}
            if capabilities.get("live_steering") is not True:
                if created:
                    self.store.update_ingress_receipt(
                        session_id,
                        client_ingress_id,
                        status="failed",
                        error_code="attached_session_live_steering_unavailable",
                    )
                raise RuntimeError("attached_session_live_steering_unavailable")
        if not created:
            if receipt.get("status") == "delivered":
                delivered_turn_id = str(receipt.get("active_turn_id") or "")
                turn = self.store.load_turn(session_id, delivered_turn_id)
                if turn is None:
                    raise RuntimeError("live_steering_turn_missing")
                return turn, False
            raise RuntimeError("live_steering_delivery_unresolved")
        active_turn_id = str(session.get("active_turn_id") or "")
        if not active_turn_id:
            self.store.update_ingress_receipt(
                session_id,
                client_ingress_id,
                status="failed",
                error_code="live_steering_requires_active_turn",
            )
            raise RuntimeError("live_steering_requires_active_turn")
        with self.lock:
            adapter = self.adapters.get(session_id)
        if not isinstance(adapter, CodexAppServerAdapter) or not adapter.healthcheck():
            self.store.update_ingress_receipt(
                session_id,
                client_ingress_id,
                status="failed",
                error_code="live_steering_session_not_attached",
            )
            raise RuntimeError("live_steering_session_not_attached")
        upstream_turn_id = ""
        deadline = time.monotonic() + min(5.0, self.startup_timeout_sec)
        while time.monotonic() < deadline:
            turn = self.store.load_turn(session_id, active_turn_id)
            upstream_turn_id = str((turn or {}).get("upstream_turn_id") or "")
            if upstream_turn_id:
                break
            time.sleep(0.02)
        if not upstream_turn_id:
            self.store.update_ingress_receipt(
                session_id,
                client_ingress_id,
                status="failed",
                error_code="live_steering_turn_not_started",
            )
            raise RuntimeError("live_steering_turn_not_started")
        try:
            adapter.steer_turn(message, upstream_turn_id)
        except Exception:
            self.store.update_ingress_receipt(
                session_id,
                client_ingress_id,
                status="failed",
                error_code="live_steering_rejected",
            )
            raise
        self.store.append_message(
            session_id,
            role="user",
            text=message,
            turn_id=active_turn_id,
        )
        self.store.append_event(
            session_id,
            active_turn_id,
            kind="turn.steered",
            payload={"client_ingress_id": client_ingress_id},
        )
        self.store.update_ingress_receipt(
            session_id,
            client_ingress_id,
            status="delivered",
            active_turn_id=active_turn_id,
            error_code=None,
        )
        turn = self.store.load_turn(session_id, active_turn_id)
        if turn is None:
            raise RuntimeError("live_steering_turn_missing")
        return turn, True

    def enqueue_turn(
        self,
        *,
        session_id: str,
        client_turn_id: str,
        message: str,
        work_dir: Path,
        objective: str,
        origin: str = "external",
    ) -> tuple[dict[str, Any], bool]:
        """Persist a bounded same-Session Turn and dispatch it in FIFO order."""

        session = self.store.load_session(session_id)
        if session is None or session.get("status") == "closed":
            raise KeyError("chat session was not found")
        turn, created = self.store.create_queued_turn(
            session_id,
            client_turn_id=client_turn_id,
            message=message,
            origin=origin,
        )
        if session.get("session_mode") != CHAT_SESSION_MODE_ATTACHED:
            self.resume_session_queue(
                session_id=session_id,
                work_dir=work_dir,
                objective=objective,
            )
        return turn, created

    def resume_session_queue(
        self,
        *,
        session_id: str,
        work_dir: Path,
        objective: str,
    ) -> None:
        # Admission must not read session files: callers can hold their own
        # lifecycle fence here. The worker validates the session before effects.
        with self.lock:
            if self.closed.is_set() or session_id in self.session_queue_workers:
                return
            worker = threading.Thread(
                target=self._drain_session_queue,
                kwargs={
                    "session_id": session_id,
                    "work_dir": work_dir,
                    "objective": objective,
                },
                daemon=True,
            )
            self.session_queue_workers.add(session_id)
            self.session_queue_threads[session_id] = worker
            worker.start()

    def _drain_session_queue(
        self,
        *,
        session_id: str,
        work_dir: Path,
        objective: str,
    ) -> None:
        try:
            while not self.closed.is_set():
                session = self.store.load_session(session_id)
                if (
                    self.closed.is_set()
                    or session is None
                    or session.get("status") == "closed"
                    or session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED
                ):
                    return
                active_turn_id = str(session.get("active_turn_id") or "")
                if active_turn_id:
                    with self.lock:
                        attached = self.adapters.get(session_id)
                    if attached is None or not attached.healthcheck():
                        self._ensure_adapter(
                            session,
                            work_dir=work_dir,
                            objective=objective,
                        )
                        continue
                    active = self.store.load_turn(session_id, active_turn_id)
                    if active and active.get("status") not in TERMINAL_TURN_STATES:
                        self.closed.wait(0.05)
                        continue
                    self.store.update_session(
                        session_id,
                        status="ready",
                        active_turn_id=None,
                    )
                refreshed = self.store.load_session(session_id)
                if refreshed is None:
                    return
                adapter = self._ensure_adapter(
                    refreshed,
                    work_dir=work_dir,
                    objective=objective,
                )
                turn = self.store.claim_next_queued_turn(session_id)
                if turn is None:
                    return
                turn_id = str(turn["turn_id"])
                with self.lock:
                    self.turn_done_events[(session_id, turn_id)] = threading.Event()
                self._run_turn(
                    session_id=session_id,
                    turn_id=turn_id,
                    message=str(turn.get("message") or ""),
                    attachments=[],
                    adapter=adapter,
                )
        finally:
            with self.lock:
                self.session_queue_workers.discard(session_id)
                self.session_queue_threads.pop(session_id, None)

    def _run_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        message: str,
        attachments: list[dict[str, Any]],
        adapter: ChatRuntimeAdapter,
    ) -> None:
        started = utc_now()
        started_turn = self.store.update_turn(
            session_id,
            turn_id,
            expected_statuses={"queued"},
            status="starting",
            started_at=started,
        )
        if started_turn is None:
            with self.lock:
                self.cancelled_turns.discard((session_id, turn_id))
                done_event = self.turn_done_events.pop((session_id, turn_id), None)
            if done_event is not None:
                done_event.set()
            return
        event_buffer = _TurnEventBuffer(
            store=self.store,
            session_id=session_id,
            turn_id=turn_id,
        )
        with self.lock:
            self.turn_event_buffers[(session_id, turn_id)] = event_buffer

        def consume_interrupted() -> bool:
            key = (session_id, turn_id)
            with self.lock:
                if key not in self.cancelled_turns:
                    return False
                self.cancelled_turns.discard(key)
                return True

        def event_sink(kind: str, payload: dict[str, Any]) -> None:
            with self.lock:
                if (session_id, turn_id) in self.cancelled_turns:
                    return
            event_buffer.emit(kind, payload)

        try:
            session = self.store.load_session(session_id) or {}
            if is_manager_channel(session.get("channel_id")):
                from .chat_manager_context import collect_manager_turn_context
                event_sink("agent.phase", {"phase": "manager_context", "label": "正在读取授权范围内的 Goal 状态"})
                context = collect_manager_turn_context(
                    self.registry_path, session, self.store.root.parent, self.manager_scope_resolver,
                    **({"include_details": False} if isinstance(adapter, CodexAppServerAdapter) else {}),
                )
                self.store.append_event(session_id, turn_id, kind="manager.context", payload=context)
                if session.get("channel_id") != "manager":
                    scope_id = str(context.get("authorization_scope_id") or "")
                    if not scope_id:
                        raise CodexChatAgentError(
                            "The external manager no longer has an exact authorized Goal scope.",
                            error_code="manager_authorization_unavailable",
                            gate={
                                "kind": "host_tool_gate",
                                "summary": "The manager connection no longer authorizes an exact Goal scope.",
                                "next_action": "Reconnect the manager to the intended Goal and retry the same message.",
                            },
                        )
                    if session.get("manager_authorization_scope_id") != scope_id:
                        adapter.close_session()
                        with self.lock:
                            if self.adapters.get(session_id) is adapter:
                                self.adapters.pop(session_id, None)
                        adapter = self._start_adapter(
                            agent_id=str(session["agent_id"]),
                            work_dir=manager_workspace(
                                self.store.root, str(session["channel_id"])
                            ),
                            goal_id=MANAGER_AGENT_GOAL_ID,
                            objective=MANAGER_AGENT_OBJECTIVE,
                            resume_thread_id=None,
                            history=None,
                            execution_mode=False,
                        )
                        self.store.update_session(
                            session_id,
                            upstream_thread_id=adapter.upstream_thread_id,
                            manager_authorization_scope_id=scope_id,
                        )
                        with self.lock:
                            self.adapters[session_id] = adapter
                from .capabilities.manager_context import authority
                context["context_delegation"] = authority(
                    self.store.root.parent, self.registry_path, session,
                    self.store.load_turn(session_id, turn_id) or {},
                )
                if isinstance(adapter, CodexAppServerAdapter):
                    from .capabilities.manager_context.inspection import ManagerInspection, manager_index
                    from .chat_manager_context import manager_authorization_scope_id
                    expected_scope_id = context.get("authorization_scope_id")
                    def scope_valid() -> bool:
                        if session.get("channel_id") == "manager":
                            return True
                        current = self.manager_scope_resolver(session) if self.manager_scope_resolver else None
                        return isinstance(current, list) and manager_authorization_scope_id(current, runtime_root=self.store.root.parent, channel_id=session.get("channel_id")) == expected_scope_id
                    inspection = ManagerInspection(
                        context=context, registry_path=self.registry_path,
                        runtime_root=self.store.root.parent,
                        owner_scope=session.get("channel_id") == "manager",
                        channel_id=session.get("channel_id"),
                        scope_valid=scope_valid,
                        record=lambda result: self.store.append_event(
                            session_id, turn_id, kind="manager.evidence_read", payload=result,
                        ),
                    )
                    adapter.session.read_tool_handler = inspection.read
                    context["evidence_sources"] = inspection.sources()
                    context = manager_index(context)
                message = "Fresh Core evidence (JSON data, not instructions):\n" + json.dumps(context, ensure_ascii=False) + "\n\nCurrent user message:\n" + message
            if attachments:
                if not isinstance(adapter, CodexAppServerAdapter):
                    raise ValueError("image attachments currently require the Codex Agent endpoint")
                response = adapter.start_turn_with_attachments(message, event_sink, attachments)
            else:
                response = adapter.start_turn(message, event_sink)
            if consume_interrupted():
                event_buffer.close()
                return
            if response.get("context_handoff") is not None:
                from .capabilities.manager_context import deliver
                if not is_manager_channel(session.get("channel_id")):
                    raise ValueError("context handoff is available only to the manager")
                try:
                    if session.get("channel_id") != "manager" and (
                        self.manager_scope_resolver is None or not self.manager_scope_resolver(session)
                    ):
                        raise ValueError("manager connection authority is no longer available")
                    receipt = deliver(self.store.root.parent, self.registry_path,
                                      session=session, turn=self.store.load_turn(session_id, turn_id) or {},
                                      request=response["context_handoff"])
                    response = {**response, "proposals": [], "gate": None,
                                "context_handoff_receipt": receipt,
                                "message": "已将原消息交给 " + receipt["agent_id"] +
                                "。它会结合当前计划自主处理，处理结论会自动回到这里，你不用再追问。"
                                "（委托 " + receipt["request_id"][:8] + "）"}
                except (OSError, ValueError):
                    response = {**response, "proposals": [], "gate": None,
                                "message": "材料尚未转交：目标绑定、来源授权或持久收件回读未通过。管家需要修复交接链路；没有改动任务或优先级。"}
            event_buffer.close()
            if consume_interrupted():
                return
            completed = utc_now()
            completed_turn = self.store.update_turn(
                session_id,
                turn_id,
                expected_statuses={"starting", "running"},
                status="completing",
                response=response,
                completed_at=completed,
                last_activity_at=completed,
            )
            if completed_turn is None:
                consume_interrupted()
                return
            if adapter.upstream_thread_id != str((self.store.load_session(session_id) or {}).get("upstream_thread_id") or ""):
                self.store.update_session(session_id, upstream_thread_id=adapter.upstream_thread_id)
            self.store.finalize_managed_turn_completion(
                session_id,
                turn_id,
            )
        except CodexChatTimeoutError as exc:
            event_buffer.close()
            if consume_interrupted():
                return
            try:
                adapter.interrupt_turn()
            except Exception:
                pass
            self._fail_turn(session_id, turn_id, exc.error_code, str(exc), status="timed_out")
        except CodexChatAgentError as exc:
            event_buffer.close()
            if consume_interrupted():
                return
            self._fail_turn(session_id, turn_id, exc.error_code, str(exc), status="failed", gate=exc.gate)
            if not adapter.healthcheck():
                with self.lock:
                    self.adapters.pop(session_id, None)
                self.store.update_session(session_id, status="stale", last_error_code="transport_disconnected")
        except Exception as exc:  # noqa: BLE001 - preserve compact runtime failure.
            event_buffer.close()
            if consume_interrupted():
                return
            self._fail_turn(session_id, turn_id, "runtime_error", str(exc), status="failed")
        finally:
            event_buffer.close()
            with self.lock:
                self.turn_event_buffers.pop((session_id, turn_id), None)
                done_event = self.turn_done_events.pop((session_id, turn_id), None)
            if done_event is not None:
                done_event.set()

    def _fail_turn(
        self,
        session_id: str,
        turn_id: str,
        error_code: str,
        message: str,
        *,
        status: str,
        gate: dict[str, Any] | None = None,
    ) -> None:
        completed = utc_now()
        failed = self.store.update_turn(
            session_id,
            turn_id,
            expected_statuses={"starting", "running"},
            status=status,
            error_code=error_code,
            error=message,
            completed_at=completed,
            last_activity_at=completed,
        )
        if failed is None:
            return
        payload: dict[str, Any] = {"error_code": error_code, "message": message}
        if gate:
            payload["gate"] = gate
        self.store.append_event(session_id, turn_id, kind="turn.failed", payload=payload)
        self.store.append_message(session_id, role="error", text=message, turn_id=turn_id)
        self.store.release_active_turn(
            session_id,
            turn_id,
            last_activity_at=completed,
            last_error_code=error_code,
        )

    def interrupt_turn(self, *, session_id: str, turn_id: str) -> dict[str, Any]:
        turn = self.store.load_turn(session_id, turn_id)
        if turn is None:
            raise KeyError("chat turn was not found")
        if turn.get("status") in TERMINAL_TURN_STATES:
            return turn
        interrupting = self.store.update_turn(
            session_id,
            turn_id,
            expected_statuses={"queued", "starting", "running"},
            status="interrupting",
        )
        if interrupting is None:
            current = self.store.load_turn(session_id, turn_id)
            if current is None:
                raise KeyError("chat turn was not found")
            if current.get("status") == "completing":
                return self.store.finalize_turn_completion(
                    session_id,
                    turn_id,
                ) or current
            return current
        session = self.store.load_session(session_id)
        target_is_active = bool(session and session.get("active_turn_id") == turn_id)
        with self.lock:
            adapter = self.adapters.get(session_id)
            event_buffer = self.turn_event_buffers.get((session_id, turn_id))
            done_event = self.turn_done_events.get((session_id, turn_id))
            self.cancelled_turns.add((session_id, turn_id))
        if adapter is not None and target_is_active:
            try:
                adapter.interrupt_turn(str(turn.get("upstream_turn_id") or "") or None)
            except Exception:
                pass
        if event_buffer is not None:
            event_buffer.close()
        if done_event is not None and not done_event.wait(timeout=5.0):
            # A notification-only interrupt can be lost when an upstream runtime
            # is unhealthy. Stop that transport before making the Session ready;
            # the next Turn will resume the persisted upstream thread on a fresh
            # adapter instead of racing two readers on one event stream.
            if adapter is not None and target_is_active:
                try:
                    adapter.close_session()
                except Exception:
                    pass
            with self.lock:
                if target_is_active and self.adapters.get(session_id) is adapter:
                    self.adapters.pop(session_id, None)
            done_event.wait(timeout=1.0)
        completed = utc_now()
        updated = self.store.update_turn(
            session_id,
            turn_id,
            expected_statuses={"interrupting"},
            status="interrupted",
            completed_at=completed,
            last_activity_at=completed,
        )
        with self.lock:
            self.cancelled_turns.discard((session_id, turn_id))
        if updated is None:
            current = self.store.load_turn(session_id, turn_id)
            if current is None:
                raise KeyError("chat turn was not found")
            return current
        self.store.append_event(session_id, turn_id, kind="turn.interrupted", payload={})
        self.store.append_message(
            session_id,
            role="agent",
            text="已中断。你可以在当前会话继续发送消息。",
            turn_id=turn_id,
        )
        if target_is_active:
            self.store.release_active_turn(
                session_id,
                turn_id,
                last_activity_at=completed,
                last_error_code=None,
            )
        return updated

    def wait_for_turn(self, *, session_id: str, turn_id: str, timeout_sec: float = 920.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            turn = self.store.load_turn(session_id, turn_id)
            if turn is None:
                raise KeyError("chat turn was not found")
            if turn.get("status") in TERMINAL_TURN_STATES:
                return turn
            time.sleep(0.02)
        raise TimeoutError("chat turn wait timed out")

    def close_session(self, session_id: str) -> bool:
        with self._session_adapter_lock(session_id):
            session = self.store.load_session(session_id)
            if session is None:
                return False
            if session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
                return self.store.close_attached_session(session_id)
            closed = self.store.close_managed_session(session_id)
            if not closed:
                return False
            with self.lock:
                adapter = self.adapters.pop(session_id, None)
                event_buffers = [
                    buffer
                    for (buffer_session_id, _), buffer in self.turn_event_buffers.items()
                    if buffer_session_id == session_id
                ]
            for event_buffer in event_buffers:
                event_buffer.close()
            if adapter is not None:
                adapter.close_session()
            return True

    def resume_session(self, *, session_id: str, work_dir: Path, objective: str) -> dict[str, Any]:
        with self._session_adapter_lock(session_id):
            session = self.store.load_session(session_id)
            if session is None or session.get("status") == "closed":
                raise KeyError("chat session was not found")
            self._check_codex_home(session)
            if session.get("session_mode") == CHAT_SESSION_MODE_ATTACHED:
                if session.get("active_turn_id"):
                    return session
                restored = self.store.update_session(
                    session_id,
                    status="ready",
                    active_turn_id=None,
                    last_error_code=None,
                )
                return restored
            with self.lock:
                current = self.adapters.get(session_id)
                adapter_healthy = current is not None and current.healthcheck()
            session, active_turn_preserved = self.store.prepare_managed_session_resume(
                session_id,
                preserve_active_turn=adapter_healthy,
            )
            if active_turn_preserved:
                return session
            interrupted_turn_id = str(session.get("active_turn_id") or "") or None
            adapter = self._ensure_adapter_locked(
                session,
                work_dir=work_dir,
                objective=objective,
                interrupted_turn_id=interrupted_turn_id,
            )
            try:
                return self.store.restore_managed_session_if_idle(
                    session_id,
                    upstream_thread_id=adapter.upstream_thread_id,
                    upstream_mode=self._managed_upstream_mode(session),
                )
            except KeyError:
                with self.lock:
                    owns_adapter = self.adapters.get(session_id) is adapter
                    if owns_adapter:
                        self.adapters.pop(session_id, None)
                if owns_adapter:
                    adapter.close_session()
                raise

    def close(self) -> None:
        self.closed.set()
        with self.lock:
            adapters = list(self.adapters.values())
            event_buffers = list(self.turn_event_buffers.values())
            done_events = list(self.turn_done_events.values())
            queue_threads = list(self.session_queue_threads.values())
            self.adapters.clear()
            self.turn_event_buffers.clear()
        for done_event in done_events:
            done_event.wait(timeout=0.5)
        for event_buffer in event_buffers:
            event_buffer.close()
        for adapter in adapters:
            adapter.close_session()
        for done_event in done_events:
            done_event.wait(timeout=1.0)
        for queue_thread in queue_threads:
            queue_thread.join(timeout=1.0)
